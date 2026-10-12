# Último handoff material

```text
DOCUMENT_ROLE = LAST_HANDOFF
PROJECT_ID = projeto_telegram_courses
RECORDED_AT = 2026-10-12 / America/Sao_Paulo
HANDOFF_STATUS = S1-A_PASS / S1-B_PASS / S1-C_PASS / S1-C-OFF-01_PASS / S1-D_CLOSED / CREDENTIAL_VAULT_PASS / FULL_REGRESSION_PASS / CONTRACT_FROZEN / GOV-01_RESOLVED / S1_CLOSED / S2_CLOSED / S3_ACCEPTED / S3_CLOSED / S4_ACCEPTED / S4_CLOSED / FIRST_VERTICAL_SLICE_GATE_PASS / S5_SAFETY_LIMIT_ADDENDUM / S5_REAL_PROOF_PASS / S5_FORMAL_ACCEPTANCE_APPROVED / S5_CLOSED
```

## Handoff anterior — S5-REAL-FAILURE-DIAG-01 — 2026-10-11

A investigação read-only encontrou quatro linhas de download com
`FAILED_RETRYABLE`, `failure_category=SESSION_INVALID`, `error_details` igual à
categoria, uma tentativa, zero bytes e quatro `.part` físicos vazios. SQLite
passou em `integrity_check`, não teve erros FK. A mídia 5 concluiu com
11.649.955 bytes e SHA-256 igual ao persistido. A prova continua preservada no
`PROOF_ROOT` informado pelo usuário.

O código S5 publicava o gateway lazy antes de aguardar `restore()`. Dois workers
podiam compartilhar esse gateway parcialmente inicializado: o segundo recebia
`SESSION_INVALID` no guard anterior a qualquer pedido de entidade, mensagem ou
arquivo, depois drenava os quatro itens restantes. Timestamps SQLite colocam
as quatro falhas durante a transferência bem-sucedida. A causa é de alta
confiança, mas não há trace da execução histórica. O transcript disponível é
uma prévia anterior, encerrada sem confirmação às 18:55 locais; as linhas
SQLite foram gravadas às 19:52–19:53 locais. A exceção Telethon original não
está recuperável.

Depois de autorização do usuário, `mechanical_implementer` alterou somente
`src/telegram_courses/cli.py`: todos os workers aguardam uma única tarefa de
criação/restauração da sessão. A validação focalizada passou com harness
temporário da classe `_LazyGateway` extraída do código atual: duas tarefas,
restore bloqueado e compartilhado, zero streams antes da autenticação, ambos
streams concorrentes após liberação, sessão inválida e falha de restore
propagadas de forma sanitizada, inicialização lazy e fechamento uma vez. O
executor precisou de loop seletor local sem I/O para contornar bloqueio do
socketpair padrão; nenhum socket, Telegram, fila real ou prova real foi usado.
Harness temporário removido; nenhum teste permanente foi adicionado. Não houve
fila/download/Telegram nesta continuação e não houve ações Git. Aceite S5
permanece pendente.

```text
ACTIVITY = S5-REAL-FAILURE-DIAG-01
ACTIVITY_COMPLETION_PERCENT = 100%
STATUS = COMPLETED / FIX VALIDATED SYNTHETICALLY; REAL VALIDATION PARTIAL
ROOT_CAUSE = lazy gateway initialization race between two workers
ROOT_CAUSE_CONFIDENCE = HIGH / persisted timing and code path; no historical trace
DEFECT_CONFIRMED = YES
ERROR_DETAILS = SESSION_INVALID / sanitized category only; raw Telethon error unavailable
FAILED_MEDIA_COUNT = 4
ZERO_BYTE_PART_FILES = 4
DOWNLOADED_MEDIA = 1 / 11649955 bytes / physical SHA-256 matches SQLite
RETRY_POLICY_FINDING = one attempt correct for terminal SESSION_INVALID; S5 does not retry it
FIX = shared initialization task awaited before any stream
SYNTHETIC_CONCURRENCY_TEST = PASS / one restore; no premature streams; two streams proceed concurrently after auth
SINGLE_RESTORE_TEST = PASS
NO_PREMATURE_STREAM_TEST = PASS
INVALID_SESSION_TEST = PASS / SESSION_INVALID; no stream
RESTORE_FAILURE_TEST = PASS / GATEWAY_FAILURE; no stream
LAZY_INITIALIZATION_AND_CLOSE = PASS
TESTS = TEMPORARY_SYNTHETIC_HARNESS / PASS / removed after execution
QUEUE_EXECUTIONS = 0 / during this continuation
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PARTIAL / historical failed execution; post-fix validation pending
S5_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Await separate authorization before controlled real resumption; preserve SQLite, successful media, four `.part` files and evidence; do not deduplicate
NEXT_ACTION = Prepare a separately authorized controlled resumption; formal S5 acceptance remains pending
```

## Handoff vigente — S5-FORMAL-CLOSURE-01 — Encerramento formal da S5 — 2026-10-12

O usuário aprovou formalmente a S5 com as ressalvas documentadas e autorizou o encerramento documental sem commit ou push. S5 está CLOSED / PASS; a prova S5-REAL-PROOF-01 e o diagnóstico S5-REAL-FAILURE-DIAG-01 estão CLOSED / PASS. Os checkpoints anteriores preservam o histórico da falha inicial, diagnóstico, correção, recuperação e deduplicação.

A prova real abrange somente cinco mídias observadas (CATALOG_SCOPE = PARTIAL); não declara completude do módulo remoto ou canal. Chamadas ao gateway/GetFile não foram diretamente observadas. SQLite original, mídia, manifestos e evidências devem permanecer preservados. Nesta atividade não houve validações, execuções de fila, mudanças de código ou operações Git de escrita.

ACTIVITY = S5-FORMAL-CLOSURE-01
ACTIVITY_COMPLETION_PERCENT = 100%
STATUS = COMPLETED / DOCUMENTARY CLOSURE PASS
USER_FORMAL_APPROVAL = GRANTED
S5_FORMAL_ACCEPTANCE = APPROVED
S5_STATUS = CLOSED
S5_CLOSURE_RESULT = PASS
S5_IMPLEMENTATION = COMPLETED
S5_VALIDATION = PASS / offline 206 + 11 subtests; real proof PASS
S5_REAL_PROOF_01 = CLOSED / PASS
S5_REAL_FAILURE_DIAG_01 = CLOSED / PASS
HISTORICAL_CHECKPOINTS = PRESERVED
CATALOG_SCOPE = PARTIAL / five observed media only
GATEWAY_DOWNLOAD_CALLS = NOT_DIRECTLY_OBSERVABLE
SOURCE_CODE_CHANGES = NONE
QUEUE_EXECUTIONS = 0
SQLITE_MODIFICATIONS = NONE
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
S6_STATUS = PLANNED / NOT_STARTED
NEXT_SAFE_ACTION = Await separate direction/authorization for S6 entry review; do not start it
PROJECT_STATE_RECONCILIATION = PASS

---

## Handoff anterior — S5-REAL-PROOF-01 — Prova técnica concluída — 2026-10-12

A prova real técnica passou conforme evidência fornecida pelo usuário: quatro
downloads completos mais uma mídia válida reutilizada, total de cinco mídias
íntegras, zero falhas e zero pendências. O acumulado de 73.071.671 bytes
respeitou o limite de 83.886.080; dois workers foram observados. Diagnóstico da
concorrência encerrado e correção sintética aprovada. A recuperação real e a
deduplicação real passaram; a deduplicação ocorreu uma vez, exit 0, com cinco
itens já válidos, zero pendências e zero transferência.

As verificações informadas passaram: SHA256 vs SQLite, integridade de arquivos
e SQLite, foreign keys; nenhum `.part` permaneceu. Arquivos e hashes ficaram
inalterados. Manifest SHA-256:
`aed7c3651c90827c54d83bbd35a23ca536a6452ef523e67542d8ca0a364136d6`. Catálogo
parcial: a prova limita-se às cinco mídias observadas. Chamadas ao gateway não
foram observadas diretamente. A fonte original não deve ser alterada; preserve
SQLite e arquivos de prova.

```text
ACTIVITY = S5-REAL-PROOF-01
ACTIVITY_COMPLETION_PERCENT = 100%
STATUS = COMPLETED / TECHNICAL PROOF PASS
CONCURRENCY_DIAGNOSIS = CLOSED
SYNTHETIC_CORRECTION = PASS / APPROVED
RECOVERY = PASS / 4 complete; 1 reused
DEDUP = PASS / one execution; exit 0; 5 already valid; 0 pending; 0 transferred
ACCUMULATED_BYTES = 73071671 / AUTHORIZED_LIMIT = 83886080 / RESPECTED
WORKERS_OBSERVED = 2
REAL_PROOF_MEDIA_COUNT = 5 / INTACT
CATALOG_SCOPE = PARTIAL / only five observed media
GATEWAY_CALLS = NOT_DIRECTLY_OBSERVED
SHA256_VS_SQLITE = PASS
FILES_INTEGRITY = PASS
SQLITE_INTEGRITY = PASS
FOREIGN_KEY_CHECK = PASS
PART_FILES_REMAINING = 0
FILES_UNCHANGED = YES
HASHES_UNCHANGED = YES
MANIFEST_SHA256 = aed7c3651c90827c54d83bbd35a23ca536a6452ef523e67542d8ca0a364136d6
ORIGINAL_SOURCE = MUST_NOT_BE_ALTERED
PROOF_SQLITE_AND_FILES = PRESERVE
S5_REAL_VALIDATION = PASS / technical only
S5_FORMAL_ACCEPTANCE = PENDING / explicit user acceptance required
GIT_ACTIONS = NONE
NEXT_ACTION = Await explicit S5 formal acceptance
```

## Handoff anterior — S5-REAL-PROOF-01 preflight — 2026-10-11

O usuário autorizou uma única fila de recuperação das quatro mídias restantes
do módulo 29 e uma única fila de deduplicação condicionada à validação integral.
O preflight somente leitura passou: SQLite isolado íntegro, zero violações FK,
mídia 598 já válida com size/hash conferidos, quatro mídias 599–602 planejadas
como pendentes, sem bloqueios/exclusões, quatro `.part` vazios preservados.
Plano: cinco itens, quatro pendentes, 61.421.716 bytes esperados. O limite
restante é 72.236.125, aplicado pelo código antes de cada solicitação GetFile
com reservas compartilhadas de até 256 KiB; não houve transferência nesta
continuação. O catálogo é parcial e a CLI exige confirmação.

Este runtime não conclui nem mesmo `asyncio.run(asyncio.sleep(0))`; o comando
foi interrompido antes de fila ou Telegram. O procedimento a executar no
PowerShell funcional do usuário deve reutilizar os caminhos existentes,
validar o estado, chamar a CLI com dois workers e os caps 5/72.236.125, fazer
uma única recuperação e parar em qualquer falha. Deduplicação só após
`DOWNLOADED=5`, `PENDING=0`, `ALREADY_VALID=5`, integridade de arquivos e SQLite
PASS. A recuperação usa 72.236.125 bytes; a deduplicação usa cap separado de 1
byte. O código rejeita 0 e `None` significa sem cap; todos os tamanhos do plano
são positivos, então qualquer pendência bloqueia antes dos workers. Com plano
vazio, a CLI retorna antes de criar o gateway. A prova de deduplicação exige a
prévia vazia, mensagem explícita sem itens pendentes e inventário/hashes
idênticos depois. O procedimento usa `asyncio.run` normal no Windows e
registra hashes da SQLite fonte antes e depois sem abri-la para escrita.
Nenhum arquivo da prova foi alterado nesta preparação; não houve source code
changes nem ações Git. Aceite formal S5 segue pendente.

