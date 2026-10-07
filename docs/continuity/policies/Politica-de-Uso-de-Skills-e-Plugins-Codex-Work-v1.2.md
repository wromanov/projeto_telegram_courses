# Política de Uso de Skills e Plugins OpenAI — Codex + Work
## Versão 1.2 — CANONICAL / ACTIVE

```text
STATUS = CANONICAL
LIFECYCLE = ACTIVE
BASELINE = Politica-de-Uso-de-Skills-e-Plugins-Codex-Work-v1.1.md
BASELINE_ROLE = SUPERSEDED_HISTORICAL_PREDECESSOR
SCOPE = TRANSVERSAL
DOMAIN_SPECIFIC_CONTENT = PROHIBITED
SKILLS_SOURCE_POLICY = OPENAI_FIRST_PARTY_ONLY
PLUGINS_SOURCE_POLICY = OPENAI_PLUGIN_ECOSYSTEM + GOVERNANCE_APPROVAL
CUSTOM_SKILLS = NO
LOCAL_SKILLS = NO
USER_CREATED_SKILLS = NO
CANONICALIZATION = YES
PROMOTION = YES
PROJECT_PROPAGATION = NO
USER_REVIEW_REQUIRED = NO
VERSION = 1.2
PREVIOUS_VERSION = 1.1
NORMATIVE_OWNER = PM-04
REVIEW_SCOPE = CROSS_POLICY_REFERENCE_ALIGNMENT_ONLY
CHANGE_TYPE = CROSS_POLICY_ALIGNMENT_ONLY
SUPERSEDES = 1.1
SUPERSESSION_STATUS = EXECUTED
```

---

# 0. Finalidade

Esta política define **como agentes devem identificar, selecionar, declarar e utilizar capacidades nativas, skills oficiais da OpenAI e plugins disponíveis pelo ecossistema OpenAI sob aprovação de governança** em atividades executadas no Codex e no Work.

O objetivo não é maximizar o uso de plugins ou skills. O objetivo é escolher a **menor capacidade suficiente** que agregue valor material ao trabalho, mantendo:

- clareza operacional;
- rastreabilidade;
- proporcionalidade;
- segurança;
- controle de permissões;
- independência analítica;
- preservação das authorities do projeto;
- ausência de uso silencioso de plugins;
- ausência de invenção de capabilities inexistentes.

A política também estabelece que a identificação de **modelo, esforço, skill e plugin** deve aparecer no **cabeçalho do prompt**, antes do corpo da atividade.

---

# 1. Princípio fundamental

> **Use a menor capacidade suficiente para resolver corretamente a tarefa.**

A ordem normal de decisão é:

```text
TAREFA
  ↓
CAPACIDADE NATIVA É SUFICIENTE?
  ├── YES → executar nativamente
  │         SKILL = NONE
  │         PLUGIN = NONE
  │
  └── NO / existe ganho material
          ↓
EXISTE SKILL OFICIAL OPENAI ADEQUADA?
          ├── YES → considerar skill
          └── NO / insuficiente
                  ↓
EXISTE PLUGIN DISPONÍVEL PELO ECOSSISTEMA OPENAI E APROVADO ADEQUADO?
          ├── YES → verificar disponibilidade e aplicar política de invocação
          └── NO → executar com capacidade nativa disponível ou parar se o plugin for requisito real
```

A existência de uma skill ou plugin **não cria obrigação de uso**.

```text
AVAILABLE != REQUIRED
INSTALLED != SHOULD_USE
PLUGIN != AUTHORITY
SKILL != AUTHORITY
CAPABILITY != PERMISSION
```

---

# 2. Taxonomia oficial de uso

## 2.1 Capacidade nativa

Capacidade nativa é uma função que Codex ou Work já conseguem executar diretamente sem depender de uma skill ou plugin adicional.

Exemplos típicos:

- ler e inspecionar arquivos;
- analisar código;
- implementar;
- corrigir bugs;
- refatorar;
- executar testes;
- revisar código;
- trabalhar com Git local;
- raciocinar sobre arquitetura;
- produzir análise textual;
- editar artefatos quando a superfície nativa oferecer essa função.

Regra:

```text
NATIVE_EXECUTION_SUFFICIENT = YES
→ PREFER_NATIVE_EXECUTION
→ SKILL = NONE
→ PLUGIN = NONE
```

Não utilizar skill ou plugin apenas para ornamentar uma tarefa que já é resolvida de forma simples e segura pela capacidade nativa.

---

## 2.2 Skill

