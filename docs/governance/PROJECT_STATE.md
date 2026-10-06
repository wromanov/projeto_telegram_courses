# Estado do projeto — projeto_telegram_courses

~~~text
DOCUMENT_ROLE = PROJECT_STATE
STATE_VERSION = 1.4
STATUS = OPENING_COMPLETE / PRE_S0
LAST_UPDATED = 2026-10-05 / America/Sao_Paulo
PROJECT_ID = projeto_telegram_courses
PROJECT_CONTINUITY_ROOT = docs/
CONTINUITY_ENTRYPOINT = docs/START_HERE.md
CURRENT_ENVIRONMENT = HOME
PROJECT_ROOT = C:\Users\walac\desenvolvimento\projeto_telegram_courses
REMOTE_ORIGIN = https://github.com/wromanov/projeto_telegram_courses.git
REMOTE_ORIGIN_STATE = CONFIGURED / REMOTE_NOT_UPDATED_BY_THIS_CHECKPOINT
LOCAL_GIT_REPOSITORY = INITIALIZED
CURRENT_BRANCH = master
EXACT_CURRENT_HEAD = DISCOVER_AT_RUNTIME_WHEN_GIT_AVAILABLE
PRE_COMMIT_DOCUMENTATION_BASELINE = a00f325df45f3adad13b3a99d00c3230f913b282
UPSTREAM = origin/master
REMOTE_HEAD_AFTER_FETCH = a00f325df45f3adad13b3a99d00c3230f913b282
INDEX_STAGING = DISCOVER_AT_RUNTIME_WHEN_GIT_AVAILABLE
GIT_WORKTREE_STATE = DISCOVER_AT_RUNTIME_WHEN_GIT_AVAILABLE
CURRENT_PHASE = OPENING_COMPLETE / PRE_S0
DELIVERY_UNIT = SPRINT
CURRENT_DELIVERY_UNIT = NONE_STARTED
CURRENT_ACTIVITY = S0_IMPLEMENTATION_CONTRACT_AUTHORING
CURRENT_ACTIVITY_STATE = BLOCKED_CONTRACT_GAPS
LAST_COMPLETED_ACTIVITY = HOME_CONTINUITY_RECOVERY_AND_PROJECT_OPENING_GATE_REASSESSMENT
LAST_VALIDATED_INTEGRATED_BASELINE = NONE_PRODUCT_NOT_IMPLEMENTED
NEXT_DELIVERY_UNIT = S0
S0_SELECTED = YES
S0_READY = YES
S0_STARTED = NO
S0_AUTHORIZED = NO
ARCHITECTURE_APPROVAL = APPROVED
FOUNDATION_APPROVAL = APPROVED
PROJECT_GOVERNANCE_BINDING = ACTIVE / VALIDATED
PROJECT_OPENING_GATE = PASS
CONTINUITY_RECOVERY_GATE = PASS
OPENING_CONTINUITY_HANDOFF = PASS
AGENT_HANDOFF_GATE = PRIOR_PASS / NOT_REASSESSED_THIS_ACTIVITY
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
GIT_PUBLICATION_AUTHORIZATION = STAGE_AND_COMMIT_ONLY / PENDING_DOCUMENTATION_PACKAGE
CONTRACT_FIRST_IMPLEMENTATION = REQUIRED
S0_CONTRACT_ID = S0_IMPLEMENTATION_CONTRACT
S0_CONTRACT_VERSION = 1.0
S0_CONTRACT_STATUS = DRAFT_BLOCKED
S0_CONTRACT_APPROVAL = NOT_GRANTED
S0_CONTRACT_GAPS = CG-01, CG-02, CG-03, CG-04, CG-05
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

SAFE_RESUME_POINT = Revisar o draft bloqueado em docs/contracts/S0_IMPLEMENTATION_CONTRACT.md e fechar CG-01–05 com decisões rastreáveis antes de aprovação do contrato. S0 permanece selecionado e não iniciado. A revisão anterior de DoR está em READY_FOR_AUTHORIZATION; o novo requisito de contrato aprovado e sem gaps também deve ser satisfeito antes de implementação. Aprovação do contrato e autorização de S0 são decisões distintas.

