# S6 Unified Architectural Audit and Correction Contract

```text
CONTRACT_ID = S6_UNIFIED_CORRECTION_CONTRACT_V1
DOCUMENT_ROLE = ACTIVITY_SCOPED_CORRECTION_CONTRACT
ACTIVITY = S6_FULL_ARCHITECTURAL_AUDIT_AND_REMEDIATION
STATUS = ROOT_ADJUDICATED / BOUNDED_OFFLINE_IMPLEMENTATION_AUTHORIZED
CANONICAL_S5_OR_S6_CONTRACT_CHANGE = NO
V1_ACTIVE = YES
V2_OPERATIONALLY_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
```

## 1. Purpose and authority boundary

This document records the architectural audit summary supplied by Root from
the Architect's audit and Root's closed adjudications F01–F08. It authorizes
only the offline corrections listed in this contract. It does not create or
change product requirements, architecture, governance, or canonical contract
content. The approved and frozen S6 V1 contract remains active. The S6 V2
proposal/design remains non-operative outside an isolated proof child.

Canonical S5/S6 contract changes remain proposal-only and require separate
approval. No implementation may infer new policy from audit observations.
Where a finding is explicitly conditional or unresolved, its bounded action
must stop at that condition.

## 2. Audit scope and recorded result

The 12 domain summaries below are recorded from Root's summary of the
Architect's audit. They are not independent new evidence or a declaration of
acceptance.

| Domain | Recorded audit summary | Related finding / limitation |
|---|---|---|
| AUD-01 — Component boundaries | Downloader, repository, gateway, and S5 boundaries are identifiable. The proof harness concentrates authorization, budget, process, and adjudication responsibilities; strict validation is required there. | F04, F05 |
| AUD-02 — Integrity modes and policy | V1 is the default and operational V2 is blocked. V2 integrity classes do not promote remote integrity. No automatic downgrade requirement was found. | V1/V2 invariants; no new policy decision |
| AUD-03 — Remote hash and EOF | The evaluator does not truncate or pad a digest at EOF; invalid and divergent ranges remain preserved. There is no complete real-proof evidence of EOF/coverage. `REMOTE_HASH_ACCEPTANCE` remains a separate acceptance dimension. | Audit limitation; real acceptance remains pending |
| AUD-04 — Resume and reference paths | V1/V2 test matrices exist. An unaligned `TRUSTED_REFERENCE` resume fails before overlap. Rename recovery revalidates bytes. | F03 is conditional on synthetic reproduction |
| AUD-05 — Persistence and migration | The migration is additive; terminal V2 persistence is transactional; ownership and checkpoint protections are present. The harness lacks full independent reconciliation. | F05 |
| AUD-06 — S5 budgets and retries | S5 reservation precedes requests and adapter retries are controlled. The ledger can accept invalid state. Cross-phase attempts must follow Root's conservative F07 interpretation. Internal RPCs remain unknown. | F04, F07; `RPC_TOTAL_UNKNOWN=YES` |
| AUD-07 — Process harness and lifecycle | The supervisor records PID, exit, JSON, and timeouts with fail-closed behavior. The principal gate uses `runpy` differently from production direct spawn. Publication, cleanup, and cancellation need regression coverage. | F02; only bounded harness/test changes authorized |
| AUD-08 — Runtime environment | The sandbox's socketpair/loopback restriction is confirmed; the native direct/default loop succeeds. This does not explain a later timeout after bootstrap: with an 8-second diagnostic timeout, process 40216 created a ProactorEventLoop in about 0.87 seconds, advanced phase 2 through synthetic streaming/hash work and the supervisor observed `COMPLETED_V2` with a complete file, but no child JSON arrived before timeout. With a 45-second diagnostic timeout under the same policy, interpreter, cwd, argv, bytes, and guards, A30 completed direct/default execution with both JSONs/receipts, phase 1 `PROCESS_INTERRUPTED` exit 0, phase 2 `PROCESS_COMPLETED` exit 0, and distinct PIDs 26512/19732. | F01/F02; sandbox cause and post-bootstrap timeout are distinct |
| AUD-09 — Isolation and diagnostics | V2 scope/isolation has improved. Persisting arbitrary exception messages is unsuitable. The fixture blocks access to the credential vault. | F06; no vault/session access authorized |
| AUD-10 — Test coverage and result semantics | Unit coverage is useful, but runtime variants and unaligned reference resume were missing. Skipped or blocked checks are distinct from PASS. | F02, F03, F08 |
| AUD-11 — Evidence and historical reporting | Historical PASS/RPC claims conflict with gaps in evidence; identity/version reconciliation is incomplete. A contract hash does not identify the executed source. | F05, F08; preserve original historical reports |
| AUD-12 — Authority and release state | V1 is active, V2 ineffective, and acceptance pending. Prior contracts have their own scope and ownership. This contract applies only to this activity. | No acceptance, sprint close, or canonical amendment |

## 3. Adjudicated findings

