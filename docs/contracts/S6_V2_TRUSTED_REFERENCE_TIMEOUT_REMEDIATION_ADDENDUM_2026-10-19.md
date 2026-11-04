# S6 V2 TRUSTED_REFERENCE — adendo de timeout e reconciliação

```text
CONTRACT_ID = S6_V2_TRUSTED_REFERENCE_TIMEOUT_REMEDIATION_ADDENDUM_2026_10_19
DOCUMENT_ROLE = ACTIVITY_SCOPED_TECHNICAL_ADDENDUM
ACTIVITY = S6_V2_TRUSTED_REFERENCE_TIMEOUT_REMEDIATION
STATUS = CLOSED_FOR_BOUNDED_OFFLINE_HARNESS_AND_TEST_IMPLEMENTATION
CANONICAL_S5_OR_S6_CONTRACT_CHANGE = NO
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_RETRY = NOT_AUTHORIZED
GIT_ADD_COMMIT_PUSH = NO
```

## 1. Authority and scope

This activity-scoped addendum records the root-adjudicated timeout and
interruption contract for the isolated `TRUSTED_REFERENCE` proof harness. It
does not amend a canonical S5/S6 contract, make V2 effective, accept S6, close
the sprint checkpoint, or authorize a real proof or retry.

Implementation scope is limited to the proof harness and its offline tests:

- `tools/manual_proofs/s6_v2_proof_harness.py`
- `tests/manual_proofs/test_s6_v2_proof_harness.py`

Do not modify the operational downloader, operational SQLite, historical
`.part` files, historical evidence, or canonical contracts. All validation
under this addendum is offline and synthetic. No Telegram calls, real
downloads, or retries are permitted.

## 2. Adjudicated cause and observed behavior

The 900-second aggregate deadline originates in R7.2 of
`S6_UNIFIED_CORRECTION_CONTRACT_V1.md`. That policy governed the common
`OPERATIONAL_ONLY` scenario with an 11,649,955-byte allowance; its
implementation was applied globally, including the much larger controlled
`TRUSTED_REFERENCE` payload. The prior phase receipt records a 3,600-second
requested process timeout and a 899.947-second effective timeout. The
effective limit was the lesser of the request and the time remaining in the
900-second aggregate deadline.

The latest controlled-run observations supplied in this activity's root
adjudication are: 833,617,920 payload bytes in 863.160 seconds; the slowest
full 60-second throughput bucket was 688,052 bytes/second; the last semantic
byte advancement occurred 0.254 seconds before the aggregate timeout, and the
largest observed gap between byte advancements was 1.152 seconds. These
observations do not support inactivity, Telegram, or integrity failure as the
cause of the stop. The global deadline expired while transfer was still
advancing.

The repeated `semantic_events=12` terminal display is `len(seen_stages)`: the
number of distinct stage types observed. It counts neither semantic events
nor bytes. Byte progress continued to renew `last_semantic` in the harness;
the repeated terminal value was visually misleading and did not indicate
inactivity or stopped transfer. The harness must report confirmed byte
progress separately from this distinct-stage count.

Phase 2 lacked an individual child report because the child writes that report
only after normal stage completion; supervisor termination can occur before
that write. A child report is therefore not guaranteed after forced
termination. The supervisor's durable receipt remains mandatory and must
represent the missing child evidence as incomplete; it must not synthesize
child facts.

`budget.within_caps=false` in this interrupted run means the budget result
could not be established from complete counters: the observed numeric GetFile
counters were below their limits, while identity/GetMe values were null when
the child report was absent. It does not establish numeric cap overrun.
Preserve this legacy aggregate result as fail-closed. New budget output must
distinguish at least numeric cap exceeded, unresolved reservation, missing
counters/evidence, and ledger corruption. Unknown or missing counters cannot
be reported as within caps or as a numeric overrun without evidence.

## 3. Deadline policy by scenario

Deadlines are measured from the first child spawn. The effective timeout for
each child is the lesser of its requested per-process cap and the remaining
aggregate hard-deadline time. The 30-second cancellation grace is included
within, and cannot extend, the aggregate deadline.

| Scenario | Requested per-process cap | Aggregate hard deadline | Purpose |
|---|---:|---:|---|
| `common / OPERATIONAL_ONLY` | 3,600 seconds | 900 seconds | Preserve the existing R7.2 common-scenario policy. |
| `controlled / TRUSTED_REFERENCE` | 4,500 seconds | 4,800 seconds | Allow the approved controlled payload reservation to complete under the measured throughput basis. |

