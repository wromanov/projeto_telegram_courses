# Ambiente de desenvolvimento S0

## Plataforma e ambiente

S0 foi especificada para Windows 11 x64, CPython 3.14.x padrão com GIL. Use
PowerShell 7 e o checkout existente. Não crie outro repositório para executar
estas instruções.

Resolva a raiz e os caminhos uma vez, no PowerShell aberto na raiz do projeto:

```powershell
$GitS0 = (Get-Command git -CommandType Application -ErrorAction Stop).Source
$RepoRootText = & $GitS0 rev-parse --show-toplevel
$RepoExitCode = $LASTEXITCODE
if ($RepoExitCode -ne 0) {
    throw 'repository preflight failed'
}
$RepoRoot = [IO.Path]::GetFullPath($RepoRootText.Trim())
$VenvRoot = Join-Path $RepoRoot '.venv'
$PyS0 = Join-Path $VenvRoot 'Scripts\python.exe'
$CliS0 = Join-Path $VenvRoot 'Scripts\telegram-courses.exe'
$ConstraintsPath = Join-Path $RepoRoot 'requirements\s0-resolved-win-cp314.txt'
```

Se `.venv/` já existir antes da criação, interrompa e investigue; não a reutilize
nem a remova automaticamente. O mesmo vale para `.venv-replay/`. Para criar o
ambiente aprovado, selecione o CPython 3.14 pelo launcher e siga o oracle,
fail-fast e procedimento de instalação definidos em
`docs/contracts/S0_IMPLEMENTATION_CONTRACT.md` §§8.1, 8.2 e 22.5. Eles verificam
Windows, arquitetura, GIL, caminho do executável e versões antes de prosseguir.
Não atualize pip nem acrescente dependências.

## Validar o ambiente instalado

Use sempre o interpretador absoluto de `.venv`; a ativação é opcional. Para a
validação contratual completa, invoque os comandos pelo helper
`Invoke-S0Native` do contrato §8.1 e pare no primeiro erro:

```powershell
Invoke-S0Native -Step 'DEV-TEST' -Executable $PyS0 -Arguments @('-m','pytest')
Invoke-S0Native -Step 'DEV-LINT' -Executable $PyS0 -Arguments @('-m','ruff','check','src','tests')
```

A stack base e as dependências de desenvolvimento são instaladas pelo comando
contratual `pip install -e ($RepoRoot + '[dev]')`. Após SP-01, as dependências
resolvidas ficam registradas em `requirements/s0-resolved-win-cp314.txt`.
Execute a instalação SP01-03 por `Invoke-S0Native`, conforme §22.5.1; a forma
resumida do comando acima identifica seus argumentos, não uma chamada nativa
fora do helper.
Para reproduzir, crie `.venv-replay/` com o mesmo interpretador base e instale
usando `-c $ConstraintsPath -e ($RepoRoot + '[dev]')`, conforme §22.5.2. A
validação compara versões completas; constraints não fixam hashes de artefatos.

## Smoke contratual do SP-01

No SP01-09, use o caminho absoluto do executável instalado e o helper
`Invoke-S0Native` de §8.1. Todo comando externo deste procedimento — inclusive
Python, pip, pytest, Ruff, probes, CLI e replay — passa pelo helper. Ele mantém
stdout e stderr separados, obtém `ExitCode` independentemente e interrompe no
primeiro erro; validar conteúdo de saída exclusivamente em `.stdout`. Não usar
chamada nativa direta, shell intermediária ou combinação de streams como prova
contratual. Preservar os streams capturados; para comparar a linha de saída,
normalizar CRLF para LF conforme §22.4.

```powershell
$PreviousPyDontWriteBytecode = [Environment]::GetEnvironmentVariable(
    'PYTHONDONTWRITEBYTECODE', 'Process'
)
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $SmokeResult = Invoke-S0Native `
        -Step 'SP01-09-CLI-SMOKE' `
        -Executable $CliS0 `
        -Arguments @('smoke')
    $NormalizedSmokeStdout = $SmokeResult.stdout -replace "`r`n", "`n"
    if ($NormalizedSmokeStdout -cne "telegram-courses 0.1.0 config=file log_level=INFO`n" -or
        $SmokeResult.stderr -cne '') {
        throw 'SP01 CLI smoke mismatch'
    }
} finally {
    [Environment]::SetEnvironmentVariable(
        'PYTHONDONTWRITEBYTECODE', $PreviousPyDontWriteBytecode, 'Process'
    )
}
```

Saída de sucesso esperada:

```text
telegram-courses 0.1.0 config=file log_level=INFO
```

## Uso humano da CLI fora do SP-01

Depois das validações contratuais, o usuário pode executar manualmente o
entrypoint pelo caminho absoluto. Esta chamada interativa não é evidência de
SP-01; durante o procedimento SP-01, use sempre o exemplo anterior com
`Invoke-S0Native`.

```powershell
$PreviousPyDontWriteBytecode = [Environment]::GetEnvironmentVariable(
    'PYTHONDONTWRITEBYTECODE', 'Process'
)
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $CliS0 smoke
} finally {
    [Environment]::SetEnvironmentVariable(
        'PYTHONDONTWRITEBYTECODE', $PreviousPyDontWriteBytecode, 'Process'
    )
}
```

O comando também aceita `--config PATH` e `--log-level LEVEL`. Para selecionar
configuração por ambiente, use `TELEGRAM_COURSES_CONFIG` e
`TELEGRAM_COURSES_LOG_LEVEL`. A precedência e as rejeições estão fechadas no
contrato §22.3. A ausência do arquivo default permite defaults; ausência de um
arquivo selecionado explicitamente é erro.

O smoke é local e somente leitura: não conecta ao Telegram, não cria arquivos,
logs, bancos, sessões ou diretórios. Não informe credenciais nem crie arquivos
de sessão. Para os efeitos de `PYTHONDONTWRITEBYTECODE` e a oracle de filesystem,
siga §§22.4.1 e 22.5.
