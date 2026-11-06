# Fechamento do Gate C4 — SIGINT / Ctrl+C

```text
ACTIVITY_ID = TELEGRAM-3-CLI-V1-SLICE-C-C4-CLOSURE-01
PARENT = TELEGRAM-3-CLI-V1-SLICE-C-REVIEW-01
CONTRACT = CLI V1 v0.2
SCOPE = C4_EVIDENCE_CLOSURE_ONLY
MODE = DIRECT
RESULT = SLICE_C_C4_READY_FOR_CANONICAL_ACCEPTANCE
IMPLEMENTATION = NOT_AUTHORIZED / NO_PRODUCTION_CHANGE
REAL_TELEGRAM = NOT_EXECUTED
REAL_DOWNLOAD = NOT_EXECUTED
OPERATIONAL_DATABASE = NOT_ACCESSED
COMMIT_PUSH = NOT_EXECUTED
```

## 1. Ambiente e preservação

- Repositório: `projeto_telegram_courses`.
- Branch: `work/s0-bootstrap`.
- HEAD no início e no fim: `cdbe0a8cd9e432c04a9e04a55048dade07ebc852`.
- O worktree já estava sujo, com alterações WIP de Slice A/B/C e documentação. Nenhum arquivo de produção ou teste foi alterado nesta atividade; o WIP foi preservado e nada foi staged.
- Os harnesses de processo e diretórios de teste criados para esta validação usaram somente dados sintéticos, SQLite temporário e o gateway em memória da `OfflineCourseSandbox`. Foram removidos após a coleta das evidências.
- O comando público permaneceu sem habilitação da execução Slice C. O harness chamou a orquestração offline real (`run_offline_with_rich` → `OfflineCourseSandbox.execute` → `DownloadQueue` S5) com dependências sintéticas injetadas para teste.

## 2. Mecanismos de interrupção distinguidos

| Mecanismo | Evidência | Resultado |
|---|---|---|
| `asyncio.Event` | Teste focado antes da admissão | PASS |
| `Task.cancel()` | Teste focado durante transferência e retomada | PASS |
| Sinal efetivo do processo | Subprocesso Windows com console isolado; `GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)`; handler padrão de `asyncio.run` | PASS |
| Exceção `KeyboardInterrupt` injetada | Não foi injetada nem contabilizada como sinal | NÃO USADA |
| Ctrl+C digitado manualmente no PowerShell | Não executado; é uma evidência separada | NÃO EXECUTADO |

O sinal do processo foi efetivamente enviado pelo mecanismo de console do Windows; não foi inferido a partir de uma exceção simulada. Os subprocessos finais terminaram com código 0 após retornarem o resumo de cancelamento. Os dois eventos de console foram controlados por barreiras determinísticas no harness, sem abrir o comando público.

## 3. Matriz C4

| Cenário | Estado | Evidência observada |
|---|---|---|
| **C4-01 — interrupção antes do primeiro payload** | **PASS** | O filho anunciou a barreira `BEFORE_FIRST_PAYLOAD`; o supervisor enviou `CTRL_C_EVENT`; `asyncio.run` retornou `CANCELADO`. Duas mídias estavam selecionadas/elegíveis, ambas ficaram explicitamente `CANCELLED`, nenhuma identidade foi chamada no gateway e nenhum registro de download ou `.part` foi criado. Processo: exit code 0. |
| **C4-02 — interrupção durante o primeiro arquivo** | **PASS** | A barreira só foi anunciada depois de 60 bytes serem escritos, sincronizados e checkpointados. O `CTRL_C_EVENT` produziu resumo `CANCELADO`. SQLite: primeira mídia `FAILED_RETRYABLE`, `downloaded_bytes=60`, `expected_bytes=120`, `failure_category=CANCELLED`, `owner_pid=NULL`. O `.part` permaneceu com 60 bytes. Processo: exit code 0. |
| **C4-03 — arquivo seguinte não admitido** | **PASS** | O plano continha as identidades sintéticas `(-1001, 10, 0)` e `(-1001, 20, 0)`. Antes da interrupção, apenas `(-1001, 10, 0)` foi chamada no gateway. Após o cancelamento não houve chamada para `(-1001, 20, 0)`; ambas as identidades aparecem no resultado como `CANCELLED`. |
| **C4-04 — parcial, ownership, checkpoint e SQLite** | **PASS** | Antes da retomada: arquivo parcial físico de 60 bytes, checkpoint SQLite de 60/120, estado `FAILED_RETRYABLE`, falha `CANCELLED` e ownership liberado (`owner_pid=NULL`). Não houve promoção a concluído. Após retomada autorizada, ambos os registros terminaram `DOWNLOADED`, com 120/120 e 80/80 bytes e `owner_pid=NULL`; não restou `.part`. |
| **C4-05 — resultado e contagens por identidade** | **PASS** | Resumo autoritativo e Rich: `CANCELADO`, selecionados=2, elegíveis=2, concluídos=0, pendentes=0, cancelados=2, falhos=0, bloqueados=0. As duas identidades aparecem com estado/motivo `CANCELLED`. `pendentes=0` não oculta a segunda mídia: a fila registrou explicitamente seu cancelamento sem admiti-la. O Rich mostrou o resumo `CANCELADO` e a linha de pendentes. |
| **C4-06 — retomada e integridade** | **PASS** | O plano fresco reconheceu `part_bytes=60`. Após confirmação sintética separada, a retomada concluiu as duas mídias. Prova: `proof_verified_bytes=120`, `proof_received_bytes=120`; overlap recebido=60; bytes validados=200; orçamento contabilizado=320; resultado `CONCLUIDO`. O parcial foi preservado até a prova e a conclusão; os arquivos finais tiveram exatamente os tamanhos esperados. O tráfego adicional de prova e overlap decorre dos controles S6, não de promoção do prefixo local como válido. |
| **C4-07 — sinal no Windows** | **PASS** | Subprocessos em consoles isolados receberam `CTRL_C_EVENT` efetivo, antes do payload e após 60 bytes persistidos. A execução real da orquestração offline devolveu resumo consolidado e terminou normalmente. Isso prova o evento controlado de console no harness; não prova digitação manual de Ctrl+C no PowerShell 5.1. |

