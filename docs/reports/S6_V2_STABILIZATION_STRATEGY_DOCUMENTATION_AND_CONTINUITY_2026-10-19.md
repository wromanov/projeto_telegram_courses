# S6_V2_STABILIZATION_STRATEGY_DOCUMENTATION_AND_CONTINUITY

```text
DOCUMENT_ROLE = ACTIVITY_REPORT_AND_RECOVERY_CHECKPOINT
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_V2_STABILIZATION_STRATEGY_DOCUMENTATION_AND_CONTINUITY
DATE = 2026-10-19 / America/Sao_Paulo
DECISION = ALTERNATIVE_B / BOUNDED HARNESS AND QA STRUCTURAL STABILIZATION
ACTIVITY_SCOPE = DOCUMENTATION_AND_CONTINUITY_ONLY
IMPLEMENTATION_PERFORMED = NO
EXECUTOR_IMPLEMENTED = NO
TESTS_OR_PROOFS_EXECUTED = NO
REAL_TELEGRAM_RPC = NONE
REAL_DOWNLOADS = NONE
GIT_ADD_COMMIT_PUSH = NONE
V1 = CANONICAL_AND_ACTIVE
V2_GLOBAL = OFF
S6_FORMAL_ACCEPTANCE = PENDING
S7_S8 = DEFERRED
PRINCIPAL_ARCHITECT = CLOSED / NO_REENTRY
```

## Purpose and authority

This activity records the user-approved direction, the attached **“Parecer de auditoria arquitetural — S6 V2”**, and the bounded execution strategy in one recoverable place. The user approved Alternative B and requested durable documentation for continuation after context loss. The architectural review was read-only, was invoked once, and is closed; it must not be invoked again. This document records a plan and decision, not implementation or proof evidence.

The authority for the active decision is the user's approval in the referenced conversation **Projeto Telegram 2.0** and the present request. The architectural opinion is evidence and recommendation, not a substitute for that approval. The current task's scope ended at documentation and checkpointing. No code, executor, fixture, probe, assertion, runner, or process-supervision implementation was changed here.

## Decision and rationale

**DECISION = ALTERNATIVE B.** Stabilize the harness and QA infrastructure in bounded, evidence-driven batches. Keep the S6 download/resume algorithm, V1 contract, and integrity model stable unless a new, separate finding justifies a narrowly scoped change.

This choice addresses failures at observation, child/supervisor, fixture, runner, receipt, and reconciliation boundaries before considering a broad refactor. It preserves reversibility and guards against treating incomplete evidence as a pass.

### Architectural review disposition

```text
principal_architect = Astra / Medium / READ_ONLY
INVOCATIONS = 1
STATUS = CLOSED
REENTRY = PROHIBITED
ROOT = GPT-6 Luna / XHIGH
```

Next roles for a future execution activity:

| Role | Model / effort | Scope |
|---|---|---|
| `diagnostic_analyst` | Sol / READ_ONLY | Diagnose one falsifiable issue, capture evidence, distinguish fact from inference, and propose a bounded contract. |
| `mechanical_implementer` | Luna / WRITE_SCOPED | Implement only the approved batch and listed files. |
| `scriber` | Luna / DOCUMENTATION_ONLY | Reconcile evidence, report, PROJECT_STATE, and CONTINUITY_RECORD append-only. |
| Architect | None | Do not re-enter or invoke `principal_architect`. |

The ROOT retains decision ownership and reconciles gates. Role/model labels describe the approved routing, not proof that a future runtime can instantiate those exact capabilities; verify actual capabilities when that future activity begins.

## Evidence baseline and limits

Two distinct Harness receipts are preserved. They represent different snapshots/runs and must never be combined into one baseline.

| Evidence | Receipt | Result | SHA-256 |
|---|---|---|---|
| Historical Harness run | `.s6r/2656a231b02f/t/receipt.json` | 163 collected, 163 PASS, 0 FAIL, 0 skipped, 0 xfail; exit 0; JUnit present; termination confirmed. Run ID `c506ba020976421fb55d2d5f17291932`. | `E1CE23D717622DCF4F2817E5CF42C65A65EF3F26EE09B83F7AE8B27E7E2CB61F` |
| Current audit Harness run | `.s6r/598cd797e185/t/receipt.json` | 176 collected, 173 PASS, 3 FAIL, 0 skipped, 0 xfail; exit 1; JUnit present; termination confirmed. Run ID `bafaa544d4ef4840bfc52c6a122145e9`. | `5EA51E64FB113A46AABA906A275DB656E8E09373C71527EEC30A75EBB51E2628` |

