# TELEGRAM 3.0 — S8 Operational Hardening

```text
ACTIVITY_ID = TELEGRAM_3.0_S8_OPERATIONAL_HARDENING
ACTIVITY_DATE = 2026-10-28 / America-Sao_Paulo
AUTHORITY = User-pasted S8 implementation card / offline scope
IMPLEMENTATION_STATUS = COMPLETE
INTEGRATION_STATUS = COMPLETE
OFFLINE_VALIDATION_STATUS = PASS / POST_REMEDIATION / 366 tests passed / 11 subtests passed / 0 failures
FORMAL_S8_ACCEPTANCE = APPROVED_WITH_DOCUMENTED_LIMITATIONS / USER_DECISION_2026-10-28
DELIVERY_STATUS = SENT / SECOND_ATTEMPT_AUTHORIZED_BY_DIRECT_USER / TOOL_IS_ERROR_FALSE
GIT_PUBLICATION = NOT_AUTHORIZED / no stage, commit, or push performed
LIVE_TELEGRAM_OR_RPC = NONE
```

## Resultado — registro histórico da execução inicial (superado pelos adendos)

A configuração, logging operacional, fila e caminho de download individual foram endurecidos e integrados offline. Os testes síncronos e os checks estáticos listados abaixo passaram. Os testes assíncronos de resiliência e a medição `tracemalloc` foram escritos, mas não executados: o runtime Windows bloqueia ao criar o socketpair do event loop, antes de entrar no teste. Portanto, esta atividade não declara validação assíncrona completa nem aceite formal de S8.

## Implementação

- `config/settings.toml`, `src/telegram_courses/config.py` e `src/telegram_courses/cli.py`: precedência CLI → ambiente → TOML → defaults; validação de workers `1..2` e tentativas `1..3`; configuração de diretório e database; resultado final da fila como `COMPLETED`, `PARTIAL`, `FAILED`, `SKIPPED` ou `CANCELLED`. Chaves de credenciais não são aceitas no TOML e erros de configuração mantêm mensagem genérica.
- `src/telegram_courses/operational_logging.py`: eventos JSON em UTC, com campos de contexto permitidos. Mensagens livres, traceback, paths e valores fora do formato seguro não são serializados. Eventos cobrem configuração rejeitada, retry, FloodWait, falha de cleanup e resultado da fila.
- `src/telegram_courses/s5_downloads.py`: retry transitório com full jitter, até três tentativas por mídia (`0–1s` e `0–2s` nas duas esperas possíveis). Mantidos limite de workers, cooldown compartilhado e budget FloodWait de 120 segundos existentes; não foi adicionado outro budget.
- `src/telegram_courses/downloads.py`: o caminho S4 direto verifica espaço antes de reivindicar estado, criar parcial ou solicitar payload, usando a margem S5 de `max(1 GiB, 10%)`; tamanho desconhecido ou falha ao consultar armazenamento bloqueia. Falhas ao salvar checkpoint, transicionar estado, atualizar tentativa V2 ou fechar o pool produzem aviso seguro sem substituir o erro/cancelamento original.
- `tests/conftest.py` e `tests/integration/test_cli_smoke.py`: variáveis S8 são isoladas nos testes. O snapshot de não mutação considera arquivos rastreados do repositório e a pasta temporária dedicada do teste; não percorre o WIP local não rastreado. As expectativas de erro da CLI validam o evento JSON sanitizado seguido da mensagem genérica.
- Novos testes: `tests/integration/test_s8_cli.py`, `tests/unit/test_s8_config_logging.py` e `tests/unit/test_s8_resilience.py`. O teste de memória prepara fluxo S4 sintético de 16 MiB em chunks de 256 KiB e registra método, pico, tamanho e hash. Nenhum limite de memória NFR foi inventado.

Não houve mudança de schema, migração, regra de integridade S6 ou comportamento de sincronização S7. Os budgets S5, exigência de remote hash e fluxo fail-closed permanecem preservados.

## Validação executada

