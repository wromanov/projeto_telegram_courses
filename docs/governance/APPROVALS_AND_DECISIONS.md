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
| PHASE 0–8 e S0–S10; primeiro valor em S4 | §7 | [ROADMAP.md](../continuity/planning/ROADMAP.md) / [SPRINTS.md](../continuity/planning/SPRINTS.md) |
| S0 selecionado; estado corrente e autorização em PROJECT_STATE | §§7 e 11 | [PROJECT_STATE.md](../continuity/PROJECT_STATE.md) |
| Implementação sem autorização | §§1, 11 e 14 | PROJECT_STATE |

As aprovações são reafirmadas diretamente pelo usuário nesta fonte; não dependem de recuperar a conversa “Projeto Telegram 1.0”. Registros anteriores da conversa são proveniência histórica, sem ampliar o baseline fornecido.

## Aprovação explícita — proteção de sessão S1 e ownership de retry

Fonte: decisão explícita do usuário em 2026-10-07, para preparação arquitetural e de segurança da S1.

```text
DECISION = S1 session protection + retry ownership
DECISION_MAKER = USER
USER_APPROVAL = APPROVED
DATE = 2026-10-07
DECISION_SCOPE = architecture/security/runtime preparation for S1
DECISION_CONTENT =
- DPAPI CURRENT_USER protects the at-rest representation of Telethon StringSession; DPAPI_LOCAL_MACHINE scope is prohibited.
- Plaintext session is prohibited at rest and may exist only in memory inside the adapter for the minimum necessary lifecycle.
- Store the protected representation in user-scoped application data outside the repository with restrictive user-level filesystem access.
- Use an independent authorization/session per machine; no automatic backup or export.
- Local session-blob deletion is distinct from remote revocation; reauthenticate when the session is no longer valid.
- Application owns semantic retry policy, wait/budget/cancellation decisions; Telethon adapter owns transport mechanics.
- Adapter translates FloodWait to an application/domain error carrying retry_after_seconds.
- Disable Telethon automatic FloodWait sleep for the S1 design; internal Telethon retries are finite/bounded and must not mask FloodWait or authentication/access/configuration failures.
- Keep DC migration/protocol details and Telethon types/exception implementation details inside the adapter when transparent to application semantics.
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
S1_STARTED = NO
```

This approval records architecture and security/runtime preparation only. It is not implementation evidence, S1 authorization, or a DoR PASS.

## Aplicação normativa e limites

DELIVERY_UNIT = SPRINT; integração incremental; máximo de atividades formais simultâneas = 1, sob PM-01. FRONTEND_FIRST_RULE = NOT_APPLICABLE: CLI sem frontend gráfico/web; fluxos e UX CLI continuam integrados e validados por unidade.

PM-04 v1.2 é canônica/ativa pela PM-00, operational_current_versions do Registry, cabeçalho da própria policy e GOV-10. O campo baseline_role do Registry está mal delimitado: a própria policy declara BASELINE = v1.1 e BASELINE_ROLE = SUPERSEDED_HISTORICAL_PREDECESSOR. Essa evidência permite identificar a v1.2 atual; o campo externo permanece visível como finding, sem ser corrigido aqui.

O Card B autorizou materializar a primeira adoção. [PROJECT_GOVERNANCE_BINDING.json](../continuity/PROJECT_GOVERNANCE_BINDING.json) registra GOVERNANCE_BASELINE V1 / contract 1 com PM-00–PM-05, VP-01 e Continuity 3.0, todos resolvidos por identidade, versão e SHA-256. Schema Draft 2020-12 e pins passaram. Migração não foi solicitada e nenhuma authority foi promovida.

O estado corrente, readiness, autorização e ponto seguro têm authority única em [PROJECT_STATE.md](../continuity/PROJECT_STATE.md). A abertura/handoff e evidências estão em [PROJECT_OPENING_GATE.md](PROJECT_OPENING_GATE.md); PASS não aprova execução de S0.

## Aprovação do contrato de implementação S0 v1.0

Fonte: decisão explícita do usuário no Card B de reconciliação documental, acompanhada do resultado informado da verificação final focada concluída fora do checkout atual.

```text
DECISION = APPROVE S0_IMPLEMENTATION_CONTRACT v1.0
DECISION_MAKER = USER
RESULT = APPROVED
CONTRACT_ID = S0_IMPLEMENTATION_CONTRACT
CONTRACT_VERSION = 1.0
CONTRACT_CLOSURE_VERIFICATION = PASS
CONTRACT_APPROVAL_READINESS = READY_FOR_USER_APPROVAL
FINAL_FOCUSED_VERIFICATION = PASS
CONTRACT_SEMANTIC_STATE = FROZEN
S0_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
S0_STARTED = NO
SP01_RUNTIME_VALIDATION = NOT_EXECUTED
```

