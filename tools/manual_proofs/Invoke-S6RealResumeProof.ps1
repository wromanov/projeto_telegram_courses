<#
.SYNOPSIS
Runs the offline S6 proof, or starts a protected real proof after an explicit
interactive confirmation in this native PowerShell process.
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
    throw 'S6 resume proof harness was not found.'
}
if ([string]::IsNullOrWhiteSpace($env:TEMP)) {
    throw 'TEMP is not set.'
}

Push-Location $repositoryRoot
try {
    if ($Mode -eq 'DryRun') {
        & $pythonPath $harnessPath '--dry-run'
        $pythonExitCode = $LASTEXITCODE
    }
    else {
        $requiredConfirmation = 'EXECUTE S6 REAL RESUME 598'
        Write-Output 'This starts the fixed S6 real proof, using only the existing protected Telegram session.'
        Write-Output 'It creates a new isolated evidence directory under TEMP and uses the fixed call and byte caps.'
        Write-Output 'No authentication flow will be started. A missing or invalid session stops the proof.'
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
        $previousAuthorization = $env:S6_REAL_EXECUTE_AUTH
        try {
            $env:S6_REAL_EXECUTE_AUTH = $authorizationToken
            & $pythonPath $harnessPath '--execute'
            $pythonExitCode = $LASTEXITCODE
        }
        finally {
            $env:S6_REAL_EXECUTE_AUTH = $previousAuthorization
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
