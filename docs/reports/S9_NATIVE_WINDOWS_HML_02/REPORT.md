# Homologação real RASMOO S9 — launcher pronto para Windows nativo

Data: 2026-11-02 (America/Sao_Paulo)

```text
ACTIVITY_ID = TELEGRAM_S9_NATIVE_WINDOWS_HML_02
PARENT = TELEGRAM_S9_RASMOO_PERFORMANCE_HML_01
ROUTING_MODE_ACTUAL = DIRECT / ROOT_ONLY
ACTIVITY_STATUS = LAUNCHER_READY / AWAITING_NATIVE_OPERATOR
ACTIVITY_COMPLETION_PERCENT = 80%
COMPLETION_BASIS = launcher and offline preparation path implemented and statically parsed; native run/G0/G4/download remain operator actions
USER_AUTHORIZATION = USER_EXPLICIT / PROCEED / REAL_DOWNLOAD_NOW / bounded first F item only
RUNTIME = NATIVE_WINDOWS_POWERSHELL_5_1 / NOT_EXECUTED_FROM_CODEX
PREFLIGHT = PASS_AS_REPORTED_BY_OPERATOR / launcher rechecks non-network conditions
PRIVATE_ROOT = PRESENT_AND_PRIVATE_AS_REPORTED / %LOCALAPPDATA%\telegram_courses\S9-HML-02
DPAPI_STATUS = SESSION_AND_CREDENTIALS_PRESENT_AS_REPORTED / launcher verifies presence+ACL without reading content
G0 = READY / NOT_YET_EXECUTED / interactive TTY required before first RPC
G4 = REQUIRED / fresh plan and limits must be approved in interactive TTY before download
DELIVERY_STATUS = no pending question to canonical chat; user explicitly authorized this activity in the current chat
TELEGRAM_RPC = 0 in this Codex thread / native launcher not run
REAL_DOWNLOAD_BYTES = 0 in this Codex thread / not yet measured
REAL_DOWNLOAD_SECONDS = NOT_MEASURED
REAL_AVERAGE_MIB_S = NOT_MEASURED
S10 = NOT_AUTHORIZED
GIT_STAGE_COMMIT_PUSH = NOT_EXECUTED
```

## Histórico do preflight anterior — superado pelas informações do operador abaixo

O teste genérico de TCP para a porta 443 expirou neste runtime. Não houve
tentativa de conexão com o Telegram. Conforme a instrução da atividade, as
tentativas de rede foram encerradas aqui; a homologação real precisa ocorrer
em uma sessão nativa do operador com conectividade permitida.

O usuário informou que o Windows nativo dispõe de 90 GB livres. A leitura de
2,82 GiB obtida pelo Codex pertence ao runtime restrito e não representa esse
host. O disco não é tratado como bloqueio para a execução nativa; o escopo
final ainda deve respeitar os limites S9 ratificados.

O venv local funciona: Python 3.14.7, Telethon 1.45.0 e SQLite 3.50.4. A
consulta não encontrou processos Python/Telegram concorrentes. O hash do
contrato S9 é
`BD89EEB0B9C76565FD2780926D50D40EC97255302B2A7DA46CE5676828F85EA2`, igual ao
valor congelado.

A configuração padrão ainda aponta o banco e os downloads para dentro do
checkout. O banco original possui arquivos SQLite associados de WAL/SHM; não
foi aberto, copiado ou migrado. A pasta de Downloads observada não atende ao
isolamento exigido. Não existe raiz privada do run no perfil observado, e os
arquivos `session.dpapi` e `credentials.dpapi` não foram encontrados. Nenhum
conteúdo de credencial ou sessão foi lido.

O supervisor S9 está presente no código e no P0 offline anterior. O fluxo
`g1` solicita G0 com nonce e TTY antes de iniciar descoberta. A fila real exige
confirmação TTY de G4; não se deve usar `--confirm`. Não existe launcher S9
pronto em `tools/`. O início do run também inicia o deadline global de uma
hora, então o run só deve ser criado depois que o preflight, a raiz privada,
o backup SQLite e o manifesto estiverem prontos.