```text
ACTIVITY = S5-REAL-PROOF-01
ACTIVITY_COMPLETION_PERCENT = 55%
STATUS = PARTIAL / PREFLIGHT PASS; LOCAL FUNCTIONAL WINDOWS RUNTIME REQUIRED
DIAGNOSTIC_ACTIVITY = CLOSED_100_PERCENT
SYNTHETIC_FIX_VALIDATION = PASS
RESUME_PREFLIGHT = PASS_READ_ONLY
FAILED_RETRYABLE_ELIGIBILITY = PLANNER PASS / four PENDING, no DB mutation
PREVIOUS_COMPLETED_MEDIA_REUSED = YES / media 598 ALREADY_VALID
RECOVERY_QUEUE_EXECUTIONS = 0
RECOVERY_RESULT = NOT_RUN / executor cannot initialize functional asyncio event loop
PREVIOUS_TRANSFER_BYTES = 11649955
RECOVERY_TRANSFER_BYTES = NOT_RUN
CUMULATIVE_TRANSFER_BYTES = 11649955 / before recovery
CUMULATIVE_BUDGET_RESPECTED = PREFLIGHT PASS / request-level runtime accounting not yet exercised
DOWNLOADED_MEDIA = 1
FAILED_MEDIA = 4
PENDING_MEDIA = 4
WORKERS_CONFIGURED = 2
WORKERS_OBSERVED = NOT_RUN
FILES_INTEGRITY = PASS / media 598 verified; four `.part` files preserved
SHA256_VERIFICATION = PASS / media 598 hash matches SQLite
SQLITE_INTEGRITY = PASS / integrity ok; foreign keys clean
PART_FILES_REMAINING = 4
DEDUP_QUEUE_EXECUTIONS = 0
DEDUP_RESULT = NOT_RUN / conditional
DEDUP_TRANSFERRED_BYTES = NOT_RUN
SOURCE_SQLITE_UNMODIFIED = YES
SOURCE_CODE_CHANGES = NONE
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PARTIAL
S5_FORMAL_ACCEPTANCE = PENDING
NEXT_SAFE_ACTION = Run the supplied preflight-gated PowerShell procedure in the functional user runtime
```

## Handoff vigente — S5-REAL-UNBLOCK-01 Offline Closure and Module A Preview — 2026-10-11

O usuário forneceu e autorizou registrar como evidência offline: Python 3.14.7;
testes corretivos 4/4, focused S4/S5 56/56, regressão completa 206/206 + 11
subtests, Ruff e diff check PASS, todos exit 0. Nenhum teste foi repetido.

O catálogo RASMOO indicado foi copiado por SQLite Online Backup para arquivo
temporário aberto com a fonte em read-only. `integrity_check` passou e migration
004 foi aplicada somente na cópia. O planner async não retornou no executor,
inclusive com Selector event loop process-local; o processo foi interrompido
antes de apresentar resultado da CLI. Portanto, módulo, contagens, bytes,
ordem e limite permanecem sem resultado de preview. A cópia temporária não é
persistente após o encerramento do executor.

```text
ACTIVITY = S5-REAL-UNBLOCK-01 — Offline Closure and Module A Read-only Preview
ACTIVITY_COMPLETION_PERCENT = 40%
STATUS = PARTIAL
OFFLINE_VALIDATION = PASS / user-provided; not rerun
CORRECTED_TESTS = 4 PASSED
FOCUSED_S4_S5 = 56 PASSED
FULL_REGRESSION = 206 PASSED + 11 SUBTESTS
RUFF = PASS
DIFF_CHECK = PASS
ONLINE_BACKUP = PASS / isolated temp copy
MIGRATION_004 = PASS / isolated temp copy
PLANNER_PREVIEW = BLOCKED / async planner did not return in executor
MAX_MEDIA_ITEMS = 5
MAX_TRANSFER_BYTES = 83886080
WORKERS = 2 / requested preview value
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
SOURCE_SQLITE_WRITE = NO
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PENDING
S5_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Run only the read-only CLI plan preview in functional PowerShell against a fresh SQLite Online Backup; apply migration 004 only on the copy. Do not run queue.
NEXT_ACTION = Resume the module preview in functional PowerShell; do not repeat offline tests
```

## Handoff anterior — S5-REAL-UNBLOCK-01 — 2026-10-11

### Continuação corretiva

O diagnóstico read-only confirmou um `AttributeError` em `_Reservation.settle`:
o limite era lido no objeto de reserva depois de contabilizar bytes. A closure
agora captura o limite da fila. Testes refletem bytes cumulativos entre retries
e uma segunda reserva recusada; a fila bloqueia byte cap com exclusão
`UNKNOWN_SIZE`, conforme o contrato. A integração de seleção de curso testa o
fluxo sem cap. `close()` agora está declarado em `TelegramGateway`.

Ruff e `git diff --check` passaram. A tentativa focada local não encontrou a
instalação base do Python 3.14 e terminou sem resultado de testes; o Python 3.15
global não substitui o runtime fixado. Focados e regressão completa seguem
pendentes. Execute os comandos preparados no [CONTINUITY_RECORD](../CONTINUITY_RECORD.md)
em PowerShell funcional antes de qualquer preview; queue/Telegram continuam
fora da autorização.

```text
ACTIVITY_COMPLETION_PERCENT = 72%
STATUS = PARTIAL / VALIDATION PENDING
FOCUSED_TESTS = NOT_VERIFIED / Python 3.14 base runtime unavailable
FULL_REGRESSION = NOT_RUN
RUFF = PASS
DIFF_CHECK = PASS
S5_OFFLINE_VALIDATION = PENDING
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
GIT_ACTIONS = NONE
```

A correção de orçamento deixa de confiar no callback após a escrita. Cada
resposta de arquivo agora exige reserva atômica no orçamento global antes do
pedido Telethon `GetFile`. A inspeção da versão local 1.45.x confirmou o caminho
direto sem prefetch quando `request_size == chunk_size`; o adapter intercepta
cada `_request`, incluindo os retries internos de timeout/migração, e desliga
temporariamente retries RPC ocultos enquanto streams limitados estão ativos.
Recebimentos concluídos debitam o tamanho efetivo; EOF sem payload libera a
reserva; erro/cancelamento com payload incerto consome a reserva integral. A
configuração original de retries é restaurada após todos os streams.

O catálogo isolado RASMOO segue disponível e foi validado somente leitura
(`integrity_check=ok`, 1 canal, 589 nós, 26 mídias). O usuário escolheu Módulo A
com 5 aulas e 5 mídias, estimativa de 73.071.671 bytes, teto configurado de
83.886.080 bytes e 2 workers futuros. A nova prévia read-only ainda não foi
executada; o preview histórico de 30 MiB não serve como resultado do teto novo.

A única tentativa de pytest nesta atividade encerrou com 53 erros durante
fixture setup, antes de qualquer teste rodar, porque o executor negou criação
de `tmp_path` no `--basetemp` externo. Não repetir pytest aqui. Ruff e
`git diff --check` passaram depois da correção. O focused suite e a regressão
completa seguem pendentes no PowerShell funcional do usuário; o comando está
registrado no [CONTINUITY_RECORD](../CONTINUITY_RECORD.md). Nenhum acesso
Telegram, sessão, credencial, download, escrita SQLite ou operação Git ocorreu.

```text
ACTIVITY = S5-REAL-UNBLOCK-01
ACTIVITY_COMPLETION_PERCENT = 56%
STATUS = PARTIAL
ROOT_CAUSE = Budget callback ran after chunk receipt
STREAMING_REQUEST_BOUNDARY = Telethon 1.45.x GetFile request / gated before _request
CHUNK_CONTROL = request_size == chunk_size <= 256 KiB; direct path; no prefetch
PREFETCH_BEHAVIOR = NONE ON PINNED DIRECT PATH / locally inspected source
BUDGET_RESERVATION = Atomic invocation-wide per-request maximum
BUDGET_ACCOUNTING = RECEIVED plus UNCERTAIN in-flight; RESERVED separately; no double count
CONCURRENT_BUDGET_SAFETY = CODED / SYNTHETIC TEST PENDING
RETRY_BUDGET_SAFETY = CODED / RUNTIME TEST PENDING
CANCELLATION_SAFETY = UNCERTAIN REQUEST RESERVATION KEPT CONSUMED
LIMIT_ENFORCEABILITY = PENDING_VALIDATION
FOCUSED_TESTS = BLOCKED / 53 fixture setup errors; test bodies not entered
BUDGET_TESTS = NOT_RUN
FULL_REGRESSION = NOT_RUN
RUFF = PASS
DIFF_CHECK = PASS
RASMOO_CATALOG = READ_ONLY / integrity ok; 1 channel, 589 nodes, 26 media
MODULE_A_ELIGIBILITY = PREVIEW_PENDING / 5 lessons, 5 media, 73071671 expected bytes
PLANNER_PREVIEW = NOT_RUN
LIMIT_CHECK_RESULT = NOT_RUN
WORKERS = 2 / future run only
MAX_MEDIA_ITEMS = 5
MAX_TRANSFER_BYTES = 83886080
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PENDING
S5_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Run focused and full suites in PowerShell with external basetemp; then run read-only Module A plan preview. Do not run queue; real execution requires separate authorization.
```

## Handoff vigente — S5-REAL-CANDIDATE-01 — 2026-10-11

O inventário dos quatro módulos populados e o preview de download plan foram
concluídos em cópia isolada. A menor subtree de módulo observado tem 5 mídias,
5 aulas e 73.071.671 bytes (69,69 MiB), acima do teto fixo de 30 MiB. Os outros
módulos têm 6, 7 e 8 mídias e totais maiores. O preview selecionou o menor,
confirmou equivalência de escopo/ordem e retornou LIMIT_CHECK_RESULT=FAIL.
Nenhum candidato definitivo foi encontrado. A origem do catálogo continua
parcial; integridade ok e nenhum banco-fonte foi alterado.

Os limites offline de contagem, reservas concorrentes, chunks, retries e falhas
foram inspecionados no código. O orçamento compartilha reservas e conta cada
chunk antes da escrita, mas sua callback só roda depois da recepção do chunk;
um fluxo excedente pode passar até 256 KiB pela rede antes da rejeição. Isso,
mais a incompletude do catálogo e a ausência de módulo dentro do orçamento,
bloqueia qualquer prova real nesta preparação.

```text
ACTIVITY = S5-REAL-CANDIDATE-01
ACTIVITY_COMPLETION_PERCENT = 100% / preparação concluída
STATUS = BLOCKED
S5_OFFLINE_VALIDATION = PASS / user evidence: 13 focused, 199 full, 11 subtests, Ruff, diff check; not rerun
CANDIDATE_FOUND = NO
PLANNER_PREVIEW = READ_ONLY / exit 0 / selection-plan equivalence PASS / limit FAIL
WORKERS = 2 / preview configuration
MAX_MEDIA_ITEMS = 5 / exact smallest-module size
MAX_TRANSFER_BYTES = 31457280 / 30 MiB
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
SOURCE_CODE_CHANGES = NO
REAL_SQLITE_MODIFICATION = NO
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PENDING
S5_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Find a complete catalog with a full eligible module <=30 MiB, or obtain an explicit user decision changing the fixed scope/budget; close strict receive-side byte cap; then request/receive separate authorization before queue execution.
```
## Handoff histórico — S5-REAL-PREP-02 — 2026-10-11

