# Safe Windows 11 entry point; strictly local, no Telegram RPC or downloads.
param(
    [ValidateSet('ajuda','smoke','catalogo','arquivos')]
    [string]$Acao = 'ajuda'
)
$ErrorActionPreference = 'Stop'
$Root = 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
Set-Location -LiteralPath $Root
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$Product = Join-Path $env:LOCALAPPDATA 'telegram_courses_product'
$DB = Join-Path $Product 'db\catalog.sqlite3'
$Destination = Join-Path $Product 'downloads'
if (-not (Test-Path -LiteralPath $Py -PathType Leaf)) { throw 'VENV_LOCAL_AUSENTE' }
switch ($Acao) {
    'smoke' {
        & $Py -B -m telegram_courses smoke
        exit $LASTEXITCODE
    }
    'catalogo' {
        if (-not (Test-Path -LiteralPath $DB -PathType Leaf)) { throw 'CATALOGO_LOCAL_AUSENTE' }
        & $Py -B -m telegram_courses catalog list --database $DB
        exit $LASTEXITCODE
    }
    'arquivos' {
        if (-not (Test-Path -LiteralPath $Destination -PathType Container)) { throw 'DIRETORIO_DOWNLOADS_AUSENTE' }
        & explorer.exe $Destination
        exit 0
    }
    default {
        Write-Host 'TELEGRAM COURSES 3.0 — operacoes locais (nenhuma RPC Telegram)'
        Write-Host 'Use -Acao smoke    : verificacao tecnica offline'
        Write-Host 'Use -Acao catalogo : visualizar catalogo local'
        Write-Host 'Use -Acao arquivos : abrir pasta com cursos ja baixados'
        Write-Host 'Downloads reais exigem plano e autorizacao especificos.'
        exit 0
    }
}
