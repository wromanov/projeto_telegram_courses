# HISTORICAL_SNAPSHOT — superseded PROJECT_STATE

This file preserves the prior state snapshot for traceability. It is not an
active authority; use [docs/continuity/PROJECT_STATE.md](../continuity/PROJECT_STATE.md).

# Estado do projeto — projeto_telegram_courses

~~~text
DOCUMENT_ROLE = PROJECT_STATE
STATE_VERSION = 1.9
STATUS = STOPPED / CONTINUITY_CHECKPOINT_PENDING
LAST_UPDATED = 2026-10-06 / America/Sao_Paulo
PROJECT_ID = projeto_telegram_courses
PROJECT_CONTINUITY_ROOT = docs/
CONTINUITY_ENTRYPOINT = docs/START_HERE.md
CURRENT_ENVIRONMENT = HOME
PROJECT_ROOT = C:\Users\walac\desenvolvimento\projeto_telegram_courses
REMOTE_ORIGIN = https://github.com/wromanov/projeto_telegram_courses.git
REMOTE_ORIGIN_STATE = CONFIGURED / REMOTE_NOT_UPDATED_BY_THIS_CHECKPOINT
LOCAL_GIT_REPOSITORY = INITIALIZED
CURRENT_BRANCH = work/s0-bootstrap
EXACT_CURRENT_HEAD = 0ba4fe58ee9be8c26045105a13c23afb9472ef5c
PRE_COMMIT_DOCUMENTATION_BASELINE = a00f325df45f3adad13b3a99d00c3230f913b282
UPSTREAM = NONE / CONTINUITY_BRANCH_NOT_YET_PUBLISHED
REMOTE_HEAD_AFTER_FETCH = a00f325df45f3adad13b3a99d00c3230f913b282
INDEX_STAGING = EMPTY
GIT_WORKTREE_STATE = FOUR TRACKED DOCUMENT DELTAS; THREE UNTRACKED S0 FILES; ALL UNSTAGED BEFORE CONTINUITY STAGE
CURRENT_PHASE = S0 / STOPPED_FOR_MACHINE_TRANSFER
DELIVERY_UNIT = SPRINT
CURRENT_DELIVERY_UNIT = S0 / IN_PROGRESS
CURRENT_ACTIVITY = S0_CONTINUITY_CHECKPOINT_AND_PUSH
CURRENT_ACTIVITY_STATE = AUTHORIZED / PREPARING_CONTINUITY_BRANCH / STOP_AFTER_VERIFIED_PUSH
LAST_COMPLETED_ACTIVITY = S0-SL02_VERIFIED_CHECKPOINT
LAST_VALIDATED_INTEGRATED_BASELINE = S0-SL01-AND-SL02-CHECKPOINTS / CLI_ACCEPTANCE_PENDING
NEXT_DELIVERY_UNIT = S0
S0_SELECTED = YES
S0_READY = YES
S0_STARTED = YES
S0_AUTHORIZED = YES / CURRENT_USER_CARD_B / S0_ONLY
ARCHITECTURE_APPROVAL = APPROVED
FOUNDATION_APPROVAL = APPROVED
PROJECT_GOVERNANCE_BINDING = ACTIVE / VALIDATED
PROJECT_OPENING_GATE = PASS
CONTINUITY_RECOVERY_GATE = PASS
OPENING_CONTINUITY_HANDOFF = PASS
AGENT_HANDOFF_GATE = PRIOR_PASS / NOT_REASSESSED_THIS_ACTIVITY
IMPLEMENTATION_AUTHORIZATION = GRANTED_FOR_S0_ONLY / RESUME_AUTHORIZED_SINGLE_ACTIVITY
GIT_PUBLICATION_AUTHORIZATION = ONE_TIME_CONTINUITY_PUSH_AUTHORIZED / CURRENT_BRANCH_ONLY
CONTRACT_FIRST_IMPLEMENTATION = REQUIRED
S0_CONTRACT_ID = S0_IMPLEMENTATION_CONTRACT
S0_CONTRACT_VERSION = 1.0
S0_CONTRACT_STATUS = APPROVED
S0_CONTRACT_APPROVAL = APPROVED_BY_USER
S0_CONTRACT_GAPS = NENHUM
S0_CONTRACT_CLOSURE_VERIFICATION = PASS
S0_CONTRACT_SEMANTIC_STATE = FROZEN
CURRENT_SLICE = CONTINUITY_PUSH / STOP_AFTER_VERIFIED_PUSH
SPRINT_COMPLETION_PERCENT = 40%
SP01_RUNTIME_VALIDATION = FAIL / PREVIOUS_ATTEMPT_STOPPED_AT_SP01-PREFLIGHT-ROOT
CYCLE_GATE = BOUNDED_CYCLIC_SUSPENDED_BY_USER / SINGLE_ACTIVITY_AUTHORIZED
ORCHESTRATION_MODE = SINGLE_ACTIVITY
BOUNDED_CYCLIC_EXECUTION = SUSPENDED
ACTIVITY_COMPLETION_PERCENT = 50%
CONTINUITY_PUSH_AUTHORIZED = YES / WORK-S0-BOOTSTRAP / NO FORCE / NO TAGS
SAFE_RESUME_POINT = Remote continuity branch will preserve S0 at 40%, with SL01/SL02 checkpoints and SL03 validation pending. On the other machine, revalidate Git/contract, execute SP01-01 only; if PASS, prepare .venv per §22.5.1, run T10A-E, checkpoint SL03 at 60%, then continue remaining SP-01/SL04. Stop this session after verified push; do not run implementation or tests here.
~~~