O perfil de limites configuráveis S5 foi implementado em `cli.py`,
`s5_downloads.py` e `downloads.py`. `--max-media-items` e
`--max-transfer-bytes` são opcionais em `download plan|queue`; quando omitidos,
não criam teto fixo para downloads normais. Preview agora registra contagens,
bytes, limites e resultado; a fila reavalia a seleção antes de workers. Para o
teto byte a fila reserva o esperado de cada mídia em um orçamento compartilhado,
conta cada chunk antes da escrita e mantém bytes de falhas/retries consumidos.
Tamanho desconhecido bloqueia a execução byte-capped. Telethon valida a
identidade/tamanho anunciado e emite chunks de até 256 KiB. O contrato S5 tem
adendo delimitado; sem alteração à semântica de deduplicação S4.

O SQLite S3 fornecido foi auditado read-only, copiado por Online Backup e a
cópia passou integridade/FK. A migration 004 só foi aplicada à cópia; ela
permanece fora do repositório porque a tentativa de remoção encontrou um handle
SQLite aberto no executor. A auditoria final da origem permaneceu em 30 mensagens,
26 mídias, 589 nós, 4 unresolved e zero downloads. O S4 de referência existe e
ficou intacto. O inventário de 47 módulos ativos encontrou quatro populados,
com 5–8 mídias elegíveis cada; nenhum módulo natural satisfaz a exigência de
2–3. `planner.build()` não completou: o Python disponível trava na criação do
socketpair Proactor do Windows. Focados também ficaram bloqueados; não repetir
no sandbox. Ruff sem cache e diff check passaram.

```text
ACTIVITY = S5-REAL-PREP-02
ACTIVITY_COMPLETION_PERCENT = 88%
STATUS = PARTIAL
S3_CATALOG_AVAILABLE = YES / read-only
S4_REFERENCE_AVAILABLE = YES / untouched
CANDIDATE_FOUND = NO / no full module with 2–3 eligible media
MODULE_SELECTION = NONE
LESSON_COUNT = N/A
MEDIA_COUNT = N/A
TOTAL_EXPECTED_BYTES = N/A
PLANNER_PREVIEW = NOT_RUN / no matching candidate
ELIGIBILITY = NO NATURAL CANDIDATE
MEDIA_LIMIT_IMPLEMENTED = YES / functional test pending
BYTE_LIMIT_IMPLEMENTED = YES / functional test pending
CONCURRENT_BUDGET_SAFE = IMPLEMENTED / test blocked
RETRY_BUDGET_SAFE = IMPLEMENTED / test blocked
FOCUSED_TESTS = BLOCKED / local Python 3.14 runtime not usable
FULL_REGRESSION = NOT_RUN
RUFF = PASS
DIFF_CHECK = PASS
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
SOURCE_DATABASE_MODIFICATION = NO
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PENDING
S5_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Validate focused S4/S5 tests in functional Python 3.14 PowerShell; obtain a natural 2–3-media module or ask user to revise candidate constraint
```

Comando de retomada para PowerShell funcional; os diretórios temporários ficam
fora do repositório e o cacheprovider está desabilitado:

```powershell
$S5TestToken = [guid]::NewGuid().ToString('N')
$S5FocusedTemp = Join-Path $env:TEMP "telegram-s5-prep-focused-$S5TestToken"
$S5FullTemp = Join-Path $env:TEMP "telegram-s5-prep-full-$S5TestToken"
.\.venv\Scripts\python.exe -m pytest tests/unit/test_s5_queue_policy.py tests/integration/test_s5_download_flow.py tests/unit/test_downloads.py tests/integration/test_download_flow.py -q -p no:cacheprovider --basetemp $S5FocusedTemp
if ($LASTEXITCODE -ne 0) { throw 'Focused S4/S5 tests failed' }
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $S5FullTemp
if ($LASTEXITCODE -ne 0) { throw 'Full regression failed' }
.\.venv\Scripts\ruff.exe check src tests --no-cache
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
```

## Handoff histórico — S5-REAL-ENTRY-01 — 2026-10-11

A evidência funcional pós-correção fornecida pelo usuário foi reconciliada:
Python 3.14.7, 9 testes focados, 195 testes completos + 11 subtests, Ruff e
diff check PASS, todos com exit 0. `S5_OFFLINE_IMPLEMENTATION = COMPLETE` e
`S5_OFFLINE_VALIDATION = PASS`; nenhuma regressão foi repetida. S5 continua
`IN_PROGRESS` e o aceite formal, `PENDING`.

`data/catalog.sqlite3` existe, mas não é o catálogo RASMOO requerido: SQLite
integrity `ok`, zero nós de catálogo, cinco mídias sem aula associada, zero
linhas de download e nenhum canal com título RASMOO. Uma cópia via SQLite
Online Backup foi feita com origem `mode=ro` + `query_only=ON`; a cópia passou
integrity e foi removida. A cópia não continha módulos selecionáveis, então não
houve preview real nem candidato. O snapshot de 5 mídias corresponde ao dado
parcial antigo registrado no histórico, não à evidência RASMOO de 30 mensagens
e 26 mídias.

As opções existentes foram confirmadas em `cli.py`: `download plan|queue`,
`--database`, `--download-dir`, `--channel-id`, `--scope` e `--workers` (1–2,
padrão 2); `--confirm` é apenas de `queue`. Não há teto rígido de itens nem de
bytes pendentes. `DISK_SAFETY_MARGIN` limita espaço livre exigido, não a soma
que pode ser transferida. Antes de qualquer execução, corrigir isso em escopo
próprio: propor atualização pontual ao contrato congelado e validação no
planner/fila/CLI de `MAX_MEDIA_ITEMS=3` e `MAX_PENDING_BYTES=31457280`, sobre a
mesma seleção recém-calculada, antes de construir gateway/workers ou fazer
qualquer escrita, com testes negativos e zero efeitos colaterais. Nenhum código
ou contrato foi alterado aqui.

### PowerShell — preparação A–F

Executar A somente quando o caminho da cópia correta RASMOO for conhecido. O
caminho antigo `data/catalog.sqlite3` não serve para esta atividade. A rotina
abaixo abre a origem em leitura somente e cria a cópia isolada; não executa
migrations. Cada execução usa uma pasta exclusiva:

```powershell
$S5SourceDatabase = 'C:\caminho\para\catalogo-rasmoo.sqlite3'
$S5ChannelId = [long](Read-Host 'ID técnico confirmado do canal RASMOO')
$S5RunRoot = Join-Path $env:TEMP ('telegram-s5-real-' + [guid]::NewGuid().ToString('N'))
$S5DatabaseCopy = Join-Path $S5RunRoot 'catalog-copy.sqlite3'
$S5DownloadRoot = Join-Path $S5RunRoot 'downloads'
New-Item -ItemType Directory -Path $S5RunRoot, $S5DownloadRoot | Out-Null
$env:S5_SOURCE_DB = (Resolve-Path -LiteralPath $S5SourceDatabase).Path
$env:S5_COPY_DB = $S5DatabaseCopy
@'
import os, sqlite3
from pathlib import Path
source_path = Path(os.environ['S5_SOURCE_DB']).resolve()
source = sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)
source.execute('PRAGMA query_only=ON')
target = sqlite3.connect(os.environ['S5_COPY_DB'])
try:
    source.backup(target)
    result = target.execute('PRAGMA integrity_check').fetchone()[0]
    if result != 'ok':
        raise SystemExit('temporary copy integrity check failed')
    print('TEMP_COPY=PASS; INTEGRITY=ok')
finally:
    target.close()
    source.close()
'@ | & .\.venv\Scripts\python.exe -
if ($LASTEXITCODE -ne 0) { throw 'SQLite backup/preflight failed' }
```

**B — Preview e aprovação.** Só depois de A comprovar integridade e um módulo
naturalmente adequado, execute o plan read-only. O CLI faz a seleção contextual;
não pede node ID:

```powershell
.\.venv\Scripts\python.exe -m telegram_courses download plan --database $S5DatabaseCopy --download-dir $S5DownloadRoot --channel-id $S5ChannelId --scope module
if ($LASTEXITCODE -ne 0) { throw 'S5 plan failed' }
```

Revisar o output do plan na própria tela e prosseguir somente se houver um
módulo completo com 2–3 mídias elegíveis, `bytes pendentes <= 31457280`, sem
bloqueados/unresolved/out-of-scope e com ordem determinística. Essas condições
ainda não são protegidas pelo CLI atual; não aprovar fila antes da correção de
hard caps e da autorização específica da execução.

**C — Primeira execução (não executar nesta atividade).** Após fechar os
hard caps e receber autorização específica, o comando real existente é:

```powershell
.\.venv\Scripts\python.exe -m telegram_courses download queue --database $S5DatabaseCopy --download-dir $S5DownloadRoot --channel-id $S5ChannelId --scope module --workers 2
if ($LASTEXITCODE -ne 0) { throw 'S5 queue failed' }
```

Sem `--confirm`, o CLI pede confirmação interativa depois de recalcular e
mostrar o plano. Conferir novamente o módulo/quantidade/bytes exibidos antes de
responder. O comando não deve ser usado até a guarda rígida estar implementada.

**D — Verificação física e SQLite (não executar nesta atividade).** Rode o
mesmo `download plan` do passo B para reavaliar o módulo. O planner existente
consulta o SQLite em leitura somente e valida os arquivos finais usando path
determinístico, tamanho e SHA-256. Conferir que pendentes e bloqueados sejam
zero e os resultados estejam válidos. Os comandos abaixo registram apenas
agregados, não caminhos ou títulos:

```powershell
$S5Files = @(Get-ChildItem -LiteralPath $S5DownloadRoot -File -Recurse)
"FINAL_FILES=$($S5Files.Count)"
"PART_FILES=$(@($S5Files | Where-Object { $_.Name.EndsWith('.part', [System.StringComparison]::OrdinalIgnoreCase) }).Count)"
$env:S5_VERIFY_DB = $S5DatabaseCopy
@'
import os, sqlite3
from pathlib import Path
db = Path(os.environ['S5_VERIFY_DB']).resolve()
con = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
con.execute('PRAGMA query_only=ON')
print('INTEGRITY=' + str(con.execute('PRAGMA integrity_check').fetchone()[0]))
print('FOREIGN_KEY_VIOLATIONS=' + str(len(con.execute('PRAGMA foreign_key_check').fetchall())))
print('DOWNLOAD_ROWS=' + str(con.execute('SELECT COUNT(*) FROM downloads').fetchone()[0]))
print('DUPLICATE_MEDIA_ROWS=' + str(con.execute('SELECT COUNT(*) FROM (SELECT media_item_id FROM downloads GROUP BY media_item_id HAVING COUNT(*) > 1)').fetchone()[0]))
print('DUPLICATE_FINAL_PATHS=' + str(con.execute("SELECT COUNT(*) FROM (SELECT final_path FROM downloads WHERE state='DOWNLOADED' GROUP BY final_path HAVING COUNT(*) > 1)").fetchone()[0]))
con.close()
'@ | & .\.venv\Scripts\python.exe -
if ($LASTEXITCODE -ne 0) { throw 'Read-only SQLite checks failed' }
```

Conservar o escopo no diretório isolado e registrar contagens, não nomes de
arquivos/títulos. O planner faz a verificação física/hash por mídia ao
reconstruir o plano; as consultas acima não leem conteúdo de mensagem.

**E — Uma execução de deduplicação (não executar nesta atividade).** Repetir o
comando C exatamente uma vez, com a mesma cópia, channel, módulo, pasta e dois
workers. Revisar o plano reavaliado e confirmar somente se os hard caps forem
aplicados e todo item estiver `ALREADY_VALID`; a execução deve retornar sem
streaming ou novos arquivos.