Uma **skill** é um workflow reutilizável que fornece instruções, orientação, padrões, templates, exemplos ou metodologia para ajudar o agente a executar uma classe de tarefa de forma consistente.

Uma skill responde principalmente:

> **Como o agente deve executar esse tipo de trabalho?**

Uma skill pode existir de forma independente ou ser fornecida dentro de um plugin.

```text
SKILL = WORKFLOW / PROCEDURE / GUIDANCE
```

Uma skill **não transfere authority** e não substitui:

- requisitos oficiais;
- arquitetura canônica;
- políticas de segurança;
- regras de domínio;
- critérios de aceite;
- gates;
- autorização humana.

---

## 2.3 Plugin

Um **plugin** é um recurso empacotado/instalável que disponibiliza capabilities para um workflow.

Um plugin pode incluir:

- skills;
- apps conectados;
- app templates;
- ferramentas;
- integrações;
- recursos adicionais do fluxo de trabalho.

Portanto:

```text
PLUGIN != SKILL
PLUGIN MAY_CONTAIN_SKILLS = YES
SKILL MAY_EXIST_WITHOUT_PLUGIN = YES
```

Um plugin responde principalmente:

> **Que capability adicional precisa estar disponível para executar melhor este workflow?**

---

## 2.4 App e integração

Um app pode ser uma integração usada por um plugin para conectar o agente a dados, contas ou ações externas.

O fato de um plugin estar instalado não elimina requisitos próprios do app, como:

- autenticação;
- OAuth;
- permissões;
- role/workspace;
- disponibilidade regional;
- confirmação de escrita.

```text
PLUGIN_INSTALLED != APP_AUTHORIZED
APP_CONNECTED != WRITE_AUTHORIZED
```

---

## 2.5 Templates e workflows fornecidos por plugins

Templates e workflows fornecidos por plugins devem ser tratados conforme sua finalidade concreta.

Exemplo importante:

```text
PLUGIN = Default templates
WORKFLOW/TEMPLATE = Operating Review
```

O template `Operating Review` serve para estruturar um artefato de revisão operacional. Ele **não deve ser confundido automaticamente com uma auditoria técnica de operação**.

Nomes como `System Design`, `Strategy Memorandum`, `Experiment Analysis`, `Design Report`, `Project Kickoff`, `Project Tracker` e `Operating Review` só devem ser tratados como skills/workflows disponíveis quando essa disponibilidade estiver confirmada na superfície atual.

```text
NAME_KNOWN != RUNTIME_AVAILABLE
TEMPLATE_NAME != TECHNICAL_AUTHORITY
```

---

## 2.6 Classificação pela superfície, não pelo nome

Sintaxe, nome de produto, nome de template ou nome de plugin não definem por si
sós a classe de uma capability.

```text
NAME_SYNTAX_DOES_NOT_DEFINE_CLASS = YES
@name != AUTOMATICALLY_PLUGIN
@name != AUTOMATICALLY_SKILL
$name != AUTOMATICALLY_SKILL
PRODUCT_NAME != AUTOMATICALLY_CAPABILITY
TEMPLATE_NAME != AUTOMATICALLY_SKILL
PLUGIN_NAME != CONTAINED_SKILL
```

A classificação deve derivar nesta ordem:

1. metadata/runtime oficial da superfície atual;
2. documentação oficial aplicável;
3. catálogo operacional aprovado/aceito como referência;
4. se ainda houver dúvida, `CLASSIFICATION = VERIFY_AT_RUNTIME`.

Nunca inventar classificação. `RUNTIME / PLATFORM CLASSIFICATION > NAME INFERENCE`.

**ChatGPT Sites / @Sites** deve ser tratado como `NATIVE PRODUCT CAPABILITY`
quando essa for a classificação confirmada na superfície e documentação
correntes. Não é automaticamente skill nem plugin:

```text
CHATGPT_SITES_IS_AUTOMATICALLY_SKILL = NO
CHATGPT_SITES_IS_AUTOMATICALLY_PLUGIN = NO
```

---

# 3. Estratégia vigente: somente recursos oficiais OpenAI

Neste estágio da governança:

```text
SKILLS_SOURCE_POLICY = OPENAI_FIRST_PARTY_ONLY
PLUGINS_SOURCE_POLICY = OPENAI_PLUGIN_ECOSYSTEM + GOVERNANCE_APPROVAL
CUSTOM_SKILLS = NO
LOCAL_SKILLS = NO
USER_CREATED_SKILLS = NO
PLUGIN_AVAILABLE_THROUGH_OPENAI_ECOSYSTEM = POSSIBLE
OPENAI_AUTHORED = DO_NOT_ASSUME
GOVERNANCE_APPROVAL_REQUIRED = YES
PROJECT_FIT_REQUIRED = YES
```

