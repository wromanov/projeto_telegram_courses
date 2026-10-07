# Política de Geração de Prompts Multiagente — v1.7-R2.6 — CANONICAL / ACTIVE

```text
STATUS = CANONICAL
LIFECYCLE = ACTIVE
PREVIOUS_BASE = Politica-Prompts-Agente-v1.7-R2.5.md
CONSOLIDATES = Politica-Prompts-Agente-v1.7-R2.5.md
REVISION_FOCUS = GPT6_MODEL_ROUTING + CURRENT_AGENT_RUNTIME_SEMANTICS + ROLE_MODEL_TOOL_SEPARATION + CONTEXT_DIET
MULTIAGENT_ALIGNMENT = AGENTS-Multiagente-Generico-v1.7-R2.3-Roteamento-Economico.md
SCOPE = TRANSVERSAL
DOMAIN_SPECIFIC_CONTENT = PROHIBITED
BOUNDED_CYCLIC_EXECUTION_INCLUDED = NO
CANONICALIZATION = YES
PROMOTION = YES
USER_REVIEW_REQUIRED = NO
```

---

## 0. Finalidade

Esta política governa a criação de prompts de atividade para Work ou Codex.

Ela possui dois objetivos simultâneos:

1. escolher uma arquitetura de execução tecnicamente correta e economicamente racional;
2. entregar ao executor somente o contexto necessário para executar a atividade.

A política deve impedir dois desperdícios distintos:

```text
EXECUTION_WASTE =
UNNECESSARY_MODEL_COST
+ UNNECESSARY_REASONING_COST
+ UNNECESSARY_SUBAGENT_COST
+ UNNECESSARY_COORDINATION_COST

PROMPT_WASTE =
IRRELEVANT_EXECUTOR_CONTEXT
+ DUPLICATED_CONTEXT
+ INTERNAL_GOVERNANCE_REASONING_EXPOSED_TO_EXECUTOR
+ UNUSED_CAPABILITY_INFORMATION
```

Princípio central:

```text
THE_GENERATOR_MAY_REASON_BROADLY
THE_EXECUTOR_PROMPT_MUST_BE_NARROW
```

A análise necessária para escolher modelo, esforço, subagentes, Skills e Plugins
não precisa ser enviada integralmente ao Codex/Work.

---

## 1. Duas audiências, dois outputs

Toda geração de prompt deve separar obrigatoriamente:

```text
OUTPUT_A = EXECUTION_DECISION_CARD
AUDIENCE_A = USER

OUTPUT_B = EXECUTOR_PAYLOAD
AUDIENCE_B = CODEX | WORK
```

### 1.1 Regra de cópia

```text
USER_SHOULD_COPY_TO_EXECUTOR = OUTPUT_B_ONLY
```

O Card A existe para o usuário visualizar e auditar a decisão de roteamento.

O Card B contém o prompt executável.

Não misturar as duas audiências.

---

# PARTE I — DECISÃO INTERNA DO GERADOR

## 2. Internal Routing Worksheet — NÃO enviar ao executor

O agente gerador deve avaliar internamente, quando aplicável:

```text
TASK_CLASS
RISK
COGNITIVE_COMPLEXITY
OPERATIONAL_VOLUME
VERIFIABILITY
REVERSIBILITY

COGNITIVE_HOTSPOTS
MECHANICAL_WORK
OBJECTIVE_VALIDATION_WORK

AMBIGUITY_SCORE
NOVELTY_SCORE
COUPLING_SCORE
INVARIANT_COMPLEXITY_SCORE
CAUSAL_DEPTH_SCORE
QUANT_SCIENTIFIC_DEPTH_SCORE
CONTEXT_RECONCILIATION_SCORE
PEAK_DIFFICULTY
HIGH_DIMENSION_COUNT
CAPABILITY_DEMAND_CLASS

MATERIAL_DECISION_COUNT
DEPENDENCY_DEPTH
CONSTRAINT_INTERACTION
EVIDENCE_VOLUME
DEFENSIBLE_ALTERNATIVES
ITERATIVE_REASONING_NEED
DELIBERATION_DEMAND_CLASS

EXECUTION_RISK_CLASS

COGNITIVE_MECHANICAL_SPLIT
CLOSED_DECISION_MATERIALIZATION
ROOT_MUST_READ_SOURCE_TO_MAKE_DECISION
ROOT_MUST_REVIEW_FINAL_DELTA

INITIAL_ROUTING_SELECTION
CURRENT_ROOT_SUFFICIENCY
MID_TASK_ROUTING_RECLASSIFICATION
ROOT_RECLASSIFICATION_REQUIRED
MULTIAGENT_RECLASSIFICATION_REQUIRED
SAFE_RESUME_POINT
USER_RECONFIGURATION_REQUIRED

ROUTINE_EXECUTION_GATE
ASTRA_SELECTION_GATE
ARCHITECTURE_ESCALATION_PROTOCOL

PARALLEL_INDEPENDENT_FRONTS
DISTINCT_SPECIALIZATION_REQUIRED
MATERIAL_DECOMPOSITION_GAIN
IDENTIFIED_CONFLICT_REQUIRES_ADJUDICATION
GOVERNANCE_REQUIRES_INDEPENDENT_REVIEW
MATERIAL_INTELLIGENCE_ROUTING_GAIN

EXPECTED_MATERIAL_GAIN
HANDOFF_COST
DUPLICATED_CONTEXT_COST
INTEGRATION_COST
REDUNDANCY_CHECK
```

Esses campos são instrumentos de decisão.

Por padrão:

```text
INTERNAL_ROUTING_WORKSHEET
NOT_IN_EXECUTOR_PAYLOAD
```

Só transformar uma conclusão interna em instrução do executor quando ela alterar:

- ação;
- escopo;
- authority;
- ownership;
- delegation;
- validação;
- stop condition;
- output esperado.

---

## 3. Relevance Gate do payload

Antes de inserir qualquer informação no Card B, aplicar:

```text
EXECUTOR_RELEVANCE_TEST
```

Pergunta:

> Se eu remover esta informação, existe chance material de o Codex/Work executar
> uma ação diferente, ultrapassar o escopo, validar incorretamente, delegar
> incorretamente, parar no lugar errado ou produzir um output inadequado?

Se:

```text
NO
```

então:

```text
OMIT_FROM_EXECUTOR_PAYLOAD
```

### 3.1 Informação normalmente pertinente

Inclua quando aplicável:

- objetivo;
- resultado esperado;
- root oficial;
- branch/baseline quando forem gates reais;
- authorities que precisam ser consultadas;
- arquivos ou superfícies relevantes;
- escopo autorizado;
- não escopo material;
- invariantes;
- contrato congelado;
- critérios de aceite;
- ações concretas;
- ordem operacional quando necessária;
- subagentes efetivamente autorizados;
- ownership;
- write mode;
- validações;
- comandos necessários;
- regras de Git;
- ações externas autorizadas ou proibidas quando plausíveis;
- stop conditions;
- formato mínimo de retorno.

### 3.2 Informação normalmente NÃO pertinente

Não enviar ao executor por padrão:

- histórico de evolução da policy;
- explicação longa sobre por que outro modelo foi rejeitado;
- gates completos G1–G6;
- score interno de risco;
- lista completa de alternativas descartadas;
- cálculo narrativo de economicidade;
- justificativas de `NO` para papéis não usados;
- catálogo de Skills não selecionadas;
- catálogo de Plugins não selecionados;
- anti-patterns genéricos da policy;
- exemplos de conformidade;
- telemetria de governança sem impacto na atividade;
- rationale repetido em múltiplas seções;
- conteúdo de documento canônico que o executor pode ler diretamente;
- regras genéricas que não mudam a execução concreta.

---

## 4. Referenciar em vez de duplicar

Quando Codex/Work tiver acesso ao repositório ou arquivo:

```text
REFERENCE_CANONICAL_SOURCE
PREFER_OVER_COPYING_CANONICAL_SOURCE
```

Use:

```text
AUTHORITY_TO_READ =
<path exato>
```

e, quando possível:

```text
READ_ONLY_RELEVANT_SECTION =
<título, seção ou assunto necessário>
```

Não copie para o prompt dezenas ou centenas de linhas de um documento local
se o executor pode lê-lo no próprio workspace.

Exceção:

- valor congelado necessário para comparação;
- checksum esperado;
- invariant curto;
- requisito que precisa estar imediatamente visível;
- boundary crítico cuja omissão seria perigosa.

---

# PARTE II — MODELO E ESFORÇO

## 5. Configuração mínima suficiente

A configuração é composta por decisões independentes:

```text
MINIMUM_SUFFICIENT_CONFIGURATION =
MODEL
+ REASONING_EFFORT
+ EXECUTION_MODE
+ SKILL
+ PLUGIN
+ NATIVE_EXECUTION
```

Objetivo:

```text
EXPECTED_COST_PER_SUCCESSFUL_TASK
```

sujeito a:

```text
QUALITY
ROBUSTNESS
VERIFIABILITY
AUTHORITY_PRESERVATION
SCOPE_CONTROL
```

Não selecionar por prestígio ou disponibilidade.

```text
MODEL_AVAILABLE != MODEL_REQUIRED
STRONGER_MODEL != BETTER_DEFAULT
HIGHER_EFFORT != BETTER_DEFAULT
TASK_IMPORTANT != STRONGER_MODEL_REQUIRED
TASK_LARGE != STRONGER_MODEL_REQUIRED
MANY_FILES != STRONGER_MODEL_REQUIRED
LONG_CONTEXT != STRONGER_MODEL_REQUIRED
HIGH_RISK != STRONGER_MODEL_REQUIRED
SCIENTIFIC_TASK != SOL_REQUIRED
ARCHITECTURE_RELATED_TASK != MATERIAL_ARCHITECTURAL_DECISION
```

### 5.1 Três eixos independentes

A seleção deve separar:

```text
CAPABILITY_DEMAND
→ seleciona MODEL_FAMILY

DELIBERATION_DEMAND
→ seleciona REASONING_EFFORT dentro da família

EXECUTION_RISK
→ seleciona rigor de AUTHORITY, VALIDATION, REVIEW e STOP CONDITIONS
```

Regra central:

```text
MODEL_FAMILY
IS_SELECTED_BY
CAPABILITY_DEMAND

REASONING_EFFORT
IS_SELECTED_BY
DELIBERATION_DEMAND

VALIDATION_AND_AUTHORITY
ARE_SELECTED_BY
EXECUTION_RISK
```

Não usar risco, importância, domínio científico ou rótulo arquitetural como
atalho para selecionar um modelo mais forte.

### 5.2 Capability Demand — C0 a C4

A demanda de capacidade deve ser classificada por dimensões cognitivas de `0–4`.

```text
AMBIGUITY
NOVELTY
COUPLING
INVARIANT_COMPLEXITY
CAUSAL_DEPTH
QUANT_SCIENTIFIC_DEPTH
CONTEXT_RECONCILIATION
```

Interpretação geral:

```text
0 = ausente / fechado / trivial
1 = baixo
2 = moderado
3 = alto
4 = extremo / excepcional
```

Guia por dimensão:

| Dimensão | 0 | 2 | 4 |
|---|---|---|---|
| `AMBIGUITY` | requisitos fechados | algumas escolhas relevantes | problema fortemente subespecificado |
| `NOVELTY` | padrão conhecido | adaptação relevante | sem padrão confiável conhecido |
| `COUPLING` | componente isolado | vários componentes | muitas interdependências materiais |
| `INVARIANT_COMPLEXITY` | invariantes simples | múltiplos invariantes | invariantes difíceis, conflitantes ou altamente sensíveis |
| `CAUSAL_DEPTH` | causa direta | diagnóstico multietapa | causalidade difícil/cross-system |
| `QUANT_SCIENTIFIC_DEPTH` | trivial/ausente | análise técnica não trivial | derivação/modelagem científica difícil |
| `CONTEXT_RECONCILIATION` | uma fonte | várias fontes compatíveis | authorities/evidências difíceis de reconciliar |

Não somar mecanicamente os pontos.

Calcular:

```text
PEAK_DIFFICULTY =
MAX(all cognitive dimensions)

HIGH_DIMENSION_COUNT =
COUNT(dimensions >= 3)
```

Classificação:

```text
C0 =
NO_MATERIAL_DECISION
AND SOLUTION_CLOSED

C1 =
PEAK_DIFFICULTY <= 1

C2 =
PEAK_DIFFICULTY = 2

C3 =
PEAK_DIFFICULTY = 3
OR HIGH_DIMENSION_COUNT >= 2

C4 =
PEAK_DIFFICULTY = 4
OR HIGH_DIMENSION_COUNT >= 3
OR EXCEPTIONAL_CAPABILITY_TRIGGER = PRESENT
```

A classificação é um instrumento de roteamento, não um score científico exato.

### 5.3 Baseline de família por Capability Demand

A família deve ser escolhida pela capacidade necessária, sem transformar o mapping em
uma escada rígida de efforts.

```text
C0
→ LUNA

C1
→ LUNA

C2
→ LUNA por padrão
→ SOL quando julgamento técnico material exceder a faixa segura de Luna

C3
→ SOL por padrão

C4
→ SOL por padrão
→ ASTRA somente quando ASTRA_SELECTION_GATE = PASS
```

Importante:

```text
LUNA_XHIGH_ROOT = ALLOWED
LUNA_XHIGH_DOES_NOT_IMPLY_SOL_REQUIRED = YES
```

