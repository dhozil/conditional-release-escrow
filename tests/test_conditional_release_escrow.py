"""Direct-mode tests for the ConditionalReleaseEscrow contract."""

import json
import re
from datetime import datetime, timedelta

from gltest.direct import create_address

ESCROW_ID = "e0"
RECIPIENT = "0x646454E139609564ae2bbDA7762bB4ADaA01B467"
DEPOSITOR = "0x646454E139609564ae2bbDA7762bB4ADaA01B467"
AMOUNT = 1000

JUDGE_APPROVE_JSON = json.dumps({"score": 70, "reasoning": "Condition satisfied."})
JUDGE_DENY_JSON = json.dumps({"score": 30, "reasoning": "Condition not satisfied."})


def _create_escrow(
    contract,
    vm,
    depositor=DEPOSITOR,
    recipient=RECIPIENT,
    amount=AMOUNT,
    condition="llm",
    release_after_seconds=3600,
):
    vm.sender = depositor
    vm.value = amount
    return contract.create_escrow(
        escrow_id=ESCROW_ID,
        depositor=depositor,
        recipient=recipient,
        amount=amount,
        condition=condition,
        release_after_seconds=release_after_seconds,
    )


def test_create_escrow_validates(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    direct_vm.value = AMOUNT

    with direct_vm.expect_revert("Escrow id is required"):
        contract.create_escrow(escrow_id="", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600)
    with direct_vm.expect_revert("Depositor and recipient are required"):
        contract.create_escrow(escrow_id="e0", depositor="", recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600)
    with direct_vm.expect_revert("Condition must be 'llm' or 'time'"):
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="bogus", release_after_seconds=3600)
    with direct_vm.expect_revert("Escrow amount must be > 0"):
        direct_vm.value = 0
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600)
    direct_vm.value = 5
    with direct_vm.expect_revert("Escrow funding must equal the escrow total"):
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="llm", release_after_seconds=3600)
    direct_vm.value = AMOUNT
    with direct_vm.expect_revert("Escrow funding must equal the escrow total"):
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=5, condition="llm", release_after_seconds=3600)
    direct_vm.value = AMOUNT
    with direct_vm.expect_revert("Release window must be at least 1 second"):
        contract.create_escrow(escrow_id="e0", depositor=DEPOSITOR, recipient=RECIPIENT, amount=AMOUNT, condition="time", release_after_seconds=0)

    rid = _create_escrow(contract, direct_vm, condition="llm")
    r = contract.get_escrow(rid)
    assert r["status"] == "open"
    assert r["amount"] == AMOUNT
    assert r["condition"] == "llm"
    assert r["judgment_approved"] is False


def test_release_by_time(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    rid = _create_escrow(contract, direct_vm, condition="time", release_after_seconds=3600)

    with direct_vm.expect_revert("Release window has not reached"):
        contract.release_escrow(escrow_id=rid)

    direct_vm.warp((datetime.now() + timedelta(seconds=7200)).isoformat())
    res = contract.release_escrow(escrow_id=rid)
    assert bool(res.get("released")) is True
    assert contract.get_escrow(rid)["status"] == "released"


def test_release_by_llm_consensus(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    rid = _create_escrow(contract, direct_vm, condition="llm", release_after_seconds=3600)

    direct_vm.mock_llm(re.escape("You are an escrow arbiter"), JUDGE_APPROVE_JSON)
    res = contract.release_escrow(escrow_id=rid)
    assert bool(res.get("released")) is True
    assert contract.get_escrow(rid)["status"] == "released"


def test_release_llm_denied_then_refund(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    rid = _create_escrow(contract, direct_vm, condition="llm", release_after_seconds=3600)

    direct_vm.mock_llm(re.escape("You are an escrow arbiter"), JUDGE_DENY_JSON)
    with direct_vm.expect_revert("Escrow condition not satisfied"):
        contract.release_escrow(escrow_id=rid)

    res = contract.refund_escrow(escrow_id=rid)
    assert bool(res.get("refunded")) is True
    assert contract.get_escrow(rid)["status"] == "refunded"


def test_refund_before_time_release_window(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    rid = _create_escrow(contract, direct_vm, condition="time", release_after_seconds=7200)

    res = contract.refund_escrow(escrow_id=rid)
    assert bool(res.get("refunded")) is True
    assert contract.get_escrow(rid)["status"] == "refunded"


def test_refund_after_release_not_open(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/conditional_release_escrow.py")
    rid = _create_escrow(contract, direct_vm, condition="time", release_after_seconds=3600)

    direct_vm.warp((datetime.now() + timedelta(seconds=7200)).isoformat())
    contract.release_escrow(escrow_id=rid)

    with direct_vm.expect_revert("Escrow is not open"):
        contract.refund_escrow(escrow_id=rid)
