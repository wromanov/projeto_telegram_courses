# Checkpoint de continuidade — Sprint S6, Gates A e B

- **Data do checkpoint:** 2026-10-24 (America/Sao_Paulo)
- **Atividade:** `S6_GATE_A_EXITCODE_ROOT_CAUSE_AND_B_TARGET_TRIAGE`
- **Repositório:** `C:\Users\walac\desenvolvimento\projeto_telegram_courses`
- **Branch / HEAD registrados:** `work/s0-bootstrap` / `98d9d6b9ce152b8d2764a4d160fcbdf4722fb257`
- **WIP:** preservar o estado de trabalho preexistente da S6 e todos os recibos/evidências históricos; este checkpoint é documental.

> Este documento é um handoff independente para continuidade. Ele não fecha S6, não concede aceite e não autoriza execução técnica. Use os relatórios e recibos listados como evidência primária quando um detalhe exigir reconferência.

## Resumo executivo

S6 permanece **OPEN**. O Gate A está **PARTIAL**: os testes funcionais JUnit passaram, mas o recibo não observou o `Process.ExitCode` do processo externo. O código 0 gravado nos metadados do worker não pode substituir essa evidência externa. A causa técnica do nulo não foi confirmada; materializar `$externalProcess.Handle` antes da espera é uma hipótese/workaround documentado, não aplicado e não comprovado.

O Gate B está **BLOCKED_BY_REMOTE_EVIDENCE**: a evidência V2 demonstra correspondência local com a referência, mas não satisfaz o contrato ativo V1 de verificar remotamente o prefixo antes de append. A cobertura remota existente termina 36.954 bytes antes de EOF. Não há alvo alternativo selecionado nem evidência completa de checkpoint físico e orçamento S5.

A próxima ação técnica possível é somente a probe sintética de captura de exit code em Windows PowerShell 5.1, após autorização separada. Ela **não foi autorizada nem executada**. Não repetir os 196 testes sem um novo gate. Não executar Harness, probe, regressão, download, chamada Telegram/RPC ou ação Git neste checkpoint.

## Baselines e estado da S6

**FATO**

- O estado registrado é `V1_ACTIVE=YES`, `V2_GLOBAL=OFF`, `S6_STATUS=OPEN`, `S7/S8=DEFERRED`; aceite formal S6 segue pendente.
- A branch e HEAD acima são os valores registrados nos relatórios/recibos desta atividade. Não foi feita consulta Git neste checkpoint.
- Há WIP extenso da S6 e evidência histórica que deve ser preservada. Nenhum código, teste, recibo histórico, referência, SQLite ou artefato de download deve ser sobrescrito para produzir este handoff.
- A correção do Gate A documentada em `docs/reports/S6_FINAL_GATE_REMEDIATION_2026-10-24/GATE_A_PATCH.md` corrige o procedimento documentado; ela não significa que a causa desta execução foi identificada nem que o Gate A passou.

## Gate A — execução funcional e captura do processo externo

### Resultado observado

**FATO**

- O recibo principal é `.s6r/d33e020d9dd0/gate-a-evidence-receipt.json` (7.865 bytes; SHA-256 `85f261f4877c6ed0ddb739d5bab59b50a3022c28a93f71f038723db8634f04f9`). O arquivo de reconciliação é `.s6r/d33e020d9dd0/gate-a-reconciliation-addendum.json` (3.618 bytes; SHA-256 `538be97f238f964ac427639836bde66973de8501414b96175ec1672bfe6fc528`). Os arquivos originais permanecem no run root e não devem ser editados.
- O JUnit em `.s6r/d33e020d9dd0/junit.xml` registrou **196 casos, 196 executados, 0 falhas, 0 erros e 0 skips**; os IDs coletados e executados coincidem com o baseline.
- Os 196 testes já passaram em mais de uma execução registrada. A execução única mais recente, deste run root, durou **82,674 s** (limite configurado: 145.000 ms). Não repetir a suíte/Harness sem um novo gate e autorização aplicável.
- O processo externo era PID `33916`; o worker metadata registra PID `10696` e `exit_code=0`. O recibo externo registra `process_exit_code=null`, `process_exit_code_observed=false`, `has_exited=true`, `termination_confirmed=true`, `timed_out=false` e `failure_class=null`. O agregado contém uma entrada `errors` causada pela guarda fail-closed posterior ao recibo de processo. A relação entre os PIDs e a relação pai-filho permanecem `UNVERIFIED`.
- Portanto, JUnit PASS e worker exit 0 demonstram o resultado funcional, mas não demonstram o exit code externo exigido pelo Gate A. O Gate A segue `PARTIAL`.
- A reconciliação posterior corrigiu a apresentação do inventário: `remaining_python_pids` é um array vazio; uma agregação anterior havia representado esse array como nulo. Não há processo Python remanescente atribuído à execução na reconciliação final.