Somente skills disponibilizadas pela própria OpenAI são permitidas nesta fase.
Não criar, recomendar criação ou usar skill local, customizada ou criada pelo
usuário. Para plugins, disponibilidade no diretório/ecossistema OpenAI não
prova autoria pela OpenAI nem dispensa aprovação de governança e aderência ao
projeto. Esta política não expande a allowlist de plugins.

Qualquer futura criação de skill ou plugin próprio exige decisão de governança
específica e autorização explícita do usuário.

---

# 4. Cabeçalho obrigatório dos prompts

## 4.1 Regra de posição

A decisão de **modelo, esforço, skills e plugins deve aparecer no início do prompt**, no mesmo bloco de recomendação de execução.

Ordem recomendada:

```text
1. MODELO
2. ESFORÇO
3. CATEGORIA
4. SKILL
5. PLUGIN
6. EXECUÇÃO NATIVA
7. MULTIAGENTE
8. RESPONSABILIDADE / ESCALONAMENTO
9. IDIOMA
10. OBJETIVO / ESCOPO / AUTHORITIES / GATES / TESTES / RELATÓRIO
```

## 4.2 Cabeçalho normativo

Todo prompt para Work ou Codex deve iniciar, quando aplicável, com estrutura equivalente a:

```text
RECOMENDAÇÃO DE EXECUÇÃO

Modelo principal recomendado: [Luna | Terra | Sol | outro modelo disponível]
Esforço recomendado: [Leve | Médio | Alto | Extra Alto | outro nível disponível]
Categoria: [categoria vigente]
Motivo da escolha: [...]

🧩 SKILLS
SKILL OFICIAL OPENAI RECOMENDADA = [nome | NONE]
SKILL_USE = [NONE | OPTIONAL_IF_MATERIAL | REQUIRED]
SKILL_AVAILABILITY = [CONFIRMED | VERIFY_AT_RUNTIME | UNKNOWN | NOT_REQUIRED]
SKILL_PURPOSE = [...]

🔌 PLUGINS
PLUGIN RECOMENDADO = [nome | NONE]
PLUGIN_USE = [NONE | OPTIONAL_IF_MATERIAL | REQUIRED]
PLUGIN_AVAILABILITY = [CONFIRMED | VERIFY_AT_RUNTIME | UNKNOWN | NOT_REQUIRED]
USER_PLUGIN_INVOCATION = [NOT_REQUIRED | REQUIRED_IF_ACTUALLY_USED | REQUIRED_BEFORE_DEPENDENT_STEP]
PLUGIN_PURPOSE = [...]

⚙️ EXECUÇÃO NATIVA
NATIVE_EXECUTION_SUFFICIENT = [YES | NO | PARTIAL]
NATIVE_EXECUTION_PURPOSE = [...]

Estratégia multiagente: [...]
Responsabilidade pela implementação: [...]
Critério de escalonamento: [...]

IDIOMA OBRIGATÓRIO:
RESPONDA SEMPRE EM PORTUGUÊS DO BRASIL (pt-BR).
```

`NONE` é uma decisão explícita e válida.

---

# 5. Política de uso de skills

## 5.1 Quando usar

Uma skill oficial OpenAI deve ser considerada quando:

- existe workflow claramente alinhado à tarefa;
- o workflow adiciona estrutura material;
- reduz ambiguidade;
- melhora consistência;
- melhora rastreabilidade;
- reduz risco de esquecer etapas relevantes;
- melhora qualidade do artefato;
- ajuda a comparar alternativas de maneira disciplinada;
- melhora análise experimental ou revisão especializada.

## 5.2 Quando não usar

Não usar skill quando:

- capacidade nativa já resolve bem;
- a tarefa é pequena e localizada;
- a skill produziria documentação desnecessária;
- o workflow não corresponde ao problema real;
- o resultado da skill não será utilizado;
- há risco de duplicar source of truth;
- a skill criaria burocracia sem ganho material.

## 5.3 Seleção

Antes de selecionar uma skill:

```text
SKILL_OFFICIAL_OPENAI = YES?
SKILL_AVAILABLE_IN_CURRENT_SURFACE = YES?
SKILL_MATCHES_TASK = YES?
MATERIAL_BENEFIT = YES?
OVERLAP_ACCEPTABLE = YES?
```

Se algum requisito crítico não puder ser confirmado:

