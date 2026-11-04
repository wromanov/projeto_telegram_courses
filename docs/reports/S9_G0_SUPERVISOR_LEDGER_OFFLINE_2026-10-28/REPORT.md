# S9-G0 — Supervisor Windows e Operational Ledger

**Atividade:** `TELEGRAM_S9_G0_SUPERVISOR_LEDGER_2026-10-28`  
**Data de validação:** 2026-10-29  
**Contrato:** S9 RASMOO v1.0 — `APPROVED / FROZEN`  
**Branch / HEAD:** `work/s0-bootstrap` / `d36e96055a26556221bc487717f18ed322c76f02` (inalterado)

## Resumo

Foram implementados o supervisor Windows com Job Object, o ledger SQLite
isolado e a integração externa limitada ao comando existente `smoke`. O
handshake de confirmação humana foi conectado ao caminho de confirmação da
fila na CLI e testado com processos sintéticos. Nenhum login, scan, download,
RPC Telegram, banco operacional ou publicação Git foi executado.

A validação focada S9 passou: **68 testes**. `compileall`, Ruff dos arquivos
da atividade e `git diff --check` passaram. A regressão completa do repositório
foi bloqueada antes da suíte S9: o loop Proactor do Python 3.14.7 fica parado
criando o self-pipe com `socket._fallback_socketpair().accept()`. Uma execução
diagnóstica com Selector também parou nesse self-pipe. O scan de segurança
formal continua incompleto porque o working tree contém 3.415 itens de diff e
não há runtime utilizável para revisão delegada.

## Estado solicitado

```text
ACTIVITY_ID = TELEGRAM_S9_G0_SUPERVISOR_LEDGER_2026-10-28
ROUTER_SKILL_INVOKED = YES / codex-task-router skill, catalog, model-policy e routing-matrix lidos
ROUTING_MODE_ACTUAL = MULTIAGENT / 2 componentes independentes com ownership delimitado
MULTIAGENT_GATE_DECISION = JUSTIFIED / supervisor e ledger independentes; root reteve integração e QA
AGENTS_USED = /root/s9_supervisor; /root/s9_ledger
ROUTING_POLICY_ARTIFACT = POL-CHAT-CODEX-ROUTING-01 v1.2 não encontrado; não alegada como lida
CONTRACT_STATUS = APPROVED_FROZEN / S9 v1.0
IMPLEMENTATION_STATUS = COMPONENTES OFFLINE IMPLEMENTADOS / aceitação formal pendente
INTEGRATION_STATUS = PARTIAL / CLI smoke supervisionada; fila real não habilitada neste runner
SUPERVISOR_OFFLINE_GATE = PASS / processos Windows sintéticos e receipt
LEDGER_OFFLINE_GATE = PASS / WAL, integridade, caps, concorrência, crash e incerteza
PROCESS_CONTROL_OFFLINE_GATE = PASS / Job Object; falhas de contenção mantêm gate BLOCKED
MEMORY_MONITORING_OFFLINE_GATE = PASS / Working Set, Peak Working Set, Private Bytes e baseline sintética
G0_REAL_EXECUTION_GATE = NOT_AUTHORIZED / BLOCKED
FOCUSED_TESTS = PASS / 68 passed / testes unitários S9
NEGATIVE_TESTS = PASS_COM_LACUNA_T24 / T21-T23, T25-T27 e T29 negativos cobertos; T24 bloqueado
WINDOWS_PROCESS_PROOF = PASS / timeout, cancelamento, descendente, TTY herdado e contenção
MEMORY_MEASUREMENT = PASS / PROCESS_MEMORY_COUNTERS_EX / amostragem-alvo 250 ms
FULL_OFFLINE_REGRESSION = BLOCKED / 433 coletados; Proactor trava antes de alcançar testes S9
RUFF = PASS / arquivos S9 alterados; GLOBAL BLOCKED / 2.877 violações em WIP e evidências existentes
COMPILEALL = PASS / src
GIT_DIFF_CHECK = PASS / avisos LF->CRLF em arquivos já modificados
SECURITY_REVIEW = PARTIAL / subconjunto S9 revisado; scan de 3.415 itens continua RUNNING e não concluído
OBSERVABILITY_GAPS = logging S8 best-effort sem gate de falha; bytes medidos e limites não integrados a uma fila real; sampling não é firewall de tempo real; scan amplo incompleto
FILES_CHANGED = cli.py; s9_supervisor.py; s9_supervisor_handshake.py; s9_supervisor_cli.py; s9_operational_ledger.py; 4 testes S9; este relatório; PROJECT_STATE; CONTINUITY_RECORD; LAST_HANDOFF
WIP_PRESERVED = YES / nenhum arquivo preexistente descartado ou sobrescrito intencionalmente
REAL_TELEGRAM_CALLS = 0
OPERATIONAL_DB_WRITES = 0 / somente ledgers sintéticos separados em diretórios temporários da atividade
GIT_STAGE_COMMIT_PUSH = NOT_EXECUTED
BLOCKERS = regressão completa no Proactor; T24 logging fail-fast; scan completo de segurança; autorização real não concedida
NEXT_EXACT_ACTION = executar regressão completa em host Windows com socketpair funcional; fechar T24 e revisão de segurança antes de propor qualquer autorização G0 real
DELIVERY_STATUS = SENT / DESTINATION=Projeto Telegram 3.0 / THREAD_ID=6add6aa9-12e0-83e8-b02f-870f0a0edaf9 / SEND_ATTEMPT_COUNT=1 / MESSAGE_SENT=YES / TOOL_IS_ERROR_FALSE
PROJECT_STATE_RECONCILIATION = PASS / estado de código offline e bloqueios reconciliados; S9 real permanece NOT_STARTED
ACTIVITY_COMPLETION_PERCENT = PARTIAL / 96%
FINAL_RESULT = S9_G0_OFFLINE_COMPONENTS_IMPLEMENTED / ACCEPTANCE_AND_FULL_VALIDATION_PENDING
```