### Causa, hipótese e proposta

**FATO**

- O JSON contém o campo de exit code como `null` antes/depois da serialização e marca `observed=false`. `WaitForExit` e `HasExited` foram confirmados. O `failure_class` do recibo de processo é nulo; a única entrada de erro agregada é o bloqueio fail-closed posterior, não uma exceção registrada pelo getter.
- O wrapper usou `Start-Process -PassThru -NoNewWindow -RedirectStandardOutput -RedirectStandardError`, aguardou a saída, atualizou o objeto e leu `Process.ExitCode`. O estado real do tipo/handle e a resolução do comando não foram registrados durante o run.
- A revisão estática de Windows PowerShell 5.1.26100.9711 reportou zero erros de parser para o runner, a linha proposta e a probe preparada.

**HIPÓTESE**

- O sintoma e a combinação `-NoNewWindow` com streams redirecionados são compatíveis com comportamento de caching de handle de `Start-Process` (PowerShell issue #5421). Isso não confirma causa raiz nesta execução, nem prova retroativamente o estado do objeto usado.
- A menor correção experimental proposta é materializar o handle logo depois de iniciar o processo: `$externalProcessHandle = $externalProcess.Handle`. Ela não foi aplicada ao runner nem aos recibos históricos.

**DECISÃO / AUTORIZAÇÃO PENDENTE**

- Não alterar recibos históricos e não executar o Harness novamente agora.
- Solicitar autorização específica antes de executar **uma única probe sintética**, em Windows PowerShell 5.1, com processo filho que permaneça vivo por cerca de 2 segundos, handle `IntPtr` válido e não zero, exit esperado `37`, limite de espera e logs em diretório único preservado. A probe deve registrar a resolução de `Start-Process`, o tipo concreto do processo e o valor/erro do getter.
- A probe foi **preparada, NÃO autorizada e NÃO executada**. Seu bloco de referência completo está na seção “Probe sintético preparado — não executado” de `docs/reports/S6_GATE_A_EXITCODE_ROOT_CAUSE_AND_B_TARGET_TRIAGE_2026-10-24/REPORT.md`.
- Se a probe autorizada não observar `37`, parar e preservar seu diretório. Não repetir a probe automaticamente e não avançar para Harness. Uma nova execução nativa do Harness exige outro gate/autorização explícita, posterior à demonstração da captura externa.

## Gate B — V1 e evidência remota

**FATO**

- O resultado V2 `TRUSTED_REFERENCE_MATCH` demonstra igualdade byte a byte e SHA-256 local da saída com a referência: tamanho `E=1.119.129.690` bytes, SHA-256 `3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c`. Isso é evidência válida para aquele perfil V2; **não equivale ao gate V1** e não comprova a leitura/hash remoto do prefixo antes da continuação.
- Sob o contrato V1 ativo, o caminho `REMOTE_HASH_REQUIRED` valida `_verify_prefix` antes de abrir o writer e valida faixas remotas da continuação antes da finalização. A revisão estática não encontrou motivo para alterar `downloads.py`, `TelegramGateway`, o contrato V1 ou o modelo de integridade.
- A evidência remota existente cobre `[0, 1.119.092.736)` de `E=1.119.129.690`. O sufixo `[1.119.092.736, 1.119.129.690)` de **36.954 bytes** permanece `REMOTE_HASH_UNVERIFIABLE_EOF`. Uma faixa para além do EOF não comprova esse sufixo. A consulta de hashes registrada começou depois do início da continuação; logo, não comprova remote-prefix-before-append.
- Nenhum alvo alternativo foi selecionado. O alvo controlado já avaliado não tem cobertura remota completa; também faltam reconciliação demonstrada do checkpoint físico `P` para casos alinhado e não alinhado e confirmação de suficiência do orçamento S5 sem orçamento extra.
- A ideia de criar ou usar um arquivo pequeno e alinhado (por exemplo, 16 MiB) continua sendo uma hipótese não comprovada. Não é um alvo selecionado nem evidência de cobertura remota [0,E), checkpoint físico reconciliado ou orçamento S5 suficiente.

**DECISÃO / BLOQUEIO**

- Gate B permanece `BLOCKED_BY_REMOTE_EVIDENCE`; nenhum download, RPC/Telegram ou nova prova foi autorizado por este checkpoint.
- Para reabrir a seleção, identificar um alvo controlado e estável e obter evidência `GetFileHashes` válida cobrindo integralmente `[0,E)`, sem lacunas e sem faixa além do EOF. Depois, reconciliar `P` físico com o checkpoint SQLite `D` (não usar `D` isoladamente como offset autoritativo), demonstrar casos alinhado e não alinhado em processos reiniciados com overlap validado e comprovar o orçamento S5 existente.
- Parâmetros S5 que não podem ser ampliados sem aprovação: até **3 tentativas por mídia incluindo a inicial**; **1 ou 2 workers**; FloodWait cumulativo de até **120 s por mídia**; reserva `GetFile` de até **256 KiB por chamada**; orçamento agregado já aprovado, sem orçamento extra.
- Qualquer prova V1 real e qualquer chamada Telegram/download requerem autorização separada. A decisão offline `ALTERNATE_CONTROLLED_TARGET_REQUIRED` não seleciona nem autoriza um alvo.

## Restrições para continuidade

- Preservar `work/s0-bootstrap`, HEAD registrado e todo WIP/evidência; não inferir limpeza ou ausência de mudanças além do que os documentos registram.
- `V1_ACTIVE=YES`; manter `V2_GLOBAL=OFF`; `S6=OPEN`; `S7/S8=DEFERRED`.
- Nenhum pytest, regressão dos 196 casos, Harness, probe, download, Telegram/RPC, chamada de rede para prova ou comando Git (incluindo status, add, commit, push ou fetch) foi executado neste checkpoint. Não executar essas ações como parte da leitura deste documento.
- **CODEX_LOCAL primeiro; DC somente como fallback** para a ferramenta/canal de execução local autorizado. Não tratar fallback como autorização adicional.
- Para trabalho futuro multiagente, usar `$codex-task-router` explicitamente e executar o gate previsto pela skill; delegar somente se trouxer benefício material e todos os critérios de autorização, escopo, ownership e capacidade forem satisfeitos. Não criar delegações artificiais. O registro anterior marca `principal_architect=CLOSED/NO_REENTRY`; não reabrir nem chamar esse perfil sem uma nova solicitação explícita que altere esse limite.
- O envio de continuidade por `send_message_to_thread` ao chat **“Projeto Telegram 2.0”** só pode ocorrer com aprovação direta/específica. Houve bloqueio anterior por auto-review antes do envio; não contornar o bloqueio nem repetir tentativa sem a aprovação requerida. Este checkpoint local não envia mensagem.

## Plano de rollback documental

Não existe rollback de código: nenhum código ou teste foi alterado. Se este checkpoint contiver erro, corrigir somente este novo arquivo, preservando relatórios, recibos, WIP e demais históricos. Não remover ou reescrever evidência de execução para “alinhar” o documento.

## Checklist de aceitação do handoff

- [ ] O checkpoint está sob `docs/continuity/handoff/` e é o único arquivo novo desta atividade.
- [ ] Baseline de branch/HEAD, estado WIP e estados V1/V2/S6/S7/S8 estão registrados.
- [ ] O resultado V2 está explicitamente separado do gate V1.
- [ ] Gate A inclui JUnit 196/196, múltiplas execuções, duração da execução mais recente, exit externo nulo, exit do worker 0 e relação de PID não verificada.
- [ ] A hipótese do handle está rotulada como não confirmada; a probe esperada 37 está marcada não autorizada/não executada.
- [ ] Gate B registra a cobertura e o sufixo EOF exatos, ausência de alvo alternativo e requisitos `P`, `D` e S5.
- [ ] Próximas autorizações e ações estão separadas; nenhum comando proibido foi executado.
- [ ] PROJECT_STATE, CONTINUITY_RECORD e LAST_HANDOFF permanecem intactos porque já cobrem o estado corrente.
- [ ] Apenas validação estática do documento foi realizada.

## Fontes canônicas

1. `docs/reports/S6_FINAL_GATE_REMEDIATION_2026-10-24/REPORT.md`
2. `docs/reports/S6_FINAL_GATE_REMEDIATION_2026-10-24/GATE_A_PATCH.md`
3. `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/REPORT.md`
4. `.s6r/d33e020d9dd0/gate-a-evidence-receipt.json`
5. `.s6r/d33e020d9dd0/gate-a-reconciliation-addendum.json`
6. `.s6r/d33e020d9dd0/external-process.json`
7. `.s6r/d33e020d9dd0/process-identity-reconciliation.json`
8. `.s6r/d33e020d9dd0/junit.xml` e `.s6r/d33e020d9dd0/worker-result.json`
9. `docs/reports/S6_GATE_A_EXITCODE_ROOT_CAUSE_AND_B_TARGET_TRIAGE_2026-10-24/REPORT.md` e diagnóstico fornecido pelo usuário nesta conversa.
10. `docs/continuity/PROJECT_STATE.md`, `docs/continuity/CONTINUITY_RECORD.md` e `docs/continuity/handoff/LAST_HANDOFF.md` para o estado cumulativo anterior.

**Limite de validação desta atividade:** conferir somente conteúdo e estrutura do documento criado. Não executar probe, regressão, download, Telegram/RPC ou Git.


