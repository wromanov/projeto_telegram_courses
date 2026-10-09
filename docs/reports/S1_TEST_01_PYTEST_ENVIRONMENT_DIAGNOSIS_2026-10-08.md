# S1-TEST-01 — Pytest Environment Diagnosis

```text
ACTIVITY = S1-TEST-01
DATE = 2026-10-08 / America/Sao_Paulo
STATUS = BLOCKED
PYTEST_DIAGNOSIS = BLOCKED
PYTEST_ROOT_CAUSE = CONFIRMED / immediate mechanism
TEST_REVALIDATION = PENDING
```

## Precheck

| Item | Observed |
|---|---|
| Repository root | `C:\Users\walac\desenvolvimento\projeto_telegram_courses` |
| Branch / HEAD | `work/s0-bootstrap` / `e947406dbcab8ef593123f079daa279903805d2c` |
| Upstream | `origin/work/s0-bootstrap`, same local reference; no fetch performed |
| Worktree before execution | Clean |
| Virtual environment | Existing `.venv` |
| Python / pytest / pluggy | 3.14.7 / 9.1.1 / 1.6.0 |
| Pytest plugins | Internal pytest plugins only, including `faulthandler` and `subtests`; no external pytest plugin distributions found |
| Configuration | `pyproject.toml`; no `pytest.ini`; `testpaths = tests/unit, tests/integration`, `addopts = -ra`; no asyncio plugin/configuration |

The interpreter printed `Failed to find real location` for the base Python executable path on each invocation, although Python ran and the referenced path exists. Causality with the hang was not established.

## Controlled evidence

1. Collection only: `.venv\Scripts\python.exe -m pytest --collect-only -vv --trace-config` exited 0 and collected 55 tests in 1.66 s. Collection did not hang.
2. Focused gateway: `.venv\Scripts\python.exe -m pytest tests/unit/test_telethon_gateway.py -vv -o faulthandler_timeout=15 -o faulthandler_exit_on_timeout=true` stopped at the first case after the faulthandler timeout. The outer 90 s limit was not reached.
3. Affected case: `test_restore_missing_and_invalid_session_then_replace_only_on_success`, at its first `asyncio.run` call (`tests/unit/test_telethon_gateway.py:112`). It has no fixture setup. The gateway test uses `FakeClient`, `FakeVault` and synthetic credentials.
4. Faulthandler stack: `asyncio.run` → Windows `ProactorEventLoop` initialization → `_make_self_pipe` → `socket._fallback_socketpair` → `socket.accept`. The stack was in test execution, before gateway behavior.
5. A single minimal `asyncio.run(asyncio.sleep(0))` probe outside pytest, with faulthandler and an 8 s exit limit, reproduced the same stack and exited 1. This confirms the immediate failure is independent of pytest.

## Classification and limits

```text
HANG_CLASSIFICATION = TEST_EXECUTION_HANG + ENVIRONMENT_ISSUE
COLLECTION_HANG = NO
FIXTURE_SETUP_HANG = NO
TEARDOWN_HANG = NO
RUNNER_OUTPUT_ISSUE = NO EVIDENCE
ROOT_CAUSE = CONFIRMED / Windows Proactor loop initialization blocks in fallback socketpair accept
UNDERLYING_OS_OR_VENV_TRIGGER = NOT_ESTABLISHED
TELEGRAM_NETWORK_USED = NO
ORPHANED_PYTHON_OR_PYTEST_PROCESSES = NONE OBSERVED BEFORE OR AFTER
```

The prior S1-GIT-01 command transcript was not present in the repository artifacts searched, so the originally affected test cannot be independently identified. The current focused repro identifies the first gateway test above. No full suite, Ruff, or `git diff --check` was run because the focused test did not pass. The earlier `55 passed / 8 subtests passed` result remains historical baseline evidence and is not a result of this activity.

## Final report

```text
ACTIVITY = S1-TEST-01
STATUS = BLOCKED
ACTIVITY_COMPLETION_PERCENT = 76%
ROOT_RUNTIME_MODEL = GPT-6 SOL (requested target; exact runtime model not exposed)
BRANCH = work/s0-bootstrap
HEAD = e947406dbcab8ef593123f079daa279903805d2c
WORKTREE = DOCUMENTATION MODIFIED ONLY / published HEAD unchanged
PYTHON_VERSION = 3.14.7
PYTEST_VERSION = 9.1.1
AFFECTED_TEST = tests/unit/test_telethon_gateway.py::test_restore_missing_and_invalid_session_then_replace_only_on_success
HANG_CLASSIFICATION = TEST_EXECUTION_HANG / ENVIRONMENT_ISSUE
ROOT_CAUSE = CONFIRMED immediate mechanism; underlying OS/venv trigger not established
DIAGNOSTIC_EVIDENCE = 55 collected in 1.66 s; focused test faulthandler stack at asyncio Proactor self-pipe socket.accept; minimal asyncio.run probe reproduced it outside pytest
FOCUSED_PYTEST = BLOCKED / faulthandler exit at 15 s, exit code 1
FULL_PYTEST = NOT RUN
RUFF = NOT RUN
DIFF_CHECK = NOT RUN
TEST_REVALIDATION = PENDING
SOURCE_CHANGES = NONE
GIT_ACTIONS = NONE
TELEGRAM_NETWORK_USED = NO
S1_STATUS = IN_PROGRESS
S1D_STATUS = NOT_STARTED
FINAL_VERDICT = pytest collection works; test execution is blocked by the local Windows asyncio Proactor loop startup hang, reproduced outside pytest
SAFE_RESUME_POINT = S1-D Architectural Entry Review, DIRECT / GPT-6 SOL / HIGH
NEXT_ACTION = S1-D Architectural Entry Review, DIRECT / GPT-6 SOL / HIGH
```