Um problema pode exigir deliberação muito alta e ainda permanecer dentro da capacidade
de Luna. Nesse caso, `Luna / XHigh` é ROOT válido. Inversamente, um problema pode exigir
mais capacidade com deliberação moderada e selecionar `Sol / Medium`.

```text
DELIBERATION_GAP != CAPABILITY_GAP
```

### 5.4 Deliberation Demand — D0 a D4

A demanda de deliberação mede quanto raciocínio sustentado é necessário **depois**
de escolhida a família de modelo.

Avaliar:

```text
MATERIAL_DECISION_COUNT
DEPENDENCY_DEPTH
CONSTRAINT_INTERACTION
EVIDENCE_VOLUME
NEED_FOR_COUNTERFACTUAL_ANALYSIS
DEFENSIBLE_ALTERNATIVES
ITERATIVE_REASONING_NEED
```

Classificação:

```text
D0 = decisão já fechada / execução prescrita
D1 = raciocínio curto
D2 = raciocínio moderado
D3 = raciocínio profundo
D4 = raciocínio excepcionalmente sustentado
```

Regra:

```text
DELIBERATION_GAP
→ INCREASE_EFFORT

CAPABILITY_GAP
→ INCREASE_MODEL
```

Não usar esforço extremo para compensar incapacidade real do modelo.

### 5.5 Effort mapping por família

O effort é escolhido **depois** da família e mede deliberação, não prestígio.

#### Luna

```text
D0
→ LUNA / LOW

D1
→ LUNA / MEDIUM

D2-D3
→ LUNA / HIGH

D4
→ LUNA / XHIGH
   somente se Luna continuar capability-sufficient
```

Aplicar:

```text
LUNA_XHIGH_ROOT = ALLOWED
LUNA_XHIGH_SUBAGENT = ALLOWED
LUNA_XHIGH_MUST_NOT_COMPENSATE_FOR_CAPABILITY_GAP = YES
```

`Luna / XHigh` é indicado para investigação/reconciliação longa, priorização e solução
de problemas com restrições claras quando a demanda principal é deliberação sustentada.

#### Sol

```text
D0-D1
→ SOL / LOW OR MEDIUM conforme runtime/benefício

D2
→ SOL / MEDIUM

D3
→ SOL / HIGH

D4
→ SOL / XHIGH when materially justified
```

Para **decisão arquitetural material**, aplicar override operacional:

```text
MATERIAL_ARCHITECTURAL_DECISION
→ SOL / HIGH
```

Se `Sol / High` declarar insuficiência para essa decisão, não exigir `Sol / XHigh` como
degrau intermediário obrigatório:

```text
SOL_HIGH_ARCHITECTURE_INSUFFICIENT
→ ROOT_RECLASSIFICATION_REPORT
→ STOP
→ USER_RECONFIGURES
→ ASTRA / MEDIUM
```

`Sol / XHigh` permanece válido para revisão, auditoria, debug ou análise muito profunda
quando o problema continua dentro da capacidade de Sol e o gap é de deliberação.

#### Astra

```text
ASTRA_ENTRY = MEDIUM
ASTRA_HIGH = ONLY_IF_MEDIUM_INSUFFICIENT
ASTRA_XHIGH = ONLY_IF_HIGH_INSUFFICIENT
ASTRA_MAX = ONLY_IF_XHIGH_INSUFFICIENT
MAX_EFFORT_DEFAULT = PROHIBITED
```

Astra continua excepcional e sujeito ao `ASTRA_SELECTION_GATE`.

### 5.6 Execution Risk — R0 a R4

Risco operacional permanece separado da escolha de modelo.

```text
R0 = read-only / impacto desprezível
R1 = alteração local e facilmente reversível
R2 = alteração material, bounded e reversível
R3 = ação consequencial / publicação / mudança de estado relevante
R4 = produção, LIVE, financeiro, segurança crítica, irreversibilidade alta
```

Risco controla:

```text
AUTHORIZATION_STRENGTH
VALIDATION_DEPTH
PRECONDITIONS
POSTCONDITIONS
REVIEW_REQUIREMENT
STOP_ON_MISMATCH
```

e não:

```text
MODEL_STRENGTH
```

Exemplos:

```text
C0 + D0 + R4
→ modelo barato pode ser suficiente
→ authority/validation devem ser rigorosas

C4 + D4 + R0
→ SOL/HIGH pode ser necessário
→ atividade continua read-only
```

### 5.7 Regra de quantificação para arquitetura e ciência

Antes de escalar por domínio:

```text
HIGH_DIFFICULTY
MUST_BE_QUANTIFIED
BEFORE_MODEL_ESCALATION
```

Ciência continua seguindo classificação normal:

```text
SCIENCE
→ CLASSIFY C + D + R
```

Arquitetura exige distinguir tarefa relacionada a arquitetura de decisão arquitetural
material:

```text
ARCHITECTURE_RELATED_TASK
!=
MATERIAL_ARCHITECTURAL_DECISION
```

Leitura de ADR, documentação, materialização de decisão fechada ou alteração mecânica
não seleciona Sol/High por rótulo.

Quando existe **decisão arquitetural material**:

```text
MATERIAL_ARCHITECTURAL_DECISION = YES
→ ROOT = SOL / HIGH
```

Se `Sol / High` não atingir confiança/capacidade suficiente:

```text
SOL_HIGH_CONFIDENCE = INSUFFICIENT
→ ROOT_RECLASSIFICATION_REQUIRED = YES
→ RECOMMENDED_ROOT = ASTRA / MEDIUM
→ STOP_AT_SAFE_BOUNDARY
→ WAIT_FOR_USER_ROOT_RECONFIGURATION
```

Portanto:

```text
ARCHITECTURE_RELATED_TASK
!= AUTOMATIC_SOL_HIGH

MATERIAL_ARCHITECTURAL_DECISION
= SOL_HIGH_DEFAULT
```

## 6. Taxonomia operacional de modelos

```text
NORMAL_OPERATING_RANGE =
LUNA | SOL

ASTRA =
EXCEPTIONAL_ESCALATION_MODEL

LEGACY_TERRA =
COMPATIBILITY_ONLY_WHEN_RUNTIME_OR_EXISTING_PROFILE_REQUIRES

TERRA = OUTSIDE_CURRENT_GPT6_ROUTING_BASELINE
```

### 6.1 Luna

Preferido para:

- trabalho focado;
- repetitivo;
- mecânico;
- baixo ou moderado em ambiguidade;
- volumoso e sensível a custo;
- execução derivada de decisão já tomada;
- análise longa com restrições claras quando Luna permanece capability-sufficient.

```text
LUNA_ROOT = ALLOWED
LUNA_EFFORT = BY_DELIBERATION
LUNA_XHIGH_ROOT = ALLOWED
```

`Luna / XHigh` é uma configuração de ROOT válida quando a família Luna continua
suficiente e a tarefa precisa de deliberação profunda/sustentada. Não é um substituto
para Sol quando existe capability gap.

### 6.2 Sol

Sol é a família técnica normal quando existe julgamento material que excede a faixa
segura de Luna.

Preferido para:

- coding cotidiano com julgamento técnico;
- integração conhecida mas não trivial;
- implementação com escolhas locais materiais;
- debug difícil;
- revisão profunda;
- auditoria técnica;
- decisão arquitetural material.

```text
SOL_TECHNICAL_ROOT_BASELINE = MEDIUM
SOL_HIGH_JUDGMENT_BASELINE = HIGH
ROOT_BASELINE != ROOT_FLOOR
```

### 6.2.1 Seleção do ROOT pela demanda cognitiva remanescente

O ROOT deve ser escolhido pela **demanda cognitiva ainda existente na atividade atual**,
não pela importância do projeto, pela categoria documental ou pelo fato de a ação ser
consequencial.

```text
SELECT_ROOT_BY_REMAINING_COGNITIVE_DEMAND = YES
```

Princípios:

```text
TASK_IS_GOVERNANCE != SOL_REQUIRED
CONSEQUENTIAL_GIT_ACTION != STRONGER_MODEL_REQUIRED
HIGH_CONSEQUENCE != HIGH_COGNITIVE_COMPLEXITY
PERMISSION_REQUIREMENT != MODEL_REQUIREMENT
```

Uma atividade completamente fechada, mecânica e objetivamente verificável pode usar
Luna como ROOT no effort compatível.

```text
LUNA_ROOT_ELIGIBLE_FOR_CLOSED_MECHANICAL_TASKS = YES
LUNA_XHIGH_ROOT_ELIGIBLE_FOR_DEEP_BOUNDED_REASONING = YES
```

Gate mecânico:

```text
IF
SCOPE_ALREADY_ADJUDICATED = YES
AND FILE_SET_EXACT = YES
AND SEMANTIC_DECISIONS_REMAINING = NONE
AND AUTHORITY_CONFLICT = NONE
AND VALIDATION_IS_OBJECTIVE = YES
AND OPERATION_SEQUENCE_IS_PRESCRIBED = YES
AND CONSEQUENTIAL_ACTIONS_EXPLICITLY_AUTHORIZED = YES

THEN
ROOT = LUNA / LOW | MEDIUM | HIGH BY DELIBERATION
```

Se houver investigação longa/reconciliação extensa, mas Luna continuar capability-sufficient:

```text
DELIBERATION_DEMAND = D4
AND CAPABILITY_GAP = NO
→ ROOT = LUNA / XHIGH
```

Se ainda houver reconciliação técnica material, integração, interpretação complexa de
authority ou decisão semântica que exceda Luna:

```text
CAPABILITY_GAP_FROM_LUNA = YES
→ ROOT = SOL / MEDIUM OR HIGH BY DELIBERATION
```

### 6.2.2 Consequência, autorização e inteligência são eixos distintos

Ações como commit, push, deploy, publicação ou alteração externa podem exigir
autorização explícita e gates rigorosos, mas isso não implica modelo mais forte.

```text
CONSEQUENTIAL_ACTION
→ STRONG_PERMISSION_BOUNDARY

CONSEQUENTIAL_ACTION
!=
STRONGER_MODEL_BY_DEFAULT
```

O modelo responde à dificuldade de raciocínio.
A permission responde à authority concedida.
A validação responde à necessidade de evidência.

### 6.3 Protocolo arquitetural Sol → Astra

Uma decisão arquitetural material começa em:

```text
ROOT = SOL / HIGH
```

Sol/High deve tentar resolver integralmente o hotspot. Se atingir confiança suficiente,
encerra sem Astra.

Se concluir que sua capacidade/confiança é insuficiente:

```text
ROOT_RECLASSIFICATION_REQUIRED = YES
CURRENT_ROOT = SOL / HIGH
RECOMMENDED_ROOT = ASTRA / MEDIUM
STOP_AT_SAFE_BOUNDARY = YES
```

O `ROOT_RECLASSIFICATION_REPORT` deve incluir, quando aplicável:

```text
ALTERNATIVES_CONSIDERED =
DECISION_IMPACT =
```

Nenhum spawn de Astra pode contornar a regra de mudança de ROOT controlada pelo usuário.

### 6.4 Astra

Astra é excepcional.

Somente elegível quando:

```text
ASTRA_SELECTION_GATE = PASS
```

Exige justificativa concreta de por que Sol não é suficiente ou é materialmente inferior
para o hotspot restante.

Hard triggers podem incluir:

```text
OPEN_ENDED_UNFAMILIAR_PROBLEM
MATERIAL_NOVELTY_WITH_NO_CLEAR_SOLUTION_PATTERN
EXCEPTIONALLY_DIFFICULT_CAUSAL_DEBUGGING
HARD_END_TO_END_REASONING_ACROSS_MULTIPLE_SYSTEMS
FRONTIER_TECHNICAL_OR_SCIENTIFIC_REASONING
VERY_DIFFICULT_LONG_CONTEXT_RECONCILIATION
HIGH_COMPLEXITY_COMPUTER_OR_TOOL_ORCHESTRATION
SOL_CAPABILITY_ALREADY_OBSERVED_AS_INSUFFICIENT
```

Para arquitetura:

```text
ASTRA_ENTRY = MEDIUM
ASTRA_HIGH = ONLY_IF_MEDIUM_INSUFFICIENT
ASTRA_XHIGH = ONLY_IF_HIGH_INSUFFICIENT
ASTRA_MAX = ONLY_IF_XHIGH_INSUFFICIENT
```

### 6.5 Compatibilidade legada Terra

Terra está fora do baseline atual de roteamento GPT-6. Perfis ou runtimes GPT-5.6
Terra podem permanecer temporariamente disponíveis para compatibilidade ou histórico,
mas novos prompts e novas decisões de roteamento desta revisão devem preferir a
hierarquia GPT-6 `Luna → Sol → Astra`.

```text
LEGACY_TERRA_PROFILE_AVAILABLE
!=
LEGACY_TERRA_PROFILE_PREFERRED
```

### 6.6 Modelo e esforço são independentes

```text
MODEL != REASONING_EFFORT

CAPABILITY_GAP
→ CONSIDER_STRONGER_MODEL

DELIBERATION_GAP
→ CONSIDER_HIGHER_EFFORT

MISSING_INFORMATION_OR_ACCESS
→ ACQUIRE_INFORMATION_OR_STOP
```

Nunca usar modelo ou esforço para compensar arquivo, contexto, requisito, permission,
tool/plugin ou authority ausente.

## 7. ROOT antes dos subagentes

Decidir primeiro:

```text
ORCHESTRATOR_MODEL
ORCHESTRATOR_EFFORT
```

