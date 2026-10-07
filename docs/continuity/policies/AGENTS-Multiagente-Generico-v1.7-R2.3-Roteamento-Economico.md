# Política transversal de execução direta, delegação multiagente e roteamento econômico de inteligência — v1.7-R2.3 — CANONICAL / ACTIVE

## 0. Status e finalidade

```text
VERSION = v1.7-R2.3
STATUS = CANONICAL
LIFECYCLE = ACTIVE
PREVIOUS_BASELINE = v1.7-R2.2
PREVIOUS_BASELINE_ROLE = CURRENT_CANONICAL_UNTIL_PROMOTION
REVISION_FOCUS = GPT6_MODEL_ROUTING + CURRENT_AGENT_RUNTIME_SEMANTICS + ROLE_MODEL_TOOL_SEPARATION + LUNA_XHIGH_ROOT_ELIGIBILITY
PROMPT_POLICY_ALIGNMENT = Politica-Prompts-Agente-v1.7-R2.6.md
CANONICALIZATION = YES
PROMOTION = YES
USER_REVIEW_REQUIRED = NO
TRANSITION_SCOPE = AGENT ARCHITECTURE, ECONOMICAL INTELLIGENCE ROUTING, RUNTIME CAPABILITIES AND FUNCTIONAL ROLES

SCOPE = ANY GOVERNED PROJECT / AGENT
DIRECT_EXECUTION = DEFAULT
MULTIAGENT_EXECUTION = EXCEPTION
OPTIONAL_SUBAGENT = CONDITIONAL_WITHIN_AUTHORIZED_MULTIAGENT_SCOPE
AUTO_ESCALATION = NO
ROLE_CATALOG_IS_FUNCTIONAL_GUIDANCE = YES
RUNTIME_PROFILE_REQUIRED = NO
ROLE_AVAILABLE != ROLE_NECESSARY
USER_FINAL_AUTHORITY = YES
```

Esta política define **quando executar diretamente e quando delegar a subagentes**.

O objetivo continua sendo obter a melhor relação entre qualidade, robustez, tempo,
consumo de contexto/tokens e custo de coordenação.

Esta revisão `v1.7-R2.3` é uma **candidata incremental** sobre a `v1.7-R2.2`.
Ela preserva o modelo operacional central da família v1.7 e não introduz metodologia
de execução cíclica bounded.

O foco desta revisão é:

- readequar o roteamento para a família GPT-6 `Luna → Sol → Astra`;
- preservar DIRECT-first, gates multiagente, authority e controle do usuário;
- tornar `Luna / XHigh` explicitamente elegível como ROOT quando Luna continua capability-sufficient;
- posicionar `Sol / Medium` como baseline técnico normal quando existe julgamento material;
- posicionar `Sol / High` como baseline de alto julgamento e decisão arquitetural material;
- definir `Sol / High → declaração de insuficiência → Astra / Medium` para escalonamento arquitetural;
- manter Terra fora do baseline atual de roteamento GPT-6, preservando-a somente para compatibilidade/histórico quando necessário;
- preservar `STOP / WAIT / USER RECONFIGURES / RESUME` para qualquer mudança mid-task de modelo/effort.

O modo multiagente **continua não sendo padrão, ritual, sinal de qualidade nem
consequência automática da complexidade da tarefa**. Ele só deve ser usado quando
houver **ganho material, identificável e verificável** em relação à execução direta.

Regra central:

> **Escolha a rota com menor custo esperado para uma tarefa concluída corretamente,
> preservando confiabilidade e autoridade. Se delegação, especialização, independência,
> paralelismo ou roteamento para tier inferior não produzirem ganho material líquido,
> execute diretamente.**

---

## 1. Precedência e autoridade

As authorities, regras de segurança, limites de escopo, gates, convenções e
instruções específicas do projeto, repositório, diretório ou tarefa têm
precedência sobre esta política.

```text
THIS_POLICY != PROJECT_AUTHORITY_REPLACEMENT
CAPABILITY != PERMISSION
DELEGATION != AUTHORITY_TRANSFER
MULTIAGENT != EXECUTION_AUTHORIZATION
```

O uso de subagentes não concede automaticamente autorização para:

- escrever arquivos;
- alterar arquitetura ou contrato;
- avançar fase/sprint/milestone;
- executar experimento;
- operar ambiente produtivo/LIVE;
- alterar dados persistidos;
- executar comandos de alto impacto;
- realizar `git add`, commit, push ou tag;
- modificar governance;
- tomar decisão reservada ao usuário.

Quando existir política canônica de Skills/Plugins, segurança, continuidade ou
outra governança transversal, ela complementa esta política sem ser substituída
por ela.

---

## 1.1. Escopo desta transição

Esta revisão altera **arquitetura, papéis e roteamento** de subagentes, mas
deliberadamente **não** introduz nesta etapa:

- metodologia formal de `Bounded Cyclic Execution`;
- Work Units como unidade normativa obrigatória;
- ledger operacional de ciclo;
- regras novas de retry cíclico;
- mudança de fluxo para loop autônomo estruturado.

Em outras palavras:

```text
THIS_REVISION = AGENT_ARCHITECTURE_PHASE
CYCLIC_EXECUTION_METHODOLOGY = OUT_OF_SCOPE_FOR_NOW
```

A adoção futura de execução cíclica poderá ocorrer em revisão posterior, separada
e explicitamente autorizada.

---
## 2. Invariantes fundamentais

```text
DIRECT_EXECUTION = DEFAULT
MULTIAGENT_EXECUTION = EXCEPTION

OPTIONAL_SUBAGENT = CONDITIONAL_WITHIN_AUTHORIZED_MULTIAGENT_SCOPE
AUTO_SPAWN = ALLOWED_AFTER_MULTIAGENT_AUTHORIZATION_AND_DELEGATION_GATE
AUTO_ESCALATION = NO

IN_EXECUTION_ROOT_AUTO_ESCALATION = PROHIBITED
MID_TASK_AUTO_MULTIAGENT_SWITCH = PROHIBITED
MODEL_CHANGE = USER_CONTROLLED
EFFORT_CHANGE = USER_CONTROLLED
EXECUTION_MODE_CHANGE = USER_CONTROLLED

COMPLEX_TASK != MULTIAGENT_REQUIRED
LARGE_TASK != MULTIAGENT_REQUIRED
HIGH_RISK_TASK != AUTOMATIC_SUBAGENT
STRONG_MODEL != MULTIAGENT_MODE
REVIEW != INDEPENDENT_AGENT_REVIEW
SELF_REVIEW != INDEPENDENT_REVIEW

MODEL_ESCALATION != MULTIAGENT_ESCALATION
SKILL_USE != SUBAGENT_REQUIRED
PLUGIN_USE != SUBAGENT_REQUIRED

DELEGATION_REQUIRES_MATERIAL_BENEFIT
COORDINATION_COST_MUST_BE_JUSTIFIED
IF_BENEFIT_IS_UNCLEAR = DIRECT
```

---

## 3. Direct-first com roteamento econômico

`DIRECT` continua sendo o padrão quando a execução direta for simultaneamente
**suficiente, simples e economicamente racional**.

A regra `DIRECT_EXECUTION = DEFAULT` não significa:

```text
ROOT_CAN_DO_THE_WORK
→ ROOT_SHOULD_DO_ALL_THE_WORK
```

Antes de decidir `DIRECT`, o agente principal deve avaliar não apenas se consegue
concluir toda a atividade, mas se manter a inteligência atual em todas as etapas
é a forma mais eficiente de alcançar o resultado correto.

Execução direta é preferida quando:

- existe uma única linha principal de raciocínio;
- o trabalho é fortemente acoplado e não possui fronteiras de handoff úteis;
- os mesmos arquivos/contextos precisariam ser relidos integralmente por todos;
- o custo de coordenação supera qualquer economia de tier;
- o trabalho delegado continuaria exigindo o mesmo julgamento do root;
- a quantidade de trabalho mecânico delegável é pequena demais para justificar handoff;
- a principal dificuldade é raciocínio contínuo e monolítico;
- um self-review do root é suficiente;
- não existe ganho material de paralelismo, especialização, independência,
  decomposição ou roteamento econômico de inteligência.

Por outro lado, uma atividade **sequencial** pode ser multiagente quando há ganho
material ao manter inteligência cara somente nos pontos cognitivos difíceis e
delegar execução bounded/verificável para tiers mais baratos.

```text
MULTIAGENT != PARALLELISM_ONLY
SEQUENTIAL_MULTIAGENT_PIPELINE = ALLOWED
```

Princípio:

```text
EXPENSIVE_INTELLIGENCE = COGNITIVE_HOTSPOTS_ONLY
BOUNDED_VERIFIABLE_EXECUTION = LOWEST_SUFFICIENT_TIER
```

Se todos os gates multiagente, inclusive o gate econômico, forem negativos:

```text
EXECUTION_MODE = DIRECT
SUBAGENTS_ALLOWED = NO
```

Se houver dúvida real e não for possível demonstrar ganho material:

```text
EXECUTION_MODE = DIRECT
```

---

## 4. Gate obrigatório para uso de multiagente

Um subagente só pode ser criado quando existir **benefício material verificável**
ligado a pelo menos uma das condições abaixo.

### G1 — Frentes paralelas realmente independentes

```text
PARALLEL_INDEPENDENT_FRONTS = YES
```

Exige pelo menos duas frentes que:

- possam avançar simultaneamente;
- tenham escopos claros e separáveis;
- não dependam de escrita concorrente sobre o mesmo estado;
- produzam entregáveis reconciliáveis;
- tragam redução real de tempo ou custo total.

### G2 — Especialização distinta necessária

```text
DISTINCT_SPECIALIZATION_REQUIRED = YES
```

Use quando uma disciplina separada for materialmente necessária, por exemplo
segurança, pesquisa externa, arquitetura, análise estatística, infraestrutura ou
performance, e sua separação reduzir risco ou melhorar substancialmente a decisão.

Especialização apenas conveniente não basta.

### G3 — Ganho material de decomposição

```text
MATERIAL_DECOMPOSITION_GAIN = YES
```

A decomposição deve reduzir materialmente pelo menos um destes fatores:

- wall-clock time;
- consumo de contexto do root;
- risco de omissão;
- volume operacional do root;
- custo total esperado;
- ruído de logs/evidências no root;
- complexidade cognitiva mantida no agente principal.

Dividir apenas para distribuir trabalho não constitui ganho.

### G4 — Conflito identificado que exige adjudicação

```text
IDENTIFIED_CONFLICT_REQUIRES_ADJUDICATION = YES
```

