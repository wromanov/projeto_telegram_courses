# PM-01 — Condução de Projetos v1.0

```text
POLICY_ID = PM-01
VERSION = 1.0
STATUS = CANONICAL
LIFECYCLE = ACTIVE
CANONICALIZATION = YES
USER_REVIEW_REQUIRED = NO
NORMATIVE_OWNER = PROJECT_EXECUTION_AND_CONTINUITY
```

## 1. Finalidade e escopo

Esta proposta define regras transversais para planejar, executar, integrar, validar, encerrar e retomar atividades de projetos. Authorities específicas do projeto continuam governando domínio, arquitetura, contratos e critérios locais. Esta policy define condução e estado de execução, sem substituir essas authorities.

## 2. Hierarquia operacional e authorities documentais

```text
PROJECT
→ ROADMAP
→ PHASE
→ DELIVERY_UNIT
→ SLICE
→ ACTIVITY
```

- **ROADMAP**: direção macro, fases, dependências e milestones.
- **PHASE**: etapa de projeto com objetivo, resultado e condições de avanço.
- **DELIVERY_UNIT**: unidade executável de planejamento dentro da direção do roadmap.
- **SLICE**: menor incremento integrado prático que produz resultado verificável no fluxo do projeto.
- **ACTIVITY**: tarefa concreta autorizada dentro da unidade e slice aplicáveis.

```text
DELIVERY_UNIT =
SPRINT
| MILESTONE
| ITERATION
| CONTINUOUS_FLOW
| EXPERIMENT
| RESEARCH_CAMPAIGN

PREFERRED_DELIVERY_UNIT_FOR_STANDARD_SOFTWARE_PROJECTS = SPRINT
```

`ROADMAP` define direção macro, fases, dependências e milestones. `DELIVERY_UNIT` organiza o planejamento executável; projects podem selecionar o tipo adequado sem tratar sprint como unidade universal.

- **EXECUTION_PLAN / SPRINTS**: plano e sequência executáveis para as delivery units, gates e backlog.
- **PROJECT_STATE**: estado factual corrente, atividade, gates, baseline e bloqueios.

Para continuidade, os papéis documentais são: `ROADMAP` (para onde o projeto vai), `EXECUTION_PLAN` (como delivery units executam), `PROJECT_STATE` (onde está), `CONTINUITY_RECORD` (dados para reassumir), `ACTIVE_AUTHORITY_MAP` (authority por assunto), `BOOTSTRAP` (procedimento de início/retomada) e `SPECS / ADRs / CONTRACTS` (decisões duráveis e seu funcionamento). Projetos podem adotar nomes físicos diferentes, mas devem declarar equivalência e localização.

```text
ONE_RESPONSIBILITY = ONE_PRIMARY_AUTHORITY
CONTINUITY_RECORD != SECOND_PROJECT_STATE
DETAIL_ONCE = REQUIRED
REFERENCE_EVERYWHERE_ELSE = REQUIRED
```

Bootstrap é procedimento, não uma cópia de authorities ou source of truth.

## 3. Integração incremental obrigatória

```text
INCREMENTAL_INTEGRATION_RULE = MANDATORY
IMPLEMENT
→ MODULE_VALIDATE
→ INTEGRATE_INTO_CANONICAL_FLOW
→ INTEGRATION_VALIDATE
→ VALIDATE_ACCUMULATED_FLOW
→ REGRESSION_VALIDATE
→ RECONCILE_PROJECT_STATE
→ CLOSE
```

```text
IMPLEMENTED != INTEGRATED
UNIT_TEST_PASS != SLICE_DONE
MODULE_COMPLETE != PROJECT_FLOW_COMPLETE
BIG_BANG_INTEGRATION_AT_END = PROHIBITED
UNTRACKED_INTEGRATION_DEBT = PROHIBITED
ISOLATED_MODULE_ACCUMULATION = PROHIBITED
SYSTEM_GROWS_FROM_LAST_INTEGRATED_BASELINE = REQUIRED
```

Cada slice aplicável passa por `MODULE_GATE`, `INTEGRATION_GATE`, `ACCUMULATED_FLOW_GATE` e `REGRESSION_GATE`. Uma slice não fecha por estar apenas implementada ou validada isoladamente; precisa estar integrada ao fluxo canônico e passar os gates pertinentes.

