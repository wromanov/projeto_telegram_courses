# S6 V2 common aligned proof resume — 2026-10-17

```text
ACTIVITY = S6_V2_COMMON_ALIGNED_PROOF_RESUME
RESULT = INCOMPLETE
REMOTE_IDENTITY = NOT_CHECKED / PHASE-1 CHILD REPORT NOT PRODUCED
PROCESS_1 = INCOMPLETE / SUPERVISOR SPAWN PID 32104 / EXIT CODE UNCONFIRMED
PROCESS_2 = NOT_STARTED
CHECKPOINT = NOT_CREATED
PREFIX_SHA256 = NOT_AVAILABLE
FULL_PREFIX_REREAD = NOT_RUN
OVERLAP_VERIFICATION = NOT_RUN
FINAL_BYTES = NOT_AVAILABLE
FINAL_SHA256 = NOT_AVAILABLE
FINAL_STATE = NOT_AVAILABLE
INTEGRITY_CLASSIFICATION = NOT_AVAILABLE
GETFILE_CALLS = 0 / NO PROOF LEDGER CREATED
GETFILEHASHES_CALLS = 0 / NO PROOF LEDGER CREATED
RESERVED_BYTES = 0 / NO PROOF LEDGER CREATED
UNCERTAIN_BYTES = 0 / NO PROOF LEDGER CREATED
AUXILIARY_RPCS_OBSERVED = 0 / GATEWAY NOT REACHED
RPC_TOTAL_UNKNOWN = NO / NO TELETHON GATEWAY OR CONNECTION CREATED
SQLITE_RECONCILIATION = INCOMPLETE / PROOF SQLITE NOT CREATED; OPERATIONAL SQLITE EXCLUDED
LEDGER_RECONCILIATION = INCOMPLETE / PROOF BUDGET SQLITE NOT CREATED
SAFETY_GATE = STOPPED BEFORE GATEWAY / NO DOWNLOAD OR PHASE 2
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
SECRETS_EXPOSED = NO
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
```

## Preflight and authorization

The existing launcher was run as `ROMA_CASA\walac` with a process-scoped
`LOCALAPPDATA=C:\Users\walac\AppData\Local`. The PowerShell host was
interrupted and exited, so the process-local value ceased to exist with that
process; no persistent environment value was changed.
Credential and session artifacts were loaded without printing their contents.
Their resolved paths were distinct:

- `C:\Users\walac\AppData\Local\telegram_courses\credentials.dpapi`
- `C:\Users\walac\AppData\Local\telegram_courses\session.dpapi`

The launcher presented channel `-1002758699600`, message `598`, `DOCUMENT`,
`11,649,955` bytes; mode `common / OPERATIONAL_ONLY / aligned`; aligned prefix
`1,048,576` bytes; GetFile cap `139`; GetFileHashes cap `138`; aggregate payload
reservation cap `36,438,016` bytes; three resume attempts; one worker; and
FloodWait cap 120 seconds. The user supplied the exact native confirmation
phrase. The harness created a new isolated proof root:

`C:\Users\walac\desenvolvimento\projeto_telegram_courses\.s6-v2-authorized-aligned-3bf161058a794f9483ad8a4b0f376bb2\s6-v2-real-proof-23f2dc0358204b65b957b0fd0282c430`

No earlier real-proof root was used as input. The configured operational
SQLite is `C:\Users\walac\desenvolvimento\projeto_telegram_courses\data\telegram_courses.sqlite3` and is separate from this proof root.

## Execution and stop

The phase-1 supervisor record stayed at `EVIDENCE_INCOMPLETE /
PROCESS_RUNNING` for about ten minutes without producing a child report. The
root contained only `.execution.lock`, `authorization.json`, and the initial
supervisor `aligned/phase-1.json`; it contained no proof SQLite, budget ledger,
download directory, or `.part` file. Source order creates the proof budget
ledger and proof SQLite before `_real_gateway`; therefore the gateway and the
remote identity request were not reached. No GetFile, GetFileHashes, or other
Telegram RPC was observed. The root remained protected by the operational
SQLite and historical `.part` isolation controls.

Because the live process made no observable progress and the remote identity
gate had not passed, the user-facing PowerShell session was interrupted once.
The shell exited with a control-C status; the harness did not record a
confirmed child exit. The phase-1 supervisor receipt and execution lock remain
in the root as incomplete evidence and must not be resumed or reused. No
phase-2 process was started. No retry is authorized by this report.

The reason the child failed to reach the proof database/gateway is
`UNKNOWN`; this activity did not perform a second diagnostic pass or another
execution. V1 remains active, V2 remains ineffective, S6 acceptance remains
pending, and the sprint checkpoint remains deferred.

```text
EXECUTION_ROOT_CAUSE = UNKNOWN / PROCESS DID NOT REACH PROOF SQLITE OR GATEWAY
PROCESS_1_SUPERVISOR_RECORD = EVIDENCE_INCOMPLETE / PROCESS_RUNNING / EXIT_UNCONFIRMED
PROOF_SQLITE = NOT_CREATED
PROOF_BUDGET_LEDGER = NOT_CREATED
DOWNLOAD_PART = NOT_CREATED
REMOTE_IDENTITY = NOT_CHECKED
REAL_TELEGRAM_CALLS = 0 / INFERRED FROM GATEWAY NOT REACHED
OPERATIONAL_SQLITE_ACCESS = NO
HISTORICAL_PART_ACCESS = NO
AUTOMATIC_RETRY = NO
```
