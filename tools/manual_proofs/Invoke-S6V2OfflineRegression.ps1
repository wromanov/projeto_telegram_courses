[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Infrastructure')]
    [Alias('Profile')]
    [string]$RegressionProfile
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
    throw 'BLOCKED: this launcher requires Windows PowerShell 5.1.'
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$executor = Join-Path $PSScriptRoot 's6_v2_mxc_host_executor.py'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'BLOCKED: repository .venv Python is missing.'
}
if (-not (Test-Path -LiteralPath $executor -PathType Leaf)) {
    throw 'BLOCKED: MXC host executor is missing.'
}

# Keep this process in the exec_command session. The persistent stdin/stdout
# channel is the executor's JSONL control transport; it starts no job by itself.
& $python -I $executor
exit $LASTEXITCODE
