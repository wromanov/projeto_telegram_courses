# Gate A — correção do wrapper documentado

```text
ACTIVITY = S6_FINAL_GATE_REMEDIATION
SCOPE = GATE_A_ONLY
IMPLEMENTATION_KIND = DOCUMENTED_FUNCTION_REPLACEMENT
HISTORICAL_REPORT = PRESERVED / NOT EDITED
NATIVE_EXECUTION = NOT RUN
PYTEST_OR_HARNESS = NOT RUN
```

## Localização e causa

O wrapper usado na regressão de 2026-10-20 está somente como bloco de procedimento
em `docs/reports/S6_V2_NATIVE_REGRESSION_7_FAILURES_FIX_2026-10-20.md`.
Não existe um script próprio para essa regressão. O arquivo
`tools/manual_proofs/Invoke-S6V2OfflineRegression.ps1` é um launcher diferente,
restrito ao perfil Infrastructure/MXC; ele não implementa `Invoke-BoundedPython`.

A função histórica enviava linhas informativas e um `PSCustomObject` pelo stream
de sucesso. A atribuição `$focusedResult = Invoke-BoundedPython ...` podia,
portanto, capturar vários valores e deixar `.ExitCode` nulo. O bloco também não
gravava o `Process.ExitCode` observado em um recibo próprio. O PID do processo
criado pelo supervisor e o PID informado pelo worker são evidências distintas;
PIDs diferentes não demonstram parentesco.

## Substituição proposta para `Invoke-BoundedPython`

Este adendo contém apenas a função substituta e a reconciliação mínima de
identidade. Ela deve ser incorporada ao procedimento nativo somente em uma
execução que receba autorização separada. O `RunRoot` deve continuar vindo de
`New-RunArea`, que cria diretório GUID exclusivo sob `.s6r`.