| ID | Finding and evidence summary | Root status | Authorized disposition |
|---|---|---|---|
| F01 | B06's socketpair/loopback restriction is attributable to the sandbox: the same Python version's direct/default loop passes in the authorized native Windows runner. This diagnosis applies to the sandbox restriction only; it does not explain a post-bootstrap timeout. | `ENVIRONMENT_RESTRICTION_PROVEN` | No product or launcher change. Use the authorized native Windows context for the final direct/default test with a short test root. |
| F02 | Main two-process test needs to prove the production direct-spawn/default path and distinguish loop-created progress from full stage completion. Diagnostic A with an 8-second timeout was `INCOMPLETE / SUPERVISOR_TIMEOUT`: PID 40216 created `ProactorEventLoop` in about 0.87 seconds, advanced phase 2 through synthetic streaming/hash work, and the supervisor observed `COMPLETED_V2`/complete file, but did not receive child JSON before timeout. Diagnostic A30 with a 45-second timeout and the same policy/interpreter/cwd/argv/bytes/guards was `PASS`: two JSONs/receipts, phase 1 `PROCESS_INTERRUPTED` exit 0, phase 2 `PROCESS_COMPLETED` exit 0, distinct PIDs 26512/19732. This diagnostic is not the corrected suite gate and does not establish global acceptance. | `APPROVED_FOR_IMPLEMENTATION` | Keep `runpy`/Selector as comparison variants; separate the loop-created marker from full-stage completion; separate the intentional-timeout test from the functional gate and set a sufficient functional timeout. Preserve timeout as a diagnosable incomplete result. |
| F03 | Non-aligned `TRUSTED_REFERENCE` resume appears to fail before overlap. | `NEEDS_MORE_EVIDENCE` | Reproduce locally with synthetic isolated input first. Only if reproduced, patch/test `src/telegram_courses/downloads.py` and `tests/unit/test_s6_v2.py`. Otherwise do not modify product code for F03. |
| F04 | Proof ledger accepts invalid types/values/invariants, creating a path for invalid counters to influence budget decisions. | `APPROVED_FOR_IMPLEMENTATION` | Strictly validate types, values, and invariants before gateway access and within transactional/idempotent reservation; add harness and tests. |
| F05 | Harness reconciliation does not sufficiently reconcile identity, versions, digests, receipts, and ledger. | `APPROVED_FOR_IMPLEMENTATION` | Add independent consistency checks in harness and tests; mismatches or missing evidence fail closed. |
| F06 | Arbitrary exception text is persisted/emitted in logs, JSON, or stdout. | `APPROVED_FOR_IMPLEMENTATION` | Replace message text with allowlisted exception class/category only; never persist arbitrary exception text. Add tests. |
| F07 | Phase-level attempt allocation could allow phase 1 plus phase 2 to exceed the S5 per-media limit. | `APPROVED_FOR_IMPLEMENTATION` | Apply a maximum of three transfer attempts per media across both phases combined. Count every phase 1 transfer attempt, including the planned-interruption attempt; do not reset on resume. Phase 2 receives only the remaining allowance. Do not raise any caps. Change harness formula/tests only. |
| F08 | Historical evidence/reporting includes a PASS/RPC statement despite absent individual phase evidence; historical artifacts must be preserved. | `APPROVED_DOCUMENTATION_ONLY` | New reports must distinguish historical reported claims, corroborated artifacts, current execution, and unknowns. Do not edit historical reports or other docs under this contract. |

## 4. Authorized implementation matrix

| Finding | Authorized files | Required validation |
|---|---|---|
| F01 | None | Keep the sandbox restriction and native loop success distinct from the post-bootstrap timeout. Do not change runtime security settings. |
| F02 | `tests/manual_proofs/test_s6_v2_proof_harness.py`; harness changes are limited to what is needed to exercise the real entry point and direct-spawn/default path | Prove direct child spawn/default behavior with a sufficient functional timeout; represent loop creation separately from stage completion; keep an intentional-timeout test separate from the functional gate; keep `runpy`/Selector as named comparison cases. The diagnostic A30 run is evidence for diagnosis only, not suite or global acceptance. |
| F03 | Conditional: `src/telegram_courses/downloads.py`, `tests/unit/test_s6_v2.py` | First run a synthetic, local reproduction. If the defect does not reproduce, report `NOT_REPRODUCED` and leave both files unchanged for F03. |
| F04 | `tools/manual_proofs/s6_v2_proof_harness.py`, `tests/manual_proofs/test_s6_v2_proof_harness.py` | Reject malformed schema, wrong types, negative values, over-cap values, and inconsistent ledger invariants before a gateway call; prove transactional/idempotent reservation and no budget reset. |
| F05 | `tools/manual_proofs/s6_v2_proof_harness.py`, `tests/manual_proofs/test_s6_v2_proof_harness.py` | Cross-check identity, schema/evidence versions, digest, receipts, SQLite, physical files, and ledger independently; tampering/missing/mismatch must fail closed. |
| F06 | `tools/manual_proofs/s6_v2_proof_harness.py`, `tests/manual_proofs/test_s6_v2_proof_harness.py` | Ensure arbitrary exception messages do not appear in stdout, logs, JSON, or receipts; only allowlisted classifications may be recorded. |
| F07 | `tools/manual_proofs/s6_v2_proof_harness.py`, `tests/manual_proofs/test_s6_v2_proof_harness.py` | Verify total phase 1 + phase 2 transfer attempts per media never exceed 3, including the planned interruption attempt; resume spends only the remaining count. |
| F08 | Contract only: `docs/contracts/S6_UNIFIED_CORRECTION_CONTRACT_V1.md` | Do not edit historical reports or create/update any other documentation artifact in this activity. Future reports follow the distinction stated above. |

