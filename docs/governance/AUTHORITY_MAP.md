# Mapa de authorities — projeto_telegram_courses

DOCUMENT_ROLE = ACTIVE_AUTHORITY_MAP  
VERIFIED_AT = 2026-10-05 / America/Sao_Paulo  
PROJECT_ID = projeto_telegram_courses  
PROJECT_CONTINUITY_ROOT = docs/  
GOVERNANCE_BINDING_TARGET = docs/governance/PROJECT_GOVERNANCE_BINDING.json

## Convenção governada de continuidade

Este projeto declara docs/ como raiz equivalente de continuidade, sob PM-01 §12.5 e Opening §5, para preservar os caminhos exigidos pelo usuário. Estado, mapa, record, bootstrap, binding e planejamento ficam dentro dessa raiz, em governance/ e planning/. [START_HERE.md](../START_HERE.md) é o entrypoint de navegação. Não existem segundas cópias ativas de estado/roadmap/sprints. O binding-alvo permanece pendente; Markdown não o substitui.

Identidade, roots dependentes do ambiente e fatos locais: [PROJECT_STATE.md](PROJECT_STATE.md). Authorities de domínio: product/, architecture/ e engineering/.

## Hierarquia e ownership

Sob PM-00 §4: instrução explícita atual do usuário dentro dos mecanismos de governança; authority específica do projeto para fatos/contratos/decisões; Matrix para arquitetura global; subpolicy dentro de seu domínio; protocolo operacional; convenção/template/exemplo. Framework de execução, permissões da sessão e instruções superiores continuam aplicáveis.

Fonte do pedido e aprovações: [APPROVALS_AND_DECISIONS.md](APPROVALS_AND_DECISIONS.md). O Registry resolve identidade/status; o conteúdo normativo pertence a cada policy. Global current não substitui automaticamente pins já adotados.

## Resolver externo e baseline global

Governance root WORK: C:/Users/walacedelgado/PycharmProjects/governanca_de_projetos. Resolver principal desta atividade: ZIPs entregues pelo usuário. Sintaxe archive::member indica a entrada exata no ZIP, sem cópia vendorizada.

Matrix archive: Matriz Unificada de Políticas.zip. Member prefix: Matriz Unificada de Políticas/. Registry: POLICY_REGISTRY.json dentro desse prefixo. Caminhos são pistas de resolução, não identidade universal.

| ID | Versão current | Papel / owner | Member relativo ao prefixo | Integridade |
|---|---|---|---|---|
| PM-00 | 1.0 | governance_matrix / GOVERNANCE_SYSTEM_ARCHITECTURE | Politica-Matriz-de-Governanca-de-Projetos-v1.0.md | PASS |
| PM-01 | 1.0 | project_conduct_policy / PROJECT_EXECUTION_AND_CONTINUITY | policies/PM-01-Conducao-de-Projetos-v1.0.md | PASS |
| PM-02 | 1.7-R2.6 | policy / geração de prompts e roteamento recomendado | policies/Politica-Prompts-Agente-v1.7-R2.6.md | PASS |
| PM-03 | 1.7-R2.3 | policy / DIRECT–MULTIAGENT e delegação | policies/AGENTS-Multiagente-Generico-v1.7-R2.3-Roteamento-Economico.md | PASS |
| PM-04 | 1.2 | policy / skills, plugins e permissões | policies/Politica-de-Uso-de-Skills-e-Plugins-Codex-Work-v1.2.md | PASS; finding de metadata |
| PM-05 | v1 | policy / independência analítica | policies/Independencia-Analitica-Agente-v1.md | PASS |
| VP-01 | v2.0 | validation_protocol / VALIDATION_ONLY | validation/Gate-de-Internalizacao-Operacional-v2.0.md | PASS |

Todos são CANONICAL / ACTIVE, contract 1. Baseline global = GOVERNANCE_BASELINE V1. Os sete hashes exatos conferem com sha256/current_governed_hash do Registry: [SOURCE_INTEGRITY_CHECK.json](evidence/SOURCE_INTEGRITY_CHECK.json). A lista é descoberta global e intenção de adoção; não é substitute do binding nem lista de pins adotados.

