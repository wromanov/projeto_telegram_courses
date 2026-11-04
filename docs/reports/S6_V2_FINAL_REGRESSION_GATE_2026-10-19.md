# S6 V2 final regression gate — 2026-10-19

```text
ACTIVITY = S6_V2_FINAL_REGRESSION_GATE
SCOPE = TEST_INFRASTRUCTURE_AND_REGRESSION_ONLY
ROOT_CAUSE_CLASS = WINDOWS_SANDBOX_ASYNCIO_SOCKETPAIR_BOOTSTRAP
ISOLATED_AFFECTED_TEST = INCOMPLETE / 25s EXTERNAL LIMIT / STACK CAPTURED
AGGREGATE_HARNESS_REGRESSION = INCOMPLETE / 150s EXTERNAL LIMIT / STACK CAPTURED
CONTROLLED_CRITICAL_TESTS = PRIOR PASS EVIDENCE / NOT REACHED IN THIS AGGREGATE
FUNCTIONAL_FIX = NONE / NOT INDICATED
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_PROOF_EXECUTION = NO
V1_ACTIVE = YES
V2_EFFECTIVE = NO
GIT_ADD_COMMIT_PUSH = NO
```

## Scope and conclusion

This gate examined the incomplete harness run from the preceding activity and
the two earlier intermittent lifecycle failures. No downloader, timeout,
ledger, or SQLite behavior was changed. The observed hang is in Windows
`asyncio` event-loop startup under the current sandboxed execution context,
before the affected test's coroutine starts. It is not evidence of a defect in
unaligned byte preparation or `TRUSTED_REFERENCE` transfer behavior.

## Historical intermittent failures

The two earlier aggregate runs failed in the common
`test_two_process_handoff...unaligned-prepared` case with `KeyError: attempts`.
The historical record says its isolated case passed and the later native
235-test aggregate passed, including synthetic two-process
`TRUSTED_REFERENCE`. The saved summaries do not include enough per-run
diagnostics to identify why `attempts` was missing. These failures remain
intermittent and unexplained; they are distinct from the current event-loop
startup hang. See the [homologation report](S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_2026-10-18.md)
and [continuity record](../continuity/CONTINUITY_RECORD.md).

## Bounded isolated run

The incomplete suite had stopped at
`test_unaligned_preparation_uses_controlled_application_stream_and_reconciles_wire`,
which calls `asyncio.run(consume())`. One isolated run used the project Python
3.14.7, `pytest -vv -s`, a 25-second external wait limit, and a
`faulthandler` dump at 12 seconds. Pytest collected the test and entered its
body, but the test did not reach `consume()`.

The captured stack ended at `socket.accept` inside
`socket._fallback_socketpair`, called by the Windows Proactor loop's
`_make_self_pipe` while `asyncio.run` lazily created the event loop. Pytest
stdout had no assertion or application exception, and stderr was empty. The
child was stopped at the external limit. This is a runtime/socketpair
bootstrap block, not a deadlock in the chunk stream, test interference, or a
failure of a semantic assertion.

## Single aggregate run

One aggregate run covered the harness test module with only the isolated
startup-blocked test deselected, using a 150-second external wait limit and a
stack dump at 120 seconds. Pytest had emitted 61 progress dots when the limit
was reached. The stack was in the same socketpair fallback, this time from
`test_unaligned_prefix_reread_and_overlap_observation_pass` at its own
`asyncio.run` call. Thus the environment issue affects more than one
independent synchronous test that initializes an asyncio loop.

At the aggregate limit, `taskkill` returned a Windows credential error. The
supervising PowerShell command was then interrupted; a subsequent process
check showed no Python test process remaining. No pytest summary was
available. The aggregate is `INCOMPLETE`, never counted as passing, and no
further run was made under this activity's one-isolated/one-aggregate limit.

The same failure signature is documented in the earlier
[Windows bootstrap investigation](S6_V2_WINDOWS_BOOTSTRAP_ROOT_CAUSE_2026-10-17.md).
The later [runtime isolation report](S6_RUNTIME_ISOLATION_2026-10-18.md)
compared contexts using the same interpreter: socketpair and asyncio probes
timed out under sandbox-redirected `TEMP`/`LOCALAPPDATA`, while both passed
with native Windows paths. That A/B evidence classifies this as an environment
restriction, not a Python source regression. No test or application code
change is justified.