## Identidade e fatos locais

O checkout ativo é `C:\Users\walac\desenvolvimento\projeto_telegram_courses`, em `master`, com `origin/master` como upstream. O `HEAD` permaneceu em `a00f325df45f3adad13b3a99d00c3230f913b282`, igual ao remoto após `git fetch origin`; não foi necessário `pull`. A evidência de recuperação registra que o worktree estava limpo antes daquela atividade documental. No início desta revisão, estavam presentes as mudanças de abertura/recuperação, binding/evidências e o relatório não rastreado `docs/audit/AUDITORIA_TECNICA_2026-10-05.md`, conforme inventário/evidências. Esta revisão modificou documentação de continuidade, estado e plano, e criou seu registro em `docs/governance/S0_READINESS_REVIEW_2026-10-05.md`. `AGENTS.md` também consta não rastreado no estado final, foi lido por ser específico do projeto e foi preservado sem alteração. Nada foi staged.

## Authorities e baseline adotado

- Requisitos, arquitetura e fundação: [REQUIREMENTS](../product/REQUIREMENTS.md), [ARCHITECTURE](../architecture/ARCHITECTURE.md) e [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md).
- Plano: [ROADMAP](../planning/ROADMAP.md) e [SPRINTS](../planning/SPRINTS.md).
- Mapa ativo: [AUTHORITY_MAP](AUTHORITY_MAP.md); fonte de aprovações: [APPROVALS_AND_DECISIONS](APPROVALS_AND_DECISIONS.md).
- Binding canônico validado: [PROJECT_GOVERNANCE_BINDING.json](PROJECT_GOVERNANCE_BINDING.json). Baseline adotado: GOVERNANCE_BASELINE V1, contract 1; PM-00 1.0, PM-01 1.0, PM-02 1.7-R2.6, PM-03 1.7-R2.3, PM-04 1.2, PM-05 v1 e VP-01 v2.0. Os sete pins foram resolvidos por identidade, versão e SHA-256.
- Registro dos probes, checks e reconciliação: [OPENING_RECOVERY_VALIDATION](evidence/OPENING_RECOVERY_VALIDATION.json).

GLOBAL_BASELINE_RELATION = CURRENT. As referências de dependência do Continuity Manifest são PM-02 1.7-R2.6 e PM-03 1.7-R2.3; `STALE_ACTIVE_DEPENDENCY_REFERENCES = 0`.

## Ponto seguro, readiness e autorização

HISTORICAL_SAFE_RESUME_POINT = Contrato docs/contracts/S0_IMPLEMENTATION_CONTRACT.md v1.0 aprovado pelo usuário e semanticamente congelado após verificação final focada PASS; antes do Card B de execução S0.

