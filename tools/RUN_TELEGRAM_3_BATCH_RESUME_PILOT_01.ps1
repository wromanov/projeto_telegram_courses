# Projeto Telegram 3.0 - piloto controlado e interativo, fora do contrato S9.
# Execute SOMENTE em PowerShell 5.1 nativo no ROMA_CASA; nao redirecionar stdin.
$ErrorActionPreference = 'Stop'
$Root = 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
Set-Location -LiteralPath $Root
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$Guard = Join-Path $Root 'tools\telegram_3_pilot_scope_guard.py'
$Produto = Join-Path $env:LOCALAPPDATA 'telegram_courses_product'
$Banco = Join-Path $Produto 'db\catalog.sqlite3'
$Destino = Join-Path $Produto 'downloads'
if (-not [Environment]::UserInteractive) { throw 'G0_INTERACTIVE_TTY_REQUIRED' }
& $Py -B $Guard
if ($LASTEXITCODE -ne 0) { throw 'PILOT_SCOPE_GUARD_BLOCKED' }
Write-Host ''
Write-Host 'TELEGRAM-3-BATCH-RESUME-PILOT-01 / G0'
Write-Host 'Canal autorizado: RASMOO (-1002758699600)'
Write-Host 'Escopo: Candidato de Ouro / Contagem Regressiva / 5 MP4'
Write-Host 'Limites: 128 MiB por arquivo, 512 MiB no total, 1 worker, 1 tentativa, 60 min de fila.'
Write-Host 'Integridade: prova de hash remoto integral obrigatoria, sem downgrade.'
Write-Host 'O catalogo observado foi copiado em modo somente leitura da run S9 encerrada.'
Write-Host 'O prompt de confirmacao de downloads (G4) sera apresentado depois do plano.'
$Nonce = [Guid]::NewGuid().ToString('N').Substring(0,16)
$Expected = 'APROVAR PILOTO G0 ' + $Nonce
$Approval = Read-Host ('Para autorizar somente esta execucao, digite ' + $Expected)
if ($Approval -cne $Expected) {
    Write-Host 'G0_CANCELLED'
    exit 4
}
Write-Host 'G0=PASS / HUMAN_INTERACTIVE / THIS_PROCESS_ONLY'
& $Py -B -m telegram_courses download queue `
    --channel-id -1002758699600 `
    --scope module `
    --required-module-id 46 `
    --database $Banco `
    --download-dir $Destino `
    --workers 1 `
    --attempts-per-media 1 `
    --max-media-items 5 `
    --max-single-media-bytes 134217728 `
    --max-transfer-bytes 536870912 `
    --max-runtime-seconds 3600 `
    --integrity-mode REMOTE_HASH_REQUIRED `
    --private-downloads `
    --require-full-remote-hash
exit $LASTEXITCODE
