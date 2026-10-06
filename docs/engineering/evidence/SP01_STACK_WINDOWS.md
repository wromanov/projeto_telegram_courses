# SP-01 — Windows Stack Compatibility & Reproducibility

```text
SP01_RESULT = FAIL
SP01_FAILURE_STEP = SP01-10-CREATE-REPLAY
SP01_FAILURE_KIND = NATIVE_EXIT
SP01_NATIVE_EXIT_CODE = 1
HISTORICAL_SP01_FAILURE_STEP = SP01-02-CREATE-ATTEMPT-2
HISTORICAL_SP01_FAILURE_KIND = NATIVE_EXIT
HISTORICAL_SP01_NATIVE_EXIT_CODE = 1
SP01_EXECUTION_DATE = 2026-10-06 / America/Sao_Paulo
HISTORICAL_SP01_COMMAND_STEPS_ATTEMPTED = SP01-01-SELECT; SP01-01-BASE; SP01-02-CREATE-ATTEMPT-1; RECOVERY-CYCLE-R1; RECOVERY-CYCLE-R2; SP01-02-SELECT-BASE-ATTEMPT-2; SP01-02-BASE-ORACLE-ATTEMPT-2; SP01-02-CREATE-ATTEMPT-2
HISTORICAL_SP01_VALIDATED_CYCLES = CYCLE-00 PASS; CYCLE-01 PASS
HISTORICAL_SP01_FAILED_CYCLE = CYCLE-02 / SP01-02-CREATE
HISTORICAL_SP01_DEPENDENT_STEPS = NOT_EXECUTED_AFTER_THE_FAILED_ATTEMPT
RECOVERY_CYCLE_R1 = PASS
RECOVERY_CYCLE_R2 = PASS / ONLY <RepoRoot>\.venv removed
SP01_02_ATTEMPT_1 = FAIL / EXIT_CODE=1 / CAUSE=INDETERMINATE
SP01_02_ATTEMPT_2 = FAIL / EXIT_CODE=1 / ensurepip subprocess returned non-zero exit status 1; raw stderr retained in turn report only
SP01_02_AUTHORIZED_RETRIES = 1
SP01_02_ACTUAL_RETRIES = 1
SP01_EVIDENCE = sanitized step, failure kind, exit code, oracle facts, recovery guard/removal, and post-failure artifact state; raw streams and exception detail not persisted
HISTORICAL_SP01_VENV_ATTEMPT_2 = PARTIAL / later removed by the user
SP01_VENV_CREATED = YES / a new .venv was manually created by the user in PowerShell 7 and subsequently used for SP01-02..09 PASS
SP01_REPLAY_VENV_CREATED = YES / PARTIAL; Scripts/python.exe exists; telegram-courses.exe absent; DO NOT REUSE, REMOVE OR RETRY AUTOMATICALLY
SP01_01 = PASS
SP01_02 = PASS / CPython 3.14.0; standard GIL enabled; sys.prefix and venv validated
SP01_03 = PASS / pip 25.2; editable [dev] install exit 0; pip check PASS; approved dependency versions
SP01_04 = PASS / required imports
SP01_05 = PASS / pytest exit 0, 20 passed; Ruff exit 0, All checks passed
SP01_06 = PASS / asyncio.run; ASYNCIO_OK; exit 0; stderr empty
SP01_07 = PASS / sqlite3 round-trip; SQLITE_OK; SQLite 3.50.4; exit 0
SP01_08 = PASS / aiosqlite round-trip; AIOSQLITE_OK; aiosqlite 0.22.1; exit 0
SP01_09 = PASS / CLI smoke 9 passed; exit 0; stderr empty; T09/T10 PASS
SP01_10 = FAIL / SP01-10-CREATE-REPLAY returned native exit 1
CURRENT_BLOCKER = Partial .venv-replay remains after replay creation failed; no retry or cleanup
SAFE_RESUME_POINT = SP01-10 failure recovery requires a new explicit user instruction
PYTHON_IMPLEMENTATION = CPython
PYTHON_VERSION = 3.14.0
PYTHON_EXECUTABLE = C:\Users\walacedelgado\AppData\Local\Programs\Python\Python314\python.exe
PYTHON_ARCHITECTURE = AMD64 / 64-bit process
GIL = ENABLED / standard build
WINDOWS_RELEASE = 11 / 10.0.26100
POWERSHELL_VERSION = 7.6.5
TELEGRAM_NETWORK_USED = NO
SECRETS_CREATED = NO
```

Historical record: the original CYCLE-00 and CYCLE-01 PASS results remain valid. ATTEMPT-1 failed
with exit code 1 and indeterminate cause. RECOVERY-CYCLE-R1 confirmed the
exact `.venv` target, ordinary directory attributes, Git ignore status, and
absence of running `python*`/`pip*` processes; `.venv-replay/` was absent.
RECOVERY-CYCLE-R2 removed only `<RepoRoot>\.venv` and confirmed it absent.

The approved CPython 3.14.0 base interpreter was reselected by the launcher
and passed the complete Windows 11 AMD64, 64-bit, standard GIL-enabled base
oracle. The single authorized ATTEMPT-2 ran the contract's
`Invoke-S0Native` command and returned exit code 1. Its stdout was empty. Its
stderr identified the failed `ensurepip --upgrade --default-pip` subprocess.
The failed command recreated `.venv` and `Scripts\python.exe`, but the venv
oracle and GIL probe were not run because native creation failed. No dependent
cycle ran. This historical partial `.venv` was later removed by the user. It
is distinct from the new `.venv` manually created and validated in a later
execution. ATTEMPT-3 and CYCLE-03 onward were not executed in that earlier run.

