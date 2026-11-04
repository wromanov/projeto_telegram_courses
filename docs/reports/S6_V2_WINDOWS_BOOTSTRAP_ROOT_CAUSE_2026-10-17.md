# S6 V2 Windows child bootstrap root cause — 2026-10-17

```text
ACTIVITY = S6_V2_WINDOWS_BOOTSTRAP_ROOT_CAUSE
CORRECTION_CYCLES_EXECUTED = 2 / MAXIMUM 4
RESULT = BLOCKED / ROOT_CAUSE PARTIAL
WINDOWS_DIRECT_CHILD_BOOTSTRAP_GATE = BLOCKED
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
PROTECTED_CREDENTIAL_OR_SESSION_ACCESS = NO
V1_ACTIVE = YES / V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD_COMMIT_PUSH = NO
```

## Preflight and preserved evidence

The repository is `C:\Users\walac\desenvolvimento\projeto_telegram_courses`,
branch `work/s0-bootstrap`, HEAD
`98d9d6b9ce152b8d2764a4d160fcbdf4722fb257`, upstream
`origin/work/s0-bootstrap`. The worktree was already dirty before this
activity; pre-existing changes were preserved.

The interrupted real proof root and `.execution.lock` remain untouched at
`.s6-v2-authorized-aligned-3bf161058a794f9483ad8a4b0f376bb2/`. PID 32104 is
not currently visible; its historical exit remains unknown. No historical or
unrelated process was terminated. Diagnostic children created and held by the
probe supervisor were stopped only after their own timeout and their exits
were confirmed.

The earlier synthetic run that timed out (PID 25084) ended with exit code 1
after the 15-second test timeout. Its event log stopped at
`credential_loader_stubbed`; it had no child report, proof SQLite, or budget
ledger. A prior `runpy` synthetic handoff report passed, but that run did not
exercise the direct script entrypoint.

## Diagnostic instrumentation

Instrumentation is gated by test-only environment variables and writes
allow-root-contained JSONL records under a fresh test `tmp_path`. Records
contain execution ID, PID/PPID, monotonic timestamp, stage/boundary, outcome
or exception class, thread, and event-loop/policy names. They do not include
environment dumps, arguments, exception messages, credentials, or session
content. `faulthandler` writes to an isolated stack file. The diagnostic
timeout is capped at eight seconds for probes; the operational 3600-second
supervisor timeout is unchanged. Timeout handling kills only the child held
by that supervisor's `Popen` and confirms its exit.

The synthetic bootstrap replaces the gateway and credential loader before
the child can reach authentication, blocks external sockets, confines SQLite
to the test root, redirects `LOCALAPPDATA` only in the child process to a
temporary fixture, and blocks historical `.part` access. Credential/session
vault entry points and protected-path file opens are replaced by immediate
fail-closed stubs. A dedicated test deliberately invoked these stubs and
confirmed 13 protected operations were blocked before any real vault or file
read; its sanitized events contain no path or content.

## Findings

The direct-child probes used the same base interpreter, cwd, child arguments,
and synthetic fixtures:

| Case | Entry point / loop policy | Last stage | Stack / outcome |
|---|---|---|---|
| A | `python -u <harness.py> ...`, default Proactor | `B06_loop_setup` start | `socket.accept` in `socket._fallback_socketpair`, called by Proactor `_make_self_pipe`; supervisor timeout and exit confirmed |
| B | Direct script, Windows Selector | `B06_loop_setup` start | Same fallback `accept`, called by Selector `_make_self_pipe`; supervisor timeout and exit confirmed |
| C | Historical `-c/runpy`, Selector | `B06_loop_setup` start | Same fallback `accept`, with additional `runpy` frames; supervisor timeout and exit confirmed |

No case reached the first coroutine, ledger, or synthetic gateway. The
instrumented minimal bootstrap and injected-stall checks passed. A separate
direct-script probe with no harness imports, gateway, or credential stub also
hung in `asyncio.run(asyncio.sleep(0))` and captured the same stack under
Proactor and Selector. The base runtime reports no `_socket.socketpair`, so
Python uses `socket._fallback_socketpair` over loopback. The blocking point is
proved; why the local connection does not complete at `accept` is not.

Therefore `ROOT_CAUSE = PARTIAL`: the event-loop startup path and blocking
call are located, but the underlying loopback/socket failure is unresolved.
Selector does not resolve it. No functional correction was made.

The ten-minute wait in the earlier proof is consistent with the operational
`communicate(timeout=3600)` setting. That timeout applies to the whole child
process and provides no bootstrap progress signal; ten minutes alone does not
prove a 60-minute wait or identify the blocking call.

