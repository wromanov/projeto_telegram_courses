# S6 V2 native regression: bounded corrections to seven failures — 2026-10-20

```text
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_V2_NATIVE_REGRESSION_7_FAILURES_FIX
RESULT = PATCH_IMPLEMENTED / STATIC_QA_PASS / POST_CHANGE_NATIVE_VALIDATION_PENDING
S6_STATUS = OPEN / FORMAL_ACCEPTANCE_PENDING
V1_ACTIVE = YES / V2_GLOBAL = OFF / S7_S8 = DEFERRED
BRANCH = work/s0-bootstrap
HEAD = 98d9d6b9ce152b8d2764a4d160fcbdf4722fb257
UPSTREAM_DIVERGENCE = 0/0
PRIOR_NATIVE_RUN = .s6r/7a8ebf154869 / 193 COLLECTED / 186 PASSED / 7 FAILED / EXIT 1
FOCUSED_POST_CHANGE_PYTEST = NOT RUN
FULL_POST_CHANGE_HARNESS = NOT RUN
REAL_TELEGRAM_CALLS = 0 / REAL_DOWNLOADS = NO / REAL_PROOF_EXECUTION = NO
GIT_ADD_COMMIT_PUSH = NO
ACTIVITY_COMPLETION_PERCENT = 80% / bounded corrections and static review complete; native functional validation remains pending
```

## Scope and preserved baseline

This activity applied the current explicit authorization to the seven failures
in the preserved Harness run. For code and tests, it changed only:

- `tools/manual_proofs/s6_v2_proof_harness.py`
- `tests/manual_proofs/test_s6_v2_proof_harness.py`

Both files were already untracked WIP before this activity. Their prior hashes
at the start of the patch were harness
`A1F8ED0CB76D283F5F1E9A2693346AD635EBB792BE4A41A89A63116A8F687C7D` and tests
`F5145F1B94B42337FAB52D247DF9D503199C82E20B231579982CB6596E270668`. Their
current hashes are harness
`11132B2EC6EC9D3DCCCD07536E0834342B8F1432520FA744E5E0C961F1736197` and tests
`FD9959C190D59DC2079DBA21766ED14FD95F189C7830C07E7B3A0FD841FFF6EC`.

The earlier `.s6r/7a8ebf154869/` root and all other pre-existing WIP were
preserved. No application source, operational launcher, runner, production
SQLite, trusted reference, historical partial, proof receipt, or V2 activation
was changed. No Git staging, commit, or push occurred.

## Findings and bounded resolutions

| Finding | Adjudication | Resolution |
|---|---|---|
| Launcher test expected `$env:LOCALAPPDATA` to be assigned from a prior value, although the launcher inherits it and blocks if absent. | Incorrect test expectation. | The test now asserts inherited, unmodified `LOCALAPPDATA`, the fail-closed missing-value guard, and absence of an environment assignment. The launcher was not changed. |
| Aligned and unaligned handoff tests required a live phase-1 checkpoint after phase 2 had consumed it. | Incorrect post-run expectation; strict admission still applies before phase 2. | Post-run receipt checks allow a historical checkpoint. Existing pre-phase-2 admission remains strict. |
| Trusted-reference synthetic fixture derived final and `.part` paths beyond the 240-character guard. | Confirmed fixture defect; operational path guard is correct. | The fixture uses a shorter pytest temp root and preflights the complete destination derived from `DownloadCandidate`, including the `.part` path. Both must remain at or below 240 characters. |
| Sanitization test contaminated the error category itself with secret text and expected that exact category to survive. | Expected fail-closed behavior: contaminated category becomes `OTHER`. | The domain failure fixture now uses the exact allowlisted category and places synthetic secret text only in exception args; the separate negative case asserts contaminated category becomes `OTHER` without leaking the text. |
| The declared/observed child-exit mismatch branch could not run because envelope validation included the observed-exit comparison. | Confirmed harness defect. | Structural envelope validation is separate from process exit reconciliation. A structurally valid child declaration is retained for diagnosis, but an exit mismatch produces `EVIDENCE_INCOMPLETE`, `child_report_valid=false`, and `child_result=null`; phase acceptance remains closed. |
| Planner test matched `PATH_TOO_LONG` in human-readable text, while the message is normalized to `path too long`. | Incorrect test expectation. | The test now asserts the structured `DownloadError.category == "PATH_TOO_LONG"`; no production error text changed. |