```text
SKILL_AVAILABILITY = VERIFY_AT_RUNTIME
```

Nunca inventar a skill.

---

# 6. Política de uso de plugins

## 6.1 Quando usar

Usar plugin aprovado e disponível pelo ecossistema OpenAI quando ele acrescentar capability material que a execução nativa ou skill isolada não fornece adequadamente.

Casos típicos:

- pesquisa multi-pass especializada;
- acesso a repositório remoto;
- acesso a serviço externo;
- segurança especializada;
- design/prototipagem especializada;
- visualização avançada;
- uso de dados autenticados;
- integração com APIs/serviços;
- produção de artefatos fornecidos por plugin;
- ferramenta especializada necessária à atividade.

## 6.2 Quando não usar

Não usar plugin:

- por curiosidade;
- porque está instalado;
- preventivamente sem necessidade;
- quando capability nativa já é suficiente;
- quando outro plugin já cobre o mesmo papel;
- quando exige credenciais/permissões sem necessidade real;
- quando cria risco operacional maior que o benefício;
- quando o serviço externo não é utilizado pelo projeto.

---

# 7. Regra obrigatória de aviso e invocação de plugin

Esta é uma regra explícita da governança.

```text
PLUGIN_ACTUAL_USE_INTENDED = YES
→ AGENT_MUST_NOTIFY_USER = YES
→ USER_PLUGIN_INVOCATION_REQUIRED = YES
→ AGENT_MUST_WAIT_FOR_USER_CONFIRMATION = YES
→ DEPENDENT_STEP_EXECUTION_BEFORE_CONFIRMATION = PROHIBITED

PLUGIN_USE = NONE
→ USER_PLUGIN_INVOCATION = NOT_REQUIRED

PLUGIN_USE = OPTIONAL_IF_MATERIAL
→ USER_PLUGIN_INVOCATION = REQUIRED_IF_ACTUALLY_USED

PLUGIN_USE = REQUIRED
→ USER_PLUGIN_INVOCATION = REQUIRED_BEFORE_DEPENDENT_STEP
```

Sempre que um plugin for efetivamente utilizado, o agente deve informar o
usuário, solicitar a chamada/seleção consciente pelo usuário e aguardar sua
confirmação antes da etapa dependente, mesmo que a plataforma permita seleção
implícita ou automática.

O aviso deve conter:

```text
PLUGIN = <nome>
PLUGIN_USE = REQUIRED | OPTIONAL_IF_MATERIAL
WHY = <motivo objetivo>
AVAILABILITY = CONFIRMED | VERIFY_AT_RUNTIME | UNKNOWN
USER_ACTION = <como selecionar/invocar na superfície atual>
```

## 7.1 Plugin REQUIRED

Se o plugin for necessário:

```text
PLUGIN_USE = REQUIRED
AGENT_NOTIFY_USER = YES
USER_PLUGIN_INVOCATION = REQUIRED_BEFORE_DEPENDENT_STEP
DEPENDENT_STEP_EXECUTION = PAUSE
```

O agente deve solicitar ao usuário que faça a chamada/seleção do plugin e
aguardar confirmação; esta exigência independe de a superfície exigir ou não
seleção manual.

Exemplos de instrução ao usuário:

```text
ChatGPT/Work:
Use @<Nome do Plugin> ou selecione o plugin pelo controle disponível na interface.

Codex task view compatível:
Sources / Fontes
→ Use plugins / Usar plugins
→ selecionar <Nome do Plugin>
```

Após a confirmação do usuário de que o plugin foi chamado/selecionado, a execução da etapa dependente pode continuar.

Se o plugin for REQUIRED e não puder ser disponibilizado:

```text
PLUGIN_REQUIRED = YES
PLUGIN_AVAILABLE = NO
→ STOP_DEPENDENT_STEP
→ REPORT
→ DO_NOT_SIMULATE_PLUGIN
```

Não substituir silenciosamente por outra capability.

## 7.2 Plugin OPTIONAL_IF_MATERIAL

Se o plugin for apenas complementar:

```text
PLUGIN_USE = OPTIONAL_IF_MATERIAL
USER_PLUGIN_INVOCATION = REQUIRED_IF_ACTUALLY_USED
```

Se decidir não usar o plugin, nenhuma chamada é necessária e a execução nativa
é permitida se suficiente. Se decidir efetivamente utilizá-lo, o agente deve
explicar o ganho esperado, solicitar a chamada/seleção pelo usuário e aguardar
confirmação antes da etapa dependente.

Se o plugin não for usado e a capacidade nativa ainda puder produzir resultado adequado:

```text
FALLBACK_TO_NATIVE = ALLOWED
```

O agente deve registrar que o plugin não foi usado.

## 7.3 Proibição de uso silencioso

```text
SILENT_PLUGIN_USE = PROHIBITED
SILENT_REQUIRED_PLUGIN_SUBSTITUTION = PROHIBITED
```

O agente não deve:

- afirmar que utilizou plugin sem evidência;
- simular resultado de plugin;
- esconder que uma conclusão dependeu de plugin;
- presumir que o usuário chamou o plugin;
- usar plugin antes de confirmação do usuário;
- substituir silenciosamente um plugin REQUIRED por outra capability;
- tratar instalação como autorização de escrita;
- tratar plugin instalado como disponível em toda superfície.

---

# 8. Disponibilidade e superfície

A disponibilidade de plugins e skills pode variar por superfície, workspace, plano, função, região, conexão de app e permissões.

```text
PLUGIN_INSTALLED != PLUGIN_AVAILABLE_IN_SURFACE
PLUGIN_AVAILABLE != APP_CONNECTED
PLUGIN_AVAILABLE != WRITE_AUTHORIZED
SKILL_KNOWN != SKILL_AVAILABLE
```

Antes de declarar um plugin indisponível, quando houver mecanismo de Plugin Management disponível, o agente deve verificar o diretório/estado atual.

```text
PLUGIN_UNAVAILABLE_CLAIM
→ PLUGIN_MANAGEMENT_CHECK_REQUIRED
```

salvo quando a indisponibilidade já estiver factual e recentemente confirmada na mesma atividade.

---

# 9. Política de permissões e side effects

Plugins podem adicionar acesso a sistemas externos.

A sequência preferida é:

```text
READ
↓
ANALYZE
↓
PROPOSE
↓
USER CONFIRMATION
↓
WRITE
```

quando aplicável.

Nunca presumir autorização para:

- commit;
- push;
- merge;
- deploy;
- delete;
- migration;
- publicação;
- envio de mensagens;
- alteração de banco;
- mudança de produção;
- criação de recurso pago;
- alteração de billing;
- rotação de secrets.

```text
PLUGIN_CAPABILITY != WRITE_AUTHORIZATION
```

---

# 10. Plugins oficiais de maior valor para o ambiente atual

Esta seção é **referência operacional**, não garantia de disponibilidade permanente.

## 10.1 GitHub

**Serve para:** repositórios, issues, pull requests, reviews, CI/workflows, histórico remoto e evidência factual de source control.

**Usar quando:** a atividade depende de informação ou ação no GitHub.

**Não usar quando:** Git local já resolve completamente a tarefa e o remoto não é necessário.

**Risco:** pode possuir capacidade de escrita.

```text
READ = ALLOWED_WHEN_AUTHORIZED
WRITE = EXPLICIT_AUTHORIZATION
MERGE = EXPLICIT_AUTHORIZATION
DELETE = RESTRICTED
```

## 10.2 Deep Research

**Classificação operacional no contexto Work/Codex:** plugin disponível pelo ecossistema OpenAI para pesquisa multi-pass com evidência e citações.

**Serve para:** estado da arte, pesquisa científica, literatura, benchmark, comparação ampla de soluções, mercado, pesquisa regulatória, documentação dispersa e decisões que dependem de múltiplas fontes externas.

**Usar quando:** pesquisa superficial não é suficiente e a resposta precisa de profundidade, triangulação e citações.

**Não usar quando:** pergunta simples, documentação oficial fácil de localizar, análise de arquivo local, implementação, backtest propriamente dito ou cálculo local sem pesquisa externa.

## 10.3 Default templates

**Serve para:** fornecer templates/workflows oficiais de documentos, apresentações e planilhas.

Pode incluir, conforme disponibilidade atual, `System Design`, `Strategy Memorandum`, `Experiment Analysis`, `Design Report`, `Project Kickoff`, `Operating Review`, `Project Tracker`, dashboards e outros templates.

**Usar quando:** o objetivo é produzir um artefato no formato fornecido pelo template/workflow.

**Não usar como:** substituto automático de metodologia técnica, authority ou gate.

## 10.4 Product Design

**Serve para:** explorar direções de produto, auditar fluxos, prototipar, validar UI/UX antes do código e transformar screenshots/URLs em protótipos revisáveis.

**Usar quando:** existe atividade real de UI/UX, redesign, onboarding, dashboard, fluxo operacional ou protótipo visual.

## 10.5 Codex Security

