# S6 V2 Offline Regression Runner Contract — 2026-10-19

```text
DOCUMENT_ROLE = ACTIVITY_SCOPED_TECHNICAL_CONTRACT
ACTIVITY = S6_V2_FINAL_REGRESSION_GATE
SCOPE = TEST_INFRASTRUCTURE_AND_REGRESSION_ONLY
AUTHORITY = ROOT_ADJUDICATED_ACTIVITY_CONTRACT
CANONICAL_AUTHORITY = NO
EXECUTION_AUTHORIZATION = NO
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_PROOF_EXECUTION = NO
V1_ACTIVE = YES
V2_EFFECTIVE = NO
```

## Purpose and boundary

This contract bounds offline Windows regression runs for the S6 V2 test
harness. It addresses collection, supervision, diagnostic capture, process
termination, and truthful result classification when Windows asyncio startup
or a test process stalls. It does not change downloader behavior, transfer
semantics, timeout policy of the operational proof harness, or S6 acceptance
criteria. It is activity-scoped technical guidance, not a canonical project
authority and not permission to run either profile, invoke Telegram, access
credentials, download real media, or conduct a real proof.

## Evidence basis and limits

The activity report records one isolated run of
`test_unaligned_preparation_uses_controlled_application_stream_and_reconciles_wire`.
At the 12-second diagnostic dump, pytest had collected and entered the test,
but its coroutine had not begun. The captured stack was in Windows Proactor
event-loop lazy creation, at `socket.accept` in
`socket._fallback_socketpair` while `_make_self_pipe` ran. The external hard
limit was 25 seconds. No application assertion or exception was captured.

One aggregate run excluded only that isolated test. It emitted 61 progress
dots and, at the 120-second diagnostic dump, stopped at
`test_unaligned_prefix_reread_and_overlap_observation_pass`, in the same
socketpair fallback during that test's `asyncio.run`. Its external hard limit
was 150 seconds; no pytest summary was produced. At the limit, `taskkill`
reported a Windows credential error and the supervising PowerShell command
was interrupted. A subsequent process check found no Python test runner.
Because the supervisor did not confirm the whole process-tree exit in-band,
the aggregate result remains `INCOMPLETE`; no full-suite PASS is inferred.

Earlier aggregate failures reported `KeyError: attempts` in the common
`test_two_process_handoff...unaligned-prepared` case. The isolated case passed,
and the retained per-run evidence has no corresponding traces or enough
details to diagnose those two episodes. These failures are distinct from the
socketpair startup hang. A later native-context aggregate recorded 235 passes,
including synthetic two-process `TRUSTED_REFERENCE`; this is historical
evidence, not a result of the current bounded regression activity.

The runtime-isolation report compared the same interpreter under sandbox-
redirected and native Windows `TEMP`/`LOCALAPPDATA`: socketpair and asyncio
probes timed out in the redirected context and passed in the native context.
The current environment was reported blocked by sandbox path redirection.
This supports an environment-specific Windows socketpair/asyncio bootstrap
classification; it does not prove that every intermittent `KeyError:
attempts` has the same cause. See the [final regression gate report](../reports/S6_V2_FINAL_REGRESSION_GATE_2026-10-19.md),
[runtime isolation evidence](../reports/S6_RUNTIME_ISOLATION_2026-10-18.md),
and [TRUSTED_REFERENCE homologation record](../reports/S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_2026-10-18.md).

## Allowed runner profiles

Only these fixed offline profiles are defined:

| Profile | Selection | Scope |
|---|---|---|
| `Affected` | One exact pytest node ID: `test_unaligned_preparation_uses_controlled_application_stream_and_reconciles_wire` | Isolated diagnosis of the affected case |
| `Harness` | The complete harness test module, with no test deselections or exclusions | Bounded aggregate harness regression |

The runner must require the repository `.venv` Python interpreter. It must
reject an unsupported profile, a missing interpreter, and any invocation that
could select operational downloader, Telegram, credentials, network, or real
media behavior. Fixtures and all child processes must remain offline and
synthetic.

## Environment and work-root admission

Before starting pytest, the runner must inspect the effective `TEMP` and
`LOCALAPPDATA` paths for the known sandbox-redirection signature. If that
signature is present, it must return `BLOCKED` without relaunching under a
different environment or attempting to bypass the sandbox.

Each invocation must use a new short root inside the repository, with the
resolved root path no longer than 220 characters. Pytest temporary state,
diagnostic artifacts, receipts, and captured stdout/stderr must stay under that
root. Child stdout and stderr must be file-backed so a blocked pipe cannot
prevent supervisor diagnostics or process termination.

