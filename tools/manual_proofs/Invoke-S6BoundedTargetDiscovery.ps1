<#
.SYNOPSIS
Runs the S6 metadata-only target discovery in DryRun or Execute mode.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('DryRun', 'Execute')]
    [string] $Mode
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$pythonPath = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
$runnerPath = Join-Path $PSScriptRoot 's6_bounded_target_discovery.py'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw 'Repository virtual-environment Python was not found.'
}
if (-not (Test-Path -LiteralPath $runnerPath -PathType Leaf)) {
    throw 'S6 bounded discovery runner was not found.'
}

if ($Mode -eq 'DryRun') {
    & $pythonPath $runnerPath '--dry-run'
    if ($LASTEXITCODE -ne 0) {
        throw "DryRun failed with exit code $LASTEXITCODE."
    }
    return
}

$confirmationText = @'
EXECUTE reads metadata using only the existing protected session for the already authorized Telegram account. It does not log in or create a protected session. GetDialogs may return recent message previews; the application will discard them without reading, projecting, logging, or persisting them. The operation makes one GetDialogs RPC with a maximum of 100 dialogs (within the 200-dialog / 3-RPC ceiling), then reads at most 200 raw messages if the exact channel peer is found. It does not access SQLite, download media, request hashes, or read media bytes.
Type exactly: I CONFIRM S6 METADATA RASMOO
'@
Write-Host $confirmationText
$entered = Read-Host 'Confirmation'
if ($entered -cne 'I CONFIRM S6 METADATA RASMOO') {
    Write-Output 'Confirmation did not match. No Python process, session restore, or RPC was started.'
    exit 2
}

$variableName = 'S6_BOUNDED_TARGET_CONFIRMATION'
$hadPreviousValue = Test-Path -LiteralPath "Env:$variableName"
$previousValue = [Environment]::GetEnvironmentVariable($variableName, 'Process')
try {
    [Environment]::SetEnvironmentVariable(
        $variableName,
        'I CONFIRM S6 METADATA RASMOO',
        'Process'
    )
    & $pythonPath $runnerPath '--execute'
    $pythonExitCode = $LASTEXITCODE
}
finally {
    if ($hadPreviousValue) {
        [Environment]::SetEnvironmentVariable($variableName, $previousValue, 'Process')
    }
    else {
        [Environment]::SetEnvironmentVariable($variableName, $null, 'Process')
    }
}
if ($pythonExitCode -ne 0) {
    throw "Execute stopped with exit code $pythonExitCode."
}