O artefato `POL-CHAT-CODEX-ROUTING-01 v1.2` não estava disponível; a skill
interna do roteador e as referências presentes foram aplicadas. O roteamento
delegado foi autorizado pelo card quando havia ganho material entre supervisor
e ledger. Os dois agentes entregaram seus componentes; a integração e a
validação final foram retomadas pelo root depois que os agentes atingiram
limite de uso.

## Alterações

- `src/telegram_courses/s9_supervisor.py`: processo suspenso, associação a Job
  Object `KILL_ON_JOB_CLOSE`, inventário de descendentes, timeouts, deadline
  global, cancelamento cooperativo, contenção, métricas nativas Windows e
  receipt sanitizado sem overwrite.
- `src/telegram_courses/s9_operational_ledger.py`: ledger WAL separado com
  integridade, pseudônimos HMAC, limites F/M, reservas, incerteza conservadora,
  margem de disco e estados terminais persistentes.
- `src/telegram_courses/s9_supervisor_handshake.py` e `cli.py`: confirmação da
  fila escreve sinal de prompt fresco, aguarda liberação do supervisor e só
  então lê a resposta. Sem as variáveis internas do supervisor, a CLI preserva
  seu prompt atual.
- `src/telegram_courses/s9_supervisor_cli.py`: integração externa restrita a
  `python -m telegram_courses.cli smoke`, diretório novo e ledger separado.
  Flags adicionais e comandos `auth`, `scan` ou `download` são rejeitados.
  `limit_check=UNKNOWN` nunca é convertido em PASS; o classificador exige
  `LIMIT_CHECK_RESULT=PASS` além do processo e dos gates.
- Testes sintéticos em `tests/unit/test_s9_supervisor.py`,
  `tests/unit/test_s9_operational_ledger.py`,
  `tests/unit/test_s9_supervisor_handshake.py` e
  `tests/unit/test_s9_supervisor_cli.py`.

