# S6 V2 Proof Harness Correction — 2026-10-17

```text
ACTIVITY = S6_V2_PROOF_HARNESS_CORRECTION
RESULT = COMPLETE_FOR_OFFLINE_HARNESS_SCOPE
TELEGRAM_CALLS = 0
DOWNLOADS = 0
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
```

## Scope and governance

Corrected only the isolated proof harness and its offline tests. The bounded
correction contract is
[`docs/contracts/S6_V2_PROOF_HARNESS_CORRECTION_CONTRACT.md`](../contracts/S6_V2_PROOF_HARNESS_CORRECTION_CONTRACT.md).
The canonical S5/S6 contracts, downloader, gateway, operational SQLite,
historical `.part` files, earlier proof reports, and V1 contract were not
edited. No Git mutation, formal acceptance, or sprint checkpoint was made.

The ratified V2 contract digest still matches the harness pin:

```text
C9C8A59B5F370B67A86D04CE7407517965711AE5E9780A17DED1C56A747BDF52
```

## Findings and correction

- **Phase 1 stop boundary — probable, high confidence.** The historical record
  is consistent with requesting one more chunk after the configured 1 MiB
  prefix. The exact historical cause remains probable because the original
  executed source and stack trace were not preserved. The harness now
  interrupts immediately after the exact prefix. Its regression asserts four
  256 KiB reservations and proves no fifth reservation occurs.
- **Missing phase 2 JSON — structural cause confirmed, high confidence.** The
  child previously wrote its result only after the entire async stage returned.
  An exception or crash before that write left no child report. The immediate
  historical exception remains unknown. The child now writes an atomic
  provisional result for normal return and recoverable exceptions; the
  supervisor records process-handle PID, observed start/end and exit, validates
  the distinct child report, and marks missing/corrupt evidence incomplete.
- Atomic publication uses a same-directory exclusive temporary file, strict
  JSON, flush/fsync, replace, and read-back validation. Existing terminal
  evidence is not overwritten. Phase receipts, execution IDs, budgets,
  checkpoint/final file observations, and child declarations are reconciled
  separately; incomplete evidence cannot become PASS.
- Process-boundary tests use actual offline child processes with distinct PIDs
  and execution IDs. A stale/missing-PID legacy phase 1 report cannot be
  credited as a new checkpoint.
- Telethon's internal RPCs during `connect()` remain uninstrumented. The
  report records this count as `null`; it does not mislabel known wrapped
  calls as an exact total Telegram API count.

## Offline verification

| Check | Result |
|---|---|
| Proof harness tests, including native asyncio subprocess | PASS — 26 passed |
| Selected S5/S6 regression set | PASS — 207 passed, 2 skipped |
| Skips | The two parametrized real-evidence cases require `S6_REAL_EVIDENCE_PATH`; no real proof was run |
| Ruff, changed Python files | PASS |
| `compileall`, changed Python files | PASS |
| PowerShell launcher parser | PASS |
| `git diff --check`, changed tracked Python files | PASS |
| Common OPERATIONAL_ONLY DryRun | PASS — plan-only SQLite, zero network calls, V2 false |
| Native asyncio diagnostic | PASS in native Windows runner; sandbox subprocess timed out and was not counted as a pass |

The correction suite and regressions used isolated temporary roots. DryRun
produced only an isolated plan report and proof database. No Telegram session
was opened, no target was queried or transferred, and no operational database
or historical partial file was accessed by this activity.

## Common aligned proof budget (planning only)

Target: channel `-1002758699600`, message `598`, expected `11,649,955` bytes;
mode `OPERATIONAL_ONLY`; 1 MiB aligned phase 1 prefix; one worker.

| Budget | Bound |
|---|---:|
| Phase 1 GetFile | 4 |
| Resume GetFile per S5 attempt | 45 |
| Aggregate GetFile | 139 |
| GetFileHashes per attempt | 46 |
| Aggregate GetFileHashes | 138 |
| Aggregate reserved payload | 36,438,016 bytes |
| Resume reservation per attempt | 11,796,480 bytes |
| S5 attempts per resume process | 3 |
| FloodWait limit per resume process | 120 seconds |
| Disk minimum phase 1 | 1,085,391,779 bytes |
| Disk minimum resume | 1,084,343,203 bytes |
| Free space observed on C: during planning | 51,220,783,104 bytes |

The arithmetic reserves each GetFile in 256 KiB units. At the aligned prefix,
there is no overlap. The four-call phase 1 cap and aggregate ledger reject a
fifth request before it can reach the gateway. The maximum aggregate payload
reservation is below the S5 ceiling used for this proof. Identity and restore
call counters are bounded separately. The internal `TelegramClient.connect()`
RPC count remains unknown and must not be represented as part of an exact
observed total. These are preflight bounds only, not consumed requests or proof
results.

## Final gate

```text
IMPLEMENTATION_READINESS = OFFLINE_HARNESS_READY
V1_COMPATIBILITY = PRESERVED
V2_ACTIVATION_LOCK = PRESERVED_OUTSIDE_SCOPED_CHILD
TEST_EVIDENCE = 26_HARNESS_PASS; 207_REGRESSION_PASS; 2_REAL_EVIDENCE_CASES_SKIPPED
DRYRUN = PASS
REAL_PROOF_EXECUTED = NO
REAL_TELEGRAM_CALLS = 0
REAL_PROOF_READY = YES_FOR_NEXT_USER_AUTHORIZED_PROOF_DECISION
NEXT_ACTION = USER_SCOPED_REAL_PROOF_AUTHORIZATION
```

The pre-existing `PROJECT_STATE.md` does not reflect the already-preserved
real-proof evidence referenced during preflight. It was not reconciled here:
this bounded correction did not authorize a checkpoint or formal state update.
