# Mapa de authorities — projeto_telegram_courses

DOCUMENT_ROLE = ACTIVE_AUTHORITY_MAP  
VERIFIED_AT = 2026-10-05 / America/Sao_Paulo  
PROJECT_ID = projeto_telegram_courses  
PROJECT_CONTINUITY_ROOT = docs/  
GOVERNANCE_BINDING_TARGET = docs/governance/PROJECT_GOVERNANCE_BINDING.json

## Convenção governada de continuidade

Este projeto declara docs/ como raiz equivalente de continuidade, sob PM-01 §12.5 e Opening §5. Estado, mapa, record, bootstrap, binding e planejamento ficam nessa raiz, em governance/ e planning/. [START_HERE.md](../START_HERE.md) é o entrypoint de navegação. Não existem segundas cópias ativas de estado/roadmap/sprints. O binding JSON está materializado e validado.

Identidade, roots dependentes do ambiente e fatos locais: [PROJECT_STATE.md](PROJECT_STATE.md). Authorities de domínio: product/, architecture/ e engineering/.

## Hierarquia e ownership

Sob PM-00 §4: instrução explícita atual do usuário dentro dos mecanismos de governança; authority específica do projeto para fatos/contratos/decisões; Matrix para arquitetura global; subpolicy dentro de seu domínio; protocolo operacional; convenção/template/exemplo. Framework de execução, permissões da sessão e instruções superiores continuam aplicáveis.

Fonte do pedido e aprovações: [APPROVALS_AND_DECISIONS.md](APPROVALS_AND_DECISIONS.md). O Registry resolve identidade/status; o conteúdo normativo pertence a cada policy. Global current não substitui automaticamente pins já adotados.

## Resolver externo e baseline global

Governance root verificado nesta atividade: `C:\Users\walac\desenvolvimento\governança_de_projetos`, branch `master`, HEAD e `origin/master` em `eb028a3b8ea1df906fd91578259791fcb8bd5b6c`. Resolver: `Matriz Unificada de Políticas/POLICY_REGISTRY.json` e suas current governed sources. Os paths são pistas de resolução; identidade normativa é id + versão + SHA-256.

| ID | Versão current | Papel / owner | Member relativo ao prefixo | Integridade |
|---|---|---|---|---|
| PM-00 | 1.0 | governance_matrix / GOVERNANCE_SYSTEM_ARCHITECTURE | Politica-Matriz-de-Governanca-de-Projetos-v1.0.md | PASS |
| PM-01 | 1.0 | project_conduct_policy / PROJECT_EXECUTION_AND_CONTINUITY | policies/PM-01-Conducao-de-Projetos-v1.0.md | PASS |
| PM-02 | 1.7-R2.6 | policy / geração de prompts e roteamento recomendado | policies/Politica-Prompts-Agente-v1.7-R2.6.md | PASS |
| PM-03 | 1.7-R2.3 | policy / DIRECT–MULTIAGENT e delegação | policies/AGENTS-Multiagente-Generico-v1.7-R2.3-Roteamento-Economico.md | PASS |
| PM-04 | 1.2 | policy / skills, plugins e permissões | policies/Politica-de-Uso-de-Skills-e-Plugins-Codex-Work-v1.2.md | PASS; finding de metadata |
| PM-05 | v1 | policy / independência analítica | policies/Independencia-Analitica-Agente-v1.md | PASS |
| VP-01 | v2.0 | validation_protocol / VALIDATION_ONLY | validation/Gate-de-Internalizacao-Operacional-v2.0.md | PASS |

Todos são CANONICAL / ACTIVE, contract 1. Baseline global e adotado = GOVERNANCE_BASELINE V1. Os sete bytes foram calculados e conferem com identidade, versão e SHA-256 do Registry; os pins adotados estão em [PROJECT_GOVERNANCE_BINDING.json](PROJECT_GOVERNANCE_BINDING.json). [OPENING_RECOVERY_VALIDATION.json](evidence/OPENING_RECOVERY_VALIDATION.json) registra os resultados. PM-04 permanece CANONICAL/ACTIVE v1.2; a metadata `baseline_role` do Registry é um finding e não muda a authority confirmada pelo conteúdo e pelos demais campos normativos.