NEXT_REQUIRED_ACTIVITY = S0_CONTRACT_GAP_RESOLUTION_WITH_USER_DECISIONS
NEXT_ACTIVITY_READINESS = BLOCKED_PENDING_CG_01_TO_05
NEXT_ACTIVITY_AUTHORIZATION = NOT_GRANTED_FOR_NEW_DECISIONS_OR_IMPLEMENTATION
USER_CONTINUITY_VALIDATION = A atividade de recuperação foi explicitamente solicitada e concluída; nenhum avanço para S0 foi feito.

## Invariantes e limites

Invariantes de produto permanecem em REQUIREMENTS, ARCHITECTURE e ENGINEERING_FOUNDATION: adapters/gateway, parsers plugáveis, três fontes de verdade, commit físico antes de DOWNLOADED, resume condicional, workers limitados e acesso legítimo. `FRONTEND_FIRST_RULE = NOT_APPLICABLE` para a CLI sem frontend gráfico/web.

GOV-B01 foi resolvido: os pacotes e schema canônicos conferem com seus manifests; binding, pins e checks aplicáveis passaram. Nenhuma decisão de arquitetura/fundação foi reaberta. Nenhuma capability de produto foi implementada. `S0_STARTED = NO`, `S0_AUTHORIZED = NO`, `IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED` e `GIT_PUBLICATION_AUTHORIZATION = NOT_GRANTED`.

Readiness de S0 e DoR foram avaliados em [S0_READINESS_REVIEW_2026-10-05](S0_READINESS_REVIEW_2026-10-05.md): `READY_FOR_AUTHORIZATION`. `S0_STARTED = NO`, `S0_AUTHORIZED = NO` e `IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED`; somente decisão explícita do usuário pode autorizar o início.