The controlled aggregate basis is the approved payload reservation of
2,230,321,152 bytes divided by the slowest observed full 60-second bucket of
688,052 bytes/second, or approximately 3,241.5 seconds. The adjudicated
sizing adds a 10% duration reserve (approximately 324.2 seconds), up to 120
seconds for the existing FloodWait ceiling, and 300 seconds for startup and
finalization, totaling approximately 3,985.7 seconds. The adjudicated
process/aggregate caps are padded to 4,500/4,800 seconds respectively. The
full controlled transfer envelope is bounded by the observed minimum full
bucket; no historical remote hash-query throughput is available to claim or
use as a separate measured rate. This calculation sizes finite deadlines; it
does not remove the deadline or authorize additional payload, attempts, or
retries.

The 4,500-second controlled process cap leaves aggregate time for both phases
and lifecycle/finalization overhead. Actual child time remains bounded by
whichever limit expires first. Child readiness retains its existing
30-second bound. The semantic inactivity timeout is 180 seconds without
semantic progress.

## 4. Transfer progress and inactivity

The supervisor emits a progress heartbeat at least every 15 seconds. Each
heartbeat reports separately:

- confirmed bytes received;
- confirmed bytes persisted;
- observed byte rate over the reporting interval; and
- phase, process identity, timestamp, and current lifecycle stage from the
  existing allowlist.

Heartbeat emission, polling, duplicate events, unchanged counts, and
unverified byte estimates do not reset semantic inactivity. Semantic
inactivity resets only on evidenced semantic progress: first completion of a
stage, a newly increased verified byte/count value, or successful completion
of an RPC, checkpoint, hash/equality comparison, or other already-defined
semantic gate. Byte counts and byte rate remain explicit data, separate from
the semantic-event counter. Do not expose payload content, secrets, arbitrary
exception text, or unbounded diagnostic data.

## 5. Timeout, child termination, and receipts

On semantic inactivity or an approaching hard deadline, the supervisor:

1. records a sanitized timeout observation and the latest counters;
2. requests cooperative child cancellation;
3. allows no more than 30 seconds for cancellation and confirmed process exit,
   subject to the aggregate hard deadline;
4. if necessary, force-terminates the child and waits for confirmed exit;
5. records the actual observed exit status, or leaves the execution
   incomplete if exit cannot be confirmed; and
6. persists an authoritative supervisor receipt before any recovery or
   reconciliation is considered complete.

The receipt separates supervisor observations from child declarations. It
records the configured/requested and effective timeouts, aggregate deadline
and remaining time, termination method, observed process exit, last semantic
progress, heartbeat byte counts/rate, phase, and evidence availability. A
missing child report is explicitly `EVIDENCE_INCOMPLETE`. Missing evidence,
unconfirmed exit, timeout, or interrupted transfer cannot produce a phase
`PASS`, `COMPLETED_V2`, or `TRUSTED_REFERENCE_MATCH`.

## 6. Safe SQLite, physical-file, and ledger reconciliation

Reconciliation begins only after the supervisor confirms child exit. If exit
cannot be confirmed, perform no recovery write or reconciliation and classify
the state `BLOCKED`. After confirmed exit, reconciliation is confined to the
fresh proof root and reconciles, without overwriting child facts:

1. the proof-only SQLite row and checkpoint state;
2. physical `.part` and final-file lengths/identities;
3. SQLite journal/checkpoint state available after process exit; and
4. the durable budget-ledger reservation, receipt, and confirmed byte
   counters.

Use a transactional, idempotent reconciliation record. For the timed-out
phase only, after confirmed child exit, transition the proof-only download
row `DOWNLOADING -> FAILED_RETRYABLE` and its `SELECTED` attempt to
`FAILED_RETRYABLE`, categorized `SUPERVISOR_TIMEOUT`. Preserve checkpoint and
physical file; do not create completion evidence or mark the media complete.
The budget ledger settles each reservation by `reservation_id` with explicit
`PENDING`, `RECEIVED`, or `UNCERTAIN` state. A pending reservation becomes
`UNCERTAIN` exactly once during timeout settlement; retries or repeated
reconciliation cannot settle or count it again. Preserve original reservation
and receipt facts. Do not change an operational database or historical file.
A missing receipt, inconsistent ledger, or corrupt SQLite state remains
explicitly incomplete or blocked. Reconciliation must never infer successful
bytes, fabricate a receipt, or turn incomplete evidence into `PASS`.