Deve existir divergência concreta entre evidências, contratos, interpretações ou
resultados. Não criar adjudicador preventivamente.

### G5 — Governança exige revisão independente

```text
GOVERNANCE_REQUIRES_INDEPENDENT_REVIEW = YES
```

Use agente independente quando policy, gate, standard, contrato ou decisão do
usuário exigir independência. Segunda opinião genérica não equivale a requisito
de independência.

### G6 — Ganho material de roteamento de inteligência

```text
MATERIAL_INTELLIGENCE_ROUTING_GAIN = YES
```

Existe quando a tarefa possui um ou mais **hotspots cognitivos** que justificam
um root/modelo mais forte, mas outras etapas podem ser executadas com segurança
por um tier mais barato.

O gate é satisfeito quando, em conjunto:

```text
HIGHER_TIER_REQUIRED_FOR_SOME_JUDGMENT = YES
LOWER_TIER_CAPABLE_OF_BOUNDED_EXECUTION = YES
DELEGATED_WORK_IS_OBJECTIVELY_VERIFIABLE = YES
HANDOFF_SCOPE_IS_CLEAR = YES
EXPECTED_TIER_SAVING_EXCEEDS_HANDOFF_COST = YES
```

Exemplos típicos:

- root Sol/High fecha a decisão matemática e Luna/High aplica patch mecânico;
- root Sol/High define invariantes e Luna/Medium ou High executa validações;
- root Luna/XHigh coordena investigação longa quando Luna continua capability-sufficient;
- root Sol/Medium coordena quando existe julgamento técnico material;
- root resolve um ponto difícil e de-escalona a execução operacional.

Este gate **não exige paralelismo**.

```text
PARALLEL_INDEPENDENT_FRONTS = NO
MATERIAL_INTELLIGENCE_ROUTING_GAIN = YES
EXECUTION_MODE = MULTIAGENT  # permitido se os demais critérios forem satisfeitos
```

---

## 5. Regra de elegibilidade multiagente

Atender a um gate é necessário, mas não suficiente.

Antes de delegar, também deve ser verdadeiro:

```text
AT_LEAST_ONE_MULTIAGENT_GATE = YES
EXPECTED_MATERIAL_GAIN = YES
SCOPE_PARTITION_IS_CLEAR = YES
COORDINATION_COST_IS_ACCEPTABLE = YES
RESULTS_CAN_BE_RECONCILED = YES
AUTHORITY_BOUNDARIES_ARE_PRESERVED = YES
ROOT_CAPABILITY_REDUNDANCY_CHECK = PASS
```

Somente então:

```text
EXECUTION_MODE = MULTIAGENT
```

Caso contrário:

```text
EXECUTION_MODE = DIRECT
SUBAGENTS_ALLOWED = NO
```

### 5.1 Regra custo-benefício

A métrica relevante é o custo esperado para uma tarefa concluída corretamente,
não o custo isolado de uma chamada.

```text
OPTIMIZATION_TARGET = EXPECTED_COST_PER_SUCCESSFUL_TASK
```

Considere:

```text
NET_MULTIAGENT_GAIN =
PARALLELISM_GAIN
+ SPECIALIZATION_GAIN
+ INDEPENDENCE_VALUE
+ ROOT_CONTEXT_REDUCTION
+ EXPENSIVE_TIER_TIME_SAVED
+ OPERATIONAL_WORK_OFFLOADED
-
COORDINATION_OVERHEAD
-
DUPLICATED_CONTEXT_COST
-
HANDOFF_COST
-
INTEGRATION_COST
-
CONSISTENCY_RISK
-
EXPECTED_RETRY_COST
```

Se o ganho líquido não for claramente positivo:

```text
EXECUTION_MODE = DIRECT
```

### 5.2 Gate de redundância do root

Antes de cada spawn, avaliar:

```text
DOES_ROOT_ALREADY_COVER_THIS_ROLE_SUFFICIENTLY?
```

Se `YES`, perguntar:

```text
IS_INDEPENDENCE_REQUIRED?
IS_DISTINCT_SPECIALIZATION_REQUIRED?
IS_ECONOMIC_OFFLOAD_MATERIAL?
```

Se todas forem `NO`:

```text
DO_NOT_SPAWN
```

Um subagente não deve duplicar uma capacidade já presente no root sem valor
adicional identificável.

### 5.3 Escolher entre reclassificar o ROOT e criar subagente

Antes de criar um agente mais inteligente, distinguir:

```text
NEED_MORE_INTELLIGENCE
vs
NEED_SEPARATE_RESPONSIBILITY
vs
NEED_INDEPENDENCE
```

Na seleção inicial, antes da atividade começar:

```text
IF NEED_MORE_INTELLIGENCE
AND NEED_SEPARATE_RESPONSIBILITY = NO
AND NEED_INDEPENDENCE = NO
→ SELECT_STRONGER_INITIAL_ROOT
```

Durante a execução:

```text
IF NEED_MORE_INTELLIGENCE
AND NEED_SEPARATE_RESPONSIBILITY = NO
AND NEED_INDEPENDENCE = NO
→ ROOT_RECLASSIFICATION_REQUIRED
→ STOP_AT_SAFE_BOUNDARY
→ REQUEST_USER_ROOT_RECONFIGURATION
→ WAIT_FOR_USER_CONFIRMATION
```

Quando existe responsabilidade separada:

```text
IF NEED_SEPARATE_RESPONSIBILITY = YES
→ APPLY_MULTIAGENT_GATES
→ APPLY_OFFLOAD_MATERIALITY_GATE
→ DELEGATE_ONLY_IF_MATERIAL_NET_GAIN
```

Quando existe requisito de independência:

```text
IF NEED_INDEPENDENCE = YES
→ USE_INDEPENDENT_AGENT_WHEN_AUTHORIZED
```

```text
ROOT_CAPABILITY_GAP
!=
MULTIAGENT_TRIGGER
```

Não criar subagente mais forte apenas para contornar um ROOT insuficiente se a
responsabilidade material continua única.

---

### 5.4 Múltiplas rotas válidas e critério de seleção

Uma mesma atividade pode admitir mais de uma arquitetura tecnicamente defensável.
A política não exige uma topologia única quando diferentes rotas preservam contrato,
authority, qualidade e critérios de aceite.

```text
MULTIPLE_VALID_ROUTINGS_MAY_EXIST = YES
```

Quando houver mais de uma rota válida, selecionar pela combinação de:

```text
ROUTE_SELECTION_OBJECTIVE =
EXPECTED_COST_PER_SUCCESSFUL_TASK
+ RELIABILITY
+ AUTHORITY_PRESERVATION
+ CONTEXT_EFFICIENCY
+ REVERSIBILITY
```

A comparação deve considerar pelo menos:

- tier e tempo do root;
- tier e tempo dos subagentes;
- volume operacional;
- duplicated context;
- handoff e integração;
- retries prováveis;
- verificabilidade;
- impacto de uma falha;
- necessidade real de independência.

Não escolha uma rota apenas porque ela possui mais agentes, menos agentes ou modelos
mais baratos por chamada. A unidade de otimização continua sendo a tarefa concluída
corretamente.

```text
CHEAPEST_CALL != CHEAPEST_SUCCESSFUL_ROUTE
FEWEST_AGENTS != ALWAYS_CHEAPEST_ROUTE
MOST_CAPABLE_ROUTE != ALWAYS_BEST_ROUTE
```

---

## 6. Cabeçalho obrigatório de decisão

Em atividades governadas relevantes, declare antes da execução:

```text
EXECUTION_MODE = DIRECT | MULTIAGENT

ORCHESTRATOR_MODEL =
ORCHESTRATOR_EFFORT =
ORCHESTRATOR_ROLE = ROOT

PARALLEL_INDEPENDENT_FRONTS = YES | NO
DISTINCT_SPECIALIZATION_REQUIRED = YES | NO
MATERIAL_DECOMPOSITION_GAIN = YES | NO
IDENTIFIED_CONFLICT_REQUIRES_ADJUDICATION = YES | NO
GOVERNANCE_REQUIRES_INDEPENDENT_REVIEW = YES | NO
MATERIAL_INTELLIGENCE_ROUTING_GAIN = YES | NO

EXPECTED_MATERIAL_GAIN = YES | NO
COORDINATION_COST = LOW | MEDIUM | HIGH
ROOT_CAPABILITY_REDUNDANCY_CHECK = PASS | FAIL

SUBAGENTS_ALLOWED = YES | NO
SUBAGENTS_PLANNED = <n>
```

Quando `EXECUTION_MODE = MULTIAGENT`, registrar para cada papel:

```text
SUBAGENT_ROLE =
MODEL =
EFFORT =
WHY_NOT_ROOT =
WHY_THIS_TIER =
EXPECTED_GAIN =
```

Se `EXECUTION_MODE = DIRECT`:

```text
SUBAGENTS_ALLOWED = NO
SUBAGENTS_PLANNED = 0
```

Não declarar subagente como “opcional”. A decisão deve ser justificada antes do
spawn ou reavaliada quando surgir novo gatilho material durante a execução.

---

## 7. Roteamento de inteligência e arquitetura operacional

Modelo, esforço, execução direta/delegada e papel são decisões relacionadas, mas
não equivalentes.

```text
MODEL
EFFORT
EXECUTION_MODE
ROLE
AUTHORITY
```

Orquestração e topologia de modelos são eixos independentes:

```text
ORCHESTRATION_RUNTIME = NATIVE | EXTERNAL | MANUAL
MODEL_TOPOLOGY = HOMOGENEOUS | HETEROGENEOUS

ROLE != MODEL != EFFORT != TOOL_SURFACE
```

`NATIVE_MULTIAGENT` descreve `ORCHESTRATION_RUNTIME = NATIVE`; `HETEROGENEOUS_MULTIAGENT`
descreve `MODEL_TOPOLOGY = HETEROGENEOUS`. Portanto, não são categorias mutuamente
exclusivas. Responses Multi-agent pode ser `NATIVE + HOMOGENEOUS` quando compartilha o
modelo da request; Codex com custom subagent models pode ser `NATIVE + HETEROGENEOUS`
quando os modelos por worker estão explicitamente configurados e confirmados pelo
runtime.

Aplicar:

```text
USE_MINIMUM_SUFFICIENT_INTELLIGENCE = YES
COST_MUST_NOT_OVERRIDE_RISK = YES
MODEL_ESCALATION != MULTIAGENT_ESCALATION
MODEL_ESCALATION != AUTHORITY_ESCALATION
```

Uma tarefa difícil e monolítica pode justificar um root mais forte em modo direto.
Uma tarefa com hotspot cognitivo seguido de trabalho bounded pode justificar root
forte + subagentes baratos em pipeline sequencial.