## 4. Testes e validações

Cinco testes focados passaram (`5 passed in 4.06s`):

- cancelamento antes da admissão no gateway fake;
- cancelamento durante transferência por `asyncio.Event`;
- cancelamento durante transferência por `Task.cancel()`;
- accounting S5 de requisição em voo cancelada;
- preview de retomada S5 sem mutação.

As duas parametrizações da integração provaram `.part` de 60 bytes, ausência de admissão do próximo arquivo e retomada sob a integridade existente. A inspeção de estado após o SIGINT efetivo foi feita também no subprocesso, separadamente dos testes de tarefa.

O primeiro pytest no executor restrito não pôde abrir o SQLite sob `%TEMP%`; o dump de pilha mostrou o Proactor do Python 3.14 bloqueado no socketpair local (`socket.accept`) interno do `asyncio`. Com o diretório temporário colocado dentro do workspace e a permissão de execução necessária ao socketpair local, os cinco testes concluíram. Essa falha foi do ambiente de execução, não dos casos de produto.

- Ruff nos módulos S5/S6, orquestração/progresso Slice C e testes diretamente pertinentes: **PASS** (`All checks passed`).
- `git diff --check`: **PASS**. O Git emitiu somente avisos de conversão LF/CRLF em arquivos WIP preexistentes; nenhum erro de whitespace.
- Não foi executada suíte global.

## 5. Integridade, escopo e limitações

- Cancelamento não promoveu o arquivo incompleto: o registro permaneceu `FAILED_RETRYABLE`, o prefixo físico e checkpoint coincidiram em 60 bytes, e o ownership foi liberado.
- O arquivo seguinte foi listado como cancelado por identidade, sem chamada ao gateway.
- A retomada passou pelo plano fresco, prova do prefixo, overlap e validação do downloader existente. Nenhuma regra S5/S6/S9, schema ou contrato foi alterada.
- Não houve Telegram RPC, autenticação, sessão, download real, banco operacional, segredo, alteração de produção, alteração de teste, staging, commit ou push.
- O comando público não foi usado para habilitar execução da Slice C; o teste de processo chamou a orquestração offline real com o gateway fake.
- Ctrl+C manual no PowerShell 5.1 continua uma evidência separada e não foi executado. Não foi usada exceção `KeyboardInterrupt` para substituir o sinal efetivo.
- Nenhum defeito de produção foi reproduzido. Duas tentativas preliminares do harness foram descartadas por problemas do próprio harness (limpeza/codificação e patch do stream não restaurado antes da retomada); a execução final corrigida foi repetida e terminou com exit code 0 e evidências consistentes.

## 6. Parecer

**`SLICE_C_C4_READY_FOR_CANONICAL_ACCEPTANCE`** — os cenários C4-01 a C4-07 passaram com evidência offline; o evento SIGINT/console foi exercitado como sinal real do Windows, e os resultados, partial, checkpoint, ownership e retomada foram observados. A validação manual no PowerShell 5.1 não foi alegada.

Este parecer fecha somente a evidência C4 e aguarda revisão canônica. Não aceita toda a Slice C, não inicia Slice D e não autoriza operação Telegram real.

## 7. Entrega

Destino solicitado: chat canônico **Projeto Telegram 3.0**. O relatório sanitizado foi enviado por MCP e o readback confirmou a mensagem e a resposta canônica (`SENT / READBACK_OBSERVED`). O chat reconheceu o Gate C4 como aprovado e recomendou `SLICE_C_ACCEPTED_OFFLINE_WITH_FINDINGS`; também solicitou decisão humana formal para o aceite da Slice C e autorização separada para a Slice D. Essa pergunta permanece pendente e não foi tratada como autorização.