Depois avaliar subagentes.

```text
ROOT_CAN_EXECUTE != ROOT_SHOULD_EXECUTE
LOWER_TIER_CAN_EXECUTE != LOWER_TIER_SHOULD_EXECUTE
```

---

## 8. DIRECT vs MULTIAGENT

### 8.1 DIRECT

Preferir DIRECT quando:

- trabalho pequeno;
- contexto pequeno;
- ROOT já possui contexto suficiente;
- decomposição não reduz custo/risco/contexto;
- handoff custa mais que a economia;
- não existe independência obrigatória;
- não existe especialização material separável.

```text
IF_BENEFIT_IS_UNCLEAR = DIRECT
```

### 8.2 MULTIAGENT

Multiagente exige ganho material demonstrável.

```text
MULTIAGENT != PARALLELISM
```

Pipeline sequencial é válido.

Exemplo:

```text
ROOT
→ IMPLEMENTER
→ VALIDATOR
→ ROOT
```

### 8.3 Offload Materiality Gate — obrigatório antes de qualquer delegação

Capacidade técnica para delegar não constitui justificativa econômica para delegar.

```text
OBJECTIVE_WORK != DELEGABLE_WORK
LOWER_TIER_CAPABLE != HANDOFF_ECONOMICALLY_JUSTIFIED
DELEGABLE != WORTH_DELEGATING
```

Depois de identificar um papel tecnicamente compatível, o gerador deve aplicar:

```text
OFFLOAD_MATERIALITY_GATE
```

O gate só passa quando o ganho líquido de separar a responsabilidade é material.

```text
OFFLOAD_MATERIALITY_GATE = PASS

IF:

DELEGATED_OPERATIONAL_VOLUME = MATERIAL
OR ROOT_TIME_SAVED = MATERIAL
OR ROOT_CONTEXT_POLLUTION_AVOIDED = MATERIAL
OR DISTINCT_SPECIALIZATION_VALUE = MATERIAL
OR INDEPENDENCE_VALUE = MATERIAL

AND:

EXPECTED_OFFLOAD_GAIN
>
HANDOFF_COST
+ DUPLICATED_CONTEXT_COST
+ RECONCILIATION_COST
+ INTEGRATION_COST
```

Caso contrário:

```text
OFFLOAD_MATERIALITY_GATE = FAIL
→ KEEP_WORK_IN_ROOT
```

A mera existência de um agente especializado não reduz o limiar econômico.

```text
ROLE_EXISTS != ROLE_SHOULD_BE_USED
PROFILE_AVAILABLE != OFFLOAD_JUSTIFIED
```

### 8.4 Evidence duplication vs final review

Antes de delegar, distinguir:

```text
ROOT_MUST_READ_SOURCE_TO_MAKE_DECISION
```

de:

```text
ROOT_MUST_REVIEW_FINAL_DELTA
```

Esses custos não são equivalentes.

```text
ROOT_MUST_REVIEW_FINAL_DELTA
!=
DUPLICATED_CONTEXT_BY_DEFAULT

REVIEW_COST
!=
MATERIALIZATION_COST
```

Existe penalidade forte quando o subagente precisa absorver praticamente o mesmo
contexto amplo do ROOT para **redescobrir ou reinterpretar a solução**.

Exemplo:

```text
ROOT reads all authorities
→ SUBAGENT rereads all authorities
→ SUBAGENT re-derives decisions
→ ROOT rereads everything

DUPLICATED_CONTEXT_COST = HIGH
```

Não aplicar a mesma penalidade quando o ROOT já fechou a decisão e entrega um
contrato estreito:

```text
ROOT reads authorities
→ closes decisions / invariants
→ freezes narrow contract
→ LOWER_TIER materializes
→ ROOT reviews only final delta

DUPLICATED_CONTEXT_COST = LOW | MODERATE
```

Portanto:

```text
IF ROOT_MUST_READ_SOURCE_TO_MAKE_DECISION = YES
AND LOWER_TIER_MUST_RECONSUME_SAME_SOURCE_CONTEXT = YES
AND DELEGATED_VOLUME = LOW | MEDIUM
THEN
PREFER_DIRECT = YES
```

Mas:

```text
IF ROOT_MUST_REVIEW_FINAL_DELTA = YES
AND LOWER_TIER_RECEIVES_CLOSED_NARROW_CONTRACT = YES
THEN
DO_NOT_TREAT_FINAL_REVIEW_AS_FULL_CONTEXT_DUPLICATION
```

A revisão final do ROOT preserva adjudicação; ela não implica que o ROOT deveria
ter produzido fisicamente todo o delta.

### 8.5 Routine Governance / Git Checkpoint

Atividades de reconciliação e versionamento rotineiro de governança/configuração
devem ser consideradas, por padrão, uma única linha operacional do ROOT quando:

```text
KNOWN_BASELINE = YES
BOUNDED_FILE_SET = YES
NO_ARCHITECTURAL_DECISION = YES
ROUTINE_GIT_OPERATIONS = YES
SMALL_CONFIG_VALIDATION = YES
ROOT_MUST_REVIEW_DIFF = YES
```

Rota padrão:

```text
ROUTINE_GOVERNANCE_CHECKPOINT
→ DIRECT_BY_DEFAULT
→ ZERO_SUBAGENTS_BY_DEFAULT
→ ROOT_SELECTED_BY_REMAINING_COGNITIVE_DEMAND
```

Não hard-code `Sol / Medium` apenas porque o checkpoint é de governança.

Se ainda houver reconciliação, classificação, interpretação de authority ou
julgamento semântico:

```text
ROOT = SOL / MEDIUM
```

Se todas as decisões estiverem fechadas e restar apenas execução prescrita,
bounded e objetivamente verificável:

```text
ROOT = LUNA / LOW | MEDIUM | HIGH BY DELIBERATION
```

Não criar Validator apenas para deslocar checks pequenos de Git, TOML, filenames,
registry ou stage.

MULTIAGENT só se torna elegível quando houver ganho material adicional, por exemplo:

- suíte longa ou pesada;
- build demorado;
- grandes volumes de logs;
- varredura extensa de dados;
- centenas de arquivos/artefatos independentes;
- revisão independente obrigatória;
- especialização distinta material.

### 8.6 Nova atividade fechada vs reclassificação no meio da atividade

Distinguir:

```text
NEW_TASK_WITH_ALL_DECISIONS_ALREADY_CLOSED
```

de:

```text
MID_TASK_ROUTING_RECLASSIFICATION
```

Uma nova atividade cujo contrato já nasce fechado pode começar diretamente no
menor ROOT suficiente:

```text
NEW_TASK_WITH_ALL_DECISIONS_ALREADY_CLOSED
+ MECHANICAL
+ OBJECTIVELY_VERIFIABLE
→ LUNA ROOT IS ELIGIBLE
→ SIZE EFFORT BY DELIBERATION
```

A seleção inicial de ROOT ocorre antes da execução e não constitui mudança de runtime:

```text
INITIAL_ROUTING_SELECTION
!=
MID_TASK_ROUTING_RECLASSIFICATION
```

Se a atividade já está em execução, mudar modelo ou effort do ROOT é uma ação da
superfície/runtime controlada pelo usuário.

```text
MODEL_CHANGE = USER_CONTROLLED
EFFORT_CHANGE = USER_CONTROLLED
IN_EXECUTION_ROOT_AUTO_ESCALATION = PROHIBITED
```

Se o ROOT atual continua suficiente e resta pouco trabalho:

```text
CURRENT_ROOT_IS_STILL_SUFFICIENT = YES
REMAINING_WORK = SMALL
→ CURRENT_ROOT_CONTINUES_DIRECTLY
```

Não interromper a atividade apenas para economizar poucas operações.

Se uma mudança real de ROOT para tier/effort inferior produzir economia material:

```text
MID_TASK_ROOT_DEESCALATION_GAIN = MATERIAL
→ ROOT_DEESCALATION_RECOMMENDATION = ALLOWED
→ USER_DECISION_REQUIRED
```

Delegar trabalho mecânico a tier inferior sem mudar o ROOT continua sendo
`COGNITIVE_MECHANICAL_SPLIT`, não `ROOT_DEESCALATION`.

```text
LOWER_TIER_IS_SUFFICIENT
!=
MID_TASK_ROOT_CHANGE_IS_ECONOMICALLY_JUSTIFIED
```

### 8.7 Cognitive–Mechanical Split Gate

Antes de fechar `DIRECT` ou `MULTIAGENT`, verificar se a mesma atividade contém:

```text
A) COGNITIVE_WORK
```

como:

- arquitetura;
- ciência;
- modelagem;
- adjudicação;
- definição de invariantes;
- definição de contracts;
- decisões semânticas;
- interpretação de authorities;
- resolução de conflitos;
- escolhas técnicas materiais;

e:

```text
B) MECHANICAL_MATERIALIZATION
```

como:

- escrita de documentação;
- materialização de Authority já definida;
- atualização factual de estado/roadmap/sprints;
- implementação prescrita;
- wiring simples;
- alterações repetitivas;
- configuração fechada;
- geração de arquivos segundo especificação;
- validações objetivas extensas.

Princípios:

```text
HIGH_TIER_REASONING
!=
HIGH_TIER_MATERIALIZATION

DECISION_OWNER
!=
PHYSICAL_WRITER

ROOT_CAN_MATERIALIZE
!=
ROOT_SHOULD_MATERIALIZE

ROOT_FINAL_REVIEW
!=
ROOT_MUST_AUTHOR_THE_DELTA

DELEGATING_MATERIALIZATION
!=
ROOT_DEESCALATION
```

O ROOT de tier alto pode permanecer responsável pela atividade enquanto um tier
inferior executa materialização fechada.

Classificar:

```text
COGNITIVE_MECHANICAL_SPLIT = PRESENT | ABSENT
```

A materialização só pode ser delegada quando:

```text
DECISIONS_CLOSED = YES
SEMANTICS_CLOSED = YES
INVARIANTS_CLOSED = YES
SCOPE_BOUNDED = YES
OWNERSHIP_CLEAR = YES
UNRESOLVED_MATERIAL_CHOICES = NONE
HANDOFF_CONTRACT_IS_NARROW = YES
LOWER_TIER_CAN_MATERIALIZE_WITHOUT_INTERPRETATION = YES
```

e:

```text
EXPECTED_MATERIALIZATION_OFFLOAD_GAIN
>
HANDOFF_COST
+ CONTEXT_TRANSFER_COST
+ RECONCILIATION_COST
+ EXPECTED_REWORK_COST
```

Se passar:

```text
PREFER_SEQUENTIAL_MULTIAGENT = YES
```

Fluxo preferencial:

```text
HIGHER_TIER_ROOT
→ THINK / DESIGN / DECIDE / FREEZE CONTRACT

LOWER_TIER_EXECUTOR
→ WRITE / IMPLEMENT CLOSED SPECIFICATION

HIGHER_TIER_ROOT
→ REVIEW / ADJUDICATE / ACCEPT
```

`PREFER_SEQUENTIAL_MULTIAGENT = YES` não torna delegação obrigatória.

Se o delta mecânico for pequeno demais para amortizar handoff:

```text
EXECUTION_MODE = DIRECT
```

continua correto.

#### 8.7.1 Materialization Stop Rule

Se o tier inferior encontrar:

```text
UNPRESCRIBED_CHOICE
SEMANTIC_AMBIGUITY
CONTRACT_CONFLICT
INVARIANT_CONFLICT
AUTHORITY_CONFLICT
ARCHITECTURAL_DECISION
SCIENTIFIC_DECISION
```

deve:

```text
STOP_AFFECTED_SCOPE
RETURN_TO_ROOT
```

O tier inferior não resolve por inferência.

Depois:

```text
ROOT_CLOSES_DECISION
→ FREEZES_UPDATED_CONTRACT
→ LOWER_TIER_MAY_CONTINUE
```

---

## 9. G6 — Material Intelligence Routing Gain

```text
HIGHER_TIER_REQUIRED_FOR_REASONING = YES
AND LOWER_TIER_CAPABLE_OF_BOUNDED_EXECUTION = YES
AND DELEGATED_WORK_IS_OBJECTIVELY_VERIFIABLE = YES
AND HANDOFF_SCOPE_IS_CLEAR = YES
AND EXPECTED_COST_SAVING > COORDINATION_OVERHEAD
→ MULTIAGENT_ALLOWED
```

Inteligência cara deve permanecer no hotspot cognitivo.

Trabalho bounded e verificável deve ser avaliado para tier inferior.

Entretanto:

```text
G6_TECHNICALLY_ELIGIBLE
!=
G6_ECONOMICALLY_JUSTIFIED
```

Antes de converter G6 em `MULTIAGENT`, também exigir:

```text
OFFLOAD_MATERIALITY_GATE = PASS
```

Quando houver hotspot cognitivo seguido de materialização fechada, avaliar
explicitamente:

```text
COGNITIVE_MECHANICAL_SPLIT_GATE = PASS | FAIL
```

Sem materialidade suficiente:

```text
EXECUTION_MODE = DIRECT
```

mesmo que um tier inferior seja perfeitamente capaz de executar a etapa.

---

## 10. Redundancy Gate

Antes de criar subagente:

```text
DOES_ROOT_ALREADY_COVER_THIS_ROLE_SUFFICIENTLY?
```

Se sim, exigir pelo menos um:

```text
INDEPENDENCE_REQUIRED = YES
DISTINCT_SPECIALIZATION_GAIN = YES
MATERIAL_ECONOMIC_GAIN = YES
MATERIAL_RISK_REDUCTION = YES
```