PM-04: a interpretação do papel histórico de sua baseline e fontes convergentes estão em APPROVALS_AND_DECISIONS. PM-02/PM-03 anteriores, PM-04 v1.1 e VP-01 v1.0 estão superseded/historical no Registry; não são defaults operacionais.

## Protocolos e schema

ZIPs sob Protocolos para Projetos - Vigente/ no governance root:

| ID / papel | Versão declarada | Entrada principal | Estado verificado |
|---|---|---|---|
| PROJECT_OPENING / abertura | 3.0 CANONICAL / ACTIVE | Protocolo Inicio de Abertura de Projeto 3.0/OPENING_PROTOCOL.md | Texto disponível; exact-byte integrity FAIL |
| CONTINUITY / recuperação | 3.0 CANONICAL / ACTIVE | Protocolo Continuidade Projeto Em Andamento Com Novo Agente 3.0/CONTINUITY_PROTOCOL.md | Texto disponível; exact-byte integrity FAIL |
| Binding schema / contract 1 | schema_version 1.0, Draft 2020-12 | Protocolo Continuidade Projeto Em Andamento Com Novo Agente 3.0/schemas/PROJECT_GOVERNANCE_BINDING.schema.json | JSON parse PASS; exact-byte integrity FAIL |

As cópias extraídas foram verificadas como alternativa de resolução e também divergem dos manifests. Diferença CRLF/LF explica o diagnóstico, mas não satisfaz hash dos bytes exatos. Não houve normalização, atualização de manifest ou adoção silenciosa de hash diferente.

O CONTINUITY_MANIFEST contém PM-02 R2.5 e PM-03 R2.2 como dependências ativas antigas. Para primeira adoção, current global é resolvido por PM-00/Registry; essas dependências antigas não são usadas. Qualquer futuro binding já existente preserva seus pins até migração autorizada. Correção das referências externas não é autorizada nesta atividade.

## Authorities específicas do projeto

| Papel / assunto | Localização canônica dentro de docs/ |
|---|---|
| REQUIREMENTS | [product/REQUIREMENTS.md](../product/REQUIREMENTS.md) |
| ARCHITECTURE / ADR-001–ADR-007 | [architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md) |
| ENGINEERING_FOUNDATION | [engineering/ENGINEERING_FOUNDATION.md](../engineering/ENGINEERING_FOUNDATION.md) |
| ROADMAP | [planning/ROADMAP.md](../planning/ROADMAP.md) |
| EXECUTION_PLAN | [planning/SPRINTS.md](../planning/SPRINTS.md) |
| PROJECT_STATE / safe resume / autorização | [governance/PROJECT_STATE.md](PROJECT_STATE.md) |
| ACTIVE_AUTHORITY_MAP | Este documento |
| APPROVALS_AND_DECISIONS | [governance/APPROVALS_AND_DECISIONS.md](APPROVALS_AND_DECISIONS.md) |
| PROJECT_OPENING_GATE_RECORD / FOUNDATION_REVIEW | [governance/PROJECT_OPENING_GATE.md](PROJECT_OPENING_GATE.md) |
| CONTINUITY_RECORD / LAST_HANDOFF_ATTEMPT | [governance/CONTINUITY_RECORD.md](CONTINUITY_RECORD.md) |
| BOOTSTRAP | [governance/NEW_AGENT_BOOTSTRAP.md](NEW_AGENT_BOOTSTRAP.md) |
| PROJECT_GOVERNANCE_BINDING | governance/PROJECT_GOVERNANCE_BINDING.json — pendente, sem substitute |

## Relação de baseline

PROJECT_ADOPTED_GOVERNANCE = NOT_MATERIALIZED  
GLOBAL_BASELINE_RELATION = UNKNOWN_UNTIL_ADOPTION  
MIGRATION = NOT_REQUESTED  
NO_SILENT_FALLBACK_TO_OLD_VERSION = YES

O protocolo Opening é necessário para reproduzir esta avaliação ainda aberta. Depois do handoff aceito poderá ser preservado como evidência histórica; Continuity permanece como pin operacional pertinente. Não derivar resultado do gate pelo status declarado do pacote.