| Verificação | Resultado |
|---|---|
| `tests/unit/test_downloads.py -k 'not unbounded_mode'` | **10 passed, 1 deselected** |
| `tests/unit/test_config.py` e identidade explícita da CLI | **11 passed** (inclui 10 testes de configuração e o teste de identidade) |
| `tests/unit/test_s8_config_logging.py` + `tests/integration/test_s8_cli.py` | **10 passed** |
| `tests/integration/test_cli_smoke.py` após limitar o snapshot | **9 passed** |
| Ruff nos arquivos Python alterados | **PASS** |
| Compileall nos módulos e testes alterados | **PASS** |
| `git diff --check` | **PASS**; apenas avisos de conversão LF→CRLF nos arquivos existentes |

Nos testes de configuração, `TEMP` e `TMP` foram apontados a uma pasta temporária isolada no workspace, pois o diretório temporário padrão do runtime retornou `PermissionError`. A seleção então passou. Os basetemps e artefatos de teste foram preservados.

## Limites e gates pendentes — registro histórico pré-remediação

- Uma tentativa assíncrona com o loop Windows padrão e outra com `WindowsSelectorEventLoopPolicy` ficaram bloqueadas em `_fallback_socketpair → socket.accept`, antes da entrada no corpo do teste. As tentativas foram interrompidas; nenhuma foi registrada como PASS.
- `tests/unit/test_s8_resilience.py` permanece sem execução. Isso inclui retry/floodwait/concurrency, gate de disco e o fluxo sintético de memória. Nenhum pico `tracemalloc` foi observado ou inferido; o teste apenas contém a instrumentação para medi-lo quando houver runtime compatível.
- Não houve chamada ao Telegram/RPC, escrita em database operacional, publicação Git ou aceite formal de S8.
- A primeira tentativa foi rejeitada pela revisão automática. Após nova autorização direta do usuário para o chat `Projeto Telegram 3.0`, a segunda tentativa foi enviada com sucesso (`isError=false`). Não houve nova tentativa além dessa.

## Estado factual e próxima ação — registro histórico pré-remediação

```text
REPOSITORY = C:/Users/walac/desenvolvimento/projeto_telegram_courses
BRANCH = work/s0-bootstrap
HEAD = 8ddb085950e140ebfd51da603485c7ed0bd384f2 (unchanged)
UPSTREAM = origin/work/s0-bootstrap
WORKTREE = dirty; pre-existing WIP and S8 artifacts preserved
STAGED = none
COMMIT = not created
PUSH = not attempted
NEXT_ACTION = user reviews this report and decides formal S8 acceptance; async/memory tests require a runtime that can create the Windows event-loop socketpair
```

O estado de continuidade foi atualizado sem reconciliar ou remover o WIP pré-existente. A dependência documental de publicação S6/S7 permanece separada e pendente. `S8_FORMAL_ACCEPTANCE` continua `PENDING_USER`.

---

## Adendo — remediação focalizada e validação offline direta (2026-10-28)

Este adendo é posterior ao relatório original e atualiza apenas o resultado da
validação offline da S8. Não altera contratos congelados nem concede aceite formal.

```text
POST_REMEDIATION_IMPLEMENTATION = COMPLETE
POST_REMEDIATION_OFFLINE_REGRESSION = PASS / 366 passed / 11 subtests passed / 0 failed
FOCUSED_TESTS = PASS / 32 passed
RUFF = PASS
COMPILEALL = PASS
GIT_DIFF_CHECK = PASS
FORMAL_S8_ACCEPTANCE = PENDING_USER
REAL_TELEGRAM_CALLS = 0
REAL_DATABASE_WRITES = 0
GIT_STAGE = NOT_EXECUTED
GIT_COMMIT = NOT_EXECUTED
GIT_PUSH = NOT_EXECUTED
HEAD = 8ddb085950e140ebfd51da603485c7ed0bd384f2
```

### Correções verificadas

- `tests/unit/test_s8_resilience.py`: double Repository inclui `get_record`
  com retorno ausente; disk gate passou sem alterar produção.
