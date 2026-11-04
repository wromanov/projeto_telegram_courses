# S6 V2 Common Aligned Reproof — 2026-10-17

```text
ACTIVITY = S6_V2_COMMON_ALIGNED_REPROOF
RESULT = INCOMPLETE
TWO_PROCESS_PROOF = INCOMPLETE
REAL_TELEGRAM_CALLS = YES / bounded calls recorded below; total API count partly uninstrumented
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
```

## Scope and preflight

The user authorized one real proof for channel `-1002758699600`, message `598`,
mode `OPERATIONAL_ONLY`, aligned 1 MiB checkpoint, two processes, one worker.
The native launcher received the exact required confirmation. The launcher
created a new isolated root and proof-only SQLite/ledger; it did not open the
operational SQLite or historical `.part` files. There was no upload, Git
operation, or global V2 activation.

Preflight evidence: repository `work/s0-bootstrap`, HEAD
`98d9d6b9ce152b8d2764a4d160fcbdf4722fb257`; the ratified V2 design digest
matched `C9C8A59B5F370B67A86D04CE7407517965711AE5E9780A17DED1C56A747BDF52`;
the corrected harness suite passed 26 tests; V1 was active and global
`V2_EFFECTIVE` was false. The proof root had approximately 50.95 GB free before
phase 1, exceeding its 1,085,391,779-byte minimum disk requirement.

Target identity preflight passed for the configured message/media identity,
including the expected 11,649,955-byte size. The observed remote media ID was
`5175124468544046445`.

## Phase evidence

Evidence root:
`C:\Users\walac\AppData\Local\Temp\s6-v2-real-proof-8ed3209295e24714ab5ed0be24fe20a1`

| Field | Observed result |
|---|---|
| Process 1 PID / process-handle PID | `30596` / `30596` |
| Process 1 observed exit | `5`, confirmed by supervisor |
| Child-declared exit | `0` — conflicts with observed process exit |
| Child-declared status / stop | `PROCESS_INTERRUPTED` / `CONTROLLED_INTERRUPT` |
| Supervisor phase status / stop | `PROCESS_FAILED` / `CONTROLLED_INTERRUPT`; stdout recorded `STOP=PHASE_REPORT_WRITE_FAILED:RuntimeError` |
| Phase 1 checkpoint | Physical `.part` and proof SQLite both contain 1,048,576 bytes; partial SHA-256 is `dee6ef9f3ed4b021b55cefb90d9f03cfbc958cc1dbb6d00238b2a7576ae72a95`; supervisor `checkpoint_confirmed=false` |
| Phase 1 reports | `aligned/phase-1.json` and `aligned/phase-1.child.json` exist |
| Process 2 | Not started; no PID, exit code, resume offset, stop condition, or phase 2 reports |
| Prefix reread / overlap | Not performed |
| Final file / size / SHA-256 | No final file; final size and SHA-256 unavailable |
| SQLite final state | `FAILED_RETRYABLE`; downloaded/checkpoint bytes `1,048,576`; SHA-256 `NULL` |
| Versioned V2 evidence | No evidence row; `COMPLETED_V2` was not reached |
| Integrity classification | Not established; `UNVERIFIED_ORIGIN` was not persisted as completion evidence |
| Deduplication | Not run |

## Request and payload accounting

The durable proof ledger and phase receipt agree:

| Counter | Observed |
|---|---:|
| GetFile | 4 |
| GetFileHashes | 0 |
| Payload reserved | 1,048,576 bytes |
| Payload received | 1,048,576 bytes |
| Uncertain bytes | 0 |
| Identity `GetMessages` | 1 |
| Direct `GetMe` | 1 |
| Session restore wrapper calls | 1 |
| Known wrapped remote-call subtotal | 6 |

`TelegramClient.connect()` internal RPCs are uninstrumented, so the exact total
Telegram API request count is unknown and is not inferred. The aggregate
budget gate remained within limits: GetFile cap 139, GetFileHashes cap 138,
reserved-payload cap 36,438,016 bytes. Only the phase 1 budget was consumed.

## Failure diagnosis and stop

The planned prefix interruption occurred after exactly four GetFile requests.
The child result was published, but the child process then exited with code 5
and `PHASE_REPORT_WRITE_FAILED`. The supervisor correctly refused to treat the
phase as accepted and did not start process 2.

The immediate writer failure is explained by a confirmed serialization
mismatch: `_atomic_write_json` compares the parsed JSON value with the original
Python object. The phase result contains tuple-valued queue outcomes; JSON
round-tripping converts those tuples to lists, so the equality check fails
after publication. Consequently, the child report says exit 0 while the
actual process exit is 5.

There is a second independent checkpoint-evidence gap: the phase 1 child result
does not contain `prefix_sha256`, while the supervisor requires that field to
match its read-only hash of the physical `.part`. Thus
`checkpoint_confirmed=false` even though physical and SQLite byte counts
match. Either gap is sufficient to keep phase 2 gated; neither was bypassed.

The proof stopped after phase 1. No retry, phase 2, resume, overlap check,
finalization, or deduplication was attempted. The proof directory and its
reports are preserved as evidence.

```text
PROCESS_1_PID = 30596
PROCESS_1_EXIT_CODE = 5 / CHILD_DECLARED_EXIT_CODE = 0
PROCESS_1_STOP_CONDITION = CONTROLLED_INTERRUPT / SUPERVISOR_STATUS = PROCESS_FAILED
PROCESS_1_CHECKPOINT = 1,048,576 physical and SQLite bytes / not accepted by supervisor
PROCESS_2_PID = NOT_STARTED
PROCESS_2_EXIT_CODE = NOT_AVAILABLE
PROCESS_2_RESUME_OFFSET = NOT_AVAILABLE
PROCESS_2_STOP_CONDITION = NOT_STARTED
FULL_PREFIX_REREAD = NOT_PERFORMED
OVERLAP_VERIFICATION = NOT_PERFORMED
FINAL_SIZE = NOT_AVAILABLE
FINAL_SHA256 = NOT_AVAILABLE
FINAL_STATE = FAILED_RETRYABLE
INTEGRITY_CLASSIFICATION = NOT_ESTABLISHED
GETFILE_CALLS = 4
GETFILEHASHES_CALLS = 0
RESERVED_BYTES = 1,048,576
UNCERTAIN_BYTES = 0
SAFETY_GATE = STOPPED_FAIL_CLOSED_AFTER_PHASE_1
NEXT_ACTION = USER_NONALIGNED_PROOF_DECISION / only after deciding whether to authorize offline harness correction and a new aligned proof; no automatic retry
```

The attempt does not satisfy acceptance. S6 formal acceptance remains pending;
the sprint checkpoint remains deferred. No continuity, contract, launcher,
downloader, operational database, or historical partial-file changes were
made by this proof attempt.
