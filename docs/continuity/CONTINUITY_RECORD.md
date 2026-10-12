# Registro de continuidade

## Checkpoint corrente — S5-FORMAL-CLOSURE-01 — Encerramento formal da S5 — 2026-10-12

O usuário aprovou explicitamente: “Aprovo formalmente a S5, com as ressalvas documentadas. Prepare o encerramento formal, sem commit ou push.” O aceite formal está APPROVED, S5 está CLOSED e o resultado do encerramento é PASS. A prova técnica S5-REAL-PROOF-01 permanece CLOSED / PASS, assim como o diagnóstico S5-REAL-FAILURE-DIAG-01; correção, falha inicial, recuperação e deduplicação continuam nos checkpoints históricos abaixo.

As ressalvas permanecem: CATALOG_COMPLETE = FALSE (prova limitada às cinco mídias observadas; não representa completude do módulo/canal) e GATEWAY_DOWNLOAD_CALLS = NOT_DIRECTLY_OBSERVABLE (deduplicação evidenciada pelo estado, plano vazio, ausência de novas transferências e hashes inalterados). S6 permanece PLANNED / NOT_STARTED. Nenhuma validação, fila, transferência ou acesso/modificação de SQLite foi executado nesta atividade. Código-fonte e artefatos de prova foram preservados; nenhuma operação Git de escrita ocorreu.

ACTIVITY = S5-FORMAL-CLOSURE-01
ACTIVITY_COMPLETION_PERCENT = 100%
STATUS = COMPLETED / FORMAL DOCUMENTARY CLOSURE PASS
USER_FORMAL_APPROVAL = GRANTED
S5_FORMAL_ACCEPTANCE = APPROVED
S5_STATUS = CLOSED
S5_CLOSURE_RESULT = PASS
S5_IMPLEMENTATION = COMPLETED
S5_OFFLINE_VALIDATION = PASS / 206 passed + 11 subtests; 56 focused tests; user-provided prior evidence
S5_REAL_PROOF_01 = CLOSED / PASS
S5_REAL_FAILURE_DIAG_01 = CLOSED / PASS
HISTORICAL_CHECKPOINTS = PRESERVED / initial failure, correction, recovery, deduplication
CATALOG_SCOPE = PARTIAL / five observed media only
GATEWAY_DOWNLOAD_CALLS = NOT_DIRECTLY_OBSERVABLE
SOURCE_CODE_CHANGES = NONE
QUEUE_EXECUTIONS = 0
SQLITE_MODIFICATIONS = NONE
GIT_ADD = NO / GIT_COMMIT = NO / GIT_PUSH = NO
S6_STATUS = PLANNED / NOT_STARTED
NEXT_SAFE_ACTION = Await separate direction/authorization for S6 entry review; do not initiate S6 automatically
PROJECT_STATE_RECONCILIATION = PASS

---

## Checkpoint anterior — S5-REAL-PROOF-01 — Recuperação real e deduplicação — 2026-10-12

A evidência final fornecida pelo usuário fecha a prova técnica S5-REAL-PROOF-01
como PASS. A recuperação concluiu quatro downloads e reutilizou uma mídia já
válida: cinco mídias íntegras, zero falhas e zero pendências. Os bytes
acumulados foram 73.071.671, abaixo do limite autorizado de 83.886.080; dois
workers foram observados. O catálogo é parcial e a prova está limitada às
cinco mídias observadas.

A deduplicação foi executada uma vez, com exit code 0: cinco já válidas, zero
pendentes e zero bytes transferidos. `SHA256_VS_SQLITE`, `FILES_INTEGRITY`,
`SQLITE_INTEGRITY` e `FOREIGN_KEY_CHECK` passaram; restaram zero arquivos
`.part`; arquivos e hashes permaneceram inalterados. Manifest SHA-256:
`aed7c3651c90827c54d83bbd35a23ca536a6452ef523e67542d8ca0a364136d6`.

O diagnóstico da concorrência está encerrado. A correção de inicialização
compartilhada do gateway passou pela validação sintética já registrada e foi
aprovada para esta prova; a recuperação real e a deduplicação real passaram.
Chamadas ao gateway/GetFile não foram observadas diretamente, portanto a prova
comprova os resultados persistidos e físicos informados, sem alegar contagem
ou sequência de chamadas remotas. A fonte original não deve ser alterada; a
evidência confirma arquivos e hashes inalterados na deduplicação. SQLite e
arquivos de prova devem ser preservados.

Esta conclusão é somente técnica. S5 permanece em andamento até aceite formal
explícito do usuário; não houve avanço de fase nem autorização de Git.

```text
ACTIVITY = S5-REAL-PROOF-01
ACTIVITY_COMPLETION_PERCENT = 100%
STATUS = COMPLETED / TECHNICAL PROOF PASS; S5 FORMAL ACCEPTANCE PENDING
CONCURRENCY_DIAGNOSIS = CLOSED
SYNTHETIC_CORRECTION = PASS / APPROVED
RECOVERY = PASS / 4 downloads complete; 1 already-valid media reused
RECOVERY_FAILURES = 0
RECOVERY_PENDING = 0
DEDUP = PASS / one execution; exit 0; already valid=5; pending=0; transferred=0
ACCUMULATED_BYTES = 73071671
AUTHORIZED_BYTE_LIMIT = 83886080
ACCUMULATED_BUDGET = RESPECTED
WORKERS_OBSERVED = 2
REAL_PROOF_MEDIA_COUNT = 5 / all intact
CATALOG_SCOPE = PARTIAL / proof limited to the five observed media
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
S5_REAL_VALIDATION = PASS / technical proof only
S5_FORMAL_ACCEPTANCE = PENDING / explicit user acceptance required
GIT_ACTIONS = NONE
NEXT_ACTION = Await explicit S5 formal acceptance; no repeated proof/validation
PROJECT_STATE_RECONCILIATION = PASS
```

---

## Checkpoint anterior — S5-REAL-PROOF-01 — Controlled Real Resume — 2026-10-11

A retomada autorizada foi submetida somente a preflight read-only no runtime
atual. A raiz existente `s5-real-proof-5f8a5d4b38d14d009ecdc1646f476d3b`
continua intacta. O SQLite isolado passou `integrity_check=ok` e
`foreign_key_check=0`. A mídia 598 permanece `DOWNLOADED`, 11.649.955 bytes,
com SHA-256 físico e persistido
`3bfe15fabb50cd47ddc2b40aa06881bf5a17faff6bb5729c2e34d38ef1edd5c4`. As mídias
599–602 permanecem `FAILED_RETRYABLE`, `SESSION_INVALID`, uma tentativa cada,
zero bytes; seus quatro `.part` seguem presentes e vazios.

O planner atual, executado em modo somente leitura sobre a seleção do módulo
29, retornou exatamente cinco itens: mídia 598 `ALREADY_VALID`, mídias 599–602
`PENDING`, zero bloqueados e zero excluídos. A seleção contextual de módulo é
a opção 4 no menu atual. Bytes pendentes esperados: 61.421.716; cap cumulativo
restante autorizado: 72.236.125 bytes, somado aos 11.649.955 bytes já
transferidos, dentro do teto de 83.886.080 bytes. O catálogo continua parcial;
a CLI mostrará o aviso e pedirá confirmação interativa. O contrato trata
`FAILED_RETRYABLE` como estado persistido genérico; o planner aceita os quatro
itens sem alterar seus estados. A recuperação autorizada é uma única fila, e
uma fila de deduplicação só poderá seguir depois do gate integral
`DOWNLOADED=5`, `PENDING=0`, `ALREADY_VALID=5`, integridade dos arquivos e
SQLite PASS. O cap da recuperação é 72.236.125 bytes; o cap da deduplicação é
separado e será 1 byte. O código rejeita limite 0 e `None` deixa a transferência
sem cap. Como as cinco identidades têm tamanhos conhecidos maiores que 1 byte,
qualquer pendência bloqueia antes do worker; com plano integralmente válido, a
CLI retorna antes de criar o gateway.

O código local aplica o limite de bytes por orçamento compartilhado e reserva
no máximo 256 KiB antes de cada solicitação Telethon; a execução real ainda
precisa ocorrer no runtime que contém Telethon 1.45.x e o vault funcional. O
procedimento revisado usa `asyncio.run` normal no Windows, sem avançar coroutine
manualmente, e registra hash da SQLite fonte antes e depois sem abri-la para
escrita. Aqui,
o Python 3.14 da venv reportou caminho-base ausente, e até
`asyncio.run(asyncio.sleep(0))` não concluiu em dez segundos; o processo foi
interrompido antes de qualquer fila ou chamada Telegram. Por isso, nenhuma
execução de recuperação ou deduplicação ocorreu. O espaço livre observado era
48.319.725.568 bytes. Foi reconciliado procedimento PowerShell interativo com
preflight, execução única e validações condicionais; nenhuma alteração de
código de produção, scan, catálogo, prova ou Git ocorreu.

```text
ACTIVITY = S5-REAL-PROOF-01
ACTIVITY_COMPLETION_PERCENT = 55%
STATUS = PARTIAL / PREFLIGHT PASS; REAL RUNTIME UNAVAILABLE HERE; LOCAL POWERSHELL EXECUTION PENDING
DIAGNOSTIC_ACTIVITY = CLOSED / 100%
SYNTHETIC_FIX_VALIDATION = PASS
RESUME_PREFLIGHT = PASS_READ_ONLY / isolated SQLite, row states, files, hashes, selection and disk verified
FAILED_RETRYABLE_ELIGIBILITY = PLANNER PASS / four rows selected as PENDING; no SQLite reclassification
PREVIOUS_COMPLETED_MEDIA_REUSED = YES / media 598 is ALREADY_VALID, exact size and SHA-256 preserved
RECOVERY_QUEUE_EXECUTIONS = 0
RECOVERY_RESULT = NOT_RUN / local executor cannot complete asyncio event loop; PowerShell procedure supplied
PREVIOUS_TRANSFER_BYTES = 11649955
RECOVERY_TRANSFER_BYTES = NOT_RUN
CUMULATIVE_TRANSFER_BYTES = 11649955 / before authorized recovery
CUMULATIVE_BUDGET_RESPECTED = YES / preflight cap arithmetic; runtime request accounting not yet exercised
DOWNLOADED_MEDIA = 1
FAILED_MEDIA = 4
PENDING_MEDIA = 4 / planner result before recovery
WORKERS_CONFIGURED = 2
WORKERS_OBSERVED = NOT_RUN
FILES_INTEGRITY = PASS / completed media size/hash match; four part files remain zero bytes
SHA256_VERIFICATION = PASS / media 598 matches SQLite
SQLITE_INTEGRITY = PASS / integrity ok; zero foreign-key violations
PART_FILES_REMAINING = 4 / preserved
DEDUP_QUEUE_EXECUTIONS = 0
DEDUP_RESULT = NOT_RUN / conditional on full recovery PASS
DEDUP_TRANSFERRED_BYTES = NOT_RUN
SOURCE_SQLITE_UNMODIFIED = YES / source catalog not opened for writing
SOURCE_CODE_CHANGES = NONE
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PARTIAL / original real run remains partial; post-fix queue not yet executed
S5_FORMAL_ACCEPTANCE = PENDING
NEXT_SAFE_ACTION = Run the supplied preflight-gated procedure in functional user Windows PowerShell; one recovery queue; dedup only after five-media validation
PROJECT_STATE_RECONCILIATION = PASS / current runtime blocker and exact safe resume point recorded; proof preserved
```

---

## Checkpoint corrente — S5-REAL-FAILURE-DIAG-01 — Forensics and Shared Gateway Initialization Fix — 2026-10-11

A prova isolada foi inspecionada sem escrita no SQLite (`mode=ro`) e sem
executar helper, fila, testes ou chamadas Telegram. `integrity_check=ok` e
`foreign_key_check` vazio. O schema `downloads` contém `error_details` e
`failure_category`; as quatro mídias 1–4 (mensagens 602–599) persistem
`SESSION_INVALID`, `attempts=1`, `downloaded_bytes=0`, hash nulo e caminhos
`.part` existentes com zero bytes. A mídia 5 (mensagem 598) terminou com
11.649.955 bytes. SHA-256 físico e persistido conferem:
`3bfe15fabb50cd47ddc2b40aa06881bf5a17faff6bb5729c2e34d38ef1edd5c4`.

Os timestamps mostram mídia 5 em transferência de 22:52:49.572 a 22:53:00.322
UTC, enquanto os quatro erros ocorreram em sequência entre 22:52:50.539 e
22:52:50.945 UTC. No código S5, `_LazyGateway.stream_media` tornava a instância
visível antes de `await restore()`. O segundo worker podia chamar
`TelethonGateway._iterate_media` enquanto `_state` ainda era `None`; seu guard
produz `SESSION_INVALID` antes de resolver entidade, buscar mensagem ou iniciar
GetFile. O worker continuava a esgotar os outros itens durante a restauração.
Isso estabelece um defeito concorrente no código e explica fortemente a
execução, embora não exista trace original da fila que confirme a sequência
histórica frame a frame.

`queue-first.txt` e `powershell-transcript.txt` terminam com “execução não
confirmada” às 18:55 locais; as gravações SQLite são de 19:52–19:53 locais.
Esses arquivos registram a prévia anterior, não a execução que produziu os
downloads. Portanto a exceção Telethon original não está disponível; o banco
reteve somente a categoria sanitizada. O transcript separado de preflight não
prova acessibilidade remota das quatro mensagens.

O contrato S5 exclui `SESSION_INVALID` da lista transitória; uma tentativa por
mídia está conforme a política observada, e o `FAILED_RETRYABLE` de S4 é o
estado persistido genérico para exceções de download, não sinal de retry
automático. O aplicativo abriu cada `.part` antes da iteração e o erro ocorreu
antes do primeiro chunk, explicando os quatro arquivos vazios. Não há evidência
de falha de integridade/persistência nem de causa em referência expirada,
mensagem ausente ou mídia divergente; os estados remotos desses itens não foram
consultados.

Após autorização explícita do usuário, `mechanical_implementer` alterou somente
o wrapper lazy do gateway na fila S5 em `src/telegram_courses/cli.py`: todos os
workers agora aguardam a mesma tarefa de inicialização/restauração antes de
obter o gateway para streaming. A criação continua lazy.

