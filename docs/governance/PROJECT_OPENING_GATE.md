# Avaliação do Project Opening Gate

~~~text
DOCUMENT_ROLE = PROJECT_OPENING_GATE_RECORD + FOUNDATION_REVIEW
PROJECT_ID = projeto_telegram_courses
RECORDED_AT = 2026-10-05 / America/Sao_Paulo
OPENING_PROTOCOL = PROJECT_OPENING 3.0 / DECLARED_CANONICAL_ACTIVE
PROJECT_OPENING_GATE = BLOCKED
FOUNDATION_REVIEW = BLOCKED_ON_GOVERNANCE_INTEGRITY
STATUS = BLOCKED
ACTIVITY_COMPLETION_PERCENT = 70%
PROJECT_GOVERNANCE_BINDING = BLOCKED
DOCUMENT_RECONCILIATION = FAIL
OPENING_CONTINUITY_HANDOFF = NOT_PASSED
CONTINUITY_RECOVERY_GATE = NOT_PASSED
AGENT_HANDOFF_GATE = FAIL
~~~

## Critérios reais e evidências

Opening §6 exige revisão aplicável da fundação, artifacts descobríveis, aprovação explícita e handoff pronto. §§2 e 5 exigem resolução verificável e binding validado. PM-01 §12.3 exige continuidade/pins atuais e ausência de estado contraditório. Continuity §§3 e 6 exige schema/pins íntegros, fatos e validação pertinente antes de PASS. Templates não introduzem novos critérios.

| Condição | Resultado | Evidência |
|---|---|---|
| Identidade/root factual e limites de autorização | PASS | PROJECT_STATE e auditoria local |
| Baseline current por Matrix/Registry | PASS com finding de metadata | 7/7 authorities com hash exato; PM-04 esclarecida pelo conteúdo/Matrix/GOV-10 |
| Protocolos e schema disponíveis/lidos | PASS de disponibilidade | Ambos ZIPs e cópias extraídas, incluindo schema real |
| Integridade exata dos protocols/schema | FAIL | 0/17 entradas conferem com manifests; GOV-B01 |
| Intenção, FR/NFR, escopo e acesso | PASS documental | REQUIREMENTS reconciliado com Card B §4 |
| Arquitetura e decisões duráveis | PASS documental | ARCHITECTURE, sete ADRs, aprovação direta Card B §§3 e 5 |
| Engenharia, dados, testes, operações e limites | PASS documental | ENGINEERING_FOUNDATION, aprovação Card B §§3 e 6; testes futuros explícitos |
| Roadmap e delivery unit escolhida | PASS documental | PHASE 0–8/S0–S10; S4 com nove critérios; SPRINTS |
| Raiz, navegação e papéis de continuidade | PASS de discoverability, binding pendente | docs/ como equivalente governado; START_HERE, mapa, record, bootstrap e plans |
| Binding real, estruturalmente validado e pins reproduzíveis | BLOCKED | Schema lido; binding não materializado devido a integridade de authority, sem substitute Markdown |
| VP-01 / Continuity recovery completa | BLOCKED | Discovery/reconciliation read-only; validação integral/handoff não declarados como executados |
| Aprovação explícita de fundação | PASS | Card B §3 FOUNDATION_APPROVAL = APPROVED; provenance em APPROVALS_AND_DECISIONS |
| Prontidão de handoff sob PM-01 | FAIL | Binding e integridade dos pins pendentes; AGENT_HANDOFF_GATE não passa |
| S0/implementação/Git mutável não iniciados | PASS | Inventário contém somente documentação/evidência; sem init/clone/stage/commit/push |

Foundation approval permanece aprovada; a revisão documental atual não reabre a decisão técnica. Review de código/runtime, smoke Windows, download, resume e Telegram não são claimed nesta abertura. Não há requisito aplicável de reviewer independente para este delta documental; houve self-review do agente, sem alegação de independência.

## Git: CASE A

LOCAL_GIT_REPOSITORY = NOT_INITIALIZED. Branch, HEAD, upstream, index/staging e worktree não foram inventados. URL remoto é configuração declarada, sem origin configurado.

Opening §§2 e 5–6/Wizard §§0 e 6–8 não exigem repositório Git materializado para Opening Gate. PM-01 §12.1 condiciona HEAD a Git disponível; Continuity §4 condiciona inspeção Git à disponibilidade. A S0 do baseline usuário §7 é Repository / Project Bootstrap. Ausência de .git é condição inicial factual e não blocker desta abertura. Não houve init/clone.

## Blocker remanescente

~~~text
BLOCKER_ID = GOV-B01
SOURCE = OPENING_PROTOCOL §2; CONTINUITY_PROTOCOL §3 passos 3–4; manifests dos dois pacotes
REQUIRED_CONDITION = Resolver bytes exatos canônicos dos protocols e schema que confiram com seus manifests, sem normalização/substituição silenciosa.
CURRENT_EVIDENCE = 13/13 entradas Opening e 4/4 Continuity divergem em SHA-256 e tamanho; cópias extraídas também divergem. Conversão CRLF→LF em memória confere 17/17 apenas como diagnóstico; nenhum source foi alterado.
NEXT_REQUIRED_ACTION = Restaurar/exportar fontes canônicas com bytes íntegros, ou corrigir/reemitir manifests/pacotes por atividade de governança explicitamente autorizada; depois reexecutar checks e materializar/validar binding.
~~~