## Gate and validation

| Gate | Result |
|---|---|
| Direct script entry and synthetic isolation | PASS |
| B00–B10 instrumentation and persisted records | PASS where reached |
| Diagnostic timeout and injected-stack capture | PASS |
| Child exit confirmation / no observed probe orphan | PASS |
| Bootstrap ready / first coroutine | FAIL — loop setup blocks first |
| Full direct synthetic handoff, checkpoint, reports, SQLite/ledger | BLOCKED — A/B/C time out before stage preparation |
| S5/S6 regressions | BLOCKED — first async integration test did not advance; interrupted after 20 seconds |
| Targeted probe tests | PASS — independent rerun: 5 passed, 51 deselected; includes direct protected-vault guards and A/B/C probes |
| Ruff | PASS — independent final rerun: `ruff check src tests tools` |
| `compileall` | PASS — independent rerun on `src tests tools` |
| PowerShell parser | PASS |
| DryRun common / controlled | PASS / PASS; plan-only, no network, V2 false |
| `git diff --check` | PASS; pre-existing line-ending notices only |

The full suite was also started and then interrupted after more than two
minutes without a summary. Neither interrupted suite is counted as passing.

Final hardening validation redirected only the synthetic child process's
`LOCALAPPDATA`, blocked `CredentialVault`, both protected session vaults, the
gateway's vault alias, `Path.open`, and `os.open`, and recorded 13 blocked
attempts without path/content fields. The independent targeted rerun passed
all five selected tests in 35.73 seconds. The historical lifecycle E2E remains
`INCOMPLETE` because its child again stalls before the first coroutine. The
first test invocation used the system Python without `pytest`; the next
invocation's default sandbox TEMP also rejected pytest basetemp creation. The
successful rerun used the project `.venv` and a new basetemp inside the
workspace. These runner setup errors are not counted as test results.

## Safety and next action

No Telegram call/download, credential access, protected-session access,
source downloader change, contract change, or Git publication occurred.
V1 remains active and V2 remains ineffective. The historical proof stays
incomplete and must not be reused or retried automatically.

```text
ROOT_CAUSE = PARTIAL
FUNCTIONAL_CORRECTION = NOT_AUTHORIZED_BY_EVIDENCE
WINDOWS_DIRECT_CHILD_BOOTSTRAP_GATE = BLOCKED
SAFE_RESUME_POINT = Diagnose why the base runtime's local TCP socketpair fallback blocks at accept; preserve the incomplete real-proof root.
NEXT_ACTION = USER_REAL_PROOF_AUTHORIZATION_DECISION
```

## Final delivery fields

```text
ACTIVITY = S6_V2_WINDOWS_BOOTSTRAP_ROOT_CAUSE
DIAGNOSTIC_AGENT = SOL/MEDIUM/READ_ONLY
IMPLEMENTER = LUNA/HIGH/WRITE_SCOPED
ROOT = LUNA/XHIGH
CYCLES_EXECUTED = 2/4
LAST_CONFIRMED_BOOTSTRAP_STAGE = B06_LOOP_SETUP / START
BLOCKING_CALL_OR_STACK = socket._fallback_socketpair.accept from asyncio.run while creating the loop
EVENT_LOOP_POLICY_A = _WindowsProactorEventLoopPolicy
EVENT_LOOP_POLICY_B = _WindowsSelectorEventLoopPolicy
ROOT_CAUSE = PARTIAL
CONTRACT_STATUS = NOT_REQUIRED / no functional correction was justified
IMPLEMENTATION_STATUS = DIAGNOSTIC INSTRUMENTATION AND FAIL-CLOSED SYNTHETIC FIXTURE HARDENING ONLY
DIRECT_SCRIPT_PROBE = A/B timed out at loop setup; stack captured; child exit confirmed; C runpy also timed out
SYNTHETIC_TWO_PROCESS_GATE = INCOMPLETE / no child reached ledger or gateway; handoff did not start
WINDOWS_DIRECT_CHILD_BOOTSTRAP_GATE = BLOCKED
TARGETED_TESTS = PASS / 5 passed, 51 deselected / includes vault guards and A/B/C probes
S5_S6_REGRESSIONS = BLOCKED / full and focused runs stalled in asyncio-dependent tests and were interrupted
SAFETY_GATE = PASS / temporary child-only LOCALAPPDATA; 13 protected operations blocked; no secret/path/content in probe events
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
NEXT_ACTION = USER_REAL_PROOF_AUTHORIZATION_DECISION
```
