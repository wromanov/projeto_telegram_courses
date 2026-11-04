# S6 V2 common aligned final reproof — 2026-10-17

```text
ACTIVITY = S6_V2_COMMON_ALIGNED_FINAL_REPROOF
RESULT = INCOMPLETE / STOP BEFORE MEDIA DOWNLOAD
PREFLIGHT = BLOCKED / CREDENTIALS AND PROTECTED SESSION UNAVAILABLE
PHASE_1_STATUS = NOT_STARTED
PHASE_2_STATUS = NOT_STARTED
TWO_PROCESS_PROOF = NOT_RUN
REAL_TELEGRAM_CALLS = 0
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
```

## Authority and preflight evidence

The current user instruction authorized one new `common / OPERATIONAL_ONLY /
aligned` real proof, with the fixed target and limits below. The approved V2
design identity was verified against the ratification record: SHA-256
`C9C8A59B5F370B67A86D04CE7407517965711AE5E9780A17DED1C56A747BDF52`. The
approved/frozen S6 V1 contract remains canonical; the ratified V2 draft is not
effective. The four harness corrections and prior synthetic gate result were
present in the current source and documented in the prior remediation report.

Repository facts at preflight: root
`C:\Users\walac\desenvolvimento\projeto_telegram_courses`, branch
`work/s0-bootstrap`, HEAD
`98d9d6b9ce152b8d2764a4d160fcbdf4722fb257`, upstream
`origin/work/s0-bootstrap`. The worktree contains extensive prior changes;
they were preserved. No Git operation was performed.

DryRun passed and created a new isolated root:

`C:\Users\walac\desenvolvimento\projeto_telegram_courses\.s6-v2-final-reproof-preflight\s6-v2-real-proof-e44d09a39bf64f77807b0c9b223d3907`

The DryRun report records the fixed target `-1002758699600/598`, media ID
`5175124468544046445`, kind `DOCUMENT`, expected size `11,649,955`, prefix
`1,048,576`, `V1_ACTIVE=true`, `V2_EFFECTIVE=false`, and zero Telegram calls.
The aggregate limits match the requested caps: GetFile `139`, GetFileHashes
`138`, reserved payload `36,438,016` bytes, up to 3 attempts, 1 worker, and
FloodWait limit 120 seconds. Available disk space was `50,562,617,344` bytes;
the harness requires `1,085,391,779` bytes before phase 1 and `1,084,343,203`
bytes before resume. The root is new and contains only the DryRun proof SQLite
marker and its report; it is separate from all previous real-proof roots.

The protected credential status command reported `credentials vault
configured: no` and `credentials available: no`. A metadata-only check of the
protected session vault reported `PROTECTED_SESSION_ARTIFACT_AVAILABLE=NO`;
no credential or session contents were read. Consequently the session gate
failed. Remote identity could not be revalidated without restoring that
session. No native Execute confirmation was issued, no child process started,
and no media request or download occurred.

## Gate results

| Gate | Result |
|---|---|
| Ratified V2 design identity | PASS — digest matches approval record |
| Correction-cycle source integration | PASS — four bounded corrections present |
| DryRun | PASS — no network, V1 active, V2 ineffective |
| Static target and expected size | PASS — target profile matches requested identity and size |
| Disk and fixed request/payload budget | PASS — within configured requirements and limits |
| Fresh isolated root / conflict check | PASS — unique new root; no prior proof root reused |
| Protected credentials | FAIL — unavailable in this runtime |
| Protected session | FAIL — artifact unavailable in this runtime |
| Live Telegram identity | NOT_CHECKED — stopped before session restoration |
| Native Execute confirmation | NOT_REACHED |
| Phase 1 / phase 2 | NOT_STARTED |

The credential/session failure is a required preflight stop. No real proof
gate is promoted by static identity data or the earlier synthetic test.

## Final fields

```text
PHASE_1_STATUS = NOT_STARTED
PHASE_1_PID = NOT_AVAILABLE
PHASE_1_EXIT_CODE = NOT_AVAILABLE
PHASE_1_JSON = NOT_CREATED
PHASE_1_CHECKPOINT = NOT_CREATED
PHASE_2_STATUS = NOT_STARTED
PHASE_2_PID = NOT_AVAILABLE
PHASE_2_EXIT_CODE = NOT_AVAILABLE
PHASE_2_JSON = NOT_CREATED
TWO_PROCESS_PROOF = NOT_RUN
CONTROLLED_INTERRUPTION = NOT_RUN
FULL_PREFIX_REREAD = NOT_RUN
OVERLAP_VERIFICATION = NOT_RUN
FINAL_SIZE = NOT_AVAILABLE
FINAL_SHA256 = NOT_AVAILABLE
FINAL_STATE = NOT_AVAILABLE
INTEGRITY_CLASSIFICATION = NOT_AVAILABLE
GETFILE_CALLS = 0
GETFILEHASHES_CALLS = 0
RESERVED_BYTES = 0
UNCERTAIN_BYTES = 0
AUXILIARY_RPCS_OBSERVED = 0 / no connection attempted
SQLITE_RECONCILIATION = NOT_RUN
LEDGER_RECONCILIATION = NOT_RUN
DEDUPLICATION = NOT_RUN
SAFETY_GATE = STOP_BEFORE_MEDIA_DOWNLOAD / protected credentials and session unavailable
V1_ACTIVE = YES
V2_EFFECTIVE = NO
REAL_TELEGRAM_CALLS = 0
OPERATIONAL_SQLITE_ACCESS = NO
HISTORICAL_PART_ACCESS = NO
GIT_ADD = NO / GIT_COMMIT = NO / GIT_PUSH = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
NEXT_ACTION = Make the existing protected credentials and session available in the functional Windows runtime, then resume preflight; do not execute automatically.
```