Senão:

```text
DO_NOT_SPAWN
```

Regra:

```text
DO_NOT_DUPLICATE_EXPENSIVE_INTELLIGENCE_WITHOUT_DISTINCT_VALUE
```

---

## 11. Papéis funcionais e seleção de runtime

Os identificadores abaixo representam responsabilidades funcionais. A família de modelo, reasoning effort e tool surface são campos independentes e refletem a seleção real do runtime apenas quando essa superfície os expõe ou os configura.

```text
Campos de roteamento separados:
AGENT_ROLE = responsabilidade funcional
MODEL_TARGET = família de modelo recomendada pela demanda de capacidade
RUNTIME_MODEL = modelo efetivamente resolvido, se reportado; senão INHERITED ou UNKNOWN
REASONING_EFFORT = valor recomendado separadamente pela demanda de deliberação
TOOL_SURFACE = ferramentas/capabilities efetivamente disponíveis

AGENT_ROLE != MODEL_TARGET
MODEL_TARGET != RUNTIME_MODEL
MODEL_TARGET != REASONING_EFFORT
REASONING_EFFORT != TOOL_SURFACE
```

| Papel funcional | Heurística de rota (quando material; não vinculada ao papel) | Superfície a confirmar |
|---|---|---|
| SCOUT | selecionados conforme demanda | leitura do escopo |
| RESEARCHER | selecionados conforme demanda | pesquisa externa disponível |
| VALIDATOR | selecionados conforme demanda | comandos/checks necessários |
| TRIAGE_ANALYST | selecionados conforme demanda | logs/evidências necessários |
| MECHANICAL_IMPLEMENTER | selecionados conforme demanda | escrita bounded no ownership |
| SCRIBE | selecionados conforme demanda | escrita documental bounded |
| IMPLEMENTER | selecionados conforme demanda | ferramentas e escrita do escopo |
| REVIEWER | selecionados conforme demanda | leitura do delta/authorities |
| SECURITY_REVIEWER | selecionados conforme demanda | ferramentas de análise requeridas |
| ARCHITECTURE_REASONING | MODEL_TARGET Sol com effort High é heurística de governança | authorities e artefatos relevantes |

O modelo/effort recomendado é decisão de roteamento, não uma propriedade do papel. Se o runtime não confirmar o target solicitado, usar RUNTIME_SELECTED, INHERITED ou UNKNOWN e não declarar tier saving.

### 11.1 Mechanical Implementer

Somente quando:

```text
SOLUTION_CLOSED = YES
INVARIANTS_CLOSED = YES
SCOPE_BOUNDED = YES
OWNERSHIP_CLEAR = YES
OBJECTIVE_VALIDATION_AVAILABLE = YES
MATERIAL_NET_GAIN = YES
```

### 11.2 Implementer

Use Sol quando ainda houver:

- julgamento técnico;
- integração;
- interpretação local;
- escolhas de implementação;
- entendimento de fluxo.

### 11.2.1 Scribe

```text
SCRIBE_RECORDS_DECISIONS
SCRIBE_DOES_NOT_CREATE_DECISIONS
```

`scribe / High` é preferido para materialização documental bounded quando
o conteúdo já foi decidido por um ROOT suficiente.

Pode executar:

- documentação factual;
- `PROJECT_STATE`;
- roadmap;
- sprints;
- changelog;
- atualização de referências;
- reconciliação textual factual;
- formatação de conteúdo normativo já fechado;
- materialização física de uma Authority já definida.

Materialização física de Authority é permitida somente quando:

```text
AUTHORITY_PHYSICAL_AUTHORING_BY_SCRIBE = ALLOWED

ONLY_IF:

NORMATIVE_CONTENT_CLOSED = YES
DECISIONS_CLOSED = YES
INVARIANTS_CLOSED = YES
STRUCTURE_DEFINED = YES
UNRESOLVED_SEMANTIC_CHOICES = NONE
OWNERSHIP_CLEAR = YES
```

O Scribe pode **escrever uma decisão já tomada**.

O Scribe não pode **inventar a decisão**.

Se encontrar qualquer escolha material não prescrita:

```text
STOP_AFFECTED_SCOPE
RETURN_TO_ROOT
```

### 11.3 Validator

```text
VALIDATOR_VALIDATES
VALIDATOR_DOES_NOT_IMPLEMENT
VALIDATOR_ELIGIBLE != VALIDATOR_REQUIRED
```

Ferramentas podem gerar artefatos transitórios:

```text
TECHNICAL_WORKSPACE_WRITE_CAPABILITY = ALLOWED_WHEN_REQUIRED
SOURCE_WRITE_AUTHORIZATION = NO
```

#### 11.3.1 Validation Offload Gate

Antes de criar `validator`, exigir:

```text
VALIDATION_OFFLOAD_GATE = PASS
```

O gate só passa se existir volume operacional material ou redução material de
contexto/custo do ROOT.

Sinais favoráveis incluem pelo menos um:

```text
LONG_RUNNING_TEST_SUITE = YES
LARGE_LOG_VOLUME = YES
LARGE_DATASET_SCAN = YES
MANY_INDEPENDENT_VALIDATION_OPERATIONS = YES
ROOT_CONTEXT_POLLUTION_IS_MATERIAL = YES
ROOT_TIME_SAVED_IS_MATERIAL = YES
```

e também:

```text
EXPECTED_VALIDATION_OFFLOAD_GAIN
>
HANDOFF_COST
+ DUPLICATED_CONTEXT_COST
+ RECONCILIATION_COST
```

Se não:

```text
VALIDATION_OFFLOAD_GATE = FAIL
→ ROOT_VALIDATES_DIRECTLY
```

#### 11.3.2 Micro Validation Bundle

As seguintes operações, isoladamente ou em pequeno conjunto, não constituem
ganho material de offload:

```text
MICRO_VALIDATION_BUNDLE =
git status
+ git diff
+ git diff --check
+ git rev-parse
+ git rev-list
+ small TOML parse
+ file existence checks
+ filename / identity checks
+ small registry consistency checks
+ staged scope inspection
```

Regra padrão:

```text
MICRO_VALIDATION_BUNDLE
→ DIRECT_ROOT_EXECUTION
```

Em particular:

```text
ROUTINE_GIT_CHECKS
+
SMALL_CONFIG_PARSE
+
SMALL_FILE_IDENTITY_CHECKS

DO_NOT_CONSTITUTE_MATERIAL_VALIDATION_OFFLOAD_GAIN
BY_THEMSELVES
```

Não criar Validator apenas porque os checks são objetivos.

### 11.4 Reviewer

```text
IMPLEMENTATION_COMPLETE != REVIEWER_REQUIRED
```

Se:

```text
ROOT_CAPABILITY >= REVIEW_REQUIREMENT
AND INDEPENDENT_REVIEW_REQUIRED = NO
```

então:

```text
ROOT_SELF_REVIEW = YES
REVIEWER = NO
```

### 11.5 Triage

```text
TEST_FAIL != TRIAGE_REQUIRED
```

Triage só entra com ganho diagnóstico material.

---

# PARTE IV — SKILLS, PLUGINS E EXECUÇÃO NATIVA

## 12. Taxonomia

```text
CAPABILITY != SKILL
SKILL != PLUGIN
PLUGIN_MAY_CONTAIN_SKILLS = YES
SKILL_MAY_EXIST_WITHOUT_PLUGIN = YES
NAME_SYNTAX_DOES_NOT_DEFINE_CLASS = YES
```

Capacidade nativa = função já disponível diretamente.

Skill = workflow, procedimento ou guidance reutilizável.

Plugin = recurso empacotado que pode fornecer skill, app, template, ferramenta ou integração.

Nenhum transfere authority.

---

## 13. Native-first

```text
NATIVE_EXECUTION = PREFERRED_WHEN_SUFFICIENT

PLUGIN_INSTALLED != PLUGIN_REQUIRED
SKILL_AVAILABLE != SKILL_REQUIRED

USE_ONLY_WITH_MATERIAL_BENEFIT = YES
TOOL_SPRAWL = PROHIBITED
```

Se nativo for suficiente:

```text
NATIVE_EXECUTION_SUFFICIENT = YES
SKILL = NONE
PLUGIN = NONE
```

---

### 13.1 Semântica de runtime multiagente

```text
ORCHESTRATION_RUNTIME = NATIVE | EXTERNAL | MANUAL
MODEL_TOPOLOGY = HOMOGENEOUS | HETEROGENEOUS

NATIVE_MULTIAGENT = shorthand for ORCHESTRATION_RUNTIME = NATIVE
HETEROGENEOUS_MULTIAGENT = shorthand for MODEL_TOPOLOGY = HETEROGENEOUS
NATIVE_MULTIAGENT AND HETEROGENEOUS_MULTIAGENT = COMPATIBLE_AXES

RESPONSES_MULTIAGENT = NATIVE + HOMOGENEOUS
  when the request model is shared by root and subagents
CODEX_CUSTOM_SUBAGENT_MODELS = NATIVE + HETEROGENEOUS
  when per-worker models are explicitly configured and runtime-confirmed

TIER_SAVING_CLAIM = REQUIRES_ACTUAL_RUNTIME_MODEL_EVIDENCE
ROLE != MODEL != EFFORT != TOOL_SURFACE
```

`NATIVE_MULTIAGENT` e `HETEROGENEOUS_MULTIAGENT` não são categorias mutuamente
exclusivas: a primeira descreve quem orquestra e a segunda descreve a topologia de
modelos. `EXTERNAL` descreve um loop de orquestração fora do harness nativo e `MANUAL`
descreve handoff controlado por usuário/operador. Uma superfície nativa pode
compartilhar modelo e ferramentas entre agentes ou aplicar outra herança. Não
generalizar comportamento entre Agents API, Responses Multi-agent, Codex e Work.
Papel funcional não prova capability; verificar a tool surface necessária antes de
delegar. Defaults de concorrência permanecem runtime-discovered/configurable.
Neste documento, NATIVE_EXECUTION na seção 13 significa preferência por ferramentas/plataformas integradas quando suficientes; não identifica a modalidade de delegação multiagente.

## 14. Skills

Classificar apenas com evidência da superfície/runtime/documentação/catálogo
operacional aplicável.

Sem confirmação:

```text
SKILL_AVAILABILITY = VERIFY_AT_RUNTIME
```

Não inventar Skill.

`NONE` é decisão válida.

---

## 15. Plugins

Plugin só deve ser recomendado quando acrescentar capability material que o
nativo ou a Skill escolhida não fornecem adequadamente.

```text
PLUGIN_USE =
NONE
| OPTIONAL_IF_MATERIAL
| REQUIRED
```

Regra:

```text
PLUGIN_CAPABILITY != WRITE_AUTHORIZATION
CAPABILITY != PERMISSION
```

Se o ambiente exigir ação explícita do usuário para conectar/invocar o Plugin,
o prompt gerador deve informar isso no Card A.

Não inserir no payload do executor instruções sobre Plugins que não serão usados.

---

# PARTE V — FORMATO OBRIGATÓRIO DE SAÍDA

## 16. CARD A — EXECUTION DECISION CARD

Este card é para o usuário. Deve aparecer no início da resposta e permanecer curto.

AMBIENTE = CODEX | WORK
ROOT_ROLE = ROOT_ORCHESTRATOR
MODEL_TARGET = <modelo sugerido pela governança>
RUNTIME_MODEL = <runtime reportado | inherited | unknown>
REASONING_EFFORT = <target e runtime resolvido separados>
TOOL_SURFACE = <superfície/ferramentas efetivamente disponíveis ou unknown>
EXECUTION_MODE = DIRECT | MULTIAGENT
ORCHESTRATION_RUNTIME = NATIVE | EXTERNAL | MANUAL | UNKNOWN
MODEL_TOPOLOGY = HOMOGENEOUS | HETEROGENEOUS | UNKNOWN
SUBAGENTS = <papéis funcionais usados ou NONE>
FLOW = <opcional>
SKILL = <NONE | nome + uso>
PLUGIN = <NONE | nome + uso>
ESCALATION = <regra curta>
COPY_TO_EXECUTOR = CARD B ONLY

### 16.1 Rationale no Card A

Adicionar no máximo uma justificativa curta quando materialmente útil.

Exemplo:

```text
RATIONALE =
Sol/High fecha o hotspot; Luna/Medium ou High executa validação objetiva.
```

Não despejar no card:

- G1–G6;
- rejected alternatives;
- score de risco;
- long model rationale;
- policy history.

### 16.2 Sol/Astra

Se Sol ou Astra forem selecionados, Card A deve acrescentar somente o motivo
mínimo necessário:

```text
ESCALATION_REASON =
<1–2 linhas>
```

A análise completa do gate permanece interna.

---

## 17. CARD B — EXECUTOR PAYLOAD

O Card B é o contrato de execução enviado ao Codex/Work. Incluir somente os campos aplicáveis:

AMBIENTE = CODEX | WORK
IDIOMA = pt-BR
ROLE = <responsabilidade funcional do root>
MODEL_TARGET = <somente quando a política indicar um target>
RUNTIME_MODEL = <reportado | herdado | desconhecido>
REASONING_EFFORT = <target e valor resolvido separados quando observáveis>
TOOL_SURFACE = <ferramentas efetivamente disponíveis, se material>

OBJETIVO
<resultado concreto>

AUTHORITIES
<somente authorities que o executor precisa consultar>