**Serve para:** workflows especializados de scan, análise e investigação de segurança.

**Usar quando:** houver risco material em autenticação, autorização, filesystem, execução de comandos, secrets, rede, parser/deserialização, criptografia, dependências críticas, release relevante ou trust boundaries.

**Não usar como:** garantia absoluta de segurança ou substituto de threat model, testes adversariais ou pentest quando exigido.

## 10.6 Build Web Data Visualization

**Serve para:** charts, dashboards, mapas, UML, Gantt, relatórios visuais, visualização operacional e interfaces orientadas a dados.

**Usar quando:** dados realmente precisam virar interface, visualização ou diagrama material para decisão/operabilidade.

**Não usar quando:** tabela ou explicação textual simples é suficiente.

## 10.7 OpenAI Developers

**Serve para:** desenvolvimento com OpenAI APIs, Agents SDK e ChatGPT Apps.

**Usar quando:** a atividade envolve diretamente integração com stack OpenAI.

**Não usar preventivamente** quando a atividade não envolve essa stack.

## 10.8 Plugin Management

**Serve para:** descobrir plugins, verificar instalação/disponibilidade, revisar dependências e evitar declaração incorreta de indisponibilidade.

**Usar quando:** um plugin é necessário mas disponibilidade não está confirmada ou o agente está prestes a afirmar que um plugin não existe/não está disponível.

---

# 11. Skills/workflows oficiais de maior valor

Esta seção se refere a workflows/templates oficiais OpenAI **quando efetivamente disponíveis**.

## 11.1 System Design

**Serve para:** estruturar arquitetura, responsabilidades, interfaces, fluxos, trade-offs e riscos.

**Usar quando:** novo subsistema, mudança arquitetural, persistência, concorrência, integração complexa ou mudança difícil de reverter.

**Não usar:** bug localizado, ajuste cosmético ou refatoração trivial.

## 11.2 Strategy Memorandum

**Serve para:** decisão estruturada entre alternativas.

**Usar quando:** existem opções reais com trade-offs relevantes.

**Não usar:** decisão óbvia, pequena e facilmente reversível.

## 11.3 Experiment Analysis

**Serve para:** estruturar hipótese, metodologia, resultados, limitações e conclusão experimental.

**Usar quando:** backtest, benchmark, A/B, ablation, performance, ML, comparação de estratégias ou validação estatística.

**Não usar:** simples execução de teste unitário ou tarefa sem experimento.

## 11.4 Design Report

**Serve para:** findings estruturados de UI/UX/design.

**Usar quando:** há auditoria de experiência, Design System, interface ou fidelidade visual.

## 11.5 Project Kickoff

**Serve para:** estruturar abertura de projeto/fase, objetivos, escopo, riscos e modelo de trabalho.

**Regra de authority:** se existir Project Opening Standard canônico, o standard governa. O template apenas auxilia o artefato.

```text
PROJECT_OPENING_STANDARD > PROJECT_KICKOFF_TEMPLATE
```

## 11.6 Project Tracker

**Serve para:** acompanhar workstreams, milestones, dependências e status.

**Não usar:** se já existe source of truth oficial que cobre a mesma função.

## 11.7 Operating Review

**Serve para:** criar/revisar artefatos periódicos de operação com scorecards, status, riscos, decisões e action items.

**Não confundir com:** auditoria técnica profunda ou final review técnico.

---

# 12. Matriz rápida de decisão

| Situação | Capacidade nativa | Skill/workflow | Plugin |
|---|---|---|---|
| Implementar bug localizado | Principal | NONE | NONE |
| Refatoração simples | Principal | NONE | NONE |
| Decisão arquitetural importante | Parcial | System Design / Strategy Memorandum, se disponível | Default templates, se for o container necessário |
| Pesquisa científica ampla | Parcial | NONE, salvo workflow específico | Deep Research |
| Backtest/experimento formal | Execução | Experiment Analysis, se disponível | Default templates, se necessário para o workflow |
| Prototipagem UI/UX | Parcial | Design Report, se disponível | Product Design |
| Revisão de segurança | Parcial | workflow específico, se disponível | Codex Security |
| Repo/PR/CI remoto | Parcial/local | NONE | GitHub |
| Dashboard/visualização complexa | Parcial | workflow visual, se disponível | Build Web Data Visualization |
| Documento/apresentação estruturada | Parcial | template adequado | Default templates |
| Integração OpenAI API/Agents SDK | Principal para código | NONE | OpenAI Developers |
| Verificar plugin existente | NONE | NONE | Plugin Management |

---

# 13. Combinação skill + plugin

