# Submission: ConditionalReleaseEscrow

## Category
Intelligent Contracts

## Contract Name
ConditionalReleaseEscrow

## Summary
A reusable GenLayer primitive for AI-judged conditional release escrow: a depositor locks value in escrow together with an **explicit condition text** and a **hash-bound evidence URL**; the contract fetches the evidence on-chain, and GenLayer validators score whether the fetched evidence satisfies the explicit condition. On approval the recipient is paid; on an explicit recorded denial or expiry the depositor can refund. Funds stay locked through the agreed decision window.

## What Makes This Unique
- **Evidence-bound AI release**: the judge receives the explicit `condition_text` plus the contract-fetched evidence content (not just a label); each validator independently re-fetches the evidence URL
- **Explicit recorded denial / expiry refunds (steward fix)**: LLM denials are recorded on-chain (score/reasoning/denied flag) rather than reverted away, so refund eligibility is auditable; time escrows are refundable only after expiry. Premature and unauthorized refunds revert, keeping funds locked through the decision window
- **Conditional release**: escrow funds are released when the explicit condition is satisfied via LLM consensus (score >= 50) or a deterministic time gate
- **Consensus-bound release**: LLM scoring with exact-agreement semantics (`SCORE_TOLERANCE = 5`), unreachable evidence -> deterministic deny (score 0)

## How Consensus Is Used
The contract uses `gl.vm.run_nondet_unsafe()` for the release judgment: each validator independently fetches the stored evidence URL on-chain, evaluates the fetched content against the stored explicit condition text, and scores satisfaction. Consensus requires exact agreement with the leader (`SCORE_TOLERANCE = 5`, with `score` and `reasoning` required). Unreachable evidence deterministically scores 0; denial is explicitly recorded on-chain.

## Technical Details
- Python-based GenLayer Intelligent Contract
- Conditions: `llm` or `time`; `llm` requires explicit `condition_text` and `evidence_url` (hash-bound as `sha256(url|condition_text)`); `time` releases deterministically after `release_after_seconds`
- Refund lifecycle: `refund_escrow` is depositor-only; LLM requires explicit recorded denial, time requires expiry — no premature refunds
- Release score quantized to multiples of 10 with exact consensus tolerance; release when score >= 50
- Integer-only domain (wei amounts; `bool`/`u256` flags); time gates via `datetime` against consensus time
- Storage: `Escrow` dataclass under `TreeMap` with `u256`/`bool`/`str` fields (judgment_denied/score/reasoning recorded)
- Funding invariant: actual payable value must equal the recorded amount

## Use Case
Escrowed funds that depend on an external condition (task/milestone completion attested at a public evidence URL) while keeping a deterministic, consensus-backed release path, an auditable denial record, and a safe depositor-only refund after denial or expiry.

## Verification
- 8/8 direct-mode unit tests (create validation + evidence hash, time-based release, LLM approve on fetched evidence, LLM deny records explicit denial then depositor refund, unreachable evidence records denial, premature/unauthorized refunds fail and eligible refunds succeed, refund-after-release guard, auth/address/duplicate guards)
- `genvm-lint check` + validation pass (5 methods: 2 view, 3 write)
- On-chain verified on studionet: payable creation, funding/invalid-condition guards, release-before-window revert, premature refund revert, unauthorized refund revert, eligible expiry refund by depositor succeeds, release-after-refund revert
- Full AI-consensus integration test (`leader_only=False`, all methods): LLM denial explicitly recorded on-chain (tx `0x52e969941e6f1802b0087e1c0c828ef6d6b4142acb9162e48a9530fc5f689cd5`, stderr empty) then depositor refund succeeded; time-gated release succeeded (tx `0xf2299d088eb14926e68e6afe9b61ad521beb733e5bbc6f0d9a8aaca81089dde2`, stderr empty)

## Live Deployment
Deployed on GenLayer studionet (chain `61999`):
[`0x1F25Fd52468091e5a3b410669Ae33867634739F8`](https://explorer-studio.genlayer.com/address/0x1F25Fd52468091e5a3b410669Ae33867634739F8)

## Source Code
See `contracts/conditional_release_escrow.py`