Se a sessão continuar ausente no Windows nativo, o código atual de G1 retorna
`AUTHENTICATION_REQUIRED` ou `SESSION_INVALID`; ele não solicita login dentro
do gate G1. O comando interativo `auth` existe separadamente e faz RPC. Essa
autenticação só pode ser acionada depois de um G0 válido. Não iniciar `auth`
antes de G0, nem tratar as credenciais informadas no chat como alternativa.
Esse caminho precisa ser reconciliado localmente no operador antes de iniciar
uma fila real.

## Entrega ao chat canônico

O resumo minimizado foi submetido uma vez à ferramenta de envio e rejeitado
pela revisão automática. A razão informada foi que ownership/confiabilidade
do destino não foram reconhecidos e que o pedido não autorizava
especificamente aquele envio. Nenhuma mensagem foi entregue. Não houve retry
nem uso de transporte alternativo.
`list_threads` e `read_thread` identificaram o destino pelo título
“Projeto Telegram 3.0”; o readback posterior não mostrou mensagem nova.

## Evidências deste preflight

| Item | Resultado observado |
|---|---|
| Rede externa genérica | TCP 443 expirou no runtime Codex |
| Venv | PASS — Python 3.14.7 / Telethon 1.45.0 / SQLite 3.50.4 |
| Disco no host nativo | 90 GB livres, informado pelo operador |
| Disco visto pelo runtime Codex | 2,82 GiB; não representa o host nativo |
| Processos Python/Telegram | Nenhum observado |
| Contrato S9 | SHA-256 congelado, sem alteração |
| Banco/downloads privados | Não preparados; defaults do checkout não serão usados |
| DPAPI no perfil observado | `session.dpapi` e `credentials.dpapi` ausentes |
| G0/G4 e G1–G9 | Não executados |
| RPC, login, scan e download | Nenhum |
| Stage/commit/push | Não executados |

## Comando de preflight para Windows PowerShell nativo

Executar no Windows PowerShell 5.1 do operador, fora do processo restrito do
Codex. O comando apenas verifica runtime, conectividade genérica, disco,
concorrência, existência dos artefatos DPAPI e hash do contrato. Ele não cria
pastas, não abre o banco, não lê credenciais e não chama o Telegram. Se a
conectividade não passar, parar sem iniciar S9.

```powershell
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
Set-Location -LiteralPath $repo

if ($PSVersionTable.PSVersion -lt [version]'5.1') {
    throw 'Use Windows PowerShell 5.1.'
}

$python = Join-Path $repo '.venv\Scripts\python.exe'
$contract = Join-Path $repo 'docs\contracts\S9_RASMOO_REAL_CHANNEL_ACCEPTANCE_CONTRACT_2026-10-28.md'
$expectedHash = 'BD89EEB0B9C76565FD2780926D50D40EC97255302B2A7DA46CE5676828F85EA2'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Project venv not found.' }
$versions = & $python -B -c "import sys, sqlite3, telethon; print(sys.version.split()[0] + '|' + telethon.__version__ + '|' + sqlite3.sqlite_version)"
if ($LASTEXITCODE -ne 0) { throw 'Project venv import check failed.' }

$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $contract).Hash
$active = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(python|pythonw|telegram|telegramdesktop)$' })
$localData = [Environment]::GetFolderPath('LocalApplicationData')
$appData = Join-Path $localData 'TelegramCourses'
$privateRoot = Join-Path $appData 'S9-HML-02'
$drive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($localData))

$client = New-Object System.Net.Sockets.TcpClient
$network = 'NO_GO'
try {
    $pending = $client.BeginConnect('www.microsoft.com', 443, $null, $null)
    if ($pending.AsyncWaitHandle.WaitOne(5000, $false)) {
        $client.EndConnect($pending)
        $network = 'PASS'
    }
} catch {
    $network = 'NO_GO'
} finally {
    $client.Dispose()
}

[pscustomobject]@{
    POWERSHELL = $PSVersionTable.PSVersion.ToString()
    PYTHON_TELETHON_SQLITE = ($versions -join '')
    TCP_443 = $network
    FREE_GIB = [math]::Round($drive.AvailableFreeSpace / 1GB, 2)
    CONTRACT_HASH = if ($actualHash -eq $expectedHash) { 'PASS' } else { 'MISMATCH' }
    CONCURRENCY = if ($active.Count -eq 0) { 'NONE' } else { 'ACTIVE' }
    SESSION_DPAPI_PRESENT = [bool](Test-Path -LiteralPath (Join-Path $appData 'session.dpapi'))
    CREDENTIALS_DPAPI_PRESENT = [bool](Test-Path -LiteralPath (Join-Path $appData 'credentials.dpapi'))
    PRIVATE_ROOT_PRESENT = [bool](Test-Path -LiteralPath $privateRoot)
} | Format-List

if ($network -ne 'PASS' -or $actualHash -ne $expectedHash -or $active.Count -gt 0) {
    throw 'PREFLIGHT_NO_GO: stop here; do not start a run or contact Telegram.'
}
```