No other files are authorized by this contract. A necessary change outside
this matrix, or any canonical contract change, returns to Root before work.

## 5. Invariants and prohibited operations

```text
V1_ACTIVE = YES
V2_OPERATIONALLY_EFFECTIVE = NO
CANONICAL_CONTRACTS_MODIFIED = NO
TELEGRAM_CALLS = 0
REAL_DOWNLOADS = 0
CREDENTIAL_OR_PROTECTED_SESSION_ACCESS = NO
OPERATIONAL_SQLITE_ACCESS_OR_WRITE = NO
HISTORICAL_PART_ACCESS_OR_WRITE = NO
HISTORICAL_PROOF_ARTIFACTS_MODIFIED = NO
GIT_STAGE_COMMIT_PUSH = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
```

Only synthetic fixtures, isolated proof roots, and offline test databases may
be used. Do not access credentials, the protected session, the operational
database, prior proof roots, historical `.part` files, or Telegram. Do not
run the real launcher or `Execute` flow. Do not change product policy, S5
ceilings, V1 semantics, retry caps, FloodWait limits, or worker limits. Do
not edit historical reports to make evidence appear complete. No Git staging,
commit, push, reset, restore, clean, stash, or other Git mutation is allowed.

## 6. Gates and evidence rules

1. **Scope gate:** implementation must match the file matrix. Any scope
   expansion or canonical change stops the affected item for Root.
2. **Synthetic reproduction gate (F03):** run only against fresh synthetic
   local data. No reproduction means no F03 code change.
3. **Ledger gate (F04):** parse/validate all existing state before any gateway
   call. Reservation is atomic, idempotent under its defined request identity,
   and enforces nonnegative counters plus the existing S5 ceilings and ledger
   relationships. Never silently repair consumed budget.
4. **Evidence gate (F05):** phase receipts, identity, contract/source version,
   digest, SQLite state, physical files, and budget-ledger deltas must reconcile
   independently. Unknown or unavailable fields stay explicit as unknown/null
   with reason; they are not inferred.
5. **Diagnostic gate (F06):** exception data is limited to allowlisted class
   and category. No exception message or secret-bearing text is persisted or
   printed.
6. **Attempt gate (F07):** maximum three transfer attempts per media across
   both processes/phases in total. Phase 1 counts, including its planned stop;
   phase 2 gets only the unused balance. No reset or cap increase.
7. **Runtime gate (F01/F02):** final principal lifecycle test proves two
   independent direct-spawn child processes under the default runtime in an
   authorized native Windows context. Use a fresh short isolated root so
   application path-length guards are not tripped. `runpy`/Selector remains a
   comparative test, not the principal proof. Record loop creation separately
   from stage completion. A deliberate short-timeout case is diagnostic and
   must not substitute for the functional gate; the functional timeout must be
   sufficient for the complete child lifecycle. The diagnostic A30 result is
   not the corrected suite result or global S6 acceptance.
8. **Reporting gate (F08):** reports created in future work distinguish
   historical claims, corroborated artifacts, current execution, and unknowns.
   Existing historical reports are immutable for this activity.
9. **Acceptance gate:** offline checks may establish correction readiness only.
   They do not establish real Telegram proof, S6 formal acceptance, V2
   adoption, or sprint completion. This contract does not authorize a real
   proof retry.

`PASS` may be reported only for a specific gate when its required evidence is
present and reconciled. Skipped, blocked, incomplete, or non-reproduced results
must be labeled as such. No aggregate S6 acceptance may be declared here.

## 7. Stop, failure, and rollback rules

- Stop the affected finding if its reproduction/evidence gate fails, if a
  required file is outside the matrix, or if the change would amend a canonical
  contract or alter an S5/V1 limit.
- Stop before any external/Telegram call, credential/session access, or
  operational storage access. Such actions are outside authorization.
- Preserve existing unrelated worktree changes and all historical evidence.
- If a correction regresses an invariant or its targeted test fails, do not
  broaden scope or silently weaken assertions. Root decides the next action.
