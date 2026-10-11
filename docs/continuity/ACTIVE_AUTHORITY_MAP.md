# Mapa de authorities ativas — projeto_telegram_courses

```text
DOCUMENT_ROLE = ACTIVE_AUTHORITY_MAP
PROJECT_ID = projeto_telegram_courses
PROJECT_CONTINUITY_ROOT = docs/continuity/
CONTINUITY_ENTRYPOINT = docs/continuity/START_HERE.md
GOVERNANCE_BINDING = docs/continuity/PROJECT_GOVERNANCE_BINDING.json
POLICY = PM-01 v1.0 / CANONICAL / ACTIVE
```

## Authority primária por assunto

| Assunto | Authority primária | Observação |
|---|---|---|
| Estado, gates, autorização, baseline e safe resume | [PROJECT_STATE](PROJECT_STATE.md) | Fonte única do estado corrente |
| Navegação e bootstrap | [START_HERE](START_HERE.md) | Navegação, não um segundo state |
| Roadmap, fases e milestones | [ROADMAP](planning/ROADMAP.md) | Uma authority ativa |
| Plano executável, sprints e gates | [SPRINTS](planning/SPRINTS.md) | Uma authority ativa |
| Continuidade e informações para reassumir | [CONTINUITY_RECORD](CONTINUITY_RECORD.md) | Referencia PROJECT_STATE |
| Procedimento para novo agente | [NEW_AGENT_BOOTSTRAP](NEW_AGENT_BOOTSTRAP.md) | Procedimento, não cópia de authorities |
| Handoff material mais recente | [LAST_HANDOFF](handoff/LAST_HANDOFF.md) | Resume resultado e aponta para authorities |
| Baseline de governança adotado | [PROJECT_GOVERNANCE_BINDING](PROJECT_GOVERNANCE_BINDING.json) | Pins e hashes preservados |
| Aprovações e decisões | [APPROVALS_AND_DECISIONS](../governance/APPROVALS_AND_DECISIONS.md) | Fonte decisória registrada |
| Gate de abertura e evidência | [PROJECT_OPENING_GATE](../governance/PROJECT_OPENING_GATE.md) | Resultado histórico de abertura |
| Requisitos de produto | [REQUIREMENTS](../product/REQUIREMENTS.md) | Authority de domínio |
| Arquitetura e ADRs | [ARCHITECTURE](../architecture/ARCHITECTURE.md) | Authority de domínio |
| Fundação de engenharia | [ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md) | Authority de domínio |
| Contrato de implementação S0 | [S0_IMPLEMENTATION_CONTRACT](../contracts/S0_IMPLEMENTATION_CONTRACT.md) | Contrato aprovado e congelado |
| Contrato de implementação S1-A | [S1A_PROTECTED_SESSION_IMPLEMENTATION_CONTRACT](../contracts/S1A_PROTECTED_SESSION_IMPLEMENTATION_CONTRACT.md) | Proteção local de sessão; frozen for S1-A only |
| Contrato de implementação S1-B | [S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT](../contracts/S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT.md) | Offline auth/gateway; frozen for S1-B only |
| Contrato S1-D | [S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md) | Aprovado e congelado em 2026-10-09 após GOV-01 RESOLVED; aceite funcional e formal PASS; S1-D CLOSED |
| Contrato S2 | [S2_MESSAGE_SCANNER_SQLITE_CONTRACT](../contracts/S2_MESSAGE_SCANNER_SQLITE_CONTRACT.md) | Aprovado e congelado em 2026-10-10; implementação offline e aceite real SQLite PASS; S2 ACCEPTED / CLOSED conforme PROJECT_STATE |
| Contrato S4 | [S4_SINGLE_MEDIA_DOWNLOAD_CONTRACT](../contracts/S4_SINGLE_MEDIA_DOWNLOAD_CONTRACT.md) | Congelado para a primeira mídia de Lesson; S4 ACCEPTED / CLOSED conforme PROJECT_STATE; limites S5–S9 preservados |
| Procedimento de ambiente S0 | [S0_SETUP](../development/S0_SETUP.md) | Instruções; execução exige readiness/autorização |
| Findings técnicos | [AUDITORIA_TECNICA](../audit/AUDITORIA_TECNICA_2026-10-05.md) | Contexto não normativo; risks/gates correntes resolvidos pelo plano |