Adiar integração é excepcional e exige registro explícito:

```text
INTEGRATION_DEFERRED = EXPLICIT
REASON = REQUIRED_EXPLICIT_VALUE
DEPENDENCY = REQUIRED_EXPLICIT_VALUE
OWNER = REQUIRED_EXPLICIT_VALUE
TARGET_SLICE = REQUIRED_EXPLICIT_VALUE
RISK = REQUIRED_EXPLICIT_VALUE
USER_APPROVAL = EXPLICIT_DECISION_OR_NOT_REQUIRED_WITH_BASIS
```

O adiamento não transforma a slice em integrada nem permite iniciar atividade dependente antes do gate requerido.

## 4. Vertical slice

```text
VERTICAL_SLICE_FIRST = PREFERRED
BUILD_COMPONENTS_FIRST_INTEGRATE_LATER = PROHIBITED_BY_DEFAULT
DEFER_ALL_INTEGRATION_TO_FINAL_DELIVERY_UNIT = PROHIBITED
```

SPIKE, PROTOTYPE ou RESEARCH_ARTIFACT podem ter escopo isolado quando isso for necessário para reduzir incerteza. Registrar objetivo, limite e resultado esperado. `PROTOTYPE_COMPLETE != PRODUCT_INTEGRATED`; resultado de pesquisa não conta como capacidade operacional integrada.

## 5. Frontend-first e integração incremental de produto

Avaliar e registrar a aplicabilidade no nível do projeto:

```text
USER_FACING_FRONTEND_REQUIRED = YES | NO
```

Quando `YES`:

```text
FRONTEND_FIRST_DELIVERY_MODEL = REQUIRED
```

Fluxo padrão:

```text
DISCOVER_USER_FLOWS
→ DEFINE_UI_REQUIREMENTS
→ BUILD_UI_UX_PROTOTYPE
→ VALIDATE_PROTOTYPE
→ FREEZE_INITIAL_UI_CONTRACT
→ IMPLEMENT_FRONTEND_FUNCTIONAL_BASELINE
→ VALIDATE_FRONTEND_FLOW
→ IMPLEMENT_BACKEND_VERTICAL_SLICE
→ CONNECT_SLICE_TO_FRONTEND
→ INTEGRATE_WITH_CANONICAL_SYSTEM_FLOW
→ VALIDATE_END_TO_END
→ VALIDATE_ACCUMULATED_FLOW
→ CLOSE_SLICE
```

```text
PROTOTYPE_APPROVED != FRONTEND_IMPLEMENTED
FRONTEND_IMPLEMENTED != FRONTEND_BACKEND_INTEGRATED
BACKEND_IMPLEMENTED != USER_FACING_CAPABILITY_DONE
DEFER_FRONTEND_INTEGRATION_TO_END = PROHIBITED
BIG_BANG_FRONTEND_BACKEND_INTEGRATION_AT_END = PROHIBITED
ISOLATED_MODULE_ACCUMULATION = PROHIBITED
```

Cada backend slice voltada ao usuário passa por:

```text
IMPLEMENT
→ MODULE_VALIDATE
→ CONNECT_TO_FRONTEND
→ INTEGRATE_WITH_EXISTING_CANONICAL_FLOW
→ INTEGRATE_WITH_REAL_UPSTREAM_AND_DOWNSTREAM_DEPENDENCIES
→ VALIDATE_FRONTEND_BACKEND_CONTRACT
→ VALIDATE_USER_FLOW
→ VALIDATE_ACCUMULATED_SYSTEM
→ CLOSE
```

Integrar com dependências reais do fluxo; não criar acoplamento artificial apenas para conectar um módulo ao próximo módulo. A baseline frontend pode usar `MOCK_DATA`, `STUBS`, `FAKE_ADAPTERS` ou `STATIC_FIXTURES` quando isso permitir validar a experiência antes da integração real. `MOCKED_INTEGRATION != PRODUCT_INTEGRATION`.