The attached audit attributes the increase of 13 cases to added checks around reference, integrity, root, confirmation, and remote identity. This explains suite growth but does not identify which code change introduced each failure. The status of the current run is **FAIL**, regardless of the expected-status mismatch in two assertions.

The active repository records other prior results, including a 235-test historical native aggregate and later incomplete sandbox runs. Those are additional historical evidence, not replacements for either receipt above. Keep each run tied to its receipt, snapshot, environment, and date. The current repository HEAD observed while preparing this checkpoint was `98d9d6b9ce152b8d2764a4d160fcbdf4722fb257` on `work/s0-bootstrap`; it does not identify the large WIP snapshot under test.

### Confirmed findings from the attached audit

1. Two `OPERATIONAL_ONLY` E2E assertions require `reference_integrity_post_verification.status == PASS`, although the correct result when trusted reference integrity does not apply is `NOT_APPLICABLE`. Earlier completion, file, SQLite, and ledger checks passed. The fix belongs in the expectation; do not fabricate a PASS for a nonexistent reference.
2. A child failure report may correctly have `PROCESS_FAILED`, exit 5, and `child_result = null` when no functional result exists. The supervisor currently requires a dictionary for `child_result` and rejects this valid failure envelope as `CHILD_REPORT_MISSING_OR_INVALID`. A valid failure envelope is never functional success and never permits phase 2.
3. Exact-type exception matching classifies domain exceptions such as `DownloadError` as generic `OTHER`, obscuring the stage and primary failure. Safe diagnostics should use allowlisted codes/stages and sanitized frames, without free-form exception text, secrets, or local variables.
4. Static reconstruction found trusted-fixture final and `.part` paths longer than the existing 240-character guard. The path incompatibility is confirmed for the reconstructed layout.
5. The trusted probe is configured under `proof_root`, then the fixture narrows `S6_V2_TEST_ALLOWED_ROOT` to descendant `evidence_root`. The containment guard correctly rejects the probe and the expected artifact is absent.

### Uncertainty that must remain explicit

The exact primary cause of the trusted E2E's `OTHER` / exit 5 is **not confirmed**. `PATH_TOO_LONG` is a high-confidence hypothesis because the planner computes the oversized destination before queue admission, but the historical child traceback was not retained. Do not report the cause as confirmed until a new diagnostic run captures a safe stage/code event. Manifest identity/hash, Proactor, missing download rows, and shared test state are not established as the primary cause by these artifacts.

## Repository WIP and preservation boundary

Read-only inspection found the expected active continuity package under `docs/continuity/`; the governance paths `docs/governance/PROJECT_STATE.md` and `docs/governance/CONTINUITY_RECORD.md` are legacy redirects or superseded records. Active authorities are `docs/continuity/PROJECT_STATE.md`, `docs/continuity/CONTINUITY_RECORD.md`, `docs/continuity/ACTIVE_AUTHORITY_MAP.md`, and `docs/continuity/handoff/LAST_HANDOFF.md`.

The repository was on `work/s0-bootstrap`, HEAD `98d9d6b9ce152b8d2764a4d160fcbdf4722fb257`, with upstream `origin/work/s0-bootstrap`. It already contained numerous modified tracked files and many untracked files, including S6 implementation, test, evidence, receipt, temporary, and documentation artifacts. The initial status is part of the protected WIP; it is not a clean baseline. No attempt was made to clean, restore, stage, or normalize any of it.

The documentation edit in this activity is additive: add this report, append decision and continuity records, and update only the active summary fields in PROJECT_STATE. Preserve all other WIP and prior history. Before a future implementation batch, capture a fresh explicit inventory and hashes of the exact files/receipts selected for that batch. Do not infer that the historical receipt hashes represent all current source files.

## Execution sequence for the future stabilization activity

Work one batch at a time; after each batch collect independent evidence and reconcile the gates before opening the next. Limit offline correction to **at most four cycles per batch**. A cycle must test one falsifiable hypothesis. Never repeat the same failure signature without new evidence, changed input, or a changed environment that explains why the retry is informative.

### P0 — Preserve and identify the WIP snapshot