Skill e plugin podem coexistir porque exercem papéis diferentes.

```text
PLUGIN = Default templates
SKILL/WORKFLOW = Experiment Analysis
```

O plugin fornece o pacote/capability. O workflow fornece a estrutura de execução/artefato.

Não combinar múltiplas skills/plugins sem responsabilidade distinta.

Pergunta obrigatória:

> **Cada capability desta combinação resolve um problema diferente e material?**

Se não, simplificar.

---

# 14. Anti-padrões

1. **Plugin porque está instalado** — proibido como justificativa.
2. **Skill por decoração** — não usar para sofisticar artificialmente o prompt.
3. **Deep Research para pergunta simples** — desproporcional.
4. **Template como metodologia** — template não vira gate técnico.
5. **Plugin como authority** — proibido.
6. **Instalar integrações preventivamente** — evitar plugin sprawl.
7. **Uso silencioso de plugin** — proibido.
8. **Simular plugin indisponível** — proibido.
9. **Criar skill local sem decisão específica** — fora do escopo vigente.

---

# 15. Checklist antes de usar skill

- [ ] É oficial OpenAI?
- [ ] Está disponível na superfície atual?
- [ ] Corresponde diretamente à tarefa?
- [ ] A capacidade nativa é insuficiente ou claramente inferior?
- [ ] Existe ganho material?
- [ ] Não duplica outro workflow?
- [ ] Não cria source of truth paralelo?
- [ ] Não transfere authority?
- [ ] O resultado será utilizado?

---

# 16. Checklist antes de usar plugin

- [ ] Está disponível pelo ecossistema OpenAI e aprovado pela governança?
- [ ] Qual problema concreto resolve?
- [ ] A capability nativa já resolve?
- [ ] Está instalado?
- [ ] Está disponível na superfície atual?
- [ ] Precisa conexão/autenticação?
- [ ] Quais dados pode ler?
- [ ] Pode executar writes?
- [ ] Pode gerar custo?
- [ ] Pode alterar produção?
- [ ] Existe plugin sobreposto?
- [ ] O uso agrega valor recorrente/material?
- [ ] O usuário foi avisado?
- [ ] Se será efetivamente utilizado, o usuário confirmou a invocação?

---

# 17. Relatório final da atividade

Quando skill ou plugin forem considerados, o relatório final deve registrar:

```text
MODEL_USED = ...
EFFORT_USED = ...

SKILL_SELECTED = <nome | NONE>
SKILL_USE = <NONE | OPTIONAL_IF_MATERIAL | REQUIRED>
SKILL_ACTUALLY_USED = <YES | NO>

PLUGIN_SELECTED = <nome | NONE>
PLUGIN_USE = <NONE | OPTIONAL_IF_MATERIAL | REQUIRED>
PLUGIN_ACTUALLY_USED = <YES | NO>
USER_PLUGIN_INVOCATION_CONFIRMED = <YES | NO | NOT_REQUIRED>

NATIVE_EXECUTION_USED = <YES | NO | PARTIAL>

CAPABILITY_DECISION_RATIONALE = ...
```

Nunca declarar `PLUGIN_ACTUALLY_USED = YES` sem evidência da utilização real.

---

# 18. Política para tarefas críticas

Em segurança, dinheiro real, produção, migração, autenticação, autorização, persistência, concorrência, disponibilidade, recuperação ou compliance:

```text
SKILL/PLUGIN = AUXILIARY_CAPABILITY
GOVERNANCE_GATES = STILL_REQUIRED
USER_AUTHORIZATION = STILL_REQUIRED_WHEN_APPLICABLE
```

A existência de plugin especializado não elimina validações independentes exigidas pela governança.

---

# 19. Snapshot operacional atual — não normativo

Data de referência: **05/09/2026**.

## Observados como instalados/disponíveis no ambiente consultado

- GitHub — instalado;
- Deep Research — instalado por padrão;
- Default templates — instalado por padrão;
- Product Design — instalado;
- Template Creator — instalado por padrão;
- Plugin Management — capability de governança disponível neste ambiente.

## Recomendados para disponibilidade quando o ambiente permitir

- Codex Security — alto valor para atividades sensíveis de segurança;
- Build Web Data Visualization — alto valor para dashboards, trading, operação, analytics e diagramas.

## On demand

- OpenAI Developers — quando houver atividade real com OpenAI APIs / Agents SDK / ChatGPT Apps;
- Figma — quando Figma for source of truth de design;
- Supabase/Neon — apenas se a arquitetura realmente os utilizar;
- Vercel/AWS — apenas quando a stack exigir;
- Datadog/Honeycomb — quando houver telemetria/observabilidade operacional real;
- Linear/Notion/Atlassian — somente se forem systems of record adotados.