The fail-closed negative coverage remains present for mismatched PID,
corrupt/missing child JSON, contaminated category, and `PROCESS_FAILED` with
exit 5 and `child_result=null`. These assertions were reviewed statically;
they were not executed in this activity.

## Verification performed here

| Check | Result |
|---|---|
| Ruff on the two authorized Python files | PASS — `All checks passed!` |
| Python AST parse of both files | PASS |
| Trailing-whitespace scan of both files | PASS |
| Static invariant review | PASS for preserved 240-character guard, strict phase-1 admission, fail-closed child identity/exit handling, and no application-source changes |
| Documented PowerShell procedure syntax | PASS with the current PowerShell parser; Windows PowerShell 5.1 runtime remains pending |
| Git diff check | Not applicable to the two code/test files: they remain pre-existing untracked WIP, so ordinary `git diff` does not show their content. Their exact current hashes and reviewed sections are recorded above. |
| Post-change pytest | NOT RUN — this session's shell is inside the Codex AppContainer; the known hanging pytest signature must not be repeated there. |

The previous native execution remains a historical failure, not a post-change
result: 193 collected/executed, 186 passed, 7 failed, 0 errors, 0 skipped,
metadata exit code 1. Its JUnit, worker metadata, logs, and basetemp remain
under `.s6r/7a8ebf154869/`.

## One bounded native validation procedure

Run the following once from the repository root in **Windows PowerShell 5.1**
outside the Codex AppContainer. It runs the focused selectors first. The full
Harness profile starts only if focus has exactly 12 passing cases with no
skip/error/failure. Each run gets a new `.s6r/<12-char-token>/t` root; no
existing artifacts are reused or deleted. The focused process is bounded at
90 seconds plus up to five seconds of termination grace. The Harness process
is bounded at 145 seconds plus up to five seconds of termination grace. A
timeout, nonzero result, count disagreement, or remaining worker stops the
sequence; preserve both roots and do not retry.

The procedure leaves inherited `TEMP` and `LOCALAPPDATA` unchanged. It blocks
if either is missing or matches the AppContainer path signature. It does not
call `Invoke-S6V2OfflineRegression.ps1` (which routes through MXC), contact
Telegram, download media, perform a real proof, or enable V2.