## Diagnostics and deadline policy

The diagnostic stack dump is scheduled at 12 seconds for the `Affected`
profile and at 120 seconds for the `Harness` profile. These are diagnostic
capture times, not pytest timeouts.

The external hard deadlines for pytest are 25 seconds for `Affected` and 150
seconds for `Harness`. There is no retry. At a deadline, the supervisor
captures the available diagnostics and starts bounded termination. The total
termination grace is at most 5 seconds after that deadline; the runner must
not add an unbounded post-grace wait.

The implemented Python supervisor uses `taskkill.exe /PID <pid> /T /F` on
Windows with a maximum five-second termination window. It considers
termination confirmed when the tree-kill request succeeds and the worker root
process is observed exited (`poll()` is non-null). A timeout remains
`INCOMPLETE` even when termination is confirmed; the process exit code can be
nonzero and is recorded as observed. Confirmation does not mean a clean test
exit. If termination is not confirmed, classify the timeout as `BLOCKED` with
`PROCESS_EXIT_UNCONFIRMED`.

## Receipts and result classification

When the runner reaches receipt creation, its machine-readable JSON records
the fields emitted by the implementation: `profile`, worker `pid` when
available, configured and applied deadline seconds, `exit_code`,
`termination_confirmed`, pytest counts (`tests`, `passed`, `failed`,
`skipped`, `xfail`), collected node IDs when worker metadata is available,
`junit_present`, `receipt_path`, `worker_pid` when available, `result`, and a
`reason` or `worker_error` when applicable. Fields vary by launch, worker,
and timeout outcome; the receipt does not claim to contain the exact selected
node, interpreter path, classified environment, timestamps, or diagnostic
artifact paths. Receipt creation can itself be absent if setup or filesystem
operations fail; an absent receipt is not success.

Pytest is invoked with `--basetemp <run_dir>/pytest-temp`. The resolved
`pytest-temp` path is validated to remain under the resolved run root, which
must be under the repository `.s6r` directory, and must be no longer than
220 characters.

Classify outcomes as follows:

| Condition | Required result |
|---|---|
| Pytest completes with failures | `FAIL` |
| External deadline expires and process-tree exit is confirmed | `INCOMPLETE` |
| Process-tree exit cannot be confirmed | `BLOCKED / PROCESS_EXIT_UNCONFIRMED` |
| Environment admission, setup, or diagnostic collection fails | `BLOCKED` |
| Required JUnit/receipt/collection artifact is missing or disagrees with observed process output | `INCOMPLETE` |
| Any skip or xfail occurs in the selected profile | Never `PASS` |
| Worker finishes normally with exit code zero, collection/JUnit/receipt are valid, no skip/xfail occurred, and supervision completes | `PASS` |

On timeout, the runner writes a conservative `INCOMPLETE` or `BLOCKED`
receipt with the available process and termination evidence. That timeout
path does not reconcile pytest collection or JUnit data. Missing evidence
must remain missing; the runner must not synthesize a success result from
partial output or from a subsequent process-list check alone.

## Execution boundary and validation record

No new test profile was executed for the activity recorded in the final gate
report. Sandbox path redirection was identified from the runtime context; the
runner was deliberately not invoked under that context. The report records 13
new test-infrastructure tests passing and
PowerShell parser validation passing. Those checks validate runner
infrastructure only; they are not execution of `Affected` or `Harness`.
Accordingly, the full harness regression remains `INCOMPLETE`, and the
controlled critical-test status remains based on prior evidence only.

The report's runtime-isolation evidence records a prior launcher-mediated,
synthetic, two-process offline E2E pass and a prior selected S5/S6 regression
pass in native Windows paths. The prior TRUSTED_REFERENCE homologation report
records a native 235-test aggregate pass that included its synthetic
two-process E2E. These records do not upgrade the current activity's incomplete
aggregate to PASS and do not authorize a real proof.

```text
CURRENT_AFFECTED_PROFILE = NOT_RUN / SANDBOX_CONTEXT_IDENTIFIED
CURRENT_HARNESS_PROFILE = NOT_RUN / SANDBOX_CONTEXT_IDENTIFIED
FULL_HARNESS_REGRESSION = INCOMPLETE
OFFLINE_RUNNER_INFRASTRUCTURE_TESTS = PASS / 13
POWERSHELL_PARSER = PASS
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_PROOF_EXECUTION = NO
```

The next profile execution requires a separately authorized activity and an
environment that passes the explicit admission check. This document alone
does not authorize it. V1 remains active, V2 remains ineffective, and S6
formal acceptance remains pending.
