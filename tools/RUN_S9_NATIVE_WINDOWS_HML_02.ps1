$ErrorActionPreference = 'Stop'

if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
    throw 'BLOCKED: execute em Windows PowerShell 5.1.'
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$runner = Join-Path $PSScriptRoot 's9_native_windows_hml_02.py'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'BLOCKED: project virtual environment Python was not found.'
}
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw 'BLOCKED: local S9 HML runner was not found.'
}

$oldPythonPath = $env:PYTHONPATH
$runnerExitCode = 2
try {
    $sourceRoot = Join-Path $repoRoot 'src'
    if ([string]::IsNullOrEmpty($oldPythonPath)) {
        $env:PYTHONPATH = $sourceRoot
    } else {
        $env:PYTHONPATH = $sourceRoot + ';' + $oldPythonPath
    }
    & $python -B $runner
    $runnerExitCode = $LASTEXITCODE
} finally {
    if ($null -eq $oldPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $oldPythonPath
    }
}

if ($runnerExitCode -ne 0) {
    Write-Warning "S9 launcher stopped with exit code $runnerExitCode. LASTEXITCODE retains the Python result."
}
