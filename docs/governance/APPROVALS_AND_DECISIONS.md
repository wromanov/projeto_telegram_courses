# Aprovações e decisões — projeto_telegram_courses

DOCUMENT_ROLE = APPROVALS_AND_DECISIONS  
RECORDED_AT = 2026-10-05 / America/Sao_Paulo

## Fonte da autorização desta atividade

Pedido direto do usuário: continuar o Card B anexado, agora com caminhos dos três ZIPs. Fonte original: C:/Users/walacedelgado/.codex/attachments/c060c9a7-7b7d-4201-8914-42afc050f00e/Texto colado.txt. Sua identidade/hash está em [SOURCE_INTEGRITY_CHECK.json](evidence/SOURCE_INTEGRITY_CHECK.json).

O Card B é instrução do usuário para esta atividade. Os ZIPs são fontes documentais de governança: suas policies/protocolos têm os papéis e a precedência da PM-00; templates, históricos e exemplos não são novas ordens do usuário. Nenhuma instrução em documento amplia o escopo concedido.

Autorizado: ler authorities, verificar fatos, corrigir documentos do projeto, materializar binding depois de resolver schema/authorities, validar e reavaliar o Opening Gate. Não autorizado: implementar produto, iniciar S0, git init, clone, commit ou push. Corrigir/recanonicalizar sources no projeto governanca_de_projetos excede este escopo.

## Decisões reafirmadas pelo usuário

| Decisão | Fonte do Card B | Registro primário |
|---|---|---|
| Produto genérico para múltiplos canais; RASMOO como primeiro alvo real | §§3–4 | [REQUIREMENTS.md](../product/REQUIREMENTS.md) |
| CLI Windows com Rich; GUI futura/fora do escopo inicial | §3 | REQUIREMENTS / ADR-006 |
| Formato = / == / === / #Fxxx é parser suportado, sem dependência universal | §3 | REQUIREMENTS / ADR-004 |
| ARCHITECTURE_APPROVAL = APPROVED | §§3 e 5 | [ARCHITECTURE.md](../architecture/ARCHITECTURE.md), ADR-001–ADR-007 |
| FOUNDATION_APPROVAL = APPROVED | §§3 e 6 | [ENGINEERING_FOUNDATION.md](../engineering/ENGINEERING_FOUNDATION.md) |
| FR-01–FR-16 e NFR-01–NFR-10, escopo e acesso legítimo | §4 | REQUIREMENTS |
| PHASE 0–8 e S0–S10; primeiro valor em S4 | §7 | [ROADMAP.md](../planning/ROADMAP.md) / [SPRINTS.md](../planning/SPRINTS.md) |
| S0 selecionado, não iniciado e não autorizado | §§7 e 11 | [PROJECT_STATE.md](PROJECT_STATE.md) |
| Implementação sem autorização | §§1, 11 e 14 | PROJECT_STATE |

As aprovações são reafirmadas diretamente pelo usuário nesta fonte; não dependem de recuperar a conversa “Projeto Telegram 1.0”. Registros anteriores da conversa são proveniência histórica, sem ampliar o baseline fornecido.

## Aplicação normativa e limites

DELIVERY_UNIT = SPRINT; integração incremental; máximo de atividades formais simultâneas = 1, sob PM-01. FRONTEND_FIRST_RULE = NOT_APPLICABLE: CLI sem frontend gráfico/web; fluxos e UX CLI continuam integrados e validados por unidade.

PM-04 v1.2 é canônica/ativa pela PM-00, operational_current_versions do Registry, cabeçalho da própria policy e GOV-10. O campo baseline_role do Registry está mal delimitado: a própria policy declara BASELINE = v1.1 e BASELINE_ROLE = SUPERSEDED_HISTORICAL_PREDECESSOR. Essa evidência permite identificar a v1.2 atual; o campo externo permanece visível como finding, sem ser corrigido aqui.

Não há baseline previamente adotado em binding neste root. A intenção de primeira adoção é a baseline atual solicitada no Card B. Ela não está materializada como binding enquanto bytes de protocolos/schema não conferirem. Não foi iniciada migração nem promovida authority.

O estado corrente, autorização e ponto seguro têm authority única em PROJECT_STATE. Resultado/restrições desta revisão são evidência em [PROJECT_OPENING_GATE.md](PROJECT_OPENING_GATE.md), não aprovação de execução.