- Rollback is limited to reverting only the newly introduced activity-scoped
  implementation changes after inspecting exact diffs and preserving all
  pre-existing/user changes. No blanket restore/reset/clean/stash is allowed.
- An environment-blocked check is `BLOCKED`, not `PASS`; F01's known sandbox
  restriction is handled by the authorized native Windows test context, not by
  weakening security controls.

## 8. Risks and dependencies

- F03 remains conditional until a synthetic reproduction establishes the exact
  failure. Its source fix is not pre-authorized absent that reproduction.
- The direct-spawn acceptance test depends on a functioning native Windows
  loopback environment and a sufficiently short test root. The earlier sandbox
  failure is environmental evidence, not product acceptance.
- Telegram client connection may issue internal RPCs not instrumented by the
  harness. Keep `AUXILIARY_RPCS_OBSERVED` distinct from `RPC_TOTAL_UNKNOWN`;
  do not claim an exact total when those calls remain unobserved.
- Historical report claims and preserved artifacts can disagree. Preserve both
  facts and describe the discrepancy; do not rewrite historical evidence.
- A contract/source digest alone does not prove which source actually ran;
  source/evidence versions must be independently represented in receipts.
- Direct/default diagnostic artifacts supplied by Root include initial probes
  under `C:\s6a\test_probe_full_synthetic_hand0` through `hand2` and retained
  A30 evidence at
  `C:\s6a\direct-default-long2\s6-v2-real-proof-661326fcae0b495d9461dff40d840e39`.
  The 8-second result is `INCOMPLETE / SUPERVISOR_TIMEOUT`; the A30 45-second
  result is a diagnostic PASS only. Neither is the corrected suite gate or
  global acceptance.

## 9. Recorded closeout state

This document records an implementation authorization for bounded offline
corrections, not their completion. No implementation result or acceptance is
asserted here.

```text
OFFLINE_CORRECTION_AUTHORIZATION = BOUNDED / THIS CONTRACT ONLY
IMPLEMENTATION_RESULT = NOT_RECORDED
REAL_PROOF = NOT_AUTHORIZED
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
SECRETS_EXPOSED = NO
REAL_TELEGRAM_CALLS = 0
```

## 10. Addendum R1 — F03 synthetic reproduction and revised authorization

```text
CONTRACT_REVISION = R1
REVISION_STATUS = ROOT_ADJUDICATED
REVISION_SCOPE = F03 ONLY
F03_STATUS_R0 = NEEDS_MORE_EVIDENCE
F03_STATUS_R1 = APPROVED_FOR_IMPLEMENTATION
```

This addendum is append-only. It preserves the original F03 status and
conditional disposition in Sections 3 and 4 as the R0 decision record. For F03
only, this later Root adjudication supersedes that conditional status after the
following synthetic reproduction.

### R1 evidence and adjudicated cause

The reproduction ran under the project `.venv` on native Windows, using a
synthetic non-aligned `.part` prefix of 7 bytes, a valid trusted-reference
manifest, and `FakeV2Gateway`. The preserved artifact is
`C:\s6a\f03-trusted-reference-repro`.

```text
REPRODUCTION_RESULT = REPRODUCED
OBSERVED_ERROR = CHECKPOINT_INCONSISTENT
PHYSICAL_PREFIX_BYTES_PRESERVED = 7
GATEWAY_DOWNLOAD_CALLS = 0
TELEGRAM_CALLS = 0
CREDENTIAL_OR_PROTECTED_SESSION_ACCESS = NO
```

Root adjudicates the cause as follows: for `TRUSTED_REFERENCE`, the remote
wire offset is `W = floor(P/C) * C`, which is zero for this 7-byte prefix. The
partial file is opened at its physical EOF, so the local output cursor is 7;
the current code then requires `output.tell() == W` and fails before overlap
verification or append. The bytes remained preserved and no gateway download
was issued.

### R1 implementation authorization

F03 is now `APPROVED_FOR_IMPLEMENTATION`, limited to:

- `src/telegram_courses/downloads.py`
- `tests/unit/test_s6_v2.py`

The correction must validate the local cursor against physical prefix size `P`
while retaining remote reread offset `W`, perform overlap comparison before
append, preserve the existing prefix, and preserve request/payload budgets.
This authorization does not permit changes to any other file or canonical
contract.

Required offline synthetic regression cases are:

- `P=1`, `P=C-1`, and `P=C+123`;
- `P=E-1`, an aligned prefix, and `P=E`;
- reference/overlap mismatch;
- insufficient budget and cancellation;
- V1 compatibility.

This addendum authorizes implementation only. It records no patch result,
regression-test result, real proof, or acceptance. All other findings F01/F02
and F04–F08, scope boundaries, and safety limits remain as stated in R0.

## 11. Addendum R2 — F05 ledger and receipt reconciliation; F02 timeout

```text
CONTRACT_REVISION = R2
REVISION_STATUS = ROOT_ADJUDICATED
REVISION_SCOPE = F05 / F02 CLARIFICATIONS ONLY
```