**F — Verificação final.** Repetir o plan do passo B e as verificações do D.
Comparar as contagens antes/depois: zero novas transferências, zero novos
arquivos/downloads, nenhum duplicado e nenhum `.part`; integridade, tamanho e
SHA-256 continuam válidos. Qualquer diferença interrompe o experimento.

Não houve Telegram, gateway, sessão, credenciais, streaming, download, migration,
escrita na origem ou ação Git nesta atividade. O próximo passo é localizar a
cópia RASMOO correta e fechar o bloqueio dos hard caps; só então repetir A/B.
O restante da preparação e os resultados estão em
[CONTINUITY_RECORD](../CONTINUITY_RECORD.md) e [PROJECT_STATE](../PROJECT_STATE.md).

```text
ACTIVITY = S5-REAL-ENTRY-01
ACTIVITY_COMPLETION_PERCENT = 88%
STATUS = PARTIAL / REAL CATALOG AND HARD-CAP BLOCKERS
S5_OFFLINE_IMPLEMENTATION = COMPLETE
S5_OFFLINE_VALIDATION = PASS / 9 focused; 195 full + 11 subtests
CATALOG_AVAILABLE = FILE PRESENT / WRONG SNAPSHOT; NO RASMOO COURSE CATALOG
SQLITE_SOURCE_READ_ONLY = PASS
TEMPORARY_COPY = BACKUP AND INTEGRITY PASS / REMOVED
CANDIDATE_FOUND = NO / BLOCKED
SELECTION_SCOPE = NONE
LESSON_COUNT = N/A
MEDIA_COUNT = N/A
TOTAL_EXPECTED_BYTES = N/A
ELIGIBILITY_CHECK = BLOCKED / ZERO CATALOG NODES
PLANNER_PREVIEW = NOT_RUN
PENDING_COUNT = N/A
EXCLUDED_COUNT = N/A
ALREADY_VALID_COUNT = N/A
WORKERS_PROPOSED = 2
ITEM_LIMIT_ENFORCEABLE = NO / HARD GUARD REQUIRED
BYTE_LIMIT_ENFORCEABLE = NO / HARD GUARD REQUIRED
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
GIT_ACTIONS = NONE
MATERIAL_BLOCKERS = CORRECT RASMOO SQLITE SOURCE; HARD ITEM/BYTE CAPS ABSENT
S5_REAL_VALIDATION = PENDING
S5_FORMAL_ACCEPTANCE = PENDING
FINAL_VERDICT = PARTIAL / PREPARATION RECORDED; PREVIEW AND EXECUTION BLOCKED
NEXT_ACTION = Obtain the correct catalog and approve a narrow hard-cap contract/CLI correction before any real queue run
```

## Handoff anterior — S5-FIX-01-CONTINUATION — 2026-10-11

A falha remanescente era um defeito S5: a linhagem física usada pelo planner
divergia daquela retornada pelo seletor S4, produzindo `DOWNLOAD_ROOT_CHANGED`
para arquivos válidos. O planner foi alinhado ao S4 vigente, preservando a
ancestralidade completa para seleção/ordem. A expectativa de dois outcomes
`ALREADY_VALID` foi mantida; a fila já suportava esses outcomes sem enfileirar
itens válidos. O retorno sem pendências passou também a emitir progresso
agregado. Nenhuma mudança no Downloader S4 ou nos contratos nesta atividade.

Os testes agora cobrem execução/reexecução de módulo e curso, arquivos,
hashes, tamanhos, SQLite e identidades sem duplicação, ausência de `.part`,
zero novas chamadas/tarefas/tentativas/bytes e resumo coerente. A evidência e
os limites da sonda síncrona PASS estão em
[CONTINUITY_RECORD](../CONTINUITY_RECORD.md); pytest foi bloqueado no setup
temporário em uma única tentativa. Ruff completo sem cache e diff check PASS.
S5 offline validation e aceite permanecem PENDING; progresso desta atividade
88% / PARTIAL. A regressão anterior fornecida pelo usuário tinha uma falha.

Retomar em PowerShell funcional no root do repositório. Use um token novo
por execução para evitar reutilização/limpeza de diretórios temporários antigos.
Não há Telegram ou banco real nos comandos abaixo:

```powershell
$s5RunToken = [guid]::NewGuid().ToString('N').Substring(0, 8)
$s5FocusedTemp = Join-Path $env:TEMP "telegram-s5-focused-$s5RunToken"
$s5FullTemp = Join-Path $env:TEMP "telegram-s5-full-$s5RunToken"
.\.venv\Scripts\python.exe -m pytest tests/unit/test_s5_queue_policy.py tests/integration/test_s5_download_flow.py tests/unit/test_downloads.py tests/integration/test_download_flow.py -q -p no:cacheprovider --basetemp $s5FocusedTemp
if ($LASTEXITCODE -ne 0) { throw 'Focused S4/S5 tests failed' }
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $s5FullTemp
if ($LASTEXITCODE -ne 0) { throw 'Full regression failed' }
.\.venv\Scripts\ruff.exe check src tests --no-cache
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Diff check failed' }
```

Reconciliar os resultados em [PROJECT_STATE](../PROJECT_STATE.md) antes de
qualquer validação/aceite S5. ROADMAP/SPRINTS ainda contêm o status anterior de
S5, registrado como defasagem no estado. HEAD `e1e9f734e1cff0e105ab2135b7b09090465e2ac8`
e branch `work/s0-bootstrap` preservados; sem staging, commit ou push.

## Handoff anterior — S5-IMPL-01 — 2026-10-11

O contrato [S5 Course Selection, Download Planner and Queue](../../contracts/S5_COURSE_SELECTION_PLANNER_QUEUE_CONTRACT.md)
está APPROVED / FROZEN. O HEAD permanece
`e1e9f734e1cff0e105ab2135b7b09090465e2ac8`, branch `work/s0-bootstrap`; as
alterações estão no worktree, sem staging/commit/push.

A implementação offline inclui seleção contextual, planner determinístico e
somente leitura, execução via S4, até dois workers, três tentativas por mídia,
FloodWait com duração e teto cumulativo de 120 segundos, preflight/recheck de
disco, progresso Rich e uma integração sintética. Ruff e diff check passaram.
Pytest ficou bloqueado no executor Windows sandbox durante setup de temp e
execução async/aiosqlite; interrompido sem tratar como falha de código. Full
pytest não foi executado; aceite formal permanece pendente.

```text
ACTIVITY = S5-IMPL-01
ACTIVITY_COMPLETION_PERCENT = 76%
STATUS = PARTIAL / IMPLEMENTATION PRESENT; TEST EXECUTION BLOCKED
CONTRACT_STATUS = APPROVED / FROZEN
COURSE_MODULE_LESSON_SELECTION = IMPLEMENTED / OFFLINE TEST PENDING
DOWNLOAD_PLANNER = IMPLEMENTED / READ-ONLY
QUEUE = IMPLEMENTED / EPHEMERAL / S4 REUSE
WORKER_CONCURRENCY = DEFAULT 2 / ALLOWED 1..2
RETRY_POLICY = MAX 3 ATTEMPTS INCLUDING INITIAL
FLOODWAIT = retry_after_seconds PRESERVED / 120-SECOND CUMULATIVE CAP
DISK_SAFETY = MAX(1 GiB, 10% PENDING BYTES)
SQLITE_PERSISTENCE = REUSE S4 / NO QUEUE MIGRATION
RUFF = PASS
DIFF_CHECK = PASS
FOCUSED_TESTS = BLOCKED / SANDBOX TEMP AND ASYNCIO-AIOSQLITE
FULL_PYTEST = NOT_RUN
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = NONE
GIT_ACTIONS = NONE
S5_FORMAL_ACCEPTANCE = PENDING
S5_REAL_VALIDATION = NOT_AUTHORIZED
SAFE_RESUME_POINT = Run focused integration and full pytest from functional PowerShell with external basetemp and cacheprovider disabled; reconcile results before formal acceptance
```

## Handoff anterior — S5-ENTRY-01 — 2026-10-10

O checkpoint de preparação contratual continua abaixo para histórico. O
contrato foi posteriormente congelado e a implementação autorizada pela
instrução explícita S5-IMPL-01.

## Handoff anterior — S4-CLOSE-01 Formal Acceptance and Publication — 2026-10-10

S4 formalmente ACCEPTED / CLOSED; `FIRST_VERTICAL_SLICE_GATE = PASS`. A
regressão offline informada pelo usuário passou: 19 testes focados, 186 testes
completos e 11 subtests; Ruff e `git diff --check` também passaram. A prova real
cobriu uma mídia DOCUMENT de Lesson, 6.199.635 bytes, arquivo íntegro e
SHA-256 correspondente ao registro SQLite isolado. A segunda invocação retornou
`ALREADY_DOWNLOADED`, sem progresso de transferência ou duplicação. O aceite
continua limitado a uma mídia; fila é S5, resume por offset S6, sync incremental
S7 e validação integrada abrangente no canal RASMOO S9.

S1-B — Offline Authentication Flow & Telegram Gateway foi concluída após S1-A.
O modelo de autenticação, gateway, adapter Telethon, reutilização da sessão,
OTP/2FA e CLI passaram em testes offline. A suíte completa terminou com 50
passed e 8 subtests passed; Ruff passou. A regressão S1-A de DPAPI/ACL passou.
No checkpoint S1-B, nenhuma conexão Telegram, sessão ou credencial real foi
usada. S1 continua `IN_PROGRESS`; S1-B `PASS` não conclui a Sprint. O
fechamento anterior da S0 e seu replay permanecem históricos em
[PROJECT_STATE](../PROJECT_STATE.md) e
[SP01_STACK_WINDOWS](../../engineering/evidence/SP01_STACK_WINDOWS.md).

S1-C e S1-C-OFF-01 estão `PASS`. A tentativa anterior que falhou permanece
histórica e S1 continua `IN_PROGRESS`, pois descoberta/seleção de canais não
foi implementada nem validada. A sequência de evidências e seus limites de
verificação independente estão em [PROJECT_STATE](../PROJECT_STATE.md).

Na retomada, comece por [START_HERE](../START_HERE.md), confirme Git em runtime
e resolva authorities pelo [ACTIVE_AUTHORITY_MAP](../ACTIVE_AUTHORITY_MAP.md).
S1-TEST-01 está `BLOCKED`: collection passou, mas o teste focado e uma sonda
mínima de asyncio travaram na criação do loop Proactor local; revalidação segue
`PENDING`. O mecanismo imediato e a stack sanitizada estão em
[PROJECT_STATE](../PROJECT_STATE.md) e no
[relatório S1-TEST-01](../../reports/S1_TEST_01_PYTEST_ENVIRONMENT_DIAGNOSIS_2026-10-08.md).
O Entry Review foi informado como PASS pelo pedido subsequente, que autorizou
o draft arquitetural S1-D. O draft foi entregue; o safe resume corrente está em
[PROJECT_STATE](../PROJECT_STATE.md) e aponta para revisão das decisões OPEN de
[S1-D](../../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md), ainda
NOT_APPROVED / NOT_FROZEN. A implementação S1-D ainda não começou. Nenhuma
implementação, descoberta real ou acesso ao conteúdo de canais está autorizado. Os contratos
S1-B e S0 continuam congelados; a `.venv-replay` permanece local e ignorada.
A autorização Git de S1-GIT-01 expirou após o checkpoint publicado em
`e947406dbcab8ef593123f079daa279903805d2c`; esta reconciliação não executou
operações Git nem alterou código de aplicação ou testes.