```text
HARD_SINGLE_THREAD_PROBLEM
→ STRONGER_DIRECT_REASONING

HARD_POINT_PLUS_CHEAP_BOUNDED_WORK
→ STRONG_ROOT_FOR_HARD_POINT
→ DELEGATE_CHEAP_BOUNDED_WORK
→ ROOT_RECONCILES
```

## 7.1. Escolha do orquestrador vem antes dos subagentes

Antes de selecionar subagentes, determine a inteligência necessária para o root.

O root deve ser capaz de:

- manter estado e authorities;
- identificar hotspots cognitivos;
- decompor e contratar trabalho;
- arbitrar evidência;
- revisar quando sua própria capacidade for suficiente;
- decidir escalation/de-escalation;
- emitir o veredicto final.

```text
ROOT_INTELLIGENCE_IS_PART_OF_ROUTING_DECISION = YES
```

O root **não precisa executar pessoalmente** todo trabalho que seja capaz de fazer.

## 7.2. Baseline do orquestrador

No ambiente GPT-6, não existe um único ROOT universal. O baseline deve seguir a demanda
cognitiva remanescente e separar capability de deliberation.

```text
SIMPLE_ORCHESTRATION
→ LUNA / MEDIUM

BOUNDED_REASONING_ROOT
→ LUNA / HIGH

DEEP_BUT_CLEARLY_BOUNDED_ROOT
→ LUNA / XHIGH

NORMAL_TECHNICAL_ROOT
→ SOL / MEDIUM

HIGH_JUDGMENT_ROOT
→ SOL / HIGH
```

Esses valores são baselines operacionais, não pisos nem tetos.

A seleção deve seguir a policy de prompts vigente:

```text
MODEL_FAMILY
← CAPABILITY_DEMAND

REASONING_EFFORT
← DELIBERATION_DEMAND
```

Consequentemente:

```text
LUNA_XHIGH_ROOT = ALLOWED
LUNA_XHIGH_ROOT_REQUIRES_LUNA_CAPABILITY_SUFFICIENT = YES
LUNA_XHIGH_MUST_NOT_MASK_CAPABILITY_GAP = YES

SOL_MEDIUM = NORMAL_TECHNICAL_BASELINE
SOL_HIGH = HIGH_JUDGMENT_BASELINE
ASTRA = EXCEPTIONAL_ESCALATION_MODEL
```

> O orquestrador deve ser o menor modelo/effort que coordene, adjudique e conclua a
> atividade com confiabilidade suficiente. ROOT é papel de responsabilidade; não é
> sinônimo de modelo forte.

## 7.3. Faixa operacional dos agentes Luna

GPT-6 Luna pode atuar tanto como ROOT quanto como subagente. O effort é escolhido pela
demanda de deliberação, não por um piso artificial de High.

```text
LUNA_LOW = SIMPLE_MECHANICAL_OR_FACTUAL
LUNA_MEDIUM = NORMAL_BOUNDED_ORCHESTRATION_OR_EXECUTION
LUNA_HIGH = SUBSTANTIAL_BOUNDED_REASONING
LUNA_XHIGH = DEEP_OR_LONG_DELIBERATION_WHILE_LUNA_CAPABILITY_REMAINS_SUFFICIENT
```

Aplicar:

```text
LUNA_XHIGH_ROOT = VALID
LUNA_XHIGH_SUBAGENT = VALID
LUNA_XHIGH_MUST_NOT_BE_USED_TO_COMPENSATE_FOR_CAPABILITY_GAP = YES
```

`Luna / XHigh` é especialmente elegível quando a tarefa exige investigação longa,
reconciliação extensa ou raciocínio sustentado, mas continua bem delimitada, com
restrições claras e sem capability gap material.

## 7.4. Posicionamento dos tiers

```text
SIMPLE ORCHESTRATION / FACTUAL EXECUTION
→ LUNA / MEDIUM

BOUNDED IMPLEMENTATION OR VALIDATION
→ LUNA / MEDIUM OR HIGH BY DELIBERATION

DEEP BOUNDED ANALYSIS WITH CLEAR CONSTRAINTS
→ LUNA / XHIGH WHEN LUNA CAPABILITY REMAINS SUFFICIENT

NORMAL IMPLEMENTATION REQUIRING TECHNICAL JUDGMENT
→ SOL / MEDIUM

COMPLEX IMPLEMENTATION / HARD DEBUG / DEEP REVIEW
→ SOL / HIGH

VERY DEEP SOL-LEVEL REVIEW OR AUDIT
→ SOL / XHIGH WHEN MATERIALLY JUSTIFIED

MATERIAL ARCHITECTURAL DECISION
→ SOL / HIGH

SOL/HIGH INSUFFICIENT FOR MATERIAL ARCHITECTURAL DECISION
→ ROOT_RECLASSIFICATION_REPORT
→ STOP_AT_SAFE_BOUNDARY
→ USER RECONFIGURES ROOT
→ ASTRA / MEDIUM
```

Astra é escalonamento excepcional. Para arquitetura, o caminho normativo é
`Sol/High → Astra/Medium` quando Sol/High declarar insuficiência objetiva.

```text
ASTRA_HIGH
→ only if ASTRA_MEDIUM is insufficient

ASTRA_XHIGH
→ only if ASTRA_HIGH is insufficient

ASTRA_MAX
→ only if ASTRA_XHIGH is insufficient

MAX_EFFORT_DEFAULT = PROHIBITED
```

## 7.5. Fatores de roteamento

A escolha deve considerar:

```text
AMBIGUITY
COGNITIVE_COMPLEXITY
IMPACT
REVERSIBILITY
VERIFIABILITY
NOVELTY
FAILURE_HISTORY
SECURITY_SENSITIVITY
CONTEXT_DEPTH
MECHANICALITY
CONTRACT_CLOSURE
OBJECTIVE_TESTABILITY
ROOT_CURRENT_CAPABILITY
```

## 7.6. Hotspots cognitivos

Antes de manter um modelo caro em toda a tarefa, identifique:

```text
WHERE_DOES_HIGHER_INTELLIGENCE_CHANGE_SUCCESS_PROBABILITY?
```

Se apenas parte da tarefa exige tier alto:

```text
IDENTIFY_HARD_POINT
→ USE_STRONG_MODEL
→ CLOSE_DECISION_AND_INVARIANTS
→ FREEZE_BOUNDED_EXECUTION_CONTRACT
→ DELEGATE_TO_LOWER_TIER
→ VALIDATE_CHEAPLY
→ RETURN_TO_ROOT_FOR_ADJUDICATION
```

## 7.7. Regra de redundância de inteligência cara

```text
DO_NOT_DUPLICATE_EXPENSIVE_INTELLIGENCE_WITHOUT_DISTINCT_VALUE = YES
```

Exemplo normalmente inadequado:

```text
SOL/HIGH ROOT
+ SOL/HIGH IMPLEMENTER
+ SOL/HIGH REVIEWER
```

sobre o mesmo contexto e sem independência exigida.

Antes de spawn de `reviewer` ou outro tier caro, verificar se o root já cobre
a necessidade.

## 7.8. Escalonamento, reclassificação e de-escalation

Distinguir:

```text
INITIAL_ROUTING_SELECTION
!=
MID_TASK_ROUTING_RECLASSIFICATION
```

A policy pode recomendar um ROOT mais forte. Isso não significa que o executor
possa reconfigurar autonomamente seu próprio runtime.

```text
ROUTING_RECOMMENDATION
!=
RUNTIME_RECONFIGURATION

IN_EXECUTION_ROOT_AUTO_ESCALATION = PROHIBITED
MODEL_CHANGE = USER_CONTROLLED
EFFORT_CHANGE = USER_CONTROLLED
EXECUTION_MODE_CHANGE = USER_CONTROLLED
```

### 7.8.1 Detecção de insuficiência do ROOT

```text
DELIBERATION_GAP
→ RECOMMEND_HIGHER_EFFORT_WITHIN_SUFFICIENT_MODEL_FAMILY

CAPABILITY_GAP
→ RECOMMEND_STRONGER_MODEL
```

Para decisão arquitetural material:

```text
CURRENT_ROOT = SOL / HIGH
AND SOL_HIGH_CONFIDENCE = INSUFFICIENT
→ RECOMMEND ASTRA / MEDIUM
→ ROOT_RECLASSIFICATION_REQUIRED = YES
```

O `ROOT_RECLASSIFICATION_REPORT` deve registrar, quando aplicável:

```text
ALTERNATIVES_CONSIDERED =
DECISION_IMPACT =
```

Não inserir `Sol / XHigh` como degrau obrigatório entre `Sol / High` e
`Astra / Medium` para arquitetura. `Sol / XHigh` continua elegível em revisão,
auditoria ou análise longa quando não há capability gap.

Não usar como justificativa isolada:

```text
HIGH_IMPACT
MANY_FILES
LARGE_CODE_VOLUME
LONG_ACTIVITY
MANY_TESTS
MECHANICAL_IMPLEMENTATION
LARGE_DOCUMENTATION_DELTA
COMMON_TEST_FAILURE
ROUTINE_API_WIRING
READ_MODEL_CREATION
REPETITIVE_WORK
```

```text
MECHANICAL_SCALE
!=
COGNITIVE_COMPLEXITY
```

Se o ROOT atual for insuficiente e a responsabilidade continuar única:

```text
ROOT_RECLASSIFICATION_REQUIRED = YES
STOP_AT_SAFE_BOUNDARY = YES
EXECUTION_STATE = WAITING_FOR_USER_ROOT_RECONFIGURATION
```

O agente deve emitir `ROOT_RECLASSIFICATION_REPORT`, solicitar mudança manual do
modelo/effort e aguardar confirmação.

Enquanto aguarda, não pode:

- decidir o hotspot pendente;
- alegar mudança de modelo/effort;
- criar subagente forte para contornar o ROOT insuficiente;
- converter DIRECT em MULTIAGENT silenciosamente.

### 7.8.2 Retomada

Depois da confirmação do usuário:

```text
IF RUNTIME_EXPOSES_CURRENT_ROOT = YES
→ VERIFY_MODEL_AND_EFFORT

ELSE
→ ROOT_PROFILE_STATE = USER_CONFIRMED_RUNTIME_UNVERIFIED
```

Retomar do `SAFE_RESUME_POINT`.

Não repetir trabalho já válido sem evidência de staleness.

### 7.8.3 De-escalation

Depois que o ponto difícil for resolvido:

- o ROOT pode permanecer no perfil atual se o trabalho remanescente for pequeno;
- delegação de materialização barata pode ocorrer sem mudar o ROOT, se economicamente justificada;
- mudança manual para ROOT mais barato só deve ser recomendada quando a economia líquida for material.

```text
CURRENT_ROOT_IS_STILL_SUFFICIENT = YES
AND REMAINING_WORK = SMALL
→ CONTINUE_CURRENT_ROOT
```

Não criar interrupção ritual de de-escalation.

## 7.9. Pipeline sequencial multiagente

Multiagente não exige simultaneidade.

Pipeline recomendado quando economicamente vantajoso:

```text
STRONG ROOT
→ closes reasoning / constraints / invariants
→ CHEAP MECHANICAL IMPLEMENTER
→ CHEAP VALIDATOR
→ TRIAGE ONLY ON FAILURE
→ STRONG ROOT SELF-REVIEW / FINAL ADJUDICATION
```

Esse fluxo é válido quando o ganho econômico supera handoff e integração.

---

## 8. Registro operacional de subagentes e catálogo normativo de papéis

O catálogo nomeia responsabilidades funcionais. Configurações de perfil do runtime podem implementar esses papéis, mas não são obrigatórias nem provam quais capacidades estão disponíveis.

```text
ROLE_CATALOG_IS_FUNCTIONAL_GUIDANCE = YES
RUNTIME_PROFILE_REQUIRED = NO
ROLE_EXISTS != ROLE_MUST_BE_USED
ROLE_AVAILABLE != ROLE_NECESSARY
RUNTIME_PROFILE != GUARANTEED_TOOL_OR_MODEL_CAPABILITY
PROFILE_RELEVANT != MULTIAGENT_JUSTIFIED
```

## 8.1. Catálogo normativo de papéis

### SCOUT

```text
ROLE = SCOUT
MODEL_BINDING = RUNTIME_SELECTED_OR_INHERITED
EFFORT_BINDING = RUNTIME_SELECTED_OR_INHERITED
DESIRED_SANDBOX = READ_ONLY
```

Exploração factual: arquivos, símbolos, fluxos, dependências, configuração,
contratos e divergências. Não escreve nem decide arquitetura.

### RESEARCHER

```text
ROLE = RESEARCHER
MODEL_BINDING = RUNTIME_SELECTED_OR_INHERITED
EFFORT_BINDING = RUNTIME_SELECTED_OR_INHERITED
DESIRED_SANDBOX = READ_ONLY
```

Documentação oficial, APIs, versões, compatibilidade, breaking changes e pesquisa
externa autorizada. Não implementa.

### VALIDATOR

```text
ROLE = VALIDATOR
MODEL_BINDING = RUNTIME_SELECTED_OR_INHERITED
EFFORT_BINDING = RUNTIME_SELECTED_OR_INHERITED
DESIRED_SANDBOX = WORKSPACE_WRITE_WHEN_REQUIRED_FOR_VALIDATION
SOURCE_WRITE_AUTHORIZATION = NO
```

Responsável por:

- testes focais e suites;
- lint;
- type checking;
- build;
- collect-only;
- diff checks;
- checks objetivos;
- coleta factual de evidência.

Ferramentas de validação podem criar caches, bytecode, build outputs, coverage e
outros artefatos transitórios. Isso não autoriza alteração de código-fonte,
testes, configuração ou critérios de aceite.

```text
WRITE_CAPABILITY != SOURCE_WRITE_AUTHORIZATION
VALIDATOR != IMPLEMENTER
```

Falha deve retornar ao root ou a Triage; Validator não corrige automaticamente.

### TRIAGE_ANALYST

```text
ROLE = TRIAGE_ANALYST
MODEL_BINDING = RUNTIME_SELECTED_OR_INHERITED
EFFORT_BINDING = RUNTIME_SELECTED_OR_INHERITED
DESIRED_SANDBOX = READ_ONLY
```

Interpreta failure signatures, formula hipótese de root cause, estima escopo e
recomenda próxima ação. Não implementa.

### MECHANICAL_IMPLEMENTER

```text
ROLE_ID = mechanical_implementer
ROLE = MECHANICAL_IMPLEMENTER
MODEL_BINDING = RUNTIME_SELECTED_OR_INHERITED
EFFORT_BINDING = RUNTIME_SELECTED_OR_INHERITED
DESIRED_SANDBOX = WORKSPACE_WRITE
```

Usar quando:

```text
SOLUTION_IS_CLOSED = YES
SCOPE_IS_BOUNDED = YES
OWNERSHIP_IS_CLEAR = YES
IMPLEMENTATION_IS_MECHANICAL_OR_LOW_JUDGMENT = YES
OBJECTIVE_VALIDATION_EXISTS = YES
```

Responsabilidades:

- aplicar alteração prescrita;
- editar apenas ownership recebido;
- produzir o menor patch compatível com o contrato;
- preservar invariantes e decisões fechadas;
- reportar exatamente o que mudou.

Não pode:

- escolher nova arquitetura;
- resolver trade-off material;
- alterar requisito;
- reinterpretar contrato congelado;
- refatorar oportunisticamente;
- relaxar testes;
- executar Git consequencial sem autorização.

Se surgir decisão material:

```text
STOP_AFFECTED_SCOPE
RETURN_TO_ROOT
```

### IMPLEMENTER

```text
ROLE_ID = implementer
ROLE = IMPLEMENTER
MODEL_BINDING = RUNTIME_SELECTED_OR_INHERITED
EFFORT_BINDING = RUNTIME_SELECTED_OR_INHERITED
DESIRED_SANDBOX = WORKSPACE_WRITE
```

Usar quando a implementação está delimitada, mas ainda exige julgamento técnico
material, decisões locais não triviais ou integração que excede trabalho mecânico.

Quando a implementação for cognitivamente complexa:

```text
EFFORT_BINDING = RUNTIME_SELECTED_OR_INHERITED
```

sem ampliar authority.

### REVIEWER

```text
ROLE_ID = reviewer
ROLE = REVIEWER
MODEL_BINDING = RUNTIME_SELECTED_OR_INHERITED
EFFORT_BINDING = RUNTIME_SELECTED_OR_INHERITED
DESIRED_SANDBOX = READ_ONLY
```

Reviewer existe para **independência** ou **ganho material de revisão**.

Não usar apenas porque houve implementação.

Antes de spawn:

```text
ROOT_CAN_REVIEW_SUFFICIENTLY?
INDEPENDENCE_REQUIRED?
DISTINCT_REVIEW_VALUE?
```

Se root já for suficiente e independência não for exigida:

```text
REVIEW = ROOT_SELF_REVIEW
REVIEWER_SUBAGENT = NO
```

`Sol / XHigh` pode ser selecionado para review/auditoria excepcionalmente profundos
quando a demanda for de deliberação e o ganho for material.

### SECURITY_REVIEWER

```text
ROLE_ID = security_reviewer
ROLE = SECURITY_REVIEWER
MODEL_BINDING = RUNTIME_SELECTED_OR_INHERITED
EFFORT_BINDING = RUNTIME_SELECTED_OR_INHERITED
DESIRED_SANDBOX = READ_ONLY
```

Usar somente quando houver superfície material de segurança.

### ARCHITECT

```text
ROLE_ID = architect
ROLE = ARCHITECT
MODEL_BINDING = RUNTIME_SELECTED_OR_INHERITED
EFFORT_BINDING = RUNTIME_SELECTED_OR_INHERITED
DESIRED_SANDBOX = READ_ONLY
ARCHITECT != PERSISTENT_ORCHESTRATOR
MATERIAL_ARCHITECTURAL_DECISION_DEFAULT = SOL_HIGH
ASTRA_ESCALATION = EXPLICIT_ONLY
```

`architect` é o perfil técnico normal para **decisão arquitetural material**.
O simples fato de uma tarefa tocar documentação, artefatos ou conceitos de arquitetura
não seleciona automaticamente o perfil: deve existir decisão arquitetural material.

Se `Sol / High` concluir que sua confiança/capacidade é insuficiente para uma decisão
segura, deve emitir `ROOT_RECLASSIFICATION_REPORT`, parar em boundary seguro e
recomendar `Astra / Medium`. Astra não é spawn silencioso nem bypass do ROOT.

### SCRIBE

```text
ROLE = SCRIBE
MODEL_BINDING = RUNTIME_SELECTED_OR_INHERITED
EFFORT_BINDING = RUNTIME_SELECTED_OR_INHERITED
DEFAULT_WRITE_SCOPE = DOCUMENTATION_ONLY
```

```text
SCRIBE_DOES_NOT_CREATE_REALITY
SCRIBE_RECORDS_REALITY
```

Registra apenas fatos/evidências/decisões estabelecidas.

## 8.2. Catálogo funcional e vínculos de runtime

O papel descreve responsabilidade. Modelo, effort e ferramentas são resolvidos separadamente pelo runtime ou explicitamente configurados quando a superfície permite.

| Papel | Responsabilidade | Superfície necessária a verificar |
|---|---|---|
| SCOUT | exploração factual | leitura dos caminhos e arquivos pertinentes |
| RESEARCHER | pesquisa externa | web e documentação oficial disponível |
| VALIDATOR | verificações objetivas | comandos e ferramentas necessários aos checks |
| TRIAGE_ANALYST | diagnóstico de falha | logs e evidências relevantes, normalmente leitura |
| MECHANICAL_IMPLEMENTER | patch fechado e bounded | escrita apenas no ownership autorizado |
| IMPLEMENTER | implementação com julgamento local | ferramentas e escrita necessárias ao escopo |
| REVIEWER | revisão independente/material | acesso de leitura ao delta e às authorities |
| SECURITY_REVIEWER | análise de segurança material | ferramentas de leitura/análise requeridas |
| ARCHITECT | consulta arquitetural material | acesso às authorities e artefatos relevantes |
| SCRIBE | registro de fatos/decisões fechadas | escrita documental limitada ao ownership |

AGENT_ROLE != RUNTIME_SELECTED_MODEL
AGENT_ROLE != REASONING_EFFORT
AGENT_ROLE != TOOL_SURFACE

Rotas como ROOT Sol/High com MECHANICAL_IMPLEMENTER alvo Luna/High ou VALIDATOR alvo Luna/Medium são alvos de roteamento econômico, não garantias do runtime. Só classificar um fluxo como heterogêneo ou atribuir economia de tier quando modelo e effort por agente estiverem explicitamente configurados e confirmados pela superfície.

Papel disponível não obriga spawn. Um papel que não esteja pré-cadastrado na configuração do runtime pode ser solicitado como instrução funcional quando a superfície aceitar agentes com prompt livre, desde que a capacidade e as ferramentas necessárias sejam verificadas.