This addendum is append-only. It preserves the R0 and R1 decisions and
evidence. It clarifies implementation and verification details for F05 and
F02 only. No canonical contract, request limit, payload cap, retry cap, or
other safety limit is changed.

### R2.1 Capacity, admission, and snapshot semantics (F05)

Keep the following quantities distinct; they describe different things and
must not be required to equal one another:

1. `s6_v2_attempts.bytes_reserved` is per-attempt calculated capacity. For a
   common target with `E=11,649,955` and `C=262,144`, the exact capacity is
   `ceil(E/C)*C = 45*C = 11,796,480` bytes.
2. The S5 temporary pool is the capacity available to that attempt under the
   existing S5 budget policy.
3. `ProofLedger.payload_reserved` is cumulative `GetFile` payload reservation
   admitted by the proof ledger. At a planned interruption at 1 MiB, four
   admitted requests yield `4*C = 1,048,576` bytes.

`total_reserve` may have been calculated and persisted before
`operation_reserver` is attempted, including when the operation returns
`BUDGET_BLOCK`. Its presence does not prove that the reservation was admitted.
Validate the exact capacity calculated by the existing formula for the
selected mode and prefix; do not accept a loose range.

### R2.2 Phase ledger absence and before/after snapshots (F05)

- A missing phase 1 ledger may be classified as `ABSENT_EXPECTED_NEW_ROOT`
  only when the proof root is independently established as new and empty.
- Keep the contract's zero baseline distinct from a SQLite snapshot actually
  observed as zero. If a child exits before creating the ledger, phase 1
  `after` is unavailable; do not substitute zero.
- Phase 2 requires a valid ledger. Its `before` snapshot must exactly equal
  phase 1's observed `after` snapshot. Missing, corrupt, unavailable, or
  divergent phase 2 ledger state fails closed.

### R2.3 Exact planned-interruption evidence (F05)

`CONTROLLED_INTERRUPT` is a specific planned phase outcome, not a generic
`BLOCKED` classification. Accept it only when the observed fields form this
exact combination:

- `attempt.status = BLOCKED` and `details.reason = CONTROLLED_INTERRUPT`;
- download state/failure category are `FAILED_RETRYABLE` /
  `CONTROLLED_INTERRUPT`;
- queue state/failure category are `FAILED` / `CONTROLLED_INTERRUPT`;
- child exit and supervisor-observed exit are both 0;
- prefix bytes, SQLite checkpoint, and SHA-256 are mutually consistent; and
- there is no V2 terminal state.

Do not change downloader behavior solely to make a status match this evidence
classification.

### R2.4 Retry-set and transfer accounting (F05)

- Bind each new attempt to its attempt ID and invocation ID, and validate the
  complete set of attempts belonging to the phase.
- Do not compare a phase delta only with the final attempt when earlier
  attempts in the same phase consumed budget. Preserve pre-existing attempts;
  account for request and byte admission independently of the final attempt
  status.
- Application `attempt.requests` may remain unchanged when the gateway fails
  after admission. The proof ledger is the record of admitted reservations.
- Where truncation can occur, distinguish remote payload from bytes delivered
  to or persisted by the application.

### R2.5 Receipt counters (F05)

Receipt request counters must reconcile with requests actually admitted by the
ledger. `payload_reserved` must equal `GetFile_admitted * C`, and
`received + uncertain <= reserved`. These ledger quantities are not the same
as per-attempt calculated capacity in `s6_v2_attempts.bytes_reserved`.

### R2.6 Effective diagnostic timeout (F02)

`_run_phase_child` applies the lower of the requested timeout and the
environment override. Record the effective timeout in evidence. For the
functional direct/default test gate, after installing the fixture, set
`S6_V2_TEST_PROBE_TIMEOUT_SECONDS=60`; when the requested parameter is 90,
the effective timeout is 60 seconds. Keep the operational timeout at 3600
seconds. The intentional short-timeout diagnostic remains separate from the
functional gate.

### R2.7 Required F05/F02 regressions

The authorized tests must cover:

- interrupted capacity of `45*C` versus admitted ledger payload of `4*C`;
- tampered calculated capacity;
- valid initial absent ledger on a proven new/empty root and rejection of a
  pre-existing root with absent ledger;
- missing phase 2 ledger and phase 2 snapshot divergence;
- `BLOCKED` with a reason other than `CONTROLLED_INTERRUPT`;
- retries consumed before the final attempt completes;
- hash-call failure after admission but before the application request counter
  increments; and
- requested versus effective timeout recording, including 90 reduced to 60
  seconds for the functional test.

This addendum records Root's adjudicated requirements; it does not assert that
implementation or these regressions have run or passed. F01/F03/F04/F06/F07/
F08, all prior evidence, and the no-real-proof/no-acceptance boundaries remain
unchanged.

## 12. Addendum R3 — planned queue identity and final-path evidence (F05)