ESCOPO AUTORIZADO
<ações, arquivos ou superfícies permitidos>

NÃO ESCOPO
<somente proibições materialmente plausíveis>

INVARIANTES / CONTRATOS
<somente os necessários>

ATIVIDADE
<passos executáveis>

DELEGAÇÃO
<somente se MULTIAGENT; campos funcionais e runtime conforme a seção 20>

VALIDAÇÃO
<comandos e critérios realmente necessários>

GIT / AÇÕES EXTERNAS
<permissões e proibições pertinentes>

STOP CONDITIONS
<condições reais de parada>

RETORNO
<incluindo ACTIVITY_COMPLETION_PERCENT para a atividade do prompt e COMPLETION_BASIS quando aplicável>

Se uma seção não for relevante, omitir. Não preencher com NONE só para manter o template.

## 18. Minimal Payload Rule

O Card B não é um relatório de governança.

É um contrato de execução.

Aplicar:

```text
MINIMUM_SUFFICIENT_EXECUTOR_CONTEXT = REQUIRED
```

O gerador deve procurar remover, não adicionar, informação.

Antes de finalizar:

```text
FOR_EACH_PARAGRAPH:
    DOES_THIS_CHANGE_EXECUTION?
    IF NO:
        DELETE_OR_MOVE_TO_CARD_A_IF_USER_RELEVANT

    CAN_THIS_BE_EXPRESSED_ONCE_AS_A_HIGHER_LEVEL_BOUNDARY?
    IF YES:
        COLLAPSE_DETAIL
```

O gerador deve preferir uma boundary semântica compacta quando ela preservar o
mesmo comportamento operacional.

Exemplo:

```text
SCIENTIFIC_EXECUTION = OUT_OF_SCOPE
```

é preferível a repetir uma longa lista de operações científicas proibidas quando
todas representam a mesma fronteira e nenhuma exige tratamento individual.

---


## 18.1 GPT-6 Context Diet

Aplicar carregamento seletivo para reduzir contexto irrelevante e evitar instruções redundantes ou conflitantes.

GPT6_CONTEXT_DIET = REQUIRED
LOAD_ONLY_MATERIAL_AUTHORITIES
REFERENCE_BEFORE_REPRODUCE
DO_NOT_INJECT_FULL_POLICY_STACK_BY_DEFAULT
DO_NOT_RELOAD_ALREADY_VALID_CONTEXT

Carregar policy, AGENTS.md, skill ou histórico quando forem materiais para a tarefa; preferir referência por caminho e disclosure progressiva. Não transformar esta regra em obrigação de ler o repositório inteiro ou todas as policies em cada atividade.
## 19. Proibições do Card B

Não inserir automaticamente:

```text
TASK_CLASS
RISK
COGNITIVE_COMPLEXITY
OPERATIONAL_VOLUME
VERIFIABILITY
REVERSIBILITY

ROUTINE_EXECUTION_GATE
ASTRA_SELECTION_GATE
ARCHITECTURE_ESCALATION_PROTOCOL

PARALLEL_INDEPENDENT_FRONTS
DISTINCT_SPECIALIZATION_REQUIRED
MATERIAL_DECOMPOSITION_GAIN
MATERIAL_INTELLIGENCE_ROUTING_GAIN

EXPECTED_MATERIAL_GAIN
COORDINATION_COST
DUPLICATED_CONTEXT_COST

ROOT_CAPABILITY_REDUNDANCY_CHECK
REDUNDANCY_GATE_ANALYSIS

MODEL_SELECTION_REASON
WHY_LUNA_IS_NOT_SUFFICIENT
WHY_SOL_IS_NOT_SUFFICIENT

WHY_ROOT_SHOULD_NOT_DO_THIS_WORK
EXPECTED_ECONOMIC_GAIN
```

Esses itens permanecem internos ou no Card A de forma condensada.

Exceção: inserir um deles somente quando seu valor for necessário para uma
decisão que o executor terá de tomar durante a atividade.

---

## 20. Delegação compacta no Card B

Quando MULTIAGENT já estiver autorizado para o escopo, o root pode criar subagentes
bounded que passem o gate sem pedir aprovação por spawn individual. Uma mudança de
DIRECT para MULTIAGENT durante a execução continua a exigir parada segura e
autorização do usuário conforme 28.4.

```text
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
```

Para cada subagente, manter somente o contrato necessário à tarefa:

ROLE = <responsabilidade funcional>
OBJECTIVE = <objetivo estreito>
OWNERSHIP = <recurso/escopo>
MODEL_TARGET = <opcional; apenas se configurável>
RUNTIME_MODEL = <confirmed | inherited | unknown>
REASONING_EFFORT = <target e resolvido separados quando observáveis>
REQUIRED_TOOL_SURFACE = <capacidade necessária>
TOOL_SURFACE_VERIFIED = YES | NO | UNKNOWN
WRITE_MODE = <somente quando houver escrita>
RETURN = <evidência mínima>
STOP_OR_ESCALATE = <somente se material>

`MODEL_TOPOLOGY = HETEROGENEOUS` requer configuração explícita por worker confirmada
pelo runtime. Em delegação nativa que herda o modelo da requisição, registrar
`MODEL_TOPOLOGY = HOMOGENEOUS` quando isso estiver confirmado; não alegar economia
de tier sem `ACTUAL_RUNTIME_MODEL_EVIDENCE`.

RECURSIVE_DELEGATION = DISABLED_BY_DEFAULT
Permitir somente com ganho material de paralelismo, tarefa bounded, ownership claro, orçamento dentro do limite runtime e suporte recursivo verificado. Não usar limites globais fixos: descobrir a concorrência efetiva da superfície e configurá-la para esta atividade.

Antes da delegação, verificar a tool surface requerida pelo papel. A resolução de
capability deve preferencialmente ocorrer na resolução de sessão, configuração ou
papel e pode ser reutilizada enquanto runtime e configuração permanecerem estáveis.
Isso não elimina a verificação da tool surface exigida antes de delegar.

```text
REGISTERED_ROLE != GUARANTEED_RUNTIME_CAPABILITY
BEFORE_DELEGATION = VERIFY_REQUIRED_TOOL_SURFACE
RUNTIME_CAPABILITY_RESOLUTION = SESSION_CONFIG_ROLE_RESOLUTION_PREFERRED
CAPABILITY_RESOLUTION_REUSE = ALLOWED_WHILE_RUNTIME_AND_CONFIGURATION_STABLE
RUNTIME_CAPABILITY_RESOLUTION != PER_SPAWN_HUMAN_GATE
```

Se a capability ou a tool surface necessária permanecer desconhecida, não assumir que
está disponível: adaptar a tarefa ou mantê-la no root.

```text
PROVIDER_DOCUMENTATION_DIVERGENCE
→ VERIFY_RUNTIME_AND_MODEL_CAPABILITY
UNKNOWN_CAPABILITY
→ DO_NOT_ASSUME
```

## 21. Authorities compactas

Não copiar documentos canônicos extensos.

Preferir:

```text
AUTHORITIES_TO_READ
1. <path> — ler somente <seção/tema>
2. <path> — usar como authority para <decisão>
```

Se um valor exato for gate:

```text
EXPECTED_VALUE =
<valor>
```

pode ser incluído diretamente.

---

## 22. Background filter

Contexto histórico só entra no Card B se alterar a execução atual.

Não incluir por padrão:

- história da sprint;
- commits antigos sem efeito no baseline atual;
- decisões superadas;
- tentativas anteriores já irrelevantes;
- narrativa de como a arquitetura evoluiu;
- explicações para o usuário compreender o projeto.

Codex/Work precisa de estado operacional atual, não de biografia do projeto.

---

## 23. Negative-boundary filter

Não listar dezenas de proibições genéricas.

Uma proibição entra somente se:

```text
ACTION_IS_PLAUSIBLE_IN_THIS_TASK = YES
OR CONSEQUENCE_IS_HIGH_IF_MISTAKEN = YES
OR GOVERNANCE_REQUIRES_EXPLICIT_BOUNDARY = YES
```

Exemplo:

Se a tarefa é read-only:

```text
SOURCE_WRITE = PROHIBITED
GIT_CONSEQUENTIAL = PROHIBITED
```

pode bastar.

Não é necessário repetir todas as operações impossíveis ou irrelevantes.

Aplicar também:

```text
BOUNDARY_COLLAPSE_RULE =

IF MULTIPLE_PROHIBITIONS_SHARE_THE_SAME_OPERATIONAL_MEANING
AND INDIVIDUAL_ITEMIZATION_DOES_NOT_CHANGE_BEHAVIOR

THEN
COLLAPSE_TO_ONE_HIGH_LEVEL_BOUNDARY
```

O objetivo é preservar segurança sem transformar o Card B em inventário de tudo
que não deve acontecer.

---

## 24. Validation filter

Enviar validações necessárias e proporcionais ao escopo, materialidade, risco e falha plausível. Mudanças pequenas, reversíveis e de baixo risco não exigem testes ou verificações redundantes; usar checks objetivos focais quando necessários e já disponíveis. Expandir a validação quando a mudança alterar comportamento, contrato, segurança, dados, tiver impacto material de falha ou quando a authority da tarefa exigir.

Não criar uma validação delegada se o handoff e a reconciliação custarem mais que o ganho. Não tratar falha de um teste como necessidade automática de Triage; encaminhar a falha ao root e separar triagem somente se houver ambiguidade e ganho material.

Formato quando houver validação:

VALIDATION
1. <comando ou verificação>
   EXPECTED = <critério>
2. <comando ou verificação>
   EXPECTED = <critério>

Se o ROOT deve interpretar uma divergência:

ON_MISMATCH = REPORT_AND_ADJUDICATE

## 24.1 Activity Completion Reporting

Todo prompt relevante para Work ou Codex deve exigir acompanhamento de conclusão
da **atividade específica daquele prompt**.

```text
ACTIVITY_COMPLETION_PERCENT = <0-100>%
```

A porcentagem representa:

```text
PROMPT_ACTIVITY_PROGRESS
```

e nunca:

```text
PROJECT_PROGRESS
SPRINT_PROGRESS
MILESTONE_PROGRESS
ROADMAP_PROGRESS
```

salvo quando o próprio prompt tiver explicitamente uma dessas unidades como sua
atividade integral.

Princípio:

```text
ACTIVITY_COMPLETION_PERCENT
!=
SUCCESS_PERCENT
```

A porcentagem mede quanto da atividade foi efetivamente percorrido/concluído,
independentemente do resultado ser positivo, negativo ou bloqueado.

### 24.1.1 Coerência com STATUS

Aplicar:

```text
STATUS = PASS
→ ACTIVITY_COMPLETION_PERCENT = 100%
```

como regra normal.

Exceção somente se o próprio contrato admitir `PASS` parcial explicitamente,
o que deve ser raro e declarado.

Para bloqueio:

```text
STATUS = BLOCKED
→ ACTIVITY_COMPLETION_PERCENT = <percentual efetivamente concluído antes do blocker>
```

Para falha:

```text
STATUS = FAIL
→ ACTIVITY_COMPLETION_PERCENT = <percentual efetivamente executado>
```

Uma atividade pode terminar:

```text
STATUS = FAIL
ACTIVITY_COMPLETION_PERCENT = 100%
```

quando todas as etapas previstas foram executadas e o resultado final foi
negativo.

Portanto:

```text
100_PERCENT_COMPLETE
!=
PASS
```

### 24.1.2 Base da porcentagem

A porcentagem deve ser derivada do contrato real da atividade.

Usar, conforme aplicável:

- etapas obrigatórias do prompt;
- gates obrigatórios;
- validações previstas;
- entregáveis requeridos;
- ações autorizadas ainda pendentes;
- critérios de aceite já satisfeitos.

Não calcular com base em:

- tamanho do projeto;
- número total de arquivos do repositório;
- número de tokens;
- tempo decorrido;
- impressão subjetiva genérica.

Quando a atividade possuir fases com pesos muito diferentes, o agente pode usar
ponderação razoável, mas deve evitar falsa precisão.

Preferir incrementos coerentes com marcos materiais.

Exemplo:

```text
PREFLIGHT = COMPLETE
INSPECTION = COMPLETE
IMPLEMENTATION = NOT_STARTED
VALIDATION = NOT_STARTED

ACTIVITY_COMPLETION_PERCENT = 40%
```

A política não exige aritmética exata quando o trabalho não possuir decomposição
natural; exige apenas estimativa operacional consistente e explicável.

### 24.1.3 Completion Basis

Sempre que:

- `STATUS != PASS`;
- percentual for inferior a `100%`;
- o cálculo não for autoexplicativo;
- houver blocker;
- houver diferença material entre execução e sucesso;

incluir:

```text
COMPLETION_BASIS =
<breve explicação objetiva do que foi concluído e do que resta>
```

`COMPLETION_BASIS` deve ser curto e factual.

Exemplo:

```text
STATUS = BLOCKED
ACTIVITY_COMPLETION_PERCENT = 65%
COMPLETION_BASIS =
Baseline, inspeção e validação concluídos; implementação não iniciada
devido a conflito de authority.
```

### 24.1.4 Atualizações intermediárias

Quando Work/Codex emitir atualizações de progresso durante uma atividade longa,
incluir o percentual apenas em **marcos materiais**, não a cada comando.

Formato preferido:

```text
PROGRESS_UPDATE
ACTIVITY_COMPLETION_PERCENT = <0-100>%
COMPLETION_BASIS = <breve marco atingido e próximo bloco restante>
```