## Critical evidence and residual risk

The latest recorded controlled synthetic two-process result remains PASS in
the historical native aggregate of 235 tests. The preceding timeout-remediation
work also recorded 157 harness tests and 129 S5/S6 regression tests passing;
the launcher timeout preflight change subsequently passed 13 policy/budget
tests and 27 timeout/reconciliation tests. Those results are prior evidence,
not results from this aggregate, which stalled before reaching those cases.

| Gate | Result | Evidence limit |
|---|---|---|
| Isolated unaligned preparation test | `INCOMPLETE` | 25s external limit; captured Proactor socketpair accept stack |
| Aggregate harness regression | `INCOMPLETE` | 150s external limit; second test blocked at the same loop bootstrap |
| Timeout policy and deadline regressions | `PASS` in preceding focused runs | Not reached by this aggregate |
| Timeout reconciliation / child interruption | `PASS` in preceding focused runs | Not reached by this aggregate |
| Synthetic two-process controlled lifecycle | `PASS` in historical native aggregate | Not reached by this aggregate |
| Full harness regression | `NOT ESTABLISHED` | No complete summary from this activity |
| Functional regression attributed to this hang | `NO EVIDENCE` | Coroutine body was not entered |

Residual risk remains in two areas: this sandbox cannot reliably run tests
that initialize the Windows asyncio loop, and the historical `KeyError:
attempts` failures have no run-level traces despite a later passing aggregate.
Native-context regression evidence and the unchanged application source support
`READY_WITH_EXCEPTION`; the current full harness suite is not declared passed.

```text
ROOT_CAUSE_CLASS = ENVIRONMENTAL / SANDBOXED WINDOWS LOOPBACK SOCKETPAIR
INTERFERENCE_BETWEEN_TESTS = NOT INDICATED / ISOLATED TEST REPRODUCED
FUNCTIONAL_REGRESSION = NOT INDICATED / TEST COROUTINE NOT ENTERED
CONTROLLED_CRITICAL_TESTS = PRIOR PASS EVIDENCE / CURRENT AGGREGATE DID NOT REACH THEM
FULL_HARNESS_REGRESSION = INCOMPLETE
REAL_REPROOF_READINESS = READY_WITH_EXCEPTION
NEXT_ACTION = USER_REAL_REPROOF_AUTHORIZATION
```

## Contract and offline runner follow-up

After the bounded functional-test executions, the root adjudicated a separate
test-infrastructure-only contract for future offline Windows diagnosis. The
contract is activity-scoped and does not change canonical project contracts,
the operational harness, downloader behavior, or proof timeout semantics.
It defines two fixed profiles (`Affected` and `Harness`), bounded diagnostic
and hard deadlines, sandbox admission, process-tree termination reporting,
and conservative PASS/INCOMPLETE/BLOCKED classification. See
[`S6_V2_OFFLINE_REGRESSION_RUNNER_CONTRACT_2026-10-19.md`](../contracts/S6_V2_OFFLINE_REGRESSION_RUNNER_CONTRACT_2026-10-19.md).

A standalone PowerShell/Python runner and its infrastructure unit tests were
added. Pytest temporary state is directed to `<run_dir>/pytest-temp`; the
resolved path must remain inside the unique `.s6r` run root and stay within
220 characters. The runner does not auto-relaunch outside the sandbox and was
not invoked in this activity. The affected and aggregate functional profiles
were not repeated. Thirteen runner-infrastructure tests passed, as did the
PowerShell parser, Python compilation, Ruff, and `git diff --check`. These
checks do not change the status of the isolated or aggregate functional runs.

```text
OFFLINE_REGRESSION_RUNNER = IMPLEMENTED / NO FUNCTIONAL PROFILE EXECUTED
RUNNER_INFRASTRUCTURE_TESTS = PASS / 13
RUFF = PASS / PYTHON_COMPILE = PASS / POWERSHELL_PARSER = PASS
FULL_HARNESS_REGRESSION = INCOMPLETE
REAL_TELEGRAM_CALLS = 0 / REAL_DOWNLOADS = NO / REAL_PROOF_EXECUTION = NO
V1_ACTIVE = YES / V2_EFFECTIVE = NO
GIT_ADD_COMMIT_PUSH = NO
```