## Evidência de validação

O teste focal executado no Python 3.14.7/Windows terminou com `68 passed in
28.11s`. Ele usou processos Windows sintéticos, banco temporário e nenhum
payload Telegram. Uma execução real do wrapper `smoke` sob TTY terminou com
exit code externo 0, Job Object confirmado, sete amostras de memória e ledger
`COMPLETED`; o receipt manteve `limit_check_result=UNKNOWN`. Uma prova adicional
supervisionou processo filho e observou `stdin`, `stdout` e `stderr` como TTY.

O comando padrão da regressão completa coletou 433 testes e parou no primeiro
teste que cria `asyncio` na rotina de autenticação. O diagnóstico independente
registrou a thread parada em:

```text
socket.accept
socket._fallback_socketpair
asyncio.proactor_events._make_self_pipe
asyncio.windows_events.ProactorEventLoop
asyncio.runners.Runner._lazy_init
```

O teste isolado reproduziu o mesmo bloqueio com `asyncio.run(asyncio.sleep(0))`.
O loop Selector foi tentado apenas como diagnóstico e atingiu o mesmo
self-pipe. As tentativas foram interrompidas após confirmação do bloqueio; não
foram convertidas em SKIP nem registradas como regressão PASS.

Ruff dirigido aos oito arquivos de implementação/testes alterados passou. Ruff
global retornou 2.877 violações, concentradas em artefatos de teste/evidência
preexistentes no working tree; nenhum `--fix` foi usado. `compileall -q src`
e `git diff --check` terminaram com exit 0. O diff check emitiu apenas avisos
de normalização LF/CRLF para arquivos já modificados.

## Matriz T01–T30

| Caso | Status | Evidência / limite |
|---|---|---|
| T01 execução normal | PASS | Processo sintético, exit externo 0 e árvore vazia. |
| T02 exit não zero | PASS | Exit 7 permanece FAILED. |
| T03 timeout por etapa | PASS | Processo sintético contido no timeout. |
| T04 deadline global | PASS | Expiração antes e durante processo; contenção confirmada. |
| T05 cancelamento cooperativo | PASS | Evento de cancelamento e encerramento da árvore. |
| T06 descendente sobrevivente | PASS | Filho após saída do root é detectado e encerrado. |
| T07 falha de contenção | PASS | Falha simulada mantém gate BLOCKED e receipt sem confirmação falsa. |
| T08 Working Set excessivo | PASS | Limite excedido aciona contenção. |
| T09 crescimento excessivo | PASS | Crescimento de amostra após baseline aciona contenção. |
| T10 baseline e amostragem | PASS | Janela sintética de 2 s, mediana e intervalos medidos; processo herda TTY. |
| T11 reserva/consumo | PASS | Observed, Reserved e Uncertain separados no ledger. |
| T12 retry sem duplicação | PASS | Tentativas e recovery limitados por identidade. |
| T13 interrupção de gravação | PASS | Transação WAL interrompida preserva reserva anterior. |
| T14 ledger corrompido | PASS | Corrupção e banco estrangeiro falham fechados. |
| T15 reserva concorrente | PASS | Transações concorrentes são serializadas sem dupla reserva. |
| T16 bytes incertos | PASS | Reserva incerta continua cobrada. |
| T17 orçamento F/M | PASS | Caps individuais e agregado validados. |
| T18 tamanho individual | PASS | Limites F/M e fórmula M aplicados. |
| T19 disco insuficiente | PASS | Margem S5 e reserva S9 aplicadas. |
| T20 falha de consulta de disco | PASS | Falha é registrada como UNKNOWN e operação bloqueada. |
| T21 flag incompatível | PASS | Runner rejeita flags não autorizadas. |
| T22 V2 ativada | PASS | Runner rejeita `--v2-global` e opções extras; nenhum caminho V2 é lançado. |
| T23 supervisor indisponível | PASS | Falha antes do launch; receipt BLOCKED. |
| T24 logging falha | BLOCKED | Logging S8 suprime erros do handler e não sinaliza falha ao gate S9; sem alteração para preservar S8. |
| T25 segredo-canário | PASS | Ambiente filho remove variáveis `TELEGRAM_*`; canário sintético não aparece no ambiente construído. |
| T26 exit 0 + LIMIT_CHECK FAIL | PASS | Classificador retorna BLOCKED para FAIL e UNKNOWN. |
| T27 preservação após cancelamento | PASS | Reservas abertas tornam-se incertas em estado terminal; evidência de processo separada. |
| T28 nenhum acesso Telegram | PASS | Só `smoke` foi lançado e não chama gateway; supervisor não é firewall de rede. |
| T29 sem autorização | PASS | Runner rejeita `auth`, `scan` e comandos diferentes do smoke. |
| T30 sem órfão | PASS | Processo árvore confirmado encerrado nos ensaios sintéticos. |

