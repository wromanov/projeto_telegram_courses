$ErrorActionPreference = 'Stop'
$supervisorStartedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')
$supervisorPid = [int]$PID
$runRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent $runRoot)
$allowedRoot = Join-Path $repoRoot '.s6r'
$baseTemp = Join-Path $runRoot 't'
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$testFile = 'tests/manual_proofs/test_s6_v2_proof_harness.py'
$relativeFiles = @('tools/manual_proofs/s6_v2_proof_harness.py', 'tests/manual_proofs/test_s6_v2_proof_harness.py')
$patchPath = Join-Path $repoRoot 'docs/reports/S6_FINAL_GATE_REMEDIATION_2026-10-24/GATE_A_PATCH.md'
$patchSha256Expected = '9FED56D6B6072FF3F8F0A72E8060104931F84E0BC165F18FFBF65FDE7CA5C62F'
$harnessSha256Expected = '11132B2EC6EC9D3DCCCD07536E0834342B8F1432520FA744E5E0C961F1736197'
$testSha256Expected = 'FD9959C190D59DC2079DBA21766ED14FD95F189C7830C07E7B3A0FD841FFF6EC'
$fullJUnit = Join-Path $runRoot 'junit.xml'
$fullMetadata = Join-Path $runRoot 'worker-result.json'
$externalReceiptPath = Join-Path $runRoot 'external-process.json'
$identityReceiptPath = Join-Path $runRoot 'process-identity-reconciliation.json'
$finalReceiptPath = Join-Path $runRoot 'gate-a-evidence-receipt.json'
$hashSidecarPath = Join-Path $runRoot 'gate-a-evidence-receipt.sha256.json'
$nativeRunCount = 0
$scriptExitCode = 3

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
function Write-ExclusiveDurableJson([string]$Path, [object]$Value) {
    if (Test-Path -LiteralPath $Path) { throw "BLOCKED: receipt already exists; preserve run root: $Path" }
    $json = ConvertTo-Json -InputObject $Value -Depth 12
    $encoding = [System.Text.UTF8Encoding]::new($false)
    $bytes = $encoding.GetBytes($json + [Environment]::NewLine)
    $stream = [System.IO.FileStream]::new($Path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read, 4096, [System.IO.FileOptions]::WriteThrough)
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
    $readBack = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($readBack)) { throw "BLOCKED: durable receipt is empty: $Path" }
    $null = ConvertFrom-Json -InputObject $readBack -ErrorAction Stop
}
function Invoke-BoundedPython([string[]]$Arguments, [string]$RunRoot, [int]$WaitMilliseconds) {
    if ($WaitMilliseconds -le 0 -or -not (Test-Path -LiteralPath $RunRoot -PathType Container)) { throw 'BLOCKED: invalid deadline or missing exclusive run root.' }
    $stdout = Join-Path $RunRoot 'worker.stdout.log'
    $stderr = Join-Path $RunRoot 'worker.stderr.log'
    $receiptPath = Join-Path $RunRoot 'external-process.json'
    $externalProcess = $null
    $externalProcessPid = $null
    $startedAtUtc = $null
    $endedAtUtc = $null
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $timedOut = $false
    $terminationConfirmed = $false
    $exitCodeObserved = $false
    $processExitCode = $null
    $failureClass = $null
    $launchAttempted = $false
    $initialWaitForExitOutcome = 'NOT_STARTED'
    $terminationWaitForExitOutcome = 'NOT_REQUIRED'
    $finalWaitForExitOutcome = 'NOT_CONFIRMED'
    try {
        $processesBefore = @(Get-Process -ErrorAction Stop)
        $pythonPidsBefore = @($processesBefore | Where-Object { $_.ProcessName -in @('python', 'pythonw') } | Select-Object -ExpandProperty Id)
    } catch {
        $failureClass = 'PROCESS_INVENTORY_BEFORE_UNAVAILABLE'
        $pythonPidsBefore = @()
    }
    if ($null -eq $failureClass) {
        try {
            $launchAttempted = $true
            $script:nativeRunCount = 1
            $externalProcess = Start-Process -FilePath $python -ArgumentList $Arguments -WorkingDirectory $repoRoot -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
            $null = $externalProcess.Handle
            $externalProcessPid = [int]$externalProcess.Id
            $startedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')
            if (-not $externalProcess.WaitForExit($WaitMilliseconds)) {
                $timedOut = $true
                $initialWaitForExitOutcome = 'TIMED_OUT'
                $grace = [Diagnostics.Stopwatch]::StartNew()
                try {
                    $killer = Start-Process -FilePath (Join-Path $env:WINDIR 'System32\taskkill.exe') -ArgumentList @('/PID', "$($externalProcessPid)", '/T', '/F') -PassThru -WindowStyle Hidden
                    $killerWaited = $killer.WaitForExit(3000)
                    $terminationWaitForExitOutcome = if ($killerWaited) { 'TASKKILL_EXITED' } else { 'TASKKILL_WAIT_TIMED_OUT' }
                } catch {
                    $terminationWaitForExitOutcome = 'TASKKILL_LAUNCH_OR_WAIT_FAILED'
                }
                $externalProcess.Refresh()
                if (-not $externalProcess.HasExited -and $grace.ElapsedMilliseconds -lt 5000) {
                    try {
                        Stop-Process -Id $externalProcessPid -Force -ErrorAction Stop
                        $remainingGrace = [Math]::Max(1, 5000 - [int]$grace.ElapsedMilliseconds)
                        $graceWaited = $externalProcess.WaitForExit($remainingGrace)
                        if ($graceWaited) { $terminationWaitForExitOutcome = 'FORCED_PROCESS_EXITED_WITHIN_GRACE' } else { $terminationWaitForExitOutcome = 'FORCED_PROCESS_WAIT_TIMED_OUT' }
                    } catch {
                        $failureClass = 'TIMEOUT_TERMINATION_FAILED'
                        $terminationWaitForExitOutcome = 'FORCED_TERMINATION_FAILED'
                    }
                }
            } else {
                $initialWaitForExitOutcome = 'EXITED_WITHIN_TIMEOUT'
                [void]$externalProcess.WaitForExit()
                $terminationWaitForExitOutcome = 'FINAL_WAITFOR_EXIT_COMPLETED'
            }
        } catch {
            if ($null -eq $failureClass) { $failureClass = 'PROCESS_LAUNCH_OR_WAIT_FAILED' }
        }
    }
    if ($null -ne $externalProcess) {
        try {
            $externalProcess.Refresh()
            if ($externalProcess.HasExited) {
                [void]$externalProcess.WaitForExit()
                $finalWaitForExitOutcome = 'EXIT_CONFIRMED'
                $processExitCode = $externalProcess.ExitCode
                $exitCodeObserved = ($processExitCode -is [int])
                $terminationConfirmed = [bool]$externalProcess.HasExited
            } elseif ($null -eq $failureClass) {
                $failureClass = 'PROCESS_TERMINATION_UNCONFIRMED'
            }
        } catch {
            $failureClass = 'PROCESS_EXIT_CODE_UNAVAILABLE'
            $finalWaitForExitOutcome = 'EXIT_CODE_UNAVAILABLE'
        }
    }
    $remainingPython = @()
    $processInventoryAfterComplete = $false
    try {
        $processesAfter = @(Get-Process -ErrorAction Stop)
        $remainingPython = @($processesAfter | Where-Object { $_.ProcessName -in @('python', 'pythonw') -and $pythonPidsBefore -notcontains $_.Id } | Select-Object -ExpandProperty Id)
        $processInventoryAfterComplete = $true
        if ($remainingPython.Count -gt 0 -and $null -eq $failureClass) { $failureClass = 'NEW_PYTHON_PROCESS_REMAINS' }
    } catch {
        $failureClass = 'PROCESS_INVENTORY_AFTER_UNAVAILABLE'
    }
    $timer.Stop()
    $endedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')
    $receiptStatus = if ($timedOut) { 'TIMEOUT' } elseif ($null -ne $failureClass) { 'BLOCKED' } elseif ($terminationConfirmed -and $exitCodeObserved) { 'COMPLETED' } else { 'INCOMPLETE' }
    $processReceipt = [PSCustomObject]@{
        schema_version = 1
        status = $receiptStatus
        launch_attempted = $launchAttempted
        supervisor_pid = $supervisorPid
        supervisor_started_at_utc = $supervisorStartedAtUtc
        external_process = [PSCustomObject]@{ pid = $externalProcessPid; executable = $python; role = 'process_started_by_supervisor'; started_at_utc = $startedAtUtc }
        worker_metadata_pid = $null
        worker_metadata_status = 'RECORDED_SEPARATELY_AFTER_PROCESS'
        ended_at_utc = $endedAtUtc
        elapsed_seconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
        timeout_limit_ms = $WaitMilliseconds
        timed_out = $timedOut
        process_has_exited = $terminationConfirmed
        process_completed_status = $receiptStatus
        initial_wait_for_exit_outcome = $initialWaitForExitOutcome
        termination_wait_for_exit_outcome = $terminationWaitForExitOutcome
        final_wait_for_exit_outcome = $finalWaitForExitOutcome
        termination_confirmed = $terminationConfirmed
        process_exit_code = $processExitCode
        process_exit_code_observed = $exitCodeObserved
        process_inventory_after_complete = $processInventoryAfterComplete
        remaining_python_pids = @($remainingPython)
        failure_class = $failureClass
    }
    Write-ExclusiveDurableJson -Path $receiptPath -Value $processReceipt
    Write-Host "PROCESS_RECEIPT=$receiptPath STATUS=$receiptStatus"
    if ($null -ne $failureClass -or $timedOut -or -not $terminationConfirmed -or -not $exitCodeObserved -or $processExitCode -isnot [int]) { throw "BLOCKED: process result incomplete or inconsistent; preserve $RunRoot; no retry." }
    return [PSCustomObject]@{ ExitCode = [int]$processExitCode; SupervisorProcessId = [int]$supervisorPid; ExternalProcessId = [int]$externalProcessPid; StartedAtUtc = $startedAtUtc; EndedAtUtc = $endedAtUtc; ElapsedSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3); TerminationConfirmed = $terminationConfirmed; TimedOut = $timedOut; ReceiptPath = $receiptPath; RunRoot = $RunRoot; Stdout = $stdout; Stderr = $stderr }
}
function Get-JUnitCounts([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "STOP: JUnit missing: $Path" }
    [xml]$junit = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    return [PSCustomObject]@{ Cases = $junit.SelectNodes('//testcase').Count; Failures = $junit.SelectNodes('//failure').Count; Errors = $junit.SelectNodes('//error').Count; Skipped = $junit.SelectNodes('//skipped').Count }
}
function Get-ArtifactEvidence([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $item = Get-Item -LiteralPath $Path -Force
    return [PSCustomObject]@{ path = $Path; size_bytes = [long]$item.Length; sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
}

$scriptExitCode = 3
$envSaved = $false
$hadProfile = $false
$hadMetadata = $false
$hadPytestAddopts = $false
$invokeError = $null
try {
    if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) { throw 'STOP: Windows PowerShell 5.1 required.' }
    $sandboxPattern = 'AppData[\\/]+Local[\\/]+Packages[\\/]+sandbox\.'
    if ([string]::IsNullOrWhiteSpace($env:TEMP) -or [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA) -or $env:TEMP -match $sandboxPattern -or $env:LOCALAPPDATA -match $sandboxPattern) { throw 'STOP: TEMP/LOCALAPPDATA missing or AppContainer-backed.' }
    $nativeGroups = & whoami /groups | Out-String
    if ($LASTEXITCODE -ne 0 -or $nativeGroups -match 'S-1-15-2-|AppContainer') { throw 'STOP: current Windows token is AppContainer-backed.' }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'STOP: project .venv Python is missing.' }
    if (-not (Test-Path -LiteralPath $baseTemp -PathType Container)) { throw 'STOP: unique basetemp is missing.' }
    if (((Get-Item -LiteralPath $allowedRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'STOP: .s6r is redirected.' }
    if (((Get-Item -LiteralPath $runRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'STOP: run root is redirected.' }
    if ([IO.DriveInfo]::new('C:\').AvailableFreeSpace -lt 1GB) { throw 'STOP: less than 1 GiB free.' }
    $pythonVersion = (& $python --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne 'Python 3.14.7') { throw "STOP: project Python mismatch: $pythonVersion" }
    $pipCheck = (& $python -B -m pip check 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "STOP: dependency check failed: $pipCheck" }
    if ((Get-FileHash -LiteralPath $patchPath -Algorithm SHA256).Hash -ne $patchSha256Expected) { throw 'STOP: Gate A procedure patch changed.' }
    $initialSnapshot = Get-SourceSnapshot
    if ($initialSnapshot[$relativeFiles[0]] -ne $harnessSha256Expected -or $initialSnapshot[$relativeFiles[1]] -ne $testSha256Expected) { throw 'STOP: reviewed Harness/test source snapshot changed.' }
    foreach ($destination in @($fullJUnit, $fullMetadata, $externalReceiptPath, $identityReceiptPath, $finalReceiptPath, $hashSidecarPath)) {
        if (Test-Path -LiteralPath $destination) { throw "STOP: evidence destination already exists: $destination" }
    }
    $baselinePath = Join-Path $repoRoot '.s6r\bcb2a1158934\worker-result.json'
    if (-not (Test-Path -LiteralPath $baselinePath -PathType Leaf)) { throw 'STOP: historical Harness baseline metadata missing.' }
    $savedProfile = $env:S6_OFFLINE_REGRESSION_PROFILE
    $savedMetadata = $env:S6_OFFLINE_REGRESSION_METADATA
    $savedPytestAddopts = $env:PYTEST_ADDOPTS
    $hadProfile = Test-Path Env:S6_OFFLINE_REGRESSION_PROFILE
    $hadMetadata = Test-Path Env:S6_OFFLINE_REGRESSION_METADATA
    $hadPytestAddopts = Test-Path Env:PYTEST_ADDOPTS
    $envSaved = $true
    Remove-Item Env:S6_OFFLINE_REGRESSION_PROFILE -ErrorAction SilentlyContinue
    Remove-Item Env:S6_OFFLINE_REGRESSION_METADATA -ErrorAction SilentlyContinue
    Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue
    $env:S6_OFFLINE_REGRESSION_PROFILE = 'Harness'
    $env:S6_OFFLINE_REGRESSION_METADATA = $fullMetadata
    $fullArgs = @('-B', '-m', 'pytest', '-q', '-p', 'tools.manual_proofs.s6_v2_offline_regression_runner', '--junitxml', $fullJUnit, '--basetemp', $baseTemp, $testFile)
    Write-Host "PREFLIGHT_STATUS=PASS / POWERSHELL=$($PSVersionTable.PSVersion) / PYTHON=$pythonVersion / PIP_CHECK=PASS"
    Write-Host "NATIVE_RUN=FULL_HARNESS_ONLY / FOCUSED_RUN=PROHIBITED / TEST_SCOPE=$testFile / TIMEOUT_MS=145000"
    $fullResult = $null
    try { $fullResult = Invoke-BoundedPython -Arguments $fullArgs -RunRoot $runRoot -WaitMilliseconds 145000 } catch { $invokeError = $_.Exception.Message; Write-Host "HARNESS_INVOCATION_STATUS=INCOMPLETE / ERROR=$invokeError" }
    try { Assert-SourceSnapshot $initialSnapshot } catch { $invokeError = $_.Exception.Message }
    $externalReceipt = $null
    if (Test-Path -LiteralPath $externalReceiptPath -PathType Leaf) {
        try { $externalReceipt = Get-Content -LiteralPath $externalReceiptPath -Raw | ConvertFrom-Json -ErrorAction Stop } catch { $invokeError = 'EXTERNAL_RECEIPT_INVALID' }
    }
    if ($externalReceipt -and $externalReceipt.launch_attempted) { $nativeRunCount = 1 }
    if (Test-Path -LiteralPath $fullMetadata -PathType Leaf) {
        try { $metadata = Get-Content -LiteralPath $fullMetadata -Raw | ConvertFrom-Json -ErrorAction Stop } catch { $invokeError = 'WORKER_METADATA_INVALID' }
    } else { $metadata = $null }
    $junitCounts = $null
    try { $junitCounts = Get-JUnitCounts -Path $fullJUnit } catch { $invokeError = 'JUNIT_MISSING_OR_INVALID' }
    $baseline = Get-Content -LiteralPath $baselinePath -Raw | ConvertFrom-Json -ErrorAction Stop
    $collected = @()
    $executed = @()
    if ($metadata -and $metadata.collected_nodeids) { $collected = @($metadata.collected_nodeids) }
    if ($metadata -and $metadata.executed_nodeids) { $executed = @($metadata.executed_nodeids) }
    $sortedCollected = @($collected | Sort-Object)
    $sortedExecuted = @($executed | Sort-Object)
    $nodeDiff = @(Compare-Object -ReferenceObject $sortedCollected -DifferenceObject $sortedExecuted)
    $nodeIdsUnique = (@($collected | Sort-Object -Unique).Count -eq $collected.Count) -and (@($executed | Sort-Object -Unique).Count -eq $executed.Count)
    $nodeIdsEqual = $collected.Count -gt 0 -and $collected.Count -eq $executed.Count -and $nodeDiff.Count -eq 0 -and $nodeIdsUnique
    $baselineCollected = @($baseline.collected_nodeids)
    $baselineExecuted = @($baseline.executed_nodeids)
    $baselineDiff = @(Compare-Object -ReferenceObject @($baselineCollected | Sort-Object -Unique) -DifferenceObject @($collected | Sort-Object -Unique))
    $addedNodeIds = @($baselineDiff | Where-Object { $_.SideIndicator -eq '=>' } | Select-Object -ExpandProperty InputObject)
    $removedNodeIds = @($baselineDiff | Where-Object { $_.SideIndicator -eq '<=' } | Select-Object -ExpandProperty InputObject)
    $inventoryChanged = $baselineDiff.Count -gt 0
    $metadataPidValid = $metadata -and ($metadata.pid -is [int] -or $metadata.pid -is [long]) -and [long]$metadata.pid -gt 0 -and [long]$metadata.pid -le [int]::MaxValue
    $metadataPass = $metadataPidValid -and $metadata.profile -eq 'Harness' -and $metadata.exit_code -eq 0 -and $metadata.termination_confirmed -eq $true -and $metadata.xfail -eq 0 -and $metadata.xpass -eq 0
    $junitPass = $junitCounts -and $junitCounts.Cases -gt 0 -and $junitCounts.Failures -eq 0 -and $junitCounts.Errors -eq 0 -and $junitCounts.Skipped -eq 0
    $externalExitObserved = $externalReceipt -and $externalReceipt.process_exit_code_observed -eq $true -and ($externalReceipt.process_exit_code -is [int] -or $externalReceipt.process_exit_code -is [long])
    $externalProcessPid = if ($externalReceipt) { $externalReceipt.external_process.pid } else { $null }
    $externalProcessPass = $externalExitObserved -and $externalReceipt.process_exit_code -eq 0 -and $externalReceipt.process_has_exited -eq $true -and $externalReceipt.termination_confirmed -eq $true -and $externalReceipt.initial_wait_for_exit_outcome -eq 'EXITED_WITHIN_TIMEOUT' -and $externalReceipt.final_wait_for_exit_outcome -eq 'EXIT_CONFIRMED' -and $externalReceipt.timed_out -eq $false -and $externalReceipt.process_inventory_after_complete -eq $true -and @($externalReceipt.remaining_python_pids).Count -eq 0
    $identityStatus = if ($metadataPidValid -and $externalProcessPass) { 'OBSERVED' } else { 'BLOCKED' }
    $pidRelation = if (-not $metadataPidValid -or $null -eq $externalProcessPid) { 'UNVERIFIED' } elseif ([long]$metadata.pid -eq [long]$externalProcessPid) { 'PID_NUMERICALLY_EQUAL' } else { 'UNVERIFIED' }
    $identityReceipt = [PSCustomObject]@{
        schema_version = 1
        status = $identityStatus
        supervisor_pid = $supervisorPid
        external_process_pid = $externalProcessPid
        worker_metadata_pid = if ($metadataPidValid) { [int]$metadata.pid } else { $null }
        worker_metadata_source = 'worker-result.json'
        worker_metadata_identity = if ($metadata) { "profile=$($metadata.profile); exit_code=$($metadata.exit_code); termination_confirmed=$($metadata.termination_confirmed)" } else { 'UNAVAILABLE' }
        external_vs_worker_pid_relation = $pidRelation
        parent_child_relationship = 'UNVERIFIED / NOT_INFERRED_FROM_PID_DIFFERENCE'
        external_exit_code = if ($externalExitObserved) { [int]$externalReceipt.process_exit_code } else { $null }
        external_exit_code_source = 'Process.ExitCode after WaitForExit'
        external_termination_confirmed = if ($externalReceipt) { [bool]$externalReceipt.termination_confirmed } else { $false }
    }
    Write-ExclusiveDurableJson -Path $identityReceiptPath -Value $identityReceipt
    $sourceStable = $true
    try { Assert-SourceSnapshot $initialSnapshot } catch { $sourceStable = $false; $invokeError = $_.Exception.Message }
    $allPass = $externalProcessPass -and $metadataPass -and $junitPass -and $nodeIdsEqual -and -not $inventoryChanged -and $identityReceipt.status -eq 'OBSERVED' -and $sourceStable -and $nativeRunCount -eq 1
    if ($allPass) { $gateAStatus = 'PASS' }
    elseif (($externalExitObserved -and $externalReceipt.process_exit_code -ne 0) -or ($junitCounts -and ($junitCounts.Failures -gt 0 -or $junitCounts.Errors -gt 0 -or $junitCounts.Skipped -gt 0)) -or ($metadata -and ($metadata.exit_code -ne 0 -or $metadata.xfail -gt 0 -or $metadata.xpass -gt 0)) -or ($metadata -and $externalExitObserved -and (-not $nodeIdsEqual -or -not $junitPass))) { $gateAStatus = 'FAIL' } else { $gateAStatus = 'PARTIAL' }
    $artifactPaths = @((Join-Path $runRoot 'run-gate-a.ps1'), $externalReceiptPath, $identityReceiptPath, $fullMetadata, $fullJUnit, (Join-Path $runRoot 'worker.stdout.log'), (Join-Path $runRoot 'worker.stderr.log'))
    $artifactEvidence = @($artifactPaths | ForEach-Object { Get-ArtifactEvidence -Path $_ } | Where-Object { $null -ne $_ })
    $finalReceipt = [PSCustomObject]@{
        schema_version = 1
        activity = 'S6_GATE_A_NATIVE_FINAL_VALIDATION'
        preflight_status = 'PASS'
        native_run_count = $nativeRunCount
        full_harness_result = if ($gateAStatus -eq 'PASS') { 'PASS' } elseif ($externalExitObserved -and $externalReceipt.process_exit_code -ne 0) { 'FAIL' } else { 'INCOMPLETE' }
        gate_a_status = $gateAStatus
        repository = [PSCustomObject]@{ root = $repoRoot; branch = (git branch --show-current); head = (git rev-parse HEAD); upstream = (git rev-parse --abbrev-ref --symbolic-full-name '@{u}') }
        environment = [PSCustomObject]@{ host = $env:COMPUTERNAME; user = [Security.Principal.WindowsIdentity]::GetCurrent().Name; powershell = $PSVersionTable.PSVersion.ToString(); python = $pythonVersion; temp = $env:TEMP; localappdata = $env:LOCALAPPDATA; profile = 'Harness' }
        harness = [PSCustomObject]@{ test_scope = $testFile; invocation = '-B -m pytest -q -p tools.manual_proofs.s6_v2_offline_regression_runner --junitxml junit.xml --basetemp <run-root>\t tests/manual_proofs/test_s6_v2_proof_harness.py'; timeout_limit_ms = 145000 }
        supervisor = [PSCustomObject]@{ pid = $supervisorPid; started_at_utc = $supervisorStartedAtUtc }
        external_process = [PSCustomObject]@{ pid = $externalProcessPid; started_at_utc = if ($externalReceipt) { $externalReceipt.external_process.started_at_utc } else { $null }; ended_at_utc = if ($externalReceipt) { $externalReceipt.ended_at_utc } else { $null }; exit_code = if ($externalExitObserved) { [int]$externalReceipt.process_exit_code } else { $null }; exit_code_observed = [bool]$externalExitObserved; has_exited = if ($externalReceipt) { [bool]$externalReceipt.process_has_exited } else { $false }; wait_for_exit = if ($externalReceipt) { $externalReceipt.initial_wait_for_exit_outcome } else { 'UNAVAILABLE' }; final_wait_for_exit = if ($externalReceipt) { $externalReceipt.final_wait_for_exit_outcome } else { 'UNAVAILABLE' }; elapsed_seconds = if ($externalReceipt) { $externalReceipt.elapsed_seconds } else { $null }; timed_out = if ($externalReceipt) { [bool]$externalReceipt.timed_out } else { $null }; termination_confirmed = if ($externalReceipt) { [bool]$externalReceipt.termination_confirmed } else { $false }; status = if ($externalReceipt) { $externalReceipt.status } else { 'UNAVAILABLE' } }
        worker = [PSCustomObject]@{ pid = if ($metadataPidValid) { [int]$metadata.pid } else { $null }; metadata_path = $fullMetadata; metadata_identity = if ($metadata) { [PSCustomObject]@{ profile = $metadata.profile; exit_code = $metadata.exit_code; termination_confirmed = $metadata.termination_confirmed; xfail = $metadata.xfail; xpass = $metadata.xpass } } else { $null }; process_relationship = $identityReceipt.parent_child_relationship }
        junit = [PSCustomObject]@{ path = $fullJUnit; cases = if ($junitCounts) { $junitCounts.Cases } else { $null }; failures = if ($junitCounts) { $junitCounts.Failures } else { $null }; errors = if ($junitCounts) { $junitCounts.Errors } else { $null }; skipped = if ($junitCounts) { $junitCounts.Skipped } else { $null }; result = if ($junitPass) { 'PASS' } else { 'FAIL_OR_INCOMPLETE' } }
        node_id_reconciliation = [PSCustomObject]@{ collected = $collected.Count; executed = $executed.Count; exact_match = [bool]$nodeIdsEqual; unique_ids = [bool]$nodeIdsUnique; baseline_collected = $baselineCollected.Count; baseline_executed = $baselineExecuted.Count; baseline_inventory_changed = [bool]$inventoryChanged; added_nodeids = @($addedNodeIds); removed_nodeids = @($removedNodeIds) }
        process_termination = [PSCustomObject]@{ remaining_python_pids = if ($externalReceipt) { @($externalReceipt.remaining_python_pids) } else { @() }; inventory_complete = if ($externalReceipt) { [bool]$externalReceipt.process_inventory_after_complete } else { $false } }
        source_snapshot = [PSCustomObject]@{ harness_sha256 = $initialSnapshot[$relativeFiles[0]]; test_module_sha256 = $initialSnapshot[$relativeFiles[1]]; stable_after_run = [bool]$sourceStable; gate_a_patch_sha256 = $patchSha256Expected }
        evidence_artifacts = $artifactEvidence
        errors = @($invokeError)
    }
    Write-ExclusiveDurableJson -Path $finalReceiptPath -Value $finalReceipt
    $finalEvidence = Get-ArtifactEvidence -Path $finalReceiptPath
    Write-ExclusiveDurableJson -Path $hashSidecarPath -Value ([PSCustomObject]@{ receipt_path = $finalEvidence.path; size_bytes = $finalEvidence.size_bytes; sha256 = $finalEvidence.sha256 })
    Write-Host "GATE_A_STATUS=$gateAStatus"
    Write-Host "NATIVE_RUN_COUNT=$nativeRunCount"
    Write-Host "EVIDENCE_RECEIPT=$finalReceiptPath"
    Write-Host "EVIDENCE_SIZE_BYTES=$($finalEvidence.size_bytes)"
    Write-Host "EVIDENCE_SHA256=$($finalEvidence.sha256)"
    Write-Host "EXTERNAL_PID=$externalProcessPid WORKER_PID=$(if ($metadataPidValid) { $metadata.pid } else { 'UNKNOWN' })"
    Write-Host "COLLECTED=$($collected.Count) EXECUTED=$($executed.Count) NODE_IDS_EQUAL=$nodeIdsEqual"
    $scriptExitCode = if ($gateAStatus -eq 'PASS') { 0 } else { 2 }
} catch {
    Write-Host "PREFLIGHT_OR_RECONCILIATION_ERROR=$($_.Exception.Message)"
    $scriptExitCode = 3
} finally {
    if ($envSaved) {
        if ($hadProfile) { $env:S6_OFFLINE_REGRESSION_PROFILE = $savedProfile } else { Remove-Item Env:S6_OFFLINE_REGRESSION_PROFILE -ErrorAction SilentlyContinue }
        if ($hadMetadata) { $env:S6_OFFLINE_REGRESSION_METADATA = $savedMetadata } else { Remove-Item Env:S6_OFFLINE_REGRESSION_METADATA -ErrorAction SilentlyContinue }
        if ($hadPytestAddopts) { $env:PYTEST_ADDOPTS = $savedPytestAddopts } else { Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue }
    }
}
exit $scriptExitCode

