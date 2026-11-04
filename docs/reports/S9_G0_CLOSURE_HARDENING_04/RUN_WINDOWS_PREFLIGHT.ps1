[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Python 3.14 do ambiente virtual não encontrado: $pythonPath"
}

$cases = @(
    [pscustomobject]@{
        Name = "P01_SOCKETPAIR"
        Code = "import socket; left, right = socket.socketpair(); left.close(); right.close(); print('P01_SOCKETPAIR_OK')"
    },
    [pscustomobject]@{
        Name = "P02_ASYNCIO_RUN"
        Code = "import asyncio; asyncio.run(asyncio.sleep(0)); print('P02_ASYNCIO_OK')"
    }
)

function Get-DescendantProcessIds {
    param([Parameter(Mandatory)][int]$RootProcessId)

    $snapshot = @(Get-CimInstance -ClassName Win32_Process `
        -Property ProcessId, ParentProcessId -ErrorAction Stop)
    $known = [System.Collections.Generic.HashSet[int]]::new()
    $descendants = [System.Collections.Generic.HashSet[int]]::new()
    [void]$known.Add($RootProcessId)

    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($entry in $snapshot) {
            $processIdValue = [int]$entry.ProcessId
            $parentProcessId = [int]$entry.ParentProcessId
            if ($known.Contains($parentProcessId) -and $known.Add($processIdValue)) {
                [void]$descendants.Add($processIdValue)
                $changed = $true
            }
        }
    }

    return @($descendants)
}

$results = foreach ($case in $cases) {
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $pythonPath
    $startInfo.WorkingDirectory = $repoRoot
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    [void]$startInfo.ArgumentList.Add("-I")
    [void]$startInfo.ArgumentList.Add("-B")
    [void]$startInfo.ArgumentList.Add("-c")
    [void]$startInfo.ArgumentList.Add($case.Code)

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $started = $process.Start()

    if (-not $started) {
        throw "Não foi possível iniciar o processo para $($case.Name)."
    }

    $processId = $process.Id
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $descendantIds = [System.Collections.Generic.HashSet[int]]::new()
    $treeObservationAvailable = $true
    $treeObservationErrorType = $null
    $naturalExit = $false
    while (-not $process.HasExited -and $watch.ElapsedMilliseconds -lt 10000) {
        try {
            foreach ($descendantId in (Get-DescendantProcessIds -RootProcessId $processId)) {
                [void]$descendantIds.Add([int]$descendantId)
            }
        }
        catch {
            $treeObservationAvailable = $false
            $treeObservationErrorType = $_.Exception.GetType().FullName
        }

        if ($process.WaitForExit(50)) {
            $naturalExit = $true
            break
        }
    }
    if ($process.HasExited) {
        $naturalExit = $true
    }

    $killRequested = $false
    $killError = $null
    $exitCode = $null
    $exitCodeAfterCleanup = $null

    if (-not $naturalExit) {
        if ($treeObservationAvailable) {
            try {
                foreach ($descendantId in (Get-DescendantProcessIds -RootProcessId $processId)) {
                    [void]$descendantIds.Add([int]$descendantId)
                }
            }
            catch {
                $treeObservationAvailable = $false
                $treeObservationErrorType = $_.Exception.GetType().FullName
            }
        }

        try {
            $process.Kill($true)
            $killRequested = $true
        }
        catch {
            $killError = $_.Exception.GetType().FullName
        }

        $treeEnded = $process.WaitForExit(5000)
        if ($treeEnded) {
            $exitCodeAfterCleanup = $process.ExitCode
        }
    }
    else {
        $treeEnded = $process.HasExited
        $exitCode = $process.ExitCode
    }

    $processTreeEnded = $false
    if ($treeObservationAvailable -and $process.HasExited) {
        $treeCheck = [System.Diagnostics.Stopwatch]::StartNew()
        do {
            try {
                $currentDescendants = @(Get-DescendantProcessIds -RootProcessId $processId)
                foreach ($descendantId in $currentDescendants) {
                    [void]$descendantIds.Add([int]$descendantId)
                }
                if ($currentDescendants.Count -eq 0) {
                    $processTreeEnded = $true
                    break
                }
            }
            catch {
                $treeObservationAvailable = $false
                $treeObservationErrorType = $_.Exception.GetType().FullName
                break
            }
            Start-Sleep -Milliseconds 50
        } while ($treeCheck.ElapsedMilliseconds -lt 2000)
        $treeCheck.Stop()
    }

    $watch.Stop()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    $status = if (-not $naturalExit) {
        "TIMEOUT"
    }
    elseif ($exitCode -eq 0 -and $treeObservationAvailable -and $processTreeEnded) {
        "PASS"
    }
    elseif (-not $treeObservationAvailable -or -not $processTreeEnded) {
        "TREE_UNPROVEN"
    }
    else {
        "FAIL"
    }

    [pscustomobject]@{
        probe = $case.Name
        status = $status
        pid = $processId
        duration_ms = $watch.ElapsedMilliseconds
        timeout_ms = 10000
        natural_exit_code_observed = $naturalExit
        exit_code = $exitCode
        timeout_cleanup_exit_code = $exitCodeAfterCleanup
        timeout_kill_tree_requested = $killRequested
        root_process_ended = $treeEnded
        process_tree_observation_available = $treeObservationAvailable
        process_tree_observation_error_type = $treeObservationErrorType
        observed_descendant_pids = @($descendantIds | Sort-Object)
        process_tree_ended_after_observation = $processTreeEnded
        kill_error_type = $killError
        stdout = $stdout.Trim()
        stderr = $stderr.Trim()
    }

    $process.Dispose()
}

$results | ConvertTo-Json -Depth 4
$failed = @($results | Where-Object {
    $_.status -ne "PASS" -or -not $_.root_process_ended `
        -or -not $_.process_tree_observation_available `
        -or -not $_.process_tree_ended_after_observation
})

if ($failed.Count -gt 0) {
    exit 1
}

exit 0
