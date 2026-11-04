# S9-G0 Final Correction 02 — relatório

Data: 2026-10-29 (America/Sao_Paulo)

```text
ACTIVITY_ID = TELEGRAM_S9_G0_FINAL_CORRECTION_02
RESULT = S9_G0_PARTIAL
BRANCH = work/s0-bootstrap
HEAD = d36e96055a26556221bc487717f18ed322c76f02 / unchanged
CONTRACT_BASELINE = S9_RASMOO_REAL_CHANNEL_ACCEPTANCE_CONTRACT_2026-10-28.md / v1.0 / APPROVED / FROZEN / unchanged
ROUTER_SKILL_INVOKED = YES / read manually; POL-CHAT-CODEX-ROUTING-01 v1.2 unavailable
ROUTING_MODE_ACTUAL = DIRECT
AGENTS_USED = NONE
INITIAL_FAILURES = 73 PASS / 5 FAIL; five reproduced individually
FIVE_FAILURES_RESOLVED = YES
CORRECTIVE_CYCLES_USED = 1 / maximum 2
GATE_A = PASS
FOCUSED_REGRESSION = PASS / 79 S9 + 9 affected S8 tests
GATE_B = BLOCKED
GATE_C = BLOCKED
T24 = PASS / T24-A..J covered by passing S9 tests
AUDIT_DURABILITY = PASS / acknowledged persistence failures enter durable quarantine
QUARANTINE_AFTER_REOPEN = PASS / new object and bounded independent process
FAIL_CLOSED_AFTER_RESTART = PASS / new operation rejected after quarantine re-open
NO_FALSE_SUCCESS = PASS / audit-unavailable and expired-deadline cases block launch
LEDGER_TAMPER_HANDLING = CORRUPTION/CHAIN VALIDATION; NOT AUTHENTICATED TAMPER PROTECTION
WINDOWS_ASYNCIO_PREFLIGHT = BLOCKED / Python loopback socketpair fallback hangs
FOCUSED_TESTS = PASS / 79 S9 tests; five former failures retested individually; 9 affected S8 tests
FULL_OFFLINE_REGRESSION = BLOCKED / not run because runtime preflight failed
RUFF = PASS
COMPILEALL = PASS
GIT_DIFF_CHECK = PASS / exit 0; line-ending warnings on pre-existing tracked WIP
UNTRACKED_FILE_QA = PASS / 8 S9 source/test files checked for trailing whitespace and final newline
SECURITY_REVIEW_SCOPED = BLOCKED / no authoritative native scan context available
CRITICAL_FINDINGS = NOT_ASSESSED / no zero-findings claim
REAL_TELEGRAM_CALLS = 0
OPERATIONAL_DB_WRITES = 0
GIT_STAGE_COMMIT_PUSH = NOT_EXECUTED
G0_REAL_EXECUTION = NOT_AUTHORIZED
DELIVERY_STATUS = SENT / DESTINATION=Projeto Telegram 3.0 / THREAD_ID=6add6aa9-12e0-83e8-b02f-870f0a0edaf9 / SEND_ATTEMPT_COUNT=1 / MESSAGE_SENT=YES / TOOL_IS_ERROR_FALSE
```

## Gate A — correções funcionais e T24

A execução focal inicial, em Python 3.14.7, registrou 73 aprovados e cinco
falhos. Os cinco casos foram repetidos isoladamente; nenhum teste teve sua
assertion enfraquecida ou alterada para obter aprovação.