```text
FRONTEND_INTEGRATION_GATE
BACKEND_MODULE_IMPLEMENTED = YES
BACKEND_MODULE_VALIDATED = PASS
FRONTEND_CONSUMPTION_IMPLEMENTED = YES
FRONTEND_BACKEND_CONTRACT_VALIDATED = PASS
USER_FLOW_VALIDATED = PASS
ACCUMULATED_FLOW_VALIDATED = PASS
REGRESSION_VALIDATION = PASS
```

Sem todos os critérios aplicáveis do gate, `CAPABILITY_STATUS != DONE`.

`FRONTEND_FIRST_RULE = NOT_APPLICABLE` para `HEADLESS_SERVICE`, `LIBRARY`, `CLI`, `BACKGROUND_WORKER`, `INFRASTRUCTURE_COMPONENT` ou `DATA_PIPELINE`, quando a capability não exigir frontend voltado ao usuário. Trabalho técnico fundacional pode preceder o frontend somente quando necessário para viabilidade, domain/API/integration contract ou restrição arquitetural. Esse trabalho permanece mínimo e não pode se tornar implementação completa backend-first.

## 6. Definition of Ready

Antes de iniciar implementação material, o gate `DEFINITION_OF_READY` deve passar:

```text
AUTHORITY_IDENTIFIED = YES
OBJECTIVE_DEFINED = YES
SCOPE_DEFINED = YES
PREDECESSORS_SATISFIED = YES
DEPENDENCIES_KNOWN = YES
CANONICAL_INTEGRATION_POINT_KNOWN = YES
ACCEPTANCE_CRITERIA_DEFINED = YES
VALIDATION_STRATEGY_DEFINED = YES
BLOCKERS = NONE
```

Se o ponto de integração canônico for desconhecido, não iniciar implementação material. Atividade de descoberta limitada pode ser autorizada como SPIKE para determiná-lo.

Para slice voltada ao usuário, incluir no `DEFINITION_OF_READY`:

```text
USER_FLOW_DEFINED = YES
UI_STATE_DEFINED = YES
FRONTEND_ENTRY_POINT_KNOWN = YES
BACKEND_INTEGRATION_POINT_KNOWN = YES
CONTRACT_DEFINED = YES
UPSTREAM_DEPENDENCIES_KNOWN = YES
DOWNSTREAM_DEPENDENCIES_KNOWN = YES
```

Se qualquer item aplicável estiver ausente, ou o ponto de integração user-facing for desconhecido:

```text
USER_FACING_SLICE_READY = NO
```

## 7. Definition of Done e encerramento de slice

`DEFINITION_OF_DONE = PASS` somente após verificar, quando aplicável:

```text
IMPLEMENTATION_COMPLETE = YES
MODULE_VALIDATION = PASS
CANONICAL_INTEGRATION = COMPLETE
INTEGRATION_VALIDATION = PASS
ACCUMULATED_FLOW_VALIDATION = PASS
REGRESSION_VALIDATION = PASS
INVARIANTS_PRESERVED = YES
ACCEPTANCE_CRITERIA = PASS
DOCUMENTATION_RECONCILED = YES
PROJECT_STATE_UPDATED = YES
DELIVERY_UNIT_STATE_UPDATED = YES
ROADMAP_UPDATED_IF_MATERIAL = YES
FRONTEND_INTEGRATION_GATE = PASS_WHEN_APPLICABLE
OUT_OF_SCOPE_CHANGES = NONE
BLOCKERS = NONE
```

`SLICE_CLOSE_GATE` verifica: escopo autorizado; implementação; integração; fluxo acumulado; regressão; documentação pertinente; PROJECT_STATE; estado da delivery unit; roadmap quando material; blockers; e estado Git factual. Marcar requisitos não aplicáveis com justificativa verificável.

Para capability voltada ao usuário, a seção 5 `FRONTEND_INTEGRATION_GATE` é requisito de fechamento; se qualquer critério aplicável falhar, a capability não está `DONE`.

```text
TECHNICAL_DONE != GIT_PUBLISHED
SLICE_TECHNICALLY_CLOSED != CHECKPOINT_PUBLISHED
PROJECT_CHECKPOINT_CLOSED != GIT_PUBLICATION_AUTHORIZED
```

