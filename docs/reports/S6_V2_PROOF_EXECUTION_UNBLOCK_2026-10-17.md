# S6 V2 proof execution unblock — 2026-10-17

```text
ACTIVITY = S6_V2_PROOF_EXECUTION_UNBLOCK
RESULT = HARNESS_PREPARED / NO_LIVE_EXECUTION
V1_ACTIVE = YES
V2_EFFECTIVE = NO
V2_ACTIVATION_EXECUTED = NO
REAL_TELEGRAM_CALLS = 0
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
```

## Implemented harness

New isolated assets:

- `tools/manual_proofs/s6_v2_proof_harness.py`
- `tools/manual_proofs/Invoke-S6V2Proof.ps1`
- `tests/manual_proofs/test_s6_v2_proof_harness.py`

The launcher defaults to DryRun, requires an explicit target and integrity
mode, and asks for the exact native PowerShell confirmation before Execute.
Execute creates fresh proof directories, SQLite databases, an authorization
manifest and a durable aggregate request/payload ledger. Child phases are
bound to the target, mode, root, case, phase and ratified contract hash. The
proof-only V2 switch is restored to `False` in `finally`; V1 source and the
operational feature flag are not changed. The restart phase fails closed if
the prior database, partial, report or budget ledger is missing or inconsistent.
Disk space is checked before session restoration or any RPC.

The controlled interruption is intentionally reported as a retryable failed
attempt. Phase 1 must show the exact physical and SQLite prefix, its checkpoint
state and the controlled interruption cause. Phase 2 must run in a different
process. OPERATIONAL_ONLY queue deduplication expects `ALREADY_COMPLETED_V2`;
TRUSTED_REFERENCE queue deduplication expects the existing fail-closed
`V2_COMPLETION_REQUIRES_REFERENCE_REVALIDATION` and verifies no remote request
was issued.

## Candidate assessment

**Common media.** The configured identity is channel `-1002758699600`, message
`598`, historical media ID `5175124468544046445`, size `11,649,955` bytes.
It is eligible as a small-scale `OPERATIONAL_ONLY`/`UNVERIFIED_ORIGIN` resume
candidate if live identity validation succeeds. It is not representative of
large-media throughput. The prior ID is only offline evidence; a protected
session must resolve the channel peer from its existing cache and confirm the
identity before payload. No dialog discovery or remote query was done here.

**Controlled media.** Channel `-1002368271467`, message `7603`, media ID
`5089068167339181674`, size `1,119,129,690` bytes. DryRun re-read the local
original file and verified size and SHA-256 against the preparation manifest;
the historical refetch record binds the same Telegram identity and size. A
fresh V2-schema manifest is created only in a new proof root. The reported
provenance says the user supplied the path; creator/origin was not independently
attested. Live availability and identity still require the proof's first
identity gate. This candidate remains separate from the common-media proof.

## Request and payload budgets

`C = 262,144` bytes. S5 allows one initial interrupted phase and up to three
attempts in the restart process. Counts below are conservative caps. Actual
GetFileHashes calls may be lower because returned hash ranges can cover more
than one chunk. Current app behavior queries GetFileHashes in either V2 mode;
these results are independent evidence, not a required full-coverage criterion
for OPERATIONAL_ONLY or TRUSTED_REFERENCE. The adapter also issues one
`get_messages` metadata RPC for each hash query, up to four identity
`get_messages` calls per two-phase case, and two `get_me` session checks.

| Proof profile | Phase 1 GetFile | Each resume attempt GetFile | Restart process cap | Aggregate GetFile | Aggregate GetFileHashes | Phase 1 payload reservation | Restart process payload reservation | Aggregate payload reservation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Common OPERATIONAL_ONLY, aligned | 4 | 45 | 135 | 139 | 138 | 1,048,576 B | 35,389,440 B | 36,438,016 B |
| Common OPERATIONAL_ONLY, +123 B prefix | 5 | 45 | 135 | 140 | 138 | 1,310,720 B | 35,389,440 B | 36,700,160 B |
| Controlled TRUSTED_REFERENCE, aligned | 512 | 3,758 | 11,274 | 11,786 | 12,813 | 134,217,728 B | 2,955,411,456 B | 3,089,629,184 B |
| Controlled TRUSTED_REFERENCE, +123 B prefix | 513 | 3,758 | 11,274 | 11,787 | 12,813 | 134,479,872 B | 2,955,411,456 B | 3,089,891,328 B |