Authorities externas de políticas/protocolos são resolvidas por identidade,
versão e SHA-256 no binding e pelas fontes governadas fora deste repositório.
PM-01 governa condução e continuidade; ela não substitui requisitos,
arquitetura, contratos ou decisões específicas do projeto.

## Inventário e reconciliação dos caminhos anteriores

| Artefato / caminho anterior | Classificação factual | Caminho canônico | Ação |
|---|---|---|---|
| `docs/governance/PROJECT_STATE.md` | CURRENT_PRIMARY_AUTHORITY; root/HEAD/upstream salvos estavam stale | `PROJECT_STATE.md` | Snapshot antigo preservado em `docs/governance/PROJECT_STATE_HISTORICAL_2026-10-06_PRE_CONTINUITY.md`; nova authority reconciliada |
| `docs/START_HERE.md` | CURRENT_OPERATIONAL_RECORD de navegação | `START_HERE.md` | Movido; path antigo virou redirect |
| `docs/governance/AUTHORITY_MAP.md` | CURRENT_PRIMARY_AUTHORITY | `ACTIVE_AUTHORITY_MAP.md` | Movido e reconciliado; path antigo virou redirect |
| `docs/governance/CONTINUITY_RECORD.md` | CURRENT_OPERATIONAL_RECORD | `CONTINUITY_RECORD.md` | Movido e reconciliado; path antigo virou redirect |
| `docs/governance/NEW_AGENT_BOOTSTRAP.md` | CURRENT_OPERATIONAL_RECORD | `NEW_AGENT_BOOTSTRAP.md` | Movido e reconciliado; path antigo virou redirect |
| `docs/governance/PROJECT_GOVERNANCE_BINDING.json` | CURRENT_PRIMARY_AUTHORITY; validado anteriormente | `PROJECT_GOVERNANCE_BINDING.json` | Movido sem alteração de conteúdo; JSON parse revalidado |
| `docs/planning/ROADMAP.md` | CURRENT_PRIMARY_AUTHORITY, conteúdo atual | `planning/ROADMAP.md` | Movido; links internos reconciliados; path antigo virou redirect |
| `docs/planning/SPRINTS.md` | CURRENT_PRIMARY_AUTHORITY, conteúdo atual | `planning/SPRINTS.md` | Movido; links internos reconciliados; path antigo virou redirect |
| `LAST_HANDOFF.md` | MISSING | `handoff/LAST_HANDOFF.md` | Criado e ligado às authorities correntes |
| Schema do binding | DERIVED_REFERENCE externa | `C:\Users\walacedelgado\PycharmProjects\governanca_de_projetos\Protocolos para Projetos - Vigente\Protocolo Continuidade Projeto Em Andamento Com Novo Agente 3.0\schemas\PROJECT_GOVERNANCE_BINDING.schema.json` | Continua no governance root; não foi copiado |

Não existe `AUTHORITY_MAP.md` alternativo além do mapa acima. Os redirects
legados não contêm cópias de estado, roadmap ou plano. O snapshot preservado é
explicitamente histórico, não uma authority ativa.

## Regras de ownership

```text
ONE_RESPONSIBILITY = ONE_PRIMARY_AUTHORITY
DETAIL_ONCE = REQUIRED
REFERENCE_EVERYWHERE_ELSE = REQUIRED
DUPLICATE_ACTIVE_PROJECT_STATE = NO
DUPLICATE_ACTIVE_ROADMAP = NO
DUPLICATE_ACTIVE_EXECUTION_PLAN = NO
```

PM-01 §12.5 define `docs/continuity/` como raiz padrão. Authorities de domínio
permanecem em `docs/product/`, `docs/architecture/`, `docs/engineering/` e
nos demais caminhos semânticos indicados acima.