O retorno para o chat deve conter apenas os campos impressos acima. Não enviar
API ID/hash, telefone, código OTP, senha 2FA, session string, tokens, IDs
privados do canal ou conteúdo de sessão.

## Próxima ação exata

O operador executa o preflight acima em Windows PowerShell nativo. Se TCP 443
passar, prossegue localmente com criação/verificação de `state/`, `db/`,
`downloads/` e `logs/`, ACL restrita ao operador/SYSTEM, backup SQLite Online
consistente e manifesto privado RASMOO. O banco original do checkout permanece
intocado.

Antes da primeira RPC, iniciar o run com manifesto e orçamento revisados e
aprovar G0 no TTY. Se a sessão não existir, só usar o fluxo interativo seguro
de autenticação depois de um G0 válido; G1 atual não abre esse fluxo. Aprovar
G4 no TTY somente depois de conferir o plano fresco e suas caps. Sem aprovação,
parar sem executar a fila. Sem mídia M elegível, não inventar substituto.

```text
LOCAL_NON_NETWORK_PREFLIGHT = PASS / NATIVE_CONNECTIVITY = NOT_CONFIRMED
DELIVERY_STATUS = AUTO_REVIEW_REJECTED / ONE_MINIMIZED_ATTEMPT / NO_RETRY
AUTO_REVIEW_REASON = destination ownership/trust not recognized; request judged not specific to this send
PRIVATE_ROOT = NOT_CREATED
DPAPI = ABSENT_IN_OBSERVED_PROFILE / NO_SECRET_READ
G0 = NOT_REQUESTED / G4 = NOT_REQUESTED
REAL_TELEGRAM_RPC = 0 / REAL_DOWNLOAD_BYTES = 0
S9_REAL_STATUS = NOT_EXECUTED
BLOCKER = CURRENT_CODEX_RUNTIME_HAS_NO_CONFIRMED_EXTERNAL_NETWORK
NEXT_EXACT_ACTION = OPERATOR_RUNS_NATIVE_WINDOWS_POWERSHELL_PREFLIGHT
SAFE_RESUME_POINT = Preserve S9-L01..L16, frozen contract and all WIP; resume only in the operator's native Windows session.
PROJECT_STATE_RECONCILIATION = PASS
```

## Estado vigente — 2026-11-02

O operador confirmou Python 3.14.7, TCP 443 Telegram, mais de 85 GiB livres,
hash congelado do contrato S9, sessão e credenciais DPAPI presentes, ausência
de processos Python do projeto, raiz HML privada, backup SQLite isolado PASS e
`PRAGMA integrity_check = ok`. São fatos fornecidos pelo operador; o launcher
repete localmente as verificações sem iniciar rede antes de G0.

O readback do chat canônico “Projeto Telegram 3.0” confirmou a autorização
humana para DIRECT/ROOT_ONLY, a proposta offline do manifesto baseada no SQLite
e uma nova cópia SQLite consistente por execução, mantendo o banco preparado
intacto. A proposta não é aprovada ao ser gerada; o conteúdo será revisado e
aprovado somente no G0. A autorização cobre somente a primeira transferência
limitada do perfil F após G0 e G4. Não autoriza M, S10, canal inteiro, alteração
do contrato ou publicação Git.

O `$codex-task-router` foi consultado conforme solicitado e confirmou
DIRECT/ROOT_ONLY: a integração do launcher e a execução futura dependem do
mesmo fluxo nativo com gates interativos, sem ganho material de delegação.

Arquivos preparados:

- `tools/RUN_S9_NATIVE_WINDOWS_HML_02.ps1` — launcher mínimo para Windows
  PowerShell 5.1.