HISTORICAL_NEXT_REQUIRED_ACTIVITY = DECISÃO EXPLÍCITA DO USUÁRIO SOBRE AUTORIZAÇÃO PARA IMPLEMENTAR S0
HISTORICAL_NEXT_ACTIVITY_READINESS = READY_FOR_USER_AUTHORIZATION_DECISION
HISTORICAL_NEXT_ACTIVITY_AUTHORIZATION = NOT_GRANTED_FOR_IMPLEMENTATION
USER_CONTINUITY_VALIDATION = A atividade de recuperação foi explicitamente solicitada e concluída; nenhum avanço para S0 foi feito.

## Invariantes e limites

Invariantes de produto permanecem em REQUIREMENTS, ARCHITECTURE e ENGINEERING_FOUNDATION: adapters/gateway, parsers plugáveis, três fontes de verdade, commit físico antes de DOWNLOADED, resume condicional, workers limitados e acesso legítimo. `FRONTEND_FIRST_RULE = NOT_APPLICABLE` para a CLI sem frontend gráfico/web.

Na fotografia registrada antes do Card B de execução S0, GOV-B01 foi resolvido: os pacotes e schema canônicos conferem com seus manifests; binding, pins e checks aplicáveis passaram. Nenhuma decisão de arquitetura/fundação foi reaberta. Nenhuma capability de produto havia sido implementada. Naquele momento, `S0_STARTED = NO`, `S0_AUTHORIZED = NO`, `IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED` e `GIT_PUBLICATION_AUTHORIZATION = NOT_GRANTED`.

Na revisão de readiness [S0_READINESS_REVIEW_2026-10-05](S0_READINESS_REVIEW_2026-10-05.md), S0 e DoR estavam `READY_FOR_AUTHORIZATION`; naquele momento `S0_STARTED = NO`, `S0_AUTHORIZED = NO` e `IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED`. A decisão posterior do usuário autorizou S0, conforme a atualização corrente ao final deste documento.

