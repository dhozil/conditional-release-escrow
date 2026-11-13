"""Direct-mode tests for the ConditionalReleaseEscrow contract."""

import hashlib
import json
import re
from datetime import datetime, timedelta

from gltest.direct import create_address

ESCROW_ID = "e0"
RECIPIENT_ADDR = create_address("recipient")
DEPOSITOR_ADDR = create_address("depositor")
RECIPIENT = "0x" + RECIPIENT_ADDR.hex()
DEPOSITOR = "0x" + DEPOSITOR_ADDR.hex()
AMOUNT = 1000
CONDITION_TEXT = "Deliverable published at evidence URL and API docs show 99% test coverage."
EVIDENCE_URL = "https://docs.example.com/deliverable"

JUDGE_APPROVE_JSON = json.dumps({"score": 70, "reasoning": "Condition satisfied by evidence."})
JUDGE_DENY_JSON = json.dumps({"score": 30, "reasoning": "Condition not satisfied by evidence."})


def _create_escrow(
    contract,
    vm,
    depositor=DEPOSITOR,
    recipient=RECIPIENT,
    amount=AMOUNT,
    condition="llm",
    release_after_seconds=3600,
    condition_text=CONDITION_TEXT,
    evidence_url=EVIDENCE_URL,
):
    vm.sender = DEPOSITOR_ADDR
    vm.value = amount
    return contract.create_escrow(
        escrow_id=ESCROW_ID,
        depositor=depositor,
        recipient=recipient,
        amount=amount,
        condition=condition,
        release_after_seconds=release_after_seconds,
        condition_text=condition_text,
        evidence_url=evidence_url,
    )


def test_create_escrow_validates(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    direct_vm.sender = DEPOSITOR_ADDR
    direct_vm.value = AMOUNT

    with direct_vm.expect_revert("Escrow id is required"):
        contract.create_escrow(escrow_id="", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600, condition_text=CONDITION_TEXT, evidence_url=EVIDENCE_URL)
    with direct_vm.expect_revert("Depositor and recipient are required"):
        contract.create_escrow(escrow_id="e0", depositor="", recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600, condition_text=CONDITION_TEXT, evidence_url=EVIDENCE_URL)
    with direct_vm.expect_revert("Condition must be 'llm' or 'time'"):
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="bogus", release_after_seconds=3600, condition_text=CONDITION_TEXT, evidence_url=EVIDENCE_URL)
    with direct_vm.expect_revert("Explicit condition text is required"):
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600, condition_text="", evidence_url=EVIDENCE_URL)
    with direct_vm.expect_revert("Evidence URL is required for llm condition"):
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600, condition_text=CONDITION_TEXT, evidence_url="")
    with direct_vm.expect_revert("Escrow amount must be > 0"):
        direct_vm.value = 0
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600, condition_text=CONDITION_TEXT, evidence_url=EVIDENCE_URL)
    direct_vm.value = 5
    with direct_vm.expect_revert("Escrow funding must equal the escrow total"):
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600, condition_text=CONDITION_TEXT, evidence_url=EVIDENCE_URL)
    direct_vm.value = AMOUNT
    with direct_vm.expect_revert("Escrow funding must equal the escrow total"):
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=5, condition="llm", release_after_seconds=3600, condition_text=CONDITION_TEXT, evidence_url=EVIDENCE_URL)
    with direct_vm.expect_revert("Release window must be at least 1 second"):
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="time", release_after_seconds=0, condition_text=CONDITION_TEXT, evidence_url="")

    rid = _create_escrow(contract, direct_vm, condition="llm")
    r = contract.get_escrow(rid)
    expected_hash = hashlib.sha256(f"{EVIDENCE_URL}|{CONDITION_TEXT}".encode()).hexdigest()
    assert r["status"] == "open"
    assert r["amount"] == AMOUNT
    assert r["condition"] == "llm"
    assert r["condition_text"] == CONDITION_TEXT
    assert r["evidence_url"] == EVIDENCE_URL
    assert r["evidence_hash"] == expected_hash
    assert r["judgment_approved"] is False


