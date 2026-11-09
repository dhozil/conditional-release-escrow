# Submission: ConditionalReleaseEscrow

## Category
Intelligent Contracts

## Contract Name
ConditionalReleaseEscrow

## Summary
A reusable GenLayer primitive for AI-judged conditional release escrow: a depositor locks value in escrow together with an **explicit condition text** and a **hash-bound evidence URL**; the contract fetches the evidence on-chain, and GenLayer validators score whether the fetched evidence satisfies the explicit condition, releasing to the recipient on consensus approval; on failure the depositor is refunded.

## What Makes This Unique
- **Evidence-bound AI release**: the judge receives the explicit `condition_text` plus the contract-fetched evidence content (not just a label); each validator independently re-fetches the evidence URL
- **Conditional release**: escrow funds are released to the recipient when the explicit condition is satisfied via LLM consensus (score >= 50) or a deterministic time gate
- **Bounded release windows**: release window enforced with deterministic time gates; refund allowed while open (judgment denied or time not reached)
- **Consensus-bound release**: LLM scoring with exact-agreement semantics (`SCORE_TOLERANCE = 5`), unreachable evidence -> deterministic deny (score 0)

## How Consensus Is Used
The contract uses `gl.vm.run_nondet_unsafe()` for the release judgment: each validator independently fetches the stored evidence URL on-chain, evaluates the fetched content against the stored explicit condition text, and scores the satisfaction. Consensus requires exact agreement with the leader (`SCORE_TOLERANCE = 5`). Unreachable evidence deterministically denies release.

## Technical Details
- Python-based GenLayer Intelligent Contract
- Conditions: `llm` or `time`; `llm` requires an explicit `condition_text` and an `evidence_url` (hash-bound as `sha256(url|condition_text)`); `time` releases deterministically after `release_after_seconds`
- Release score quantized to multiples of 10 with exact consensus tolerance; release when score >= 50
- Integer-only domain (wei amounts; `bool` flags); time gates via `datetime` against consensus time
- Storage: `Escrow` dataclass under `TreeMap` with `u256`/`bool`/`str` fields (condition_text, evidence_url, evidence_hash appended at end)
- Funding invariant: actual payable value must equal the recorded amount (`Escrow funding must equal the escrow total`)
- Caller binding: only the depositor can create an escrow; addresses validated as `0x` + 40 hex; depositor != recipient

## Use Case
Escrowed funds that depend on an external condition (task/milestone completion attested at a public evidence URL) while keeping a deterministic, consensus-backed release path and a safe refund for the depositor.

## Verification
- 8/8 direct-mode unit tests (create validation + evidence hash, time-based release, LLM approve release on fetched evidence, LLM deny -> refund, unreachable evidence -> deny, refund before window, refund-after-release guard, auth/address/duplicate guards)
- `genvm-lint check` + validation pass (5 methods: 2 view, 3 write)
- Deployed on studionet and verified on-chain (payable creation + funding invariant revert, invalid-condition revert, release-before-window revert, refund flow, release-after-refund guard)
- Full AI-consensus integration test (leader_only=False, all methods): llm release attempt against example.com evidence correctly denied by validators (tx `0xd64ea27ee6b5dd3e882842aba87e57715ffd91b2d42cb678d99a400d5c743ea9`, stderr empty); time release succeeded (tx `0x193ce66c9a6f425cab08f9c6d64854f94ffbfbe71cf6964164d18f85012b7ace`, stderr empty)

## Live Deployment
Deployed on GenLayer studionet (chain `61999`):
[`0xECc3b64b23b70990c5E495A54679F91E3b571A7b`](https://explorer-studio.genlayer.com/address/0xECc3b64b23b70990c5E495A54679F91E3b571A7b)

## Source Code
See `contracts/conditional_release_escrow.py`