Em 2026-10-08, DEC-S1D-01/02 foram aprovadas e registradas em
[APPROVALS_AND_DECISIONS](../../governance/APPROVALS_AND_DECISIONS.md). O draft
foi reconciliado: payload incidental permitido com invariantes de não
processamento/exposição/persistência/logging pela aplicação; broadcast e
megagroups/supergroups elegíveis; restore-only fechado por reuso do gateway.
O antigo broadcast-only está superseded e `FUT-CHDISC-01` não foi criado.
Permanecem OPEN limites numéricos, perfil de updates e GOV-01. A decisão não
aprova nem congela o contrato e não autoriza implementação, conexão ou pytest.
O detalhe e safe resume point atualizado ficam em [PROJECT_STATE](../PROJECT_STATE.md).

## Evidência e retomada

Retomada OPEN-04 em 2026-10-08: o precheck local fora da restrição passou,
mas a única prova sintética não retornou trace e foi interrompida após
espera delimitada. GET_DIFFERENCE_COUNT permanece NOT_MEASURED; solução
sustentável por API pública não foi demonstrada. Sob MAX_PROOF_ATTEMPTS=1,
a exploração técnica desta atividade terminou. A próxima ação é uma decisão
arquitetural humana explícita, sem autorização automática para receber o
payload de GetDifference. Ver o [relatório atualizado](../../reports/S1D_OPEN04_OFFLINE_FEASIBILITY_2026-10-08.md)
e [PROJECT_STATE](../PROJECT_STATE.md). Contrato em draft; OPEN-03,
GOV-01 e pytest pendentes.

O handoff anterior foi OPEN-04 Offline Feasibility Proof:
BLOCKED_ENVIRONMENT / NOT_DEMONSTRATED, 76%. Selector isolado também falhou em
socketpair/accept; import Telethon 1.45.0 passou. Sem request trace e sem
mecanismo público suficiente identificado para a StringSession/gateway atuais.
Ver [relatório OPEN-04](../../reports/S1D_OPEN04_OFFLINE_FEASIBILITY_2026-10-08.md)
e o safe resume em [PROJECT_STATE](../PROJECT_STATE.md). Não repetir sondas
bloqueadas; recuperação delimitada do executor e eventual revisão arquitetural
exigem escopo próprio. OPEN-04 permanece aberto; draft e gates preservados.

A evidência adjudicada, o histórico integral das tentativas, os invariantes de
segurança e os limites da verificação independente estão em
[PROJECT_STATE](../PROJECT_STATE.md). O preflight inicialmente bloqueado e a
autorização exercida são fatos históricos; a autorização está esgotada.

## Handoff vigente — DEC-S1D-03 Documentation & Reconciliation

DEC-S1D-03 está `APPROVED / D_PLUS_C`. O processamento interno incidental de
`updates.GetDifference` e `updates.GetChannelDifference` está permitido somente
no lifecycle delimitado de descoberta S1-D, inclusive inicialização e loop de
updates. `PROVE_ZERO_GET_DIFFERENCE` foi superseded. Conteúdo incidental segue
proibido para processamento, persistência e exposição pela aplicação; zero RPC,
ausência de mensagens e apagamento seguro em memória não são garantidos.

OPEN-04_ARCHITECTURAL_DECISION = RESOLVED_BY_DEC-S1D-03
OPEN-04_TECHNICAL_VALIDATION = PENDING
OPEN-03 = PENDING_MEASUREMENT
GOV-01 = UNRESOLVED
FULL_PYTEST = PENDING_REVALIDATION
DEC-S1D-01/02 = PRESERVED
CONTRACT = DRAFT / NOT_APPROVED / NOT_FROZEN
S1D_DOR = NOT_PASS
IMPLEMENTATION = NOT_STARTED / NOT_AUTHORIZED

Retomar por [PROJECT_STATE](../PROJECT_STATE.md) e seção 18 do
[contrato S1-D](../../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md).
A implementação e o contrato foram aprovados posteriormente pelo usuário em
2026-10-09; este handoff vigente é atualizado ao final do documento.

## Handoff vigente — S1-D implementação offline, 2026-10-09

O usuário aprovou o contrato e o baseline numérico S1-D e autorizou a
implementação. O fluxo está implementado e a validação offline passou:
collection 96, focused 41 passed, FULL_PYTEST 96 passed + 8 subtests em
158,55 s (exit 0, sem timeout externo) e Ruff PASS, usando PowerShell local
independente. O probe de socketpair/asyncio passou no mesmo contexto. Não houve
acesso Telegram, sessão/credenciais ou publicação Git. O contrato segue
NOT_FROZEN por GOV-01; a aceitação aguarda calibração operacional e validação
real delimitada com autorização específica. S1 continua IN_PROGRESS.

Retomar por [PROJECT_STATE](../PROJECT_STATE.md) e §20 do
[contrato S1-D](../../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md).
Não repetir a suíte sem nova causa; a última execução completa já passou.

## Handoff anterior — S1-D validação real bloqueada no precheck, 2026-10-09

O usuário autorizou uma única rodada real de descoberta/calibração. O precheck
confirmou que o artefato DPAPI esperado e as variáveis locais `TELEGRAM_API_ID`
e `TELEGRAM_API_HASH` não estão disponíveis. A CLI não foi invocada; não houve
conexão, login, descoberta ou ação remota. Não iniciar login: disponibilizar a
sessão protegida válida e as credenciais no ambiente local e então retomar a
mesma autorização. GOV-01 continua bloqueando freeze, sem waiver. Evidência:
[relatório S1-D real](../../reports/S1D_REAL_DISCOVERY_VALIDATION_2026-10-09.md);
estado corrente e safe resume em [PROJECT_STATE](../PROJECT_STATE.md).

## Handoff anterior — correção offline S1-D, 2026-10-09

O usuário informou que uma primeira chamada real pediu 100 diálogos e recebeu
101, resultando em `ADAPTER_FAILURE` antes da listagem. O caminho foi rastreado:
o adapter lançava uma falha de projeto ao rejeitar o tamanho da resposta, antes
da conversão/classificação/offset; não havia exceção original Telethon. O patch
aceita excedente da primeira página apenas quando quantidade suficiente de
linhas vem marcada como fixada, mantendo contagem de cada linha no teto bruto e
mantendo 100 como limite solicitado por chamada. Foram adicionados testes para
adapter, teto bruto e CLI com objetos Telethon sintéticos. Ruff PASS; pytest
naquela atividade a coleta 109 passou, mas a execução ficou bloqueada no
executor restrito porque até `asyncio.run(asyncio.sleep(0))` pendurava. Essa
condição foi posteriormente superada ao executar no PowerShell local autorizado;
nenhuma conexão Telegram ocorreu. Veja o novo handoff vigente.

## Handoff vigente — S1-D Telegram API Credentials Vault, 2026-10-09

A implementação adicionou o vault em
`%LOCALAPPDATA%\telegram_courses\credentials.dpapi`, separado da sessão,
reutilizando DPAPI CurrentUser e ACLs existentes. A gravação é protegida,
atômica e recusa sobrescrever um vault existente. `credentials setup` solicita
API ID e oculta API HASH; `credentials status` informa somente configuração e
disponibilidade. O par completo de variáveis de ambiente tem precedência; pares
incompletos falham sem combinação com o vault. Os comandos auth e channels
permanecem integrados ao fluxo existente.

Evidência offline sintética: focused 29 passed + 11 subtests; DPAPI Windows
CurrentUser integration 1 passed; full pytest 110 passed + 11 subtests em
169,05 s; Ruff PASS. Não houve leitura de segredos reais, abertura da sessão
DPAPI real, configuração real ou rede Telegram. O resultado anterior
`ADAPTER_FAILURE / 1 page requested / 1 received / 101 raw dialogs` foi
preservado e não é corrigido por esta atividade. DEC-S1D-01/02/03 e OPEN-03 não
foram alteradas; GOV-01 ainda impede freeze.

Próximo passo do usuário: executar localmente
`telegram-courses credentials setup` e depois
`telegram-courses credentials status`. Após disponibilidade positiva, confirmar
uma sessão protegida válida e retomar a única validação delimitada já
autorizada. Não executar login. Estado completo e safe resume point em
[PROJECT_STATE](../PROJECT_STATE.md); relatório em
[S1D_CREDENTIALS_VAULT_2026-10-09](../../reports/S1D_CREDENTIALS_VAULT_2026-10-09.md).

## Handoff vigente — S1-D Consolidated Checkpoint, 2026-10-09

Este checkpoint supersede os próximos passos e status correntes dos handoffs
anteriores; eles permanecem como histórico. S1-A/B/C = PASS. S1-D =
`IMPLEMENTED / REAL_FUNCTIONAL_PASS / FINAL_ACCEPTANCE_PENDING`; CREDENTIAL_VAULT,
REAL_DISCOVERY, BROADCAST_DISCOVERY, MEGAGROUP_DISCOVERY e LOCAL_SELECTION =
PASS. A correção de `ADAPTER_FAILURE` foi validada em cenário real. Estes
resultados são os fornecidos pelo usuário nesta atividade. S1-D não está CLOSED.

DEC-S1D-01/02/03 e OPEN-03 = APPROVED. CONTRACT_FREEZE = NOT_CONFIRMED;
GOV-01 = EXTERNAL_DEPENDENCY.

Última regressão informada: 109 passed, 1 failed, 11 subtests passed em
183.63s. `FULL_REGRESSION=NOT_PASS`. Somente as evidências existentes foram
examinadas; nelas não se identifica arquivo, teste, mensagem nem causa da
falha. Causa = UNKNOWN. Não reexecutar a suíte nesta atividade.

Próxima melhoria funcional aprovada para a CLI, ainda NÃO IMPLEMENTADA:
apresentar canais numa lista numerada e aceitar o índice, mantendo o
`telegram_chat_id` estável como identidade interna; oferecer Q para cancelar;
rejeitar índice inválido; não fazer nova consulta Telegram durante a escolha;
não realizar ações remotas; cobrir com testes offline.

SAFE_RESUME_POINT = S1-D — Regression Fix + CLI Numeric Selection.
NEXT_ACTIONS = (1) identificar a falha usando evidência disponível na próxima
atividade; (2) corrigir o teste/problema confirmado; (3) implementar a seleção
numérica aprovada; (4) executar testes focados e regressão; (5) reavaliar o
aceite final de S1-D. Validação real adicional somente se necessária e
autorizada. Não iniciar S2 antecipadamente.

Commit principal `6ffe1e8fbe2e483055e28ae43021fda9426e9ff5`
(`feat(s1): add channel discovery and credentials vault`) contém os 26 arquivos
do checkpoint. Após uma rejeição inicial do auto-review, o usuário autorizou
explicitamente o destino `https://github.com/wromanov/projeto_telegram_courses.git`,
branch `work/s0-bootstrap`, e o payload deste checkpoint. Este registro foi
atualizado antes da tentativa de push autorizada; consultar o estado Git em
runtime para confirmar a publicação. Credenciais e sessão DPAPI permanecem
locais e não devem ser copiadas entre computadores.

## Handoff vigente — S1-D Regression Fix + CLI Numeric Selection, 2026-10-09

Este registro supersede o próximo passo do checkpoint consolidado anterior.
`tests/unit/test_auth.py::test_credentials_are_environment_only_and_validated`
falhava com `DID NOT RAISE ConfigurationError`: o ambiente vazio acionava o
fallback para um vault DPAPI configurado. A chamada de teste pré-correção leu
e descriptografou o vault local; nenhum valor foi exibido/logado e a sessão
DPAPI não foi acessada. O teste agora injeta um vault sintético vazio.

