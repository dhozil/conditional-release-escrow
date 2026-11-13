<div align="center">

# ConditionalReleaseEscrow

**AI-judged conditional release escrow: lock funds, release when the condition is satisfied via LLM-consensus judgment or a deterministic time gate.

![GenLayer](https://img.shields.io/badge/GenLayer-Intelligent%20Contract-6a4cff)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![Status](https://img.shields.io/badge/status-live%20on%20studionet-2ea44f)
![Tests](https://img.shields.io/badge/tests-8%20passed-2ea44f)

[Live Contract](https://explorer-studio.genlayer.com/address/0x1F25Fd52468091e5a3b410669Ae33867634739F8) 

[GenLayer Docs](https://docs.genlayer.com)

</div>

---

## Why

Escrowed funds that depend on an external condition (AI task approval, milestone
satisfaction, arbitration outcome) need a deterministic, consensus-backed release
path so that nobody can unlock funds arbitrarily and nobody is locked out forever.

ConditionalReleaseEscrow closes the loop: a depositor locks value in escrow,
then either:

- the condition is satisfied by an **LLM consensus judgment** (release), or
- the condition is satisfied by a **deterministic time gate** (release),

and on failure the depositor is made whole via an escrow refund.

## Live Deployment

| | |
|---|---|
| **Contract** | [ConditionalReleaseEscrow](https://explorer-studio.genlayer.com/address/0x1F25Fd52468091e5a3b410669Ae33867634739F8) |
| **Address** | `0x1F25Fd52468091e5a3b410669Ae33867634739F8` |
| **Network** | GenLayer studionet (chain `61999`) |
| **Status** | Deployed + verified on-chain |

## Highlights

- **Explicit condition + acquired evidence (staff fix)**: every escrow stores a `condition_text` (the real condition to verify) and an `evidence_url` hash-bound as `sha256(url|condition_text)`; the judge does NOT see only a label — the contract fetches the evidence URL itself (`gl.nondet.web.get`) and feeds the *fetched content* to the LLM, and each validator independently re-fetches the same URL
- **Conditional release**: escrow releases to the recipient when the explicit condition is satisfied, either by deterministic time gate or by LLM-consensus judgment (score >= 50)
- **Bounded windows**: release window enforced with deterministic time gates; refunds are allowed only after an **explicit recorded denial** (LLM) or **expiry** (time), and funds stay locked through the agreed decision window
- **AI judgment**: LLM consensus scoring with exact-agreement semantics (`SCORE_TOLERANCE = 5`), unreachable evidence -> deterministic deny

## How It Works

```
create_escrow (payable; condition = llm|time, condition_text, evidence_url)
      |
      v
release_escrow
  - time: after deadline -> release
  - llm: fetch evidence on-chain -> consensus score
      - score >= 50: release
      - score <  50: record explicit denial on-chain (no revert), remains open
      |
      v
refund_escrow (depositor only)
  - time: after expiry/deadline
  - llm:  after explicit recorded denial
```

## Methods

| Role | Method | Guard |
|---|---|---|
| Depositor | `create_escrow` | payable; funding == amount; depositor == sender; explicit condition + evidence URL (llm); bounded inputs; unique id |
| Any | `release_escrow` | status open; time gate or LLM consensus on fetched evidence; denial explicitly recorded |
| Depositor | `refund_escrow` | status open; depositor only; time expiry or explicit recorded LLM denial |
| Any | `get_escrow`, `get_all_escrows` | read-only |

## Security Model

- **Caller binding**: only the depositor (`depositor == sender`) can create; only the depositor can refund (addresses validated as `0x` + 40 hex; depositor ≠ recipient)
- Escrow funding invariant: actual payable value must equal the recorded amount at creation
- **Evidence binding**: condition text + evidence URL are stored at creation and hash-bound; the judge evaluates only contract-fetched evidence (unreachable → deterministic deny, score 0); each validator independently re-fetches
- **Refund lifecycle (steward fix)**: funds stay locked through the agreed decision window. Time escrows are refundable only after expiry (`release_deadline`); LLM escrows are refundable only after an **explicit recorded denial** (judgment outcome stored on-chain). Premature and unauthorized refunds revert
- LLM denial is explicitly recorded (score/reasoning/denied flag) so refund eligibility is auditable and deterministic; release is permissionless and retryable
- `reasoning` is descriptive-only: stored as an audit note and never reused in consequential computation

## Test

```bash
gltest tests/ -q   # 8 passed
```

## Lint

```bash
genvm-lint check contracts/conditional_release_escrow.py
```

## Live Deployment

Deployed on GenLayer studionet (chain `61999`):
[`0x1F25Fd52468091e5a3b410669Ae33867634739F8`](https://explorer-studio.genlayer.com/address/0x1F25Fd52468091e5a3b410669Ae33867634739F8)