A validação focalizada passou usando um harness temporário que extraiu a classe
`_LazyGateway` do código atual da CLI e a exerceu com fakes, duas tarefas
concorrentes e eventos determinísticos. Com restore bloqueado, houve uma
fábrica e uma chamada a `restore`, zero streams antes da autenticação, dois
streams simultâneos depois da liberação e um fechamento. Cenários separados
confirmaram `SESSION_INVALID` para estado inválido e `GATEWAY_FAILURE` para
exceção de restore, ambos compartilhados sem iniciar streams e fechados uma vez.
A criação permaneceu lazy sem stream solicitado. O executor bloqueou a criação
do loop Proactor padrão em `socketpair`; o harness foi executado com um loop
seletor local sem I/O, suficiente para estes fakes e tarefas em memória. Não
foram usados sockets, threads, Telegram, fila S5 nem a prova real. Harness e
artefatos temporários foram removidos; não foi adicionada infraestrutura
permanente nem alterado novamente o código de produção.

Não houve nova fila real, retomada, deduplicação, scan, acesso Telegram,
alteração na prova ou ação Git. `S5_REAL_VALIDATION` continua `PARTIAL` e a
aceitação formal S5 permanece `PENDING`.

```text
ACTIVITY = S5-REAL-FAILURE-DIAG-01
ACTIVITY_COMPLETION_PERCENT = 100%
STATUS = COMPLETED / FOCUSED SYNTHETIC VALIDATION PASS; REAL S5 VALIDATION PARTIAL
SQLITE_EVIDENCE = integrity ok; zero FK errors; four SESSION_INVALID rows; one valid download with physical SHA-256 match
ERROR_CLASSIFICATION = download guard before entity/message/file request; original Telethon exception unavailable
ROOT_CAUSE = shared lazy gateway published before restore completion; second worker observes unauthenticated in-memory state
ROOT_CAUSE_CONFIDENCE = HIGH / code mechanism and persisted timing strongly match; no execution trace for the actual queue
FAILED_MEDIA_COUNT = 4
ZERO_BYTE_PART_FILES = 4
RETRY_POLICY_FINDING = one attempt is correct for SESSION_INVALID, which is terminal under the S5 automatic retry whitelist
GATEWAY_FINDING = initialization/restoration race confirmed in code; all workers now await one shared initialization task
CONCURRENCY_FINDING = two workers; successful first transfer overlapped the four rapid failures
FILE_INTEGRITY_FINDING = downloaded media size and SHA-256 match SQLite; proof root preserved
DEFECT_CONFIRMED = YES / shared lazy gateway initialization race
PROPOSED_MINIMAL_FIX = IMPLEMENTED / cli.py S5 queue wrapper shares initialization task
PROPOSED_TARGETED_TESTS = delayed restore with two workers; assert one restore, no streams before restore, then all streams after success; cover invalid state and failed restore
SOURCE_CODE_CHANGES = src/telegram_courses/cli.py only in this correction
SYNTHETIC_CONCURRENCY_TEST = PASS / two tasks overlap; one factory and one restore
SINGLE_RESTORE_TEST = PASS / one shared restore
NO_PREMATURE_STREAM_TEST = PASS / zero streams while restore is blocked; none before auth
POST_RESTORE_CONCURRENCY = PASS / both streams active concurrently after authentication
INVALID_SESSION_TEST = PASS / SESSION_INVALID shared; zero streams; close once
RESTORE_FAILURE_TEST = PASS / GATEWAY_FAILURE shared; zero streams; close once
LAZY_INITIALIZATION_TEST = PASS / no gateway constructed without a stream request
GATEWAY_CLOSE_TEST = PASS / one close after success and both failure cases
VALIDATION_LIMIT = temporary harness extracted current CLI `_LazyGateway`; fakes only; local no-I/O selector loop; no queue or network
TESTS = TEMPORARY_SYNTHETIC_HARNESS / PASS / no permanent test or infrastructure added
QUEUE_EXECUTIONS = 0 / by this continuation; historical failed queue evidence preserved
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PARTIAL / historical 1 success + 4 failures; no post-fix run
S5_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Await separate authorization before controlled real queue resumption; preserve SQLite, completed media, four `.part` files and evidence; no deduplication
PROJECT_STATE_RECONCILIATION = PASS / synthetic validation and limits recorded; temporary harness removed; no real queue, Telegram, proof modification, staging, commit or push
NEXT_ACTION = Prepare a separately authorized controlled resumption; keep S5 formal acceptance pending
```

---

## Checkpoint corrente — S5-REAL-UNBLOCK-01 — Offline Closure and Module A Read-only Preview — 2026-10-11

O usuário forneceu evidência de validação offline em Python 3.14.7: quatro
testes corretivos, 56 testes focados S4/S5, 206 testes da regressão completa,
11 subtests, Ruff e `git diff --check`, todos PASS com exit 0. Esses resultados
foram reconciliados como `S5_OFFLINE_VALIDATION = PASS` e não foram repetidos.

A fonte SQLite RASMOO indicada estava presente e foi aberta em modo read-only.
SQLite Online Backup para arquivo temporário e migration 004 somente nessa
cópia passaram (`integrity_check=ok`; migrations 1–4). A execução parou antes
do CLI imprimir ou concluir o plano: o coroutine async do planner não retornou
neste executor, mesmo após uma tentativa process-local com Selector event
loop. O processo foi interrompido. Nenhum resultado de preview foi inferido;
a cópia temporária foi descartada pelo ambiente ao encerrar o processo.

O `--help` da CLI instalada confirmou as opções reais `download plan`,
`--database`, `--download-dir`, `--channel-id`, `--scope`, `--workers`,
`--max-media-items` e `--max-transfer-bytes`. A seleção estrutural do módulo
(5 aulas, 5 mídias e 73.071.671 bytes) não chegou a ser concluída pelo planner.
Não houve `download queue`, gateway, Telegram, transferência ou escrita na
SQLite fonte.

```text
ACTIVITY = S5-REAL-UNBLOCK-01 — Offline Closure and Module A Read-only Preview
ACTIVITY_COMPLETION_PERCENT = 40%
STATUS = PARTIAL / OFFLINE PASS RECONCILED; PREVIEW BLOCKED IN EXECUTOR
OFFLINE_VALIDATION = PASS / user-provided; not rerun
CORRECTED_TESTS = 4 PASSED / EXIT 0 / user-provided
FOCUSED_S4_S5 = 56 PASSED / EXIT 0 / user-provided
FULL_REGRESSION = 206 PASSED + 11 SUBTESTS / EXIT 0 / user-provided
RUFF = PASS / user-provided
DIFF_CHECK = PASS / user-provided
ONLINE_BACKUP = PASS / isolated temporary copy
MIGRATION_004 = PASS / isolated temporary copy only
MODULE_A_SELECTED = NOT_CONFIRMED
LESSON_COUNT = NOT_CONFIRMED
MEDIA_COUNT = NOT_CONFIRMED
PENDING_COUNT = NOT_CONFIRMED
ALREADY_VALID_COUNT = NOT_CONFIRMED
EXCLUDED_COUNT = NOT_CONFIRMED
PENDING_BYTES = NOT_CONFIRMED
MAX_MEDIA_ITEMS = 5 / requested preview setting
MAX_TRANSFER_BYTES = 83886080 / requested preview setting
LIMIT_CHECK_RESULT = NOT_RUN
DETERMINISTIC_ORDER = NOT_CONFIRMED
PREVIEW_RESULT = BLOCKED / planner async execution did not return before CLI output
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
SOURCE_SQLITE_WRITE = NO
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PENDING
S5_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Run only the read-only download plan preview in functional PowerShell against a fresh Online Backup; apply migration 004 only on the copy. Do not run queue.
PROJECT_STATE_RECONCILIATION = PASS / latest evidence and blocker recorded
FINAL_VERDICT = PARTIAL / preview pending
NEXT_ACTION = Resume the preview in functional PowerShell; do not repeat offline tests
```

---

## Checkpoint corrente — S5-REAL-UNBLOCK-01 — 2026-10-11

A investigação read-only confirmou a causa principal em `_Reservation.settle`:
o método acessava `max_transfer_bytes` no objeto de reserva, gerando
`AttributeError` depois de receber bytes. O root capturou o limite na closure,
manteve as reservas atômicas e ajustou a contabilidade de retries para refletir
bytes cumulativos: três tentativas de 4 bytes podem contabilizar 12 bytes. O
teste de saldo insuficiente agora solicita uma segunda reserva efetiva. A fila
também bloqueia byte cap quando existe exclusão `UNKNOWN_SIZE`, conforme o
contrato congelado; o teste integrado de seleção de curso permanece sem cap
para validar o fluxo de seleção independentemente desse gate. A assinatura
`close()` foi movida para o protocolo `TelegramGateway`.

Ruff passou. `git diff --check` passou, com avisos de conversão LF/CRLF. A
tentativa focada local não conseguiu localizar a instalação base do Python
3.14 (`pythoncore-3.14-64`) e terminou sem resultados de testes; não foi
repetida. O Python global disponível é 3.15 e não substitui o runtime fixado.
Regressão completa não executada. A evidência 10/8 pertence à reprodução do
usuário antes destas correções. Aceite S5, preview e execução real permanecem
pendentes.

```text
ACTIVITY = S5-REAL-UNBLOCK-01 — Root Correction
ACTIVITY_COMPLETION_PERCENT = 72%
STATUS = PARTIAL / IMPLEMENTATION AND STATIC CHECKS PASS; TESTS PENDING
DIAGNOSTIC_AGENT_USED = YES / read-only diagnostic_analyst
DIAGNOSTIC_FINDINGS = Invalid nested self reference in reservation settlement; retry-byte expectation was non-cumulative; insufficient-balance case lacked a second request; queue API lacked unknown-size cap guard
DIAGNOSTIC_CONFIDENCE = HIGH / code and contract inspection; no successful reproduction in this executor
ROOT_IMPLEMENTATION = Closure captures the queue limit; attempt tests assert cumulative bytes and denied second reservation; unknown-size byte-cap guard added; TelegramGateway close protocol corrected
FOCUSED_TESTS = NOT_VERIFIED / local Python 3.14 base runtime unavailable
FULL_REGRESSION = NOT_RUN
RUFF = PASS
DIFF_CHECK = PASS / CRLF conversion warnings only
PRE_RECEIVE_BUDGET_SAFETY = CODED / focused runtime proof pending
CONCURRENT_BUDGET_SAFETY = CODED / focused runtime proof pending
RETRY_ACCOUNTING = CUMULATIVE BY CONTRACT / focused runtime proof pending
S5_OFFLINE_VALIDATION = PENDING
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
GIT_ACTIONS = NONE
SAFE_RESUME_POINT = Run focused tests in functional PowerShell with .venv Python 3.14.7 and external basetemp; full regression only after focused PASS
```

## Continuação corretiva — S5-REAL-UNBLOCK-01 — 2026-10-11

Quatro ajustes foram aplicados em S5: `UNKNOWN_SIZE` previamente excluído não
rejeita itens pendentes elegíveis; a fila conta chunks efetivamente recebidos
mesmo quando uma tentativa sem teto falha; o fake registra o pedido de payload
somente após adquirir a reserva; e o fake cede execução entre reserva e resposta
para exercitar dois workers. O mecanismo de reserva permanece atômico e não
mantém o lock durante a transferência. Nenhuma alteração foi feita no downloader
S4, gateway, SQLite, CLI ou contrato congelado.

`ruff check src tests` e `git diff --check` passaram. A primeira tentativa
focada não conseguiu criar `tmp_path` no `%TEMP%` do executor; a tentativa com
basetemp externo sob workspace gravável coletou os casos, mas ficou parada no
primeiro teste de fila sem resultado. O executor daqui não produziu evidência
funcional suficiente; a suíte focada precisa ser executada no PowerShell
funcional. Regressão completa não iniciada. Não executar o preview nem a fila
real até os focados e a regressão passarem.

```text
ACTIVITY = S5-REAL-UNBLOCK-01 — Corrective Continuation
ACTIVITY_COMPLETION_PERCENT = 36%
STATUS = PARTIAL / CORRECTIONS APPLIED; FOCUSED TESTS NOT VERIFIED
ROOT_CAUSES = UNKNOWN_SIZE excluded rows blocked eligible work; unbudgeted failures could lose short received chunks; request fake recorded before admission; immediate fake did not exercise worker overlap
UNKNOWN_SIZE_HANDLING = EXCLUDED ITEMS NO LONGER REJECT THE PLAN; UNKNOWN SIZE IS STILL NOT TRANSFERRED
WORKER_CONCURRENCY = TWO WORKERS REMAIN AVAILABLE; FAKE YIELDS AT THE REQUEST/RESPONSE BOUNDARY
BUDGET_RESERVATION = ATOMIC SHARED RESERVATION; LOCK NOT HELD DURING DOWNLOAD
BYTE_ACCOUNTING = RECEIVED CHUNKS COUNTED FOR FAILED UNBUDGETED ATTEMPTS; BUDGETED PATH USES RESERVATION SETTLEMENT
FAKE_GATEWAY_COMPATIBILITY = S5 FAKE ACCEPTS reserve_chunk; NO SIGNATURE MISMATCH FOUND IN THE ACTIVE S5 FLOW
PRE_RECEIVE_BUDGET_SAFETY = EXISTING GATEWAY RESERVATION KEPT BEFORE REQUEST; FAKE NOW RECORDS ONLY ADMITTED PAYLOAD REQUESTS
FOCUSED_TESTS = BLOCKED IN EXECUTOR / first attempt tmp_path denied; retry stalled at first queue test without result
FULL_REGRESSION = NOT_RUN
RUFF = PASS
DIFF_CHECK = PASS
S5_OFFLINE_VALIDATION = PENDING
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
GIT_ACTIONS = NONE
SAFE_RESUME_POINT = Run focused tests in functional PowerShell with basetemp outside the repository; run full regression only after focused PASS. Do not run real preview or queue.
```

Comando para continuar no PowerShell funcional:

```powershell
$S5Temp = Join-Path $env:TEMP ("telegram-s5-focused-" + [guid]::NewGuid().ToString('N'))
$S5FullTemp = Join-Path $env:TEMP ("telegram-s5-full-" + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest tests/unit/test_s5_queue_policy.py tests/integration/test_s5_download_flow.py tests/unit/test_downloads.py tests/integration/test_download_flow.py tests/unit/test_telethon_gateway.py -q -p no:cacheprovider --basetemp $S5Temp
if ($LASTEXITCODE -ne 0) { throw 'Focused S5 tests failed' }
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $S5FullTemp
if ($LASTEXITCODE -ne 0) { throw 'Full regression failed' }
.\.venv\Scripts\ruff.exe check src tests --no-cache
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Diff check failed' }
```

## Checkpoint corrente — S5-REAL-UNBLOCK-01 — 2026-10-11

A callback S5 anterior debitava os bytes após o chunk ser recebido. O adapter
Telethon 1.45.x foi inspecionado localmente: a igualdade
`request_size == chunk_size` usa o iterador direto sem prefetch; cada pedido
`GetFile` pode ser interceptado antes do envio. A correção agora reserva o
payload máximo por pedido, num orçamento compartilhado e atômico. A reserva
vira bytes recebidos ao retorno do pedido; fim normal libera reserva sem dados;
erro/cancelamento em voo consome a reserva inteira como incerteza. O caminho
limitado desliga retries RPC ocultos enquanto há streams ativos e restaura a
configuração original ao final. Retries explícitos da fila mantêm o saldo
cumulativo. O contrato S5 foi atualizado somente no adendo de limite byte.

O Ruff e `git diff --check` passaram. A única tentativa de pytest usou o venv
prescrito, `-p no:cacheprovider` e `--basetemp` fora do repositório; 53 casos
pararam no setup porque o executor não conseguiu criar diretórios `tmp_path`.
Nenhum corpo de teste foi executado, portanto focados e regressão completa
permanecem pendentes. Não repetir pytest neste executor. O catálogo RASMOO
isolado ainda existe e foi conferido somente leitura (`integrity_check=ok`, um
canal, 589 nós, 26 mídias); a nova prévia do planner do Módulo A não foi
executada enquanto o controle preventivo aguarda validação funcional.

Limites CLI confirmados no código: `--max-media-items` e
`--max-transfer-bytes` são opcionais em `download plan|queue`, positivos quando
informados; a ausência mantém execução normal sem teto agregado. Nenhuma CLI
de fila foi executada. Nenhum acesso Telegram/sessão, download, escrita SQLite
ou ação Git ocorreu.

```text
ACTIVITY = S5-REAL-UNBLOCK-01
ACTIVITY_COMPLETION_PERCENT = 56%
STATUS = PARTIAL / PREVENTIVE CODE PRESENT; FUNCTIONAL TESTS AND NEW PREVIEW PENDING
ROOT_CAUSE = Budget callback ran after a chunk had already arrived
STREAMING_REQUEST_BOUNDARY = Telethon 1.45.x GetFile request, gated before _request
CHUNK_CONTROL = request_size == chunk_size <= 256 KiB; direct iterator; no prefetch
PREFETCH_BEHAVIOR = NONE ON THE PINNED DIRECT PATH / source inspected locally
BUDGET_RESERVATION = Atomic shared per-request maximum payload allowance
BUDGET_ACCOUNTING = RECEIVED plus uncertain in-flight allowance; no double count
CONCURRENT_BUDGET_SAFETY = IMPLEMENTED / synthetic runtime test pending
RETRY_BUDGET_SAFETY = IMPLEMENTED / retry and uncertain request bytes persist
CANCELLATION_SAFETY = IMPLEMENTED / in-flight reservation conservatively charged
LIMIT_ENFORCEABILITY = PENDING_VALIDATION
FOCUSED_TESTS = BLOCKED / 53 fixture-setup errors before test bodies; external temp denied
BUDGET_TESTS = NOT_RUN
FULL_REGRESSION = NOT_RUN
RUFF = PASS
DIFF_CHECK = PASS
RASMOO_CATALOG = READ_ONLY / integrity ok; 1 channel, 589 nodes, 26 media
MODULE_A_ELIGIBILITY = PREVIEW_PENDING / expected 5 lessons, 5 media, 73071671 bytes
PLANNER_PREVIEW = NOT_RUN / await functional validation
LIMIT_CHECK_RESULT = NOT_RUN
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PENDING
S5_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Run the prepared focused and full offline PowerShell suites with an external basetemp; if they pass, run the read-only Module A plan with the selected catalog copy and configured 5-item/83886080-byte caps. Do not run the queue.
```

PowerShell para validação no ambiente funcional do usuário:

```powershell
$S5RunToken = [guid]::NewGuid().ToString('N')
$S5FocusedTemp = Join-Path $env:TEMP "telegram-s5-unblock-focused-$S5RunToken"
$S5FullTemp = Join-Path $env:TEMP "telegram-s5-unblock-full-$S5RunToken"
.\.venv\Scripts\python.exe -m pytest tests/unit/test_s5_queue_policy.py tests/integration/test_s5_download_flow.py tests/unit/test_downloads.py tests/integration/test_download_flow.py tests/unit/test_telethon_gateway.py -q -p no:cacheprovider --basetemp $S5FocusedTemp
if ($LASTEXITCODE -ne 0) { throw 'Focused S4/S5 tests failed' }
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $S5FullTemp
if ($LASTEXITCODE -ne 0) { throw 'Full regression failed' }
.\.venv\Scripts\ruff.exe check src tests --no-cache
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
```

Após todos os testes passarem, executar somente a prévia read-only abaixo e
selecionar “Módulo A” pelo menu contextual. Não executar `download queue`:

```powershell
$S5CatalogCopy = 'C:\Users\walac\AppData\Local\Temp\telegram_courses_s3_290a03e24df04921bdda86dd0dcaec80\rasmoo_catalog.sqlite3'
$S5ChannelId = [long](Read-Host 'Confirme o channel_id do catálogo RASMOO')
$S5PreviewRoot = Join-Path $env:TEMP 'telegram-s5-module-a-preview-readonly'
.\.venv\Scripts\python.exe -m telegram_courses download plan --database $S5CatalogCopy --download-dir $S5PreviewRoot --channel-id $S5ChannelId --scope module --max-media-items 5 --max-transfer-bytes 83886080
```

## Checkpoint corrente — S5-REAL-PREP-02 — 2026-10-11

Foi implementado um perfil opcional de segurança para execuções S5 controladas:
`--max-media-items` e `--max-transfer-bytes` em `download plan|queue`. Sem as
opções, a ferramenta mantém o comportamento normal sem teto global de mídias.
O planner/CLI reporta contagens, bytes pendentes, limites configurados e
resultado da checagem. A fila confere o plano recalculado antes dos workers;
uma única reserva compartilhada cobre os tamanhos esperados concorrentes,
chunks recebidos viram bytes consumidos, e falhas/retries não reiniciam o
orçamento. Tamanho desconhecido reprova o perfil byte-capped. O contrato ganhou
um adendo delimitado S5-REAL-PREP-02; não houve mudança de deduplicação S4.

O adapter confirma identidade e tamanho anunciado antes de streaming, com
chunks de até 256 KiB. O teto conta payload de mídia recebido/entregue à
aplicação e exclui overhead de protocolo. O fluxo sem limite configurado não é
restringido permanentemente.

O catálogo RASMOO informado foi aberto em leitura somente e copiado via SQLite
Online Backup. A cópia passou `integrity_check=ok` e zero FKs; a migration 004
foi aplicada somente nela. A cópia segue retida fora do repositório porque o
executor reportou um handle SQLite aberto ao tentar removê-la. O recheck final
da origem preservou 30 mensagens,
26 mídias, 589 nós, quatro fontes unresolved, zero downloads e schema 1–3. Há
47 módulos ativos: 43 vazios e quatro com 5, 6, 7 e 8 mídias elegíveis. Nenhum
módulo completo satisfaz o recorte de 2–3 mídias; não houve seleção artificial.
A referência S4 está disponível e não foi modificada.

`planner.build()` e a suíte focused não foram validados funcionalmente neste
executor. O venv não encontra o Python 3.14 base; o Python alternativo prende
ao criar o socketpair do Windows Proactor. O Ruff sem cache e `git diff --check`
passaram. Não ocorreu Telegram, sessão, credenciais, gateway, stream, download,
escrita no SQLite original ou operação Git.

```text
ACTIVITY = S5-REAL-PREP-02
ACTIVITY_COMPLETION_PERCENT = 88%
STATUS = PARTIAL / IMPLEMENTED; FUNCTIONAL TESTS AND NATURAL CANDIDATE UNAVAILABLE
S3_CATALOG_AVAILABLE = YES / read-only audit PASS
S4_REFERENCE_AVAILABLE = YES / untouched
CANDIDATE_FOUND = NO / active populated modules contain 5–8 media each
MODULE_SELECTION = NONE
LESSON_COUNT = N/A
MEDIA_COUNT = N/A
TOTAL_EXPECTED_BYTES = N/A
PLANNER_PREVIEW = NOT_RUN / no candidate met the full-module 2–3-media constraint
ELIGIBILITY = NO NATURAL CANDIDATE FOUND
MEDIA_LIMIT_IMPLEMENTED = YES / optional; uncapped by default
BYTE_LIMIT_IMPLEMENTED = YES / shared reservation and per-chunk accounting
CONCURRENT_BUDGET_SAFE = IMPLEMENTED / runtime test blocked
RETRY_BUDGET_SAFE = IMPLEMENTED / runtime test blocked
FOCUSED_TESTS = BLOCKED / supported Python 3.14 runtime unavailable
FULL_REGRESSION = NOT_RUN
RUFF = PASS
DIFF_CHECK = PASS
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
SOURCE_DATABASE_MODIFICATION = NO
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PENDING
S5_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Run focused tests in functional Python 3.14 PowerShell; then obtain a natural 2–3-media module or wait for a user decision to adjust candidate constraints
```

## Checkpoint anterior — S5-REAL-ENTRY-01 — 2026-10-11

O usuário forneceu a evidência funcional pós-correção: Python 3.14.7,
testes focados 9 PASS, regressão completa 195 PASS + 11 subtests PASS, Ruff
PASS e diff check PASS, todos com exit 0. Ela reconcilia
`S5_OFFLINE_IMPLEMENTATION = COMPLETE` e `S5_OFFLINE_VALIDATION = PASS`;
nenhuma regressão foi repetida. S5 permanece `IN_PROGRESS` e o aceite formal
continua `PENDING`.

Foi encontrada `data/catalog.sqlite3`, mas a inspeção foi estritamente local e
somente leitura. O arquivo tem integridade SQLite `ok`, duas linhas de canal,
zero `catalog_nodes`, cinco mídias sem vínculo a nó, zero linhas `downloads`,
zero canal cujo título corresponda a RASMOO e zero violações de FK. Uma cópia
isolada foi criada com `Connection.backup()` a partir da origem aberta com
`mode=ro` e `query_only=ON`; a cópia passou `integrity_check=ok` e foi removida
após a inspeção. Esse arquivo corresponde ao snapshot parcial S2 já registrado,
não ao catálogo RASMOO anteriormente evidenciado com 30 mensagens e 26 mídias.

Não há curso/módulo/aula selecionável nessa cópia. Portanto, não foi construído
planner preview nem escolhido candidato; `CANDIDATE_STATUS = BLOCKED`. Não se
expuseram títulos, mensagens, nomes de arquivo ou identidades de mídia. Não
foram aplicadas migrations, nem houve sessão/acesso Telegram, gateway,
streaming, arquivos de mídia, mudanças no banco original, código, staging,
commit ou push.

A CLI e os parâmetros S5 existentes foram conferidos no código: `download
plan|queue`, `--database`, `--download-dir`, `--channel-id`, `--scope` e
`--workers` (1–2, padrão 2); `--confirm` aplica-se somente a `queue`. Não
existem limites CLI para total de itens ou bytes pendentes. A margem S5 de
disco não é um limite de transferência. Assim, `MAX_MEDIA_ITEMS = 3` e
`PREFERRED_TOTAL_BYTES <= 30 MiB` não podem ser impostos de forma confiável
pela fila atual. Antes de qualquer download real, propor alteração pontual ao
contrato congelado e à fila/CLI: limites de itens e bytes aplicados à mesma
seleção recém-calculada, antes de criar gateway/worker ou alterar SQLite, com
testes de rejeição acima do teto e zero efeitos colaterais. Não implementada
nesta atividade.

O procedimento PowerShell A–F e a cópia somente leitura estão em
[LAST_HANDOFF](handoff/LAST_HANDOFF.md). A próxima retomada requer o caminho da
cópia correta RASMOO; depois, selecionar naturalmente um único módulo completo
com 2–3 mídias elegíveis, sem unresolved/out-of-scope e até 30 MiB, e fechar o
hard-cap antes de pedir autorização separada para transferir.

```text
ACTIVITY = S5-REAL-ENTRY-01
ACTIVITY_COMPLETION_PERCENT = 88%
STATUS = PARTIAL / SOURCE CATALOG AND HARD LIMITS BLOCK REAL PREVIEW/EXECUTION
S5_OFFLINE_IMPLEMENTATION = COMPLETE / USER-PROVIDED EVIDENCE
S5_OFFLINE_VALIDATION = PASS / 9 FOCUSED; 195 FULL + 11 SUBTESTS
CATALOG_FILE_PRESENT = YES / data/catalog.sqlite3; NOT THE RASMOO CATALOG
SQLITE_SOURCE_READ_ONLY = PASS
TEMPORARY_COPY = BACKUP PASS / INTEGRITY PASS / REMOVED
CANDIDATE_STATUS = BLOCKED
PLANNER_PREVIEW = NOT_RUN / ZERO SELECTABLE CATALOG NODES
ITEM_LIMIT_ENFORCEABLE = NO / HARD CLI GUARD ABSENT
BYTE_LIMIT_ENFORCEABLE = NO / HARD CLI GUARD ABSENT
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
SOURCE_CODE_CHANGES = NONE
GIT_ACTIONS = NONE
S5_REAL_VALIDATION = PENDING
S5_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Obtain correct RASMOO SQLite copy; repeat A/B preflight; resolve contract and queue hard caps before any real queue execution
```

## Checkpoint corrente — S5-FIX-01-CONTINUATION — 2026-10-11