A CLI apresenta canais numerados em ordem; a escolha por índice é somente
local e resolve para o `telegram_chat_id` existente. O ID completo continua
compatível; ID parcial, entrada inválida e índice fora do intervalo falham;
vazio/Q cancela. Discovery `PARTIAL` continua selecionável. Não há nova
consulta durante a escolha, e o gateway já está fechado. A melhoria está
offline-validada.

Validação: focused regression 3 passed; focused CLI 15 passed; full pytest 121
passed e 11 subtests em 184.34s; Ruff PASS; `git diff --check` PASS. A suíte
conclusiva usou PowerShell local funcional e Python 3.14.7, pois o executor
isolado bloqueou a inicialização Proactor/socketpair. Nenhuma conexão Telegram
foi feita.

Os resultados técnicos passaram, mas a atividade fica `PARTIAL` porque o teste
pré-correção leu/descriptografou o vault local contra a restrição do pedido.
Nenhum valor foi exibido ou registrado. A revisão do incidente e os critérios
de aceite permanecem pendentes. S1-D permanece `IMPLEMENTED /
REAL_FUNCTIONAL_PASS / FINAL_ACCEPTANCE_PENDING`; não declarar CLOSED.
DEC-S1D-01/02/03, OPEN-03 e GOV-01 permanecem inalterados. Não houve Git
publication. Próximo passo: revisar a resposta ao incidente e os critérios de
aceite, sem inferir autorização para remediação, novo acesso Telegram, freeze,
publicação ou início de S2. Estado único:
[PROJECT_STATE](../PROJECT_STATE.md). Evidência:
[S1D regression and CLI report](../../reports/S1D_REGRESSION_CLI_NUMERIC_SELECTION_2026-10-09.md).

## Handoff vigente — S1-D Credential Isolation Review & Final Acceptance, 2026-10-09

Incidente anterior revisado: o teste de auth passou `{}` a
`load_telegram_credentials`; sem par na mapping, `config.py` chamou o
CredentialVault padrão, que leu/descriptografou `credentials.dpapi` pelo
`_ProtectedCredentialsVault` / `_ProtectedSessionVault._load`. Nenhum valor
constou no output/erro capturado; o processo de teste materializou plaintext
em memória e terminou. Não há evidência de log/export. Crash dumps e telemetria
externa não foram forensicamente verificados. Nenhum vault foi consultado nesta
atividade.

Isolamento global adicionado em `tests/conftest.py`: cada teste recebe
`LOCALAPPDATA` sob pytest `tmp_path`; vars de credenciais/configuração são
removidas. O unittest que substitui todo o ambiente agora também define
storage temporário. Testes de regressão garantem que as resoluções padrão de
credential/session apontam para pytest temp; usam vault/API sintéticos e não
abrem storage real. A mudança vale somente durante pytest.

Validação final: focused 42 passed + 11 subtests; full pytest 123 passed + 11
subtests em 165.76s; Ruff PASS; `git diff --check` PASS. Sem acesso Telegram,
vault ou sessão nesta atividade. Estado e detalhes em
[PROJECT_STATE](../PROJECT_STATE.md) e [CONTINUITY_RECORD](../CONTINUITY_RECORD.md).

## Calibração operacional S1-D — checkpoint de 2026-10-09

A busca em evidências anteriores não encontrou medições suficientes. O primeiro
evento real foi `ADAPTER_FAILURE` (1 página solicitada/recebida; 101 diálogos).
O sucesso funcional posterior reportado não inclui durações, contagens,
completude ou cobertura observada.

Telemetria monotônica e sanitizada está pronta e passou testes focados (43),
pytest completo (126 passed, 11 subtests), Ruff e diff check. A linha
`S1D_CALIBRATION` registra duração da operação, restore, descoberta e cleanup,
contagens, budgets, resultado e stop reason. Nenhuma conexão foi feita nesta
atividade.

```text
S1D_CALIBRATION_INSTRUMENTATION = READY
S1D_OPERATIONAL_CALIBRATION = NOT_MEASURED
S1D_FINAL_ACCEPTANCE = PENDING_REAL_OPERATIONAL_MEASUREMENTS
REAL_TELEGRAM_ACCESS = NO
```

Uma nova conexão requer autorização específica. Após autorização, executar na
raiz do repositório: `\.venv\Scripts\telegram-courses.exe channels`. Preservar
somente a linha `S1D_CALIBRATION`; a saída da CLI contém metadados de canais e
não deve ser compartilhada. Relatório: [S1-D calibration review](../../reports/S1D_REAL_DISCOVERY_VALIDATION_2026-10-09.md).

**S1-D não pode ser formalmente aceita ainda.** AC-01..12 offline e regressão
PASS; discovery e seleção por ID real constam como `PASS_USER_REPORTED`. O
contrato exige também calibração operacional; os registros disponíveis ainda
marcam tempos/contadores/cobertura como `NOT_MEASURED`. Procurar evidência
sanitizada da execução já feita. Nova calibração exige autorização específica;
nenhuma conexão Telegram está autorizada por este handoff. Não fechar S1-D,
alterar contrato, publicar Git ou iniciar S2.

## Handoff vigente — S1-D Final Acceptance & Consolidated Checkpoint, 2026-10-09

O usuário forneceu linha de calibração sanitizada: operation 2.809485s, restore
0.957923s, discovery 1.315603s, cleanup 0.001170s/COMPLETE; 4 páginas
solicitadas e recebidas; 313 diálogos brutos; budgets 100 por página, 1000
brutos, 20 páginas, 120s operação, 10s cleanup; outcome COMPLETE, sem stop
reason/failure. Real discovery, broadcast, megagroup e escolha local PASS; a
opção `69` selecionou o `telegram_chat_id` esperado. Nenhum download/scanner.

```text
FUNCTIONAL_ACCEPTANCE = PASS / AC-01..12 offline plus real functional/calibration evidence
CONTRACT_FREEZE = BLOCKED_BY_GOV01
FORMAL_CLOSURE = BLOCKED_BY_GOV01 / DO NOT MARK CLOSED
DEC-S1D-01/02/03 = APPROVED / PRESERVED
OPEN-03 = APPROVED / calibrated within budgets
FULL_PYTEST = PASS / 126 passed, 11 subtests, 167.64s
RUFF = PASS / GIT_DIFF_CHECK = PASS
CREDENTIAL_VAULT = PASS / PYTEST_CREDENTIAL_ISOLATION = PASS
INCIDENT = prior accidental credential-vault read and residual risk preserved; no new evidence, do not reopen
REAL_TELEGRAM_ACCESS_FOR_VALIDATION = YES / user-provided evidence
CREDENTIALS_ACCESSED_DURING_THIS_RECONCILIATION = NO
GIT_ACTIONS = NONE
NEXT_PHASE_CANDIDATE = S2 — Message Scanner & SQLite Persistence / not started
```

Aceite funcional passou. GOV-01 continua dependência externa sem adjudicação,
bloqueando freeze e encerramento formal; não modificar governança para contornar.
S1-D permanece sem `CLOSED` e S2 não começou. Esta reconciliação não executou
acesso real nem abriu credenciais. Não executar ações Git. Fonte única do estado:
[PROJECT_STATE](../PROJECT_STATE.md); relatório detalhado:
[S1-D final validation](../../reports/S1D_REAL_DISCOVERY_VALIDATION_2026-10-09.md).

## Handoff vigente — GOV-01 resolvido e S1-D fechado — 2026-10-09

Decisão de autoridade: `KEEP_PINNED_BASELINE`. Os hashes de PM-01 a PM-05
foram confirmados nas fontes canônicas e nas cópias locais após cópia byte a
byte. `GOV01_STATUS=RESOLVED`, `DIVERGENCES_REMAINING=0`, binding inalterado e
fontes canônicas inalteradas. A observação externa do `baseline_role` da PM-04
permanece preservada. Evidência detalhada e hashes em §21 do
[contrato S1-D](../../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md).

Contrato congelado e aceite formal S1-D concluído: aceite funcional PASS,
calibração operacional PASS, seleção numérica PASS, FULL_PYTEST 126 testes +
11 subtests PASS, Ruff PASS e diff check PASS. O incidente histórico de leitura
do vault e o risco residual foram mantidos, sem nova evidência para reabertura.
S1 está CLOSED. S2 segue apenas como candidata; não foi iniciada nem autorizada.

```text
CONTRACT_FREEZE = PASS
S1D_FORMAL_ACCEPTANCE = PASS
S1D_STATUS = CLOSED
REAL_TELEGRAM_ACCESS = NO
CREDENTIALS_OR_SESSION_ACCESSED = NO
GIT_ACTIONS = NONE
NEXT_ACTION = S2 entry review / separate authorization required
```

## Handoff anterior — S2 Entry Review & Technical Contract Draft — 2026-10-09

S2 entry review concluiu PASS. A S1 permanece formalmente CLOSED. Dependências
locais aprovadas para trabalho offline estão presentes; ainda não existe
scanner, iteração de mensagens no gateway, repository ou schema SQLite de
aplicação. Esses itens pertencem ao escopo planejado S2, sem bloqueio técnico
para desenvolvimento com fakes e dados sintéticos.

O contrato está em
[S2_MESSAGE_SCANNER_SQLITE_CONTRACT](../../contracts/S2_MESSAGE_SCANNER_SQLITE_CONTRACT.md)
com status DRAFT / NOT_APPROVED / NOT_FROZEN. Define scanner, boundary,
metadados de mensagens/mídia, migrations SQLite, runs e checkpoint atômico,
falhas, limites e aceite. S2-OPEN-01 — retenção/exclusão de texto — aguarda
decisão do usuário antes do freeze ou ingestão de conteúdo real.

```text
S2_ENTRY_REVIEW = PASS
S2_READINESS = CONTRACT_DRAFT_READY_FOR_USER_REVIEW
S2_STATUS = PLANNED / NOT_STARTED
S2_IMPLEMENTATION_AUTHORIZATION = NO
REAL_TELEGRAM_ACCESS = NO
CREDENTIALS_OR_SESSION_ACCESSED = NO
TESTS_RUN = NO
GIT_ACTIONS = NONE
NEXT_ACTION = User review of contract and S2-OPEN-01 retention decision; any implementation requires separate authorization
```

Esta atividade não alterou código ou testes, não acessou Telegram, vault ou
sessão, e não iniciou S2. Preservar o incidente histórico de acesso acidental
ao vault e seu risco residual conforme PROJECT_STATE; não reabrir sem evidência
nova.

## Handoff anterior — S2 Integrated Implementation — 2026-10-10

S2-OPEN-01 foi aprovada e o contrato
[S2_MESSAGE_SCANNER_SQLITE_CONTRACT](../../contracts/S2_MESSAGE_SCANNER_SQLITE_CONTRACT.md)
está `APPROVED / FROZEN`. Implementados scanner, iteração de histórico no
gateway, migration SQLite, repository, persistência de mensagens/mídia, scan
runs, checkpoints atômicos, retomada e integração ao fluxo da aplicação/CLI.