```powershell
function Write-ExclusiveDurableJson([string]$Path, [object]$Value) {
    if (Test-Path -LiteralPath $Path) {
        throw "BLOCKED: receipt already exists; preserve its run root: $Path"
    }

    $json = ConvertTo-Json -InputObject $Value -Depth 8
    $encoding = [System.Text.UTF8Encoding]::new($false)
    $bytes = $encoding.GetBytes($json + [Environment]::NewLine)
    $stream = [System.IO.FileStream]::new(
        $Path,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::Read,
        4096,
        [System.IO.FileOptions]::WriteThrough
    )
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }

    # Detect a truncated, unreadable, or malformed receipt before returning.
    $readBack = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($readBack)) {
        throw "BLOCKED: durable receipt is empty; preserve its run root: $Path"
    }
    $null = ConvertFrom-Json -InputObject $readBack -ErrorAction Stop
}

function Invoke-BoundedPython([string[]]$Arguments, [string]$RunRoot, [int]$WaitMilliseconds) {
    if ($WaitMilliseconds -le 0 -or
        -not (Test-Path -LiteralPath $RunRoot -PathType Container)) {
        throw 'BLOCKED: invalid deadline or missing exclusive run root.'
    }

    $stdout = Join-Path $RunRoot 'worker.stdout.log'
    $stderr = Join-Path $RunRoot 'worker.stderr.log'
    $receiptPath = Join-Path $RunRoot 'external-process.json'
    $supervisorPid = $PID
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

    try {
        # Inventory failure blocks before launch; it must not become an empty baseline.
        $processesBefore = @(Get-Process -ErrorAction Stop)
        $pythonPidsBefore = @(
            $processesBefore |
                Where-Object { $_.ProcessName -in @('python', 'pythonw') } |
                Select-Object -ExpandProperty Id
        )
    } catch {
        $failureClass = 'PROCESS_INVENTORY_BEFORE_UNAVAILABLE'
        $pythonPidsBefore = @()
    }

    if ($null -eq $failureClass) {
        try {
            $externalProcess = Start-Process -FilePath $python -ArgumentList $Arguments `
                -WorkingDirectory $repoRoot -PassThru -NoNewWindow `
                -RedirectStandardOutput $stdout -RedirectStandardError $stderr
            $externalProcessPid = [int]$externalProcess.Id
            $startedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')

            if (-not $externalProcess.WaitForExit($WaitMilliseconds)) {
                $timedOut = $true
                $grace = [Diagnostics.Stopwatch]::StartNew()
                try {
                    $killer = Start-Process `
                        -FilePath (Join-Path $env:WINDIR 'System32\taskkill.exe') `
                        -ArgumentList @('/PID', "$externalProcessPid", '/T', '/F') `
                        -PassThru -WindowStyle Hidden
                    [void]$killer.WaitForExit(3000)
                } catch {
                    # The bounded Stop-Process fallback below still gets its existing chance.
                }

                $externalProcess.Refresh()
                if (-not $externalProcess.HasExited -and $grace.ElapsedMilliseconds -lt 5000) {
                    try {
                        Stop-Process -Id $externalProcessPid -Force -ErrorAction Stop
                        [void]$externalProcess.WaitForExit(
                            [Math]::Max(1, 5000 - [int]$grace.ElapsedMilliseconds)
                        )
                    } catch {
                        $failureClass = 'TIMEOUT_TERMINATION_FAILED'
                    }
                }
            } else {
                # Drain redirected handles and wait for process completion before reading ExitCode.
                [void]$externalProcess.WaitForExit()
            }
        } catch {
            if ($null -eq $failureClass) { $failureClass = 'PROCESS_LAUNCH_OR_WAIT_FAILED' }
        }
    }

    if ($null -ne $externalProcess) {
        try {
            $externalProcess.Refresh()
            if ($externalProcess.HasExited) {
                # This is the observed .NET Process.ExitCode, read only after completion.
                [void]$externalProcess.WaitForExit()
                $processExitCode = $externalProcess.ExitCode
                $exitCodeObserved = ($processExitCode -is [int])
                $terminationConfirmed = $externalProcess.HasExited
            } elseif ($null -eq $failureClass) {
                $failureClass = 'PROCESS_TERMINATION_UNCONFIRMED'
            }
        } catch {
            $failureClass = 'PROCESS_EXIT_CODE_UNAVAILABLE'
        }
    }

    $remainingPython = @()
    $processInventoryAfterComplete = $false
    try {
        $externalProcessIdsBefore = @($pythonPidsBefore)
        $processesAfter = @(Get-Process -ErrorAction Stop)
        $remainingPython = @(
            $processesAfter |
                Where-Object {
                    $_.ProcessName -in @('python', 'pythonw') -and
                    $externalProcessIdsBefore -notcontains $_.Id
                } |
                Select-Object -ExpandProperty Id
        )
        $processInventoryAfterComplete = $true
        if ($remainingPython.Count -gt 0 -and $null -eq $failureClass) {
            $failureClass = 'NEW_PYTHON_PROCESS_REMAINS'
        }
    } catch {
        $failureClass = 'PROCESS_INVENTORY_AFTER_UNAVAILABLE'
    }

    $timer.Stop()
    $endedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')
    $receiptStatus = if ($timedOut) { 'TIMEOUT' }
        elseif ($null -ne $failureClass) { 'BLOCKED' }
        elseif ($terminationConfirmed -and $exitCodeObserved) { 'COMPLETED' }
        else { 'INCOMPLETE' }

    $processReceipt = [PSCustomObject]@{
        schema_version = 1
        status = $receiptStatus
        supervisor_pid = [int]$supervisorPid
        external_process = [PSCustomObject]@{
            pid = $externalProcessPid
            executable = $python
            role = 'process_started_by_supervisor'
        }
        worker_metadata_pid = $null
        worker_metadata_status = 'RECORDED_SEPARATELY_AFTER_PROCESS'
        started_at_utc = $startedAtUtc
        ended_at_utc = $endedAtUtc
        elapsed_seconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
        timeout_limit_ms = $WaitMilliseconds
        timed_out = $timedOut
        termination_confirmed = $terminationConfirmed
        process_exit_code = $processExitCode
        process_exit_code_observed = $exitCodeObserved
        process_inventory_after_complete = $processInventoryAfterComplete
        remaining_python_pids = @($remainingPython)
        failure_class = $failureClass
    }
    Write-ExclusiveDurableJson -Path $receiptPath -Value $processReceipt

    Write-Host "PROCESS_RECEIPT=$receiptPath STATUS=$receiptStatus"
    if ($null -ne $failureClass -or $timedOut -or
        -not $terminationConfirmed -or -not $exitCodeObserved -or
        $processExitCode -isnot [int]) {
        throw "BLOCKED: process result incomplete or inconsistent; preserve $RunRoot; no retry."
    }

    # The success stream contains exactly one object; informational output uses host stream.
    return [PSCustomObject]@{
        ExitCode = [int]$processExitCode
        SupervisorProcessId = [int]$supervisorPid
        ExternalProcessId = [int]$externalProcessPid
        StartedAtUtc = $startedAtUtc
        EndedAtUtc = $endedAtUtc
        ElapsedSeconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
        TerminationConfirmed = $terminationConfirmed
        TimedOut = $timedOut
        ReceiptPath = $receiptPath
        RunRoot = $RunRoot
        Stdout = $stdout
        Stderr = $stderr
    }
}
```

## Reconciliação do PID de worker

O wrapper registra o supervisor e o processo externo iniciado pelo supervisor.
Depois de validar `worker-result.json`, o procedimento registra o PID declarado
pelo worker em um segundo recibo exclusivo, sem inferir uma árvore de processos:

```powershell
$workerMetadataPid = $null
$metadataPidValid = $false
try {
    if (-not (Test-Path -LiteralPath $fullMetadata -PathType Leaf)) {
        throw 'worker metadata missing'
    }
    $metadata = Get-Content -LiteralPath $fullMetadata -Raw -ErrorAction Stop |
        ConvertFrom-Json -ErrorAction Stop
    if (($metadata.pid -isnot [int] -and $metadata.pid -isnot [long]) -or
        [long]$metadata.pid -le 0 -or [long]$metadata.pid -gt [int]::MaxValue) {
        throw 'worker metadata PID missing or invalid'
    }
    $workerMetadataPid = [int]$metadata.pid
    $metadataPidValid = $true
} catch {
    $metadataPidValid = $false
}