| TEST_ID / TEST_NAME | EXPECTED → OBSERVED | CLASS / ROOT_CAUSE | CORRECTION / RETEST |
|---|---|---|---|
| `test_profile_f_limits_and_rollback` | Snapshot utilizável após reserva acima do limite → `CRITICAL_AUDIT_QUARANTINED` | `PRODUCT_DEFECT`: rejeição de regra de negócio no commit final era tratada como falha do audit sink. | Separadas rejeições transacionais de falhas de persistência/replay. Reteste individual: PASS. |
| `test_terminal_with_pending_reservation_is_detected_as_invalid` | `TERMINAL_RESERVATION_INVALID` → `AUDIT_STATE_MISMATCH` | `PRODUCT_DEFECT`: a comparação genérica do replay precedia a validação da invariante terminal. | A invariante terminal é reportada antes do erro genérico. Reteste individual: PASS. |
| `test_audit_rejects_secret_canary_in_event_fields` | Evento recusado, canário sanitizado e snapshot ainda consultável → `CRITICAL_AUDIT_QUARANTINED` | `PRODUCT_DEFECT`: payload inválido era confundido com falha de confirmação do canal durável. | Tipo e detalhes do evento são validados/sanitizados antes da mutação; falhas posteriores de durabilidade continuam fail-closed. Reteste individual: PASS. |
| `test_global_deadline_prevents_launch_when_already_expired` | `GLOBAL_DEADLINE_EXCEEDED_BEFORE_LAUNCH` → `GLOBAL_DEADLINE_INVALID` | `PRODUCT_DEFECT`: deadline válido já expirado era classificado como configuração malformada. | Expiração anterior ao lançamento recebe motivo terminal próprio. Reteste individual: PASS. |
| `test_receipt_refuses_overwrite` | `RECEIPT_ALREADY_EXISTS` sem substituir o recibo → `RECEIPT_PERSISTENCE_FAILED` | `PRODUCT_DEFECT`: conflito de destino existente era convertido em falha genérica e degradava indevidamente o gate de auditoria. | Persistência distingue se esta chamada realmente fez o rename; conflito preserva o arquivo anterior e retorna o motivo estável. Reteste individual: PASS. |

Referências de contrato: §7–§10 e §12–§13 de S9 v1.0; especialmente
S9-L04 (orçamento), S9-L10–L12 (timeouts/deadline/cancelamento), §9
(segredos) e §10 (integridade e recovery). O contrato permaneceu congelado.

Os quatro arquivos de teste S9 passaram juntos: **79 passed** em 38,14 s.
Os cinco casos acima passaram em retestes isolados. A suíte S8 de configuração
e logging afetada passou: **9 passed** em 1,03 s. T24-A–J passou na cobertura
focal, incluindo sink indisponível antes do lançamento do filho, falha de
escrita/commit/sync, cadeia adulterada, evento terminal inconsistente,
sanitização do canário, preservação de reserva anterior e bloqueio de nova
operação. O marcador de quarentena foi observado após reabertura com novo
objeto e em subprocesso independente limitado. Isso prova a persistência
entre processos coberta pelo teste; não demonstra resistência a perda súbita
de energia em todos os filesystems.

As gravações SQLite feitas durante os testes foram apenas em fixtures/ledgers
sintéticos temporários do workspace, nunca em banco operacional.

Correções de produção limitadas a `s9_operational_ledger.py` e
`s9_supervisor.py`. O arquivo de teste S9 do ledger ganhou asserts/prova
adicional para quarentena durável, preservação de reserva, bloqueio após
reinício e sanitização. As rejeições por orçamento agora preservam a reserva
anterior e não colocam o ledger em quarentena por engano.

## Gate B — runtime Windows e regressão integral

Preflight executado com timeout externo explícito:

```text
Python 3.14.7: asyncio.run(asyncio.sleep(0)); timeout em 10,092 s.
Stack: socket.accept → _fallback_socketpair → ProactorEventLoop._make_self_pipe.
PID 30348 encerrado; ausente na verificação posterior.
```

Uma prova direta de `socket.socketpair()` bloqueou no mesmo `accept` por 8 s
(PID 37252, encerrado) e uma prova equivalente com Python 3.15.0 bloqueou por
8 s ao criar o event loop (PID 35468, encerrado). A política Proactor e o
executor/loopback são fatores observados; a causa de sistema subjacente não
foi isolada. Há evidência histórica de bloqueio também no Selector. Os três
PIDs estavam ausentes após encerramento; não houve descendentes.

O Python 3.14.7 do `.venv` tem pytest 9.1.1. O Python 3.15.0 do sistema não
tem pytest disponível. A primeira invocação de pytest também encontrou a
restrição do diretório temporário padrão; as suítes focais foram repetidas
com `--basetemp` dentro do workspace. Como o preflight mínimo continua
bloqueado, a regressão offline integral não foi iniciada: coleta, contagens e
exit code da suíte integral ficam `NOT_RUN`. Não houve alteração de firewall,
rede ou política global.

## Gate C — revisão de segurança delimitada