## 8.3. Compatibilidade

Aliases legados são identificadores de configuração, não evidência do modelo que o runtime executou. Quando ainda existirem configurações antigas, interpretar legacy_scout_alias, legacy_validator_or_triage_alias, legacy_implementer_alias, legacy_reviewer_alias e legacy_security_alias pela responsabilidade funcional configurada. Novos prompts usam os papéis funcionais da seção 8.2.

Não inferir modelo nem effort pelo nome histórico do perfil.

## 8.4. Gate de seleção do papel

Depois de justificar multiagente:

```text
1. QUAL GANHO MATERIAL JUSTIFICOU A DELEGAÇÃO?
2. QUAL INTELIGÊNCIA JÁ ESTÁ PRESENTE NO ROOT?
3. QUAL RESPONSABILIDADE PRECISA SER SEPARADA?
4. O TRABALHO É MECÂNICO OU EXIGE JULGAMENTO?
5. QUAL É O MENOR TIER SUFICIENTE?
6. O SANDBOX É COMPATÍVEL?
7. HÁ OVERLAP OU DUPLICAÇÃO DE INTELIGÊNCIA CARA?
8. O RETORNO É OBJETIVAMENTE RECONCILIÁVEL?
```

Mapeamento:

```text
REPOSITORY_EXPLORATION → SCOUT
EXTERNAL_RESEARCH → RESEARCHER
TEST_EXECUTION_OR_OBJECTIVE_CHECKS → VALIDATOR
FAILURE_ANALYSIS → TRIAGE_ANALYST
MECHANICAL_BOUNDED_IMPLEMENTATION → MECHANICAL_IMPLEMENTER
IMPLEMENTATION_REQUIRING_JUDGMENT → IMPLEMENTER
INDEPENDENT_TECHNICAL_REVIEW → REVIEWER
MATERIAL_SECURITY_REVIEW → SECURITY_REVIEWER
MATERIAL_ARCHITECTURAL_CONSULTATION → ARCHITECT
FACTUAL_DOCUMENTATION_UPDATE → SCRIBE
```

## 8.5. Concorrência e recursão

RUNTIME_CONCURRENCY_LIMIT = DISCOVERED_PER_SURFACE
TASK_CONCURRENCY_BUDGET = BOUNDED_TO_MATERIAL_WORK
CONCURRENT_WRITE_OVERLAP = PROHIBITED
PER_RESOURCE_WRITERS = GOVERNED_BY_NON_OVERLAPPING_OWNERSHIP
RECURSIVE_DELEGATION = DISABLED_BY_DEFAULT

Não codificar um número global de subagentes: limites e defaults variam por superfície, produto e configuração. Descobrir o limite efetivo no runtime e manter o orçamento da atividade dentro dele. Separar ownership por recurso e evitar writers simultâneos no mesmo estado mutável.

Delegação recursiva pode ser habilitada quando houver ganho material de paralelismo, a tarefa descendente for bounded, o ownership estiver claro, houver orçamento de concorrência efetivo e o runtime confirmar suporte à recursão. Essa permissão não expande o escopo autorizado nem exige aprovação humana por spawn isolado.

## 8.6. Superfícies de delegação

NATIVE_MULTIAGENT = ORCHESTRATION_RUNTIME = NATIVE

HETEROGENEOUS_MULTIAGENT = MODEL_TOPOLOGY = HETEROGENEOUS
NATIVE_MULTIAGENT AND HETEROGENEOUS_MULTIAGENT = COMPATIBLE_AXES

EXTERNAL = loop de orquestração fora do harness nativo
MANUAL = handoff controlado por usuário/operador

NATIVE_MULTIAGENT não implica seleção heterogênea, menor tier, economia ou permissões específicas. Os nomes dos papéis não são prova de modelo nem de ferramentas disponíveis.

TIER_SAVING_CLAIM = REQUIRES_ACTUAL_RUNTIME_MODEL_EVIDENCE
REGISTERED_ROLE != GUARANTEED_RUNTIME_CAPABILITY
BEFORE_DELEGATION = VERIFY_REQUIRED_TOOL_SURFACE

Se o runtime não expuser uma ferramenta necessária, dividir ou ajustar a tarefa para a superfície disponível, ou executá-la diretamente. Não delegar com base em capability presumida do papel.
Capability resolution deve preferencialmente acontecer em session/config/role resolution
e pode ser reutilizada enquanto runtime e configuração permanecerem estáveis.

```text
RUNTIME_CAPABILITY_RESOLUTION = SESSION_CONFIG_ROLE_RESOLUTION_PREFERRED
CAPABILITY_RESOLUTION_REUSE = ALLOWED_WHILE_RUNTIME_AND_CONFIGURATION_STABLE
RUNTIME_CAPABILITY_RESOLUTION != PER_SPAWN_HUMAN_GATE
UNKNOWN_CAPABILITY → DO_NOT_ASSUME
PROVIDER_DOCUMENTATION_DIVERGENCE → VERIFY_RUNTIME_AND_MODEL_CAPABILITY
```

## 9. Contrato proporcional de delegação

Cada delegação recebe contrato curto o bastante para execução e adjudicação seguras. Incluir objetivo, limite/ownership, authority relevante, ação permitida, retorno esperado e condição de parada que mudem o comportamento. Acrescentar modelo, effort ou tool surface apenas quando a superfície os expuser ou quando forem explicitamente configurados.

ROLE
OBJECTIVE
SCOPE_AND_OWNERSHIP
RELEVANT_AUTHORITIES
ALLOWED_ACTIONS
EXPECTED_RETURN
STOP_OR_ESCALATE_WHEN
RUNTIME_MODEL / EFFORT / TOOL_SURFACE = VERIFIED | INHERITED | UNKNOWN

O detalhe do contrato cresce com a materialidade e o risco da tarefa; estes campos não são uma lista ritual obrigatória quando irrelevantes. Manter limites de authority, Git e escrita consistentes com a tarefa. Validator não recebe autorização para alterar source por ter capacidade de escrita transitória.

RUNTIME_CAN_AUTODELEGATE
!=
GOVERNANCE_AUTHORIZATION_TO_AUTODELEGATE

IF EXECUTION_MODE = DIRECT
→ DO_NOT_DELEGATE_ONLY_BECAUSE_RUNTIME_CAN_AUTODELEGATE = YES

DIRECT_TO_MULTIAGENT = USER_CONTROLLED

IF EXECUTION_MODE = MULTIAGENT
AND USER_AUTHORIZATION_ALREADY_EXISTS = YES
AND DELEGATION_SCOPE_IS_BOUNDED = YES
AND DELEGATION_GATE = PASS
→ PER_SUBAGENT_USER_APPROVAL = NOT_REQUIRED_BY_DEFAULT

Somente o modo MULTIAGENT e o escopo já autorizados habilitam essa regra; capability
de autodelegação sozinha não altera `DIRECT`.

O contrato não transfere authority, não permite expansão de escopo e não exige que o subagente refaça raciocínio ou contexto já válido do root.

## 10. Responsabilidade do agente principal

O agente principal/orquestrador continua responsável por:

- interpretar a tarefa e authorities;
- escolher sua própria inteligência antes de selecionar subagentes;
- identificar hotspots cognitivos;
- decidir `DIRECT` ou `MULTIAGENT`;
- decidir entre root escalation, role delegation e independent review;
- selecionar o menor papel/tier suficiente;
- evitar duplicação de inteligência cara;
- fechar decisões antes de delegar execução mecânica;
- definir contratos;
- controlar dependências e ownership;
- reconciliar evidências;
- executar self-review quando sua capacidade for suficiente;
- validar o estado final;
- emitir o veredicto final.

```text
DELEGATION != ACCOUNTABILITY_TRANSFER
ROOT_CAN_DELEGATE_EXECUTION_WITHOUT_DELEGATING_DECISION_AUTHORITY
```

O root não deve se transformar em worker operacional apenas porque possui
capacidade para fazer todas as etapas.

---

## 11. Implementação: decisão por julgamento, não por capacidade bruta

A pergunta não é somente:

```text
CAN_ROOT_IMPLEMENT?
```

A pergunta correta é:

```text
DOES_IMPLEMENTATION_REQUIRE_ROOT_LEVEL_JUDGMENT?
```

### 11.1 Implementação direta pelo root

Preferir quando:

- patch é pequeno demais para justificar handoff;
- root já está no contexto completo e a delegação duplicaria leitura;
- implementação e raciocínio são fortemente acoplados;
- o custo de handoff supera economia de tier.

### 11.2 `mechanical_implementer` / Mechanical Implementer

Preferir quando:

```text
SOLUTION_IS_CLOSED = YES
CHANGE_BOUNDARY_IS_EXPLICIT = YES
LOW_JUDGMENT = YES
OBJECTIVE_VALIDATION = YES
EXPECTED_COST_SAVING = MATERIAL
```

Não é necessário haver paralelismo.

### 11.3 `implementer`

Preferir quando o writer precisa tomar decisões técnicas locais relevantes,
interpretar trade-offs, integrar componentes ou lidar com ambiguidade residual.

### 11.4 Regra econômica

```text
DO_NOT_USE_SOL_FOR_MECHANICAL_WRITING
WHEN_LUNA_CAN_EXECUTE_SAFELY_AND_VERIFY_OBJECTIVELY
```

Custo nunca supera risco; caso a fronteira mecânica não seja clara, mantenha ou
suba o tier.

### 11.5 Threshold de delegação entre tiers adjacentes

A capacidade de um tier inferior não basta para justificar handoff.

Exemplo especialmente relevante:

```text
ROOT = SOL / HIGH
CANDIDATE_IMPLEMENTER = SOL / MEDIUM
```

Delegar só é preferível quando:

```text
LOWER_TIER_IS_SUFFICIENT = YES
IMPLEMENTATION_VOLUME_IS_MATERIAL = YES
BOUNDARY_IS_CLEAR = YES
EXPECTED_TIER_SAVING_IS_MATERIAL = YES
AND
EXPECTED_TIER_SAVING
> HANDOFF_COST + DUPLICATED_CONTEXT_COST + INTEGRATION_COST
```

Se o root e o implementer precisarem reconstruir praticamente o mesmo contexto e o
patch for pequeno, prefira o root mesmo que o tier inferior seja tecnicamente capaz.

```text
ADJACENT_TIER_CAPABILITY != ADJACENT_TIER_DELEGATION_REQUIRED
HIGH_ROOT_TO_MEDIUM_IMPLEMENTER_REQUIRES_MATERIAL_NET_GAIN = YES
```