O usuário informou que a correção de `parent["is_active"]` passou, restando
uma falha: a segunda execução esperava dois outcomes `ALREADY_VALID`, mas
recebia zero. Evidência anterior à correção: focused 1 passed / 1 failed;
full regression 193 passed / 1 failed / 11 subtests passed; Ruff e diff PASS.

A expectativa do teste era correta: `DownloadQueue.run()` inclui itens
`plan.already_valid` nos outcomes mesmo quando `pending` está vazio. O defeito
estava na representação física do candidato no planner: ele usava ancestralidade
Curso/Módulo/Aula, enquanto o SQL de `DownloadRepository.select_candidate()`
do S4 retorna somente a Aula ligada à mídia. Assim, S4 gravava arquivos em um
caminho e o planner reconstruído esperava outro, classificando os registros
como `BLOCKED / DOWNLOAD_ROOT_CHANGED`, em vez de reconhecer arquivos válidos.

A menor correção foi alinhar a linhagem física do candidato S5 ao S4 vigente;
a ancestralidade completa continua validando seleção e ordenação. Nenhuma
alteração foi feita nesta atividade no S4, deduplicação, migrations, contratos,
parser ou transferência. A fila vazia agora também emite o mesmo resumo
agregado da fila com pendências. Não se enfileiram itens já válidos.

O teste integrado foi parametrizado para módulo (duas mídias) e curso (três
mídias, incluindo a aula do módulo irmão). Verifica equivalência do candidato
com S4, limites do escopo, exclusão por tamanho desconhecido, conclusão,
unicidade das identidades e das linhas `downloads`, integridade/FKs SQLite,
arquivos finais exatos, SHA-256/tamanhos/conteúdo, ausência de `.part`, dados e
mtime preservados. Após reconstrução exige zero pendências/bloqueios,
zero novas chamadas de download/streaming, zero novos workers, zero tentativas
e bytes, outcomes `ALREADY_VALID` e resumo agregado consistente. As expectativas
originais de deduplicação foram mantidas e ampliadas.

Uma única tentativa de pytest neste sandbox falhou no setup `tmp_path`, antes
do corpo do teste: não conseguiu criar o diretório numerado no basetemp externo.
Não houve repetição nem execução da regressão completa. O launcher também
avisou sobre a localização do interpretador-base, mas executou a sonda Python;
esse aviso não demonstra a causa do bloqueio. Ruff completo sem cache PASS e
fontes Python modificadas parseadas com sucesso.

A sonda síncrona isolada usou somente migrations existentes, SQLite sintético
e dois arquivos sintéticos fora do repositório, depois removidos. Usou o SQL
exato extraído do seletor S4 para provar a diferença antiga; os planos de curso
e módulo corrigidos reconheceram dois arquivos por tamanho/hash. O caminho
da fila sem pendências retornou dois `ALREADY_VALID`, zero tentativas/bytes e
resumo coerente, sem aplicação de download ou gate de disco. O dump SQLite
ficou idêntico, integridade OK e somente dois arquivos. Isso valida somente
planner/fila vazia; não substitui teste integrado de streaming, concorrência,
primeira transferência ou regressão.

Pins do binding adotado PM-00..05, VP-01 e CONTINUITY foram conferidos por
SHA-256: todos correspondem. Foi encontrada defasagem em ROADMAP/SPRINTS,
que ainda mostram S5 PLANNED / NOT_STARTED. A autorização explícita atual,
contrato congelado e PROJECT_STATE delimitam a correção; não houve migração
de governança, avanço de fase ou aceite. O safe resume e os comandos estão no
[LAST_HANDOFF](handoff/LAST_HANDOFF.md); estado corrente em
[PROJECT_STATE](PROJECT_STATE.md).

```text
ACTIVITY = S5-FIX-01-CONTINUATION
ACTIVITY_COMPLETION_PERCENT = 88%
STATUS = PARTIAL / CORRECTION PRESENT; FUNCTIONAL PYTEST PENDING
ROOT_CAUSE = PLANNER_S4_PHYSICAL_LINEAGE_MISMATCH
BUG_IN_IMPLEMENTATION = YES
TEST_EXPECTATION_INCORRECT = NO
SYNCHRONOUS_SYNTHETIC_PROBE = PASS / NOT TRANSFER INTEGRATION
FOCUSED_TESTS = BLOCKED_BEFORE_TEST_BODY / POST_CORRECTION_PENDING
FULL_REGRESSION = PENDING / PRIOR_USER_EVIDENCE_193_PASS_1_FAIL_11_SUBTESTS
RUFF = PASS / src tests --no-cache
DIFF_CHECK = PASS
S5_OFFLINE_VALIDATION = PENDING
S5_FORMAL_ACCEPTANCE = PENDING
REAL_TELEGRAM_SQLITE_DOWNLOAD_ACCESS = NONE
GIT_ACTIONS = NONE / NO STAGING, COMMIT OR PUSH
```

## Checkpoint anterior — S5-IMPL-01 — 2026-10-11

O pedido atual autorizou implementação offline S5 e congelou o contrato com:
dois workers por padrão (limite 1–2), três tentativas por mídia incluindo a
inicial, até 120 segundos de FloodWait acumulado por mídia, margem de disco
`MAX(1 GiB, 10% dos bytes pendentes conhecidos)`, mídias sem tamanho excluídas,
fila efêmera e estado persistido pelo S4. O contrato está
APPROVED / FROZEN; S5 permanece IN_PROGRESS e a aceitação formal, PENDING.

A implementação adiciona seleção e planner somente leitura, fila que delega
transferências a `SingleMediaDownloadApplication`, propagação de
`retry_after_seconds`, limites de disco/retries/workers, progresso Rich e teste
integrado sintético com SQLite/filesystem temporários. Ruff completo e
`git diff --check` passaram. O pytest focado não iniciou no sandbox: setup do
diretório temporário falhou inicialmente e a execução subsequente ficou parada
no ambiente de `asyncio`/`aiosqlite`; foi interrompida conforme o pedido. Não
classificar como defeito de código sem evidência. Full pytest não foi executado.

Não houve acesso a Telegram, credenciais, sessão, SQLite real ou mídia real.
Não houve staging, commit ou push. O HEAD permanece
`e1e9f734e1cff0e105ab2135b7b09090465e2ac8`, branch `work/s0-bootstrap`.

```text
ACTIVITY = S5-IMPL-01
ACTIVITY_COMPLETION_PERCENT = 76%
STATUS = PARTIAL / IMPLEMENTATION PRESENT; TEST EXECUTION BLOCKED
CONTRACT_STATUS = APPROVED / FROZEN
IMPLEMENTATION_STATUS = PRESENT / FUNCTIONAL VALIDATION PENDING
FOCUSED_TESTS = BLOCKED / pytest sandbox temp and asyncio/aiosqlite execution
OFFLINE_INTEGRATION = NOT_CONFIRMED
FULL_PYTEST = NOT_RUN
RUFF = PASS
DIFF_CHECK = PASS
S5_FORMAL_ACCEPTANCE = PENDING
S5_REAL_VALIDATION = NOT_AUTHORIZED
SAFE_RESUME_POINT = Run focused S5 integration and full pytest in functional PowerShell with an external basetemp and cacheprovider disabled; reconcile results before acceptance
```

## Checkpoint anterior — S5-ENTRY-01 — 2026-10-10

O draft de entrada e as decisões que motivaram este contrato foram preparados
em S5-ENTRY-01. Este checkpoint é histórico; o freeze e a autorização atuais
vieram da instrução explícita S5-IMPL-01.

## Checkpoint anterior — S4-CLOSE-01 Formal Acceptance and Publication — 2026-10-10

S4 foi formalmente aceita e encerrada. Os resultados offline informados pelo
usuário foram: 19 testes focados, 186 testes completos e 11 subtests aprovados;
Ruff e `git diff --check` passaram. A prova real foi limitada a uma mídia
DOCUMENT de Lesson, com tamanho esperado e transferido de 6.199.635 bytes,
exit 0, arquivo final íntegro e hash local igual ao SQLite isolado.

Na segunda chamada, o resultado informado foi `ALREADY_DOWNLOADED`, exit 0 e
sem progresso de transferência. A verificação posterior somente leitura
informada pelo usuário confirmou uma linha de download, um arquivo final,
nenhum `.part`, estado `DOWNLOADED`, tamanho e SHA-256 correspondentes; nenhum
caminho privado foi registrado. Não houve nova transferência nesta atividade.

O gate vertical passa com evidências S1–S3 para autenticação, descoberta,
parsing e catálogo, e a evidência integrada S4 para download individual,
integridade, organização e deduplicação. O aceite cobre apenas uma mídia. Fila
ou lote pertence à S5, resume por offset à S6, sincronização incremental à S7
e validação integrada abrangente no canal RASMOO à S9. S5 está PLANNED /
NOT_STARTED e sua implementação não está autorizada.

```text
ACTIVITY = S4-CLOSE-01
ACTIVITY_COMPLETION_PERCENT = 100%
S4_STATUS = ACCEPTED / CLOSED
S4_FORMAL_ACCEPTANCE = APPROVED
S4_OFFLINE_VALIDATION = PASS / 19 focused, 186 full, 11 subtests
S4_REAL_DOWNLOAD = PASS / one DOCUMENT, 6199635 bytes
S4_FILE_INTEGRITY = PASS / expected size and local SHA-256 match
S4_SQLITE_PERSISTENCE = PASS / user-provided read-only post-dedup check
S4_REAL_DEDUPLICATION = PASS / ALREADY_DOWNLOADED; no second transfer
S4_REGRESSION = PASS
FIRST_VERTICAL_SLICE_GATE = PASS
AUTH = PASS
CHANNEL_DISCOVERY = PASS
RASMOO_PARSE = PASS
CATALOG_PERSISTENCE = PASS
SINGLE_DOWNLOAD = PASS
FILE_VALIDATION = PASS
PATH_ORGANIZATION = PASS
DEDUPLICATION = PASS
SECOND_RUN_NO_DUPLICATE = PASS
GIT_PUBLICATION = USER_AUTHORIZED / one scoped commit and push; exact result is authoritative in Git
S5_STATUS = PLANNED / NOT_STARTED
S5_IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
SAFE_RESUME_POINT = Review S5 entry conditions; do not implement S5 without separate authorization
```

## Checkpoint corrente — S4-IMPL-01 — 2026-10-10

O repo foi confirmado no baseline aprovado `143c1695f3c0fc1040bf46373d40bdb4c83b559f`, branch `work/s0-bootstrap`; a árvore estava limpa antes da atividade. A divergência anterior em `PROJECT_STATE`/handoff foi reconciliada. O contrato [S4 Single Media Download](../contracts/S4_SINGLE_MEDIA_DOWNLOAD_CONTRACT.md) está congelado para uma única mídia DOCUMENT associada a Lesson, e a implementação offline autorizada está em andamento.

O fluxo adicionado contém query de elegibilidade e linhagem, migration 004 sobre a tabela `downloads` já existente, streaming Telethon limitado, arquivo `.part`, validação de tamanho/SHA-256, finalização sem sobrescrita, estado SQLite, recuperação e deduplicação; a CLI aceita `--channel-id`, `--telegram-message-id`, `--media-ordinal`, `--database` e `--download-dir`. Ruff, compileall e diff check passaram; 8 testes unitários S4 passaram; a migration 001–004 e unicidade foram verificadas em SQLite em memória; a prova Windows sintética de `os.rename` sem sobrescrita passou; 186 testes foram coletados, incluindo 11 novos cenários de integração offline. A execução dos testes SQLite integrados não retornou no executor assíncrono restrito do sandbox e foi interrompida; full pytest permanece pendente no PowerShell funcional. Não houve Telegram real, acesso a credenciais/sessão ou modificação do catálogo real; não houve staging/commit/push.

```text
S4_STATUS = IN_PROGRESS / OFFLINE IMPLEMENTATION
S4_OFFLINE_VALIDATION = PARTIAL / UNIT PASS, INTEGRATION BLOCKED IN SANDBOX
ACTIVITY_COMPLETION_PERCENT = 56%
S4_FORMAL_ACCEPTANCE = PENDING
FIRST_VERTICAL_SLICE_GATE = PENDING
SAFE_RESUME_POINT = Run focused integration and full regression in functional PowerShell; see LAST_HANDOFF
```

## S4-REAL-01B — primeira mídia real e deduplicação — 2026-10-10

O preflight confirmou o runtime Python 3.14.7 e os argumentos da CLI sem
executar download. A origem SQLite foi aberta em modo somente leitura e copiada
por Online Backup; a cópia passou integrity check, zero violações FK, 30
mensagens, 26 mídias, parser Rasmoo e elegibilidade da seleção aprovada. A
migration 004 e o índice único foram verificados somente na cópia. A sessão não
foi inspecionada.

A atividade parou antes da conexão: a checagem oficial da CLI não encontrou
cofre de credenciais configurado neste executor, e uma única tentativa de
migration pela rotina assíncrona ficou bloqueada e foi interrompida. Nenhuma
invocação de download ocorreu; nenhum byte foi transferido; não há `.part` nem
arquivo final desta atividade. A cópia criada dentro do executor não é
reutilizável no PowerShell do usuário. O primeiro download e a segunda chamada
continuam pendentes; não houve nova varredura, outro download ou ação Git.

```text
ACTIVITY = S4-REAL-01B
ACTIVITY_COMPLETION_PERCENT = 28%
STATUS = PARTIAL / PREFLIGHT PASS; BLOCKED BEFORE TELEGRAM CONNECTION
TEMP_SQLITE_CREATED = PASS / consistent online backup; migration 004 only on copy
SQLITE_INTEGRITY = PASS / integrity ok; zero FK violations
DOWNLOAD_EXECUTIONS = 0
TRANSFERRED_BYTES = 0
DEDUPLICATION_CHECK_EXECUTIONS = 0
FIRST_VERTICAL_SLICE_GATE = PENDING
S4_FORMAL_ACCEPTANCE = PENDING
NEW_SCAN = NO
OTHER_DOWNLOADS = NONE
GIT_ACTIONS = NONE
SAFE_RESUME_POINT = Recreate the isolated copy and download directory in the user's functional PowerShell, then run only the authorized selection once; independently validate before the one deduplication invocation
```

## S2 — aceite do scan SQLite real — 2026-10-10

