<#
.SYNOPSIS
Runs offline validation or a separately confirmed, one-call S6 EOF hash probe.
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
$harnessPath = Join-Path $PSScriptRoot 's6_controlled_eof_hash_probe.py'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw 'Repository virtual-environment Python was not found.'
}
if (-not (Test-Path -LiteralPath $harnessPath -PathType Leaf)) {
    throw 'Controlled S6 EOF probe harness was not found.'
}
if ([string]::IsNullOrWhiteSpace($env:TEMP)) {
    throw 'TEMP is not set.'
}

Push-Location $repositoryRoot
try {
    if ($Mode -eq 'DryRun') {
        & $pythonPath -m tools.manual_proofs.s6_controlled_eof_hash_probe '--dry-run'
        $pythonExitCode = $LASTEXITCODE
    }
    else {
        $requiredConfirmation = 'EXECUTE S6 CONTROLLED EOF HASH PROBE 7603'
        Write-Output 'This uses only the existing protected session and permits one GetFileHashes call.'
        Write-Output 'GetFile is disabled; media payload is fixed at zero; automatic retries are disabled.'
        Write-Output 'The query target is channel -1002368271467, message 7603, media 5089068167339181674.'
        Write-Output 'No full download is authorized by this probe.'
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
        $previousAuthorization = $env:S6_CONTROLLED_EOF_HASH_PROBE_AUTH
        try {
            $env:S6_CONTROLLED_EOF_HASH_PROBE_AUTH = $authorizationToken
            & $pythonPath -m tools.manual_proofs.s6_controlled_eof_hash_probe '--execute'
            $pythonExitCode = $LASTEXITCODE
        }
        finally {
            $env:S6_CONTROLLED_EOF_HASH_PROBE_AUTH = $previousAuthorization
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
