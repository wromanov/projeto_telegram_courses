# Final, fourth and one-shot attempt for message 585. Requires native PS 5.1.
$ErrorActionPreference = 'Stop'
$Root = 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
    throw 'NATIVE_WINDOWS_POWERSHELL_51_REQUIRED'
}
if ($env:COMPUTERNAME -cne 'ROMA_CASA') { throw 'EXPECTED_HOST_ROMA_CASA' }
if (-not [Environment]::UserInteractive -or [Console]::IsInputRedirected) {
    throw 'HUMAN_INTERACTIVE_CONSOLE_REQUIRED'
}
if ($env:LOCALAPPDATA -match '\\Packages\\sandbox\.') {
    throw 'SANDBOX_LOCALAPPDATA_NOT_ALLOWED'
}
Set-Location -LiteralPath $Root
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$Guard = Join-Path $Root 'tools\telegram_3_resume_585_fourth_guard.py'
$Product = Join-Path $env:LOCALAPPDATA 'telegram_courses_product'
$DB = Join-Path $Product 'db\catalog.sqlite3'
$Dest = Join-Path $Product 'downloads'
$Marker = Join-Path $Product 'db\resume_final_01_recover585_fourth.started'
if (-not (Test-Path -LiteralPath $Py -PathType Leaf)) { throw 'PYTHON_ENVIRONMENT_NOT_FOUND' }
if (Test-Path -LiteralPath $Marker) { throw 'FOURTH_ATTEMPT_ALREADY_CONSUMED' }

function Assert-NoConcurrentProjectPython {
    try {
        $AllPython = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction Stop)
    } catch { throw 'CONCURRENCY_CHECK_UNAVAILABLE' }
    if (@($AllPython | Where-Object { -not $_.ExecutablePath }).Count -ne 0) {
        throw 'CONCURRENCY_CHECK_INDETERMINATE'
    }
    $PythonPath = [System.IO.Path]::GetFullPath($Py)
    $Running = @($AllPython | Where-Object { $_.ExecutablePath -ieq $PythonPath })
    if ($Running.Count -ne 0) { throw 'CONCURRENT_PROJECT_PYTHON_PROCESS' }
}

function Invoke-Recovery585Guard([switch]$Post) {
    $GuardArgs = @('-B', $Guard)
    if ($Post) { $GuardArgs += '--post' }
    $Lines = @(& $Py @GuardArgs)
    $Exit = $LASTEXITCODE
    $Lines | ForEach-Object { Write-Host $_ }
    if ($Exit -ne 0) {
        if ($Post) { throw 'RECOVERY585_FOURTH_POSTCONDITION_BLOCKED' }
        throw 'RECOVERY585_FOURTH_PREFLIGHT_BLOCKED'
    }
    return $Lines
}

Assert-NoConcurrentProjectPython
$Before = Invoke-Recovery585Guard
$DigestLines = @($Before | Where-Object { $_ -match '^PREFIX_SHA256=[a-f0-9]{64}$' })
if ($DigestLines.Count -ne 1) { throw 'PREFIX_DIGEST_PREFLIGHT_INVALID' }
$PrefixHash = $DigestLines[0].Substring(14)

Write-Host ''
Write-Host 'GATE 2 — QUARTA E ÚLTIMA TENTATIVA AUTORIZADA / SOMENTE MENSAGEM 585'
Write-Host 'RASMOO -1002758699600 / Candidato de Ouro / Competencias ID 44'
Write-Host 'Tentativas anteriores: 3; esta execução permite no máximo 1 tentativa.'
Write-Host 'A tentativa anterior terminou REMOTE_HASH_RANGE_INVALID; qualquer nova falha encerra o piloto.'
Write-Host 'Sem downgrade, retry, 586/587, outros vídeos, alterações S9/V2 ou Git.'
Write-Host 'Depois de aceitar G0, o marcador one-shot permanece mesmo se G4 for recusado.'
$G0 = Read-Host 'G0 HUMANO: digite SIM para iniciar esta única execução e obter o plano remoto fresco'
if ($G0 -cne 'SIM') { Write-Host 'G0_CANCELLED; nenhum marcador novo criado.'; exit 4 }