ROOT and `scriber` capture the fresh repository status, exact HEAD, active paths, and SHA-256 inventory for the selected source files, fixtures, configuration, both named historical receipts, JUnit, and logs. Record which items are tracked, modified, or untracked. Keep all prior receipts append-only and do not overwrite them. If a snapshot/digest cannot be made stable while tests run, stop as `BLOCKED`.

### P1 — Restore diagnostic observability and the child/supervisor contract

`diagnostic_analyst` specifies cases; `mechanical_implementer` changes only the approved harness/report tests. Accept an explicit `PROCESS_FAILED` envelope with no functional result while preserving failure status and supervisor-observed exit/PID. Add allowlisted exception stage/code diagnostics and sanitized frames. Prove that malformed, missing, contradictory, or failed child evidence stays fail-closed and cannot open phase 2.

### P2 — Correct fixture paths, probes, assertions, and discriminate trusted failure

Keep the 240-character guard. Test a long layout as a negative case and a short contained root as a positive case. Put trusted probes inside the effective allowed root and assert that the expected probe artifact is present. Require `NOT_APPLICABLE` for non-trusted `OPERATIONAL_ONLY` reference assertions. For the trusted case, emit safe `planner.begin`, `planner.end`, and `queue.begin` observations plus path length/class; then decide whether `PATH_TOO_LONG` explains the failure. If a short-root run exposes another issue, open a distinct finding. No unsupported causal attribution.

### P3 — Harden runner, receipts, JUnit, and process supervision

Reconcile expected test IDs exactly against collection and JUnit; reconcile skip/xfail counts, exit codes, artifacts, receipt, and snapshot digest. Define nested monotonic deadlines and single ownership of each receipt field. Verify descendant-process completion and truthful cancellation/termination status. Validate the launcher in the required Windows runtime. A successful parser check alone does not prove runtime behavior.

### P4 — Decide and build the autonomous offline execution boundary

First evaluate whether the actual Codex runtime can execute in native Windows with controlled `submit/status/cancel/result`, return verifiable receipts, and confirm process-tree termination. In this Work session that capability was **not demonstrated**: repository Git access required an elevated operation and this activity performed no test or proof execution. Do not claim Option A is available based only on the Windows host or PowerShell being present.

If Option A remains unavailable, the user conditionally authorized planning/implementation of Option B in a later bounded execution activity. The executor itself was **not implemented here**. The approved design boundary is:

- Run only fixed, offline, explicitly allowlisted profiles against an immutable source snapshot identified by a cryptographic digest; reject unknown profiles and digest drift.
- Provide `submit`, `status`, `cancel`, and `result` via a local authenticated/ACL-protected request channel with unique IDs and atomic publication.
- Isolate under a least-privilege OS account, restrictive filesystem ACLs and a dedicated writable root; deny network egress at the OS boundary and verify the deny state. A profile allowlist alone is not a security boundary.
- Own and supervise the complete process tree, monotonic deadline, resource limits, cancellation grace, and terminal result. Never claim cancellation until descendants are confirmed exited.
- Fail closed on replay, concurrent unauthorized work, path escape/reparse-point escape, profile mismatch, snapshot drift, missing or contradictory receipt, unconfirmed process exit, or inability to prove network isolation.
- Expose no arbitrary command, script, working directory, credential, Telegram profile, live RPC, real download, or real-proof operation. No secrets in the child environment.
- Report outcomes separately for the child, supervisor, filesystem, database, and evidence reconciler. Missing observations remain missing; the aggregator must not invent values.

PowerShell **5.1 is mandatory** for the Windows launcher and its runtime contract. Verify it in execution, including parameter binding, timeout, cancellation, and process-tree handling—not only parsing.

### P5 — Regress and reconcile

After focused gates pass, run the complete approved offline Harness regression and relevant S5/S6 regression on the same identified snapshot. Reconcile collected IDs, JUnit, receipt, exit, logs, child reports, artifacts, and process exits. A full profile cannot be called PASS when any required ID is missing, skipped, xfailed, or contradictory. Report exact environment and snapshot digest.

## Outcome classification and acceptance fields

Use these classifications per gate:

- `PASS`: the required execution completed, all declared expectations passed, evidence is complete and mutually consistent, and all processes are confirmed stopped.
- `FAIL`: completed evidence demonstrates a contract or assertion violation.
- `BLOCKED`: a precondition, safety boundary, admission check, or unconfirmed process state prevents safe execution.
- `INCOMPLETE`: execution began but did not produce enough evidence for PASS or FAIL (for example timeout with confirmed exit but no complete summary).