Foi solicitada uma revisão Standard pelo conector nativo Codex Security,
delimitada a `src/telegram_courses`, com os testes S9/S8 indicados apenas
como evidência auxiliar. A primeira resposta veio truncada antes de expor
`scanId`, `scanDir` ou token de continuação. A tentativa de reentrada com o
mesmo escopo retornou `sqlite3.OperationalError: database is locked`. Não
foi iniciada outra varredura nem usado fluxo de terminal para contornar o
estado. Sem contexto autoritativo, Gate C não pode ser declarado completo.

`CRITICAL_FINDINGS=NOT_ASSESSED`; isso não significa ausência de findings.
Também não foram concluídas as verificações de paths/reparse points, TOCTOU,
PID reuse, contenção da árvore, concorrência de reservas, subprocessos e
dependências críticas solicitadas no card.

Limitação de integridade observável no desenho: a cadeia de hashes do ledger
permite detectar inconsistências, mas sem chave/âncora confiável não autentica
alterações feitas por alguém que controle o banco e recalcule a cadeia.
Portanto, `INTEGRITY_CHECK` e detecção de corrupção não equivalem a
`AUTHENTICATED_TAMPER_PROTECTION`. A atividade não alterou essa garantia.

## QA, limites e continuidade

Ruff passou para os 11 arquivos Python selecionados; `compileall -q src`
passou; `git diff --check` terminou com exit 0. Os avisos LF→CRLF vieram dos
arquivos rastreados de continuidade/governança e `cli.py` já modificados no
preflight. A verificação adicional de whitespace/newline dos oito arquivos
S9 não rastreados passou.

Riscos/limitações residuais: a integração real de filas/bytes não foi
exercitada; a amostragem de memória não é enforcement rígido; deadline
persistido usa relógio de parede entre processos; a persistência após crash
de energia não foi demonstrada; e a proteção contra adulteração externa
continua sem autenticação criptográfica. O Gate C incompleto impede concluir
que todos os riscos materiais foram identificados.

No início, o worktree tinha sete arquivos rastreados modificados e extenso
WIP não rastreado. Nenhum WIP não relacionado foi apagado; HEAD e branch
permaneceram inalterados e nenhum caminho foi staged. Os arquivos S9 de
código/teste editados já eram WIP não rastreado no preflight. Além deste
relatório, a reconciliação acrescenta registros em `PROJECT_STATE.md`,
`CONTINUITY_RECORD.md` e `handoff/LAST_HANDOFF.md` sem reescrever o histórico.

```text
FILES_CHANGED = src/telegram_courses/s9_operational_ledger.py;
  src/telegram_courses/s9_supervisor.py;
  tests/unit/test_s9_operational_ledger.py;
  docs/reports/S9_G0_FINAL_CORRECTION_02/REPORT.md;
  docs/continuity/PROJECT_STATE.md;
  docs/continuity/CONTINUITY_RECORD.md;
  docs/continuity/handoff/LAST_HANDOFF.md
WIP_PRESERVED = YES / unrelated paths retained / STAGED_PATHS=0
OBSERVABILITY_LIMITATIONS = full regression blocked; formal security findings unassessed; real queues/bytes, hard RSS enforcement, cross-process monotonic deadline, and authenticated tamper protection unproven
ACCEPTANCE_RECOMMENDATION = DO_NOT_RECOMMEND_INTEGRAL_OFFLINE_ACCEPTANCE / Gates B and C incomplete
BLOCKERS = asyncio/socketpair loopback hang; unavailable native security scan context
NEXT_EXACT_ACTION = Recover the authoritative context of the existing native security scan; resolve the Windows executor socketpair preflight, run full offline regression, then prepare a new decision package. Real G0 remains unauthorized.
DELIVERY_STATUS = SENT / DESTINATION=Projeto Telegram 3.0 / THREAD_ID=6add6aa9-12e0-83e8-b02f-870f0a0edaf9 / SEND_ATTEMPT_COUNT=1 / MESSAGE_SENT=YES / TOOL_IS_ERROR_FALSE
G0_REAL_EXECUTION = NOT_AUTHORIZED / S9_REAL=NOT_STARTED / S10=NOT_AUTHORIZED
OPERATIONAL_DB_WRITES = 0 / TELEGRAM_RPC=0 / GIT_STAGE_COMMIT_PUSH=NOT_EXECUTED
```
