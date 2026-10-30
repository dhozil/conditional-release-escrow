# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from genlayer import *

MAX_ESCROWS = 100
MAX_REFUND_WINDOW_DAYS = 30
STATUS_OPEN = "open"
STATUS_RELEASED = "released"
STATUS_REFUNDED = "refunded"

SCORE_TOLERANCE = 5
RELEASE_SCORE_THRESHOLD = 50
JUDGE_WINDOW_DAYS = 3


@allow_storage
@dataclass
class Escrow:
    id: str
    depositor: str
    recipient: str
    amount: u256
    condition: str
    status: str
    judgment_approved: bool
    created_at: str
    release_deadline: str


def _escrow_to_dict(e: Escrow) -> dict:
    return {
        "id": e.id,
        "depositor": e.depositor,
        "recipient": e.recipient,
        "amount": int(e.amount),
        "condition": e.condition,
        "status": e.status,
        "judgment_approved": e.judgment_approved,
        "created_at": e.created_at,
        "release_deadline": e.release_deadline,
    }


def _payout(recipient_hex: str, amount: u256) -> None:
    _PayableRecipient(Address(recipient_hex)).emit_transfer(value=u256(int(amount)))


@gl.evm.contract_interface
class _PayableRecipient:
    class View:
        pass

    class Write:
        pass


def _exec_prompt_json(prompt: str) -> dict:
    res = gl.nondet.exec_prompt(prompt, response_format="json")
    if not isinstance(res, dict):
        try:
            res = res.get()
        except Exception:
            res = None
    return res if isinstance(res, dict) else {}


def _build_judge_prompt(e: Escrow) -> str:
    return f"""
You are an escrow arbiter. Decide whether the condition for releasing escrow
is satisfied.

ESCROW ID: {e.id}
CONDITION: {e.condition}
DEPOSITOR: {e.depositor}
RECIPIENT: {e.recipient}
AMOUNT: {int(e.amount)}

TIME RELEASE DEADLINE: {e.release_deadline}

TASK:
1. Determine whether the escrow condition is satisfied.
2. Score the satisfaction from 0 to 100 (0 = not satisfied, 100 = fully satisfied).

Respond ONLY with valid JSON:
{{
    "score": 70,
    "reasoning": "Detailed explanation of the judgment"
}}
"""