```text
CONTRACT_REVIEW = PASS
CONTRACT_STATUS = APPROVED / FROZEN
S2-OPEN-01 = APPROVED
OFFLINE_INTEGRATION = PASS / gateway fake → SQLite → checkpoint
UNIT_AND_INTEGRATION_TESTS = PASS / 140 pytest + 11 subtests (full regression)
RUFF = PASS
GIT_DIFF_CHECK = PASS
REAL_TELEGRAM_ACCESS = NO
CREDENTIALS_OR_SESSION_ACCESSED = NO
GIT_ACTIONS = NONE
S2_IMPLEMENTATION_STATUS = PASS_OFFLINE
S2_ACCEPTANCE_STATUS = PENDING_SEPARATELY_AUTHORIZED_REAL_TELEGRAM_VALIDATION
S2_STATUS = IMPLEMENTED_OFFLINE / REAL_VALIDATION_PENDING / NOT_CLOSED
NEXT_ACTION = Obtain separate authorization and scope for controlled history validation
```

Retomar por [PROJECT_STATE](../PROJECT_STATE.md) e contrato S2. Preservar o
risco residual do incidente histórico de vault registrado no estado; não houve
novo acesso a vault, credenciais ou sessão nesta atividade.

## Handoff vigente — S2 Real Scan SQLite Acceptance — 2026-10-10

O banco `data/catalog.sqlite3` foi verificado em modo somente leitura. O run
`f91cbbe55540441d84092952e815e7e3` está `PARTIAL / MESSAGE_LIMIT`, com 10
mensagens e 5 mídias persistidas. Checkpoint/cursor consistente; foreign keys,
unicidade, integridade SQLite e close/reopen PASS. Nenhuma tarefa ou arquivo de
download foi encontrado. Evidência detalhada em [CONTINUITY_RECORD](../CONTINUITY_RECORD.md).

```text
S2_FORMAL_ACCEPTANCE = ACCEPTED
S2_STATUS = ACCEPTED / CLOSED
SQLITE_MESSAGES = 10
SQLITE_MEDIA = 5
SQLITE_REOPEN = PASS
DOWNLOADS = NONE
TELEGRAM_ACCESS_DURING_ACCEPTANCE = NO
CREDENTIALS_OR_SESSION_ACCESSED = NO
CODE_OR_GIT_ACTIONS = NONE
NEXT_ACTION = S3 entry review; S3 NOT_STARTED / implementation not authorized
```

Retomar pelo [PROJECT_STATE](../PROJECT_STATE.md). Preservar o incidente
histórico de vault e seu risco residual; esta atividade não acessou vault,
credenciais ou sessão.

## Handoff histórico — S3 Entry Review & Technical Contract — 2026-10-10

S2 segue `ACCEPTED / CLOSED`. A revisão de entrada S3 e o contrato draft estão
em [S3_PARSER_CATALOG_CONTRACT](../../contracts/S3_PARSER_CATALOG_CONTRACT.md).
O resultado é `PARTIAL`: foi confirmado que o material consultado não define a
semântica dos marcadores RASMOO, e SP-02 requer amostra representativa antes de
fechar parser/schema. O draft não atribui semântica presumida e define Generic,
Registry, Builder, persistência idempotente e navegação CLI.

```text
S3_ENTRY_REVIEW = PARTIAL
S3_READINESS = CONTRACT_DRAFT_READY / SP-02 AND RASMOO GRAMMAR DECISIONS OPEN
CONTRACT_STATUS = DRAFT / NOT_APPROVED / NOT_FROZEN
OPEN_DECISIONS = S3-OPEN-01..03
S3_IMPLEMENTATION_AUTHORIZATION = NO
REAL_TELEGRAM_ACCESS = NO
REAL_USER_SQLITE_ACCESS = NO
CREDENTIALS_OR_SESSION_ACCESSED = NO
TESTS_RUN = NO
GIT_ACTIONS = NONE
NEXT_ACTION = Review contract; resolve SP-02 and S3-OPEN-01..03; implementation requires separate authorization
```

Foram consultados PROJECT_STATE, ACTIVE_AUTHORITY_MAP, SPRINTS, ROADMAP,
REQUIREMENTS, ARCHITECTURE, ENGINEERING_FOUNDATION, contrato/implementação
SQLite S2 e dependências declaradas. Não se abriu o SQLite real e não se
acessou Telegram, credenciais ou sessão. A reconciliação corrente está em
[PROJECT_STATE](../PROJECT_STATE.md) e [CONTINUITY_RECORD](../CONTINUITY_RECORD.md).

### Atualização SP-02 — tentativa inconclusiva — 2026-10-10

O usuário forneceu a identidade estável do único canal autorizado. Uma operação
direcionada foi iniciada com limite de até 30 mensagens e orçamento inferior a
120s, sem scanner, download ou escrita local. O processo não retornou a saída
sanitizada antes de ser interrompido; a etapa remota e a contagem efetiva de
mensagens são desconhecidas. Não repetir sob o teto original. Nenhum resultado
de caso foi capturado e nenhuma semântica de `=`, `==`, `===`, `#Fxxx` ou
`#Docxxx` foi confirmada. O caminho local de credenciais/sessão foi invocado;
valores não foram emitidos.

```text
ACTIVITY_COMPLETION_PERCENT = 88%
SP02_STATUS = PARTIAL / NO SANITIZED RESULT
REQUESTED_MESSAGE_CAP = 30 / ACTUAL_MESSAGE_COUNT = UNKNOWN
STRUCTURAL_CASES_CAPTURED = 0
S3_OPEN_01 = UNRESOLVED
S3_OPEN_02 = UNRESOLVED
S3_OPEN_03 = UNRESOLVED
S3_IMPLEMENTATION_AUTHORIZATION = NO
REAL_USER_SQLITE_ACCESS = NO
DOWNLOADS = NONE / LOCAL_PERSISTENCE = NONE
RAW_CONTENT_EMITTED = NO
TESTS_RUN = NO
GIT_ACTIONS = NONE
NEXT_ACTION = Reconcile the message budget and obtain fresh bounded evidence, or use sanitized user-provided fixtures
```

## Handoff histórico — S3 Offline Catalog Core Implementation — 2026-10-10

O núcleo genérico offline S3 foi implementado e validado com fixtures
sintéticas e SQLite temporário. Inclui registry explícito/Generic fallback,
parser genérico, builder, migration 002, repository transacional e CLI Rich
`catalog build/list/show/items`. A implementação não inclui RasmooParser nem
autodetecção; SP-02 segue inconclusiva e nenhuma semântica de marcador foi
confirmada. Contrato permanece DRAFT; S3 não está encerrada. S2 continua
ACCEPTED / CLOSED.

```text
ACTIVITY_COMPLETION_PERCENT = 100%
S3_STATUS = IN_PROGRESS / GENERIC OFFLINE CORE COMPLETE
S3_IMPLEMENTATION_AUTHORIZATION = YES / OFFLINE GENERIC CORE ONLY
FULL_PYTEST = PASS / 157 passed + 11 subtests / 182.02s / Python 3.14.7
RUFF = PASS
DIFF_CHECK = PASS
CONTRACT = DRAFT / NOT_APPROVED / NOT_FROZEN
SP02 = INCONCLUSIVE / zero sanitized structural cases / actual count unknown
S3_OPEN_01 = UNRESOLVED / grammar
S3_OPEN_02 = PARTIAL / Generic identity validated; Rasmoo anchors open
S3_OPEN_03 = UNRESOLVED / no auto-detection
REAL_TELEGRAM_ACCESS = NO
REAL_USER_SQLITE_ACCESS = NO
CREDENTIALS_OR_SESSION_ACCESSED = NO
DOWNLOADS = NONE
GIT_ACTIONS = NONE
NEXT_ACTION = Obtain sanitized SP-02 fixtures or fresh bounded authorization, then decide S3-OPEN-01
```

Ver [PROJECT_STATE](../PROJECT_STATE.md), [CONTINUITY_RECORD](../CONTINUITY_RECORD.md)
e [contrato S3](../../contracts/S3_PARSER_CATALOG_CONTRACT.md). Não fazer
retry remoto, inferir gramática, congelar contrato ou publicar Git sem nova
authority específica.

## Handoff — S3 Generic Catalog Core Git Publication — 2026-10-10

O usuário autorizou a publicação Git seletiva do núcleo genérico offline S3.
S3 permanece IN_PROGRESS, com S3-OPEN-01, SP-02 e aceite formal pendentes. O
contrato permanece DRAFT e RasmooParser não foi implementado. A próxima
atividade é resolver a gramática RASMOO e implementar o parser especializado,
com autorização própria. Nenhum Telegram ou SQLite real é necessário para a
publicação do núcleo genérico.

## Handoff histórico — S3 SP-02 Grammar Resolution — 2026-10-10

O usuário confirmou a gramática básica suportada para `INDEX_MESSAGE` e
`MEDIA_POST` e declarou SP-02 suficiente para esses formatos. Em índice,
`=` = Track, `==` = Course, `===` = Module; `#Fxxx` é referência de conteúdo.
Em post de mídia, `#Fxxx <ordinal> <título>` identifica Lesson e o caminho é
Track sem marcador, `=` Course, `==` Module. Os posts usam a mídia anexada à
mensagem, endereçada pelas identidades S2; `#Fxxx` nunca é `telegram_message_id`.
Posts com #F distintos sob o mesmo Track/Course/Module são Lessons distintas.

`#Docxxx` identifica documento geral. A evidência fornecida confirma um RAR,
mas não vínculo com `#F001` nem curso exato; manter não atribuído sem contexto.
Referências associam por igualdade do código e contexto compatível. Entrada
sem correspondência ou ambígua fica unresolved. Reprocessamento da mesma fonte
é idempotente; não reparentar nem apagar estruturas por inferência.

```text
ACTIVITY_COMPLETION_PERCENT = 100%
SP02 = EVIDENCE SUFFICIENT FOR SUPPORTED INDEX + MEDIA POST GRAMMAR
S3_OPEN_01 = BASIC GRAMMAR CONFIRMED
S3_OPEN_02 = DETERMINISTIC IDENTITY AND CONSERVATIVE RECONCILIATION
S3_OPEN_03 = EXPLICIT PARSER SELECTION / Generic fallback
CONTRACT = DRAFT / NOT_APPROVED / NOT_FROZEN
SYNTHETIC_FIXTURES = tests/fixtures/rasmoo/sp02
RASMOO_PARSER = NOT_IMPLEMENTED / SEPARATE AUTHORIZATION REQUIRED
REAL_TELEGRAM_ACCESS = NO
REAL_USER_SQLITE_ACCESS = NO
CREDENTIALS_OR_SESSION_ACCESSED = NO
DOWNLOADS = NONE
TESTS_RUN = NO
GIT_ACTIONS = NONE
NEXT_ACTION = Obtain separate authorization before RasmooParser implementation
```

## Handoff histórico — S3 RasmooParser Integrated Implementation — 2026-10-10

O escopo comprovado pelo SP-02 foi aprovado e congelado em
[S3_PARSER_CATALOG_CONTRACT](../../contracts/S3_PARSER_CATALOG_CONTRACT.md),
limitado aos formatos documentados de índice, post de mídia e referência
documental geral. Formatos não observados permanecem unresolved.

O parser especializado está integrado ao registry, builder, SQLite e Rich CLI.
Associação de vídeo exige referência `#F` e hierarquia compatível; documentos
`#Doc` ficam gerais sem contexto explícito. Migration `003_catalog_unresolved.sql`
preserva referências e motivos não resolvidos. Reconciliação parcial/ambígua
preserva nós ativos e associações existentes. Reprocessamento igual preserva
identidades e timestamps.

Validação: 11 testes focados; FULL_PYTEST 163 passed + 11 subtests em 183,68 s;
Ruff PASS; `git diff --check` PASS. A suíte completa foi repetida sem Ruff em
paralelo após teste de smoke detectar atualização do cache Ruff; a repetição
isolada passou. Só fixtures e banco temporário foram usados. Nenhum acesso a
Telegram, SQLite real, credencial/sessão ou downloads ocorreu.