A mesma lógica vale para `Sol/Medium → Luna/High`: patch mecânico minúsculo pode
continuar direto quando o handoff custar mais que a economia de execução.

---

## 12. Política de paralelismo

Paralelize somente frentes independentes quando o ganho material cobrir coordenação, contexto duplicado e integração. Não paralelize etapas dependentes, alterações sobre o mesmo estado mutável ou leituras repetidas do mesmo contexto sem valor independente. Defina ownership por recurso antes de escrita concorrente.

CONCURRENT_WRITE_OVERLAP = PROHIBITED
RUNTIME_CONCURRENCY_LIMIT = DISCOVERED_PER_SURFACE
TASK_CONCURRENCY_BUDGET = CONFIGURABLE_WITHIN_RUNTIME_LIMIT

Os limites publicados por uma superfície são fatos de runtime sujeitos a mudança, não constantes desta política. O root ajusta ou serializa o plano conforme o limite efetivo e o escopo já autorizado.

## 13. Economia de contexto

Evite replicar o mesmo conjunto grande de arquivos ou documentos para vários
agentes.

Multiagente perde valor quando:

```text
DUPLICATED_CONTEXT_COST
>=
PARALLELISM_OR_SPECIALIZATION_GAIN
```

Prefira:

- uma única leitura pelo principal quando o contexto é altamente compartilhado;
- partições por responsabilidade quando os dados são realmente separáveis;
- retornos compactos com evidência suficiente para adjudicação.

---

## 14. Contrato de retorno dos subagentes

O retorno deve ser proporcional ao objetivo.

Para investigação/review, prefira estrutura compacta:

```text
finding_id
severity
source / file:line
fact
inference
contract_or_invariant
impact
recommendation
confidence
```

Para implementação:

```text
scope_completed
files_changed
validation_executed
known_limitations
blockers
unresolved_decisions
```

Evite relatórios narrativos extensos quando não agregarem informação material.

---

## 15. Revisão adaptativa e capacidade do root

### 15.1 Self-review é o padrão quando o root é suficiente

```text
PRIMARY_ANALYSIS
CONSISTENCY_CHECK
ADVERSARIAL_SELF_REVIEW
FINAL_SELF_REVIEW
```

Self-review não é revisão independente.

### 15.2 Reviewer não deve duplicar o root

Antes de criar `reviewer`:

```text
ROOT_REVIEW_CAPABILITY_SUFFICIENT = YES | NO
INDEPENDENCE_REQUIRED = YES | NO
DISTINCT_REVIEW_VALUE = YES | NO
```

Se:

```text
ROOT_REVIEW_CAPABILITY_SUFFICIENT = YES
INDEPENDENCE_REQUIRED = NO
DISTINCT_REVIEW_VALUE = NO
```

então:

```text
INDEPENDENT_REVIEWER = NO
REVIEW = ROOT_SELF_REVIEW
```

Exemplo típico:

```text
ROOT = SOL / HIGH
REVIEW_REQUIREMENT <= SOL / HIGH
INDEPENDENCE_REQUIRED = NO
→ DO_NOT_SPAWN_SOL_HIGH_REVIEWER
```

### 15.3 Quando a revisão exigir inteligência maior, mas não independência

Preferir comparar:

```text
TEMPORARY_ROOT_ESCALATION
vs
SEPARATE_REVIEWER
```

Se apenas mais inteligência for necessária e não houver valor em responsabilidade
separada:

```text
PREFER_TEMPORARY_ROOT_ESCALATION_WHEN_CHEAPER_AND_SAFE
```

### 15.4 Quando reviewer independente é correto

Usar quando:

- governance exige independência;
- conflito de interesse cognitivo/ownership torna self-review insuficiente;
- uma segunda leitura independente reduz materialmente risco;
- o root não cobre a disciplina necessária e separar o review é mais eficiente que
  reconfigurar o root.

### 15.5 Escrita após review independente

Se independência fizer parte do gate, escrita posterior no escopo aprovado invalida
a aprovação desse escopo:

```text
FIX
→ VALIDATE
→ INDEPENDENT_REVIEW_AGAIN
```

---

## 16. Segurança

Revisão de segurança é ortogonal à revisão técnica geral.

Use `security_reviewer` somente quando existir superfície
material, como:

- autenticação/autorização;
- secrets;
- trust boundaries;
- filesystem sensível;
- execução de comandos;
- deserialização/parser de entrada não confiável;
- criptografia;
- exposição de rede;
- permissões/ACL;
- mudança de release com impacto relevante de segurança.

Uma tarefa ser “importante” não torna automaticamente necessário um agente de
segurança.

---

## 17. Conflitos e adjudicação

Subagente de adjudicação só deve ser considerado após existir conflito material
real.

```text
NO_CONFLICT = NO_ADJUDICATION_AGENT
```

Quando houver conflito não resolvível pelas authorities existentes ou pelo
agente principal dentro de sua responsabilidade:

```text
STOP_AT_SAFE_BOUNDARY = YES
AUTO_ESCALATION = NO
REPORT_EVIDENCE = YES
RETURN_TO_USER = YES
```

Não criar cadeia automática de reviewers ou arquitetos.

---

## 18. Skills, Plugins e multiagente

As decisões são independentes:

```text
MODEL
EFFORT
EXECUTION_MODE
SKILL
PLUGIN
```

Aplicar:

```text
SKILL_REQUIRED != SUBAGENT_REQUIRED
PLUGIN_REQUIRED != SUBAGENT_REQUIRED
SUBAGENT_REQUIRED != SKILL_REQUIRED
SUBAGENT_REQUIRED != PLUGIN_REQUIRED
```

Uma Skill ou Plugin pode ser usado pelo agente principal em modo direto.

Uma arquitetura multiagente não justifica uso adicional de Skills ou Plugins
sem benefício material próprio.

---

## 19. Read-only, write capability e limites de escrita

Separar três conceitos:

```text
GOVERNANCE_READ_ONLY
SOURCE_WRITE_AUTHORIZATION
TECHNICAL_WORKSPACE_WRITE_CAPABILITY
```

Eles não são equivalentes.

### 19.1 Atividade estritamente read-only

Se nenhuma escrita persistente ou transitória no workspace for autorizada:

```text
GOVERNANCE_READ_ONLY = YES
SUBAGENT_WRITE_PERMISSION = NO
```

Isso se aplica a todos os agentes.

### 19.2 Validação que exige artefatos transitórios

Alguns comandos de teste/build criam caches, bytecode, coverage ou outputs mesmo
quando a atividade não autoriza editar source.

Nesse caso pode ser permitido:

```text
TECHNICAL_WORKSPACE_WRITE_CAPABILITY = YES
SOURCE_WRITE_AUTHORIZATION = NO
```

Isso **não** transforma Validator em writer de código.

Se a validação produzir alteração persistente inesperada em source, tests,
configuração ou documentação governada:

```text
STOP
REPORT_UNEXPECTED_WORKSPACE_CHANGE
DO_NOT_SELF_REPAIR
```

### 19.3 Escrita de implementação/documentação

Quando source/doc write estiver autorizado:

```text
OWNERSHIP_REQUIRED = YES
PER_RESOURCE_WRITERS = GOVERNED_BY_NON_OVERLAPPING_OWNERSHIP
CONCURRENT_WRITE_OVERLAP = PROHIBITED
```

A delegação nunca amplia authority de escrita além do contrato recebido.

---

## 20. Git e operações consequenciais

Nenhum modo de execução autoriza por si só:

```text
GIT_STAGE
COMMIT
PUSH
TAG
RELEASE
DEPLOY
LIVE_EXECUTION
```

Essas operações dependem da autorização específica do projeto/usuário.

```text
MULTIAGENT_PASS != GIT_AUTHORIZATION
DIRECT_PASS != GIT_AUTHORIZATION
```

---

## 21. Early exit

Se um blocker inequívoco determinar que o gate necessariamente falhará:

1. registre evidência suficiente para caracterizar o blocker;
2. conclua apenas validações ainda necessárias para delimitar o estado;
3. evite gasto em findings de baixo valor que não alterariam a decisão;
4. pare em boundary seguro;
5. retorne ao agente principal/usuário conforme authority.

Não use early exit quando investigação adicional for necessária para delimitar
impacto ou preservar segurança.

---

## 22. Fluxo operacional recomendado

### 22.1 Seleção inicial

1. identificar authorities materiais;
2. escolher o menor modelo e effort suficiente conforme PM-02;
3. manter DIRECT como padrão;
4. escolher MULTIAGENT somente após ganho líquido material e escopo claro;
5. verificar antes do spawn a superfície de ferramentas exigida pela tarefa;
6. definir ownership sem sobreposição de escrita;
7. limitar a delegação à autorização existente;
8. reconciliar os retornos e manter responsabilidade final no root.

A seleção do modo é uma decisão do usuário ou do contrato da atividade. Depois que MULTIAGENT e o escopo já estiverem autorizados e o gate passar, o root pode criar subagentes bounded sem pedir aprovação individual por spawn.

### 22.2 Reclassificação durante execução

Se a atividade começou em DIRECT e surgir uma responsabilidade separável que torne MULTIAGENT materialmente superior:

APPLY G1..G6 AND OFFLOAD_MATERIALITY_GATE
→ REPORT PROPOSED SCOPE / OWNERSHIP / NET GAIN
→ STOP AT SAFE BOUNDARY
→ WAIT FOR USER AUTHORIZATION TO CHANGE DIRECT TO MULTIAGENT

Sem essa autorização, continuar diretamente se seguro ou aguardar. Não trocar o modo silenciosamente. Mudança de modelo/effort do root também segue a fronteira de reconfiguração definida em PM-02.

Se a autorização MULTIAGENT já cobre a nova frente e o escopo não muda, esse procedimento de reclassificação não se aplica; seguir o gate normal de delegação.

## 23. Decision matrix

