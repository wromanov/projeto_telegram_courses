# TELEGRAM-3-RESUME-FINAL-01: um processo por etapa, G0 e G4 humanos.
# PowerShell 5.1 nativo; nunca redirecionar stdin, usar -NonInteractive ou passar --confirm.
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet(1,2)]
    [int]$Etapa
)
$ErrorActionPreference = 'Stop'
$Root = 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
Set-Location -LiteralPath $Root
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$Guard = Join-Path $Root 'tools\telegram_3_resume_final_guard.py'
$Product = Join-Path $env:LOCALAPPDATA 'telegram_courses_product'
$DB = Join-Path $Product 'db\catalog.sqlite3'
$DownloadRoot = Join-Path $Product 'downloads'
$Receipt = Join-Path $Product 'db\resume_final_01_stage1.json'
$Marker = Join-Path $Product 'db\resume_final_01_wave2_started.json'
if (-not [Environment]::UserInteractive) { throw 'G0_TERMINAL_INTERATIVO_OBRIGATORIO' }
if (-not (Test-Path -LiteralPath $Py -PathType Leaf)) { throw 'PYTHON_LOCAL_AUSENTE' }
& $Py -B $Guard --wave $Etapa
if ($LASTEXITCODE -ne 0) { throw 'PILOT_PRECHECK_BLOQUEADO' }
if ($Etapa -eq 1) {
    $IDs = '585'
    $MaxItems = 1
    # Reserva por GetFile: 24 * 262144, incluindo o ultimo bloco parcial.
    $MaxTransfer = 6291456
    $AllowedSeconds = 1800
} else {
    $ReceiptState = Get-Content -LiteralPath $Receipt -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($ReceiptState.activity -cne 'TELEGRAM-3-RESUME-FINAL-01' -or
        $ReceiptState.status -cne 'WAVE1_COMPLETED' -or
        $ReceiptState.wave -ne 1 -or
        $ReceiptState.message_id -ne 585 -or
        $ReceiptState.expected_bytes -ne 6199635) { throw 'WAVE1_RECEIPT_INVALIDO' }
    $ElapsedFirst = [int]$ReceiptState.elapsed_seconds
    if ($ElapsedFirst -lt 1 -or $ElapsedFirst -ge 1800) { throw 'TEMPO_TOTAL_ESGOTADO' }
    $AllowedSeconds = 1800 - $ElapsedFirst
    $IDs = '585,586,587'
    $MaxItems = 3
    # Reserva por GetFile: (43 + 43) * 262144; nao apenas bytes uteis.
    $MaxTransfer = 22544384
}
Write-Host ''
Write-Host "TELEGRAM-3-RESUME-FINAL-01 | ETAPA $Etapa/2"
Write-Host 'Canal: RASMOO (-1002758699600)'
Write-Host 'Curso: Candidato de Ouro; modulo: Competencias (id 44)'
Write-Host 'Total global: ate 3 novos MP4, 28.463.750 bytes (bem abaixo de 256 MiB).'
Write-Host 'Worker=1; tentativas por midia=1; integridade=REMOTE_HASH_REQUIRED, sem downgrade.'
Write-Host "Teto de reservas GetFile desta etapa: $MaxTransfer bytes (nao equivale a payload)."
if ($Etapa -eq 1) {
    Write-Host 'Etapa 1: baixar SOMENTE a mensagem 585, encerrar o processo.'
} else {
    Write-Host 'Etapa 2: reconhecer 585 como ALREADY_VALID e baixar SOMENTE 586 e 587.'
}
Write-Host "Teto de tempo restante (inclui confirmacao G4): $AllowedSeconds segundos"
Write-Host 'Confirme G0 pessoalmente; a fila tambem pedira G4 para o plano fresco.'
$Nonce = [Guid]::NewGuid().ToString('N').Substring(0,16)
$Expected = "AUTORIZO G0 RESUME ETAPA $Etapa $Nonce"
Write-Host ("G0_CONFIRMATION_TOKEN=" + $Expected)
$Response = Read-Host "Digite a frase G0 exibida para esta execucao"
if ($Response -cne $Expected) { Write-Host 'G0_CANCELLED'; exit 4 }
Write-Host 'G0=PASS_HUMAN_INTERACTIVE'
# Somente este processo, depois do G0 humano: aceitar input real via DC.
# A CLI ainda pede selecao e G4; nenhum --confirm ou resposta automatica.
$env:TELEGRAM_COURSES_PILOT_G0_INTERACTIVE = '1'
if ($Etapa -eq 2) {
    $MarkerRecord = [ordered]@{
        activity = 'TELEGRAM-3-RESUME-FINAL-01'
        wave = 2
        status = 'WAVE2_STARTED'
        started_utc = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json -Compress
    $UTF8 = New-Object System.Text.UTF8Encoding($false)
    $File = [System.IO.File]::Open($Marker, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $Bytes = $UTF8.GetBytes($MarkerRecord + [Environment]::NewLine)
        $File.Write($Bytes, 0, $Bytes.Length)
        $File.Flush()
    } finally { $File.Dispose() }
}
$Args = @(
    'download', 'queue',
    '--channel-id', '-1002758699600',
    '--scope', 'module',
    '--required-module-id', '44',
    '--pilot-message-ids', $IDs,
    '--database', $DB,
    '--download-dir', $DownloadRoot,
    '--workers', '1',
    '--attempts-per-media', '1',
    '--max-media-items', [string]$MaxItems,
    '--max-single-media-bytes', '134217728',
    '--max-transfer-bytes', [string]$MaxTransfer,
    '--max-runtime-seconds', [string]$AllowedSeconds,
    '--integrity-mode', 'REMOTE_HASH_REQUIRED',
    '--private-downloads', '--require-full-remote-hash'
)
if ($Etapa -eq 2) { $Args += @('--pilot-require-already-valid-id', '585') }
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
& $Py -B -m telegram_courses @Args
$ProcessExit = $LASTEXITCODE
$Stopwatch.Stop()
if ($ProcessExit -ne 0) {
    Write-Host "PILOT_QUEUE_FAILED_EXIT=$ProcessExit - nenhuma repeticao automatica"
    exit $ProcessExit
}
& $Py -B $Guard --wave $Etapa --post
if ($LASTEXITCODE -ne 0) { throw 'PILOT_POSTCONDITION_BLOCKED' }
if ($Etapa -eq 1) {
    $Seconds = [int][math]::Ceiling($Stopwatch.Elapsed.TotalSeconds)
    if ($Seconds -le 0) { $Seconds = 1 }
    if ($Seconds -ge 1800) { throw 'TEMPO_ETAPA1_EXCEDIDO' }
    $ReceiptRecord = [ordered]@{
        activity = 'TELEGRAM-3-RESUME-FINAL-01'
        wave = 1
        status = 'WAVE1_COMPLETED'
        message_id = 585
        expected_bytes = 6199635
        elapsed_seconds = $Seconds
        completed_utc = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json -Compress
    $UTF8 = New-Object System.Text.UTF8Encoding($false)
    $File = [System.IO.File]::Open($Receipt, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $Bytes = $UTF8.GetBytes($ReceiptRecord + [Environment]::NewLine)
        $File.Write($Bytes, 0, $Bytes.Length)
        $File.Flush()
    } finally { $File.Dispose() }
    Write-Host "WAVE1_PASS. Encerrado apos UM MP4. Para retomar, executar o launcher com -Etapa 2."
} else {
    Write-Host 'RESUME_FINAL_PASS: 3/3 ALREADY_VALID, 0 pendentes, 0 tentativas repetidas.'
}
exit 0