```powershell
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
    throw 'STOP: use Windows PowerShell 5.1.'
}
$sandboxPattern = 'AppData[\\/]+Local[\\/]+Packages[\\/]+sandbox\.'
if ([string]::IsNullOrWhiteSpace($env:TEMP) -or [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA) -or
    $env:TEMP -match $sandboxPattern -or $env:LOCALAPPDATA -match $sandboxPattern) {
    throw 'STOP: inherited TEMP/LOCALAPPDATA is absent or belongs to the AppContainer; do not substitute either value.'
}

$repoRoot = (Resolve-Path -LiteralPath '.').Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'STOP: project Python is missing.' }
$versionText = (& $python --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $versionText -ne 'Python 3.14.7') { throw "STOP: expected project Python 3.14.7; observed $versionText." }

$allowedRoot = Join-Path $repoRoot '.s6r'
if (-not (Test-Path -LiteralPath $allowedRoot -PathType Container)) {
    [void][IO.Directory]::CreateDirectory($allowedRoot)
}
$allowedItem = Get-Item -LiteralPath $allowedRoot -Force
if (($allowedItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'STOP: .s6r is redirected.' }

$relativeFiles = @(
    'tools/manual_proofs/s6_v2_proof_harness.py',
    'tests/manual_proofs/test_s6_v2_proof_harness.py'
)
function Get-SourceSnapshot {
    $result = @{}
    foreach ($relative in $relativeFiles) {
        $path = Join-Path $repoRoot $relative
        $result[$relative] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    return $result
}
function Assert-SourceSnapshot($Expected) {
    $actual = Get-SourceSnapshot
    foreach ($relative in $relativeFiles) {
        if ($actual[$relative] -ne $Expected[$relative]) { throw "STOP: source snapshot changed: $relative" }
    }
}
function New-RunArea {
    $token = [Guid]::NewGuid().ToString('N').Substring(0, 12)
    $runRoot = Join-Path $allowedRoot $token
    if (Test-Path -LiteralPath $runRoot) { throw 'STOP: token collision; do not reuse the directory.' }
    [void][IO.Directory]::CreateDirectory($runRoot)
    $baseTemp = Join-Path $runRoot 't'
    [void][IO.Directory]::CreateDirectory($baseTemp)
    if ($baseTemp.Length -gt 80) { throw 'STOP: basetemp exceeds 80 characters.' }
    return [PSCustomObject]@{ RunRoot = $runRoot; BaseTemp = $baseTemp }
}
function Invoke-BoundedPython([string[]]$Arguments, [string]$RunRoot, [int]$WaitMilliseconds) {
    $stdout = Join-Path $RunRoot 'worker.stdout.log'
    $stderr = Join-Path $RunRoot 'worker.stderr.log'
    $pythonPidsBefore = @(Get-Process -Name python,pythonw -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $worker = Start-Process -FilePath $python -ArgumentList $Arguments -WorkingDirectory $repoRoot `
        -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    if (-not $worker.WaitForExit($WaitMilliseconds)) {
        $grace = [Diagnostics.Stopwatch]::StartNew()
        try {
            $killer = Start-Process -FilePath (Join-Path $env:WINDIR 'System32\taskkill.exe') `
                -ArgumentList @('/PID', "$($worker.Id)", '/T', '/F') -PassThru -NoNewWindow
            [void]$killer.WaitForExit(3000)
        } catch { }
        $worker.Refresh()
        if (-not $worker.HasExited -and $grace.ElapsedMilliseconds -lt 5000) {
            Stop-Process -Id $worker.Id -Force -ErrorAction SilentlyContinue
            [void]$worker.WaitForExit([Math]::Max(1, 5000 - [int]$grace.ElapsedMilliseconds))
        }
        $timer.Stop()
        $worker.Refresh()
        if (-not $worker.HasExited) { throw "BLOCKED: worker did not exit after bounded termination; preserve $RunRoot." }
        throw "TIMEOUT: preserve $RunRoot and stop; no retry."
    }
    [void]$worker.WaitForExit()
    $timer.Stop()
    $worker.Refresh()
    $remainingPython = @(Get-Process -Name python,pythonw -ErrorAction SilentlyContinue |
        Where-Object { $pythonPidsBefore -notcontains $_.Id } | Select-Object -ExpandProperty Id)
    "RUN_ROOT=$RunRoot"
    "WORKER_PID=$($worker.Id)"
    "ELAPSED_SECONDS=$([Math]::Round($timer.Elapsed.TotalSeconds, 3))"
    "EXIT_CODE=$($worker.ExitCode)"
    "NEW_PYTHON_WORKER_PIDS=$($remainingPython -join ',')"
    if ($remainingPython.Count -gt 0) { throw "BLOCKED: new Python processes remain; preserve $RunRoot." }
    return [PSCustomObject]@{ ExitCode = $worker.ExitCode; WorkerPid = $worker.Id; Stdout = $stdout; Stderr = $stderr }
}
function Get-JUnitCounts([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "STOP: JUnit missing: $Path" }
    [xml]$junit = Get-Content -LiteralPath $Path -Raw
    return [PSCustomObject]@{
        Cases = $junit.SelectNodes('//testcase').Count
        Failures = $junit.SelectNodes('//failure').Count
        Errors = $junit.SelectNodes('//error').Count
        Skipped = $junit.SelectNodes('//skipped').Count
    }
}

$initialSnapshot = Get-SourceSnapshot
$savedProfile = $env:S6_OFFLINE_REGRESSION_PROFILE
$savedMetadata = $env:S6_OFFLINE_REGRESSION_METADATA
$savedPytestAddopts = $env:PYTEST_ADDOPTS
$hadProfile = Test-Path Env:S6_OFFLINE_REGRESSION_PROFILE
$hadMetadata = Test-Path Env:S6_OFFLINE_REGRESSION_METADATA
$hadPytestAddopts = Test-Path Env:PYTEST_ADDOPTS
try {
    Remove-Item Env:S6_OFFLINE_REGRESSION_PROFILE -ErrorAction SilentlyContinue
    Remove-Item Env:S6_OFFLINE_REGRESSION_METADATA -ErrorAction SilentlyContinue
    Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue

    $testFile = 'tests/manual_proofs/test_s6_v2_proof_harness.py'
    $focused = New-RunArea
    $focusedJUnit = Join-Path $focused.RunRoot 'focused-junit.xml'
    $focusedTests = @(
        "${testFile}::test_execute_launcher_displays_fixed_profile_and_requires_fresh_native_confirmation",
        "${testFile}::test_two_process_handoff_real_harness_lifecycle_offline[aligned]",
        "${testFile}::test_two_process_handoff_real_harness_lifecycle_offline[unaligned-prepared]",
        "${testFile}::test_trusted_reference_two_process_synthetic_e2e",
        "${testFile}::test_child_domain_failure_emits_only_allowlisted_code_and_stage",
        "${testFile}::test_child_declared_and_observed_exit_mismatch_is_explicit",
        "${testFile}::test_planner_rejects_overlong_destination_before_queue_and_plans_short_contained_path",
        "${testFile}::test_corrupt_or_missing_child_json_fails_closed",
        "${testFile}::test_child_report_pid_mismatch_keeps_declared_exit_null_and_fails_closed",
        "${testFile}::test_failed_child_with_exit_5_and_null_result_never_satisfies_phase_acceptance",
        "${testFile}::test_download_error_category_with_secret_is_reduced_to_other_without_leaking"
    )
    $focusedArgs = @('-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        '--junitxml', $focusedJUnit, '--basetemp', $focused.BaseTemp) + $focusedTests
    $focusedResult = Invoke-BoundedPython $focusedArgs $focused.RunRoot 90000
    $focusedCounts = Get-JUnitCounts $focusedJUnit
    if ($focusedResult.ExitCode -ne 0 -or $focusedCounts.Cases -ne 12 -or
        $focusedCounts.Failures -ne 0 -or $focusedCounts.Errors -ne 0 -or $focusedCounts.Skipped -ne 0) {
        throw "FOCUSED GATE FAILED: preserve $($focused.RunRoot); do not run the full Harness or retry."
    }
    Assert-SourceSnapshot $initialSnapshot

    $full = New-RunArea
    $fullJUnit = Join-Path $full.RunRoot 'junit.xml'
    $fullMetadata = Join-Path $full.RunRoot 'worker-result.json'
    $env:S6_OFFLINE_REGRESSION_PROFILE = 'Harness'
    $env:S6_OFFLINE_REGRESSION_METADATA = $fullMetadata
    $fullArgs = @('-B', '-m', 'pytest', '-q', '-p', 'tools.manual_proofs.s6_v2_offline_regression_runner',
        '--junitxml', $fullJUnit, '--basetemp', $full.BaseTemp, $testFile)
    $fullResult = Invoke-BoundedPython $fullArgs $full.RunRoot 145000
    Assert-SourceSnapshot $initialSnapshot
    $fullCounts = Get-JUnitCounts $fullJUnit
    if (-not (Test-Path -LiteralPath $fullMetadata -PathType Leaf)) { throw "BLOCKED: worker metadata missing; preserve $($full.RunRoot)." }
    $metadata = Get-Content -LiteralPath $fullMetadata -Raw | ConvertFrom-Json
    $collected = @($metadata.collected_nodeids)
    $executed = @($metadata.executed_nodeids)
    $nodeDifference = @(Compare-Object -ReferenceObject $collected -DifferenceObject $executed)
    if ($fullResult.ExitCode -ne 0 -or $metadata.profile -ne 'Harness' -or $metadata.exit_code -ne 0 -or
        $metadata.termination_confirmed -ne $true -or $metadata.xfail -ne 0 -or $metadata.xpass -ne 0 -or
        $collected.Count -eq 0 -or $collected.Count -ne $executed.Count -or $nodeDifference.Count -ne 0 -or
        $fullCounts.Cases -ne $collected.Count -or $fullCounts.Failures -ne 0 -or
        $fullCounts.Errors -ne 0 -or $fullCounts.Skipped -ne 0) {
        throw "FULL HARNESS GATE FAILED OR INCONSISTENT: preserve $($full.RunRoot); do not retry."
    }
    "FOCUSED_GATE=PASS / CASES=$($focusedCounts.Cases) / ROOT=$($focused.RunRoot)"
    "FULL_HARNESS_GATE=PASS / CASES=$($fullCounts.Cases) / ROOT=$($full.RunRoot)"
    "FULL_WORKER_PID=$($fullResult.WorkerPid) / METADATA_PID=$($metadata.pid)"
    "JUNIT=$fullJUnit"
    "METADATA=$fullMetadata"
} finally {
    if ($hadProfile) { $env:S6_OFFLINE_REGRESSION_PROFILE = $savedProfile } else { Remove-Item Env:S6_OFFLINE_REGRESSION_PROFILE -ErrorAction SilentlyContinue }
    if ($hadMetadata) { $env:S6_OFFLINE_REGRESSION_METADATA = $savedMetadata } else { Remove-Item Env:S6_OFFLINE_REGRESSION_METADATA -ErrorAction SilentlyContinue }
    if ($hadPytestAddopts) { $env:PYTEST_ADDOPTS = $savedPytestAddopts } else { Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue }
}
```

After the procedure, retain both newly created run roots unchanged. Reconcile
the full run's `worker-result.json`, JUnit, stdout/stderr, exact collected and
executed node IDs, exit code, and process termination before changing S6 gate
status. A PASS of this offline regression does not itself grant formal S6
acceptance or enable V2.

## Continuity and next action

`PROJECT_STATE.md`, `CONTINUITY_RECORD.md`, and `handoff/LAST_HANDOFF.md` now
record the native validation evidence and the process-exit receipt gap below.
Both stages have been run once; preserve their roots and do not rerun
automatically. S6 remains open until the native evidence is fully reconciled
and formal acceptance is separately recorded.

## Native validation execution — 2026-10-20

The documented sequence was executed once from native Windows PowerShell
5.1.26100.9711 outside the Codex AppContainer. The focused stage completed
12/12 cases with 0 failures, 0 errors, and 0 skips. Its JUnit, stdout/stderr,
source hashes, and execution receipt are preserved under
`.s6r/e5fca75a3aa7/`.

After the focused JUnit established all 12 cases passing, the Harness profile
ran once and completed 196/196 cases with 0 failures, 0 errors, 0 skips,
xfail=0, and xpass=0 in 80.572 seconds. `worker-result.json` records profile
`Harness`, `exit_code=0`, `termination_confirmed=true`, 196 collected and 196
executed node IDs with exact equality, and worker PID 18636. The pytest stdout
reports `196 passed in 78.60s`; JUnit agrees. No Python workers remained.
JUnit, worker metadata, stdout/stderr, PowerShell transcript, basetemp, and the
execution receipt are preserved under `.s6r/bcb2a1158934/`.

Both process-control receipts left the outer `Start-Process` exit-code field
empty. JUnit and Harness worker metadata establish passing test results, but
the exact outer process-exit check in the procedure cannot be verified. The
discrepancy is recorded in `execution-reconciliation.json` in each run root;
original artifacts were not altered. No test stage was retried. Therefore this
evidence is `FUNCTIONAL_TESTS_PASS / NATIVE_GATE_PARTIAL`, not a change to
formal S6 acceptance: S6 remains open, V1 active, and V2 globally off. No
Telegram call, real proof, or Git publication occurred.