Keep these states independent and never infer one from another:

| State | Meaning |
|---|---|
| `IMPLEMENTATION_COMPLETE` | Scoped changes are complete; this says nothing about integration or regression. |
| `INTEGRATION_VALIDATED` | Contracts and all three synthetic E2Es pass with complete evidence. |
| `NATIVE_REGRESSION_PASS` | Required full profile passes in an identified native Windows environment and snapshot. |
| `REAL_PROOF_PASS` | Separately authorized real proof passes and is reconciled. This activity did not request or perform one. |
| `USER_ACCEPTANCE` | Explicit user acceptance, recorded separately. |

At this checkpoint: documentation is complete; implementation and executor are not started; integration, native regression, real proof, and user acceptance remain pending. The report's completion must not be represented as S6 implementation or acceptance.

## Preconditions, write limits, safety, and stop conditions

Before any future source edit, satisfy P0 and re-read the active state and authorities. Use only files named for the current approved batch. Initial implementation boundaries are the S6 V2 proof harness and its tests, then specifically approved runner/launcher and infrastructure tests. Changes to `downloads.py`, gateway, migration/schema, V1, operational integrity policy, credentials, sessions, user data, or original proof payloads are out of bounds unless a separate finding, contract, and user authority explicitly covers them.

Keep V1 canonical and active; keep V2 globally off. No Telegram RPC, real download, retry, or proof is part of the activity documented here. Protect original reference files, production SQLite, partial downloads, prior proof roots, receipts, JUnit, and logs. No Git add, commit, push, reset, clean, stash, amend, or broad restore.

Stop as `BLOCKED` on egress, protected data access, path escape, digest mismatch, snapshot changes during execution, contradictory receipts, missing required observation, or an unconfirmed live descendant. Do not extend scope to fix adjacent findings without a new bounded finding and contract.

## Selective rollback for future WIP edits

Before a batch, preserve its exact before-state and hashes. If rollback is needed, stop and confirm all spawned processes exited; identify only files changed by that batch; compare each current file against its batch snapshot; and restore only those files after preserving their failed-run evidence. Never run `git reset`, `git clean`, global `git restore`, or delete broad temporary roots. Do not roll back pre-existing WIP or untracked artifacts. After selective rollback, verify the batch paths/hashes, configuration residue, active workers, and evidence integrity. Keep receipts append-only.

## Recovery instructions for the next agent

1. Read `AGENTS.md`, `docs/continuity/START_HERE.md`, `docs/continuity/PROJECT_STATE.md`, `docs/continuity/ACTIVE_AUTHORITY_MAP.md`, the current `docs/continuity/CONTINUITY_RECORD.md` entry, and this report.
2. Confirm the live repo root, branch, HEAD, worktree, and actual runtime. Treat saved Git facts as a checkpoint, not a substitute for current inspection.
3. Preserve every modified/untracked item. Do not clean or restore. Recompute receipt/source hashes before any run.
4. Start with P0; do not jump to implementation or tests until the selected WIP snapshot and evidence are identified.
5. For execution, route diagnostic-only work to `diagnostic_analyst`, scoped edits to `mechanical_implementer`, and record reconciliation to `scriber`; ROOT decides each gate. Do not call any architect.
6. Confirm PowerShell 5.1 and evaluate Option A. If native execution remains unavailable, use Option B only within the future approved offline executor boundary above.
7. Resume at P1 after P0 passes. Keep current 176/173/3 failure classification and the trusted-cause uncertainty. Do not reuse evidence as a new pass.
8. Close a batch only after P5 reconciliation. Keep formal S6 acceptance, any real proof, V2 adoption, S7/S8, and Git publication as separate user decisions.

```text
NEXT_SAFE_RESUME = P0 / fresh WIP and evidence inventory, then evaluate native Windows execution
IMPLEMENTATION_AUTHORIZATION_FOR_THIS_ACTIVITY = NO / DOCUMENTATION ONLY
OPTION_B_AUTHORIZATION = CONDITIONAL / only if Option A is unavailable and under a later bounded offline activity
CURRENT_ACTIVITY_RESULT = DOCUMENTATION_COMPLETE
INTEGRATION_VALIDATED = NOT_ESTABLISHED
NATIVE_REGRESSION_PASS = NOT_ESTABLISHED
REAL_PROOF_PASS = NOT_REQUESTED_OR_RUN
USER_ACCEPTANCE = PENDING
```
