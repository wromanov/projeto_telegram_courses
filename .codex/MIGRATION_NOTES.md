# Migração de agentes Codex para GPT-6 / PM-02 R2.6 / PM-03 R2.3

DOCUMENT_TYPE = OPERATIONAL_MIGRATION_NOTE
NORMATIVE_AUTHORITY = NO

Pacote-fonte SHA-256:

`83065fafc81424aafe832916906bde9f76d7dbf73651f31d2197bedc197447d3`

## Mudanças principais

- GPT-5.6 Luna -> GPT-6 Luna nos papéis leves/bounded.
- GPT-5.6 Terra -> GPT-6 Sol nos papéis que exigem julgamento técnico material.
- `sol_architect` antigo foi substituído por `architect` em GPT-6 Sol / High.
- Removido o default global que forçava todo subagente sem perfil para Luna/High.
  Subagentes não especializados agora herdam modelo/esforço do parent.
- `max_concurrent_threads_per_session = 2` foi preservado como orçamento LOCAL,
  não como default normativo do provider.
- Names canônicos agora são orientados a ROLE, não ao nome do modelo.
- Astra não recebeu perfil fixo: escalonamento para `gpt-6-astra` deve ocorrer
  somente quando houver capability gap e authority apropriada.
- Os dois aliases já depreciados (`luna_explorer`, `luna_test_analyst`) foram
  mantidos temporariamente para compatibilidade.

## Mapeamento de nomes

| Antigo | Novo |
|---|---|
| `luna_scout` | `scout` |
| `luna_researcher` | `researcher` |
| `luna_scribe` | `scribe` |
| `luna_triage` | `triage` |
| `luna_validator` | `validator` |
| `luna_worker` | `mechanical_implementer` |
| `terra_implementer` | `implementer` |
| `terra_reviewer` | `reviewer` |
| `terra_security` | `security_reviewer` |
| `sol_architect` | `architect` |
| `luna_explorer` | compatibilidade; preferir `scout` |
| `luna_test_analyst` | compatibilidade; preferir `validator` ou `triage` |

Prompts/projetos que invocarem explicitamente os nomes antigos ativos devem ser
atualizados para os nomes novos.

## Runtime

A configuração segue a separação:

`ROLE != MODEL != EFFORT != TOOL_SURFACE`

A capability real de ferramentas deve ser verificada no runtime. A possibilidade
técnica de multi-agent não substitui a autorização de governança para mudar de
DIRECT para MULTIAGENT.

Todos os perfis especializados deste pacote são leaf por padrão. Isso mantém
delegação recursiva desabilitada por padrão.