Riscos futuros permanecem nos documentos de produto/fundação e no contexto não normativo [AUDITORIA_TECNICA_2026-10-05](../audit/AUDITORIA_TECNICA_2026-10-05.md): identidade/revisão de mídia antes de schema/deduplicação em S2 e componentes S4/S6/S7; reconciliação filesystem/SQLite e ownership antes de finalização S4; semântica de checkpoint antes de persistência definitiva em S2 e sync S7; proteção concreta da sessão antes de acesso real em S1. As condições e spikes estão mapeados em [SPRINTS](../planning/SPRINTS.md#future-sprint-entry-conditions); não são blockers globais de S0. GUI, TDLib e suporte adicional continuam adiados; pacote Windows permanece na unidade S10.

## Contrato S0 — atividade documental atual

O Card B atual do usuário (anexo `d94b27af-126b-4487-b20b-339d8bf373b5/Texto colado.txt`) autoriza criar [S0_IMPLEMENTATION_CONTRACT](../contracts/S0_IMPLEMENTATION_CONTRACT.md) e registrar sua existência/status nos documentos estritamente necessários do projeto. Proíbe implementação, bootstrap, instalação, Telegram real, governança externa e staging/commit/push. Execução DIRECT, sem subagentes. O pedido estabelece contrato primeiro, autoria Sol e implementação futura Luna, sem reinterpretar ou preencher gaps durante implementação. O runtime desta sessão é Codex baseado em GPT-6; não se afirma execução no GPT-5.6 Sol/Médio solicitado pelo payload.

O contrato 1.0 nasce DRAFT e termina `DRAFT_BLOCKED`, sem aprovação e sem authority operacional ativa. Cinco gaps impedem entregá-lo executável sem decisões pelo implementador: faixas de aiosqlite/Rich/pytest/Ruff (CG-01); layout/manifest físico e namespace (CG-02); configuração básica exata (CG-03); entrada e smoke CLI (CG-04); backend/metadados/instalação reproduzível e perfil pytest/Ruff (CG-05). Evidência e dados necessários para fechamento estão no §22 do contrato; não foram inventadas versões ou novas decisões aprovadas.

A decisão anterior `S0_READINESS = READY_FOR_AUTHORIZATION`, com zero blockers naquela revisão, é preservada em [S0_READINESS_REVIEW_2026-10-05](S0_READINESS_REVIEW_2026-10-05.md). Ela não avaliava o novo contrato sem escolhas por Luna. Os gaps atuais bloqueiam o contrato e a implementação sob a regra nova; não reabrem a arquitetura nem promovem findings de S2+ a blockers de bootstrap. Após fechamento dos gaps, revisar/aprovar contrato explicitamente e então decidir autorização de S0, com DoR vigente.

Fatos desta atividade: root/branch/HEAD/upstream e índice foram verificados novamente; permanecem no baseline acima, com índice vazio. Sete pins de governança e Continuity 3.0 conferem por SHA-256; Registry global corresponde às versões adotadas. Schema/hash e estrutura focal do binding foram conferidos; o PASS histórico Draft 2020-12 é preservado, sem alegar nova execução genérica porque o validador não está disponível. A validação documental usou runtime já empacotado do aplicativo, sem criar ambiente de produto. Nenhum SP-01, pytest/Ruff de produto, bootstrap, instalação ou acesso Telegram foi executado.

Reconciliação temporal: Opening/evidência preservam a fotografia anterior `S0_READY = NO`; a prontidão posterior está em STATE/revisão específica. O último parágrafo do bootstrap contém texto procedural desatualizado de prontidão: não substitui essas authorities e foi explicitado no contrato §1. Não se declara novo handoff global PASS nesta atividade. Registros de gates anteriores são evidência histórica, sem ampliar autorização.

Escrita da autoria limitada ao contrato, a este registro de estado e ao mapa para descoberta do draft. Outras mudanças preexistentes foram preservadas durante a autoria. `ACTIVITY_COMPLETION_PERCENT = 80%`: quatro de cinco etapas documentais (recuperação, rastreabilidade, draft e self-review/registro) concluídas; fechamento semântico e prontidão para aprovação bloqueados por CG-01–05. `PROJECT_COMPLETION_PERCENT = 0%` pelo denominador de sprints aceitas, 0/11; este indicador não mede o trabalho documental já realizado. `S0_STARTED = NO`, `S0_AUTHORIZED = NO`, `IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED`. A autorização Git posterior está delimitada abaixo.

## Autorização posterior — checkpoint documental Git

Após receber o draft bloqueado, o usuário autorizou explicitamente stage e commit, deixando a mensagem a critério do executor. Em resposta à delimitação de conteúdo, escolheu: “Todo o pacote documental pendente do projeto, incluindo abertura, prontidão e contrato”. Essa instrução posterior autoriza incluir as mudanças documentais anteriores no mesmo checkpoint; não exige descartar ou isolar artificialmente os deltas em STATE/mapa.

Escopo: arquivos documentais pendentes em `docs/` e `AGENTS.md`, com staging por paths explícitos e verificação do índice antes do commit. A reconciliação deste registro e da navegação procedural do bootstrap acompanha o checkpoint. Nenhum produto, instalação, sessão, segredo ou arquivo da governança externa integra esse escopo. `PUSH_AUTHORIZATION = NOT_GRANTED`. A autorização se limita ao checkpoint documental solicitado; não é permissão permanente para novos commits.

Baseline antes do commit: `master`, HEAD `a00f325df45f3adad13b3a99d00c3230f913b282`, upstream `origin/master`, índice vazio e 16 arquivos documentais pendentes identificados. O hash do commit resultante, índice e worktree devem ser descobertos em Git; não se cria commit autorreferente para registrar seu próprio hash. O snapshot mantém como histórico os fatos de recuperação/abertura e da autoria antes desta autorização, inclusive as declarações de que nada foi staged ou publicado naquelas atividades. Contrato permanece `DRAFT_BLOCKED`; aprovação e implementação continuam não concedidas.