The aggregate outcome remains `INCOMPLETE` when interruption prevents a
conclusion and `BLOCKED` when a detected safety, identity, ledger, or
reconciliation violation prevents safe completion. Neither outcome is a
trusted-reference match.

## 7. Offline acceptance matrix

All cases below use controlled clocks and isolated synthetic fixtures. A
skipped, blocked, or unexecuted case is not a pass.

| Case | Required evidence |
|---|---|
| Long transfer with progress | Heartbeats show monotonically confirmed received/persisted bytes and rate; semantic progress prevents an inactivity timeout while the aggregate deadline remains enforced. |
| Transfer stopped without progress | 180-second semantic inactivity triggers cancellation; no heartbeat alone resets it. |
| Aggregate deadline | Deadline is measured from first spawn, clips a child timeout, includes the cancellation grace, and terminates safely. |
| Near-deadline transfer | Byte progress near the deadline does not extend the hard deadline; exit and receipt remain bounded. |
| Cancellation during GetFile | Cancellation/force-termination path confirms exit or leaves the execution incomplete; no fabricated receipt. |
| Pending chunk reservation | Reserved but unreceived bytes remain uncertain exactly once through reconciliation. |
| Interrupted SQLite `DOWNLOADING` | Proof DB/checkpoint and physical file are reconciled after confirmed exit; no false terminal success. |
| Interrupted attempt `SELECTED` | Selection/attempt state remains evidence-backed and interruption is explicit. |
| Receipt absent after timeout | Supervisor receipt is mandatory; missing child report is explicitly incomplete. |
| Reconciliation without false PASS | Missing, contradictory, or corrupt evidence cannot satisfy phase, budget, or aggregate PASS. |
| Two-process synthetic E2E | Distinct native Windows child processes, bounded timeout behavior, receipts, and reconciliation are demonstrated offline. |
| Final TRUSTED_REFERENCE comparison | Only full byte equality, exact size/hash, valid lifecycle, preserved reference, reconciled evidence, and no veto yield `TRUSTED_REFERENCE_MATCH`. |

Required validation also includes the applicable S5/S6 regressions, Ruff,
Python compilation, PowerShell parser, DryRuns, and `git diff --check`. These
are acceptance requirements, not results asserted by this addendum. No new
Telegram call, real download, or retry is part of validation.

## 8. Evidence boundary and open documentation gaps

The prior 900-second policy and its scenario context are recorded in section
R7.2 of `docs/contracts/S6_UNIFIED_CORRECTION_CONTRACT_V1.md`. The earlier
3,600-second request and approximately 899.947-second effective receipt are
recorded in section 2 of
`docs/contracts/S6_V2_PROOF_HARNESS_TIMEOUT_RECEIPT_ADDENDUM_2026-10-18.md`.
The controlled payload size/reservation is recorded in
`docs/contracts/S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_CONTRACT_2026-10-18.md`
and `docs/reports/S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_2026-10-18.md`.
Existing timeout, receipt, lifecycle, and fail-closed evidence requirements
are also in `docs/contracts/S6_V2_PROOF_HARNESS_CORRECTION_CONTRACT.md`.

The latest run-specific throughput bucket, byte totals/timestamps,
`semantic_events` terminal observations, phase-2 report absence, and
`budget.within_caps=false` interpretation are recorded here from the root's
adjudication. The Architect confirmed these observations by read-only
inspection of `C:\Users\walac\AppData\Local\Temp\s6v2\s6t-e8c56f34f0544e2fa5639283c85e7361`.
This temporary evidence bundle is external to the repository and remains
historical/read-only. Offline implementation, validation results, and final
evidence reconciliation are recorded in the activity's validation report
`docs/reports/S6_V2_TRUSTED_REFERENCE_TIMEOUT_REMEDIATION_2026-10-19.md`.
This addendum specifies the bounded contract and does not itself assert an
acceptance `PASS`.

```text
HISTORICAL_EVIDENCE = READ_ONLY
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_RETRY = NOT_AUTHORIZED
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
NEXT_ACTION = USER_CONTROLLED_REAL_REPROOF_AUTHORIZATION
```
