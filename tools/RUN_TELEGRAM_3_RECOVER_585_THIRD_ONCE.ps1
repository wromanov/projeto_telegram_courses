# TELEGRAM-3-RESUME-FINAL-01: third and final authorized attempt, MP4 585 ONLY.
# Execute in native interactive Windows PowerShell 5.1; no piped input / --confirm.
$ErrorActionPreference = 'Stop'
$Root = 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
Set-Location -LiteralPath $Root
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$Guard = Join-Path $Root 'tools\telegram_3_resume_585_third_guard.py'
$Product = Join-Path $env:LOCALAPPDATA 'telegram_courses_product'
$DB = Join-Path $Product 'db\catalog.sqlite3'
$Dest = Join-Path $Product 'downloads'
$Marker = Join-Path $Product 'db\resume_final_01_recover585_third.started'
$Receipt = Join-Path $Product 'db\resume_final_01_stage1.json'
if (-not [Environment]::UserInteractive) { throw 'HUMAN_INTERACTIVE_REQUIRED' }
if (-not (Test-Path -LiteralPath $Py -PathType Leaf)) { throw 'PYTHON_ENVIRONMENT_NOT_FOUND' }
$Before = @(& $Py -B $Guard)
if ($LASTEXITCODE -ne 0) { throw 'RECOVERY585_THIRD_PREFLIGHT_BLOCKED' }
$Before | ForEach-Object { Write-Host $_ }
$DigestLine = @($Before | Where-Object { $_ -match '^PREFIX_SHA256=[a-f0-9]{64}$' })
if ($DigestLine.Count -ne 1) { throw 'PREFIX_DIGEST_PREFLIGHT_INVALID' }
$OriginalPrefixHash = $DigestLine[0].Substring(14)
Write-Host ''
Write-Host 'TELEGRAM-3 — TERCEIRA E UNICA TENTATIVA EXTRA / MIDIA 585'
Write-Host 'Canal RASMOO; Candidato de Ouro; modulo Competencias, ID 44'
Write-Host 'Preservados 6.029.312 bytes; resta baixar 170.323 bytes uteis'
Write-Host 'GetFile reserve cap=6.291.456 bytes; worker=1; tentativas da fila=1'
Write-Host 'REMOTE_HASH_REQUIRED + REMOTE_HASH_FULL; sem downgrade'
Write-Host 'Outros videos, S9 e Git fora de escopo'
Write-Host 'Ao confirmar G0, o direito a esta tentativa unica sera consumido, mesmo se G4 for cancelado.'
$Approval = Read-Host 'G0: digite SIM para esta ultima tentativa'
if ($Approval -cne 'SIM') { Write-Host 'G0_CANCELLED'; exit 4 }
# Recheck local facts after human confirmation, prior to creating one-shot marker.
$Again = @(& $Py -B $Guard)
if ($LASTEXITCODE -ne 0) { throw 'RECOVERY585_THIRD_PREFLIGHT_CHANGED' }
$AgainDigest = @($Again | Where-Object { $_ -match '^PREFIX_SHA256=[a-f0-9]{64}$' })
if ($AgainDigest.Count -ne 1 -or $AgainDigest[0].Substring(14) -cne $OriginalPrefixHash) {
    throw 'PREFIX_CHANGED_BEFORE_LAUNCH'
}
$Record = [ordered]@{
    activity = 'TELEGRAM-3-RESUME-FINAL-01'
    message_id = 585
    status = 'THIRD_ATTEMPT_STARTED'
    prefix_sha256 = $OriginalPrefixHash
    expected_bytes = 6199635
    prefix_bytes = 6029312
    started_utc = (Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json -Compress
$UTF8 = New-Object System.Text.UTF8Encoding($false)
$File = [System.IO.File]::Open($Marker, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try {
    $Bytes = $UTF8.GetBytes($Record + [Environment]::NewLine)
    $File.Write($Bytes, 0, $Bytes.Length)
    $File.Flush()
} finally { $File.Dispose() }
Write-Host 'G0=PASS; marcador one-shot criado'
$env:TELEGRAM_COURSES_PILOT_G0_INTERACTIVE = '1'
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
Write-Host 'Confira: SELECTED_MEDIA_COUNT=1, PENDING_BYTES=170323, LIMIT_CHECK_RESULT=PASS.'
Write-Host 'Confira: REMOTE_HASH_FULL. Somente no G4, digite s para executar.'
$Timer = [System.Diagnostics.Stopwatch]::StartNew()
& $Py -B -m telegram_courses @Args
$QueueExit = $LASTEXITCODE
$Timer.Stop()
if ($QueueExit -ne 0) {
    Write-Host "RECOVERY585_THIRD_FAILED_EXIT=$QueueExit; sem repeticao."
    exit $QueueExit
}
& $Py -B $Guard --post
if ($LASTEXITCODE -ne 0) { throw 'RECOVERY585_THIRD_POSTCONDITION_BLOCKED' }
$Elapsed = [int][Math]::Ceiling($Timer.Elapsed.TotalSeconds)
if ($Elapsed -le 0) { $Elapsed = 1 }
if ($Elapsed -ge 1800) { throw 'RECOVERY585_THIRD_TIME_EXCEEDED' }
$ReceiptRecord = [ordered]@{
    activity = 'TELEGRAM-3-RESUME-FINAL-01'
    wave = 1
    status = 'WAVE1_COMPLETED'
    message_id = 585
    expected_bytes = 6199635
    elapsed_seconds = $Elapsed
    recovered_once = $true
    recovered_third = $true
    total_attempts = 3
    prefix_sha256 = $OriginalPrefixHash
    completed_utc = (Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json -Compress
$ReceiptFile = [System.IO.File]::Open($Receipt, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try {
    $Data = $UTF8.GetBytes($ReceiptRecord + [Environment]::NewLine)
    $ReceiptFile.Write($Data, 0, $Data.Length)
    $ReceiptFile.Flush()
} finally { $ReceiptFile.Dispose() }
Write-Host 'RECOVERY585_THIRD_PASS. A midia 585 esta valida; 586/587 permanecem fora desta execucao.'
exit 0
