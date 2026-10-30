<div align="center">

# ConditionalReleaseEscrow

**AI-judged conditional release escrow: lock funds, release when the condition is satisfied via LLM-consensus judgment or a deterministic time gate.

![GenLayer](https://img.shields.io/badge/GenLayer-Intelligent%20Contract-6a4cff)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![Status](https://img.shields.io/badge/status-live%20on%20studionet-2ea44f)
![Tests](https://img.shields.io/badge/tests-6%20passed-2ea44f)

[Live Contract](https://explorer-studio.genlayer.com/address/0xf6C308DC192B0AF14Ef357C0a92694D2893A7D24) 

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
| **Contract** | [ConditionalReleaseEscrow](https://explorer-studio.genlayer.com/address/0xf6C308DC192B0AF14Ef357C0a92694D2893A7D24) |
| **Address** | `0xf6C308DC192B0AF14Ef357C0a92694D2893A7D24` |
| **Network** | GenLayer studionet (chain `61999`) |
| **Status** | Deployed + verified on-chain |

## Highlights

- **Conditional release**: escrow releases to the recipient when the condition is satisfied, either by deterministic time gate or by LLM-consensus judgment (score >= 50)
- **Bounded windows**: release window enforced with deterministic time gates; refund allowed while open (judgment denied or time not reached)
- **AI judgment**: LLM consensus scoring with exact-agreement semantics (`SCORE_TOLERANCE = 5`), unreachable judge -> deterministic deny

## How It Works

```
create_escrow (payable; condition = llm|time, release_after_seconds)
      |
      v
release_escrow (time gate -> release; llm consensus -> approve -> release; else revert "Escrow condition not satisfied")
      |
      v
refund_escrow (while open: llm denied or time not reached -> refund depositor)
```

## Methods

| Role | Method | Guard |
|---|---|---|
| Any | `create_escrow` | payable; bounded inputs; funding == amount |
| Any | `release_escrow` | status open; time gate or LLM consensus approval |
| Any | `refund_escrow` | status open; llm denied or time not reached |
| Any | `get_escrow`, `get_all_escrows` | read-only |

## Security Model

- Escrow funding invariant: actual payable value must equal the recorded amount at creation
- LLM judgment unreachable / disapproved -> deterministic deny; release is permissionless and retryable
- Refunds keep the depositor whole; release pays the recipient atomically

## Test

```bash
gltest tests/ -q   # 6 passed
```

## Lint

```bash
genvm-lint check contracts/conditional_release_escrow.py
```

## Live Deployment

Deployed on GenLayer studionet (chain `61999`):
[`0xf6C308DC192B0AF14Ef357C0a92694D2893A7D24`](https://explorer-studio.genlayer.com/address/0xf6C308DC192B0AF14Ef357C0a92694D2893A7D24)
