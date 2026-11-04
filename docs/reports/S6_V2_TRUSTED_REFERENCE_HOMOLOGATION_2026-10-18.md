# S6 V2 TRUSTED_REFERENCE — relatório de homologação

**Data:** 2026-10-18  
**Atividade:** `S6_V2_TRUSTED_REFERENCE_ENABLEMENT`  
**Escopo:** homologação offline e sintética do perfil isolado `TRUSTED_REFERENCE`.  
**Estado deste relatório:** gates da homologação offline PASS; preflight `READY` para apresentar ao usuário a autorização separada de prova real. Nenhuma prova real foi autorizada.

## Resultado corrente

O harness e o launcher protegido foram habilitados para o perfil controlado `TRUSTED_REFERENCE`, com seleção de prefixo, orçamento específico, proteção de path e referência, confirmação nativa restrita e relatórios/ledger/reconciliação. Este relatório não autoriza execução no Telegram. Não houve chamada real ao Telegram nem download real; a referência original permaneceu somente leitura. V1 permanece canônico e ativo; V2 continua sem promoção global e inefetiva. Aceite formal S6 continua pendente e checkpoint da sprint permanece diferido.

O conjunto focado anterior registrou 14 testes aprovados e 1 skip; uma rodada intermediária registrou 146 aprovados. Duas execuções agregadas anteriores falharam intermitentemente no teste legado `test_two_process_handoff...unaligned-prepared` (`KeyError: attempts`), fora do harness `TRUSTED_REFERENCE`; uma execução isolada do caso passou. Classificação do root: flakiness observada, não reproduzida na última rodada. A rodada nativa final passou com 235 testes em 98,47 s, incluindo o E2E sintético TRUSTED_REFERENCE de dois processos. Comando: `pytest -q tests/manual_proofs/test_s6_v2_proof_harness.py tests/unit/test_s6_v2.py tests/unit/test_downloads.py tests/integration/test_download_flow.py tests/integration/test_s5_download_flow.py`, `.venv`, `TEMP`/`LOCALAPPDATA` nativos e `--basetemp .pytest-s6-trusted-regression-diagnostic`.

## Alvo, referência e integridade

O alvo controlado permanece `-1002368271467`, mensagem `7603`, ordinal `0`, `DOCUMENT`, media ID `5089068167339181674`, tamanho `1,119,129,690` bytes. A referência original tem SHA-256 `3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c`. A referência é somente leitura. Sua proveniência está documentada, mas não foi atestada independentemente.

O perfil exige comparação integral dos bytes recebidos com a referência, igualdade exata de tamanho e SHA-256, verificação da referência antes/depois e dois processos distintos com checkpoint persistente validado. A conclusão `COMPLETED_V2` requer todos os gates de integridade, lifecycle e evidência. As quatro saídas contratuais são `TRUSTED_REFERENCE_MATCH`, `TRUSTED_REFERENCE_MISMATCH`, `INCOMPLETE` e `BLOCKED`; divergência observada não pode ser rebaixada a origem não verificada. A validação corrente é sintética; o teste reportou correspondência com a fixture de referência sintética. Nenhum match de mídia real ou autenticidade de origem real é afirmado.

## Comparação de budgets

Parâmetros do contrato: `E=1,119,129,690` bytes; `C=262,144` bytes; prefixo alinhado `P`, `0<P<E`; duas tentativas reservadas para fase 2; `H=ceil(E/C)+1=4,271`. `F1=ceil(P/C)` chamadas úteis de `GetFile` na fase 1; `F2=ceil((E-P)/C)` chamadas úteis e cap `GetFile` por tentativa fase 2; cap `GetFileHashes` por tentativa fase 2 `H`; agregado GetFile `F1+2×F2`; agregado de hashes remotos `2×H=8,542`; reserva de payload quantizada `F1×C+2×F2×C`. O teto auxiliar de identidade é cinco `GetMessages`; contagem de streaming não incluída pelo contador de requests deve ser declarada parcial/desconhecida.

| Perfil | Prefixo | Fase 1 GetFile | Fase 2 GetFile por tentativa | GetFile agregado com 2 tentativas fase 2 | GetFileHashes agregado | Payload reservado |
|---|---:|---:|---:|---:|---:|---:|
| Default | 8 MiB / 8,388,608 B | 32 | 4,238 | 8,508 | 8,542 | 2,230,321,152 B |
| Alternativo | 128 MiB / 134,217,728 B | 512 | 3,758 | 8,028 | 8,542 | 2,104,492,032 B |

A opção default de 8 MiB usa 480 chamadas úteis agregadas de `GetFile` e 125,829,120 bytes reservados a mais que 128 MiB no envelope de duas tentativas. Ambos os perfis correspondem a 4,270 chunks úteis se uma retomada concluir. O prefixo menor, portanto, não implica menor orçamento agregado. O contrato recomenda 8 MiB para limitar a parcela inicial pré-checkpoint.

