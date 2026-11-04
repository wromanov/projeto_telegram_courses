# S6 V2 offline regression runner invocation correction — 2026-10-19

```text
ACTIVITY = S6_V2_OFFLINE_REGRESSION_RUNNER_INVOCATION_FIX
SCOPE = RUNNER INVOCATION ONLY
FUNCTIONAL_TEST_CHANGES = NONE
RESULT = IMPLEMENTED / STATIC INVOCATION INSPECTION PASS
POST_CHANGE_PYTEST_COLLECTION = NOT_RUN / SANDBOX_ADMISSION_BLOCK
REAL_TELEGRAM_CALLS = 0
REAL_PROOF_EXECUTION = NO
```

The PowerShell launcher now starts its supervisor with the repository root as
its working directory. The supervisor launches the repository's
`.venv\Scripts\python.exe` with `-m pytest`, from that same root, and uses a
pytest plugin hook for collection IDs, xfail accounting, and timed stack
dumps. The child inherits the supervisor environment, removes
`PYTEST_ADDOPTS`, and adds only runner metadata variables. This lets Python's
module invocation put the repository root on `sys.path` while preserving an
existing `PYTHONPATH`.

Import and command-builder inspection passed: the executable resolves to the
repository `.venv`, the child arguments are module-based pytest, its working
directory is the repository root, and inherited environment values are
preserved as specified. The PowerShell parser passed. No pytest process was
started after the change: the effective `TEMP` or `LOCALAPPDATA` matched the
runner's sandbox-admission signature, which requires a blocked result without
relaunch or environment substitution. The user's earlier import and
collection PASS results predate this correction and are not presented as
post-change evidence.

```text
PYTHON_EXECUTABLE = .venv\Scripts\python.exe
PYTEST_INVOCATION = python -m pytest
WORKING_DIRECTORY = REPOSITORY_ROOT
PYTHONPATH = INHERITED
PYTEST_ADDOPTS = REMOVED
PYTHON_IMPORT_AND_INVOCATION_INSPECTION = PASS
POWERSHELL_PARSE = PASS
PYTEST_COLLECTION_AFTER_CHANGE = NOT_RUN / SANDBOX_ADMISSION_BLOCK
FUNCTIONAL_TESTS_CHANGED = NO
REAL_TELEGRAM_CALLS = 0 / REAL_PROOF_EXECUTION = NO
SAFE_RESUME_POINT = A post-change collection or profile run requires a separately authorized invocation in a native Windows context that passes the runner's admission check.
```