| Situação | Modo / papel recomendado |
|---|---|
| Tarefa pequena/local | `DIRECT` |
| Tarefa longa, porém cognitivamente monolítica | `DIRECT`, aumentar root se necessário |
| Root forte + muito trabalho mecânico verificável | `MULTIAGENT` sequencial por ganho econômico |
| Sol/High fecha solução; patch é prescritivo | `mechanical_implementer` / Mechanical Implementer |
| Testes, lint, collect-only, build, diff checks | `validator` quando offload for material |
| Falha de validação ambígua exige diagnóstico separado | `triage_analyst` quando houver ganho material |
| Falha localizada e praticamente autoexplicativa | root corrige diretamente se handoff não pagar |
| Implementação exige julgamento técnico | `implementer` se o handoff trouxer ganho líquido; caso contrário root implementa |
| Root Sol/High já cobre review e independência não é exigida | self-review do root; sem `reviewer` |
| Governance exige review independente | `reviewer` |
| Apenas mais deliberação é necessária e Luna continua suficiente | aumentar effort de Luna, inclusive `Luna/XHigh` quando apropriado |
| Capability gap real | reclassificar ROOT para Sol antes de criar papel redundante |
| Segurança material | `security_reviewer` quando separação agrega valor |
| Decisão arquitetural material | `Sol/High`; se insuficiente, STOP + `ROOT_RECLASSIFICATION_REPORT` + recomendar `Astra/Medium` |
| Duas frentes read-only independentes | `MULTIAGENT`, mínimo necessário |
| Benefício de delegação incerto | `DIRECT` |
| Todos releriam o mesmo contexto extenso | `DIRECT` |
| Dois writers sobre o mesmo estado | proibido |

---

## 24. Anti-patterns proibidos

SPAWN_SUBAGENT_BECAUSE_TASK_IS_COMPLEX = PROHIBITED
SPAWN_SUBAGENT_BECAUSE_ROLE_EXISTS = PROHIBITED
SPAWN_MULTIPLE_AGENTS_FOR_SAME_ANALYSIS = PROHIBITED
DELEGATE_WITHOUT_MATERIAL_NET_GAIN = PROHIBITED
RELY_ON_UNVERIFIED_RUNTIME_PROFILE_CAPABILITY = PROHIBITED
CLAIM_TIER_SAVING_WITHOUT_RUNTIME_EVIDENCE = PROHIBITED
INFER_MODEL_OR_TOOL_ACCESS_FROM_ROLE_NAME = PROHIBITED

ROOT_CAN_DO_IT_THEREFORE_ROOT_MUST_DO_ALL = PROHIBITED
IGNORE_ECONOMIC_GAIN_WHEN_MATERIAL = PROHIBITED
DUPLICATE_EXPENSIVE_INTELLIGENCE_WITHOUT_DISTINCT_VALUE = PROHIBITED
SPAWN_REVIEWER_OR_TRIAGE_AS_RITUAL = PROHIBITED
VALIDATOR_AUTO_FIXES_WITHOUT_AUTHORIZED_ROUTE = PROHIBITED

IN_EXECUTION_ROOT_AUTO_ESCALATION = PROHIBITED
MID_TASK_AUTO_MULTIAGENT_SWITCH = PROHIBITED
SPAWN_STRONGER_AGENT_TO_BYPASS_ROOT_RECLASSIFICATION = PROHIBITED
USE_MECHANICAL_SCALE_AS_COGNITIVE_ESCALATION_REASON = PROHIBITED
USE_ASTRA_AS_PERSISTENT_ORCHESTRATOR_BY_DEFAULT = PROHIBITED
OVERPROVISION_EFFORT_WITHOUT_DELIBERATION_NEED = PROHIBITED

USE_SUBAGENT_AS_AUTHORITY = PROHIBITED
EXPAND_AUTHORIZED_SCOPE_THROUGH_DELEGATION = PROHIBITED
CONCURRENT_WRITE_OVERLAP = PROHIBITED
MULTIAGENT_AS_STATUS_SYMBOL = PROHIBITED
UNBOUNDED_RECURSIVE_DELEGATION = PROHIBITED

Depois que o modo MULTIAGENT e seu escopo estiverem autorizados, o root pode criar subagentes bounded que passem o delegation gate sem confirmação humana por spawn individual. A transição de DIRECT para MULTIAGENT durante a execução permanece sob controle do usuário.

## 25. Cenários de conformidade de roteamento

Os cenários desta seção são **vetores de conformidade**, não receitas rígidas.
Eles registram decisões que a política deve conseguir reproduzir por raciocínio
econômico e de autoridade. Mudanças materiais no contexto podem alterar a rota.

```text
CONFORMANCE_SCENARIO != HARD_CODED_ROUTING_RECIPE
```

### Cenário A — patch trivial e localizado

Características:

- causa e solução fechadas;
- poucas linhas;
- contexto pequeno;
- teste focal objetivo;
- sem independência ou especialização.

Rota de referência validada:

```text
ROOT = LUNA / MEDIUM
MATERIAL_INTELLIGENCE_ROUTING_GAIN = NO
EXECUTION_MODE = DIRECT
SUBAGENTS_PLANNED = 0
```

Razão: Luna é suficiente e o volume não amortiza contrato, handoff e reconciliação.

### Cenário B — hotspot cognitivo + escrita mecânica + validação extensa

Características:

- decisão matemática/financeira sensível;
- solução fechada por root técnico;
- patch posterior prescritivo em vários arquivos;
- validação objetiva e volumosa.

Rota de referência validada:

```text
SOL/HIGH ROOT
→ LUNA/HIGH MECHANICAL_IMPLEMENTER
→ LUNA/MEDIUM OR HIGH VALIDATOR
→ SOL/HIGH ROOT SELF_REVIEW + FINAL ADJUDICATION
```

Não usar `reviewer` sem independência; Triage somente em falha ambígua real.

### Cenário C — implementação bounded, mas com julgamento técnico local

Características:

- arquitetura e comportamento fechados;
- implementação exige concorrência/atomicidade/integração e decisões locais;
- volume suficiente para amortizar handoff;
- validação objetiva posterior.

Rota de referência validada:

```text
SOL/HIGH ROOT
→ SOL/MEDIUM IMPLEMENTER
→ LUNA/MEDIUM OR HIGH VALIDATOR
→ SOL/HIGH ROOT SELF_REVIEW
```

Essa rota só é preferível quando a economia de tier supera duplicated context,
handoff e integração. Em patch menor, `SOL/HIGH ROOT → DIRECT IMPLEMENTATION` pode
ser a rota economicamente correta.

### Cenário D — revisão independente obrigatória

Características:

- root forte;
- implementação concluída;
- governança exige independência;
- reviewer read-only.

Rota de referência validada:

```text
SOL/HIGH ROOT
→ SOL/HIGH INDEPENDENT REVIEWER
→ SOL/HIGH ROOT FINAL ADJUDICATION
```

A duplicação de tier é justificada por `INDEPENDENCE_VALUE`, não por incapacidade do root.

### Cenário E — falha de validação localizada e autoexplicativa

Características:

- contrato inequívoco;
- failure signature aponta diretamente para violação localizada;
- patch remanescente é mínimo;
- sem ambiguidade diagnóstica.

Rota de referência validada:

```text
ROOT = LUNA / HIGH OR SOL / MEDIUM BY CAPABILITY
EXECUTION_MODE = DIRECT
TRIAGE = NO
NEW_HANDOFF_TO_MECHANICAL_IMPLEMENTER = NO
ROOT → REPAIR → FOCUSED_VALIDATION → SELF_REVIEW
```

Se a inspeção contradisser a hipótese evidente ou surgir falha nova/ambígua, o
roteamento deve ser reavaliado; `TEST_FAIL != TRIAGE_REQUIRED`.

### Cenário F — longa investigação bounded com alta deliberação

Características:

- restrições e authority claras;
- contexto extenso;
- muitas evidências para reconciliar;
- nenhuma decisão arquitetural material;
- Luna continua capability-sufficient.

Rota de referência:

```text
ROOT = LUNA / XHIGH
EXECUTION_MODE = DIRECT
```

`Luna/XHigh` é preferível a subir de família quando o gap é de deliberação, não de capability.

### Cenário G — decisão arquitetural material excede Sol/High

```text
ROOT = SOL / HIGH
SOL_HIGH_CONFIDENCE = INSUFFICIENT
→ ROOT_RECLASSIFICATION_REPORT
→ STOP_AT_SAFE_BOUNDARY
→ USER RECONFIGURES ROOT
→ ASTRA / MEDIUM
```

Astra High/XHigh/Max somente após insuficiência demonstrada do nível anterior.

### 25.1 Estado de validação desta candidata

Os cenários A–G foram reescritos para refletir o novo roteamento GPT-6 e foram promovidos
com esta authority; a bateria formal de conformidade não foi executada nesta atividade.

```text
ROUTING_CONFORMANCE_TESTS = NOT_RUN_AS_FORMAL_BATTERY
CANONICAL_VALIDATION = POST_PROMOTION_STATIC_PASS
PREVIOUS_R2_2_VALIDATION_RESULTS = HISTORICAL_ONLY
```

O agente de governança deve decidir se executa novamente a bateria de conformidade antes
de canonizar a revisão.

---

## 26. Telemetria opcional para calibração

Quando fizer sentido e sem burocracia excessiva, registrar:

- `DIRECT` ou `MULTIAGENT`;
- root model/effort;
- motivo do root tier;
- gates ativados, inclusive `MATERIAL_INTELLIGENCE_ROUTING_GAIN`;
- papéis/tier usados;
- quantidade de subagentes;
- quantidade de handoffs;
- tempo aproximado;
- retries;
- escalations/de-escalations;
- conflitos de integração;
- se houve duplicação de contexto;
- se trabalho de tier caro foi efetivamente evitado;
- se a delegação produziu ganho real.

A telemetria existe para calibrar a política, não para justificar retroativamente
uma decisão ruim.

---

## 27. Regra de reavaliação durante a execução

Uma atividade pode revelar posteriormente dois tipos diferentes de mudança.

### 27.1 ROOT atual deixou de ser suficiente

Se a responsabilidade continua única:

```text
MORE_INTELLIGENCE
WITHOUT SEPARATE RESPONSIBILITY
=
ROOT_RECLASSIFICATION_RECOMMENDATION
```

Aplicar:

```text
ROOT_RECLASSIFICATION_REQUIRED = YES
STOP_AT_SAFE_BOUNDARY = YES
REQUEST_USER_ROOT_RECONFIGURATION = YES
WAIT_FOR_USER_CONFIRMATION = YES
```

O relatório deve conter:

```text
CURRENT_ROOT
RECOMMENDED_ROOT
TRIGGER
WHY_CURRENT_ROOT_IS_INSUFFICIENT
WHY_HIGHER_EFFORT_IS_OR_IS_NOT_SUFFICIENT
WHY_THIS_IS_NOT_MULTIAGENT
DECISION_PENDING
WORK_ALREADY_COMPLETED
REMAINING_WORK
SAFE_RESUME_POINT
USER_ACTION_REQUIRED
EXECUTION_STATE
```

Não usar subagente como substituto clandestino de mudança do ROOT.

### 27.2 Surgiu responsabilidade separável

Uma tarefa iniciada `DIRECT` pode revelar:

- frente independente;
- necessidade de especialização distinta;
- volume mecânico material separável;
- requisito novo de independência;
- outro trigger G1–G6 material.

```text
SEPARATE_RESPONSIBILITIES
WITH MATERIAL NET GAIN
=
MULTIAGENT_RECLASSIFICATION_RECOMMENDATION
```

Registrar:

```text
NEW_MULTIAGENT_TRIGGER =
EXPECTED_GAIN =
SCOPE_OF_DELEGATION =
ROOT_CURRENT_MODEL =
ROOT_CURRENT_EFFORT =
WHY_NOT_ROOT =
SELECTED_ROLE =
SELECTED_TIER =
G1 =
G2 =
G3 =
G4 =
G5 =
G6 =
OFFLOAD_MATERIALITY_GATE =
```

Se os gates passarem:

```text
MULTIAGENT_RECLASSIFICATION_REQUIRED = YES
MID_TASK_AUTO_MULTIAGENT_SWITCH = PROHIBITED
STOP_AT_SAFE_BOUNDARY = YES
WAIT_FOR_USER_MULTIAGENT_AUTHORIZATION = YES
```

### 27.3 Perda de justificativa multiagente

```text
MULTIAGENT_JUSTIFICATION_LOST
→ DO_NOT_SPAWN_ADDITIONAL_AGENTS
→ CONSOLIDATE_TO_DIRECT_WHEN_SAFE
```

Isso não autoriza mudança silenciosa de perfil do ROOT.

### 27.4 De-escalation econômica

```text
CURRENT_ROOT_IS_STILL_SUFFICIENT = YES
AND REMAINING_WORK = SMALL
→ CONTINUE_CURRENT_ROOT
```

Só recomendar mudança manual de ROOT se a economia líquida for material.

---

## 28. Checklist final antes de criar subagente

```text
1. Qual é o modelo/esforço atual do root?
2. Qual parte realmente exige essa inteligência?
3. O root já cobre suficientemente o papel proposto?
4. Existe independência obrigatória?
5. Existe especialização distinta material?
6. Existe ganho material de decomposição?
7. Existe ganho material de roteamento de inteligência?
8. O trabalho delegado é bounded e verificável?
9. O menor tier suficiente foi escolhido?
10. O handoff economiza mais do que custa?
11. Existe perfil registrado compatível?
12. O sandbox é compatível?
13. Há overlap de escrita ou contexto?
14. O retorno pode ser reconciliado objetivamente?
15. O problema exige mais inteligência ou responsabilidade separada?
16. Se exige mais inteligência apenas, isso requer `ROOT_RECLASSIFICATION` em vez de subagente?
17. Estamos duplicando inteligência cara sem valor distinto?
18. Existe mais de uma rota tecnicamente válida?
19. Entre as rotas válidas, qual minimiza EXPECTED_COST_PER_SUCCESSFUL_TASK?
20. Delegação para tier adjacente ainda compensa após duplicated context e integração?
21. Uma failure é realmente ambígua o suficiente para justificar Triage?
22. A mudança proposta é inicial ou mid-task?
23. Se mid-task, existe confirmação explícita do usuário para mudar execution mode?
```

Se não houver ganho claro:

```text
EXECUTION_MODE = DIRECT
SUBAGENTS_ALLOWED = NO
```

---

## 28.1 Registro operacional proposto

FUNCTIONAL_ROLES = SCOUT | RESEARCHER | VALIDATOR | TRIAGE_ANALYST | MECHANICAL_IMPLEMENTER | IMPLEMENTER | REVIEWER | SECURITY_REVIEWER | ARCHITECT | SCRIBE
ROLE_CATALOG = GUIDANCE; DOES_NOT_GUARANTEE_RUNTIME_CAPABILITY
RUNTIME_MODEL_AND_EFFORT = EXPLICITLY_CONFIGURED_OR_INHERITED
RUNTIME_TOOL_SURFACE = VERIFY_BEFORE_DELEGATION
ORCHESTRATION_RUNTIME = NATIVE | EXTERNAL | MANUAL | UNKNOWN
MODEL_TOPOLOGY = HOMOGENEOUS | HETEROGENEOUS | UNKNOWN
PER_SUBAGENT_USER_APPROVAL = NOT_REQUIRED_WHEN_MODE_AUTHORIZED_SCOPE_BOUNDED_AND_GATE_PASS
RECURSIVE_DELEGATION = DISABLED_BY_DEFAULT; CONDITIONAL_BOUNDED_ALLOWANCE
RUNTIME_CONCURRENCY_LIMIT = DISCOVERED_PER_SURFACE
TERRA = OUTSIDE_CURRENT_GPT6_ROUTING_BASELINE; COMPATIBILITY_OR_HISTORY_ONLY

Sol/Medium, Sol/High, Luna/XHigh e Sol/High → Astra/Medium são heurísticas de roteamento desta governança. Não são defaults impostos pela OpenAI. A superfície pode não permitir a escolha pretendida; nesse caso, não alegar que ela ocorreu.

## 28.2. Changelog resumido desta revisão

Mudanças propostas sobre a v1.7-R2.2:

- mantém o rebaseline Luna → Sol → Astra e a rota Luna/XHigh como ROOT quando Luna é suficiente;
- classifica os baselines Sol/Medium, Sol/High e a recomendação Sol/High → Astra/Medium como heurísticas desta governança;
- separa papel funcional, modelo resolvido, effort e superfície de ferramentas;
- separa `ORCHESTRATION_RUNTIME` de `MODEL_TOPOLOGY`, permitindo `NATIVE + HOMOGENEOUS` e `NATIVE + HETEROGENEOUS`;
- remove nomes de papel que implicavam modelo;
- permite spawn bounded sem confirmação individual quando o modo e o escopo MULTIAGENT já foram autorizados;
- mantém mudança de DIRECT para MULTIAGENT durante execução sob autorização do usuário;
- desabilita recursão por padrão e permite exceção com ganho material, tarefa bounded, ownership claro, orçamento de concorrência e suporte runtime confirmado;
- verifica tool surface real antes da delegação e permite reutilizar capability resolution estável;
- remove limites globais fixos de concorrência;
- mantém DIRECT-first, ganho material, authority, ownership e responsabilidade final do root;
- preserva Bounded Cyclic Execution fora do escopo.

## 29. Resumo normativo

DIRECT_EXECUTION = DEFAULT
MULTIAGENT_EXECUTION = EXCEPTION_WITH_MATERIAL_NET_GAIN
MODEL_FAMILY_SELECTED_BY_CAPABILITY = YES
REASONING_EFFORT_SELECTED_BY_DELIBERATION = YES
EXECUTION_RISK_CONTROLS_AUTHORITY_VALIDATION_AND_REVIEW = YES

AGENT_ROLE != RUNTIME_SELECTED_MODEL
AGENT_ROLE != REASONING_EFFORT
AGENT_ROLE != TOOL_SURFACE
REGISTERED_ROLE != GUARANTEED_RUNTIME_CAPABILITY
BEFORE_DELEGATION = VERIFY_REQUIRED_TOOL_SURFACE

ORCHESTRATION_RUNTIME = NATIVE | EXTERNAL | MANUAL
MODEL_TOPOLOGY = HOMOGENEOUS | HETEROGENEOUS
NATIVE_MULTIAGENT = ORCHESTRATION_RUNTIME = NATIVE
HETEROGENEOUS_MULTIAGENT = MODEL_TOPOLOGY = HETEROGENEOUS
NATIVE_MULTIAGENT AND HETEROGENEOUS_MULTIAGENT = COMPATIBLE_AXES
TIER_SAVING_CLAIM = REQUIRES_ACTUAL_RUNTIME_MODEL_EVIDENCE
RUNTIME_CAPABILITY_RESOLUTION != PER_SPAWN_HUMAN_GATE

LUNA_XHIGH_ROOT = ALLOWED_WHEN_LUNA_CAPABILITY_IS_SUFFICIENT
NORMAL_TECHNICAL_ROOT = SOL_MEDIUM (GOVERNANCE_HEURISTIC)
HIGH_JUDGMENT_ROOT = SOL_HIGH (GOVERNANCE_HEURISTIC)
MATERIAL_ARCHITECTURAL_DECISION = SOL_HIGH (GOVERNANCE_HEURISTIC)
SOL_HIGH_TO_ASTRA_MEDIUM = ESCALATION_HEURISTIC_NOT_PROVIDER_RULE

DIRECT_TO_MULTIAGENT_DURING_EXECUTION = USER_AUTHORIZATION_REQUIRED
RUNTIME_CAN_AUTODELEGATE != GOVERNANCE_AUTHORIZATION_TO_AUTODELEGATE
PER_SUBAGENT_USER_APPROVAL = NOT_REQUIRED_BY_DEFAULT_WHEN_MODE_AUTHORIZED_SCOPE_BOUNDED_AND_GATE_PASS
RECURSIVE_DELEGATION = DISABLED_BY_DEFAULT; ALLOW_ONLY_WITH_MATERIAL_GAIN_BOUNDED_TASK_CLEAR_OWNERSHIP_BUDGET_AND_RUNTIME_SUPPORT
RUNTIME_CONCURRENCY_LIMIT = DISCOVERED_PER_SURFACE
CONCURRENT_WRITE_OVERLAP = PROHIBITED

IN_EXECUTION_ROOT_AUTO_ESCALATION = PROHIBITED
MODEL_CHANGE_AND_EFFORT_CHANGE = USER_CONTROLLED_RUNTIME_RECONFIGURATION
DELEGATION != AUTHORITY_TRANSFER
CAPABILITY != PERMISSION
CYCLIC_EXECUTION_METHODOLOGY = OUT_OF_SCOPE_FOR_NOW
USER_FINAL_AUTHORITY = YES
TERRA = OUTSIDE_CURRENT_GPT6_ROUTING_BASELINE; COMPATIBILITY_OR_HISTORY_ONLY

## 30. Encerramento

O objetivo é minimizar o custo esperado por tarefa concluída corretamente, mantendo qualidade, segurança, autoridade e previsibilidade. DIRECT é o modo padrão; MULTIAGENT exige ganho material e autorização para o modo e escopo da atividade. Depois dessa autorização, o root pode criar subagentes bounded que passem o gate sem aprovação humana por spawn individual.

O root mantém a responsabilidade de reconciliar evidências e emitir o resultado. Use inteligência forte onde julgamento forte muda materialmente a probabilidade de sucesso. Feche decisões antes de delegar execução mecânica. Quando o root em execução deixar de ser suficiente, recomende reclassificação, pare em boundary seguro e aguarde reconfiguração do usuário. Não reconfigure silenciosamente o runtime.


