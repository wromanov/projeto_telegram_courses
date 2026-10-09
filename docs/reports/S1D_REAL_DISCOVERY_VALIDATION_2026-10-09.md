# S1-D — Real Discovery Validation & Calibration

```text
ACTIVITY = S1-D Real Discovery Validation & Calibration
DATE = 2026-10-09 / America/Sao_Paulo
STATUS = BLOCKED
ACTIVITY_COMPLETION_PERCENT = 12%
ROOT_RUNTIME_MODEL = NOT_INDEPENDENTLY_VERIFIED
AUTHORITY_PRECHECK = PASS_FOR_BOUNDED_ACCEPTANCE / current user instruction authorizes one controlled real validation; contract remains NOT_FROZEN and GOV-01 remains a freeze blocker only
IMPLEMENTATION = PASS_OFFLINE / existing implementation confirmed in current checkout
DECISIONS = DEC-S1D-01/02/03 approved; contract and numeric baseline approved; no new audit performed
LIMITS = DIALOGS_PER_PAGE=100; MAX_RAW_DIALOGS=1000; MAX_PAGES=20; OPERATION_TIMEOUT=120s; CLEANUP_TIMEOUT=10s
SESSION_RESTORE = NOT_RUN / protected DPAPI artifact absent
REAL_DISCOVERY = NOT_RUN / CLI not invoked
BROADCAST_FOUND = NOT_MEASURED
MEGAGROUPS_FOUND = NOT_MEASURED
RAW_DIALOGS_SCANNED = 0
PAGES_PROCESSED = 0
DISCOVERY_RESULT = NOT_STARTED
RESTORE_DURATION = NOT_MEASURED
DISCOVERY_DURATION = NOT_MEASURED
CLEANUP_DURATION = NOT_MEASURED
TOTAL_DURATION = PRECHECK_ONLY / no Telegram operation
BUDGET_VALIDATION = CONFIGURED_BUDGETS_CONFIRMED / runtime behavior not measured
PAYLOAD_ISOLATION = SUPPORTED_BY_EXISTING_OFFLINE_VALIDATION / not re-exercised live
LOCAL_SELECTION = NOT_RUN
CLEANUP = NOT_APPLICABLE / no client created
OPERATIONAL_CALIBRATION = NOT_MEASURED
API_CREDENTIAL_PRESENCE = TELEGRAM_API_ID and TELEGRAM_API_HASH absent from Process, User, and Machine environment scopes; values were not read into output
SESSION_ARTIFACT_PRESENCE = ABSENT / checked presence only; file contents were not accessed
SOURCE_CHANGES = NONE
REAL_TELEGRAM_ACCESS = AUTHORIZED / NONE PERFORMED
GIT_ACTIONS = NONE
DOCUMENTATION_CHECKPOINT = THIS_REPORT + PROJECT_STATE + CONTINUITY_RECORD + LAST_HANDOFF
S1D_ACCEPTANCE_STATUS = BLOCKED_PRECHECK
S1_STATUS = IN_PROGRESS
BLOCKERS = Valid protected DPAPI session and local API credentials unavailable; login was not authorized or attempted
FINAL_VERDICT = BLOCKED_BEFORE_CLI / no network or remote action occurred
NEXT_ACTION = Make the existing protected session and API credentials available locally, then resume the already-authorized single validation without logging in
```

## Operational calibration evidence review — 2026-10-09

```text
ACTIVITY = S1-D Operational Calibration Completion
STATUS = PARTIAL / existing evidence insufficient; offline telemetry ready
EXISTING_METRICS = first real failure: PAGES_REQUESTED=1, PAGES_RECEIVED=1, RAW_DIALOGS_RECEIVED=101, CATEGORY=ADAPTER_FAILURE; later functional discovery/selection is user-reported without measurements
METRICS_SUFFICIENT = NO
INSTRUMENTATION_READY = YES / monotonic operation, restore, discovery and cleanup durations; page/raw-dialog counts; approved limits; COMPLETE/PARTIAL and stop reason
FOCUSED_TESTS = PASS / 43 passed
FULL_PYTEST = PASS / 126 passed, 11 subtests passed in 167.64s
RUFF = PASS
DIFF_CHECK = PASS
REAL_TELEGRAM_ACCESS = NO
S1D_ACCEPTANCE = PENDING / real operational measurements remain absent
NEXT_ACTION = After separate user authorization, run .\.venv\Scripts\telegram-courses.exe channels and retain only the S1D_CALIBRATION line
```

Os logs e relatórios sanitizados disponíveis não medem duração, cleanup,
cobertura ou limites observados da descoberta funcional posterior. O evento
anterior com 101 diálogos foi uma falha do adapter; a hipótese de overflow por
diálogos fixados não foi confirmada pelos metadados reais. Ele não comprova
resultado `COMPLETE` ou `PARTIAL` de uma descoberta bem-sucedida.

A aplicação agora emite uma linha `S1D_CALIBRATION` com tempos monotônicos,
contadores, budgets, resultado e stop reason. Nenhum nome/ID de canal,
credencial, sessão ou conteúdo de mensagem integra essa linha. A descoberta e
seleção funcional mantêm seu comportamento e limites. Testes offline verificam
resultado parcial e sanitização de erro. Nenhuma conexão Telegram, leitura de
vault ou sessão ocorreu nesta atividade.