## Segurança, cobertura e limitações

A revisão de código do subconjunto S9 não confirmou vulnerabilidade reportável.
Isso não equivale a uma conclusão sem findings sobre o working tree. O plugin
Codex Security exigiu `scope="."` para Review Changes e inventariou 3.415 itens
(1.797 `.py`, 1.554 `.json`, 39 `.toml`, além de outros formatos), em grande
parte evidências históricas e fixtures temporários já presentes. O preflight
ficou `ready` com aviso de ausência de workers delegados. O scan
`65a4c83f-92af-43b1-8af6-0fd843bdd78a` permanece `RUNNING`, sem conclusão e sem
findings validados; seu snapshot foi capturado antes da correção final da
janela de baseline, então não deve servir como conclusão de segurança para o
estado atual.

Limitações técnicas abertas:

1. T24 continua bloqueado: a semântica de log best-effort existente não expõe
   falha do handler ao supervisor. Uma operação real não pode alegar esse gate
   até decisão/correção compatível com S8.
2. A integração pública adicionada executa somente `smoke`. Não existe runner
   habilitado para a fila real nem integração de `settle_bytes` com evidência
   confiável de bytes efetivamente transferidos.
3. A medição por 250 ms e os contadores nativos são observações amostradas;
   não são isolamento de recursos em tempo real nem controle de rede.
4. O prazo persistido no ledger não coordena por si só G1–G9 entre vários
   processos/reinicializações. O deadline monotônico foi provado para uma
   invocação supervisionada.
5. O preflight do disco e o ledger são componentes offline; não foram ligados
   a um download real, nem a DB/session operacional.
6. NFR-02 com mídia real M de 1–2 GiB não foi executado. S9 real, S10 e aceite
   formal permanecem não iniciados.

## Restrições e continuidade

`docs/contracts/S9_RASMOO_REAL_CHANNEL_ACCEPTANCE_CONTRACT_2026-10-28.md`
permanece congelado e inalterado. O contrato não foi aceito formalmente por
este relatório. Nenhum arquivo foi staged; não houve commit nem push. O HEAD e
a branch permanecem nos valores registrados no início, e o WIP preexistente
foi preservado.

```text
REAL_TELEGRAM_RPC = 0
LOGIN / SCAN / DOWNLOAD REAL = NÃO EXECUTADOS
MIGRATION / BANCO OPERACIONAL = NÃO ALTERADOS
LEDGER S9 = SOMENTE ARQUIVOS SQLite ISOLADOS DE TESTE
GIT_STAGE_COMMIT_PUSH = NOT_EXECUTED
S9_REAL = NOT_STARTED / NOT_AUTHORIZED
S10 = NOT_STARTED / NOT_AUTHORIZED
SAFE_RESUME_POINT = manter S9 real bloqueado; resolver T24 e o bloqueio do Proactor; retomar a revisão de segurança a partir de escopo autorizado e snapshot atual
```