class ConditionalReleaseEscrow(gl.Contract):
    next_escrow_id: u256
    escrows: TreeMap[str, Escrow]

    def __init__(self) -> None:
        self.next_escrow_id = u256(0)
        self.escrows = gl.storage.inmem_allocate(TreeMap[str, Escrow])

    @gl.public.write.payable
    def create_escrow(
        self,
        escrow_id: str,
        depositor: str,
        recipient: str,
        amount: int,
        condition: str,
        release_after_seconds: int,
    ) -> str:
        if not escrow_id.strip():
            raise gl.vm.UserError("Escrow id is required")
        if not depositor.strip() or not recipient.strip():
            raise gl.vm.UserError("Depositor and recipient are required")
        if int(gl.message.value) <= 0:
            raise gl.vm.UserError("Escrow amount must be > 0")
        if int(amount) <= 0 or int(gl.message.value) != int(amount):
            raise gl.vm.UserError("Escrow funding must equal the escrow total")
        if condition not in ("llm", "time"):
            raise gl.vm.UserError("Condition must be 'llm' or 'time'")
        if release_after_seconds < 1:
            raise gl.vm.UserError("Release window must be at least 1 second")
        if int(self.next_escrow_id) >= MAX_ESCROWS:
            raise gl.vm.UserError("Escrow limit reached")

        self.next_escrow_id = u256(int(self.next_escrow_id) + 1)
        deadline = (datetime.now() + timedelta(seconds=release_after_seconds)).isoformat()
        self.escrows[escrow_id.strip()] = Escrow(
            id=escrow_id.strip(),
            depositor=depositor.strip(),
            recipient=recipient.strip(),
            amount=u256(int(gl.message.value)),
            condition=condition.strip(),
            status=STATUS_OPEN,
            judgment_approved=False,
            created_at=str(datetime.now()),
            release_deadline=deadline,
        )
        return escrow_id.strip()

    @gl.public.write
    def release_escrow(self, escrow_id: str) -> dict:
        """Release (condition satisfied) or refuse. Permissionless crank."""
        if not escrow_id.strip():
            raise gl.vm.UserError("Escrow id is required")
        if escrow_id.strip() not in self.escrows:
            raise gl.vm.UserError("Escrow not found")
        e = self.escrows[escrow_id.strip()]
        if e.status != STATUS_OPEN:
            raise gl.vm.UserError("Escrow is not open")

        approved = False
        if e.condition == "time":
            if datetime.now() < datetime.fromisoformat(e.release_deadline):
                raise gl.vm.UserError("Release window has not reached")
            approved = True
        else:
            def judge_fn() -> dict:
                prompt = _build_judge_prompt(e)
                raw_res = _exec_prompt_json(prompt)
                if not raw_res:
                    return {"score": 0, "reasoning": "Invalid response; scored 0."}
                try:
                    score = int(float(raw_res.get("score", 0)))
                except (ValueError, TypeError, OverflowError):
                    score = 0
                if score < 0:
                    score = 0
                if score > 100:
                    score = 100
                score = ((score + 5) // 10) * 10
                if score > 100:
                    score = 100
                reasoning = str(raw_res.get("reasoning", ""))[:2000]
                return {"score": score, "reasoning": reasoning}

            def validator_fn(leader_result) -> bool:
                if not isinstance(leader_result, gl.vm.Return):
                    return False
                ld = leader_result.calldata
                if not isinstance(ld, dict):
                    return False
                if "score" not in ld:
                    return False
                ld_score = ld["score"]
                if not isinstance(ld_score, int) or ld_score % 10 != 0:
                    return False
                if ld_score < 0 or ld_score > 100:
                    return False
                my = judge_fn()
                if abs(my["score"] - ld_score) > SCORE_TOLERANCE:
                    return False
                return True

            result = gl.vm.run_nondet_unsafe(judge_fn, validator_fn)
            approved = int(result["score"]) >= RELEASE_SCORE_THRESHOLD

        if not approved:
            raise gl.vm.UserError("Escrow condition not satisfied")

        e.status = STATUS_RELEASED
        e.judgment_approved = True
        _payout(e.recipient, e.amount)
        return {"escrow_id": e.id, "released": True, "amount": int(e.amount)}

    @gl.public.write
    def refund_escrow(self, escrow_id: str) -> dict:
        """Refund depositor while open (llm denied, or time not yet reached)."""
        if not escrow_id.strip():
            raise gl.vm.UserError("Escrow id is required")
        if escrow_id.strip() not in self.escrows:
            raise gl.vm.UserError("Escrow not found")
        e = self.escrows[escrow_id.strip()]
        if e.status != STATUS_OPEN:
            raise gl.vm.UserError("Escrow is not open")

        if e.condition == "time":
            if datetime.now() >= datetime.fromisoformat(e.release_deadline):
                raise gl.vm.UserError("Release window already reached; release instead")
        else:
            if e.judgment_approved:
                raise gl.vm.UserError("Judgment already approved; release instead")

        e.status = STATUS_REFUNDED
        _payout(e.depositor, e.amount)
        return {"escrow_id": e.id, "refunded": True, "amount": int(e.amount)}

    @gl.public.view
    def get_escrow(self, escrow_id: str) -> dict:
        if not escrow_id.strip():
            raise gl.vm.UserError("Escrow id is required")
        if escrow_id.strip() not in self.escrows:
            raise gl.vm.UserError("Escrow not found")
        return _escrow_to_dict(self.escrows[escrow_id.strip()])

    @gl.public.view
    def get_all_escrows(self) -> dict:
        return {k: _escrow_to_dict(v) for k, v in self.escrows.items()}