## Current factual reconciliation — 2026-10-06

```text
DOCUMENTATION_IS_STALE = YES / prior resume-preflight text contradicted later execution facts
SP01_RESULT = FAIL
SP01_01 = PASS
SP01_02 = PASS / user removed the partial attempt and manually created a new .venv in PowerShell 7; CPython 3.14.0; standard GIL enabled; sys.prefix and venv validated
SP01_03 = PASS / pip 25.2; editable [dev] install exit 0; pip check PASS; approved dependency versions
SP01_04 = PASS / required imports
SP01_05 = PASS / pytest 20 passed; Ruff exit 0; All checks passed
SP01_06 = PASS / asyncio.run; ASYNCIO_OK; exit 0; stderr empty
SP01_07 = PASS / sqlite3 round-trip; SQLITE_OK; SQLite 3.50.4; exit 0
SP01_08 = PASS / aiosqlite round-trip; AIOSQLITE_OK; aiosqlite 0.22.1; exit 0
SP01_09 = PASS / CLI smoke 9 passed; exit 0; stderr empty; T09/T10 PASS
SP01_10 = FAIL / SP01-10-CREATE-REPLAY native exit 1; stderr present; failure detail not retained in sanitized evidence
CURRENT_BLOCKER = Partial .venv-replay exists; no reuse, removal, or automatic retry
POWERSHELL_VERSION = 7.6.5
REPO_ROOT = C:\Users\walacedelgado\PycharmProjects\projeto_telegram_courses
PYTHON_BASE_PATH = C:\Users\walacedelgado\AppData\Local\Programs\Python\Python314\python.exe / EXISTS
VENV_ROOT = <RepoRoot>\.venv / EXISTS; new manually-created environment
PY_S0 = <RepoRoot>\.venv\Scripts\python.exe / EXISTS
CLI_S0 = <RepoRoot>\.venv\Scripts\telegram-courses.exe / EXISTS
VENV_REPLAY_EXISTS_BEFORE_SP01_10 = FALSE
CONSTRAINTS_EXISTS_BEFORE_SP01_10 = FALSE
SP01_10_INITIAL_PIP = 25.2
SP01_10_INITIAL_PIP_CHECK = PASS / No broken requirements found.
SP01_10_DIRECT_DEPENDENCY_BANDS = PASS / all six required runtime/dev distributions present within contractual ranges
SP01_INITIAL_PAIRS = aiosqlite==0.22.1; colorama==0.4.6; cryptg==0.6.0; iniconfig==2.3.0; markdown-it-py==4.2.0; mdurl==0.1.2; packaging==26.3; pip==25.2; pluggy==1.6.0; pyaes==1.6.1; pyasn1==0.6.4; projeto-telegram-courses==0.1.0; pygments==2.21.0; pytest==9.1.1; rich==15.0.0; rsa==4.9.1; ruff==0.16.10; telethon==1.45.0
CONSTRAINTS_GENERATION = PASS / 16 normalized ASCII name==version rows; exact file content validated
REPLAY_CREATION = FAIL / SP01-10-CREATE-REPLAY exit 1; stderr present; sanitized cause not retained
VENV_REPLAY_POST_FAILURE = PARTIAL / directory and Scripts/python.exe exist; CliReplay absent; do not reuse/remove/retry
REPLAY_PIP = NOT_EXECUTED
REPLAY_INSTALL = NOT_EXECUTED
REPLAY_PIP_CHECK = NOT_EXECUTED
REPLAY_IMPORTS = NOT_EXECUTED
REPLAY_PYTEST = NOT_EXECUTED
REPLAY_RUFF = NOT_EXECUTED
REPLAY_SMOKE = NOT_EXECUTED
FILESYSTEM_ORACLE = NOT_EXECUTED
DISTRIBUTION_COMPARISON = NOT_EXECUTED
CONSTRAINTS_COMPARISON = NOT_EXECUTED
SP01_10_NATIVE_STEPS = SELECT-PYTHONBASE 0; LIST-INITIAL 0; CHECK-INITIAL 0; CREATE-REPLAY 1
GIT_ACTIONS = NONE
SAFE_RESUME_POINT = New explicit user instruction required before failure recovery; preserve constraints and partial replay without reuse or cleanup
```

These later execution facts supersede the earlier resume-preflight conclusion.
SP01-01..09 are not re-evaluated here. The current request authorizes SP01-10;
its preflight confirmed the repository root, PythonBase, `.venv`, PyS0, CliS0,
and the initially absent replay/constraints paths. The initial `pip list` was
captured through `Invoke-S0Native`; normalization, duplicate checks, pip/local
metadata checks, six direct dependency bands, and initial `pip check` passed.
The contract constraints file was generated and validated. Native replay venv
creation then returned exit 1 with stderr present. The cause was not retained
in sanitized evidence. The failed command left a partial `.venv-replay` with
`Scripts/python.exe` but no `telegram-courses.exe`; it was neither reused nor
removed. No replay oracle, pip replay/install/check, imports, pytest, Ruff,
smoke, filesystem oracle, or comparison ran. No automatic retry was made.
