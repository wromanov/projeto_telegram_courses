# Continuidade do projeto

`docs/continuity/` é a raiz canônica de continuidade, conforme PM-01 §12.5.
Este arquivo é apenas navegação; `PROJECT_STATE.md` é a authority do estado
corrente.

Os procedimentos de continuidade e bootstrap completos aplicam-se ao workspace
local. Os derivados públicos são informativos e não os substituem nem substituem
as authorities locais.

## Retomada

1. Leia PROJECT_STATE.md (authority canônica mantida localmente e omitida da
   baseline pública) para branch/HEAD, atividade,
   autorização, bloqueios e `SAFE_RESUME_POINT`.
2. Leia ACTIVE_AUTHORITY_MAP.md (authority canônica mantida localmente e
   omitida da baseline pública) para resolver cada
   assunto à sua authority primária.
3. Confirme Git e estado local em runtime. `EXACT_CURRENT_HEAD` nunca é
   presumido a partir de texto salvo.
4. Siga [NEW_AGENT_BOOTSTRAP.md](NEW_AGENT_BOOTSTRAP.md). Não avance se
   readiness, autorização ou um gate requerido estiver pendente.

## Authorities deste pacote

| Papel | Authority primária |
|---|---|
| Estado, autorização e safe resume | PROJECT_STATE.md (authority canônica mantida localmente e omitida da baseline pública) |
| Mapa de authorities | ACTIVE_AUTHORITY_MAP.md (authority canônica mantida localmente e omitida da baseline pública) |
| Roadmap | [planning/ROADMAP.md](planning/ROADMAP.md) |
| Plano executável / sprints | [planning/SPRINTS.md](planning/SPRINTS.md) |
| Registro de continuidade | CONTINUITY_RECORD.md (authority canônica mantida localmente e omitida da baseline pública) |
| Procedimento de retomada | [NEW_AGENT_BOOTSTRAP.md](NEW_AGENT_BOOTSTRAP.md) |
| Binding de governança | [PROJECT_GOVERNANCE_BINDING.json](PROJECT_GOVERNANCE_BINDING.json) |
| Último handoff | handoff/LAST_HANDOFF.md (authority canônica mantida localmente e omitida da baseline pública) |

## Authorities de domínio

Produto, arquitetura, engenharia, contratos e decisões permanecem em suas
localizações semânticas, listadas no mapa. A navegação aqui não duplica seu
conteúdo.