$pidRelation = if (-not $metadataPidValid) { 'UNVERIFIED' }
    elseif ($workerMetadataPid -eq $fullResult.ExternalProcessId) { 'PID_NUMERICALLY_EQUAL' }
    else { 'UNVERIFIED' }
$identityReceipt = [PSCustomObject]@{
    schema_version = 1
    status = if ($metadataPidValid -and $fullResult.TerminationConfirmed -and
        $fullResult.ExitCode -is [int]) { 'OBSERVED' } else { 'BLOCKED' }
    supervisor_pid = $fullResult.SupervisorProcessId
    external_process_pid = $fullResult.ExternalProcessId
    worker_metadata_pid = $workerMetadataPid
    worker_metadata_source = 'worker-result.json'
    external_vs_worker_pid_relation = $pidRelation
    parent_child_relationship = 'UNVERIFIED / NOT_INFERRED_FROM_PID_DIFFERENCE'
    external_exit_code = $fullResult.ExitCode
    external_exit_code_source = 'Process.ExitCode after WaitForExit'
    external_termination_confirmed = $fullResult.TerminationConfirmed
}
$identityReceiptPath = Join-Path $full.RunRoot 'process-identity-reconciliation.json'
Write-ExclusiveDurableJson -Path $identityReceiptPath -Value $identityReceipt
if ($identityReceipt.status -ne 'OBSERVED') {
    throw "BLOCKED: process identity receipt incomplete; preserve $($full.RunRoot); no retry."
}
```

`PID_NUMERICALLY_EQUAL` registra somente igualdade numérica observada; não
afirma identidade temporal ou relação pai-filho. Se os valores diferirem, a
relação fica `UNVERIFIED`. O gate completo continua condicionado às verificações
JUnit/metadata existentes, ao exit code externo igual a zero e à ausência de
processos remanescentes. Nenhum campo ausente, timeout ou divergência pode
produzir `PASS`.

## Estado da correção

```text
GATE_A_FIX = DOCUMENTED_PROCEDURE_CORRECTION_MATERIALIZED
STRUCTURED_RESULT = ONE_PSCUSTOMOBJECT_ON_SUCCESS_PIPELINE
EXTERNAL_EXIT_CAPTURE = Process.ExitCode_AFTER_WAITFOREXIT_AND_DURABLE_RECEIPT
PROCESS_IDENTITY = SUPERVISOR / EXTERNAL / WORKER_METADATA_SEPARATED
HISTORICAL_RECEIPTS = PRESERVED
STATIC_PARSER_QA = PASS / ROOT VALIDATION / Windows PowerShell 5.1.26100.9711 / 2 BLOCKS / 0 ERRORS
NATIVE_VALIDATION = PENDING / REQUIRES_SEPARATE_AUTHORIZATION
```

Esta remediação não executou pytest, Harness, wrapper, download, Telegram/RPC
ou prova real. A autorização desta atividade cobre somente a preparação do
procedimento; nova execução nativa permanece pendente de autorização própria.