A medição real continua necessária para comparar a operação funcional aos
budgets aprovados e concluir o aceite. A instrução desta atividade não autoriza
essa nova conexão. Após autorização específica, execute o comando em PowerShell
na raiz do repositório e preserve somente a linha `S1D_CALIBRATION`; não
compartilhe a listagem exibida pela CLI, que contém metadados de canais.
O bloco de autorização na seção histórica acima descreve somente a tentativa
anterior e não se aplica a esta atividade.

## Aceite final e calibração operacional — 2026-10-09

```text
ACTIVITY = S1-D Final Acceptance & Consolidated Checkpoint
ACTIVITY_COMPLETION_PERCENT = 96%
STATUS = PASS_FOR_FUNCTIONAL_ACCEPTANCE / FORMAL_CLOSURE_BLOCKED_BY_GOV01
REAL_CALIBRATION = PASS
NUMERIC_SELECTION = PASS / local option 69 resolved to expected telegram_chat_id
FULL_PYTEST = PASS / 126 passed, 11 subtests, 167.64s
RUFF = PASS
GIT_DIFF_CHECK = PASS
FUNCTIONAL_ACCEPTANCE = PASS
CONTRACT_FREEZE = BLOCKED_BY_GOV01 / not frozen
FORMAL_CLOSURE = BLOCKED_BY_GOV01
BLOCKING_REQUIREMENTS = GOV-01 external governance adjudication required before contract freeze and formal S1-D closure
DEC-S1D-01/02/03 = APPROVED / preserved
OPEN-03 = APPROVED / page_size=100; raw_dialog_limit=1000; page_limit=20; operation_budget=120s; cleanup_budget=10s
OPERATION_SECONDS = 2.809485
RESTORE_SECONDS = 0.957923
DISCOVERY_SECONDS = 1.315603
CLEANUP_SECONDS = 0.001170
CLEANUP_STATUS = COMPLETE
PAGES_REQUESTED = 4 / PAGES_RECEIVED = 4
RAW_DIALOGS_PROCESSED = 313
RESULT = COMPLETE / OUTCOME_STATE=COMPLETE / STOP_REASON=NONE / FAILURE_CATEGORY=NONE
REAL_DISCOVERY = PASS / BROADCAST_CHANNEL=PASS / MEGAGROUP=PASS
DOWNLOAD_OR_SCANNER = NOT_STARTED
CREDENTIAL_VAULT = PASS / PYTEST_CREDENTIAL_ISOLATION = PASS
REAL_TELEGRAM_ACCESS_FOR_VALIDATION = YES / bounded scenario; user-provided evidence
CREDENTIALS_ACCESSED_DURING_THIS_RECONCILIATION = NO
GIT_ACTIONS = NONE / read-only checks only
NEXT_PHASE_CANDIDATE = S2 — Message Scanner & SQLite Persistence / not started
```

### Conferência dos critérios contratuais

AC-01..12 offline: PASS conforme cobertura sintética e regressão registrada
nas evidências da implementação. A validação real e os dados desta seção
completam os gates de aceite funcional: restore, descoberta/classificação,
identidade estável, escolha local, orçamento/cobertura, resultado completo,
lifecycle e cleanup. A opção local `69` selecionou o `telegram_chat_id`
esperado sem iniciar scanner ou download.

DEC-S1D-01/02/03 e OPEN-03 permanecem conforme aprovados. Os tempos observados
estão abaixo dos budgets de operação (120s) e cleanup (10s); foram recebidas
quatro das quatro páginas e processados 313 diálogos brutos, abaixo dos limites
de 20 páginas e 1000 diálogos. Broadcast e megagroup passaram. Cleanup concluiu
em 0.001170s. Suíte completa, Ruff, diff check, vault e isolamento de credenciais
passaram conforme a evidência fornecida.

O contrato separa `CONTRACT_FREEZE` do gate de aceite; portanto o aceite
funcional é PASS. Porém, GOV-01 segue dependência externa normativa para
adjudicação antes de freeze/DoR, sem resolução registrada. Neste checkpoint
`CONTRACT_FREEZE = BLOCKED_BY_GOV01` e `FORMAL_CLOSURE = BLOCKED_BY_GOV01`;
S1-D não é declarada CLOSED e S2 permanece apenas candidata. O incidente
anterior de leitura acidental do vault e o risco residual já registrado são
preservados, sem reabertura por falta de nova evidência.

```text
GIT_ROOT = C:\Users\walac\desenvolvimento\projeto_telegram_courses
BRANCH = work/s0-bootstrap
HEAD = bf75ccf50e8912ece42a229a392752c4f96b905b
WORKTREE = pre-existing modifications present; checkpoint files listed in final report
GIT_ACTIONS = NONE / no add, commit, or push
```

## Evidence and boundary

The current user instruction authorizes one bounded real S1-D validation and
calibration. The approved contract's section 19 separates the acceptance gate
from contract freeze; GOV-01 remains unresolved and blocks freeze, and this
activity neither freezes the contract nor waives that blocker.

The current Windows process had no `TELEGRAM_API_ID` or `TELEGRAM_API_HASH`.
The same variables were absent at User and Machine environment scopes. The
protected session artifact expected by the application was absent. Only
presence was checked; no credential values or session contents were read.
Because the task requires reusing the existing session and does not authorize a
login, the CLI was not invoked. No network call, Telegram connection, message
operation, local selection, or cleanup lifecycle occurred.

The checkout already contains the S1-D implementation and its reported offline
validation. No source changes or tests were made for this blocked attempt. The
next run can proceed under the existing scoped authorization after the local
precheck passes; do not initiate login or expand the approved limits.