O banco local `data/catalog.sqlite3` foi inspecionado em modo somente leitura,
sem acessar Telegram, credenciais ou sessão. Um único `scan_run` correspondente
foi confirmado como `PARTIAL / MESSAGE_LIMIT`, com 10 mensagens e 5 mídias
persistidas. O checkpoint permaneceu `PARTIAL`, associado ao mesmo run/canal;
seu cursor corresponde à última mensagem confirmada dentro do watermark, sem
avançar além dos dados persistidos.

Integridade SQLite = PASS; foreign keys = PASS; unicidade de mensagem por
canal/ID e mídia por mensagem/ordinal = PASS. Fechar e reabrir o banco preservou
o mesmo estado agregado. A tabela `downloads` está vazia e `data/` contém apenas
o banco e sidecars SQLite; nenhum arquivo de mídia foi baixado.

```text
ACTIVITY = S2 — Real Scan SQLite Acceptance
SCAN_STATUS = PARTIAL / STOP_REASON=MESSAGE_LIMIT
SQLITE_MESSAGES = 10
SQLITE_MEDIA = 5
SCAN_RUN = f91cbbe55540441d84092952e815e7e3 / matching run confirmed
CHECKPOINT = PARTIAL / cursor consistent with committed messages and watermark
FOREIGN_KEYS = PASS / no violations
UNIQUENESS = PASS / no duplicate message or media keys
SQLITE_REOPEN = PASS
DATA_INTEGRITY = PASS / PRAGMA integrity_check=ok
DOWNLOADS = NONE / zero download rows and no media files
S2_FORMAL_ACCEPTANCE = ACCEPTED
S2_STATUS = CLOSED
TELEGRAM_ACCESS_THIS_ACCEPTANCE = NO
CREDENTIALS_OR_SESSION_ACCESSED = NO
CODE_OR_GIT_ACTIONS = NONE
NEXT_ACTION = S3 entry review only; S3 NOT_STARTED and implementation not authorized
```

O aceite cobre o scan real reportado e sua persistência local conforme os
critérios S2. O texto das mensagens não foi lido; os IDs foram comparados
internamente para validar o cursor, sem serem exibidos ou copiados para a
continuidade. Contrato congelado e implementação não foram alterados.

## Checkpoint S2 — implementação integrada offline — 2026-10-10

O contrato S2 foi revisado, aprovado e congelado após incorporar S2-OPEN-01.
Texto integral fica no SQLite local até exclusão explícita, sem expiração
automática; texto vazio é NULL; logs não recebem conteúdo; reconciliação de
remoções remotas permanece fora da S2.

Scanner, boundary de histórico no TelethonGateway, migration inicial SQLite,
repository, persistência transacional, scan runs/checkpoints, retomada e
integração de aplicação/CLI estão implementados. Evidência offline acumulada:
140 testes + 11 subtests, Ruff e `git diff --check` PASS. Gateway fake e bancos
temporários demonstraram scanner → persistência → checkpoint, edição,
idempotência, rollback e recuperação após reinício. Nenhum Telegram real,
credencial ou sessão foi acessado.