PM-04: a interpretação do papel histórico de sua baseline e fontes convergentes estão em APPROVALS_AND_DECISIONS. PM-02/PM-03 anteriores, PM-04 v1.1 e VP-01 v1.0 estão superseded/historical no Registry; não são defaults operacionais.

## Protocolos e schema

Pacotes canônicos sob Protocolos para Projetos - Vigente/ no governance root:

| ID / papel | Versão declarada | Entrada principal | Estado verificado |
|---|---|---|---|
| PROJECT_OPENING / abertura | 3.0 CANONICAL / ACTIVE | Protocolo Inicio de Abertura de Projeto 3.0/OPENING_PROTOCOL.md | 13/13 entradas do manifest íntegros; usado nesta abertura, não é pin operacional corrente após handoff |
| CONTINUITY / recuperação | 3.0 CANONICAL / ACTIVE | Protocolo Continuidade Projeto Em Andamento Com Novo Agente 3.0/CONTINUITY_PROTOCOL.md | 4/4 entradas do manifest íntegros; pin adotado e validado |
| Binding schema / contract 1 | schema_version 1.0, Draft 2020-12 | Protocolo Continuidade Projeto Em Andamento Com Novo Agente 3.0/schemas/PROJECT_GOVERNANCE_BINDING.schema.json | Hash/tamanho do manifest PASS; 9/9 refs resolvidas; binding validado |

Os manifests foram comparados com os bytes atuais sem normalização: Opening 13/13 e Continuity 4/4 passaram. O schema atual foi validado como Draft 2020-12 e seus nove refs locais resolveram. O CONTINUITY_MANIFEST lista PM-02 1.7-R2.6 e PM-03 1.7-R2.3; `STALE_ACTIVE_DEPENDENCY_REFERENCES = 0`.

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
| CONTINUITY_RECORD / LAST_HANDOFF | [governance/CONTINUITY_RECORD.md](CONTINUITY_RECORD.md) |
| BOOTSTRAP | [governance/NEW_AGENT_BOOTSTRAP.md](NEW_AGENT_BOOTSTRAP.md) |
| PROJECT_GOVERNANCE_BINDING | [governance/PROJECT_GOVERNANCE_BINDING.json](PROJECT_GOVERNANCE_BINDING.json) — ACTIVE / VALIDATED |
| Technical audit context (non-normative; time-bounded) | [AUDITORIA_TECNICA_2026-10-05](../audit/AUDITORIA_TECNICA_2026-10-05.md) |
| Contrato de implementação S0 — aprovado e ativo; execução S0 autorizada pelo Card B corrente | [S0_IMPLEMENTATION_CONTRACT](../contracts/S0_IMPLEMENTATION_CONTRACT.md), versão 1.0, APPROVED / ACTIVE PARA S0; semanticamente FROZEN; execução S0 autorizada; push corrente autorizado uma vez para continuidade S0 em `work/s0-bootstrap`, sem fechamento ou S1 |

O contrato S0 v1.0 foi aprovado explicitamente pelo usuário após verificação final focada PASS e permanece semanticamente FROZEN. Em decisão posterior registrada no [PROJECT_STATE](PROJECT_STATE.md), o usuário autorizou a execução de S0 por Card B. A autorização de push mais recente é limitada a um checkpoint de continuidade S0 na branch `work/s0-bootstrap`; não autoriza fechamento, release, deployment ou S1.

## Relação de baseline

PROJECT_ADOPTED_GOVERNANCE = GOVERNANCE_BASELINE V1 / contract 1
GLOBAL_BASELINE_RELATION = CURRENT
MIGRATION = NOT_REQUESTED  
NO_SILENT_FALLBACK_TO_OLD_VERSION = YES

O binding adota os sete authorities PM-00–PM-05 e VP-01; Continuity 3.0 é o protocolo operacional adotado. Opening 3.0 foi aplicado e permanece evidência histórica após o handoff, conforme Opening §6. A relação global/adotada é CURRENT.