Fechamento técnico não autoriza stage, commit, push, tag, release, merge ou outra publicação Git. Essas ações dependem de autorização específica aplicável.

## 8. Avanço e atividades formais

```text
MAX_ACTIVE_FORMAL_ACTIVITIES = 1
NEXT_ACTIVITY_SELECTED != NEXT_ACTIVITY_READY
NEXT_ACTIVITY_READY != NEXT_ACTIVITY_AUTHORIZED
ROADMAP_ITEM_EXISTS != EXECUTION_AUTHORIZED
DELIVERY_UNIT_PLANNED != DELIVERY_UNIT_AUTHORIZED
SPRINT_PLANNED != SPRINT_AUTHORIZED
ADVANCEMENT_MODE = FAIL_CLOSED
```

Seleção, prontidão e autorização são estados distintos. Não iniciar atividade sem autoridade, escopo e autorização identificáveis. Atividade dependente não começa enquanto o gate de integração predecessor necessário estiver pendente ou reprovado.

Dúvida material sobre integração, authority, baseline, aceite, dependência ou estado bloqueia o avanço afetado até reconciliação. Não resolver lacunas por suposição.

## 9. Métricas de progresso

Manter medidas separadas e baseadas em evidência:

- `ACTIVITY_COMPLETION_PERCENT`: somente o prompt/atividade corrente; aplicar PM-02 quando pertinente.
- `DELIVERY_UNIT_COMPLETION_PERCENT`: progresso das activities e gates da delivery unit corrente; se ela for uma sprint, o valor também pode ser nomeado `SPRINT_COMPLETION_PERCENT`.
- `PROJECT_COMPLETION_PERCENT`: progresso das entregas e critérios do roadmap canônico.

Implementação isolada não recebe crédito de conclusão integrada. `STRUCTURAL_COMPLETION != OPERATIONAL_COMPLETION`. Não usar contagem de linhas, arquivos ou tokens como medida de conclusão do projeto. Declarar evidências e denominador de cada percentual.

## 10. Regressão acumulada

```text
NEW_SLICE + PREVIOUS_VALID_INCREMENT = NEW_VALID_BASELINE
ACCUMULATED_REGRESSION_GATE = REQUIRED_WHEN_APPLICABLE
```

Validar a nova capacidade junto às capacidades previamente válidas que possam ser afetadas. Se a regressão acumulada falhar, a nova baseline integrada não é válida; registrar falha e limitar o avanço dependente.

## 11. Atualização documental por materialidade

```text
DOCUMENTATION_LAG = PROHIBITED_AT_MATERIAL_CHECKPOINT
```

Reconciliar PROJECT_STATE, execution plan/delivery unit, roadmap e registro de continuidade conforme o impacto real. Não propagar microalterações a vários documentos sem mudança de estado. Cada responsabilidade deve ter uma authority primária; os demais documentos referenciam-na.

## 12. Continuidade e rastreabilidade

```text
PROJECT_CONTINUITY_AND_TRACEABILITY = MANDATORY
PROJECT_STATE_MUST_NOT_DEPEND_ON_CHAT_HISTORY = YES
PROJECT_STATE_MUST_NOT_DEPEND_ON_SPECIFIC_AGENT = YES
TACIT_PROJECT_STATE = PROHIBITED
CHAT_HISTORY_REQUIRED_FOR_RESUMPTION = NO
NEW_AGENT_CAN_RESUME_FROM_GOVERNED_PROJECT_ARTIFACTS = YES
```

A continuidade lógica deve ser reconstruível a partir de artifacts governados, com acesso ao projeto, authorities e ferramentas necessárias. Histórico de conversa pode ser contexto adicional, nunca requisito para descobrir estado, decisões fechadas e próximo passo.

### 12.1 Dataset mínimo de continuidade

Em checkpoint material, tornar descobríveis, diretamente ou por referências estáveis:

```text
PROJECT_IDENTITY
PROJECT_ROOT
CURRENT_BRANCH
BASELINE_TRACEABILITY
CURRENT_PHASE
CURRENT_DELIVERY_UNIT
CURRENT_ACTIVITY
LAST_COMPLETED_ACTIVITY
NEXT_ACTIVITY
NEXT_ACTIVITY_READINESS
NEXT_ACTIVITY_AUTHORIZATION
CURRENT_AUTHORITIES
CURRENT_INVARIANTS
OPEN_DECISIONS
BLOCKERS
KNOWN_RISKS
DEFERRED_ITEMS
IMPLEMENTATION_AUTHORIZATION_STATE
GIT_PUBLICATION_AUTHORIZATION_STATE
LAST_VALIDATED_INTEGRATED_BASELINE
SAFE_RESUME_POINT
EXACT_CURRENT_HEAD = DISCOVER_AT_RUNTIME_WHEN_GIT_AVAILABLE
```

`BASELINE_TRACEABILITY = REQUIRED`. Descobrir o `EXACT_CURRENT_HEAD` em runtime quando Git estiver disponível. Não criar commit autorreferente apenas para registrar seu próprio hash; registrar a referência de baseline que pode ser verificada.

### 12.2 Gatilhos de reconciliação

```text
CONTINUITY_RECONCILIATION_TRIGGER =
CURRENT_ACTIVITY_CHANGED
OR NEXT_ACTIVITY_CHANGED
OR PHASE_CHANGED
OR DELIVERY_UNIT_CHANGED
OR MATERIAL_CAPABILITY_CLOSED
OR ARCHITECTURAL_DECISION_CHANGED
OR CANONICAL_AUTHORITY_CHANGED
OR MATERIAL_BLOCKER_CREATED_OR_RESOLVED
OR MATERIAL_RISK_CHANGED
OR AUTHORIZATION_STATE_CHANGED
OR SAFE_RESUME_POINT_CHANGED
```

Sem ocorrência de gatilho material:

```text
CONTINUITY_RECONCILIATION_REQUIRED = NO
```

### 12.3 Gate de handoff

Em cada checkpoint material:

```text
MATERIAL_CHECKPOINT = YES
AGENT_HANDOFF_GATE = REQUIRED
```

PASS exige todos os itens abaixo. Os campos podem ser satisfeitos por referências estáveis, desde que o destino esteja atual e seja descobrível:

```text
CONTINUITY_ROOT_EXISTS = YES
START_HERE_CURRENT = YES
PROJECT_STATE_CURRENT = YES
ROADMAP_CURRENT = YES
EXECUTION_PLAN_CURRENT = YES
ACTIVE_AUTHORITY_MAP_CURRENT = YES
CONTINUITY_RECORD_CURRENT = YES
GOVERNANCE_BINDING_CURRENT = YES
CURRENT_STATE_DISCOVERABLE = YES
LAST_COMPLETED_ACTIVITY_DISCOVERABLE = YES
NEXT_ACTIVITY_DISCOVERABLE = YES
NEXT_ACTIVITY_READINESS_DISCOVERABLE = YES
NEXT_ACTIVITY_AUTHORIZATION_DISCOVERABLE = YES
BASELINE_TRACEABLE = YES
CANONICAL_AUTHORITIES_DISCOVERABLE = YES
OPEN_DECISIONS_DISCOVERABLE = YES
BLOCKERS_DISCOVERABLE = YES
KNOWN_RISKS_DISCOVERABLE = YES
DEFERRED_ITEMS_DISCOVERABLE = YES
AUTHORIZATION_STATE_DISCOVERABLE = YES
SAFE_RESUME_POINT_DISCOVERABLE = YES
KNOWN_STALE_STATE = NO
CONTRADICTORY_ACTIVE_STATE = NO
SUPERSEDED_AUTHORITY_USED_AS_CURRENT = NO
CHAT_HISTORY_REQUIRED_FOR_RESUMPTION = NO
NEW_AGENT_CAN_RESUME_FROM_GOVERNED_PROJECT_ARTIFACTS = YES
```

Inclui também a discoverability de phase e delivery unit correntes, invariants e `LAST_VALIDATED_INTEGRATED_BASELINE`.

Falha material:

```text
AGENT_HANDOFF_GATE = FAIL
PROJECT_CHECKPOINT_CLOSURE = BLOCKED
```

### 12.4 Ponto seguro de retomada e estado obsoleto