O snapshot não substitui consulta ao Plugin Management.

---

# 20. Alinhamento com a Política de Geração de Prompts

A `Politica-Prompts-Agente-v1.7-R2.6.md` é a authority vigente para geração de prompts multiagente.

Esta versão v1.2 preserva o refinamento de ordem e semântica:

```text
MODELO + ESFORÇO + SKILL + PLUGIN
```

devem aparecer juntos no cabeçalho do prompt.

A PM-04 v1.2 alinha suas referências operacionais à PM-02 R2.6. A versão v1.1 foi supersedida e permanece apenas como registro histórico.

```text
PROMPT_POLICY_SYNC_REQUIRED = NO
PROMPT_POLICY_CURRENT_AUTHORITY = Politica-Prompts-Agente-v1.7-R2.6.md
SYNC_ACTION_AUTHORIZED = YES
CANONICAL_REFERENCE_ALIGNMENT = COMPLETE
SILENT_CROSS_POLICY_DRIFT = PROHIBITED
```

---

# 21. Princípios finais

1. Capacidade nativa primeiro quando suficiente.
2. Skill é workflow; plugin é pacote/capability instalável.
3. Plugin pode conter skills.
4. Skills somente da própria OpenAI; plugins do ecossistema OpenAI exigem aprovação de governança e aderência ao projeto, sem presumir autoria pela OpenAI.
5. Não criar skills/plugins próprios sem nova decisão formal.
6. Todo prompt declara skill e plugin no cabeçalho junto com modelo e esforço.
7. Todo plugin efetivamente utilizado deve ser comunicado ao usuário antes da etapa dependente.
8. A invocação consciente pelo usuário e sua confirmação são exigidas antes de toda etapa dependente, inclusive se a plataforma permitir seleção automática.
9. Uso silencioso de plugin é proibido.
10. Disponibilidade deve ser verificada; nunca inventar capability.
11. Instalação não equivale a autorização de escrita.
12. Skills/templates/plugins não transferem authority.
13. Não empilhar capabilities sem ganho material distinto.
14. Gates e autorizações continuam válidos em tarefas críticas.
15. A menor combinação suficiente é sempre preferível.

---

# 22. Resumo operacional

```text
IMPLEMENTAR / TESTAR / REFATORAR
→ capacidade nativa do Codex

PESQUISA EXTERNA PROFUNDA E CITADA
→ Plugin Deep Research

REPO / PR / ISSUE / CI REMOTO
→ Plugin GitHub

ARTEFATO ESTRUTURADO OFICIAL
→ Plugin Default templates
→ selecionar workflow/template adequado, se disponível

PROTOTIPAGEM / AUDITORIA DE PRODUTO E UI
→ Plugin Product Design

SEGURANÇA ESPECIALIZADA
→ Plugin Codex Security

DASHBOARD / CHART / MAP / UML / VISUALIZAÇÃO COMPLEXA
→ Plugin Build Web Data Visualization

OPENAI API / AGENTS SDK / CHATGPT APPS
→ Plugin OpenAI Developers

VERIFICAR DISPONIBILIDADE DE PLUGIN
→ Plugin Management

PLUGIN NECESSÁRIO
→ AVISAR USUÁRIO
→ SOLICITAR CHAMADA/SELEÇÃO PELO USUÁRIO
→ AGUARDAR CONFIRMAÇÃO
→ EXECUTAR ETAPA DEPENDENTE
```

---

# 23. Fontes de referência

Esta revisão foi construída a partir de:

- `Politica-de-Uso-de-Skills-Codex-Work-v1.0.md` como baseline histórica;
- `Politica-Prompts-Agente-v1.4.md` como referência histórica;
- `Catalogo-Oficial-Skills-Locais-Codex-Governanca-v1.0.md` como material de estudo, sem adoção do programa de skills locais;
- `Catalogo-de-Plugins-e-Capacidades-Codex-Work-v1.0.docx` como referência operacional;
- documentação oficial atual da OpenAI sobre Plugins no ChatGPT e no Codex;
- documentação oficial atual da OpenAI sobre Codex Skills e Plugins.

---

**Versão:** 1.2  
**Status:** CANONICAL / ACTIVE  
**Baseline preservada:** v1.1  
**Canonicalização:** EXECUTADA  
**Revisão do usuário:** concluída por autorização explícita registrada em GOV-01D.