S2 permanece `IMPLEMENTED_OFFLINE / REAL_VALIDATION_PENDING / NOT_CLOSED`.
Validação controlada de histórico real exige autorização separada. HEAD factual
na conclusão: `887d3e81036c8be7e43dd2b5fdb66d19704beb88`, branch
`work/s0-bootstrap`; nenhuma ação Git de publicação. Ver [PROJECT_STATE](PROJECT_STATE.md),
[SPRINTS — S2](planning/SPRINTS.md#s2--message-scanner--sqlite-persistence),
[contrato S2](../contracts/S2_MESSAGE_SCANNER_SQLITE_CONTRACT.md) e
[LAST_HANDOFF](handoff/LAST_HANDOFF.md).

## Checkpoint GOV-01 + fechamento formal S1-D — 2026-10-09

Decisão aprovada: `KEEP_PINNED_BASELINE`. Os hashes das cinco fontes
canônicas corresponderam aos pins do binding; as cinco cópias vinculadas em
`docs/continuity/policies/` foram copiadas byte a byte e validadas após a
cópia. Resultado GOV-01: `RESOLVED`, 5/5 matches e zero divergências. O
binding e as fontes canônicas permaneceram inalterados; a observação externa
do `baseline_role` da PM-04 permanece preservada.

O contrato S1-D foi congelado após GOV-01 PASS. A aceitação funcional e a
calibração fornecidas pelo usuário, seleção numérica, regressão completa
(126 testes + 11 subtests), Ruff e diff check atendem aos critérios existentes.
`CONTRACT_FREEZE=PASS`, `S1D_FORMAL_ACCEPTANCE=PASS` e `S1D_STATUS=CLOSED`.
O incidente anterior de leitura do vault e seu risco residual permanecem
registrados, sem nova evidência que justifique reabertura. S2 é apenas a próxima
candidata: não foi iniciada nem autorizada. Ver [PROJECT_STATE](PROJECT_STATE.md),
[contrato S1-D](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md) e
[evidência GOV-01](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md#21-gov-01-adjudication-freeze-contratual-e-aceite-formal-s1-d--2026-10-09).

```text
DOCUMENT_ROLE = CONTINUITY_RECORD
PROJECT_ID = projeto_telegram_courses
RECORDED_AT = 2026-10-09 / America/Sao_Paulo
```

O estado corrente, gates, bloqueios, riscos, autorizações, baseline e safe
resume são mantidos em [PROJECT_STATE.md](PROJECT_STATE.md). O mapa em
[ACTIVE_AUTHORITY_MAP.md](ACTIVE_AUTHORITY_MAP.md) aponta às authorities por
assunto.

Este checkpoint reconcilia o fechamento canônico da S0: SP01-01..10 PASS,
SP01_RESULT PASS e S0_COMPLETION_PERCENT 100%. O replay final de casa está
registrado de forma sanitizada em
[SP01_STACK_WINDOWS](../engineering/evidence/SP01_STACK_WINDOWS.md). O problema
anterior de `ensurepip` é histórico; a causa raiz segue indeterminada e não
bloqueia a validação S0 concluída. PROJECT_COMPLETION_PERCENT permanece
NOT_FORMALLY_DEFINED.

O checkpoint corrente conclui S1-B — Offline Authentication Flow & Telegram
Gateway, após S1-A — Protected Session Foundation. O fluxo, boundary próprio de
autenticação, adapter Telethon e integração CLI foram validados por fakes e
valores sintéticos; pytest completo (50 passed, 8 subtests passed) e Ruff
passaram. A regressão S1-A de DPAPI/ACL também passou. Não houve conexão
Telegram, credencial ou sessão real, nem publicação Git. S1 permanece
IN_PROGRESS; S1-B PASS não fecha a Sprint. O contrato S1-B está congelado em
[S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT](../contracts/S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT.md).

S1-C e S1-C-OFF-01 estão `PASS`; S1 permanece `IN_PROGRESS`, pois descoberta
e seleção de canais continuam pendentes. A sequência factual, adjudicação das
evidências, segurança e limites de verificação independente estão registrados
uma única vez em [PROJECT_STATE](PROJECT_STATE.md). Esta reconciliação não
repetiu autenticação nem conectou ao Telegram.

O pacote anterior foi publicado em `work/s0-bootstrap`, commit
`2be283f04502ff2b6980831cec6445b0b64da102`. Esse é um marco histórico,
não o HEAD corrente. Branch, HEAD, upstream e worktree devem ser descobertos
em runtime. A correção offline S1-C-OFF-01 passou em focused pytest, full
pytest e Ruff. Após um preflight inicialmente bloqueado por configuração
ausente, o usuário configurou o ambiente local e forneceu evidência de sucesso
na autenticação e reutilização de sessão. S1-C está `PASS`; S1 permanece
`IN_PROGRESS`, pois descoberta/seleção de canais segue pendente. A próxima
candidata é S1-D — Channel Discovery & Selection, limitada nesta retomada à
avaliação de escopo, readiness e contrato, sem autorização de implementação
ou descoberta real. Os contratos
[S1-B](../contracts/S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT.md) e
[S0_IMPLEMENTATION_CONTRACT](../contracts/S0_IMPLEMENTATION_CONTRACT.md)
permanecem congelados. Veja [LAST_HANDOFF](handoff/LAST_HANDOFF.md) para retomada.

O preflight inicialmente bloqueado de S1-C-A02 e a autorização limitada
exercida são históricos; essa autorização está esgotada. Nenhuma operação Git
foi feita nesta reconciliação.

S1-TEST-01 — Pytest Environment Diagnosis está `BLOCKED`: a collection local
obteve 55 itens, mas o primeiro teste focado do gateway e uma sonda mínima
`asyncio.run` pararam durante a inicialização do Proactor do Windows, em
`socket._fallback_socketpair`/`accept`. O mecanismo imediato foi confirmado; a
causa inferior do host/venv não foi estabelecida. A revalidação permanece
`PENDING`; suíte completa, Ruff e `git diff --check` não foram executados.
Nenhum acesso Telegram, mudança de código ou operação Git ocorreu. Evidência
sanitizada: [S1_TEST_01_PYTEST_ENVIRONMENT_DIAGNOSIS_2026-10-08](../reports/S1_TEST_01_PYTEST_ENVIRONMENT_DIAGNOSIS_2026-10-08.md).
O checkpoint `e947406dbcab8ef593123f079daa279903805d2c` permanece publicado e
inalterado. O safe resume point daquele diagnóstico foi S1-D Architectural Entry
Review, DIRECT / GPT-6 SOL / HIGH; foi sucedido pela atividade documental
abaixo, sem iniciar implementação de S1-D.

## S1-D — draft arquitetural, 2026-10-08

O pedido atual informou Entry Review PASS e autorizou somente análise e draft.
Foi entregue [S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md),
DRAFT / NOT_APPROVED / NOT_FROZEN. A análise estática do Telethon 1.45.0
distingue payload incidental recebido pela biblioteca de processamento de
conteúdo pela aplicação. Decisões OPEN, divergência de hashes e ponto seguro
têm estado único em [PROJECT_STATE](PROJECT_STATE.md); o contrato contém os
detalhes/evidências. As alterações e o relatório preexistentes de S1-TEST-01
foram preservados; revalidação continua PENDING. Não houve source/test, pytest,
operação Telegram, correção de policies/pins/binding, stage, commit, push ou
novo checkpoint Git. S1-C permanece PASS, S1 em andamento e implementação
S1-D não iniciada.

## S1-D — fechamento de decisões, 2026-10-08

O fechamento autorizado registrou DEC-S1D-01 (payload incidental de
`getDialogs` aceito nos limites definidos) e DEC-S1D-02 (broadcast + megagroup/
supergroup elegíveis) em [APPROVALS_AND_DECISIONS](../governance/APPROVALS_AND_DECISIONS.md).
A recomendação anterior broadcast-only foi marcada superseded; não existia
registro de `FUT-CHDISC-01`, e nenhum foi criado. O contrato em
[S1-D](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md) permanece
DRAFT / NOT_APPROVED / NOT_FROZEN. Completude, resultado parcial, cancelamento,
falhas e restore-only foram reconciliados tecnicamente pelas authorities
existentes. Permanecem OPEN os limites numéricos de descoberta, o perfil de
updates e GOV-01; os cinco hashes divergentes das policies continuam sem
reconciliação. S1-TEST-01 continua PENDING para revalidação. Nenhum código,
teste, policy, pin ou binding foi alterado; pytest, Telegram, sessão/credenciais,
stage, commit e push não foram usados.

## OPEN-04 — prova offline, 2026-10-08

Retomada delimitada em 2026-10-08: Python 3.14.7 e Telethon 1.45.0
confirmados. Fora da restrição anterior, socketpair e asyncio.run passaram.
A única prova sintética subsequente não emitiu trace em 35 segundos de espera
total e foi interrompida. GET_DIFFERENCE_COUNT = NOT_MEASURED; solução pública
= NOT_DEMONSTRATED. O limite MAX_PROOF_ATTEMPTS=1 encerra a exploração técnica
desta atividade. OPEN-04 exige decisão arquitetural humana explícita; contrato
permanece DRAFT / NOT_APPROVED / NOT_FROZEN. Evidência e limites no
[relatório OPEN-04](../reports/S1D_OPEN04_OFFLINE_FEASIBILITY_2026-10-08.md).
DEC-S1D-01/02, OPEN-03 PENDING_MEASUREMENT, GOV-01 UNRESOLVED e revalidação
pytest PENDING foram preservados.

A prova está BLOCKED_ENVIRONMENT / NOT_DEMONSTRATED: import síncrono passou,
mas a sonda isolada de Selector travou no socketpair/accept interno, encerrada
após 8 s. Não há captura simulada de requests nem solução pública suficiente
identificada para o fluxo atual. A evidência e análise estão no
[relatório OPEN-04](../reports/S1D_OPEN04_OFFLINE_FEASIBILITY_2026-10-08.md);
estado e retomada têm authority única em [PROJECT_STATE](PROJECT_STATE.md).
O contrato permanece draft; decisões anteriores, deltas, S1-A/B/C e diagnóstico
S1-TEST-01 foram preservados. Nenhum source/test, acesso Telegram, sessão real,
binding ou publicação Git. Recuperação do executor e eventual investigação
arquitetural dependem de escopo próprio; OPEN-03/GOV-01 continuam pendentes.

## S1-D — DEC-S1D-03 Documentation & Reconciliation, 2026-10-08

O usuário aprovou DEC-S1D-03 = D_PLUS_C após a auditoria independente. A decisão
permite o processamento interno incidental de `updates.GetDifference` e
`updates.GetChannelDifference` somente no lifecycle delimitado de descoberta,
incluindo inicialização e loop de updates. A restrição anterior
`PROVE_ZERO_GET_DIFFERENCE` está superseded. A aplicação continua proibida de
usar conteúdo incidental; não há garantia de zero RPC, ausência de mensagens ou
apagamento seguro em memória. A decisão e seus limites estão registrados em
[APPROVALS_AND_DECISIONS](../governance/APPROVALS_AND_DECISIONS.md), e o contrato
reconciliado em [S1-D](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md).

OPEN-04 arquitetural = RESOLVED; validação técnica = PENDING. OPEN-03 segue
PENDING_MEASUREMENT, GOV-01 segue UNRESOLVED, revalidação de pytest segue
PENDING. DEC-S1D-01/02 preservadas. Contrato segue DRAFT / NOT_APPROVED /
NOT_FROZEN, S1D_DOR = NOT_PASS e implementação NOT_STARTED / NOT_AUTHORIZED.
Próxima atividade: preparar os critérios e evidências restantes para revisão
separada de aprovação/freeze. Nenhum source/test, pytest, Telegram, credencial,
sessão real ou operação Git foi usado. O estado único e safe resume point estão
em [PROJECT_STATE](PROJECT_STATE.md).

## S1-D — implementação e revalidação offline, 2026-10-09

O usuário aprovou o contrato S1-D e seu baseline numérico, e autorizou a
implementação nesta conversa. A implementação e a prova sintética offline
passaram. A revalidação usou PowerShell local independente do executor
restrito: Python 3.14.7 da venv, `socketpair` e `asyncio.run` PASS, collection
96, focused discovery 41 passed e FULL_PYTEST 96 passed + 8 subtests em
158,55 s (exit 0; timeout externo de 180 s não alcançado); Ruff PASS. A falha
anterior com WinError 10013 e o diagnóstico com watchdog de 30 s permanecem
observações históricas do ambiente restrito/diagnóstico, não resultado da
execução final. Não houve rede Telegram, acesso a sessão/credenciais nem ação
Git. O contrato está aprovado, mas não congelado: GOV-01 ainda bloqueia freeze.
O aceite requer calibração operacional e validação real delimitada com
autorização específica. Estado e safe resume únicos em
[PROJECT_STATE](PROJECT_STATE.md); checkpoint de gates no §20 do
[contrato S1-D](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md).

## S1-D — precheck de validação real, 2026-10-09

O usuário autorizou uma validação real delimitada. O precheck parou antes da
CLI: o artefato de sessão DPAPI esperado não existe e as variáveis de API não
estão configuradas nos escopos Process/User/Machine. Nenhuma credencial ou
conteúdo de sessão foi lido; nenhuma conexão, login ou operação remota ocorreu.
A autorização não congela o contrato nem remove GOV-01, que continua bloqueando
freeze. A atividade fica `BLOCKED_PRECHECK`; retomar a mesma autorização somente
após sessão protegida válida e credenciais locais disponíveis, sem iniciar login.
Evidência sanitizada: [S1D_REAL_DISCOVERY_VALIDATION_2026-10-09](../reports/S1D_REAL_DISCOVERY_VALIDATION_2026-10-09.md).
O estado e o safe resume point únicos permanecem em [PROJECT_STATE](PROJECT_STATE.md).

## S1-D — correção offline da resposta de 101 diálogos, 2026-10-09

O usuário reportou a primeira execução real: o adapter solicitou 100 e recebeu
101 diálogos, classificando como `ADAPTER_FAILURE` antes de projetar qualquer
candidato. A origem no guard local foi confirmada; não houve exceção original
Telethon. A correção aceita apenas overflow da primeira resposta explicado por
linhas explicitamente marcadas como fixadas, conta todas no teto bruto e
preserva os limites aprovados. Testes unitários e integração CLI foram escritos
com objetos Telethon e transporte falso. Ruff passou; coleta focada/full passou
(24/109 itens), mas execução dos testes bloqueia porque `asyncio.run` mínimo
pendura neste executor. Nenhum acesso real foi repetido. Estado e safe resume
em [PROJECT_STATE](PROJECT_STATE.md); nova tentativa Telegram permanece
`PENDING_RETRY` e requer autorização separada.

## S1-D — Telegram API Credentials Vault, 2026-10-09

O usuário autorizou explicitamente a implementação offline do vault persistente
de credenciais Telegram. O vault reutiliza DPAPI CurrentUser e as verificações
de ACL existentes, grava em `credentials.dpapi` separado de `session.dpapi`,
usa payload versionado e gravação atômica sem sobrescrita. A CLI adiciona
`credentials setup` com API HASH oculto e `credentials status` sem exposição de
valores; auth e channels resolvem um par completo de ambiente antes do vault e
rejeitam variáveis incompletas sem misturar origens.

Validação com apenas valores sintéticos: focused 29 passed + 11 subtests;
integração DPAPI CurrentUser Windows 1 passed; regressão final 110 passed + 11
subtests em 169,05 s (exit 0); Ruff PASS. Nenhuma credencial real foi lida ou
configurada, a sessão DPAPI real não foi aberta, e nenhuma rede Telegram foi
usada. Evidência completa em
[S1D_CREDENTIALS_VAULT_2026-10-09](../reports/S1D_CREDENTIALS_VAULT_2026-10-09.md).

O resultado reportado anteriormente continua registrado como
`ADAPTER_FAILURE / PAGES_REQUESTED=1 / PAGES_RECEIVED=1 /
RAW_DIALOGS_RECEIVED=101`; o vault não corrige nem reavalia esse erro. O usuário
deve configurar o vault localmente com `telegram-courses credentials setup`,
verificar com `telegram-courses credentials status` e confirmar a disponibilidade
de uma sessão protegida antes de retomar a validação delimitada já autorizada.
DEC-S1D-01/02/03 e OPEN-03 permanecem inalteradas; GOV-01 ainda bloqueia freeze.
Estado e safe resume point únicos em [PROJECT_STATE](PROJECT_STATE.md).

## Checkpoint consolidado S1-D — 2026-10-09

Conforme instrução direta do usuário nesta atividade, S1-A/B/C e o vault de
credenciais estão PASS. S1-D está `IMPLEMENTED / REAL_FUNCTIONAL_PASS /
FINAL_ACCEPTANCE_PENDING`; descoberta real, descoberta de broadcast e
megagroup, seleção local e correção do adapter em cenário real estão PASS.
DEC-S1D-01/02/03 e OPEN-03 permanecem aprovadas. `CONTRACT_FREEZE` não foi
confirmado; GOV-01 é dependência externa. S1-D não está CLOSED.

A regressão mais recente informada pelo usuário foi 109 passed, 1 failed,
11 subtests passed em 183.63s (`FULL_REGRESSION=NOT_PASS`). As evidências
disponíveis não identificam arquivo, teste ou mensagem da falha nem sua causa;
causa permanece desconhecida. A suíte não foi executada novamente nesta
atividade. A próxima melhoria aprovada para CLI é seleção numérica de canais
por índice, mantendo o `telegram_chat_id` estável internamente, permitindo Q
para cancelar, rejeitando índices inválidos, sem nova consulta Telegram e sem
ações remotas; testes devem ser offline. A melhoria está aprovada e não
implementada. O safe resume é `S1-D — Regression Fix + CLI Numeric Selection`;
detalhes vigentes em [PROJECT_STATE](PROJECT_STATE.md) e
[LAST_HANDOFF](handoff/LAST_HANDOFF.md).

## S1-D — Regression Fix + CLI Numeric Selection, 2026-10-09

A falha foi reproduzida em
`tests/unit/test_auth.py::test_credentials_are_environment_only_and_validated`:
`Failed: DID NOT RAISE ConfigurationError`. O teste fornecia ambiente vazio,
mas o loader usa o vault DPAPI como fallback; um vault configurado na máquina
tornou o teste dependente do ambiente. O teste foi corrigido para injetar vault
sintético vazio. A chamada pré-correção leu/descriptografou o vault local;
nenhum valor foi exibido ou registrado, e `session.dpapi` não foi acessado.
Esta ocorrência está reportada explicitamente na evidência e em
[PROJECT_STATE](PROJECT_STATE.md).

A CLI agora exibe canais numerados em ordem, aceita o índice local ou o ID
completo exato, cancela com entrada vazia/Q e rejeita entradas inválidas. A
identidade de domínio continua `telegram_chat_id`; a seleção usa o snapshot,
inclusive em discovery `PARTIAL`, após o fechamento do gateway e sem nova
chamada de descoberta.

Validação local com Python 3.14.7: focused regression 3 passed; focused CLI 15
passed; full pytest 121 passed e 11 subtests em 184.34s; Ruff PASS; `git diff
--check` PASS. A tentativa inicial no executor isolado bloqueou no socketpair
Proactor antes dos testes; o resultado conclusivo veio do PowerShell local
funcional. Nenhuma conexão Telegram foi feita.

O resultado técnico passou, mas a atividade fica `PARTIAL` porque o teste
pré-correção acessou/descriptografou o vault local, contra a restrição do
pedido. Nenhum valor foi exibido ou registrado. A revisão do incidente e o
aceite final permanecem pendentes. S1-D segue `IMPLEMENTED /
REAL_FUNCTIONAL_PASS / FINAL_ACCEPTANCE_PENDING`. DEC-S1D-01/02/03, OPEN-03 e
GOV-01 não foram alterados. Não declarar fechamento, freeze, remediação,
publicação Git ou início de S2. Evidência:
[S1D_REGRESSION_CLI_NUMERIC_SELECTION_2026-10-09](../reports/S1D_REGRESSION_CLI_NUMERIC_SELECTION_2026-10-09.md).

## S1-D — Credential Isolation Review & Final Acceptance, 2026-10-09

### Incidente e isolamento

O caminho acidental foi: `tests/unit/test_auth.py` chamou
`load_telegram_credentials({})`; em `config.py`, ausência do par na mapping
leva ao construtor padrão `CredentialVault`; esse cria
`_ProtectedCredentialsVault`, que herda `_ProtectedSessionVault` e lê
`credentials.dpapi` via `_load`/DPAPI. A fixture antiga não injetava storage
vazio nesse caso. O teste corrigido injeta um vault sintético vazio.

Busca estática dos demais testes não encontrou outra resolução padrão para o
storage do usuário: usos de CredentialVault/TelethonGateway injetam fakes ou
diretórios temporários; os testes Windows criam artefatos sintéticos em
`tmp_path`; o teste do caminho do repositório espera rejeição. Para fechar a
lacuna global, `tests/conftest.py` agora, por teste, remove
`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_COURSES_CONFIG` e
`TELEGRAM_COURSES_LOG_LEVEL`, e define `LOCALAPPDATA` sob `tmp_path`. O
`unittest` que limpa `os.environ` cria seu próprio `LOCALAPPDATA` temporário.
Testes de regressão confirmam que os fallbacks de credential e session
resolvem somente sob o diretório temporário; nenhum vault/session real é aberto.
O fixture afeta pytest, não o runtime normal da CLI.

O resultado capturado da falha foi apenas `DID NOT RAISE ConfigurationError`;
nenhum valor apareceu no output pytest. A implementação observada sanitiza
exceções e não há caminho de log/export nesse teste. O valor descriptografado
foi materializado em memória no processo de teste, que terminou. Não houve
inspeção forense de memória, crash dumps ou telemetria externa; esses pontos
ficam como risco não verificado, não como evidência de divulgação.

### Verificação da aceitação

Critérios offline AC-01..12: cobertos por fakes, fixtures sintéticas e pela
regressão completa. Seleção numérica e legacy ID estão offline PASS. Discovery
real e seleção por ID real permanecem `PASS_USER_REPORTED`; nenhuma conexão foi
feita nesta atividade. A evidência disponível não contém duração de restore,
discovery/cleanup, contadores/cobertura observados nem comparação aos budgets
aprovados (`page_size=100`, `max_raw_dialogs=1000`, `max_pages=20`, operação
120s, cleanup 10s). O relatório existente da tentativa real anterior registra
`OPERATIONAL_CALIBRATION = NOT_MEASURED`; não foi encontrado registro posterior
com essas medições.

```text
ACTIVITY = S1-D Credential Isolation Review & Final Acceptance
INCIDENT_REVIEW = PASS / root cause and test path identified; no repeat vault access
TEST_ISOLATION = PASS / global pytest temp storage/env isolation + credential/session path regression tests
FOCUSED_PYTEST = PASS / 42 passed, 11 subtests passed
FULL_PYTEST = PASS / 123 passed, 11 subtests passed in 165.76s / Python 3.14.7
RUFF = PASS
DIFF_CHECK = PASS
REAL_TELEGRAM_ACCESS = NO
CREDENTIAL_ACCESS_THIS_ACTIVITY = NO
SECRET_EXPOSURE_EVIDENCE = no values in captured failure/output; external OS telemetry not inspected
RESIDUAL_RISK = prior test process materialized plaintext in memory; external crash/OS telemetry unknown
S1D_OFFLINE_AC01_AC12 = PASS
S1D_REAL_FUNCTIONAL_EVIDENCE = PASS_USER_REPORTED / discovery and ID selection
OPERATIONAL_CALIBRATION = NOT_MEASURED_IN_AVAILABLE_EVIDENCE
S1D_FINAL_VERDICT = NOT_ACCEPTED_YET / operational calibration is an explicit acceptance gate
CONTRACTS_AND_GOVERNANCE = UNCHANGED
GIT_ACTIONS = NONE
```

Conclusão: não declarar S1-D formalmente aceita ainda. Os resultados reais
fornecidos pelo usuário cobrem discovery e seleção por ID, e todos os gates
offline passaram. O aceite do contrato também exige calibração operacional;
ela não está comprovada nos registros disponíveis. Primeiro procurar métricas
sanitizadas da validação já realizada. Só se não existirem, considerar nova
calibração após autorização específica; esta atividade não autoriza conexão.
S1-D não está CLOSED e S2 não foi iniciado. Estado único em
[PROJECT_STATE](PROJECT_STATE.md); handoff em [LAST_HANDOFF](handoff/LAST_HANDOFF.md).

### Checkpoint — calibração operacional S1-D

Revisão dos registros disponíveis confirmou que a primeira descoberta real
falhou no adapter após 1 página solicitada/recebida e 101 diálogos brutos. A
descoberta funcional posterior e a seleção por ID foram reportadas como
aprovadas, mas sem durações, contagens ou resultado COMPLETE/PARTIAL. A causa
específica do overflow de 101 não é demonstrável a partir dos registros.

Telemetria offline foi adicionada ao workflow S1-D. Ela mede com relógio
monotônico operação, restore, descoberta e cleanup, e registra contadores,
budgets, resultado e razão de parada em uma linha sanitizada. Testes verificam
COMPLETE/PARTIAL, sanitização de erro e ausência de identificadores. Focados:
43 passed; suíte completa: 126 passed, 11 subtests; Ruff e diff check: PASS.
Nenhum acesso real foi feito.

```text
METRICS_SUFFICIENT = NO
INSTRUMENTATION_READY = YES
S1D_ACCEPTANCE = PENDING_REAL_OPERATIONAL_MEASUREMENTS
NEXT_ACTION = after separate authorization, run .\.venv\Scripts\telegram-courses.exe channels and retain only S1D_CALIBRATION
REAL_TELEGRAM_ACCESS = NO
```

Relatório atualizado: [S1D real discovery validation](../reports/S1D_REAL_DISCOVERY_VALIDATION_2026-10-09.md).

## S1-D — aceite funcional e checkpoint final, 2026-10-09

Evidência sanitizada da calibração recebida nesta atividade: operação 2.809485s,
restore 0.957923s, discovery 1.315603s e cleanup 0.001170s; cleanup COMPLETE;
4/4 páginas; 313 diálogos brutos. Limites aprovados: página 100, total bruto
1000, páginas 20, operação 120s e cleanup 10s. Resultado/outcome COMPLETE,
sem stop reason ou failure category. Discovery real, broadcast, megagroup e
seleção local PASS; a opção `69` resolveu para o `telegram_chat_id` esperado.
Nenhum download ou scanner foi iniciado.

```text
FUNCTIONAL_ACCEPTANCE = PASS
CONTRACT_FREEZE = BLOCKED_BY_GOV01
FORMAL_CLOSURE = BLOCKED_BY_GOV01 / S1-D NOT CLOSED
DEC-S1D-01/02/03 = APPROVED / PRESERVED
OPEN-03 = APPROVED / limits measured within budget
AC-01..12_OFFLINE = PASS
FULL_PYTEST = PASS / 126 passed, 11 subtests, 167.64s
RUFF = PASS / GIT_DIFF_CHECK = PASS
CREDENTIAL_VAULT = PASS / PYTEST_CREDENTIAL_ISOLATION = PASS
INCIDENT = prior accidental vault read and residual risk preserved; not reopened
REAL_TELEGRAM_ACCESS_FOR_VALIDATION = YES / user-provided evidence
CREDENTIALS_ACCESSED_DURING_THIS_RECONCILIATION = NO
GIT_ACTIONS = NONE
NEXT_PHASE_CANDIDATE = S2 — Message Scanner & SQLite Persistence / not started
```

O aceite funcional satisfaz os critérios registrados no contrato. O contrato
separa aceite de freeze; contudo, GOV-01 continua sem adjudicação e é o requisito
externo que bloqueia freeze e encerramento formal. Não declarar `CLOSED`, não
alterar governança e não iniciar S2. Ver [relatório final S1-D](../reports/S1D_REAL_DISCOVERY_VALIDATION_2026-10-09.md).

## S3 Entry Review & Technical Contract — 2026-10-10

Contrato draft criado em [S3_PARSER_CATALOG_CONTRACT](../contracts/S3_PARSER_CATALOG_CONTRACT.md).
S2 permanece ACCEPTED / CLOSED; S3 permanece PLANNED / NOT_STARTED e não há
autorização de implementação. A entrada foi considerada PARTIAL: as authorities
listam os marcadores RASMOO, mas não documentam sua semântica, e o spike SP-02
requer amostra controlada antes de fechar parser/schema. O contrato deixa
S3-OPEN-01 (gramática/SP-02), S3-OPEN-02 (identidade/reconciliação de nós) e
S3-OPEN-03 (limiar de detecção) explícitos. Tokens ambíguos ficam
unclassified/unresolved; nenhum significado foi inferido.

Foram verificados por leitura o schema/migration S2, models e ports existentes,
declarações de dependências e authorities de S3. Imports de Rich, aiosqlite e
pytest estavam disponíveis no venv; testes não foram executados. Nenhum Telegram,
banco SQLite real, credenciais ou sessão foi acessado. Sem mudanças de
código/testes, sem ações Git; nenhum contrato foi aprovado/congelado.
Reconciliado em [PROJECT_STATE](PROJECT_STATE.md) e
[LAST_HANDOFF](handoff/LAST_HANDOFF.md).

## S3 — SP-02 RASMOO Grammar Validation — 2026-10-10

Foi iniciada uma única operação direcionada ao canal RASMOO identificado pelo
usuário, com limite solicitado de 30 mensagens e orçamento inferior a 120s.
O processo não retornou os contadores sanitizados; foi interrompido antes do
teto. A etapa remota e a quantidade realmente consultada permanecem
desconhecidas, portanto nenhuma segunda tentativa foi feita sob o mesmo teto
cumulativo. Nenhuma saída bruta, download ou persistência local ocorreu. O
caminho local de credenciais/sessão foi invocado sem exibir valores. Nenhum
marcador tem semântica confirmada e S3-OPEN-01/02/03 permanecem abertos.

```text
ACTIVITY_COMPLETION_PERCENT = 88%
STATUS = PARTIAL / NO SANITIZED RESULT
SP02_REQUESTED_MESSAGE_CAP = 30
SP02_ACTUAL_MESSAGE_COUNT = UNKNOWN
SP02_STRUCTURAL_CASES_CAPTURED = 0
REMOTE_ACCESS = ATTEMPTED / SINGLE TARGET
SQLITE_ACCESS = NO
DOWNLOADS = NONE
LOCAL_PERSISTENCE = NONE
RAW_CONTENT_EMITTED = NO
S3_IMPLEMENTATION_AUTHORIZATION = NO
GIT_ACTIONS = NONE
NEXT_ACTION = Obtain a fresh reconciled read budget or sanitized user-provided fixtures
```

## S3 — Offline Catalog Core Implementation — 2026-10-10

O usuário autorizou a implementação offline do núcleo genérico S3. Foram
implementados registry de seleção explícita com fallback Generic, GenericParser
sem inferência de hierarquia, CatalogBuilder, serviço de aplicação offline,
migration aditiva `002_catalog.sql`, repository SQLite transacional e comandos
Rich `catalog build/list/show/items`. A migration S2 não foi alterada. Nós
ausentes em reparsing ficam inativos e não são apagados; identidades genéricas
estáveis são delimitadas por canal/parser/versão/node key. RasmooParser e
autodetecção não foram iniciados.

Validação integral em Python 3.14.7: 157 passed + 11 subtests em 182.02s;
Ruff PASS; `git diff --check` PASS. Os testes usam dados sintéticos e SQLite
temporário. Não foram acessados Telegram, SQLite real, credenciais ou sessão;
não houve download, staging, commit ou push.

## S3 — Generic Catalog Core Git Publication — 2026-10-10

O usuário autorizou a publicação Git seletiva do núcleo genérico offline S3.
S3 permanece IN_PROGRESS; S3-OPEN-01 e SP-02 estão pendentes, o contrato
continua DRAFT e RasmooParser não foi implementado. Esta publicação não acessa
Telegram ou SQLite real. Próxima atividade: S3 — RASMOO Grammar Resolution and
Specialized Parser Implementation, sujeita a autorização própria.

```text
ACTIVITY_COMPLETION_PERCENT = 100%
S3_STATUS = IN_PROGRESS / generic offline core done / formal acceptance pending
S3_IMPLEMENTATION_AUTHORIZATION = YES / offline generic core only
CONTRACT = DRAFT / NOT_APPROVED / NOT_FROZEN
SP02 = INCONCLUSIVE / no sanitized cases / actual message count unknown
S3_OPEN_01 = UNRESOLVED / RASMOO grammar
S3_OPEN_02 = PARTIAL / generic identity validated; specialized anchors open
S3_OPEN_03 = UNRESOLVED / no autodetection
NEXT_ACTION = Obtain sanitized SP-02 fixtures or fresh bounded authorization, then adjudicate S3-OPEN-01
GIT_ACTIONS = NONE
```

## S3 — SP-02 Grammar Resolution — 2026-10-10

O usuário forneceu e confirmou evidência manual suficiente para os formatos
RASMOO suportados de índice e post de mídia. `INDEX_MESSAGE`: `=` Track,
`==` Course, `===` Module e referências `#Fxxx` listadas sob módulos.
`MEDIA_POST`: `#Fxxx <ordinal> <título>` identifica Lesson; a hierarquia do
post é Track sem marcador, `=` Course e `==` Module. A mídia do post é ligada
à Lesson usando a identidade de mensagem/mídia já persistida pela S2; `#Fxxx`
nunca é `telegram_message_id`. `#Docxxx` referencia documento geral; sem
contexto explícito, não se atribui curso ou aula. O RAR é documental, não vídeo.

`S3-OPEN-01 = BASIC GRAMMAR CONFIRMED` para INDEX_MESSAGE + MEDIA_POST.
`S3-OPEN-02 = DETERMINISTIC IDENTITY AND CONSERVATIVE RECONCILIATION`.
Identidade lógica usa escopo de canal/parser/versão/chave semântica; identidade
de Lesson usa `#Fxxx`, documento usa `#Docxxx`, e mídia usa a identidade S2.
Reprocessamento igual é idempotente. Referências ambíguas/incompatíveis ficam
unresolved; não reparentar ou apagar estruturas por inferência.
`S3-OPEN-03 = EXPLICIT PARSER SELECTION`: seleção configurada por canal,
Generic fallback, sem autodetecção.

O contrato e fixtures sintéticas foram atualizados. CASE-03 tem exercício
sintético derivado do mapeamento confirmado, não amostra real. O contrato segue
DRAFT / NOT_APPROVED / NOT_FROZEN. RasmooParser não foi implementado e precisa
de autorização separada. Nenhuma coleta automática, conexão Telegram, SQLite
real, leitura de credenciais, download, teste ou ação Git ocorreu.

```text
ACTIVITY_COMPLETION_PERCENT = 100%
STATUS = PASS / SUPPORTED GRAMMAR AND DECISIONS RECORDED
SP02 = EVIDENCE SUFFICIENT FOR SUPPORTED INDEX + MEDIA POST GRAMMAR
S3_OPEN_01 = BASIC GRAMMAR CONFIRMED
S3_OPEN_02 = DETERMINISTIC IDENTITY AND CONSERVATIVE RECONCILIATION
S3_OPEN_03 = EXPLICIT PARSER SELECTION
CONTRACT = DRAFT / NOT_APPROVED / NOT_FROZEN
FIXTURES = tests/fixtures/rasmoo/sp02
RASMOO_PARSER_IMPLEMENTED = NO / AUTHORIZATION = NOT_GRANTED
GIT_ACTIONS = NONE
NEXT_ACTION = Separate authorization is required before parser implementation
```

## S3 — RasmooParser Integrated Implementation — 2026-10-10

O usuário aprovou a implementação offline e o congelamento do escopo comprovado
por SP-02. O contrato foi atualizado para `APPROVED / FROZEN` somente para
índice, post de mídia e referência documental geral; outras formas continuam
fora das regras confirmadas.

`RasmooParser` integrado; registry usa seleção explícita e Generic fallback.
Associação `#F` requer mesmo canal, referência igual e hierarquia compatível.
`#Doc` permanece documental geral sem associação automática a aula/curso.
A migration `003_catalog_unresolved.sql` persiste mensagens e motivos não
resolvidos; `catalog items` os exibe. Reconciliação não inativa nós nem remove
vínculos quando há qualquer incerteza. Reprocessamento idêntico preserva IDs e
timestamps.

Validação com fixtures SP-02 e SQLite temporário: focados 11 passed; suíte
completa 163 passed + 11 subtests em 183,68 s; Ruff e diff check PASS. Uma
execução inicial paralela a Ruff falhou somente porque o teste de smoke detectou
mudança no cache do Ruff; a repetição isolada passou. Nenhum Telegram, SQLite
real, credenciais/sessão ou download foi acessado. Nenhuma ação Git foi feita.

```text
ACTIVITY_COMPLETION_PERCENT = 100%
ACTIVITY_STATUS = PASS / OFFLINE FUNCTIONAL IMPLEMENTATION AND VALIDATION
S3_STATUS = IN_PROGRESS
S3_CONTRACT = APPROVED / FROZEN_FOR_CONFIRMED_SP02_SCOPE_ONLY
S3_OPEN_01 = BASIC_GRAMMAR_CONFIRMED
S3_OPEN_02 = DETERMINISTIC_IDENTITY_AND_CONSERVATIVE_RECONCILIATION
S3_OPEN_03 = EXPLICIT_PARSER_SELECTION
RASMOO_PARSER = PASS_OFFLINE
REGISTRY_BUILDER_SQLITE_RICH_CLI = PASS_OFFLINE
IDEMPOTENCY = PASS
CONSERVATIVE_RECONCILIATION = PASS
UNRESOLVED_REFERENCE_HANDLING = PASS / PERSISTED_AND_VISIBLE
SP02_FIXTURES = 9 / CASE-03 synthetic only
FOCUSED_TESTS = 11 PASSED
FULL_PYTEST = 163 PASSED + 11 SUBTESTS
RUFF = PASS
DIFF_CHECK = PASS
REAL_TELEGRAM_ACCESS = NO
REAL_SQLITE_ACCESS = NO
DOWNLOADS = NONE
GIT_ACTIONS = NONE
S3_FORMAL_ACCEPTANCE = PENDING / OFFLINE_TESTS_DO_NOT_CLOSE_S3
PROJECT_STATE_RECONCILIATION = PASS
NEXT_ACTION = Plan formal acceptance under separate authority; S3 remains IN_PROGRESS
```

## S3 — Controlled RASMOO Real Validation — bloqueio de identidade — 2026-10-10

O usuário autorizou uma única validação integrada no canal RASMOO, limitada a
30 mensagens e 120 segundos, com SQLite temporário isolado. O `--help` da CLI
retornou exit 0, com aviso de interpretador-base ausente no venv. Scanner,
deadline, resolução restrita ao ID selecionado, parâmetro de banco alternativo
e registro do `RasmooParser` foram inspecionados; uma execução da CLI sobre banco
novo não ocorreu.

A consulta somente leitura ao SQLite local não comprovou uma identidade RASMOO
única e inequívoca. O índice de interface não foi tratado como ID. A atividade
parou antes de criar o banco temporário ou conectar ao Telegram; nenhum comando
`channels`, descoberta remota, retry ou leitura de mensagens ocorreu. O SQLite
original não foi alterado; credenciais/sessão não foram inspecionadas.

```text
ACTIVITY = S3 Controlled RASMOO Real Validation
ACTIVITY_STATUS = BLOCKED_PRECHECK / CHANNEL_ID_REQUIRED
CHANNEL_ID = NOT_RESOLVED / request full identifier from user
SCAN_EXECUTIONS = 0
TEMP_DATABASE = NOT_CREATED
TELEGRAM_ACCESS = NONE
ORIGINAL_SQLITE = READ_ONLY_IDENTITY_LOOKUP / NO WRITE
DOWNLOADS = NONE
GIT_ACTIONS = NONE
S3_STATUS = IN_PROGRESS
S3_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Resume the same authorized bounded scan after the user provides the full RASMOO telegram_chat_id
```

## S3 — Retomada do preflight local — 2026-10-10

O usuário forneceu o identificador completo do canal e reafirmou a autorização
de uma única coleta, limitada a 30 mensagens e 120 segundos, sem descoberta de
canais. A validação de `--help` retornou exit 0, mas o executável reportou que o
interpretador-base configurado no venv não foi encontrado. Ao testar `catalog
list` com um caminho novo sob o diretório temporário, o processo não concluiu e
foi interrompido. Imports do venv passaram, mas `catalog list` pela invocação
direta do módulo também não concluiu. O scanner não foi iniciado; não houve
acesso Telegram. Não há diretório/banco temporário retido, e o SQLite original
não foi acessado nesta retomada.

```text
ACTIVITY_STATUS = BLOCKED_PRECHECK / CATALOG_CLI_TIMEOUT
CHANNEL_ID = USER_PROVIDED / OMITTED_FROM_RECORD
SCAN_EXECUTIONS = 0
MAX_MESSAGES = 30
TIMEOUT_SECONDS = 120
TEMP_DATABASE = NO_DATABASE_RETAINED / CATALOG_LIST_PREFLIGHT_DID_NOT_FINISH
TELEGRAM_ACCESS = NONE
DOWNLOADS = NONE
CREDENTIALS_OR_SESSION_INSPECTED = NO
GIT_ACTIONS = NONE
S3_STATUS = IN_PROGRESS
S3_FORMAL_ACCEPTANCE = PENDING
SAFE_RESUME_POINT = Restore supported Python 3.14 runtime, then continue local catalog validation on this same temporary database without another scan
```

## S3 — RASMOO Catalog Validation Using Collected Data — 2026-10-10

O banco temporário fornecido pelo usuário foi aberto somente para leitura.
`integrity_check=ok`, foreign-key check sem violações, 30 mensagens e 26 mídias.
Há um scan `PARTIAL / MESSAGE_LIMIT`; o checkpoint `PARTIAL` corresponde ao run,
canal e watermark, e seu cursor aponta para mensagem persistida dentro do
watermark. Não foram expostos conteúdo, nomes ou IDs no relatório.

O `--help` confirmou `--database`, `--channel-id` e `--parser-key`; a fonte da
CLI retorna exit 0 apenas para scan `COMPLETE` e exit 4 nos demais estados, logo
`PARTIAL / MESSAGE_LIMIT` explica o exit 4 informado. Entretanto, `catalog list`
não concluiu e uma operação mínima `aiosqlite` em memória também ficou suspensa.
O venv está configurado para Python 3.14, mas seu interpretador-base não foi
encontrado; Python 3.15 está fora do requisito `>=3.14,<3.15`. Por isso não foi
executado `catalog build/list/show/items`, e o banco temporário permanece sem
alteração de catálogo.

```text
ACTIVITY_STATUS = BLOCKED_PREFLIGHT / ASYNC_SQLITE_RUNTIME_HANG
SQLITE_INTEGRITY = PASS
FOREIGN_KEY_VIOLATIONS = 0
MESSAGES_PERSISTED = 30
MEDIA_PERSISTED = 26
SCAN_STATUS = PARTIAL / MESSAGE_LIMIT
CHECKPOINT = CONSISTENT / PARTIAL
CATALOG_BUILD = NOT_RUN
RICH_CLI = BLOCKED / ASYNC_SQLITE_RUNTIME_HANG
EXIT_CODE_4_MEANING = CLI maps non-COMPLETE scan outcomes to exit 4
IDEMPOTENCY = NOT_RUN
REAL_DATA_CATALOG_VALIDATION = NOT_RUN / runtime blocker; parser not executed
S3_STATUS = IN_PROGRESS
S3_FORMAL_ACCEPTANCE = PENDING
NEXT_ACTION = Restore supported Python 3.14 runtime and continue against this same temporary database; do not rescan
```

## S3-MAG-01 — Catalog CLI Windows Compatibility — 2026-10-10

The user authorized an offline Windows output-compatibility correction, synthetic
regression coverage, and validation using a separate copy of the supplied
temporary SQLite database. No Telegram access, download, credential/session
inspection, source-database write, or Git mutation occurred.

The Architect verdict is PASS. The original user exception was not captured, so
Unicode encoding remains the probable incident cause; the Rich write path and
the CLI's generic error handling corroborate the mechanism. The Scriber added a
Catalog-scoped output adapter and synthetic tests for UTF-8, CP1252, CP850, and
redirected output. The coordinator added an empty-stderr assertion.

A focused writer test passed (1 passed); Ruff and `git diff --check` passed. The
agent sandbox could not initialize the Windows Proactor socketpair and its
integration test stopped before SQLite access. The supported user PowerShell
run is therefore pending for `catalog items`/CLI integration and full pytest.

Read-only aggregates from an isolated copy of the supplied temporary DB:

```text
CHANNELS = 1
CATALOG_RUNS = 2 / both COMPLETE
PLAN_NODES_PER_RUN = 589
UNRESOLVED_PER_RUN = 2
PERSISTED_NODES = 589 active / 0 inactive
MEDIA = 26 rows / 26 linked
SOURCE_DATABASE_WRITTEN = NO
```

Thus, 589 is the build-plan node count and matches the active persisted count in
the provided temporary DB. The reported 98 was not reproduced there; its query
or snapshot provenance is missing. The requested before/after idempotency rebuild
on an isolated copy could not complete in the agent environment.

```text
ACTIVITY_COMPLETION_PERCENT = 72%
ACTIVITY_STATUS = PARTIAL
ARCHITECT_VERDICT = PASS
SCRIBER_VERDICT = PARTIAL
ENCODING_REGRESSION = PARTIAL / focused writer PASS; integration pending
CATALOG_CLI_INTEGRATION = PENDING_USER_WINDOWS_VALIDATION
IDEMPOTENCY = PARTIAL / isolated rebuild comparison pending
CATALOG_COUNTS_EXPLAINED = PARTIAL / 589 validated; 98 not reproduced, source query unknown
PYTEST = PARTIAL / focused writer 1 passed; full regression pending
RUFF = PASS
DIFF_CHECK = PASS
GIT_ACTIONS = NONE
TELEGRAM_ACCESS = NO
DOWNLOADS = NONE
S3_STATUS = IN_PROGRESS
S3_FORMAL_ACCEPTANCE = PENDING
NEXT_ACTION = Run the focused/full validation in the functional user PowerShell runtime; reconcile the query/snapshot behind 98
```

## S3-CLOSE-01 — Formal Acceptance and Publication — 2026-10-10

S3 foi formalmente aceita após revisão do repositório e reconciliação das
evidências fornecidas. O núcleo genérico, RasmooParser, gate S3-MAG-01,
validação do catálogo real com escopo limitado, idempotência, CLI Windows e
regressão completa foram aceitos. O catálogo real corresponde a 30 mensagens e
26 mídias; o scan terminou por `MESSAGE_LIMIT` e não cobriu o canal inteiro.
Foram preservadas duas referências unresolved. A gramática está aprovada
somente para os formatos comprovados. S3 não incluiu downloads; a validação
integral do produto no canal real permanece planejada para S9.

```text
ACTIVITY = S3-CLOSE-01
ACTIVITY_COMPLETION_PERCENT = 100%
STATUS = COMPLETED / S3 ACCEPTED AND CLOSED
S3_FORMAL_ACCEPTANCE = APPROVED
S3_GENERIC_CORE = PASS
RASMOO_PARSER = PASS
S3_MAG_01 = PASS
REAL_CATALOG_VALIDATION = PASS_WITH_SCOPE
IDEMPOTENCY = PASS
WINDOWS_CLI = PASS / catalog items without -X utf8
FULL_REGRESSION = PASS / 167 passed + 11 subtests
RUFF = PASS
DIFF_CHECK = PASS
FILES_COMMITTED = PENDING
FILES_EXCLUDED = PENDING
COMMIT_SHA = PENDING
GIT_PUSH = PENDING
S4_STATUS = PLANNED / NOT_STARTED
S4_IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
SAFE_RESUME_POINT = S4 entry review; implementation requires separate authorization
```

## S5-REAL-CANDIDATE-01 — Candidato para a prova real S5 — 2026-10-11

A atividade foi concluída em modo de preparação, sem fila, rede, alteração de
SQLite de origem, código-fonte ou Git. As evidências offline foram fornecidas
pelo usuário e não foram repetidas: 13 testes focados, 199 regressões, 11
subtests, Ruff e diff check passaram.

A origem RASMOO foi aberta somente para leitura e copiada com SQLite Online
Backup. A migration 004 e todas as leituras do planner ocorreram na cópia. O
S4 de referência também permaneceu somente para leitura. Integridade SQLite
reportou `ok`. O catálogo observado continua parcial, originado de scan com
limite de mensagens; portanto, completude integral dos módulos não está
estabelecida. Há 4 linhas unresolved (2 referências de mensagem distintas),
sem referência unresolved nos subtrees dos quatro módulos populados.

Os 47 módulos ativos incluem quatro módulos populados. Em ordem crescente de
mídias, as métricas anonimizadas são:

| Módulo | Aulas | Mídias | Bytes | MiB | Bytes pendentes | Elegibilidade no catálogo observado | Até 30 MiB |
|---|---:|---:|---:|---:|---:|---|---|
| A | 5 | 5 | 73.071.671 | 69,69 | 73.071.671 | 5 DOCUMENT, identidades únicas, tamanhos positivos, linhagem ativa válida, sem unresolved no subtree | NÃO |
| B | 6 | 6 | 91.823.981 | 87,57 | 91.823.981 | 6 DOCUMENT, identidades únicas, tamanhos positivos, linhagem ativa válida, sem unresolved no subtree | NÃO |
| C | 7 | 7 | 105.732.654 | 100,83 | 105.732.654 | 7 DOCUMENT, identidades únicas, tamanhos positivos, linhagem ativa válida, sem unresolved no subtree | NÃO |
| D | 15 | 8 | 161.608.458 | 154,12 | 161.608.458 | 8 DOCUMENT, identidades únicas, tamanhos positivos, linhagem ativa válida, sem unresolved no subtree | NÃO |

Nenhuma mídia já era válida/baixada; todas permanecem pendentes. O menor
escopo populado observado (Módulo A) excede o teto de 30 MiB em 41.614.391 bytes.
Não houve exclusões do planner nos quatro escopos.

A CLI real `download plan` foi invocada sobre a cópia read-only com seleção
MODULE, `--workers 2`, `--max-media-items 5` e
`--max-transfer-bytes 31457280`. Um ajuste process-local de `asyncio.run`
permitiu completar os coroutines síncronos do planner no runtime isolado; não
houve mudança de código. O preview retornou exit 0 e:

```text
SELECTED_MODULE = YES
LESSON_COUNT = 5
MEDIA_COUNT = 5
PENDING_COUNT = 5
ALREADY_VALID_COUNT = 0
EXCLUDED_COUNT = 0
PENDING_BYTES = 73071671
DETERMINISTIC_ORDER = PASS
SELECTION_PLAN_EQUIVALENCE = PASS
LIMIT_CHECK_RESULT = FAIL
```

A implementação da fila limita workers a 1–2, cobra o tamanho esperado em
reservas concorrentes, converte reserva em consumo por chunk antes da escrita,
conserva bytes consumidos entre retries e libera apenas reserva não consumida.
Telethon valida identidade/tamanho anunciado e emite chunks de até 256 KiB.
Ainda assim, a callback do orçamento roda depois que o chunk foi recebido;
um fluxo que exceda o tamanho anunciado pode fazer chegar até um chunk de
256 KiB antes da rejeição. O teto não está demonstrado como hard cap de bytes
recebidos na rede; offline tests não provam esse limite em streaming real.

```text
ACTIVITY = S5-REAL-CANDIDATE-01
ACTIVITY_COMPLETION_PERCENT = 100% / preparação autorizada concluída
STATUS = BLOCKED
S5_OFFLINE_VALIDATION = PASS / user-provided evidence; not rerun
CATALOG_SOURCE = RASMOO SQLite; source read-only; planner used isolated backup
CANDIDATE_FOUND = NO
CANDIDATE_MEDIA_COUNT = N/A / smallest examined scope has 5
CANDIDATE_LESSON_COUNT = N/A / smallest examined scope has 5
CANDIDATE_TOTAL_BYTES = N/A / smallest examined scope has 73071671
MODULE_COMPARISON = 5, 6, 7, 8 media; see anonymized table above
PLANNER_PREVIEW = PASS_READ_ONLY / exit 0; selected minimum populated module; limit failed
ELIGIBILITY = All four scopes eligible in observed catalog; none within 30 MiB; catalog partial
MEDIA_LIMIT = Exact preview cap 5; queue validates selected count before workers
TRANSFER_BYTE_LIMIT = 31457280 / planner preview FAIL for every populated module
BUDGET_ENFORCEMENT = BLOCKED_FOR_REAL / reservation and retry accounting exist; receive callback permits up to 256 KiB overrun before rejection on an oversized stream
REAL_TELEGRAM_ACCESS = NO
REAL_DOWNLOADS = 0
GIT_ACTIONS = NONE
MATERIAL_BLOCKERS = No populated module fits 30 MiB; catalog completeness unproven; strict network-byte cap unproven during chunk receive
S5_REAL_VALIDATION = PENDING
S5_FORMAL_ACCEPTANCE = PENDING
FINAL_VERDICT = BLOCKED / no definitive candidate is eligible under the fixed 30 MiB ceiling
NEXT_ACTION = Obtain a complete catalog with a full eligible module <=30 MiB, or request an explicit decision to change scope/budget; resolve hard-cap enforcement and obtain separate authorization before any queue run
```