Não criar cadência artificial por tempo ou quantidade fixa de comandos.

```text
PROGRESS_UPDATE_BY_MATERIAL_MILESTONE = YES
PROGRESS_UPDATE_PER_COMMAND = NO
```

Esta regra não introduz:

```text
BOUNDED_CYCLIC_EXECUTION
WORK_UNITS
CYCLE_LEDGER
STRUCTURED_RETRY_LOOP
```

O percentual é apenas telemetria de conclusão da atividade.

---

## 25. Output contract mínimo

Não exigir relatório gigantesco por padrão.

Formato base:

```text
FINAL_REPORT

STATUS =
ACTIVITY_COMPLETION_PERCENT = <0-100>%
COMPLETION_BASIS = <obrigatório quando aplicável>

FILES_CHANGED =
VALIDATIONS =
FINDINGS =
BLOCKERS =
UNAUTHORIZED_CHANGES = YES | NO
GIT_ACTIONS = NONE | <ações autorizadas realmente executadas>
FINAL_VERDICT =
```

`ACTIVITY_COMPLETION_PERCENT` é obrigatório.

`COMPLETION_BASIS` pode ser omitido somente quando:

```text
STATUS = PASS
AND ACTIVITY_COMPLETION_PERCENT = 100%
AND COMPLETION_STATE_IS_SELF_EXPLANATORY = YES
```

Adicionar outros campos apenas quando materialmente necessários.

---

# PARTE VI — REGRAS DE GERAÇÃO

## 26. Fluxo interno do gerador

1. entender objetivo;
2. identificar authority;
3. pontuar as dimensões de `CAPABILITY_DEMAND`;
4. derivar `CAPABILITY_DEMAND_CLASS = C0-C4`;
5. classificar `DELIBERATION_DEMAND = D0-D4`;
6. classificar `EXECUTION_RISK = R0-R4`;
7. identificar a demanda cognitiva remanescente;
8. escolher `MODEL_FAMILY` pela capability demand;
9. escolher `REASONING_EFFORT` pela deliberation demand;
10. escolher o menor ROOT suficiente;
11. identificar hotspots cognitivos;
12. identificar materialização mecânica;
13. identificar validação objetiva;
14. aplicar `COGNITIVE_MECHANICAL_SPLIT_GATE`;
15. avaliar DIRECT;
16. avaliar multiagente e G6;
17. aplicar `OFFLOAD_MATERIALITY_GATE`;
18. se houver validação delegável, aplicar `VALIDATION_OFFLOAD_GATE`;
19. distinguir `ROOT_MUST_READ_SOURCE_TO_MAKE_DECISION` de `ROOT_MUST_REVIEW_FINAL_DELTA`;
20. aplicar Redundancy Gate;
21. escolher subagentes mínimos;
22. avaliar execução nativa;
23. avaliar Skill;
24. avaliar Plugin;
25. montar Card A;
26. construir Card B aplicando `EXECUTOR_RELEVANCE_TEST`;
27. executar uma `PROMPT_COMPRESSION_PASS`;
28. entregar.

Esse fluxo seleciona o roteamento **antes** da execução.

```text
INITIAL_ROUTING_SELECTION
!=
MID_TASK_ROUTING_RECLASSIFICATION
```

Se o executor descobrir insuficiência do ROOT ou necessidade real de mudança do
modo de execução depois do início, aplicar a Seção 28 em vez de reconfigurar
silenciosamente.

---

## 27. Prompt Compression Pass

Antes de entregar Card B:

```text
PROMPT_COMPRESSION_PASS = REQUIRED
```

Verificar:

```text
DUPLICATED_INFORMATION = REMOVE
INTERNAL_REASONING = REMOVE
REJECTED_ALTERNATIVES = REMOVE
UNUSED_CAPABILITIES = REMOVE
GENERIC_POLICY_TEXT = REMOVE
REDUNDANT_PROHIBITIONS = COLLAPSE
CANONICAL_TEXT_AVAILABLE_BY_PATH = REFERENCE
REPEATED_RATIONALE = REMOVE
NON_ACTIONABLE_HISTORY = REMOVE
MICRO_VALIDATION_DELEGATION = REMOVE_IF_NOT_MATERIAL
SAME_EVIDENCE_READER_DUPLICATION = REMOVE_IF_NO_NET_GAIN
HIGH_LEVEL_BOUNDARY_AVAILABLE = COLLAPSE_DETAIL
```

Executar também:

```text
PROMPT_COMPRESSION_QUESTIONS =

1. O ROOT já precisa ler isso de qualquer maneira?
2. Esta informação muda alguma ação concreta?
3. Esta proibição pode ser resumida por uma boundary superior?
4. Este subagente economiza custo total ou apenas desloca um comando curto?
5. Este bloco repete authority que pode ser referenciada por path?
6. O percentual de conclusão mede esta atividade, e não o projeto inteiro?
7. `STATUS`, percentual e `COMPLETION_BASIS` são coerentes entre si?
8. O ROOT está gastando tier alto para materializar algo já decidido?
9. O tier inferior receberia contrato fechado ou teria de redescobrir a solução?
```

Objetivo:

```text
EVERY_REMAINING_LINE
MUST_HAVE_EXECUTION_VALUE
```

---

## 28. Reclassificação de roteamento durante execução

A seleção inicial e a reconfiguração durante execução são eventos diferentes.

```text
INITIAL_MODEL_SELECTION = POLICY_DECISION_BEFORE_EXECUTION
INITIAL_EFFORT_SELECTION = POLICY_DECISION_BEFORE_EXECUTION
INITIAL_EXECUTION_MODE_SELECTION = POLICY_DECISION_BEFORE_EXECUTION

MID_TASK_MODEL_CHANGE = USER_CONTROLLED_RUNTIME_ACTION
MID_TASK_EFFORT_CHANGE = USER_CONTROLLED_RUNTIME_ACTION
MID_TASK_EXECUTION_MODE_CHANGE = USER_CONTROLLED_RUNTIME_ACTION
```

```text
ROUTING_RECOMMENDATION
!=
RUNTIME_RECONFIGURATION
```

O executor pode detectar que o roteamento atual deixou de ser suficiente, mas não
pode alegar que mudou autonomamente seu próprio modelo, effort ou modo de execução.

```text
IN_EXECUTION_ROOT_AUTO_ESCALATION = PROHIBITED
MID_TASK_AUTO_MULTIAGENT_SWITCH = PROHIBITED
MODEL_CHANGE = USER_CONTROLLED
EFFORT_CHANGE = USER_CONTROLLED
EXECUTION_MODE_CHANGE = USER_CONTROLLED
```

Falha causada por input, permission, arquivo, tool, plugin, capability externa ou
authority ausente não constitui automaticamente capability gap.

### 28.1 Root Reclassification Gate

Quando a responsabilidade continua única, avaliar:

```text
CURRENT_ROOT_SUFFICIENCY = PASS | FAIL
```

Se:

```text
CURRENT_ROOT_SUFFICIENCY = FAIL
AND SEPARATE_RESPONSIBILITY_REQUIRED = NO
AND MULTIAGENT_MATERIAL_GAIN = NO
```

então:

```text
ROOT_RECLASSIFICATION_REQUIRED = YES
STOP_AT_SAFE_BOUNDARY = YES
EXECUTION_STATE = WAITING_FOR_USER_ROOT_RECONFIGURATION
```

Escolha da recomendação:

```text
DELIBERATION_GAP = YES
CAPABILITY_GAP = NO
→ RECOMMEND_HIGHER_EFFORT_WITHIN_SUFFICIENT_MODEL_FAMILY

CAPABILITY_GAP = YES
→ RECOMMEND_STRONGER_MODEL_FAMILY
→ THEN_SIZE_EFFORT_BY_DELIBERATION_DEMAND
```

Nunca usar effort extremo para mascarar capability gap.

```text
ROOT_CAPABILITY_GAP
!=
MULTIAGENT_TRIGGER
```

É proibido criar um subagente mais forte apenas para contornar a insuficiência do
ROOT quando a responsabilidade material continua pertencendo ao próprio ROOT.

```text
DO_NOT_COMPENSATE_FOR_INSUFFICIENT_ROOT
BY_SPAWNING_STRONGER_SUBAGENT
WHEN_RESPONSIBILITY_REMAINS_WITH_ROOT
```

### 28.2 Root Reclassification Report

Antes de parar, emitir:

```text
ROOT_RECLASSIFICATION_REPORT

ROOT_RECLASSIFICATION_REQUIRED = YES
CURRENT_ROOT = <model / effort atual>
RECOMMENDED_ROOT = <model / effort recomendado>
TRIGGER = <evidência concreta>
CAPABILITY_CLASS_CURRENT = <C0-C4 quando aplicável>
DELIBERATION_CLASS_CURRENT = <D0-D4 quando aplicável>
WHY_CURRENT_ROOT_IS_INSUFFICIENT = <justificativa objetiva>
WHY_HIGHER_EFFORT_IS_OR_IS_NOT_SUFFICIENT = <deliberation gap vs capability gap>
WHY_THIS_IS_NOT_MULTIAGENT = <responsabilidade única / ausência de material gain>
DECISION_PENDING = <decisão que não deve ser tomada no ROOT atual>
WORK_ALREADY_COMPLETED = <estado factual preservado>
REMAINING_WORK = <trabalho pendente>
SAFE_RESUME_POINT = <ponto preciso de retomada>
USER_ACTION_REQUIRED = Alterar manualmente modelo/esforço do ROOT e confirmar a continuação.
EXECUTION_STATE = WAITING_FOR_USER_ROOT_RECONFIGURATION
```

Depois:

```text
STOP
WAIT_FOR_USER_CONFIRMATION
```

Enquanto aguarda:

```text
MUST_NOT_TAKE_PENDING_DECISION = YES
MUST_NOT_CONTINUE_COGNITIVE_HOTSPOT = YES
MUST_NOT_CLAIM_MODEL_CHANGED = YES
MUST_NOT_SPAWN_AROUND_ROOT_INSUFFICIENCY = YES
```

### 28.3 Retomada após mudança do usuário

Após o usuário confirmar a mudança:

```text
USER_ROOT_RECONFIGURATION_CONFIRMED = YES
```

Se a superfície expuser factual e confiavelmente o ROOT atual:

```text
VERIFY_CURRENT_MODEL_AND_EFFORT = YES
```

Se não expuser:

```text
ROOT_PROFILE_STATE = USER_CONFIRMED_RUNTIME_UNVERIFIED
```

Não alegar verificação inexistente.

Retomar:

```text
RESUME_FROM = SAFE_RESUME_POINT
```

Não repetir preflight, leitura ou validação já válida apenas por causa da troca de
perfil, salvo se:

```text
EVIDENCE_BECAME_STALE = YES
OR CONTEXT_REQUIRED_FOR_SAFE_RESUME = MISSING
OR AUTHORITY_CHANGED = YES
```

### 28.4 Multiagent Reclassification Gate

Uma atividade iniciada `DIRECT` pode revelar nova responsabilidade separável. Isso
não autoriza switch automático.

```text
NEW_SEPARABLE_RESPONSIBILITY = PRESENT
AT_LEAST_ONE_G1_G6_GATE = PASS
OFFLOAD_MATERIALITY_GATE = PASS
SCOPE_PARTITION_IS_CLEAR = YES
EXPECTED_NET_GAIN = MATERIAL
```

Somente então:

```text
MULTIAGENT_RECLASSIFICATION_REQUIRED = YES
MID_TASK_AUTO_MULTIAGENT_SWITCH = PROHIBITED
STOP_AT_SAFE_BOUNDARY = YES
EXECUTION_STATE = WAITING_FOR_USER_MULTIAGENT_AUTHORIZATION
```

Emitir:

```text
MULTIAGENT_RECLASSIFICATION_REPORT
CURRENT_EXECUTION_MODE = DIRECT
TRIGGER = <novo fato observado>
WHY_DIRECT_ROUTE_IS_NO_LONGER_PREFERRED = <justificativa>
MATERIAL_GAIN = <ganho concreto>
PROPOSED_FLOW = <ROOT → ROLE → ROOT etc.>
PROPOSED_RESPONSIBILITIES = <ownership e responsabilidades>
G1 =
G2 =
G3 =
G4 =
G5 =
G6 =
OFFLOAD_MATERIALITY_GATE = PASS
AUTHORITY_BOUNDARIES = <limites>
USER_ACTION_REQUIRED = Autorizar/reclassificar manualmente a atividade para MULTIAGENT.
EXECUTION_STATE = WAITING_FOR_USER_MULTIAGENT_AUTHORIZATION
```

Depois:

```text
STOP
WAIT_FOR_USER_CONFIRMATION
```

Somente após confirmação:

```text
USER_MULTIAGENT_RECLASSIFICATION_CONFIRMED = YES
→ RESUME_FROM_SAFE_RESUME_POINT
```

### 28.4.1 Spawn dentro de MULTIAGENT já autorizado

Depois que MULTIAGENT e o escopo da atividade estiverem autorizados e os gates de benefício, ownership e capability passarem, o root pode abrir subagentes bounded sem autorização humana individual por spawn.

PER_SUBAGENT_USER_APPROVAL = NOT_REQUIRED_WHEN_MODE_AUTHORIZED_SCOPE_BOUNDED_AND_GATE_PASS
SCOPE_EXPANSION_OR_DIRECT_TO_MULTIAGENT_SWITCH = USER_AUTHORIZATION_REQUIRED