```text
CONTRACT_REVISION = R3
REVISION_STATUS = ROOT_ADJUDICATED
REVISION_SCOPE = F05 / INTERRUPTED-PHASE RECONCILIATION
IMPLEMENTATION_SCOPE = EXISTING HARNESS AND TEST FILES ONLY
```

This addendum is append-only and preserves R0–R2. It records Root's
adjudication of two false rejection gates found in the interrupted-phase
artifact. The cited source observations are `s6_v2_proof_harness.py:774`
and `download_repository.py:238`.

### R3.1 Queue identity

The checker must compare the exact queue media key triple to the target
identity, together with the expected `FAILED` / `CONTROLLED_INTERRUPT`
outcome. The canonical S5 queue outcome is shaped as
`[[channel_id, message_id, ordinal], 'FAILED', 'CONTROLLED_INTERRUPT']`.
An artifact with that exact target triple is valid; do not compare it to the
different `[media_item_id, 'FAILED', 'CONTROLLED_INTERRUPT']` shape.

### R3.2 Planned path versus physical final file

`DownloadRepository.start` persists a planned `final_path` before download or
rename. Therefore, a non-null `media_state.final_path` does not establish that
a physical final file exists. On planned interruption before rename, require:

- the planned path equals the receipt path derived for that target item;
- the resolved path is confined to the isolated proof/download root, with no
  symlink or escape from that root; and
- the physical final file is absent, represented by `final_bytes = null` and
  `exists = false` at the interruption checkpoint.

The planned path may be non-null. An existing physical final file, a symlink,
or an escaping path fails closed.

### R3.3 Authorized files and required regressions

R3 authorizes changes only within the harness and test files already authorized
for F05:

- `tools/manual_proofs/s6_v2_proof_harness.py`
- `tests/manual_proofs/test_s6_v2_proof_harness.py`

Required offline regressions:

- canonical queue identity triple with `FAILED` / `CONTROLLED_INTERRUPT`
  passes; wrong triple fails;
- a proper planned final path with no physical final file passes; and
- an existing final file, symlink, or path escaping the isolated root fails.

No downloader, repository, or S5 change is authorized. Caps, canonical
contracts, prior findings, and all safety boundaries remain unchanged. This
addendum records authorization and expected behavior only; it does not assert
implementation, test results, or acceptance.

## 13. Addendum R4 — phase-local attempt identity and accounting (F05)

```text
CONTRACT_REVISION = R4
REVISION_STATUS = ROOT_ADJUDICATED
REVISION_SCOPE = F05 / PHASE-LOCAL ATTEMPT ACCOUNTING
IMPLEMENTATION_SCOPE = EXISTING HARNESS AND TEST FILES ONLY
```

This addendum is append-only and preserves R0–R3. Architect's review of the
R3 artifact confirms `identity_calls = 2` and
`requests_used.identity_GetMessages = 2` for phase 2: one initial metadata
lookup and one pre-finalization lookup. Therefore `attempt.requests = 48`
correctly represents 45 `GetFile` calls, one hash call, and two identity
`GetMessages` calls. No `GetMe` call is included in that application counter.
Do not weaken the request-count formula or add an allowance.

The adjudicated cause is an attempt-ID key mismatch: `_read_attempt_rows`
returns rows under `id`, while `_run_phase_child` reads `attempt_id` when
constructing `prior_attempt_ids`. That produces `{None}`; phase 2 then
incorrectly includes phase 1's attempt ID in `phase_attempt_ids`. The R3
artifact consequently sums application requests as `5 + 48 = 53` and mixes
phase 1 and phase 2 byte accounting.

### R4.1 Required correction and accounting

- Normalize the persisted attempt key from either supported representation,
  `id` or `attempt_id`, to the canonical attempt identity before phase
  selection. Missing or duplicate identities fail closed.
- Exclude IDs belonging to prior phases from the current phase's attempt set;
  preserve those IDs in historical evidence and do not discard prior attempts.
- Reconcile phase 1 and phase 2 request and byte deltas separately. Do not
  include a prior phase's attempt or prefix consumption in the later phase's
  delta.
- Retain the R2 request formula and ledger-admission semantics. The two phase
  2 identity lookups are included in the application request counter as
  observed; no extra request allowance is authorized.

### R4.2 Authorized files and required regressions

R4 authorizes changes only within the harness and tests already authorized for
F05:

- `tools/manual_proofs/s6_v2_proof_harness.py`
- `tests/manual_proofs/test_s6_v2_proof_harness.py`

Required offline regressions:

- parser normalizes both `id` and `attempt_id` forms;
- phase 2 excludes the phase 1 attempt ID while retaining it in historical
  evidence;
- phase 1 and phase 2 request/byte accounting reconciles independently;
- phase 2 records both identity `GetMessages` calls in its application
  request count;
- phase 2 byte accounting excludes prior attempt/prefix consumption; and
- missing or duplicate attempt IDs fail closed.