A verificação focada confirmou MED-06–08 como `CLOSED_CONFIRMED`, preservou HIGH-01 e MED-01–05, e reportou zero regressões, decisões escondidas, liberdade semântica, gaps materiais ou issues estruturais fora do escopo. Este registro materializa o resultado fornecido pelo usuário; nenhuma nova auditoria foi executada. Aprovação contratual e autorização para implementar S0 são gates distintos.

## Autorização corrente — execução integral S0

Fonte: decisão explícita do usuário no Card B `1ba72eb6-adae-47b6-840d-da651c2a69b6`, fornecido em 2026-10-06.

```text
S0_EXECUTION_AUTHORIZED = YES
BOUNDED_CYCLIC_EXECUTION_AUTHORIZED = YES
AUTO_ADVANCE_BETWEEN_PASSED_SLICES = YES
LOCAL_COMMIT_AUTHORIZATION = YES
AUTO_LOCAL_COMMIT_ON_SLICE_PASS = YES
AUTHORIZATION_SCOPE = S0_ONLY
S1_AUTHORIZED = NO
PUSH_AUTHORIZED = NO (AT CARD B AUTHORIZATION TIME; SUPERSEDED ON COMPLETION BY LATER USER DECISION)
```

Esta decisão concede execução da S0 e commits locais por slice que passe; não altera semanticamente o contrato congelado nem autoriza S1. Em instrução posterior, o usuário autorizou stage + commit + push quando a atividade estiver finalizada e deixou a semântica das mensagens de commit a critério do executor. Essa autorização de publicação somente se aplica ao encerramento da atividade e ainda não foi exercida, pois S0 está parada. O estado atual e o safe resume point ficam em [PROJECT_STATE](PROJECT_STATE.md).

## Autorização posterior — publicação no encerramento da atividade

```text
PRIOR_STAGE_AUTHORIZATION = YES / WHEN_ACTIVITY_IS_FINISHED / SUPERSEDED
PRIOR_COMMIT_AUTHORIZATION = YES / WHEN_ACTIVITY_IS_FINISHED / SUPERSEDED
PRIOR_PUSH_AUTHORIZATION = YES / WHEN_ACTIVITY_IS_FINISHED / SUPERSEDED
CURRENT_STAGE_AUTHORIZATION = YES / FOR_AUTHORIZED_LOCAL_CHECKPOINTS
CURRENT_COMMIT_AUTHORIZATION = YES / LOCAL_ONLY
CURRENT_PUSH_AUTHORIZATION = YES / ONE-TIME CONTINUITY PUSH ONLY / work/s0-bootstrap
COMMIT_MESSAGE_SEMANTICS = DELEGATED_TO_EXECUTOR
ORCHESTRATION_MODE = SINGLE_ACTIVITY
BOUNDED_CYCLIC_EXECUTION = SUSPENDED
S0_RESUME_AUTHORIZED = YES
PUBLICATION_PERFORMED = NO
```

Em decisão posterior, o usuário autorizou a retomada de S0 em `SINGLE_ACTIVITY`, preservou SL01/SL02 e explicitamente definiu `PUSH = NOT_AUTHORIZED`, substituindo a autorização anterior de push para conclusão da S0. O Card B seguinte registrou uma exceção limitada para um único push de continuidade em `work/s0-bootstrap`; essa permissão histórica não autoriza publicação nesta atividade, pois a instrução mais recente a proíbe.

```text
CONTINUITY_PUSH_AUTHORIZED = HISTORICAL / SUPERSEDED_FOR_CURRENT_ACTIVITY
PURPOSE = MACHINE_TRANSFER
BRANCH = work/s0-bootstrap
FORCE_PUSH = PROHIBITED
TAGS = PROHIBITED
RELEASE = PROHIBITED
MERGE = PROHIBITED
STOP_AFTER_PUSH_VERIFIED = HISTORICAL
```

## Escopo Git vigente — reconciliação do pacote de continuidade

Instrução direta do usuário no Card B posterior, em 2026-10-06: depois de
confirmar branch, HEAD, upstream, delta e gates, executar staging seletivo,
um único commit e `git push origin work/s0-bootstrap` exclusivamente para o
pacote de continuidade. A autorização não cobre produto, testes, SP-01, merge,
rebase, tags, force push ou publicação adicional. O resultado do push deve ser
confirmado em runtime e não é antecipado neste registro.