```text
S3_STATUS = IN_PROGRESS
S3_CONTRACT = APPROVED / FROZEN_FOR_CONFIRMED_SP02_SCOPE_ONLY
RASMOO_PARSER = PASS_OFFLINE
REGISTRY_BUILDER_SQLITE_RICH_CLI = PASS_OFFLINE
FOCUSED_TESTS = 11 PASSED
FULL_PYTEST = 163 PASSED + 11 SUBTESTS
RUFF = PASS
DIFF_CHECK = PASS
REAL_TELEGRAM_ACCESS = NO
REAL_SQLITE_ACCESS = NO
DOWNLOADS = NONE
GIT_ACTIONS = NONE / NO STAGING, COMMIT OR PUSH
S3_FORMAL_ACCEPTANCE = PENDING / OFFLINE TESTS DO NOT CLOSE S3
SAFE_RESUME_POINT = Review offline results and plan a separately authorized acceptance activity
NEXT_ACTION = Request the full RASMOO telegram_chat_id, then resume this same authorized bounded validation
```

## Handoff histórico — S3 Controlled RASMOO Real Validation — 2026-10-10

A coleta autorizada já foi realizada pelo usuário; esta atividade opera somente
no SQLite temporário informado, sem repetir scan. A auditoria local passou:
integridade OK, zero violações FK, 30 mensagens, 26 mídias, scan PARTIAL / MESSAGE_LIMIT
e checkpoint consistente. O `--help` confirma a sintaxe e o código explica exit
4 para estado não COMPLETE. O venv exige Python 3.14, mas seu interpretador-base
está ausente; `catalog list` e um smoke assíncrono mínimo ficaram suspensos.
Nenhum parser/build/CLI Rich foi executado e o banco temporário não foi alterado.

```text
ACTIVITY_STATUS = BLOCKED_PREFLIGHT / ASYNC_SQLITE_RUNTIME_HANG
SCAN_EXECUTIONS = 0 / THIS ACTIVITY IS LOCAL-ONLY
TEMP_DATABASE = USER_PROVIDED / READ_ONLY AUDIT PASS / CATALOG UNCHANGED
MESSAGES_PERSISTED = 30
MEDIA_PERSISTED = 26
SQLITE_INTEGRITY = PASS / FK violations 0
CHECKPOINT = CONSISTENT / PARTIAL
CATALOG_BUILD = NOT_RUN
RICH_CLI = BLOCKED
S3_STATUS = IN_PROGRESS
S3_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Restore supported Python 3.14 runtime and continue local catalog validation against the same temporary database, without another scan
AUTHORITIES = PROJECT_STATE.md and CONTINUITY_RECORD.md
```

## Handoff histórico — S3-MAG-01 Catalog CLI Windows Compatibility — 2026-10-10

O adaptador de saída do Catalog foi implementado para manter Unicode que cabe na
codificação do stream e emitir escapes ASCII apenas para caracteres que não
cabem. Regressões sintéticas cobrem UTF-8, CP1252, CP850 e saída redirecionada
nos comandos `build`, `list`, `show` e `items`; o teste do writer passou, assim
como Ruff e `git diff --check`.

O incidente original continua classificado como causa provável: a exceção
original não foi capturada. A integração em execução no sandbox parou antes do
SQLite porque o Windows Proactor não conseguiu criar seu socketpair. Um rebuild
antes/depois e a suíte completa ainda precisam rodar em PowerShell funcional do
usuário.

Em cópia isolada e consultada somente para agregados, o SQLite temporário tem um
canal, dois runs completos de 589 nós e 2 unresolved, 589 nós ativos, nenhum
inativo e 26/26 mídias vinculadas. O número 589 coincide com o active count nesse
banco. O número 98 não foi reproduzido; falta a query ou snapshot que o originou.

```text
ACTIVITY_STATUS = PARTIAL / IMPLEMENTED, ROOT VALIDATION PENDING
ARCHITECT_VERDICT = PASS
SCRIBER_VERDICT = PARTIAL
ROOT_CAUSE = PROBABLE / original exception not captured
CATALOG_ITEMS_WINDOWS = PENDING_USER_WINDOWS_VALIDATION
CATALOG_CLI_REGRESSION = PENDING_USER_WINDOWS_VALIDATION
IDEMPOTENCY = PARTIAL / isolated before-after rebuild pending
CATALOG_COUNTS = 589 plan nodes = 589 active in supplied copy; 98 source query unknown
RUFF = PASS
DIFF_CHECK = PASS
GIT_ACTIONS = NONE
TELEGRAM_ACCESS = NO
DOWNLOADS = NONE
S3_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Run focused/full tests and the isolated-copy rebuild in supported PowerShell; supply the query/snapshot behind 98
```

## Handoff vigente — S3-CLOSE-01 Formal Acceptance and Publication — 2026-10-10

S3 está formalmente ACCEPTED / CLOSED. O núcleo genérico, RasmooParser,
`S3-MAG-01`, catálogo real com escopo limitado, idempotência e CLI Windows
passaram; regressão completa 167 passed + 11 subtests, Ruff e diff check PASS.
O scan real parou em `MESSAGE_LIMIT` após 30 mensagens e 26 mídias; duas
referências unresolved permanecem visíveis. A gramática está aprovada somente
para os formatos comprovados. Não houve validação de downloads; validação
integral do produto no canal real está planejada para S9.

```text
ACTIVITY = S3-CLOSE-01
S3_STATUS = ACCEPTED / CLOSED
S3_FORMAL_ACCEPTANCE = APPROVED
S3_GENERIC_CORE = PASS
RASMOO_PARSER = PASS
S3_MAG_01 = PASS
REAL_CATALOG_VALIDATION = PASS_WITH_SCOPE
IDEMPOTENCY = PASS
WINDOWS_CLI = PASS
FULL_REGRESSION = PASS / 167 passed + 11 subtests
RUFF = PASS
DIFF_CHECK = PASS
GIT_PUBLICATION = PENDING
S4_STATUS = PLANNED / NOT_STARTED
S4_IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
SAFE_RESUME_POINT = S4 entry review; implementation requires separate authorization
```

## Handoff vigente — S4-IMPL-01 Single Media Download — 2026-10-10

O estado factual foi reconciliado: repo `C:\Users\walac\desenvolvimento\projeto_telegram_courses`, branch `work/s0-bootstrap`, HEAD `143c1695f3c0fc1040bf46373d40bdb4c83b559f`, worktree sem alterações prévias antes desta atividade. O contrato S4 foi criado e congelado somente para uma mídia DOCUMENT de Lesson. A implementação inclui seleção SQLite, migration aditiva 004, adapter Telethon `iter_download`, `.part`, SHA-256 local, finalização sem sobrescrita, reconciliação e comando CLI.

Validação executada neste ambiente: 8 testes unitários focados PASS; prova Windows sintética de finalização no mesmo volume sem sobrescrita PASS; migration 001–004 e índice único exercitados em SQLite em memória PASS; Ruff em `src` e `tests` PASS; `compileall` PASS; `git diff --check` PASS; coleta pytest = 186 testes, incluindo 11 novos cenários de integração offline; Telethon local 1.45.0 e assinaturas de `iter_download`/`get_messages` confirmadas. A execução dos testes SQLite integrados foi tentada em diretório temporário fora do repositório, ficou sem retornar durante a primeira integração e foi interrompida; a suíte completa não foi executada. O runner do sandbox não confirmou causa raiz nesta tentativa; tratar como limitação de ambiente, não como falha ou aprovação do código integrado.

```text
ACTIVITY = S4-IMPL-01
ACTIVITY_COMPLETION_PERCENT = 56%
S4_STATUS = IN_PROGRESS / OFFLINE IMPLEMENTATION
S4_CONTRACT = APPROVED / FROZEN_FOR_SINGLE_LESSON_MEDIA
S4_IMPLEMENTATION_AUTHORIZATION = GRANTED / OFFLINE ONLY
S4_OFFLINE_INTEGRATION = NOT_CONFIRMED / 11 integration tests added; sandbox async runner did not return
S4_FULL_PYTEST = NOT_RUN / 186 collected
S4_RUFF = PASS
S4_FOCUSED_UNIT_TESTS = PASS / 8
S4_WINDOWS_FINALIZATION_TEST = PASS / synthetic os.rename same-volume no-overwrite
S4_MIGRATION_SMOKE = PASS / SQLite in-memory migrations 001–004 and unique media constraint
S4_DIFF_CHECK = PASS
REAL_TELEGRAM_ACCESS = NO
REAL_MEDIA_DOWNLOAD = NONE
REAL_CATALOG_SQLITE_MODIFICATION = NO
GIT_ACTIONS = NONE
S4_FORMAL_ACCEPTANCE = PENDING
FIRST_VERTICAL_SLICE_GATE = PENDING
SAFE_RESUME_POINT = Run focused integration tests, full pytest, Ruff and diff check in functional PowerShell using --basetemp under $env:TEMP; repair any reproducible code failures
NEXT_ACTION = Complete offline integration and regression; do not perform real Telegram validation or Git publication
```

Comando curto para retomar no PowerShell funcional, mantendo os temporários
fora do repositório:

```powershell
$s4TestTemp = Join-Path $env:TEMP 'telegram-courses-s4-focused'
python -m pytest tests/unit/test_downloads.py tests/integration/test_download_flow.py -q --basetemp $s4TestTemp
if ($LASTEXITCODE -ne 0) { throw 'S4 focused tests failed' }
python -m pytest -q --basetemp (Join-Path $env:TEMP 'telegram-courses-s4-full')
if ($LASTEXITCODE -ne 0) { throw 'Full pytest failed' }
ruff check src tests
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
```

## Handoff — S4-REAL-01B First Real Media Download and Deduplication — 2026-10-10

Preflight only; no Telegram connection or download was made. Python 3.14.7 and
CLI help were confirmed. The supplied catalog SQLite was opened read-only and
copied with SQLite Online Backup; the isolated copy passed integrity, foreign
key, message/media count, parser and selected-lesson eligibility checks.
Migration 004 and its unique index passed on that copy. The synchronous
preflight completed, but the project repository's async migration path blocked
in this executor and was interrupted once. The CLI credential status reported
no configured vault in this executor; no credential, DPAPI or session file was
inspected. The executor-local temporary copy cannot be reused in the user's
functional PowerShell.

No CLI download invocation occurred, no media bytes were transferred, and no
`.part` or final media file was created. The SQLite source was used read-only.
No scan, other download or Git action occurred. S4 formal acceptance and the
first vertical slice gate remain pending. Recreate the isolated copy and empty
download directory in the user's functional PowerShell, then perform exactly
one approved download, validate the file and SQLite row independently, and
only then perform the single deduplication invocation.

```text
ACTIVITY = S4-REAL-01B
ACTIVITY_COMPLETION_PERCENT = 28%
STATUS = PARTIAL / PREFLIGHT PASS; BLOCKED BEFORE TELEGRAM CONNECTION
SOURCE_SQLITE = READ_ONLY
TEMP_SQLITE = ONLINE BACKUP PASS / MIGRATION 004 PASS ON COPY
SQLITE_INTEGRITY = PASS / zero FK violations
DOWNLOAD_EXECUTIONS = 0
TRANSFERRED_BYTES = 0
DEDUPLICATION_CHECK_EXECUTIONS = 0
FIRST_VERTICAL_SLICE_GATE = PENDING
S4_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Continue in functional PowerShell with the same approved media, same isolated DB copy, same temporary download root and bounded two-invocation protocol
GIT_ACTIONS = NONE
```
