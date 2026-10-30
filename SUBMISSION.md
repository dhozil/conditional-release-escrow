# Submission: ConditionalReleaseEscrow

## Category
Intelligent Contracts

## Contract Name
ConditionalReleaseEscrow

## Summary
A reusable GenLayer primitive for AI-judged conditional release escrow: a depositor locks value in escrow, and the funds are released to the recipient when the condition is satisfied either by a deterministic time gate or by an LLM-consensus judgment; on failure the depositor is refunded.

## What Makes This Unique
- **AI-judged conditional release**: escrow funds are released to the recipient when the condition is satisfied via LLM consensus (score >= 50) or a deterministic time gate
- **Bounded release windows**: release window enforced with deterministic time gates; refund allowed while open (judgment denied or time not reached)
- **Consensus-bound release**: LLM scoring with exact-agreement semantics (`SCORE_TOLERANCE = 5`), unreachable judge -> deterministic deny

## How Consensus Is Used
The contract uses `gl.vm.run_nondet_unsafe()` with a custom validator for the release judgment: each validator independently judges whether the escrow condition is satisfied; consensus requires exact agreement with the leader (`SCORE_TOLERANCE = 5`). Unreachable judgment deterministically denies release.

## Technical Details
- Python-based GenLayer Intelligent Contract
- Conditions: `llm` or `time`; release after `release_after_seconds` for time, score-based for llm
- Release score quantized to multiples of 10 with exact consensus tolerance; release when score >= 50
- Integer-only domain (wei amounts; `bool` flags); time gates via `datetime` against consensus time
- Storage: `Escrow` dataclass under `TreeMap` with `u256`/`bool`/`str` fields
- Funding invariant: actual payable value must equal the recorded amount (`Escrow funding must equal the escrow total`)

## Use Case
Escrowed funds that depend on an external condition (AI task approval, milestone satisfaction, arbitration outcome) while keeping a deterministic, consensus-backed release path and a safe refund for the depositor.

## Verification
- 6/6 direct-mode unit tests (create validation, time-based release, LLM approve release, LLM deny -> refund, refund before window, refund-after-release guard)
- `genvm-lint check` + validation pass (5 methods: 2 view, 3 write)
- Deployed on studionet and verified on-chain (payable creation + funding invariant revert, invalid-condition revert, release-before-window revert, refund flow, release-after-refund guard)

## Live Deployment
Deployed on GenLayer studionet (chain `61999`):
[`0xf6C308DC192B0AF14Ef357C0a92694D2893A7D24`](https://explorer-studio.genlayer.com/address/0xf6C308DC192B0AF14Ef357C0a92694D2893A7D24)

## Source Code
See `contracts/conditional_release_escrow.py`