The per-attempt GetFileHashes caps are 46 for the common target and 4,271 for
the controlled target; phase 1 stops before hash evaluation. OPERATIONAL_ONLY
reserves and rereads the entire prefix on resume. TRUSTED_REFERENCE does not
reread the full remote prefix; an unaligned resume includes its overlap chunk
and final byte-for-byte comparison against the reference. The computed
request-quantized reservation admits the short final GetFile chunk: with the
last actual response shorter than `C`, exactly one full `C` lease remains in
the plan.

For comparison, controlled OPERATIONAL_ONLY has 13,322 aligned / 13,323
unaligned aggregate GetFile calls and 3,492,282,368 / 3,492,544,512 bytes
reserved. Hypothetical common TRUSTED_REFERENCE has 127 aligned / 128
unaligned aggregate GetFile calls and 33,292,288 / 33,554,432 bytes reserved.
The harness rejects those target/mode pairings; these comparison figures are
not executable profiles.

S5 disk margin is `max(1 GiB, 10% of pending bytes)`. Current required free
space on the C: volume is 1,085,391,779 bytes for a fresh common attempt and
2,192,871,514 bytes for a fresh controlled attempt. Restart checks the
remaining bytes plus the same S5 margin: 1,084,343,203 bytes common aligned
(1,084,343,080 bytes unaligned) and 2,058,653,786 bytes controlled aligned
(2,058,653,663 bytes unaligned). At inspection time C: had 51,712,581,632
bytes free. Execute rechecks before each process; that current reading is not a
future reservation.

The aggregate selected-media RPC caps, including GetMessages metadata and
GetMe but excluding connection/reconnect internals, are 421 common aligned,
422 common unaligned, 37,418 controlled aligned and 37,419 controlled
unaligned. FloodWait is bounded by 120 seconds in the restart process; S5
attempts are capped at three. A higher FloodWait, unresolved peer, changed
identity/reference, missing checkpoint/ledger, insufficient disk, reservation
exhaustion, divergent bytes/hash evidence, failed final comparison or missing
versioned evidence stops the proof without downgrade.

## Offline validation

- Common and controlled DryRun: PASS; no Telegram calls, original SQLite access
  or historical `.part` input. The controlled DryRun revalidated the original
  reference file and emitted a new manifest in its proof-only root.
- Targeted harness and S6 evidence tests: 13 passed, 13 deselected.
- Ruff: PASS for the two new Python files.
- Compileall: PASS for the two new Python files.
- PowerShell parser: PASS for the native launcher.
- `git diff --check`: PASS (line-ending notices from pre-existing dirty files
  only).
- The full `tests/unit/test_s6_v2.py` run was not completed: it hung at the
  existing `test_v2_is_inactive_before_database_or_gateway_use` before the
  test body, matching the previously recorded Windows pytest runtime issue.
  The three synchronous S6 classifier/reference tests were included in the
  passing targeted selection. No existing source, V1 behavior, SQLite or
  historical `.part` was changed by this activity.

## Delivery state

```text
COMMON_TARGET_ELIGIBILITY = CONDITIONAL / SMALL_SCALE OPERATIONAL_ONLY / LIVE IDENTITY GATE PENDING
CONTROLLED_TARGET_ELIGIBILITY = LOCAL REFERENCE PASS / LIVE IDENTITY AND AVAILABILITY GATE PENDING
V2_PROOF_HARNESS_READY = YES
ISOLATED_ACTIVATION_DESIGN = READY / NATIVE CONFIRMATION + ONE-TIME SCOPED TOKEN + ROOT-BOUND CHILD AUTHORIZATION
V2_ACTIVATION_EXECUTED = NO
NATIVE_CONFIRMATION_READY = YES / STATIC PARSE PASS; EXECUTE NOT INVOKED
DRYRUN = PASS / BOTH TARGETS
TARGETED_TESTS = PASS / 13 passed / 13 deselected
SAFETY_GATE = PASS OFFLINE / NO LIVE PROOF AUTHORIZATION
REAL_TELEGRAM_CALLS = 0
V1_ACTIVE = YES
V2_EFFECTIVE = NO
REAL_PROOF_READY = NO / USER AUTHORIZATION AND LIVE IDENTITY GATES PENDING
NEXT_ACTION = USER_SCOPED_REAL_PROOF_AUTHORIZATION
```

No commit, push, activation, formal S6 acceptance or sprint checkpoint was
performed.
