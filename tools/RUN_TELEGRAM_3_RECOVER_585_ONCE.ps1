# TELEGRAM-3-RESUME-FINAL-01 / exceptional retry of 585 only.
# PowerShell 5.1 native, human G0 and fresh CLI G4, no --confirm.
$ErrorActionPreference = 'Stop'
$Root = 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
Set-Location -LiteralPath $Root
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$Guard = Join-Path $Root 'tools\telegram_3_resume_585_once_guard.py'
$Product = Join-Path $env:LOCALAPPDATA 'telegram_courses_product'
$DB = Join-Path $Product 'db\catalog.sqlite3'
$Dest = Join-Path $Product 'downloads'
$Marker = Join-Path $Product 'db\resume_final_01_recover585_once.started'
$Receipt = Join-Path $Product 'db\resume_final_01_stage1.json'
if (-not [Environment]::UserInteractive) { throw 'HUMAN_INTERACTIVE_REQUIRED' }
if (-not (Test-Path -LiteralPath $Py -PathType Leaf)) { throw 'PYTHON_ENVIRONMENT_NOT_FOUND' }
& $Py -B $Guard
if ($LASTEXITCODE -ne 0) { throw 'RECOVERY585_PREFLIGHT_BLOCKED' }
Write-Host ''
Write-Host 'TELEGRAM-3 RECOVERY-585-ONCE (autorizacao excepcional)'
Write-Host 'RASMOO / Candidato de Ouro / Competencias / somente MP4 585'
Write-Host 'Arquivo parcial original: 6.029.312 bytes; restante util: 170.323 bytes'
Write-Host 'Teto de reservas GetFile: 6.291.456 bytes; 1 worker; UMA tentativa adicional'
Write-Host 'Prova integral de hash remoto obrigatoria; sem downgrade, sem outros videos'
Write-Host 'Uma falha encerra esta autorizacao. O .part sera preservado.'
$G0 = Read-Host 'G0: para iniciar UMA tentativa adicional, digite SIM'
if ($G0 -cne 'SIM') { Write-Host 'G0_CANCELLED'; exit 4 }
Write-Host 'G0=PASS HUMAN_APPROVED'
# Create durable one-shot marker before launching the child; no automatic retry.
$UTF8 = New-Object System.Text.UTF8Encoding($false)
$Record = [ordered]@{
    activity='TELEGRAM-3-RESUME-FINAL-01'
    message_id=585
    status='RECOVERY_ONCE_STARTED'
    started_utc=(Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json -Compress
$File = [System.IO.File]::Open($Marker,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
try {
    $Bytes = $UTF8.GetBytes($Record + [Environment]::NewLine)
    $File.Write($Bytes,0,$Bytes.Length)
    $File.Flush()
} finally { $File.Dispose() }
$env:TELEGRAM_COURSES_PILOT_G0_INTERACTIVE='1'
$Args = @(
    'download','queue',
    '--channel-id','-1002758699600',
    '--scope','module',
    '--required-module-id','44',
    '--pilot-message-ids','585',
    '--pilot-resume-585-once',
    '--database',$DB,
    '--download-dir',$Dest,
    '--workers','1',
    '--attempts-per-media','1',
    '--max-media-items','1',
    '--max-single-media-bytes','134217728',
    '--max-transfer-bytes','6291456',
    '--max-runtime-seconds','1800',
    '--integrity-mode','REMOTE_HASH_REQUIRED',
    '--private-downloads','--require-full-remote-hash'
)
Write-Host 'Modulo fixo validado automaticamente. Confira o plano fresco e confirme G4 digitando s.'
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
& $Py -B -m telegram_courses @Args
$ExitCode = $LASTEXITCODE
$Stopwatch.Stop()
if ($ExitCode -ne 0) {
    Write-Host "RECOVERY585_FAILED_EXIT=$ExitCode; sem repeticao automatica."
    exit $ExitCode
}
& $Py -B $Guard --post
if ($LASTEXITCODE -ne 0) { throw 'RECOVERY585_POSTCONDITION_BLOCKED' }
$Seconds = [int][Math]::Ceiling($Stopwatch.Elapsed.TotalSeconds)
if ($Seconds -le 0) { $Seconds = 1 }
if ($Seconds -ge 1800) { throw 'RECOVERY585_ELAPSED_EXCEEDED' }
$ReceiptRecord = [ordered]@{
    activity='TELEGRAM-3-RESUME-FINAL-01'
    wave=1
    status='WAVE1_COMPLETED'
    message_id=585
    expected_bytes=6199635
    elapsed_seconds=$Seconds
    recovered_once=$true
    total_attempts=2
    completed_utc=(Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json -Compress
$ReceiptFile = [System.IO.File]::Open($Receipt,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
try {
    $Bytes = $UTF8.GetBytes($ReceiptRecord + [Environment]::NewLine)
    $ReceiptFile.Write($Bytes,0,$Bytes.Length)
    $ReceiptFile.Flush()
} finally { $ReceiptFile.Dispose() }
Write-Host 'RECOVERY585_PASS; 585 validado, tentativa 2 contabilizada; 586/587 intactos.'
Write-Host 'Etapa 2 exige novo G0/G4 e nova execucao do launcher normal.'
exit 0
