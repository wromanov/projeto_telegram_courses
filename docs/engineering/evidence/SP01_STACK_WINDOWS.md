# SP-01 — Windows Stack Compatibility & Reproducibility

```text
SP01_RESULT = FAIL
SP01_FAILURE_STEP = SP01-PREFLIGHT-ROOT
SP01_FAILURE_KIND = POWERSHELL_TERMINATING_ERROR
SP01_NATIVE_EXIT_CODE = NOT_AVAILABLE
SP01_EXECUTION_DATE = 2026-10-06 / America/Sao_Paulo
SP01_COMMAND_STEPS_COMPLETED = NONE
SP01_DEPENDENT_STEPS = NOT_EXECUTED_DEPENDENCY_FAILED
SP01_EVIDENCE = failure step and classification only; no raw streams or exception detail persisted
SP01_VENV_CREATED = NO
SP01_REPLAY_VENV_CREATED = NO
```

The required `Invoke-S0Native` preflight stopped while resolving the repository
root with Git. The failure was classified as a PowerShell terminating error;
the native exit code was unavailable. No SP-01-dependent command ran. The
checkout root and Git facts were subsequently read for this stop report only;
the SP-01 sequence was not resumed.