Riscos futuros permanecem nos documentos de produto/fundação e no contexto não normativo [AUDITORIA_TECNICA_2026-10-05](../audit/AUDITORIA_TECNICA_2026-10-05.md): identidade/revisão de mídia antes de schema/deduplicação em S2 e componentes S4/S6/S7; reconciliação filesystem/SQLite e ownership antes de finalização S4; semântica de checkpoint antes de persistência definitiva em S2 e sync S7; proteção concreta da sessão antes de acesso real em S1. As condições e spikes estão mapeados em [SPRINTS](../planning/SPRINTS.md#future-sprint-entry-conditions); não são blockers globais de S0. GUI, TDLib e suporte adicional continuam adiados; pacote Windows permanece na unidade S10.

## Contrato S0 — checkpoint histórico após segundo ciclo de correção contratual

O Card B `148726eb-ea91-4690-8e1b-e838c31afb41/Texto colado.txt` autorizou exclusivamente corrigir CONTRACT-MED-06–08 e refletir o estado factual estritamente necessário. A segunda auditoria foi fornecida pelo usuário como findings no payload; não se alterou nem produziu relatório independente. O autor fechou os três findings e HID-01–03 em [S0_IMPLEMENTATION_CONTRACT §27](../contracts/S0_IMPLEMENTATION_CONTRACT.md#27-audit_finding_closure--segundo-ciclo-contract-med-0608): streams separados por Process/.NET com código independente; metadata editable local ignorado e distinto de source; indicador config representando arquivo lido e validado, com matriz de seis casos. Seis correções anteriores preservadas; oito eixos afetados e rastreabilidade revalidados documentalmente, cinco blocos PowerShell com parse estático PASS e 14 patterns/probes contratados. Não houve validação runtime nem nova auditoria independente nesta autoria.

Este parágrafo registra o estado daquele checkpoint, quando a terceira auditoria era o próximo passo. Foi superseded pela verificação final focada e aprovação do usuário registradas na seção corrente abaixo.

Git factual daquele checkpoint: master, HEAD `71fe536eed4edc81b1e5cd280f71e97d7c7a1160`; índice vazio e três arquivos documentais modificados. Esses fatos são históricos. Nenhum pip, instalação, código de produto, smoke real ou SP-01 ocorreu naquele checkpoint.

## Contrato S0 — registro anterior do primeiro ciclo de correção contratual

O Card B `16f378d7-565b-4fe9-bbc9-c3c6d6aa9762/Texto colado.txt` autorizou exclusivamente a correção documental de CONTRACT-HIGH-01 e CONTRACT-MED-01–05. Os seis findings foram fechados pelo autor como especificação em [S0_IMPLEMENTATION_CONTRACT §26](../contracts/S0_IMPLEMENTATION_CONTRACT.md#26-audit_finding_closure--correção-do-draft-10): fail-fast SP-01, oracle completo do ambiente, escopo/geração/replay das constraints, executáveis absolutos da CLI, política zero mutação do smoke e exclusões Git integrais. `S0_CONTRACT_VERSION=1.0`, `S0_CONTRACT_STATUS=DRAFT_READY_FOR_REVIEW`, `S0_CONTRACT_APPROVAL=NOT_GRANTED`. Próxima atividade: repetir auditoria independente, antes de solicitar aprovação. Não foi executada nova auditoria independente por esta autoria.

`PROJECT_STATE_RECONCILIATION=PASS`: cabeçalho, contrato e ponto seguro usam o mesmo ID/versão/status, seis findings fechados, zero gaps materiais e próximo passo. Estado draft já coincidia e foi preservado; somente atividade/última atividade e próximo passo foram atualizados. O texto procedural antigo de draft bloqueado no bootstrap foi identificado; o status corrente é resolvido por este STATE/contrato, e o bootstrap foi preservado no escopo desta correção. O mapa continua descobrindo corretamente o draft 1.0 sem authority operacional, sem alteração nesta atividade.

Git de entrada desta correção: `master`, HEAD `71fe536eed4edc81b1e5cd280f71e97d7c7a1160`, upstream `origin/master`, índice vazio, contrato/STATE/mapa já modificados pela atividade anterior. Alterações preexistentes preservadas. Escrita atual: contrato e este STATE; sem criação de arquivo, staging, commit ou push. Binding/schema e hashes adotados foram conferidos read-only. `SP01_RUNTIME_VALIDATION=NOT_EXECUTED`, `S0_STARTED=NO`, `S0_AUTHORIZED=NO`, `IMPLEMENTATION_AUTHORIZATION=NOT_GRANTED`.

## Contrato S0 — registro anterior de fechamento de CG-01–05

O Card B de fechamento do usuário (`6ba65121-7fd4-4247-9f22-9e79880053f6/Texto colado.txt`) autorizou exclusivamente editar o contrato para fechar os cinco gaps, sem implementação, instalação, bootstrap, staging, commit ou push. O contrato [S0_IMPLEMENTATION_CONTRACT](../contracts/S0_IMPLEMENTATION_CONTRACT.md) versão 1.0 agora especifica as faixas de dependências, namespace/manifest, configuração, smoke da CLI e metadata/instalação/ferramentas; `CG-01_STATUS` a `CG-05_STATUS = CLOSED`, `SEMANTIC_GAPS = NENHUM` e `CONTRACT_STATUS = DRAFT_READY_FOR_REVIEW`. As decisões e evidências de compatibilidade documental estão nos §§6/22–23. Compatibilidade efetiva Windows/CPython 3.14 continua `SP01_RUNTIME_VALIDATION = NOT_EXECUTED`.

`PROJECT_STATE_RECONCILIATION = PASS` para esta mudança de status: contrato e estado usam o mesmo ID/versão/status/gaps; autoridade de aprovação permanece com o usuário. Git no início desta atividade: `master`, HEAD `71fe536eed4edc81b1e5cd280f71e97d7c7a1160`, upstream `origin/master`, worktree/índice limpos e branch um commit à frente. Esta atividade produziu apenas edições documentais do contrato, deste estado e do mapa; nenhuma capability foi implementada. A seção abaixo e o checkpoint Git seguinte são registros históricos de atividades anteriores, não o status corrente.

## Contrato S0 — registro histórico da autoria inicial

O Card B da autoria inicial (anexo `d94b27af-126b-4487-b20b-339d8bf373b5/Texto colado.txt`) autorizou criar [S0_IMPLEMENTATION_CONTRACT](../contracts/S0_IMPLEMENTATION_CONTRACT.md) e registrar sua existência/status nos documentos estritamente necessários do projeto. Proibiu implementação, bootstrap, instalação, Telegram real, governança externa e staging/commit/push. Execução DIRECT, sem subagentes. O pedido estabeleceu contrato primeiro, autoria Sol e implementação futura Luna, sem reinterpretar ou preencher gaps durante implementação. O runtime daquela sessão era Codex baseado em GPT-6; não se afirmou execução no GPT-5.6 Sol/Médio solicitado pelo payload.

Naquela atividade o contrato 1.0 nasceu DRAFT e terminou `DRAFT_BLOCKED`, sem aprovação e sem authority operacional ativa. Cinco gaps impediam entregá-lo executável sem decisões pelo implementador: faixas de aiosqlite/Rich/pytest/Ruff (CG-01); layout/manifest físico e namespace (CG-02); configuração básica exata (CG-03); entrada e smoke CLI (CG-04); backend/metadados/instalação reproduzível e perfil pytest/Ruff (CG-05). A atividade inicial registrou evidência e dados necessários para fechamento, sem inventar versões ou novas decisões aprovadas.

A decisão anterior `S0_READINESS = READY_FOR_AUTHORIZATION`, com zero blockers naquela revisão, é preservada em [S0_READINESS_REVIEW_2026-10-05](S0_READINESS_REVIEW_2026-10-05.md). Ela não avaliava o novo contrato sem escolhas por Luna. Os gaps identificados naquele momento bloqueavam o contrato e a implementação sob a regra nova; não reabriram a arquitetura nem promoveram findings de S2+ a blockers de bootstrap. O fechamento atual está registrado na seção precedente.

Fatos desta atividade: root/branch/HEAD/upstream e índice foram verificados novamente; permanecem no baseline acima, com índice vazio. Sete pins de governança e Continuity 3.0 conferem por SHA-256; Registry global corresponde às versões adotadas. Schema/hash e estrutura focal do binding foram conferidos; o PASS histórico Draft 2020-12 é preservado, sem alegar nova execução genérica porque o validador não está disponível. A validação documental usou runtime já empacotado do aplicativo, sem criar ambiente de produto. Nenhum SP-01, pytest/Ruff de produto, bootstrap, instalação ou acesso Telegram foi executado.

Reconciliação temporal: Opening/evidência preservam a fotografia anterior `S0_READY = NO`; a prontidão posterior está em STATE/revisão específica. O último parágrafo do bootstrap contém texto procedural desatualizado de prontidão: não substitui essas authorities e foi explicitado no contrato §1. Não se declara novo handoff global PASS nesta atividade. Registros de gates anteriores são evidência histórica, sem ampliar autorização.

Na autoria documental inicial, `ACTIVITY_COMPLETION_PERCENT = 80%` descrevia quatro de cinco etapas documentais concluídas e CG-01–05 ainda abertos. Esses status e `S0_STARTED = NO`, `S0_AUTHORIZED = NO`, `IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED` eram históricos e foram superseded pela autorização corrente registrada ao final deste documento.

## Autorização posterior — checkpoint documental Git

Após receber o draft bloqueado, o usuário autorizou explicitamente stage e commit, deixando a mensagem a critério do executor. Em resposta à delimitação de conteúdo, escolheu: “Todo o pacote documental pendente do projeto, incluindo abertura, prontidão e contrato”. Essa instrução posterior autoriza incluir as mudanças documentais anteriores no mesmo checkpoint; não exige descartar ou isolar artificialmente os deltas em STATE/mapa.

Escopo: arquivos documentais pendentes em `docs/` e `AGENTS.md`, com staging por paths explícitos e verificação do índice antes do commit. A reconciliação deste registro e da navegação procedural do bootstrap acompanha o checkpoint. Nenhum produto, instalação, sessão, segredo ou arquivo da governança externa integra esse escopo. `PUSH_AUTHORIZATION = NOT_GRANTED`. A autorização se limita ao checkpoint documental solicitado; não é permissão permanente para novos commits.

Baseline antes do commit: `master`, HEAD `a00f325df45f3adad13b3a99d00c3230f913b282`, upstream `origin/master`, índice vazio e 16 arquivos documentais pendentes identificados. O hash do commit resultante, índice e worktree devem ser descobertos em Git; não se cria commit autorreferente para registrar seu próprio hash. O snapshot mantém como histórico os fatos de recuperação/abertura e da autoria antes desta autorização, inclusive as declarações de que nada foi staged ou publicado naquelas atividades. Contrato permanecia `DRAFT_BLOCKED` naquele checkpoint histórico; a aprovação e o estado corrente estão registrados acima.

## Contrato S0 — aprovação e reconciliação corrente

O Card B atual informa que a verificação final focada foi concluída fora deste checkout com PASS e readiness `READY_FOR_USER_APPROVAL`, e contém a decisão explícita do usuário de aprovar `S0_IMPLEMENTATION_CONTRACT v1.0`. A aprovação foi registrada em [APPROVALS_AND_DECISIONS](APPROVALS_AND_DECISIONS.md) e no §28 do [contrato](../contracts/S0_IMPLEMENTATION_CONTRACT.md). Findings MED-06–08 foram confirmados fechados, os findings anteriores preservados, sem regressão, decisões escondidas, liberdade semântica ou gaps materiais. Não foi realizada nova auditoria nesta reconciliação.

`S0_CONTRACT=APPROVED`; `S0_CONTRACT_VERSION=1.0`; `S0_CONTRACT_CLOSURE_VERIFICATION=PASS`; `S0_CONTRACT_SEMANTIC_STATE=FROZEN`. A verificação e aprovação não concedem autorização de implementação: `S0_AUTHORIZED=NO`, `IMPLEMENTATION_AUTHORIZATION=NOT_GRANTED`, `S0_STARTED=NO` e `SP01_RUNTIME_VALIDATION=NOT_EXECUTED`. O próximo passo é somente a decisão explícita do usuário sobre autorizar a implementação de S0.

## Atualização corrente — autorização e parada da execução S0

Em 2026-10-06, o usuário forneceu o Card B `1ba72eb6-adae-47b6-840d-da651c2a69b6`, autorizando expressamente execução integral S0, modo BOUNDED_CYCLIC, commits locais por slice e avanço após checkpoints PASS; push e S1 permanecem não autorizados. Essa decisão posterior altera a autorização corrente, sem modificar o contrato aprovado/congelado nem os registros históricos de antes da autorização.

S0 tem checkpoints verificados para S0-SL01 (`3b56b38ea9ef4b42006f522a17e6379909ee42e8`) e S0-SL02 (`1cde21d4d0f95b9b190c02f4a69a91c25485428c`). SL03 tem commits locais (`05b26582197b0c1c2c9a014b3acc1807c8db803b` e correção bounded `0ba4fe58ee9be8c26045105a13c23afb9472ef5c`), mas T10A-E não foram executados no ambiente real; portanto SL03 não é checkpoint verificado. A completude verificada da S0 permanece 2/5 = 40%; SL04 e o closure gate não passaram. Em autorização posterior, o usuário retomou S0 em `SINGLE_ACTIVITY` e suspendeu `BOUNDED_CYCLIC`; progresso e checkpoints preservados.

SP-01 parou em `SP01-PREFLIGHT-ROOT`: erro terminante do PowerShell ao executar o preflight por `Invoke-S0Native`, sem código nativo disponível. Nenhum passo dependente foi executado; `.venv/` e `.venv-replay/` não foram criados. Evidência sanitizada: [SP01_STACK_WINDOWS](../engineering/evidence/SP01_STACK_WINDOWS.md). Card B posterior autorizou a ordem de retomada em outra máquina: SP01-01; se PASS, preparar `.venv`; T10A-E; checkpoint SL03; continuar SP-01/SL04. O progresso permanece 40% até SL03 receber checkpoint. A atividade corrente é exclusivamente publicar continuidade em `work/s0-bootstrap`, depois parar. Push autorizado para esse propósito, sem force/tags e sem declarar encerramento da S0.