- `src/telegram_courses/operational_logging.py`: handler sanitizado não imprime
  traceback ou payload sensível se a própria escrita de log falhar;
  novo teste de falha deliberada de stream passou.
- `src/telegram_courses/cli.py`: falha inesperada antes da inicialização
  configura logger seguro no stream atual, sem reaproveitar stream fechado.
- `tests/integration/test_cli_auth.py`,
  `tests/integration/test_cli_credentials.py`,
  `tests/integration/test_cli_scan.py` e
  `tests/integration/test_cli_smoke.py`: expectativas reconciliadas com
  evento JSON sanitizado seguido de mensagem genérica; assertivas de
  ausência de segredos preservadas.
- `tests/unit/test_s8_config_logging.py`: novo teste garante que exceção
  de handler não exponha traceback ou conteúdo marcado como sensível.

### Evidência e limites

Runtime: Windows, `.venv` Python 3.14.7, execução offline via
Desktop Commander, `pytest tests/unit tests/integration`, diretório
temporário isolado fora do repositório. A execução completa terminou com
366 passed, 11 subtests passed, 0 failed em 74,11 s.

A medição sintética de streaming de 16 MiB registrou pico rastreado pelo
`tracemalloc` de 942.996 bytes; o payload foi preparado antes do início
da medição. Não representa o RSS total nem estabelece aceite quantitativo
do NFR-02, cujo limiar não foi informado.

Não houve chamadas Telegram ou uso de banco operacional. O index permaneceu
vazio, o HEAD permaneceu inalterado, o WIP anterior foi preservado. Esta
evidência torna a regressão offline PASS, mas não constitui homologação
remota, aceite formal S8 ou autorização para iniciar S9.

---

## Adendo — decisão formal de aceite da S8 (2026-10-28)

**Esta seção é o estado vigente e posterior aos relatos históricos acima.**

```text
DECISION_ID = S8_FORMAL_ACCEPTANCE_2026-10-28
DECISION_AUTHORITY = USER_EXPLICIT / "sim aprovo s8"
S8_ACCEPTANCE = APPROVED_WITH_DOCUMENTED_LIMITATIONS
S8_STATUS = CLOSED_WITH_EXCEPTIONS
S8_IMPLEMENTATION = COMPLETE
S8_OFFLINE_INTEGRATION = PASS
OFFLINE_REGRESSION = 366 PASSED / 11 SUBTESTS PASSED / 0 FAILED
RUFF_COMPILEALL_DIFF_CHECK = PASS
EXCEPTION_NFR02 = NO_QUANTITATIVE_MEMORY_THRESHOLD / TRACEMALLOC_ONLY
EXCEPTION_REAL_CHANNEL = NO_LIVE_TELEGRAM_PROOF / S9_NOT_AUTHORIZED
S6_S7_EXCEPTIONS = PRESERVED
V1_ACTIVE = YES
V2_GLOBAL = OFF
GIT_STAGE_COMMIT_PUSH = NOT_EXECUTED / NOT_AUTHORIZED_BY_ACCEPTANCE
S8_GIT_CHECKPOINT = REQUIRES_SEPARATE_APPROVAL
NEXT_SPRINT = S9 / PLANNED / NOT_STARTED / NOT_AUTHORIZED
```

O usuário aceitou expressamente a S8 com conhecimento da evidência
offline (366 testes e 11 subtestes aprovados, zero falhas) e de seus limites.
O pico \`tracemalloc\` de 942.996 bytes no cenário sintético de 16 MiB não
demonstra RSS máximo nem satisfaz um limiar NFR-02 que não foi definido.
Não houve homologação real Telegram, reservada à S9. Essas limitações
permanecem explícitas e não reabrem nem resolvem as exceções S6/S7.

Authority da decisão: [APPROVALS_AND_DECISIONS](../../governance/APPROVALS_AND_DECISIONS.md#decisão-formal--aceite-da-s8-com-limites-documentados--2026-10-28).
Nenhuma operação Git mutável ou ação externa está autorizada por este aceite.
