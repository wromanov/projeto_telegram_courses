# S9 — Correção final G0/G2/G7

```text
ACTIVITY_ID = TELEGRAM_S9_FINAL_GATES_01
PROJECT_ID = projeto_telegram_courses
ROUTING_MODE_ACTUAL = MULTIAGENT / ROOT + security_reviewer
AGENTS_USED = ROOT; security_reviewer
MODELS_ACTUAL = ROOT: UNVERIFIED; security_reviewer: runtime role declares GPT-6-Sol/High; actual child turn metadata UNVERIFIED
ROUTER = codex-task-router skill applied; reviewer selected for independent security review; no Architect or Scribe
PROJECT_ROOT = C:\Users\walac\desenvolvimento\projeto_telegram_courses
BRANCH = work/s0-bootstrap
HEAD = d36e96055a26556221bc487717f18ed322c76f02
CONTRACT_STATUS = APPROVED_FROZEN
CONTRACT_SHA256_BEFORE = BD89EEB0B9C76565FD2780926D50D40EC97255302B2A7DA46CE5676828F85EA2
CONTRACT_SHA256_AFTER = BD89EEB0B9C76565FD2780926D50D40EC97255302B2A7DA46CE5676828F85EA2
RISK03_DECISION = FORMALLY_ACCEPTED_FOR_PERSONAL_USE
RISK03_DECISION_DATE = 2026-10-31
RISK03_DECISION_SOURCE = EXPLICIT_USER_APPROVAL_IN_CANONICAL_CHAT
RISK03_SCOPE = PERSONAL_SINGLE_USER_WINDOWS
```

## Resultado

`FINAL_RESULT = S9_PREOPERATIONAL_CODE_PARTIAL`.

G0, G2 e G7 têm implementação e validação offline. Não declarei `READY` porque
o repositório não contém produtor real G6. G7 exige um recibo G6 `PASS` com
origem `REAL_CONTRACTUAL`, mas hoje só há leitura/validação desse artefato. Por
isso, a execução real de G7 permanece condicionada e `G7_REAL_EVIDENCE =
NOT_ASSESSED`. Não houve homologação real nem operação Telegram.

## Correções

**G0 antes de RPC.** A confirmação TTY agora é vinculada ao run, canal, hash do
manifesto, escopo e limites. Recusa, ausência de TTY, timeout, alteração de
escopo, replay ou streams interativos injetados no modo live bloqueiam. O
carregador real de credenciais também exige G0 mesmo com gateway factory
injetada. Os wrappers de scan G2/G7 e de download G5 revalidam o recibo G0
humano antes de iniciar o processo filho. Evidência de fixture permanece
`SYNTHETIC` e não libera G1 live. A confirmação específica de plano G4 continua
separada.

**G2 na reabertura.** O leitor compara `application_exit_code` com
`external_exit_code`, além de run, canal, manifesto, origem, supervisor,
persistência, estado terminal, contadores e ledger. `COMPLETE` exige `0/0`;
`PARTIAL/MESSAGE_LIMIT` elegível exige `4/4`, contadores no limite e supervisor
atestado. O campo `message_limit_exit_allowed` representa a política permitida
para o scan, não o resultado observado; razão e estado distinguem `0` de `4`.

**G7 incremental.** O produtor e reconciliador agora aceitam até duas syncs no
mesmo run, com recibos G7 e recibos de supervisor versionados (`01` e `02`). A
segunda sync exige a primeira `COMPLETE`, valida o hash do recibo anterior e
encadeia o hash do banco, o baseline e o high-water. Ambas compartilham
`MAX_TOTAL_SCANS=3`, `MAX_PER_SCAN=200`, `MAX_TOTAL_OBSERVATIONS=600` e janela
50. Excesso, receipt stale, predecessor ausente, divergência de run/canal,
auditoria inválida ou exit incompatível falham fechado. Sync parcial não promove
high-water; mensagens ausentes não são tratadas como deleções. Resultados
sintéticos continuam explicitamente sintéticos.

**T24.** Falha ou exceção ao finalizar o logging/auditoria retorna exit `125`,
nunca `4`. Assim, `4` continua reservado ao `MESSAGE_LIMIT` elegível; logging
finalizado corretamente preserva o `4` esperado.

## Validação

Ambiente: Windows, venv do projeto com Python 3.14.7; `TEMP`, `TMP` e
`basetemp` externos ao checkout. Todos os testes usam fixtures/gateways
injetados. Nenhuma RPC foi iniciada.