- `tools/s9_native_windows_hml_02.py` — preflight offline, proposta de
  manifesto, backup SQLite por execução, início tardio do deadline, sequência
  G1/G2/G3 e fila F supervisionada.

O launcher confere o hash do contrato, ACLs, caminhos/reparse points, schema e
integridade SQLite, identidade única RASMOO, amostra mínima Track/Course/Module,
manifesto, presença/ACL dos artefatos DPAPI sem revelar conteúdo e caps S9.
Quando não houver manifesto, gera a proposta privada a partir do SQLite, sem
aprovação antecipada. Exibe aliases, contagens e SHA-256; o conteúdo permanece
sem aprovação até o operador revisá-lo e confirmá-lo no G0 interativo. O
marcador estrutural exigido pelo loader congelado do S9 não constitui recibo nem
evidência do gate. Toda a preparação e validação da cópia ocorre antes de criar
o ledger e iniciar o prazo de 3.600 segundos.

G1 usa o prompt G0 com nonce no TTY antes da primeira RPC. G2 fica em 200
mensagens/120 s; G3 usa somente o banco por execução. A fila G5 usa perfil F,
um item, um worker, uma tentativa, cap agregado de 536.870.912 bytes e
`REMOTE_HASH_REQUIRED`; `--confirm` não é usado. A fila mostra tempo real e
bytes/s. O helper mede uma janela S4 aproximada por amostragem SQLite read-only
de 200 ms, registra bytes/eventos/tamanho do ledger e verifica integridade
SQLite, tamanho e SHA-256 do arquivo. O tempo exclusivo de ledger não pode ser
separado sem instrumentar S9; esse limite é registrado, não mascarado.

Validação feita aqui: análise sintática do PowerShell 5.1 e AST do Python
PASS; whitespace e `git diff --check` PASS. Nenhum teste amplo foi repetido.
Nenhum launcher, RPC ou download real foi executado neste runtime. O contrato
S9 e os módulos S9 não foram alterados.

### Comando exato — Windows PowerShell 5.1 nativo

```powershell
Set-Location -LiteralPath 'C:\Users\walac\desenvolvimento\projeto_telegram_courses'
& '.\tools\RUN_S9_NATIVE_WINDOWS_HML_02.ps1'
```

Resultado de preparação: `LAUNCHER_READY=YES`, `G0_READY=YES` (pronto para
solicitar; ainda não aprovado) e `G4_REQUIRED=YES`. A proposta do manifesto é
gerada offline e sua aprovação efetiva ocorre no prompt G0 deste run. A próxima
ação é o operador executar o comando acima; nenhuma RPC ocorre até a confirmação
G0 e nenhum payload começa até a confirmação G4 do plano fresco.

### Atualização P0 — diagnóstico do guard privado — 2026-11-02

O operador informou que o launcher nativo parou em
`PRIVATE_DIRECTORY_CHECK_FAILED`. A evidência ACL mostra owner igual ao usuário,
herança não protegida e ACEs herdadas para SYSTEM/Administradores/OWNER RIGHTS.

A condição exata está em `_verify_windows_private_directory`: o diretório só é
aceito quando `owner == current_user_sid`, `protected == True` e a DACL contém
exatamente três ACEs Allow explícitas `OICI/FILE_ALL_ACCESS` para o usuário,
SYSTEM e Administrators. Portanto, `not protected` e `entries != expected`
acionam `LEDGER_PRIVATE_DIRECTORY_UNVERIFIED`; o owner informado passa essa
parte do predicado. A exceção é propagada por `_open_private_directory_guard`.

Foi preparado no helper um reparo idempotente limitado ao root
`S9-HML-02` e às pastas diretas `db`, `state`, `runs`, `downloads` e `logs`.
Ele usa `WindowsSecurityApi` para inspecionar, aplica a mesma DACL protegida do
criador privado existente e reabre o guard S9 sem relaxá-lo. O caminho permitido
é uma lista fechada; owner divergente, reparse point, erro de API ou verificação
posterior malsucedida bloqueiam. A preparação das pastas só ocorre depois do
check DPAPI em modo somente leitura.

