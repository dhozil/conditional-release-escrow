<div align="center">

# ConditionalReleaseEscrow

**AI-judged conditional release escrow: lock funds, release when the condition is satisfied via LLM-consensus judgment or a deterministic time gate.

![GenLayer](https://img.shields.io/badge/GenLayer-Intelligent%20Contract-6a4cff)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![Status](https://img.shields.io/badge/status-live%20on%20studionet-2ea44f)
![Tests](https://img.shields.io/badge/tests-8%20passed-2ea44f)

[Live Contract](https://explorer-studio.genlayer.com/address/0xECc3b64b23b70990c5E495A54679F91E3b571A7b) 

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
| **Contract** | [ConditionalReleaseEscrow](https://explorer-studio.genlayer.com/address/0xECc3b64b23b70990c5E495A54679F91E3b571A7b) |
| **Address** | `0xECc3b64b23b70990c5E495A54679F91E3b571A7b` |
| **Network** | GenLayer studionet (chain `61999`) |
| **Status** | Deployed + verified on-chain |

## Highlights

- **Explicit condition + acquired evidence (staff fix)**: every escrow stores a `condition_text` (the real condition to verify) and an `evidence_url` hash-bound as `sha256(url|condition_text)`; the judge does NOT see only a label — the contract fetches the evidence URL itself (`gl.nondet.web.get`) and feeds the *fetched content* to the LLM, and each validator independently re-fetches the same URL
- **Conditional release**: escrow releases to the recipient when the explicit condition is satisfied, either by deterministic time gate or by LLM-consensus judgment (score >= 50)
- **Bounded windows**: release window enforced with deterministic time gates; refund allowed while open (judgment denied or time not reached)
- **AI judgment**: LLM consensus scoring with exact-agreement semantics (`SCORE_TOLERANCE = 5`), unreachable evidence -> deterministic deny

## How It Works

```
create_escrow (payable; condition = llm|time, condition_text, evidence_url)
      |
      v
release_escrow (time gate -> release; llm: fetch evidence on-chain -> consensus score >= 50 -> release; else revert "Escrow condition not satisfied")
      |
      v
refund_escrow (while open: llm denied or time not reached -> refund depositor)
```

## Methods

| Role | Method | Guard |
|---|---|---|
| Depositor | `create_escrow` | payable; funding == amount; depositor == sender; explicit condition + evidence URL (llm); bounded inputs; unique id |
| Any | `release_escrow` | status open; time gate or LLM consensus on fetched evidence |
| Any | `refund_escrow` | status open; llm denied or time not reached |
| Any | `get_escrow`, `get_all_escrows` | read-only |

## Security Model

- **Caller binding**: only the depositor (`depositor == sender`) can create; strangers cannot create escrows in someone else's name (addresses validated as `0x` + 40 hex; depositor ≠ recipient)
- Escrow funding invariant: actual payable value must equal the recorded amount at creation
- **Evidence binding (staff fix)**: condition text + evidence URL are stored at creation and hash-bound; the judge evaluates only contract-fetched evidence (unreachable → deterministic deny, score 0); each validator independently re-fetches
- LLM judgment unreachable / disapproved -> deterministic deny; release is permissionless and retryable
- Refunds keep the depositor whole; release pays the recipient atomically
- `reasoning` is descriptive-only: it is stored as an audit note and never reused in any later consequential computation

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
[`0xECc3b64b23b70990c5E495A54679F91E3b571A7b`](https://explorer-studio.genlayer.com/address/0xECc3b64b23b70990c5E495A54679F91E3b571A7b)