def test_release_by_time(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    rid = _create_escrow(contract, direct_vm, condition="time", release_after_seconds=3600)

    with direct_vm.expect_revert("Release window has not reached"):
        contract.release_escrow(escrow_id=rid)

    direct_vm.warp((datetime.now() + timedelta(seconds=7200)).isoformat())
    res = contract.release_escrow(escrow_id=rid)
    assert bool(res.get("released")) is True
    r = contract.get_escrow(rid)
    assert r["status"] == "released"
    assert r["judgment_approved"] is True


def test_release_by_llm_consensus(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    rid = _create_escrow(contract, direct_vm, condition="llm", release_after_seconds=3600)

    direct_vm.mock_web(re.escape(EVIDENCE_URL), {"status": 200, "body": "Deliverable published; API docs show 99% coverage."})
    direct_vm.mock_llm(re.escape("You are an escrow arbiter"), JUDGE_APPROVE_JSON)
    res = contract.release_escrow(escrow_id=rid)
    assert bool(res.get("released")) is True
    r = contract.get_escrow(rid)
    assert r["status"] == "released"
    assert r["judgment_approved"] is True
    assert r["judgment_denied"] is False
    assert r["judgment_score"] == 70


def test_release_llm_denied_records_denial_then_refund(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    rid = _create_escrow(contract, direct_vm, condition="llm", release_after_seconds=3600)

    direct_vm.mock_web(re.escape(EVIDENCE_URL), {"status": 200, "body": "Deliverable missing; no coverage report."})
    direct_vm.mock_llm(re.escape("You are an escrow arbiter"), JUDGE_DENY_JSON)
    res = contract.release_escrow(escrow_id=rid)
    assert bool(res.get("released")) is False
    assert bool(res.get("denied")) is True
    r = contract.get_escrow(rid)
    assert r["status"] == "open"
    assert r["judgment_denied"] is True
    assert r["judgment_approved"] is False
    assert r["judgment_score"] == 30

    # Depositor can refund after explicit recorded denial.
    direct_vm.sender = DEPOSITOR_ADDR
    ref = contract.refund_escrow(escrow_id=rid)
    assert bool(ref.get("refunded")) is True
    assert contract.get_escrow(rid)["status"] == "refunded"


def test_release_llm_unreachable_evidence_records_denial(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    rid = _create_escrow(contract, direct_vm, condition="llm", release_after_seconds=3600)

    direct_vm.mock_web(re.escape(EVIDENCE_URL), {"status": 404, "body": "not found"})
    direct_vm.mock_llm(re.escape("You are an escrow arbiter"), JUDGE_DENY_JSON)
    res = contract.release_escrow(escrow_id=rid)
    assert bool(res.get("released")) is False
    assert bool(res.get("denied")) is True
    r = contract.get_escrow(rid)
    assert r["status"] == "open"
    assert r["judgment_denied"] is True
    assert r["judgment_score"] == 0


def test_refund_premature_and_unauthorized_fail(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    stranger = create_address("stranger")

    # Time: premature refund before expiry fails.
    rid_time = _create_escrow(contract, direct_vm, condition="time", release_after_seconds=7200)
    direct_vm.sender = DEPOSITOR_ADDR
    with direct_vm.expect_revert("Release window not yet expired; cannot refund prematurely"):
        contract.refund_escrow(escrow_id=rid_time)

    # Time: unauthorized refund by stranger fails (even after expiry).
    direct_vm.warp((datetime.now() + timedelta(seconds=9000)).isoformat())
    direct_vm.sender = stranger
    with direct_vm.expect_revert("Only depositor can refund"):
        contract.refund_escrow(escrow_id=rid_time)

    # Time: eligible refund by depositor after expiry succeeds.
    direct_vm.sender = DEPOSITOR_ADDR
    res = contract.refund_escrow(escrow_id=rid_time)
    assert bool(res.get("refunded")) is True
    assert contract.get_escrow(rid_time)["status"] == "refunded"

    # LLM: premature refund before explicit recorded denial fails.
    direct_vm.sender = DEPOSITOR_ADDR
    rid_llm = "e1"
    direct_vm.value = AMOUNT
    contract.create_escrow(
        escrow_id=rid_llm, depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT,
        condition="llm", release_after_seconds=3600,
        condition_text=CONDITION_TEXT, evidence_url=EVIDENCE_URL,
    )
    with direct_vm.expect_revert("No explicit recorded denial; cannot refund prematurely"):
        contract.refund_escrow(escrow_id=rid_llm)

    # LLM: unauthorized refund by stranger fails (even after recorded denial).
    direct_vm.mock_web(re.escape(EVIDENCE_URL), {"status": 200, "body": "No deliverable."})
    direct_vm.mock_llm(re.escape("You are an escrow arbiter"), JUDGE_DENY_JSON)
    contract.release_escrow(escrow_id=rid_llm)
    direct_vm.sender = stranger
    with direct_vm.expect_revert("Only depositor can refund"):
        contract.refund_escrow(escrow_id=rid_llm)

    # LLM: eligible refund by depositor after recorded denial succeeds.
    direct_vm.sender = DEPOSITOR_ADDR
    ref = contract.refund_escrow(escrow_id=rid_llm)
    assert bool(ref.get("refunded")) is True
    assert contract.get_escrow(rid_llm)["status"] == "refunded"


def test_refund_after_release_not_open(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    rid = _create_escrow(contract, direct_vm, condition="time", release_after_seconds=3600)

    direct_vm.warp((datetime.now() + timedelta(seconds=7200)).isoformat())
    contract.release_escrow(escrow_id=rid)

    direct_vm.sender = DEPOSITOR_ADDR
    with direct_vm.expect_revert("Escrow is not open"):
        contract.refund_escrow(escrow_id=rid)


def test_create_escrow_auth_address_and_duplicate_guards(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    stranger = create_address("stranger")

    direct_vm.sender = stranger
    direct_vm.value = AMOUNT
    with direct_vm.expect_revert("Only depositor can create an escrow"):
        contract.create_escrow(escrow_id="e9", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600, condition_text=CONDITION_TEXT, evidence_url=EVIDENCE_URL)

    direct_vm.sender = DEPOSITOR_ADDR
    with direct_vm.expect_revert("Invalid Ethereum address"):
        contract.create_escrow(escrow_id="e9", depositor="0x123", recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600, condition_text=CONDITION_TEXT, evidence_url=EVIDENCE_URL)
    with direct_vm.expect_revert("Depositor and recipient must differ"):
        contract.create_escrow(escrow_id="e9", depositor=DEPOSITOR, recipient=DEPOSITOR, amount=AMOUNT, condition="llm", release_after_seconds=3600, condition_text=CONDITION_TEXT, evidence_url=EVIDENCE_URL)

    cid = _create_escrow(contract, direct_vm)
    assert cid == ESCROW_ID
    with direct_vm.expect_revert("Escrow already exists"):
        _create_escrow(contract, direct_vm)