Há uma dependência adicional confirmada pelo código: o launcher chama
`_ProtectedSessionVault._verify_acl(..., is_directory=True)` em
`%LOCALAPPDATA%\telegram_courses`, que exige DACL protegida com ACEs explícitas
OWNER RIGHTS/SYSTEM/Administrators. A evidência do operador (herança não
protegida) falhará esse check antes do reparo HML. O launcher agora verifica
esse pré-requisito antes de mudar qualquer ACL HML. Reparar a DACL de
`telegram_courses` é necessário para a pré-validação DPAPI e pode propagar as
ACE herdadas a seus filhos; o diretório contém os artefatos DPAPI. Nenhuma
alteração foi feita nele. É necessária nova autorização humana específica antes
de aplicar essa ACL, conforme a restrição do operador. A propagação automática
por `SetNamedSecurityInfo` é descrita pela [documentação Microsoft](https://learn.microsoft.com/en-us/windows/win32/secauthz/automatic-propagation-of-inheritable-aces).

Validação offline: AST PowerShell 5.1 PASS; AST Python PASS; teste sintético da
política/DACL e forma da chamada Win32 PASS; dois testes unitários específicos
do guard PASS. Nenhum caminho HML, arquivo DPAPI ou banco foi alterado no Codex.
Nenhuma RPC, G0 ou transferência foi executada. `G0_READY` permanece pendente
até resolver a autorização do parent DPAPI e a execução nativa confirmar todos
os guards.

O relatório desta atualização P0 e a solicitação específica de autorização da
DACL parent foram enviados ao chat canônico `Projeto Telegram 3.0`; a decisão do
operador está pendente.

### Atualização após autorização — 2026-11-02

O operador respondeu `AUTORIZO ACL DPAPI PAI`. A inspeção nativa encontrou
`%LOCALAPPDATA%\telegram_courses` já com a DACL protegida exata esperada pelo
vault (owner ROMA_CASA\walac; OWNER RIGHTS, SYSTEM, Administradores). Portanto,
a DACL parent e os arquivos DPAPI não foram alterados.

Antes do reparo HML, salvei owner/SDDL e backup restaurável das ACLs dos nove
objetos existentes em
`%LOCALAPPDATA%\Temp\S9-HML-02-acl-c815368dc6e9468691800bc2c36a3c8a`.
O reparo nativo passou `PRIVATE_DIRECTORY_GUARD` e `PRIVATE_SQLITE_FILE`, mas
`_catalog_snapshot` bloqueou com `S9_SQLITE_SCHEMA_INCOMPLETE`. Não houve
manifesto, diretório/run tree por execução, cópia SQLite por run ou RPC. Restaurei
as seis DACLs HML alteradas por `SetNamedSecurityInfoW`, somente DACL, e comparei
owner, estado de proteção e SDDL contra o snapshot; todos passaram, normalizando
somente o marcador Windows auto-inherit `D:AI`. As ACLs DPAPI conferem com o
snapshot. O diretório `runs` foi criado pelo preflight, não existia no snapshot,
e permanece vazio/privado.

Consulta SQLite nativa em modo somente leitura: Python 3.14.7,
`integrity_check=ok`, `schema_migrations` contém somente versão 1, `catalog_nodes`
tem zero linhas e faltam `catalog_runs`, `catalog_unresolved_sources` e
`remote_observation_state`. Assim, a base atual não satisfaz a amostra S3 de
catálogo que o contrato S9 exige. Nenhuma migration ou flexibilização foi feita.
O último output mostrou 52.248 bytes e LastWriteTime UTC 2026-11-02 03:31:06;
não foi capturado baseline desse timestamp antes da validação, portanto não
afirmo comparação de mtime. O código abriu a base somente leitura e não escreveu
seus dados.

Estado: `ACL_DPAPI_PARENT=PASS_ALREADY_UNCHANGED`; `HML_ACL_REPAIR=PREPARED`;
`CURRENT_HML_DACL=RESTORED_TO_PREVIOUS_INHERITED_STATE`;
`LAUNCHER_PREFLIGHT=BLOCKED_SQLITE_SCHEMA_INCOMPLETE`; `NEW_RUN_DIRECTORY_GUARD=NOT_RUN`;
`G0_READY=NO`; `G4_REQUIRED=YES`; `RPC=0`; `DOWNLOAD=0`. Aguardar DB isolado S3
elegível ou orientação do operador no chat canônico antes de repetir o preflight.