No canonical contract, S5/S6 cap, request formula, or downloader/repository
behavior changes. This addendum records authorization and expected behavior
only; it does not assert implementation, test results, or acceptance.

## 14. Addendum R5 — deterministic path-guard tests (F05 / R3)

```text
CONTRACT_REVISION = R5
REVISION_STATUS = ROOT_ADJUDICATED
REVISION_SCOPE = DETERMINISTIC PATH-GUARD TESTS ONLY
AUTHORIZED_FILE = tests/manual_proofs/test_s6_v2_proof_harness.py
```

This addendum is append-only and preserves R0–R4. It authorizes only tests in
`tests/manual_proofs/test_s6_v2_proof_harness.py` for the path-safety behavior
recorded in R3. It authorizes no product change, canonical contract change,
security-setting change, or implementation/test/acceptance claim.

### R5.1 Deterministic path-guard coverage

Keep these cases distinct: absent path, existing regular file, path escape,
and symlink. Add a deterministic symlink-guard unit test by monkeypatching
`Path.is_symlink` for the exact target path under test; delegate to the
original method for all other paths. Invoke the real path guards and use a
sentinel to prove that the unsafe target is rejected before any file read or
hash operation.

This deterministic guard test may establish the logical R3 path-guard
acceptance. Report real Windows symlink integration separately. If an actual
Win32 symlink cannot be created because the operation returns
`WinError 1314`, classify that integration check as `BLOCKED` or `SKIPPED`,
never `PASS`; do not change security settings to enable it. A junction test is
optional and cannot replace the symlink test or its status.

### R5.2 Reporting boundary

Report deterministic guard coverage and real filesystem symlink integration
as separate results. This authorization does not claim that either test has
been implemented or run, and does not establish R3 integration acceptance or
global S6 acceptance.

## 15. Addendum R6 — stale test assertions and aggregate fixtures

```text
CONTRACT_REVISION = R6
REVISION_STATUS = ROOT_AUTHORIZED
REVISION_SCOPE = TEST_ASSERTIONS_AND_FIXTURES_ONLY
AUTHORIZED_FILE = tests/manual_proofs/test_s6_v2_proof_harness.py
```

This addendum is append-only and preserves R0–R5. It authorizes only bounded
test repairs in `tests/manual_proofs/test_s6_v2_proof_harness.py` for two stale
assertions/fixtures revealed by the full test run. No product implementation,
canonical contract, cap, or broader scope change is authorized.

### R6.1 Entrypoint refusal assertion

Update the entrypoint test to assert the sanitized refusal marker
`STOP=RuntimeError`. The assertion must not expose or depend on exception
detail text.

### R6.2 Aggregate-counter fixture

Update the aggregate-counter test's synthetic receipts to satisfy the current
required process and phase proof fields. The fixture must allow `execute()` to
legitimately accept the phase boundary, so the assertion exercises aggregate
counter sums rather than being rejected for incomplete phase evidence.

### R6.3 Boundary

Only the authorized test file may be edited for R6. Preserve product code,
contracts, and all existing caps. This addendum records authorization only;
it does not claim the test edits have been made or run, and it does not assert
acceptance.

## 16. Addendum R7 — bounded real-proof authorization and execution observability

```text
CONTRACT_REVISION = R7
REVISION_STATUS = ROOT_ADJUDICATED
REVISION_SCOPE = EXECUTION MONITORING / NATIVE CONFIRMATION / ONE BOUNDED PROOF
AUTHORIZED_FILES = tools/manual_proofs/s6_v2_proof_harness.py;
                   tools/manual_proofs/Invoke-S6V2Proof.ps1;
                   tests/manual_proofs/test_s6_v2_proof_harness.py
REAL_PROOF_AUTHORIZATION = ONE EXACT TARGET / GATED
```

This addendum is append-only and preserves R0–R6. It records the user's
current direct authorization for one real proof, subject to the offline and
security preflight gates below and an explicit human confirmation in the
native PowerShell prompt. This later activity-specific authorization
supersedes the earlier no-real-proof boundary only for the single target and
limits recorded here. It does not authorize an automatic confirmation, a
second real attempt after any failure, another target/scenario, or a broader
scope. Any additional real attempt requires separate, specific authorization
and must remain within the applicable aggregate budget.

### R7.1 Exact target, preflight, and preserved limits

The sole authorized target is:

```text
CHANNEL = -1002758699600
MESSAGE = 598
TYPE = DOCUMENT
SIZE = 11649955
MODE = OPERATIONAL_ONLY
SCENARIO = aligned
```

Before the launcher offers its native confirmation, the applicable offline
gates and a local status-only secure preflight must pass in the proper native
Windows process. The preflight may confirm that the protected credential
vault and protected session can be accessed/decrypted in memory, then must
discard the values and emit only `YES`/`NO` plus provider/state categories.
It must not connect Telethon, issue an RPC, create authentication, expose
secret content, or write credential/session material. If this preflight
cannot be demonstrated, stop before the native prompt.