RECURSIVE_DELEGATION = DISABLED_BY_DEFAULT. Permitir somente com ganho material de paralelismo, tarefa bounded, ownership claro, orçamento efetivo de concorrência e suporte runtime confirmado. Essa exceção não exige aprovação por spawn se permanecer dentro do modo e escopo autorizados.
### 28.5 Mechanical Scale Is Not Cognitive Complexity

Não recomendar ROOT escalation nem MULTIAGENT apenas por:

```text
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
LARGE_BUT_OBJECTIVELY_VERIFIABLE_WORK
```

```text
MECHANICAL_SCALE
!=
COGNITIVE_COMPLEXITY
```

Grande volume operacional com baixa demanda cognitiva pode justificar offload
econômico somente se os gates aplicáveis passarem; não justifica modelo mais forte
por si só.

### 28.6 De-escalation durante execução

Quando o hotspot termina e o ROOT atual continua suficiente:

```text
CURRENT_ROOT_IS_STILL_SUFFICIENT = YES
```

Se o trabalho remanescente for pequeno:

```text
CONTINUE_CURRENT_ROOT = YES
```

Se uma mudança manual de ROOT reduzir materialmente custo/contexto sem aumentar risco:

```text
ROOT_DEESCALATION_RECOMMENDED = YES
USER_ACTION_REQUIRED = MANUAL_ROOT_RECONFIGURATION
```

De-escalation econômica não deve criar interrupção ritual.

---

## 29. Review

```text
IMPLEMENTATION_COMPLETE != REVIEWER_REQUIRED
```

Se ROOT cobre review e não existe independência obrigatória:

```text
ROOT_SELF_REVIEW = YES
REVIEWER = NO
```

Independent Reviewer só entra quando independência ou ganho distinto real
justificar.

---

## 30. Triage

```text
TEST_FAIL != TRIAGE_REQUIRED
```

Falha autoexplicativa pode ser tratada diretamente pelo ROOT ou executor
apropriado.

---

## 31. Git e ações externas

Prompt não autoriza implicitamente:

- commit;
- push;
- tag;
- release;
- deploy;
- alteração LIVE;
- publicação;
- exclusão externa;
- mensagem externa.

Incluir no Card B apenas os boundaries pertinentes à atividade.

---

# PARTE VII — EXEMPLOS DE SAÍDA

## 32. Exemplo — DIRECT

EXECUTION CARD
AMBIENTE = CODEX
ROOT_ROLE = ROOT_ORCHESTRATOR
MODEL_TARGET = SOL
RUNTIME_MODEL = <confirmar na superfície; senão UNKNOWN>
REASONING_EFFORT = MEDIUM target; runtime value somente se reportado
TOOL_SURFACE = ferramentas de leitura/escrita requeridas pelo escopo
EXECUTION_MODE = DIRECT
ORCHESTRATION_RUNTIME = N/A
MODEL_TOPOLOGY = N/A
SUBAGENTS = NONE

EXECUTOR PAYLOAD

AMBIENTE = CODEX
IDIOMA = pt-BR
ROLE = ROOT_ORCHESTRATOR
MODEL_TARGET = SOL
RUNTIME_MODEL = <reportado | inherited | unknown>
REASONING_EFFORT = MEDIUM target; runtime value somente se reportado
TOOL_SURFACE = verificar somente se o escopo exigir capability adicional

OBJETIVO
Corrigir o mapeamento localizado já especificado.

ESCOPO AUTORIZADO
- editar o formatter;
- ajustar o teste correspondente se necessário.

VALIDAÇÃO
Executar teste focal quando necessário; ampliar somente se a mudança, o risco, uma falha plausível ou a authority justificarem.

GIT / AÇÕES EXTERNAS
Commit/push não autorizados.

RETORNO
Arquivos alterados, validações e resultado final.

## 33. Exemplo — MULTIAGENT econômico

Este exemplo só representa economia de tier quando a superfície confirmar configuração explícita de modelo por worker. Sem essa evidência, usar NATIVE_MULTIAGENT, registrar modelo herdado/desconhecido e não declarar economia de tier.

EXECUTION CARD
AMBIENTE = CODEX
ROOT_ROLE = ROOT_ORCHESTRATOR
MODEL_TARGET = SOL
RUNTIME_MODEL = reportado pela superfície
REASONING_EFFORT = HIGH target; valor runtime separado
EXECUTION_MODE = MULTIAGENT
ORCHESTRATION_RUNTIME = NATIVE
MODEL_TOPOLOGY = HETEROGENEOUS (per-worker config confirmada)
SUBAGENTS = MECHANICAL_IMPLEMENTER, VALIDATOR
PER_SUBAGENT_USER_APPROVAL = NOT_REQUIRED_WHEN_MODE_AUTHORIZED_SCOPE_BOUNDED_AND_GATE_PASS

EXECUTOR PAYLOAD

AMBIENTE = CODEX
IDIOMA = pt-BR
ROLE = ROOT_ORCHESTRATOR
MODEL_TARGET = SOL
RUNTIME_MODEL = reportado pela superfície
REASONING_EFFORT = HIGH target; valor runtime separado
EXECUTION_MODE = MULTIAGENT
MULTIAGENT_MODE_AND_SCOPE = USER_AUTHORIZED

OBJETIVO
Corrigir o cálculo conforme o contrato congelado.

ROOT RESPONSIBILITIES
- fechar a decisão técnica;
- definir invariantes;
- congelar o contrato bounded;
- revisar diff e evidências;
- adjudicar resultado final.

SHARED_DELEGATION_BOUNDARIES
- não ampliar escopo;
- não alterar contrato;
- não executar commit/push;
- não delegar recursivamente sem satisfazer a exceção bounded desta policy.

SUBAGENT
ROLE = MECHANICAL_IMPLEMENTER
MODEL_TARGET = LUNA
RUNTIME_MODEL = explicitamente configurado e confirmado pelo runtime
REASONING_EFFORT = HIGH target; valor runtime separado
REQUIRED_TOOL_SURFACE = escrita nos arquivos do ownership e execução dos checks autorizados
OWNERSHIP = arquivos explicitamente atribuídos pelo ROOT
RETURN = diff summary e arquivos alterados

SUBAGENT
ROLE = VALIDATOR
MODEL_TARGET = LUNA
RUNTIME_MODEL = explicitamente configurado e confirmado pelo runtime
REASONING_EFFORT = MEDIUM target; valor runtime separado
REQUIRED_TOOL_SURFACE = execução das validações e leitura de evidências
OWNERSHIP = validation only
WRITE_MODE = artefatos transitórios; source write prohibited
RETURN = resultados exatos e blockers

VALIDAÇÃO
Executar os checks focais. Ampliar apenas quando a mudança, risco, falha plausível ou authority justificarem.

ON_VALIDATION_FAILURE
Reportar ao ROOT; não criar Triage automaticamente.

RETORNO
Diff final, resultados de validação, blockers e veredicto do ROOT.

## 33.1 Exemplo — checkpoint mecânico fechado

Quando uma nova atividade já recebe:

```text
FILES = EXACT
DIFF_ALREADY_REVIEWED = YES
SCOPE_INTEGRITY = PASS
COMMIT_MESSAGE = DEFINED
SEMANTIC_DECISIONS_REMAINING = NONE
VALIDATION = OBJECTIVE
COMMIT_PUSH_AUTHORIZED = YES
```

o roteamento esperado é:

```text
MODEL_TARGET = LUNA
REASONING_EFFORT = HIGH
EXECUTION_MODE = DIRECT
SUBAGENTS = NONE
```

O fato de existir `commit` e `push` aumenta a importância dos boundaries de
permission e pós-validação, mas não cria por si só demanda cognitiva para Sol.

Se, na mesma atividade, ainda for necessário classificar arquivos, adjudicar diff,
resolver identidade de policy ou interpretar authority:

```text
MODEL_TARGET = SOL
REASONING_EFFORT = MEDIUM
```

## 33.2 Testes de regressão — Cognitive–Mechanical Split

Os modelos e efforts indicados nos cenários abaixo são targets da política. Registrar o modelo/effort realmente resolvido em campos separados sempre que o runtime os expuser; nunca inferi-los pelo papel funcional.

### Teste A — Authority complexa + reconciliação documental material

Entrada:

```text
ARCHITECTURAL_DECISIONS = OPEN
DOCUMENTATION_DELTA = MATERIAL
```

Esperado:

```text
SOL / HIGH ROOT
→ closes Authority / decisions / invariants
→ LUNA / MEDIUM SCRIBE materializes Authority/docs
→ ROOT reviews and adjudicates
```

`MULTIAGENT` é esperado somente se `OFFLOAD_MATERIALITY_GATE = PASS`.

### Teste B — Authority complexa + delta documental mínimo

Entrada:

```text
ARCHITECTURAL_DECISIONS = OPEN
DOCUMENTATION_DELTA = 3 trivial lines
```

Esperado:

```text
ROOT = sufficient higher tier
EXECUTION_MODE = DIRECT
```

Handoff não se paga.

### Teste C — Design fechado + implementação prescrita material

Entrada:

```text
DESIGN_CLOSED = YES
INVARIANTS_CLOSED = YES
IMPLEMENTATION_FILES = 8
IMPLEMENTATION_IS_PRESCRIBED = YES
```

Esperado:

```text
HIGHER_TIER ROOT
→ LUNA / HIGH MECHANICAL_IMPLEMENTER
→ ROOT FINAL REVIEW
```

se o ganho líquido for material.

### Teste D — Implementação ainda contém escolhas técnicas

Entrada:

```text
UNRESOLVED_IMPLEMENTATION_CHOICES = YES
```

Esperado:

```text
DO_NOT_USE_LUNA_WORKER_FOR_DECISION
→ ROOT or SOL_IMPLEMENTER
```

### Teste E — Luna encontra ambiguidade

Entrada:

```text
LOWER_TIER_ENCOUNTERS_UNPRESCRIBED_CHOICE = YES
```

Esperado:

```text
STOP_AFFECTED_SCOPE
→ RETURN_TO_ROOT
→ ROOT_CLOSES_DECISION
→ LOWER_TIER_CONTINUES_ONLY_WITH_CLOSED_CONTRACT
```

## 33.3 Testes de regressão — Mid-Task Routing Reclassification

### Teste F — Luna/High precisa apenas de mais deliberação

```text
CURRENT_ROOT = LUNA / HIGH
DELIBERATION_GAP = YES
CAPABILITY_GAP = NO
SEPARATE_RESPONSIBILITY_REQUIRED = NO

→ RECOMMENDED_ROOT = LUNA / XHIGH
→ ROOT_RECLASSIFICATION_REQUIRED = YES
→ STOP
→ WAIT_FOR_USER_ROOT_RECONFIGURATION
```

Esse teste torna explícito que `Luna/XHigh` pode ser ROOT.

### Teste G — capability gap real de Luna com responsabilidade única

```text
CURRENT_ROOT = LUNA / XHIGH
CAPABILITY_GAP = YES
SEPARATE_RESPONSIBILITY_REQUIRED = NO

→ RECOMMEND_STRONGER_MODEL_FAMILY = SOL
→ SIZE_SOL_EFFORT_BY_DELIBERATION
→ STOP
→ USER_CHANGES_ROOT
→ USER_CONFIRMS
→ RESUME_FROM_SAFE_RESUME_POINT
```

### Teste G2 — decisão arquitetural material excede Sol/High

```text
CURRENT_ROOT = SOL / HIGH
MATERIAL_ARCHITECTURAL_DECISION = YES
SOL_HIGH_CONFIDENCE = INSUFFICIENT

→ RECOMMENDED_ROOT = ASTRA / MEDIUM
→ ROOT_RECLASSIFICATION_REQUIRED = YES
→ STOP_AT_SAFE_BOUNDARY
→ WAIT_FOR_USER_ROOT_RECONFIGURATION
```

### Teste H — nova responsabilidade separável durante DIRECT

```text
CURRENT_EXECUTION_MODE = DIRECT
NEW_SEPARABLE_RESPONSIBILITY = PRESENT
AT_LEAST_ONE_G1_G6_GATE = PASS
OFFLOAD_MATERIALITY_GATE = PASS
EXPECTED_NET_GAIN = MATERIAL

→ MULTIAGENT_RECLASSIFICATION_REQUIRED = YES
→ STOP
→ WAIT_FOR_USER_MULTIAGENT_AUTHORIZATION
```

### Teste I — muito volume mecânico, sem dificuldade cognitiva adicional

```text
MANY_FILES = YES
MECHANICAL_IMPLEMENTATION = YES
CAPABILITY_GAP = NO

→ ROOT_ESCALATION = NO
```

### Teste J — hotspot terminou e restam poucos comandos

```text
CURRENT_ROOT_IS_STILL_SUFFICIENT = YES
REMAINING_WORK = SMALL

→ CONTINUE_CURRENT_ROOT = YES
→ NO_RITUAL_DEESCALATION_STOP
```

---

# PARTE VIII — PRINCÍPIOS FINAIS

## 34. Regras mestres