## Evidências e gates

| Gate | Estado corrente | Evidência/limite do registro |
|---|---|---|
| Testes unitários e regressão agregada | `PASS / 235 passed in 98.47s` | Comando da suíte final abaixo; inclui S6 V2, downloads S4/S5 e o harness manual. Duas falhas agregadas anteriores no teste comum são registradas como intermitentes, não reproduzidas na rodada final. |
| E2E sintético TRUSTED_REFERENCE de dois processos | `PASS` | Incluído na rodada nativa agregada final: 235 passed. |
| Igualdade e divergência, falha de referência, erros de checkpoint, violação de budgets e paths | `PASS / suíte final` | Rodada agregada nativa completa passou; detalhes das tentativas anteriores do teste comum intermitente preservados acima. |
| DryRun launcher nativo, prefixo 8 MiB | `PASS` informado | Execução nativa reportada pelo root; não é prova real. |
| DryRun launcher nativo, prefixo 128 MiB | `PASS` informado | Execução nativa reportada pelo root; não é prova real. |
| Ruff | `PASS` | Revalidado após a última edição de asserção. |
| Compilação Python | `PASS` | Revalidada após a última edição de asserção. |
| Parser PowerShell | `PASS` | Revalidado após a última edição de asserção. |
| `git diff --check` | `PASS` | Reexecutado após remover somente blank lines extras no EOF dos três documentos de continuidade; sem erros de whitespace (apenas avisos de normalização LF/CRLF). |
| Budget comparison | `PASS_CALCULATED / PASS_REPORTED_DRYRUNS` | Fórmulas conferidas contra o contrato e ambos os DryRuns nativos passaram. A suíte agregada final passou; as duas falhas anteriores no teste comum foram intermitentes e não reproduzidas na última rodada. |
| Caminho nativo <=240 caracteres | `PASS` | DryRuns nativos em ambos os prefixos passaram; checks agregados também passaram na rodada final. |
| Proteção da referência original | `PASS` informado | Referência permaneceu somente leitura segundo o resultado comunicado para esta atividade; verificação/hash antes/depois da execução final ainda deve ser reconciliada. |
| Chamadas reais/download real | `PASS / ZERO` | Escopo offline informado: zero chamadas Telegram e nenhum download real. |
| Regressão S5/S6 | `PASS` | Rodada agregada nativa final: 235 passed em 98.47s; duas falhas intermitentes anteriores do teste comum não reproduzidas na última execução. |
| `SAFETY_GATE` | `PASS / OFFLINE` | Nenhuma prova real autorizada; V1 ativa, V2 inefetiva. |

Os resultados são reportados pelo root; não houve designação de logs/JSON duráveis, e JSONs sob `.pytest-*` são transitórios, portanto não são citados como evidência durável. A suíte final foi executada com o comando/configuração registrados acima. Falhas intermitentes anteriores são mantidas no histórico; a rodada final limpa passou. `git diff --check` foi repetido após a limpeza de EOF e passou sem erros; a saída mostrou somente avisos de normalização LF/CRLF.

## Estado de autoridade e publicação

```text
TRUSTED_REFERENCE_HARNESS = PASS / 235 native suite tests
TRUSTED_REFERENCE_SYNTHETIC_E2E = PASS / included in 235-test suite
REFERENCE_PROTECTION = PASS / synthetic final comparison passed; original remained read-only
BUDGETS_RECONCILED = PASS / both native DryRuns and formula comparison passed
NATIVE_PATH_GATE = PASS / native DryRuns and final suite
S5_S6_REGRESSION = PASS / final native suite 235 passed in 98.47s
SAFETY_GATE = PASS / OFFLINE
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
V1_ACTIVE = YES
V2_CANONICAL_PROMOTION = NO
V2_GLOBAL_ACTIVATION = NO
V2_EFFECTIVE = NO
REAL_PROOF_AUTHORIZATION = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
TRUSTED_REFERENCE_PREFLIGHT = READY
NEXT_ACTION = USER_CONTROLLED_REAL_PROOF_AUTHORIZATION
```

O preflight técnico para futura prova real é `READY` após os gates offline passarem. A confirmação nativa continua fechada; o próximo passo é apresentar o resultado ao usuário para autorização separada e explícita de prova real. Este relatório não concede essa autorização. Evidência prévia: [contrato de homologação](../contracts/S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_CONTRACT_2026-10-18.md), [preflight anterior](S6_V2_TRUSTED_REFERENCE_PREFLIGHT_2026-10-18.md) e [relatório de isolamento de runtime](S6_RUNTIME_ISOLATION_2026-10-18.md). Esse preflight anterior descreve o estado pré-implementação e deve ser lido como histórico, não como resultado dos gates desta atividade.