| Verificação | Resultado |
|---|---|
| Testes focais G0/G2/G7/supervisor/T24 | **100 passed** |
| Regressão S9 (`test_s9*.py`) | **214 passed** |
| Regressão offline unitária + integração | **586 passed, 11 subtests passed** |
| Ruff nos paths alterados | **PASS** |
| `compileall -q src tests` | **PASS** |
| `git diff --check` | **PASS**, com avisos LF/CRLF preexistentes |
| SHA-256 do contrato antes/depois | **Idêntico** |

Os testes exercitam G0, G2, G7, os negativos, T24 e duas syncs G7 sintéticas
com reabertura. A regressão integral inclui todos os testpaths unitários e de
integração. Não foi executado um novo teste único que percorra G0→G9 inteiro;
G6 real continua ausente e nenhuma operação real foi autorizada nesta atividade.

## Revisão independente

`SECURITY_REVIEW = PASS_WITH_LIMITS`.

Nenhum finding bloqueante permaneceu em G0, reabertura G2, proveniência e
reconciliação G7 ou T24. A revisão confirmou suporte à segunda sync G7 no mesmo
run. O limite residual é a ausência de produtor real G6, que mantém o fluxo
real end-to-end não demonstrado. O perfil disponível/configurado do
`security_reviewer` declara GPT-6-Sol/High e leitura somente; o catálogo local
do roteador lista Terra/Medium. Como o runtime não expôs metadado correlacionado
ao turno do agente, o modelo/esforço efetivos permanecem `UNVERIFIED`.

## Autoridade, worktree e riscos remanescentes

RISK-03 foi formalmente aceito apenas para aplicativo pessoal, operador único e
Windows sob controle do usuário: risco de modificação/rollback de evidência
local por processo com controle de escrita da mesma conta. Permanecem os
controles existentes de ACL privada, `SQLite integrity_check`, cadeia de
hashes, auditoria durável e fail-closed. Não foi adicionada infraestrutura
enterprise nem aberta qualquer credencial.

O preflight real ainda não está pronto: não há produtor real G6; manifesto,
destino e disk gate do operador não foram estabelecidos neste runtime. O
resultado é `NO-GO` para execução/preflight real neste estado. Próxima ação
exata: identificar uma origem autorizada para o produtor/recibo real G6 (ou
autorizar uma tarefa offline delimitada para prover essa etapa) e então fazer
novo preflight no ambiente do operador. Não iniciar G0 ou RPC automaticamente.

```text
FILES_CHANGED = src/telegram_courses/s9_g0_confirmation.py; src/telegram_courses/operational_logging.py; src/telegram_courses/s9_operational_ledger.py; src/telegram_courses/s9_real_gate_producers.py; src/telegram_courses/s9_supervisor_cli.py; tests/unit/test_s9_g0_confirmation.py; tests/unit/test_s9_operational_ledger.py; tests/unit/test_s9_real_gate_producers.py; tests/unit/test_s9_supervisor_cli.py; tests/unit/test_s8_config_logging.py; docs/governance/APPROVALS_AND_DECISIONS.md; docs/continuity/PROJECT_STATE.md; docs/continuity/CONTINUITY_RECORD.md; docs/continuity/handoff/LAST_HANDOFF.md; docs/reports/S9_FINAL_GATES_01/REPORT.md
WIP_PRESERVED = YES / 344 pre-existing status entries retained; activity adds two G0 files and this report; 0 staged
TELEGRAM_RPC = 0
REAL_LOGIN_SCAN_DOWNLOAD = NOT_EXECUTED
OPERATIONAL_DB_WRITES = 0
GIT_STAGE_COMMIT_PUSH = NOT_EXECUTED
S9_REAL = NOT_EXECUTED
S10 = NOT_AUTHORIZED
DELIVERY_STATUS = SENT_UNCONFIRMED / send tool returned success; readback did not expose the new message
MESSAGE_OBSERVED = NO / read_thread showed only pre-existing turns; list_threads metadata changed but no message content was visible
RESPONSE_OBSERVED = NO
THREAD_ID = 6add6aa9-12e0-83e8-b02f-870f0a0edaf9 / Projeto Telegram 3.0
WORK_VALIDATED = YES / LOCAL_REPORT_AND_CONTINUITY_PASS / DELIVERY_UNCONFIRMED
```
