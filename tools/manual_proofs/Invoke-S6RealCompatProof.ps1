<#
.SYNOPSIS
Runs the S6 real-compatibility proof using the repository virtual environment.

.PARAMETER Mode
Choose DryRun for the read-only preflight, or Execute to start the harness's
interactive proof flow. Execute is never selected automatically.

.EXAMPLE
  .\tools\manual_proofs\Invoke-S6RealCompatProof.ps1 -Mode DryRun

.EXAMPLE
  .\tools\manual_proofs\Invoke-S6RealCompatProof.ps1 -Mode Execute
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('DryRun', 'Execute')]
    [string] $Mode
)

$ErrorActionPreference = 'Continue'

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$pythonPath = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
$harnessPath = Join-Path $PSScriptRoot 's6_real_compat_proof.py'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Repository virtual-environment Python was not found: $pythonPath"
}
if (-not (Test-Path -LiteralPath $harnessPath -PathType Leaf)) {
    throw "S6 proof harness was not found: $harnessPath"
}
if ([string]::IsNullOrWhiteSpace($env:TEMP)) {
    throw 'TEMP is not set; cannot create the proof evidence directory.'
}

$runId = [Guid]::NewGuid().ToString('N')
$runName = "s6-real-compat-proof-$runId"
$evidenceDirectory = Join-Path $env:TEMP $runName
$transcriptPath = Join-Path $env:TEMP "$runName.transcript.txt"
[void][System.IO.Directory]::CreateDirectory($evidenceDirectory)

$evidenceVariable = 'S6_PROOF_EVIDENCE_DIR'
$hadPreviousEvidenceValue = Test-Path -LiteralPath "Env:$evidenceVariable"
$previousEvidenceValue = $null
if ($hadPreviousEvidenceValue) {
    $previousEvidenceValue = [Environment]::GetEnvironmentVariable($evidenceVariable, 'Process')
}

$transcriptStarted = $false
$pythonExitCode = $null
try {
    [Environment]::SetEnvironmentVariable($evidenceVariable, $evidenceDirectory, 'Process')
    Start-Transcript -LiteralPath $transcriptPath -Force | Out-Null
    $transcriptStarted = $true

    Write-Output "Mode: $Mode"
    Write-Output "Evidence directory: $evidenceDirectory"
    Write-Output "Transcript: $transcriptPath"

    if ($Mode -eq 'DryRun') {
        & $pythonPath $harnessPath '--dry-run'
    }
    else {
        # Execute is reached only when the caller explicitly selects this mode.
        & $pythonPath $harnessPath '--execute'
    }
    $pythonExitCode = $LASTEXITCODE
}
finally {
    try {
        if ($transcriptStarted) {
            Stop-Transcript | Out-Null

            # Remove common credential-shaped values from the PowerShell transcript.
            if (Test-Path -LiteralPath $transcriptPath -PathType Leaf) {
                $transcriptText = [System.IO.File]::ReadAllText($transcriptPath)
                $transcriptText = [regex]::Replace(
                    $transcriptText,
                    '(?im)(\b(?:authorization\s*[:=]\s*bearer|(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|token)\s*[:=])\s*)([^\s"'',;]+)',
                    '$1[REDACTED]'
                )
                $transcriptText = [regex]::Replace(
                    $transcriptText,
                    '(?im)^(Username|RunAs User|Machine):.*$',
                    '$1: [REDACTED]'
                )
                $transcriptText = [regex]::Replace(
                    $transcriptText,
                    '(?i)([A-Z]:\\Users\\)[^\\/\r\n]+',
                    '$1[USER]'
                )
                [System.IO.File]::WriteAllText(
                    $transcriptPath,
                    $transcriptText,
                    [System.Text.UTF8Encoding]::new($false)
                )
            }
        }
    }
    finally {
        if ($hadPreviousEvidenceValue) {
            [Environment]::SetEnvironmentVariable($evidenceVariable, $previousEvidenceValue, 'Process')
        }
        else {
            [Environment]::SetEnvironmentVariable($evidenceVariable, $null, 'Process')
        }
    }
}

if ($null -eq $pythonExitCode) {
    throw 'Harness did not return a process exit code.'
}
Write-Output "Harness exit code: $pythonExitCode"
# Preserve the Python process code in LASTEXITCODE without exiting the user's
# interactive PowerShell host.