`SAFE_RESUME_POINT` identifica o último estado confiável a partir do qual outro agente pode continuar sem repetir trabalho válido nem reabrir decisões já fechadas. Definir em cada checkpoint material.

```text
DOCUMENT_EXISTS != DOCUMENT_IS_CURRENT
```

Se documentação ativa divergir de estado factual verificável: não adivinhar; interromper o escopo afetado; reconciliar as authorities ou relatar o conflito. Bootstrap recomendado: (1) ler PROJECT_STATE; (2) ler ACTIVE_AUTHORITY_MAP; (3) identificar atividade atual/próxima; (4) carregar authorities aplicáveis; (5) ler CONTINUITY_RECORD, se houver; (6) verificar baseline do repositório; (7) conferir bloqueios e autorização; (8) confirmar SAFE_RESUME_POINT; (9) prosseguir apenas se readiness permitir.

### 12.5 Raiz do pacote de continuidade e limites

```text
PROJECT_CONTINUITY_PACKAGE = MANDATORY
PROJECT_CONTINUITY_ROOT_RULE = MANDATORY
DEFAULT_PROJECT_CONTINUITY_ROOT = docs/continuity/
CONTINUITY_ENTRYPOINT = docs/continuity/START_HERE.md
```

Estrutura padrão:

```text
docs/continuity/
├── START_HERE.md
├── PROJECT_STATE.md
├── ACTIVE_AUTHORITY_MAP.md
├── CONTINUITY_RECORD.md
├── NEW_AGENT_BOOTSTRAP.md
├── PROJECT_GOVERNANCE_BINDING.json
├── planning/
│   ├── ROADMAP.md
│   └── SPRINTS.md
└── handoff/
    └── LAST_HANDOFF.md
```

Nomes físicos podem variar quando houver convenção equivalente e explícita, registrada no próprio pacote. `START_HERE.md` é navegação/bootstrap: `START_HERE != SECOND_PROJECT_STATE`.

```text
CONTINUITY_ROOT_CONTAINS = STATE + NAVIGATION + EXECUTION_AUTHORITIES
CONTINUITY_CRITICAL_AUTHORITIES_MUST_BE_INSIDE_PROJECT_CONTINUITY_ROOT = YES
```

Manter dentro da raiz, diretamente ou na estrutura equivalente: `PROJECT_STATE`, `ROADMAP`, `EXECUTION_PLAN / SPRINTS`, `ACTIVE_AUTHORITY_MAP`, `CONTINUITY_RECORD`, bootstrap e `PROJECT_GOVERNANCE_BINDING`. O pacote deve expor a identidade do projeto, authorities/invariants atuais, situação de autorização e ponto seguro de retomada.

Authorities de domínio podem ficar em localizações semanticamente apropriadas fora da raiz, incluindo architecture specs, ADRs, API specs, domain contracts, database schemas, design system e research authorities. Todas as authorities canônicas externas devem ser listadas e descobríveis por `ACTIVE_AUTHORITY_MAP`.

### 12.6 Fonte única da verdade

```text
ONE_RESPONSIBILITY = ONE_PRIMARY_AUTHORITY
SINGLE_SOURCE_OF_TRUTH_RULE = MANDATORY
DETAIL_ONCE = REQUIRED
REFERENCE_EVERYWHERE_ELSE = REQUIRED
DUPLICATE_ACTIVE_PROJECT_STATE = PROHIBITED
DUPLICATE_ACTIVE_ROADMAP = PROHIBITED
DUPLICATE_ACTIVE_EXECUTION_PLAN = PROHIBITED
CONTINUITY_RECORD != SECOND_PROJECT_STATE
```

Se `ROADMAP` ou `SPRINTS / EXECUTION_PLAN` forem movidos para `docs/continuity/`, o caminho anterior não permanece como segunda cópia ativa. Quando necessário, ele pode conter somente redirect ou reference para a authority corrente.

## 13. Estado canônico

```text
STATUS = CANONICAL
LIFECYCLE = ACTIVE
CANONICALIZATION = YES
USER_REVIEW_REQUIRED = NO
```

PM-01 v1.0 é policy canônica ativa para condução, integração, avanço, continuidade e rastreabilidade de projetos.