Exemplos exatos, com todos os arquivos/tamanhos/hashes em [SOURCE_INTEGRITY_CHECK.json](evidence/SOURCE_INTEGRITY_CHECK.json):

| Authority | Hash esperado | Hash observado |
|---|---|---|
| Opening protocol | 6fa7c89a6481547123b8d904d65d8e553b259f944507d34ca6ba5c265fbc35ad | 6e74d4330e65982584411c8eb53253275268aabc06c7b86e3361380fd0204848 |
| Continuity protocol | 262997f3509a856ed450654c9e5c9b9128beb3f57e1092bc87967ded42d0b5f3 | 5343a7b1ae9c344afad6bf118103ebf6b986605eea44f94a1d520a0207628b69 |
| Binding schema | b2983cbad8fa2616325eb3ad6c8cb2b280c0f44942ac469fcf7749bea2ae5a22 | f6691930c1d5c0c47a39f4e9a7cb7ab5042e3eaabe4ad84d4ca8aa968a3fc943 |

GOV-B01 impede materialização segura do binding, validação estrutural de sua instância e handoff completo. O schema não está ausente: parse JSON PASS; identidade dos bytes entregues contra manifest FAIL. Não foram fabricados pins, hash adotado diferente nem resultado de JSON Schema validator. Não houve correção no governance root externo, fora do escopo.

## Reconciliação e stale references

| Relação | Resultado |
|---|---|
| Requirements ↔ architecture | PASS documental: produto genérico, parser suportado, CLI, gateway, acesso |
| Architecture ↔ engineering | PASS documental: stack, schema, estados, finalização/resume e workers |
| Foundation ↔ roadmap | PASS documental: controles/testes/riscos nas unidades pertinentes |
| Roadmap ↔ sprints | PASS documental: PHASE 0–8, S0–S10, S4, sequência/dependências |
| Sprints ↔ requirements | PASS documental: FR-01–FR-16/NFR-01–NFR-10 com evidências planejadas |
| PROJECT_STATE ↔ artifacts | PASS documental: aprovações, estado Git, blockers, safe resume e não autorização |
| Binding ↔ schema / adopted pins ↔ Registry | BLOCKED por GOV-B01; não executado como validação de instância |
| Roots ↔ ambiente | PASS factual: WORK presente/ativo; HOME ausente/configurado |
| Stale active policy references no projeto | NONE; versões antigas citadas somente como finding/histórico |
| Stale active references nas sources | Duas dependências antigas no CONTINUITY_MANIFEST: PM-02 R2.5 e PM-03 R2.2 marcadas CANONICAL/ACTIVE; não usadas |

DOCUMENT_RECONCILIATION = FAIL refere-se ao conjunto obrigatório completo, que inclui binding. O núcleo de documentos de produto/planejamento/estado passa; não elevar esse resultado parcial ao aceite global.

Findings externos não bloqueantes de identidade: metadata baseline_role de PM-04 no Registry carece de delimitação (policy BASELINE v1.1 esclarece); PM-03 contém prose residual “candidata” e PREVIOUS_BASELINE_ROLE anterior à promoção, mas cabeçalho canônico/Registry/GOV-10 confirmam v1.7-R2.3; notas históricas dos reports e palavras “candidate” em entrypoints não promovem versões antigas. Referências antigas do Continuity são drift externo visível, sem fallback e sem migration silenciosa.

## Estado separado, limites e completion basis

Estado corrente, próximos passos, readiness, autorização e SAFE_RESUME_POINT têm authority única em [PROJECT_STATE.md](PROJECT_STATE.md). Esta avaliação é evidência do gate, não segunda authority de estado.

COMPLETION_BASIS = 5 de 7 marcos materiais concluídos (aproximação arredondada 70%): leitura/resolução de fontes; fatos de root/Git; auditoria de integridade e stale refs; reconciliação documental; registro de revisão/gate e evidências. Materialização/validação do binding e validação completa VP-01/Continuity/handoff permanecem bloqueadas. A porcentagem mede esta atividade, sem crédito de conclusão do produto/S0.

POLICIES_READ = PM-00 1.0; PM-01 1.0; PM-02 1.7-R2.6; PM-03 1.7-R2.3; PM-04 1.2; PM-05 v1; VP-01 v2.0; também todos os membros textuais dos três ZIPs entregues. VP-01 é VALIDATION_ONLY: fase read-only de descoberta/reconciliação, com saída antecipada pelo blocker sob PM-03 §21; suíte adversarial/dry-runs e gate integral não foram claimed como concluídos.

CURRENT_POLICY_BASELINE = GOVERNANCE_BASELINE V1 / contract 1, versões acima. SKILL = NONE; PLUGIN = NONE; EXECUTION_MODE = DIRECT; SUBAGENTS = NONE. Capacidade nativa de arquivos/hashes foi suficiente.

A abertura permanece BLOCKED com blocker evidencial concreto. Fontes/schema antes ditos indisponíveis agora foram encontrados. Não se mantém blocker por falta de .git, histórico de chat ou necessidade de nova aprovação de arquitetura/fundação. S0 e implementação continuam sem autorização.
