<#
.SYNOPSIS
Runs offline validation or a separately confirmed, hash-only S6 diagnostic probe.
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
$harnessPath = Join-Path $PSScriptRoot 's6_real_resume_proof.py'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw 'Repository virtual-environment Python was not found.'
}
if (-not (Test-Path -LiteralPath $harnessPath -PathType Leaf)) {
    throw 'S6 hash probe harness was not found.'
}
if ([string]::IsNullOrWhiteSpace($env:TEMP)) {
    throw 'TEMP is not set.'
}

Push-Location $repositoryRoot
try {
    if ($Mode -eq 'DryRun') {
        & $pythonPath $harnessPath '--hash-eof-probe-dry-run'
        $pythonExitCode = $LASTEXITCODE
    }
    else {
        $requiredConfirmation = 'EXECUTE S6 HASH EOF PROBE 598'
        Write-Output 'This restores only the existing protected Telegram session.'
        Write-Output 'It permits at most two GetFileHashes calls; GetFile and media payload are disabled.'
        Write-Output 'A second hash call requires a validated first response that advances the cursor.'
        Write-Output 'FloodWait stops the probe. A fresh evidence directory and ledger are created under TEMP.'
        $confirmation = Read-Host "Type exactly: $requiredConfirmation"
        if ($confirmation -cne $requiredConfirmation) {
            Write-Output 'REAL_EXECUTION=NOT_STARTED'
            Write-Output 'STOP=NATIVE_CONFIRMATION_NOT_MATCHED'
            exit 5
        }

        $authorizationBytes = New-Object byte[] 32
        $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $random.GetBytes($authorizationBytes)
        }
        finally {
            $random.Dispose()
        }
        $authorizationToken = [BitConverter]::ToString($authorizationBytes).Replace('-', '').ToLowerInvariant()
        $previousAuthorization = $env:S6_HASH_PROBE_AUTH
        try {
            $env:S6_HASH_PROBE_AUTH = $authorizationToken
            & $pythonPath $harnessPath '--hash-eof-probe-execute'
            $pythonExitCode = $LASTEXITCODE
        }
        finally {
            $env:S6_HASH_PROBE_AUTH = $previousAuthorization
            [Array]::Clear($authorizationBytes, 0, $authorizationBytes.Length)
            $authorizationToken = $null
        }
    }
}
finally {
    Pop-Location
}

Write-Output "Harness exit code: $pythonExitCode"
if ($pythonExitCode -ne 0) {
    exit $pythonExitCode
}
