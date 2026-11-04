[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $PythonExe,
    [int] $FocusedTimeoutSeconds = 1200,
    [int] $AffectedTimeoutSeconds = 1800,
    [int] $FullTimeoutSeconds = 3600,
    [switch] $AuditOnly
)

$ErrorActionPreference = 'Stop'

if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Error 'Use PowerShell 7 or newer.'
    exit 2
}

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$pythonPath = (Resolve-Path -LiteralPath $PythonExe).Path
$unitRoot = Join-Path $repoRoot 'tests\unit'
$integrationRoot = Join-Path $repoRoot 'tests\integration'
$pyprojectPath = Join-Path $repoRoot 'pyproject.toml'

if (-not (Test-Path -LiteralPath $unitRoot -PathType Container) -or
    -not (Test-Path -LiteralPath $integrationRoot -PathType Container)) {
    Write-Error 'Expected offline unit/integration test roots are unavailable.'
    exit 2
}

$pyproject = Get-Content -LiteralPath $pyprojectPath -Raw
if ($pyproject -notmatch 'testpaths\s*=\s*\[\s*"tests/unit"\s*,\s*"tests/integration"\s*\]') {
    Write-Error 'Test selection changed; review it before running.'
    exit 2
}

$versionText = (& $pythonPath -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")' 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $versionText -notmatch '^3\.14\.') {
    Write-Error "Python 3.14 is required; received '$versionText'."
    exit 2
}

$pytestVersion = (& $pythonPath -m pytest --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $pytestVersion -notmatch '^pytest\s+') {
    Write-Error 'The selected Python environment does not provide pytest.'
    exit 2
}

$testFiles = @(
    Get-ChildItem -LiteralPath $unitRoot, $integrationRoot -Filter '*.py' -File -Recurse |
        Sort-Object FullName
)
if ($testFiles.Count -eq 0) {
    Write-Error 'No standard offline test files were discovered.'
    exit 2
}