Assert-NoConcurrentProjectPython
$Again = Invoke-Recovery585Guard
$AgainDigest = @($Again | Where-Object { $_ -match '^PREFIX_SHA256=[a-f0-9]{64}$' })
if ($AgainDigest.Count -ne 1 -or $AgainDigest[0].Substring(14) -cne $PrefixHash) {
    throw 'PREFIX_CHANGED_AFTER_G0'
}

$UTF8 = New-Object System.Text.UTF8Encoding($false)
$Record = [ordered]@{
    activity = 'TELEGRAM-3-585-FINAL-CLOSURE-01'
    message_id = 585
    attempt_number = 4
    prior_attempts = 3
    status = 'FOURTH_ATTEMPT_STARTED'
    prefix_bytes = 6029312
    prefix_sha256 = $PrefixHash
    g0_confirmation = 'HUMAN_INTERACTIVE'
    started_utc = (Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json -Compress
$File = [System.IO.File]::Open($Marker, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try {
    $Bytes = $UTF8.GetBytes($Record + [Environment]::NewLine)
    $File.Write($Bytes, 0, $Bytes.Length)
    $File.Flush($true)
} finally { $File.Dispose() }

$Args = @(
    'download', 'queue',
    '--channel-id', '-1002758699600',
    '--scope', 'module',
    '--required-module-id', '44',
    '--pilot-message-ids', '585',
    '--pilot-resume-585-once',
    '--database', $DB,
    '--download-dir', $Dest,
    '--workers', '1',
    '--attempts-per-media', '1',
    '--max-media-items', '1',
    '--max-single-media-bytes', '134217728',
    '--max-transfer-bytes', '6291456',
    '--max-runtime-seconds', '1800',
    '--integrity-mode', 'REMOTE_HASH_REQUIRED',
    '--private-downloads', '--require-full-remote-hash'
)
Write-Host 'G0=PASS; marcador one-shot da quarta tentativa criado.'
Write-Host 'A CLI exibirá o plano fresco; confirme G4 somente se SELECTED_MEDIA_COUNT=1, PENDING_BYTES=170323, LIMIT_CHECK_RESULT=PASS e REMOTE_HASH_FULL estiverem corretos.'
Write-Host 'A revalidação de identidade e os hashes remotos ocorrerão no caminho estrito; divergência bloqueia sem downgrade.'
$PreviousG0 = $env:TELEGRAM_COURSES_PILOT_G0_INTERACTIVE
$env:TELEGRAM_COURSES_PILOT_G0_INTERACTIVE = '1'
$Timer = [System.Diagnostics.Stopwatch]::StartNew()
try {
    & $Py -B -m telegram_courses @Args
    $QueueExit = $LASTEXITCODE
} finally {
    $Timer.Stop()
    if ($null -eq $PreviousG0) { Remove-Item Env:\TELEGRAM_COURSES_PILOT_G0_INTERACTIVE -ErrorAction SilentlyContinue }
    else { $env:TELEGRAM_COURSES_PILOT_G0_INTERACTIVE = $PreviousG0 }
}
if ($QueueExit -ne 0) {
    Write-Host "RECOVERY585_FOURTH_FAILED_EXIT=$QueueExit; marcador e parcial preservados; sem repetição."
    exit $QueueExit
}
$Post = Invoke-Recovery585Guard -Post
$Elapsed = [int][Math]::Ceiling($Timer.Elapsed.TotalSeconds)
if ($Elapsed -le 0 -or $Elapsed -ge 1800) { throw 'RECOVERY585_FOURTH_RUNTIME_POSTCONDITION_FAILED' }
Write-Host "ELAPSED_SECONDS=$Elapsed"
Write-Host 'RECOVERY585_FOURTH_PASS; arquivo, SHA-256 local, prefixo original, attempts=4 e ausência de tentativas em 586/587 confirmados.'
Write-Host 'REMOTE_HASH_REQUIRED permaneceu ativo; a conclusão da CLI passou pelo caminho REMOTE_HASH_FULL sem downgrade.'