Apply any `LOCALAPPDATA` override only to the launcher process tree and
restore the inherited value in a `finally` path. This process-only override
addresses the sandbox redirect observed in the current environment, as
recorded by Root; it does not authorize a persistent environment change. The
launcher must present the target, mode, scenario, and limits before
accepting the exact human confirmation phrase
`EXECUTE S6 V2 PROOF common OPERATIONAL_ONLY aligned`. No tool or supervisor
may enter or simulate that confirmation on the user's behalf. No `Execute`
flow or Telegram call may begin before that confirmation.

Keep V1 active, V2 globally ineffective, one worker, the S5 aggregate maximum
of three attempts per media across both phases, and FloodWait at or below 120
seconds. The launcher must show both the user-approved ceilings and the
stricter effective caps already calculated for this proof:

| Limit | Approved ceiling | Effective proof cap |
|---|---:|---:|
| GetFile calls | 139 | 94 |
| GetFileHashes calls | 138 | 92 |
| Reserved bytes | 36,438,016 | 24,641,536 |

Allocate one attempt to phase 1 and the remaining two attempts to phase 2.
These figures do not raise or replace any existing S5 limit.

### R7.2 Authorized files and execution monitoring

R7 authorizes implementation and tests only in these files:

- `tools/manual_proofs/s6_v2_proof_harness.py`
- `tools/manual_proofs/Invoke-S6V2Proof.ps1`
- `tests/manual_proofs/test_s6_v2_proof_harness.py`

If implementation requires another file, stop the affected scope and return
to Root/Architect for adjudication before editing it. Monitoring must operate
independently of `S6_V2_TEST_PROBE`. Emit JSONL progress records using an
allowlist of execution ID, phase, process ID, stage, sequence, and permitted
counts. Do not record secrets, payload bytes/content, arbitrary messages,
exception text, or Telethon objects.

The observable stages must cover supervisor initialization; child spawn,
readiness, and event-loop initialization; isolated SQLite and ledger
creation; gateway construction and categorical restoration; remote identity
validation; phase 1 checkpoint, planned interruption, report, and process
exit; phase 2 initialization and checkpoint validation; complete prefix
reread and hash reconciliation; continuation; finalization; and SQLite/ledger
reconciliation. A heartbeat or supervisor poll is not semantic progress and
must not reset the inactivity timer.

R7.2a — Event ordering and semantic progress clarification: JSONL entries also
require `monotonic_ns` and an allowlisted categorical status/outcome. Sequence
is monotonic per writer/event stream; child and supervisor streams must remain
distinguishable and mergeable by `monotonic_ns`. Semantic progress is limited
to first-time stage completion, a newly increased verified byte/count value,
or successful comparison, checkpoint, or RPC completion. Duplicate stage
events, unchanged counts, heartbeats, and polls do not reset inactivity.
Never store arbitrary exception messages or locals in events or diagnostic
stacks.

Enforce a 30-second child-readiness timeout, 180 seconds of semantic
inactivity (greater than the existing 120-second FloodWait ceiling), and a
900-second aggregate hard deadline measured from the first child spawn.
Poll at approximately one-second intervals and make status visible at least
every 15 seconds. Before stopping a stalled process, capture a bounded number
of sanitized Python stacks without locals; then stop it, confirm its exit,
and persist an incomplete receipt. A failed phase 1 must never open phase 2.

### R7.3 Aligned prefix and overlap semantics

For the authorized aligned case, `P = 1,048,576 = 4*C` and `C = 262,144`;
the wire offset is `W = P`, so the overlap length is zero. Report
`OVERLAP_VERIFICATION = NOT_APPLICABLE_ALIGNED`; do not claim that overlap
bytes were compared.

Phase 2 must reread exactly `P` bytes from remote offset zero and establish
that their SHA-256 equals the phase 1 prefix digest. Continuation at offset
`P` is permitted only after this byte comparison succeeds. Completion of
`aclose` alone is insufficient evidence. Offline regressions must include a
mismatch at the final prefix block and a short prefix; neither may produce a
positive comparison or continuation event.

### R7.4 Symlink integration result boundary

Physical Windows symlink integration that cannot run because of
`WinError 1314` remains `BLOCKED` or `SKIPPED`, separately from deterministic
path-guard coverage. This environment-limited integration result does not
block the current proof gate; it must never be reported as `PASS`. Deterministic
guard coverage may be reported on its own evidence. Do not change Windows
security settings to enable symlink creation.

### R7.5 Preservation and reporting boundary

Do not alter original operational SQLite state, historical `.part` files,
prior proof roots, or historical reports. Do not stage, commit, or push. Keep
`V1_ACTIVE = YES`, `V2_EFFECTIVE = NO`,
`S6_FORMAL_ACCEPTANCE = PENDING`, and `SPRINT_CHECKPOINT = DEFERRED` until
their separate formal decisions. This addendum records authorization and
requirements only; it asserts no implementation, test result, live-proof
result, or acceptance.