1. O gerador pode raciocinar amplamente; o executor recebe contexto estreito.
2. Card A é para o usuário; Card B é para Codex/Work.
3. O usuário copia somente Card B.
4. Escolha ROOT antes de subagentes.
5. Modelo, effort, multiagente, Skill e Plugin são decisões independentes.
6. Luna/Sol são a faixa normal; Astra exige escalonamento material.
7. `ROOT_CAN_EXECUTE != ROOT_SHOULD_EXECUTE`.
8. Multiagente não exige paralelismo.
9. G6 permite tiering econômico sequencial.
10. Reviewer não é ritual.
11. Triage não é ritual.
12. Validator não implementa.
13. Delegação não transfere authority.
14. Skills e Plugins não transferem authority.
15. Native-first quando suficiente.
16. Skill disponível não implica Skill necessária.
17. Plugin instalado não implica Plugin necessário.
18. Nenhuma informação entra no Card B sem passar pelo `EXECUTOR_RELEVANCE_TEST`.
19. Authority extensa deve ser referenciada por path, não reproduzida.
20. O Card B deve passar por `PROMPT_COMPRESSION_PASS`.
21. O relatório final deve ser mínimo e suficiente.
22. Commit, push, deploy e ações externas exigem autorização explícita.
23. Bounded Cyclic Execution permanece fora desta revisão.
24. Se o ganho de delegação for incerto, permanecer DIRECT.
25. `OBJECTIVE_WORK != DELEGABLE_WORK`.
26. `VALIDATOR_ELIGIBLE != VALIDATOR_REQUIRED`.
27. Microvalidações de Git/config/identity ficam no ROOT por padrão.
28. Se o ROOT precisa consumir a mesma evidência de qualquer forma, penalizar fortemente o handoff.
29. Todo offload exige `OFFLOAD_MATERIALITY_GATE = PASS`.
30. Toda validação delegada exige `VALIDATION_OFFLOAD_GATE = PASS`.
31. Boundaries semanticamente equivalentes devem ser compactadas quando isso não alterar comportamento.
32. `ROOT_BASELINE != ROOT_FLOOR`.
33. Selecionar ROOT pela demanda cognitiva remanescente.
34. `TASK_IS_GOVERNANCE != SOL_REQUIRED`.
35. `CONSEQUENTIAL_GIT_ACTION != STRONGER_MODEL_REQUIRED`.
36. Luna/High pode ser ROOT de atividade fechada, mecânica e objetivamente verificável.
37. Sol/Medium é baseline técnico quando existe julgamento material que excede a faixa segura de Luna.
38. Mid-task de-escalation só ocorre quando o ganho líquido do handoff for material.
39. `ACTIVITY_COMPLETION_PERCENT` mede somente a atividade específica do prompt.
40. `ACTIVITY_COMPLETION_PERCENT != SUCCESS_PERCENT`.
41. `STATUS = PASS` normalmente implica `ACTIVITY_COMPLETION_PERCENT = 100%`.
42. `STATUS = FAIL` pode coexistir com `ACTIVITY_COMPLETION_PERCENT = 100%`.
43. `STATUS = BLOCKED` deve registrar o percentual efetivamente concluído antes do blocker.
44. `COMPLETION_BASIS` explica objetivamente o que foi concluído e o que resta quando necessário.
45. Atualizações intermediárias de percentual ocorrem por marcos materiais, não por comando.
46. Activity completion reporting não introduz Bounded Cyclic Execution, Work Units ou cycle ledger.
47. `MODEL_FAMILY` é selecionada por `CAPABILITY_DEMAND`.
48. `REASONING_EFFORT` é selecionado por `DELIBERATION_DEMAND`.
49. Authority/validation/review são dimensionados por `EXECUTION_RISK`.
50. Tarefa relacionada a arquitetura não implica Sol/High; decisão arquitetural material implica Sol/High.
51. Ciência e demais domínios continuam sendo classificados por capability/deliberation/risk.
52. Luna/XHigh pode ser ROOT quando Luna continua capability-sufficient e o gap é de deliberação.
53. Luna/XHigh não deve compensar capability gap real.
54. Sol selecionado normalmente tem effort dimensionado separadamente; decisão arquitetural material usa Sol/High por regra específica.
55. `HIGH_TIER_REASONING != HIGH_TIER_MATERIALIZATION`.
56. `DECISION_OWNER != PHYSICAL_WRITER`.
57. `ROOT_FINAL_REVIEW != ROOT_MUST_AUTHOR_THE_DELTA`.
58. `ROOT_MUST_REVIEW_FINAL_DELTA` não constitui duplicated context integral por padrão.
59. Materialização por tier inferior exige decisões, semântica e invariantes fechados.
60. Luna pode escrever uma decisão fechada; Luna não deve inventar a decisão.
61. Ambiguidade material durante materialização retorna ao ROOT.
62. Delegar materialização não significa de-escalonar o ROOT.
63. Cognitive–Mechanical Split continua sujeito a `OFFLOAD_MATERIALITY_GATE`.
64. Se o ganho de Sol/Astra for incerto, usar o menor modelo suficiente.
65. `INITIAL_ROUTING_SELECTION != MID_TASK_ROUTING_RECLASSIFICATION`.
66. `ROUTING_RECOMMENDATION != RUNTIME_RECONFIGURATION`.
67. `IN_EXECUTION_ROOT_AUTO_ESCALATION = PROHIBITED`.
68. `MID_TASK_AUTO_MULTIAGENT_SWITCH = PROHIBITED`.
69. Mudanças mid-task de modelo, effort e execution mode são controladas pelo usuário.
70. `ROOT_CAPABILITY_GAP != MULTIAGENT_TRIGGER`.
71. ROOT insuficiente com responsabilidade única exige recomendação, STOP e confirmação do usuário.
72. Mudança DIRECT → MULTIAGENT durante execução exige gates, material gain, STOP e autorização do usuário.
73. Subagente mais forte não pode contornar insuficiência do ROOT quando a responsabilidade permanece única.
74. `MECHANICAL_SCALE != COGNITIVE_COMPLEXITY`.
75. Após reconfiguração, verificar modelo/effort apenas quando a superfície expuser essa evidência; caso contrário registrar `USER_CONFIRMED_RUNTIME_UNVERIFIED`.
76. Retomar de `SAFE_RESUME_POINT` sem repetir evidência ainda válida.
77. De-escalation econômica não deve interromper atividade pequena quando o ROOT atual continua suficiente.
78. `LUNA_XHIGH_ROOT = ALLOWED` quando Luna continua capability-sufficient.
79. `MATERIAL_ARCHITECTURAL_DECISION = SOL / HIGH`.
80. Se Sol/High for insuficiente em decisão arquitetural material, recomendar `Astra/Medium` via `ROOT_RECLASSIFICATION_REPORT`.
81. Astra High/XHigh/Max somente após insuficiência demonstrada do nível anterior.
82. `MAX_EFFORT_DEFAULT = PROHIBITED`.
83. Preço por token da API não deve ser convertido em multiplicador fixo de franquia Codex/Work.

---

## 35. Estado desta revisão

```text
VERSION = v1.7-R2.6
STATUS = CANONICAL
PREVIOUS_VERSION = v1.7-R2.5
REVISION_TYPE = GPT6_MODEL_ROUTING + AGENT_RUNTIME_ALIGNMENT + ROLE_MODEL_EFFORT_TOOL_SEPARATION + CONTEXT_DIET

CONSOLIDATES_ECONOMIC_MULTIAGENT_ROUTING = YES
CONSOLIDATES_SOL_ASTRA_MODEL_GATES = YES
CONSOLIDATES_SKILL_PLUGIN_NATIVE_TAXONOMY = YES

ANTI_OVERDELEGATION_HARDENING = PRESERVED
OFFLOAD_MATERIALITY_GATE = REQUIRED
VALIDATION_OFFLOAD_GATE = REQUIRED
ROOT_MUST_READ_ANYWAY_PENALTY = INCLUDED
MICRO_VALIDATION_BUNDLE = DIRECT_BY_DEFAULT
ROUTINE_GOVERNANCE_CHECKPOINT = DIRECT_BY_DEFAULT

ROOT_BASELINE_IS_NOT_ROOT_FLOOR = YES
SELECT_ROOT_BY_REMAINING_COGNITIVE_DEMAND = REQUIRED
LUNA_HIGH_ROOT_FOR_CLOSED_MECHANICAL_TASKS = ALLOWED
SOL_MEDIUM_FOR_MATERIAL_TECHNICAL_JUDGMENT = DEFAULT
CONSEQUENTIAL_GIT_DOES_NOT_FORCE_STRONGER_MODEL = YES
MID_TASK_DEESCALATION_REQUIRES_MATERIAL_NET_GAIN = YES

ACTIVITY_COMPLETION_PERCENT_REQUIRED = YES
COMPLETION_BASIS_REQUIRED_WHEN_APPLICABLE = YES
COMPLETION_MEASURES_PROMPT_ACTIVITY_ONLY = YES
COMPLETION_PERCENT_IS_NOT_SUCCESS_PERCENT = YES
MATERIAL_MILESTONE_PROGRESS_UPDATES = ALLOWED
PER_COMMAND_PROGRESS_UPDATES = NO

CAPABILITY_DEMAND_CLASSIFICATION = C0-C4
DELIBERATION_DEMAND_CLASSIFICATION = D0-D4
EXECUTION_RISK_CLASSIFICATION = R0-R4
SIMPLE_SCORE_SUMMATION = PROHIBITED
PEAK_DIFFICULTY_AND_HIGH_DIMENSION_COUNT = REQUIRED
MODEL_FAMILY_SELECTED_BY_CAPABILITY = YES
REASONING_EFFORT_SELECTED_BY_DELIBERATION = YES
VALIDATION_AUTHORITY_SELECTED_BY_RISK = YES
LUNA_XHIGH_ROOT_FOR_DELIBERATION_GAP_WHEN_CAPABILITY_SUFFICIENT = YES
SOL_EFFORT_SELECTED_BY_DELIBERATION = YES
MATERIAL_ARCHITECTURAL_DECISION_SOL_HIGH = YES
SOL_HIGH_TO_ASTRA_MEDIUM_ARCHITECTURE_ESCALATION = YES
MAX_EFFORT_DEFAULT_PROHIBITED = YES

COGNITIVE_MECHANICAL_SPLIT_GATE = REQUIRED_WHEN_APPLICABLE
HIGH_TIER_REASONING_IMPLIES_HIGH_TIER_MATERIALIZATION = NO
SCRIBE_CLOSED_AUTHORITY_MATERIALIZATION = ALLOWED
LOWER_TIER_UNPRESCRIBED_CHOICE = RETURN_TO_ROOT
FINAL_ROOT_REVIEW_IS_FULL_CONTEXT_DUPLICATION = NO
DELEGATING_MATERIALIZATION_IS_ROOT_DEESCALATION = NO

INITIAL_ROUTING_SELECTION_DIFFERS_FROM_MID_TASK_RECLASSIFICATION = YES
IN_EXECUTION_ROOT_AUTO_ESCALATION = PROHIBITED
MID_TASK_AUTO_MULTIAGENT_SWITCH = PROHIBITED
MODEL_CHANGE = USER_CONTROLLED
EFFORT_CHANGE = USER_CONTROLLED
EXECUTION_MODE_CHANGE = USER_CONTROLLED
ROOT_CAPABILITY_GAP_IS_NOT_MULTIAGENT_TRIGGER = YES
ROOT_RECLASSIFICATION_REQUIRES_SAFE_STOP = YES
ROOT_RECLASSIFICATION_REQUIRES_USER_CONFIRMATION = YES
MULTIAGENT_RECLASSIFICATION_REQUIRES_USER_CONFIRMATION = YES
SAFE_RESUME_POINT = REQUIRED_FOR_RECLASSIFICATION
RUNTIME_VERIFICATION_MUST_NOT_BE_INVENTED = YES
MECHANICAL_SCALE_IS_NOT_COGNITIVE_COMPLEXITY = YES

DUAL_AUDIENCE_OUTPUT = YES
EXECUTION_DECISION_CARD = REQUIRED
EXECUTOR_PAYLOAD_CARD = REQUIRED
COPY_ONLY_EXECUTOR_PAYLOAD = YES

EXECUTOR_RELEVANCE_TEST = REQUIRED
PROMPT_COMPRESSION_PASS = REQUIRED
BOUNDARY_COLLAPSE_RULE = INCLUDED
INTERNAL_ROUTING_WORKSHEET_EXPOSED_TO_EXECUTOR = NO

BOUNDED_CYCLIC_EXECUTION = EXCLUDED

AGENT_RUNTIME_RECONCILIATION = COMPLETE
DIRECT_EXECUTION = DEFAULT
PER_SUBAGENT_USER_APPROVAL = NOT_REQUIRED_WHEN_MODE_AUTHORIZED_SCOPE_BOUNDED_AND_GATE_PASS
RECURSIVE_DELEGATION = DISABLED_BY_DEFAULT; BOUNDED_EXCEPTION_ONLY
RUNTIME_CONCURRENCY_LIMIT = DISCOVERED_PER_SURFACE
PROVIDER_DEFAULTS_HARD_CODED = NO
GPT6_CONTEXT_DIET = REQUIRED
AGENT_ROLE_MODEL_EFFORT_TOOL_SURFACE_SEPARATION = REQUIRED
ORCHESTRATION_RUNTIME != MODEL_TOPOLOGY = YES
NATIVE_MULTIAGENT AND HETEROGENEOUS_MULTIAGENT = COMPATIBLE_AXES
TIER_SAVING_CLAIM = REQUIRES_ACTUAL_RUNTIME_MODEL_EVIDENCE
RUNTIME_CAPABILITY_RESOLUTION != PER_SPAWN_HUMAN_GATE
READY_FOR_USER_REVIEW = COMPLETED
CANONICAL_PROMOTION = EXECUTED
```