$testSources = @($testFiles | ForEach-Object {
    [IO.Path]::GetRelativePath($repoRoot, $_.FullName).Replace('\', '/')
})
if ($testSources | Where-Object { $_ -match '(^|/)manual_proofs(/|$)' }) {
    Write-Error 'Manual proofs are outside this offline regression selection.'
    exit 2
}

$directClientCalls = @(
    Select-String -LiteralPath $testFiles.FullName -Pattern '\bTelegramClient\s*\('
)
if ($directClientCalls.Count -gt 0) {
    Write-Error 'A test directly constructs TelegramClient; selection requires review.'
    exit 2
}

$gatewayConstructorFiles = @(
    Select-String -LiteralPath $testFiles.FullName -Pattern '\bTelethonGateway\s*\(' |
        Select-Object -ExpandProperty Path -Unique
)
foreach ($path in $gatewayConstructorFiles) {
    $source = Get-Content -LiteralPath $path -Raw
    if ($source -notmatch '\bclient_factory\s*=') {
        Write-Error "A TelethonGateway test lacks an injected client factory: $path"
        exit 2
    }
}

$focusedFiles = @($testFiles | Where-Object { $_.Name -like 'test_s9*.py' })
if ($focusedFiles.Count -eq 0) {
    Write-Error 'No focused S9 test files were discovered.'
    exit 2
}

$affectedFiles = @($testFiles | Where-Object {
    $relative = [IO.Path]::GetRelativePath($repoRoot, $_.FullName).Replace('\', '/')
    $relative -match '^tests/(unit|integration)/test_s[5-8].*\.py$' -or
    $relative -in @(
        'tests/unit/test_downloads.py',
        'tests/unit/test_telethon_gateway.py',
        'tests/integration/test_download_flow.py',
        'tests/integration/test_cli_scan.py'
    )
})

$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$outputDirectory = Join-Path $PSScriptRoot "native-results-$stamp"
$tempDirectory = Join-Path $env:TEMP "telegram-courses-s9-native-$stamp"

$phaseResults = [Collections.Generic.List[object]]::new()

function Invoke-PytestPhase {
    param(
        [string] $Label,
        [string[]] $Paths,
        [int] $TimeoutSeconds
    )

    $phaseTemp = Join-Path $tempDirectory $Label
    New-Item -ItemType Directory -Path $phaseTemp | Out-Null
    $arguments = [Collections.Generic.List[string]]::new()
    foreach ($argument in @('-m', 'pytest', '-q', '--basetemp', $phaseTemp)) {
        $arguments.Add($argument)
    }
    foreach ($path in $Paths) {
        $arguments.Add($path)
    }

    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $pythonPath
    $startInfo.WorkingDirectory = $repoRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    foreach ($argument in $arguments) {
        $startInfo.ArgumentList.Add($argument)
    }

    $process = [Diagnostics.Process]::Start($startInfo)
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $completed = $process.WaitForExit($TimeoutSeconds * 1000)
    $containment = 'NOT_REQUIRED'
    if (-not $completed) {
        $treeTerminated = $false
        try {
            $process.Kill($true)
            $treeTerminated = $process.WaitForExit(30000)
        }
        catch {
            $treeTerminated = $false
        }
        $containment = if ($treeTerminated) {
            'KILL_TREE_REQUESTED_ROOT_EXITED_UNVERIFIED'
        }
        else {
            'UNCONFIRMED'
        }
        $status = 'TIMEOUT'
        $exitCode = 124
    }
    else {
        $exitCode = $process.ExitCode
        $status = if ($exitCode -eq 0) { 'PASS' } else { 'FAIL' }
    }

    if ($status -eq 'TIMEOUT') {
        $stdout = '[output capture omitted after timeout; process tree was not independently verified]'
        $stderr = '[output capture omitted after timeout; process tree was not independently verified]'
    }
    else {
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
    }
    [IO.File]::WriteAllText((Join-Path $outputDirectory "$Label.stdout.txt"), $stdout)
    [IO.File]::WriteAllText((Join-Path $outputDirectory "$Label.stderr.txt"), $stderr)

    return [pscustomobject]@{
        phase = $Label
        status = $status
        exit_code = $exitCode
        process_id = $process.Id
        process_tree_containment = $containment
        timeout_seconds = $TimeoutSeconds
        selected_files = $Paths
        stdout_file = "$Label.stdout.txt"
        stderr_file = "$Label.stderr.txt"
    }
}

function Convert-ToRelativePaths {
    param([System.IO.FileInfo[]] $Files)
    return @($Files | ForEach-Object {
        [IO.Path]::GetRelativePath($repoRoot, $_.FullName).Replace('\', '/')
    })
}

$focusPaths = Convert-ToRelativePaths $focusedFiles
$affectedPaths = Convert-ToRelativePaths $affectedFiles

Write-Output "Python: $pythonPath ($versionText)"
Write-Output "Pytest: $pytestVersion"
Write-Output "Safety: standard unit/integration roots only; manual proofs excluded; no direct TelegramClient construction; TelethonGateway tests inject client_factory."
if ($AuditOnly) {
    Write-Output 'Focused S9 files:'
    $focusPaths | ForEach-Object { Write-Output "  $_" }
    Write-Output 'Affected S5-S8 files:'
    $affectedPaths | ForEach-Object { Write-Output "  $_" }
    Write-Output "Full offline selection: tests/unit tests/integration"
    exit 0
}

New-Item -ItemType Directory -Path $outputDirectory | Out-Null
New-Item -ItemType Directory -Path $tempDirectory | Out-Null
Write-Output "Evidence directory: $outputDirectory"

$phaseResults.Add((Invoke-PytestPhase -Label 'focused-s9' -Paths $focusPaths -TimeoutSeconds $FocusedTimeoutSeconds))
if ($phaseResults[-1].status -eq 'PASS') {
    $phaseResults.Add((Invoke-PytestPhase -Label 'affected-s5-s8' -Paths $affectedPaths -TimeoutSeconds $AffectedTimeoutSeconds))
}
if ($phaseResults.Count -eq 2 -and $phaseResults[-1].status -eq 'PASS') {
    $phaseResults.Add((Invoke-PytestPhase -Label 'full-offline' -Paths @('tests/unit', 'tests/integration') -TimeoutSeconds $FullTimeoutSeconds))
}

$summary = [pscustomobject]@{
    activity_id = 'TELEGRAM_S9_FINAL_INTEGRATION_01'
    generated_utc = [DateTime]::UtcNow.ToString('o')
    python_version = $versionText
    pytest_version = $pytestVersion
    safety_checks = @(
        'Python 3.14 required',
        'pyproject testpaths checked',
        'tests/unit and tests/integration only',
        'tests/manual_proofs excluded',
        'no direct TelegramClient construction in selected test sources',
        'TelethonGateway constructors use injected client_factory'
    )
    selected_focused_files = $focusPaths
    selected_affected_files = $affectedPaths
    phases = @($phaseResults)
    evidence_directory = $outputDirectory
    temporary_test_data_directory = $tempDirectory
}
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputDirectory 'summary.json') -Encoding utf8

$phaseResults | Format-Table phase, status, exit_code, timeout_seconds -AutoSize
Write-Output "Summary: $(Join-Path $outputDirectory 'summary.json')"

if ($phaseResults | Where-Object { $_.status -eq 'TIMEOUT' }) {
    exit 3
}
$failedPhases = @($phaseResults | Where-Object { $_.status -ne 'PASS' })
if ($phaseResults.Count -ne 3 -or $failedPhases.Count -gt 0) {
    exit 1
}
exit 0
