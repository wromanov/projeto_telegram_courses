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

## Autorização explícita — implementação da S1-A

Fonte: instrução direta do usuário fornecida em 2026-10-07 no pedido
`C:\Users\walacedelgado\.codex\attachments\af78adf4-4336-4600-a666-df3facbad8c4\Texto colado.txt`.

```text
DECISION_MAKER = USER
DATE = 2026-10-07
S1_DOR = PASS / evidência derivada em docs/reports/S1_DOR_GAP_REVIEW_2026-10-07.md
S1_IMPLEMENTATION_AUTHORIZATION = GRANTED
AUTHORIZATION_SCOPE = S1-A — Protected Session Foundation
S1_STARTED = NO UNTIL FIRST MATERIAL SOURCE CHANGE
```

A autorização cobre a fundação protegida e sua validação offline dentro dos
invariantes e authorities aprovados. Não autoriza conexão Telegram, credenciais
reais, criação de sessão real, expansão de escopo nem publicação Git. A
autorização anterior de preparação arquitetural permanece como registro
histórico; o estado corrente está em [PROJECT_STATE](../continuity/PROJECT_STATE.md).

## Autorização explícita — S1-B offline authentication flow e Telegram gateway

Fonte: instrução direta do usuário em 2026-10-07, atividade `S1-B — Offline Authentication Flow & Telegram Gateway`, fornecida em
`C:\Users\walacedelgado\.codex\attachments\8d3ff736-b275-4bd1-a93c-1fa1a5eac824\Texto colado.txt`.

```text
DECISION_MAKER = USER
DATE = 2026-10-07
S1_DOR = PASS
S1_IMPLEMENTATION_AUTHORIZATION = GRANTED
AUTHORIZATION_SCOPE = S1-B — Offline Authentication Flow & Telegram Gateway
REAL_TELEGRAM_CONNECTION = PROHIBITED
REAL_CREDENTIALS_OR_SESSION = PROHIBITED
GIT_STAGE_COMMIT_PUSH = PROHIBITED
RESULT = S1-B PASS / offline validation only
```

O contrato congelado é [S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT](../contracts/S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT.md). Esta autorização não inicia S1-C nem autoriza conexão, telefone, credenciais, OTP, senha 2FA ou sessão reais. Nenhuma operação Git mutável foi autorizada ou executada.

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

## Decisões aprovadas — S1-D descoberta e seleção

Fonte: instrução direta do usuário em 2026-10-08, atividade `S1-D — Architectural Decision Closeout`, no arquivo `Texto colado.txt` anexado a esta atividade. Estas decisões aprovam somente os itens listados; o contrato continua DRAFT e não há autorização de implementação, freeze ou publicação.

### DEC-S1D-01 — Payload incidental de mensagens

```text
DECISION_MAKER = USER
DATE = 2026-10-08
STATUS = APPROVED
SCOPE = S1-D channel/dialog discovery
ENUMERATION = getDialogs / iter_dialogs permitido; payload incidental pode ser recebido pela biblioteca/adapter
NO_MESSAGE_TRANSFER = NOT_GUARANTEED
NO_MESSAGE_PROCESSING = REQUIRED / BY_APPLICATION
NO_MESSAGE_PROCESSING_BY_APPLICATION = REQUIRED
LIBRARY_INTERNAL_PROCESSING = MAY_OCCUR / PROTOCOL AND LIBRARY BEHAVIOR
NO_MESSAGE_PERSISTENCE = REQUIRED
NO_MESSAGE_EXPOSURE = REQUIRED
NO_MESSAGE_LOGGING = REQUIRED
EXPLICIT_HISTORY_READ = PROHIBITED
```

A biblioteca pode desserializar/manusear payload incidental como exigência do protocolo. A aplicação não interpreta conteúdo, não persiste, não registra em logs, não expõe na CLI e não retorna conteúdo pelos modelos do gateway. A decisão não afirma ausência de transferência nem impede o processamento interno necessário à biblioteca. Controles e fronteira estão especificados no contrato S1-D.

### DEC-S1D-02 — Elegibilidade inicial de canais

```text
DECISION_MAKER = USER
DATE = 2026-10-08
STATUS = REVISED_AND_APPROVED
SUPERSEDES = DEC-S1D-02 / BROADCAST_ONLY proposal in prior S1-D draft
ELIGIBLE = BROADCAST_CHANNEL, MEGAGROUP / SUPERGROUP
NOT_ELIGIBLE = BASIC_GROUP, PRIVATE_USER_DIALOG, BOT_DIALOG, SECRET_CHAT
PRIMARY_IDENTITY = telegram_chat_id
SELECTION = LOCAL_BY_STABLE_ID
CLASSIFICATION = EXPLICIT_PROJECT_OWNED_TYPES
TELETHON_TYPES_OUTSIDE_ADAPTER = PROHIBITED
ADMIN_OR_MEMBER_OPERATIONS = OUT_OF_SCOPE
```

A classificação de broadcast e megagroup é explícita em modelos próprios; títulos/usernames não são identidade primária. A inclusão de supergrupos não autoriza operações administrativas, de membros ou outras alterações remotas. A recomendação anterior de broadcast-only fica registrada como superseded; nenhum histórico foi apagado. `FUT-CHDISC-01` não foi criado como funcionalidade adiada.

## Escolhas do usuário — S1-D Remaining Technical Decisions Closeout

Fonte: respostas diretas do usuário nesta atividade em 2026-10-08. O detalhe
técnico e os itens ainda OPEN ficam no [contrato S1-D](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md).

```text
OPEN-03_CHOICE = OPTION_1_APPROVED / complete discovery as objective, finite measured budgets, explicit partial result and cancellation
OPEN-03_NUMERIC_BUDGETS = OPEN / real Telegram measurement requires separate authorization
OPEN-04_CHOICE = PROVE_AVOIDANCE_OF_GETDIFFERENCE / approved
OPEN-04_PAYLOAD_EXPANSION = NOT_APPROVED / no incidental difference payload authorization
OPEN-04_TECHNICAL_SOLUTION = OPEN / offline proof required before discovery
CONTRACT_STATUS = DRAFT / NOT_APPROVED / NOT_FROZEN
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
```

## DEC-S1D-03 — lifecycle de diferenças internas

Fonte: aprovação humana explícita em 2026-10-08, atividade `S1-D — DEC-S1D-03 Documentation & Reconciliation`, após a auditoria independente registrada em [S1D_INDEPENDENT_ARCHITECTURE_REVIEW_2026-10-08](../audit/S1D_INDEPENDENT_ARCHITECTURE_REVIEW_2026-10-08.md). A decisão aprova somente o escopo abaixo; não aprova o contrato inteiro, freeze, DoR, implementação, validação real ou publicação Git.

```text
DECISION_MAKER = USER
DATE = 2026-10-08
STATUS = APPROVED
ARCHITECTURE = D_PLUS_C
SCOPE = incidental Telethon internal processing during bounded S1-D discovery lifecycle
ALLOWED_INTERNAL_RPC = updates.GetDifference, updates.GetChannelDifference
APPLICATION_EXPLICIT_DIFFERENCE_CALLS = PROHIBITED
LIBRARY_INTERNAL_PROCESSING = ALLOWED
APPLICATION_CONTENT_PROCESSING = PROHIBITED
APPLICATION_CONTENT_PERSISTENCE = PROHIBITED
APPLICATION_CONTENT_EXPOSURE = PROHIBITED
NO_MESSAGE_TRANSFER = NOT_GUARANTEED
PROVE_ZERO_GET_DIFFERENCE = SUPERSEDED
DEC-S1D-03 = ACTIVE_APPROVED_DECISION
CONTRACT_STATUS = DRAFT / NOT_APPROVED / NOT_FROZEN
S1D_IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
```

O recebimento e processamento transitório desses RPCs pela biblioteca são aceitos somente durante o lifecycle delimitado da operação S1-D, inclusive inicialização e loop interno de updates. Isso não permite à aplicação solicitar diferenças para sincronização, scanner ou leitura de mensagens, interpretar payload incidental, encaminhar conteúdo ao domínio, persistir, registrar ou apresentar conteúdo, habilitar handlers, baixar mídia, ler histórico, entrar automaticamente em grupos ou executar ações remotas derivadas. O adapter expõe somente DTOs próprios e metadados autorizados.

Não se garante zero RPCs de diferenças, apenas um `GetDifference`, ocorrência somente no restore, ausência absoluta de mensagens recebidas ou apagamento seguro de conteúdo em memória. `receive_updates=False` e `catch_up=False` são parâmetros do perfil aprovado, mas não provam ausência de `GetDifference` ou `GetChannelDifference`. A mitigação limita o uso e a exposição pela aplicação; não elimina a exposição transitória dentro do Telethon.

A recomendação anterior `PROVE_ZERO_GET_DIFFERENCE` e as afirmações de que payload de diferenças não estava aprovado ficam superseded por DEC-S1D-03; permanecem como histórico da decisão anterior. DEC-S1D-01 e DEC-S1D-02 não são alteradas. OPEN-04 fica resolvida somente quanto à decisão arquitetural; validação técnica continua pendente. OPEN-03, GOV-01 e revalidação FULL_PYTEST permanecem pendentes.

## S1-D — Final Contract Consolidation / sequenciamento autorizado

Fonte: pedido explícito do usuário em 2026-10-08, anexo
a304e9eb-2be7-4dc4-b596-ea5b7265d4fe/Texto colado.txt.
Escopo exclusivamente documental, DIRECT; nenhuma alteração das decisões
DEC-S1D-01/02/03 aprovadas.

O pedido atual autoriza propor orçamento inicial no contrato, implementar
posteriormente limites aprovados e medir/calibrar durante implementação/aceite
com autorização Telegram específica; checkpoint documental consolidado após
implementação/validação. Substitui a exigência anterior de medição real prévia
ao contrato. Não aprova valores numéricos automaticamente.

```text
OPEN-03_SEQUENCE = INITIAL_CONTRACT_BUDGET -> AUTHORIZED_IMPLEMENTATION -> AUTHORIZED_MEASUREMENT_AND_CALIBRATION -> DELIVERY_CHECKPOINT
OPEN-03_NUMERIC_BUDGETS = PROPOSED / NOT_APPROVED / see contract section 4
OPEN-03_STATUS = PENDING_USER_APPROVAL / NOT_CLOSED
OPEN-04_ARCHITECTURAL = RESOLVED_BY_DEC-S1D-03
OPEN-04_VALIDATION = IMPLEMENTATION_GATE / acceptance evidence required
GOV-01 = EXTERNAL_DEPENDENCY / unresolved normative freeze blocker
FULL_PYTEST = PENDING
CONTRACT_STATUS = READY_FOR_USER_REVIEW / DRAFT / NOT_APPROVED / NOT_FROZEN
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
```

Gates de contrato, implementação e aceite estão separados na seção 19 do
[contrato consolidado](../contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md).
A aprovação contratual não requer funcionalidades concluídas; não dispensa
validações de aceite. Policies, binding e evidência Astra não alterados.

## Aceite formal — contrato S6 de retomada e recuperação

Fonte: aprovação formal explícita do usuário em 2026-10-12, atividade
`S6-CONTRACT-FORMAL-CLOSURE-01`, para a versão local do
[contrato S6](../contracts/S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md)
após as correções C-01, C-02, C-03 e F-01.

```text
DECISION_MAKER = USER
DATE = 2026-10-12
STATUS = APPROVED / FROZEN
SCOPE = S6 contract only
OD-01 = APPROVED
OD-02 = APPROVED
C-01 = INCORPORATED
C-02 = INCORPORATED
C-03 = INCORPORATED
F-01 = RESOLVED
ACCEPTANCE_CRITERIA_COUNT = 18
S5_PREVIEW = OFFLINE
CONDITIONAL_CANDIDATE = REMOTE VALIDATION ONLY AFTER USER CONFIRMATION
REMOTE_VALIDATION = REQUIRED BEFORE APPEND
GETFILE = PRE-REQUEST BUDGET RESERVATION REQUIRED
S5_LIMITS = PRESERVED
REAL_TELEGRAM_TECHNICAL_PROOF = FUTURE / NOT PERFORMED
S6_STATUS = PLANNED / NOT_STARTED
S6_IMPLEMENTATION_AUTHORIZATION = NO
```

O aceite congela somente o contrato e não constitui autorização de
implementação, execução da prova Telegram ou avanço de S6.

## Autorização explícita — S6-IMPL-01 offline

Fonte: pedido direto do usuário em 2026-10-12, atividade
`S6-IMPL-01`, fornecido no anexo `Texto colado.txt`.

```text
DECISION_MAKER = USER
DATE = 2026-10-12
ACTIVITY = S6-IMPL-01
IMPLEMENTATION_AUTHORIZATION = GRANTED / OFFLINE VERTICAL IMPLEMENTATION
SCOPE = S6 contract implementation, synthetic tests, local SQLite temporary test fixtures, pytest/Ruff/diff checks
CONTRACT_STATUS = APPROVED / FROZEN / UNCHANGED
REAL_TELEGRAM_OPERATIONS = NOT_AUTHORIZED / 0
SCHEMA_MIGRATIONS = NOT_AUTHORIZED
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
S6_FORMAL_ACCEPTANCE = PENDING SEPARATE REAL TECHNICAL GATE
```

A autorização cobre somente o trabalho offline descrito no pedido. Não
autoriza prova real Telegram, alteração do contrato/schema, operações Git de
publicação ou encerramento formal de S6.

## Ratificação de diretrizes de desenho — contrato S6 V2 — 2026-10-17

```text
ACTIVITY = S6_V2_CONTRACT_APPROVAL_RATIFICATION
DOCUMENT_ROLE = APPROVAL_RECORD / DESIGN_RATIFICATION
PROJECT_ID = projeto_telegram_courses
APPROVED_ARTIFACT = docs/contracts/S6_INTEGRITY_CONTRACT_V2_PROPOSAL_DRAFT.md
APPROVED_ARTIFACT_SHA256 = C9C8A59B5F370B67A86D04CE7407517965711AE5E9780A17DED1C56A747BDF52
APPROVAL_SCOPE = FIVE V2 DESIGN DIRECTIVES ONLY
V2_DESIGN_APPROVED = YES
V1_ACTIVE = YES
V2_EFFECTIVE = NO
IMPLEMENTATION_AUTHORIZED = NO
S6_FORMAL_ACCEPTANCE = PENDING
EFFECTIVE_DATE = NOT_SET
```

O usuário ratificou as cinco diretrizes de desenho abaixo para orientar uma futura implementação e revisão final do contrato. A aprovação não substitui nem altera o contrato S6 V1 canônico, não torna a proposta V2 efetiva e não concede autorização de implementação, execução Telegram, aceite formal S6 ou avanço/fechamento de sprint.

1. **Modo operacional explícito:** `OPERATIONAL_ONLY` só pode ser escolhido explicitamente antes da execução. Sua evidência é `UNVERIFIED_ORIGIN`; não há downgrade automático. `REMOTE_HASH_REQUIRED` permanece o modo padrão.
2. **Conclusão e evidência versionadas:** `COMPLETED_V2` é distinto de `DOWNLOADED` V1. A evidência é versionada e a compatibilidade deve ser segura; registros legados não recebem provas retroativas e consumidores que não reconheçam V2 falham fechados.
3. **Critérios independentes:** operação, retomada, prova controlada por referência e cobertura de hashes remotos têm resultados separados. Nenhum resultado implica equivalência com outro.
4. **Releitura sob S5:** a releitura integral de `[0,P)` deve reservar e debitar seu custo dentro do orçamento agregado S5 existente, respeitando todos os seus limites. Não se cria orçamento paralelo nem se ultrapassa o limite compartilhado.
5. **Ativação futura controlada:** a V2 só pode ser adotada após implementação autorizada, validação dos critérios e nova autorização explícita. A aprovação atual não fixa data efetiva.

### Condições e preservação

- Até decisão futura de adoção e data efetiva, [S6 V1](../contracts/S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md) continua ativo, canônico e inalterado.
- O DRAFT identificado pelo SHA-256 acima é preservado como artefato de desenho; esta ratificação não reescreve seu conteúdo.
- Nenhum estado de sucesso pode ser persistido antes dos gates de evidência aplicáveis ao modo selecionado; em especial, `REFERENCE_MATCH` deve preceder qualquer estado persistido que denote sucesso.
- Falha, ausência ou indisponibilidade de hashes remotos não autoriza fallback. Divergência válida e resposta inválida continuam sendo vetos. `REMOTE_HASH_REQUIRED` continua padrão.
- A adoção deverá preservar compatibilidade de modo que consumidores legados não classifiquem `COMPLETED_V2` como `DOWNLOADED` verificado nem dedupliquem as duas garantias como equivalentes.

### Impactos e riscos residuais reconhecidos

A futura implementação poderá exigir migration SQLite aditiva, novo estado e evidência versionada, mudanças no downloader, gateway, CLI, fila/deduplicação e testes. Riscos reconhecidos incluem consumidores que assumem um conjunto fechado de estados; registros legados sem prova recuperável; custo de releitura de prefixos sob orçamento compartilhado; comportamento remoto de hashes/EOF não verificável; e a diferença entre coerência operacional, igualdade com uma referência e cobertura remota. A ratificação não resolve esses riscos por si só nem os converte em garantia.

```text
CANONICAL_CONTRACT_MODIFIED = NO
SQLITE_OR_PART_MODIFIED = NO
IMPLEMENTATION = NO
TELEGRAM_CALLS = 0
GIT_ADD_COMMIT_PUSH = NO
NEXT_ACTION = OBTAIN_SEPARATE_IMPLEMENTATION_AUTHORIZATION
```

## Autorização explícita posterior — implementação offline S6 V2 — 2026-10-17

Fonte: instrução direta do usuário nesta atividade, autorizando continuar a
implementação offline S6 V2. Esta decisão posterior substitui
`IMPLEMENTATION_AUTHORIZED = NO` da ratificação de desenho somente quanto ao
escopo offline abaixo. Não altera o contrato S6 V1, as cinco diretrizes de
desenho ratificadas nem os gates separados de prova real, ativação e aceite.

```text
DECISION_MAKER = USER
DATE = 2026-10-17
ACTIVITY = S6_V2_CONTROLLED_IMPLEMENTATION
IMPLEMENTATION_AUTHORIZATION = GRANTED / OFFLINE ONLY
SCOPE = OFFLINE SOURCE IMPLEMENTATION, SYNTHETIC TESTS, AND LOCAL VALIDATION AGAINST THE RATIFIED V2 DESIGN DRAFT
SUBAGENTS_AUTHORIZED = UP TO 4 TOTAL
V1_ACTIVE = YES
V2_EFFECTIVE = NO
TELEGRAM_OPERATIONS = NOT_AUTHORIZED
ORIGINAL_PRODUCTION_SQLITE_MODIFICATION = NOT_AUTHORIZED
ORIGINAL_PART_FILE_MODIFICATION = NOT_AUTHORIZED
S6_FORMAL_ACCEPTANCE = PENDING SEPARATE GATE
SPRINT_ADVANCEMENT = NOT_AUTHORIZED
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
```

Esta autorização não torna o DRAFT V2 efetivo nem substitui a autorização
posterior exigida para operação Telegram, adoção/ativação de V2, aceite formal
S6, avanço de sprint ou publicação Git.

## Resultado factual — implementação offline S6 V2 — 2026-10-17

Este registro documenta o resultado informado da atividade autorizada; não é
nova aprovação de produto nem decisão de ativação. A revisão independente
retornou `ACCEPT` para os cinco achados tratados.

```text
ACTIVITY = S6_V2_CONTROLLED_IMPLEMENTATION
IMPLEMENTATION = COMPLETE / OFFLINE
OFFLINE_VALIDATION = PASS / RESULTS BELOW
INDEPENDENT_RE_REVIEW = ACCEPT / FIVE FINDINGS
REGRESSION_SEVEN_FILES = 146 PASSED / CLI SMOKE EXCLUDED
CLI_SMOKE_T09_ISOLATED = 1 PASSED / test_t09_configuration_matrix_runs_through_cli
FINAL_FOCUSED_REGRESSION = 59 PASSED / AFTER FINAL ADJUSTMENTS
RUFF = PASS
COMPILEALL = PASS
DIFF_CHECK = PASS
TRANSIENT_ENVIRONMENT_BLOCKS = TEMP_BASETEMP_PERMISSION_DENIED; LONG_BASENAME_PATH_TOO_LONG
RERUNS = PASS / AUTHORIZED SHORT PATHS / TRANSIENT BLOCKS NOT CODE FAILURES
V1_ACTIVE = YES
V2_EFFECTIVE = NO
REAL_TELEGRAM_CALLS = 0
ORIGINAL_PRODUCTION_SQLITE_MODIFIED = NO
ORIGINAL_PART_FILES_MODIFIED = NO
S6_FORMAL_ACCEPTANCE = PENDING / SEPARATE AUTHORITY
SPRINT_ADVANCEMENT = NOT_AUTHORIZED / NOT PERFORMED
GIT_ADD_COMMIT_PUSH = NO
EVIDENCE_REFERENCE = Root execution report in current activity; durable independent-review transcript not supplied
```

Permanecem pendentes de autoridade: revisão/decisão humana do resultado;
eventual adoção de V2 e definição de data efetiva; eventual prova real Telegram
sob gate explicitamente autorizado; aceite formal S6; avanço de sprint; e
publicação Git. Este resultado offline não executa nem implica esses gates.


## Decisão aprovada — S6 V2 stabilization and continuity — 2026-10-19

Fonte: aprovação explícita do usuário na conversa referenciada **Projeto Telegram 2.0** e autorização operacional contida na atividade documental corrente.

```text
DECISION_MAKER = USER
DECISION = ALTERNATIVE_B / BOUNDED HARNESS AND QA STRUCTURAL STABILIZATION
ARCHITECTURAL_OPINION = Parecer de auditoria arquitetural — S6 V2 / read-only evidence
PRINCIPAL_ARCHITECT = Astra / Medium / READ_ONLY / INVOKED ONCE / CLOSED / NO_REENTRY
ROOT = GPT-6 Luna / XHIGH
NEXT_ROLES = diagnostic_analyst Sol READ_ONLY; mechanical_implementer Luna WRITE_SCOPED; scriber Luna DOCUMENTATION_ONLY
IMPLEMENTATION_SCOPE_THIS_ACTIVITY = DOCUMENTATION_AND_CHECKPOINT_ONLY
OPTION_A_NATIVE_CODEX_EXECUTION = MUST_BE_EVALUATED_FIRST / NOT_DEMONSTRATED_IN_CURRENT_WORK_SESSION
OPTION_B_LOCAL_OFFLINE_EXECUTOR = CONDITIONALLY_AUTHORIZED_IF_A_UNAVAILABLE / LATER_BOUNDED_ACTIVITY_ONLY
POWERSHELL = 5.1 REQUIRED
MAX_OFFLINE_CORRECTION_CYCLES_PER_BATCH = 4
NO_REPEAT_SAME_FAILURE_SIGNATURE_WITHOUT_NEW_EVIDENCE = YES
V1 = CANONICAL_AND_ACTIVE
V2_GLOBAL = OFF
TELEGRAM_RPC_DOWNLOAD_PROOF = NOT_IN_THIS_ACTIVITY
S6_FORMAL_ACCEPTANCE = PENDING
S7_S8 = DEFERRED
GIT_ADD_COMMIT_PUSH = NO
```

Os gates `IMPLEMENTATION_COMPLETE`, `INTEGRATION_VALIDATED`, `NATIVE_REGRESSION_PASS`, `REAL_PROOF_PASS` e `USER_ACCEPTANCE` permanecem independentes. Esta decisão documental não declara nenhum desses gates aprovado.

## Decisão formal — S6 aceita com exceções de escopo — 2026-10-25

```text
DECISION_ID = S6_ACCEPTANCE_WITH_EXCEPTIONS_2026-10-25
DECISION_MAKER = USER
DECISION_DATE = 2026-10-25 / America/Sao_Paulo
USER_APPROVAL = EXPLICIT / "vamos em frente autorizo o fechamento"
APPROVED_OPTION = B / ENCERRAMENTO COM ESCOPO REVISADO
DECISION_SCOPE = ACCEPT S6 WITH FORMAL EXCEPTIONS + DOCUMENTARY CLOSURE/CHECKPOINT
S6_ACCEPTANCE = ACCEPTED_WITH_EXCEPTIONS
S6_STATUS = CLOSED_WITH_EXCEPTIONS / NOT V1_FULLY_CONFORMANT
GATE_A_STATUS = PARTIAL / USER_ACCEPTED_HISTORICAL_EXTERNAL_EXIT_EVIDENCE_EXCEPTION
GATE_B_STATUS = BLOCKED_BY_REMOTE_EVIDENCE / USER_ACCEPTED_SCOPE_EXCEPTION
V1_ACTIVE = YES
V2_GLOBAL = OFF
S7_STATUS = NOT_STARTED / ENTRY_REVIEW_PENDING
S8_STATUS = NOT_STARTED / DEFERRED_UNTIL_S7_DEPENDENCY
GIT_ADD_COMMIT_PUSH = NOT_AUTHORIZED
CODE_TEST_TELEGRAM_EXECUTION = NOT_AUTHORIZED
```

**Alcance aceito:** regressão funcional histórica 196/196 PASS; retomada física alinhada em processos distintos no perfil V2, checkpoint persistido de 8 MiB, arquivo final idêntico byte a byte e por SHA-256 a uma referência local no caso observado. A origem dessa referência permanece `DOCUMENTED_UNATTESTED`. `COMPLETED_V2` não equivale a `DOWNLOADED` V1, nem a homologação de produção.

**Exceções aprovadas exclusivamente para o aceite e encerramento da sprint (não para enfraquecer os controles da aplicação):**
- Critério S6 #1: aceitar demonstração funcional da retomada alinhada observada sem extrapolação de conformidade V1.
- Critério S6 #4: dispensar para este aceite a comprovação remota integral de `[0,P)` antes do append e de `[0,E)` até EOF; a lacuna histórica de 36.954 bytes permanece não comprovada.
- Critério S6 #6: diferir prova real de offset não alinhado/overlap e restringir a alegação de resultado real à retomada alinhada observada.
- Critério S6 #11: diferir matriz integral de janelas de crash, `fsync`, checkpoint, rename, recuperação/ownership.
- Critério S6 #12: diferir comprovação real de segunda execução com zero payload novo (deduplicação após resume).
- Critério S6 #14: diferir a reconciliação documental completa de orçamento S5, `P` físico e `D` persistido para o caso de prova; manter limites S5 integralmente obrigatórios.
- Critério S6 #15: diferir comprovação medida de disco livre e margem antes da escrita.
- Critério S6 #18: diferir medição/threshold de memória limitada em arquivo grande.
- Gate A processual, separado dos 18 critérios: aceitar para fechamento o recibo histórico de Harness com `Process.ExitCode=null` não observado, sem convertê-lo em PASS. A probe sintética posterior `PASS_SYNTHETIC` não fecha a evidência retroativa.

**Preservações e limites:** os demais critérios classificados B/C no relatório continuam com o alcance de evidência indicado e não são recategorizados como A/PASS. O contrato S6 V1 segue aprovado, congelado e ativo, incluindo a exigência de integridade `REMOTE_HASH_REQUIRED` antes do writer, a recusa fail-closed quando não houver prova remota, e a proibição de falso `DOWNLOADED`. A exceção não autoriza fallback de integridade, relaxar orçamentos S5, habilitar V2 globalmente, reescrever provas históricas, publicar releases ou certificar produção.

**Riscos rastreáveis / reabertura:** exigir prova adicional antes de declarar conformidade V1 integral ou habilitar retomada não alinhada de forma homologada; quando relevante, voltar a verificar prefixo remoto e EOF, crash/ownership, deduplicação, S5/`P`/`D`, disco, memória e exit externo do Harness conforme os critérios/gatilhos da seção 7 da [decisão técnica](../reports/S6_FINAL_ACCEPTANCE_DECISION_2026-10-25/REPORT.md). O fechamento administrativo da S6 não converte essas lacunas em conformidade técnica.

**Fonte e autoridade:** aprovação expressa do usuário no chat **Projeto Telegram 3.0**, após apresentação e explicação integral da Opção B e de suas exceções; relatório decisório: [S6_FINAL_ACCEPTANCE_DECISION_2026-10-25](../reports/S6_FINAL_ACCEPTANCE_DECISION_2026-10-25/REPORT.md). Esta entrada registra a dispensa/versionamento de escopo de aceite, sem alterar o texto do contrato original (§§4, 9, 10 e S6-OD-01).

**Transição:** autoriza somente o checkpoint documental de fechamento. A próxima unidade é **S7 — revisão de entrada e preparação**, sem início automático de implementação. S8 depende da sequência e da conclusão/aceite de S7. Testes, Harness, Telegram/RPC, downloads, modificações de código, adoção V2 e Git exigem autorizações próprias.

## Ratificação formal — Contrato integrado S7 + S8 — 2026-10-25

```text
DECISION_ID = S7_S8_CONTRACT_RATIFICATION_2026-10-25
DECISION_MAKER = USER
USER_APPROVAL = EXPLICIT / "ok, aprovo"
CONTRACT = docs/contracts/S7_S8_INCREMENTAL_SYNC_OPERATIONAL_HARDENING_IMPLEMENTATION_CONTRACT.md
CONTRACT_VERSION = 1.0
CONTRACT_STATUS = APPROVED / FROZEN
RATIFICATION_SCOPE = CONTRACT_BASELINE_ONLY
IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
S7_STATUS = ENTRY_REVIEW_PENDING / NOT_STARTED
S8_STATUS = DEFERRED / NOT_STARTED
V1_ACTIVE = YES
V2_GLOBAL = OFF
TESTS_OR_TELEGRAM_OR_GIT_AUTHORIZATION = NOT_GRANTED
```

O usuário aprovou o contrato integrado S7 + S8 v1.0 apresentado no chat Projeto Telegram 3.0. A ratificação congela as regras de sincronização incremental, checkpoints, reconciliação, endurecimento operacional e gates separados por sprint; não autoriza implementação, testes, acesso Telegram, alteração de dados reais ou publicação Git. A revisão de entrada e a execução S7 dependem de autorização posterior; S8 depende da aceitação S7. Contrato normativo: [S7_S8_IMPLEMENTATION_CONTRACT](../contracts/S7_S8_INCREMENTAL_SYNC_OPERATIONAL_HARDENING_IMPLEMENTATION_CONTRACT.md).

## Autorização corretiva offline da S7 — 2026-10-26

~~~text
DECISION_ID = S7_CONTRACTED_CORRECTIVE_IMPLEMENTATION_2026-10-26
DECISION_MAKER = USER
USER_APPROVAL = EXPLICIT / pedido direto anexado a esta atividade
CONTRACT = docs/contracts/S7_ROOT_CAUSE_CORRECTION_IMPLEMENTATION_CONTRACT_2026-10-25.md
CONTRACT_STATUS = APPROVED
IMPLEMENTATION_AUTHORIZATION = AUTHORIZED_OFFLINE_S7_ONLY
IMPLEMENTATION_SCOPE = FIX-01..FIX-06 e dependências técnicas explicitadas no contrato corretivo
VALIDATION_AUTHORIZATION = GATES A-F / offline / conforme ordem e limites do pedido
EXECUTION_MODE = MULTI-AGENT / codex-task-router invocado
S8_STATUS = NOT_AUTHORIZED / DEFERRED
S6_STATUS = CLOSED_WITH_EXCEPTIONS
V1_ACTIVE = YES
V2_GLOBAL = OFF
S5_BUDGETS = PRESERVED
REMOTE_HASH_REQUIRED = PRESERVED
FAIL_CLOSED = PRESERVED
REAL_TELEGRAM_OR_RPC = NOT_AUTHORIZED
REAL_DOWNLOADS = NOT_AUTHORIZED
ORIGINAL_DATABASES_PARTS_AND_S6_PROOFS = PRESERVE
GIT_STAGE_COMMIT_PUSH_RESET_CLEAN = NOT_AUTHORIZED
S7_ACCEPTANCE = PENDING_USER_APPROVAL
~~~

O usuário aprovou expressamente o contrato corretivo indicado e autorizou somente implementação e validação offline da S7, incluindo até dois ciclos corretivos fundamentados. A atividade aplicou essa autorização: os gates offline A–F terminaram, com duas correções limitadas ao fixture de teste RASMOO. Este registro não concede aceite formal da sprint, não muda o contrato integrado S7 + S8 congelado, não autoriza S8, operações reais, alteração das provas S6 ou publicação Git. Os 20 casos históricos continuam 9 V2 / 9 CLI / 2 migration; seus node IDs e recibos permanecem UNRECONCILED.

Evidência: [relatório da implementação corretiva S7](../reports/S7_CORRECTIVE_IMPLEMENTATION_2026-10-26/REPORT.md). Fonte da aprovação: pedido do usuário anexado a esta atividade, datado de 2026-10-26.

## Decisão formal — aceite da S7 com exceções — 2026-10-26

```text
DECISION_ID = S7_ACCEPT_WITH_EXCEPTIONS_2026-10-26
DECISION_DATE = 2026-10-26
DECISION_AUTHORITY = USER_EXPLICIT
APPROVED_OPTION = OPTION_B
S7_ACCEPTANCE = APPROVED_WITH_EXCEPTIONS
S7_STATUS = CLOSED_WITH_EXCEPTIONS
ACCEPTED_EXCEPTIONS = S7-EX-01, S7-EX-02, S7-EX-03, S7-EX-04
S7_A1 = PROVEN_OFFLINE
S7_A2 = PARTIAL / EX-01 ACCEPTED
S7_A3 = PROVEN_OFFLINE
S7_A4 = PARTIAL / EX-02 ACCEPTED
S7_A5 = PROVEN_OFFLINE
S7_A6 = PARTIAL / EX-03 ACCEPTED
S7_EX_04 = ACCEPTED
HISTORICAL_NODE_IDS = UNRECONCILED / 9 V2 + 9 CLI + 2 migration
REGRESSION = 340_PASS_11_SUBTESTS / HISTORICAL IMPLEMENTATION RESULT
S6_STATUS = CLOSED_WITH_EXCEPTIONS
S6_GATE_A = PARTIAL
S6_GATE_B = BLOCKED_BY_REMOTE_EVIDENCE
V1_ACTIVE = YES
V2_GLOBAL = OFF
S5_BUDGETS = PRESERVED
REMOTE_HASH_REQUIRED = PRESERVED
FAIL_CLOSED = PRESERVED
S8_STATUS = DEFERRED
S8_IMPLEMENTATION_AUTHORIZATION = NOT_GRANTED
CODE_CHANGES = NO
TEST_EXECUTIONS = 0
REAL_TELEGRAM_CALLS = 0
GIT_PUBLICATION = NO
```

Por decisão expressa do usuário, a S7 é aceita com as quatro exceções abaixo. Os critérios A2, A4 e A6 continuam parciais; este aceite não declara conformidade integral da S7 nem homologa exclusão remota positiva. O resultado de regressão é evidência histórica do relatório corretivo e não foi repetido nesta atividade.

1. **S7-EX-01 — A2 / evidência de cancelamento e crash.** Aceitar a lacuna de prova direta sem marcar A2 como PASS. O aceite não dispensa risco material caso surja evidência de perda, salto, promoção indevida ou corrupção. Reabertura objetiva: atividade separada autorizada exercita cancelamento nas fronteiras críticas, fecha/reabre o SQLite, compara IDs e checkpoints e comprova ausência de avanço parcial.
2. **S7-EX-02 — A4-C / exclusão remota positiva.** Confirmar exclusão positiva e tombstones ficam fora do escopo homologado. Não criar tombstone por inferência, não excluir arquivos fisicamente e não prometer detecção universal. Reabrir somente com fonte positiva, política e transação aprovadas e testes correspondentes.
3. **S7-EX-03 — A6 / falha global do catálogo.** Aceitar apenas o caminho de sucesso genérico/RASMOO e parcial coberto pelas fixtures. A assertion do caminho negativo falta, embora o código mostre falha e exit 4. Reabrir para provar `catalog=FAILED`, exit não zero e sem sucesso global.
4. **S7-EX-04 — rastreabilidade histórica.** Aceitar resultados atuais como evidência nova, sem dizer que os 20 nodes históricos passaram. Manter grupos 9/9/2, IDs e recibos `UNRECONCILED`. Reabrir somente se fontes originais permitirem reconciliação individual.

Fontes: decisão do usuário nesta atividade; [parecer final S7](../reports/S7_FINAL_ACCEPTANCE_DECISION_2026-10-26/REPORT.md); [relatório corretivo S7](../reports/S7_CORRECTIVE_IMPLEMENTATION_2026-10-26/REPORT.md). A próxima atividade planejada é S8 — Operational Hardening —, ainda diferida e sem autorização de implementação. Qualquer autorização de S8 exige decisão separada. Esta decisão não modifica contratos congelados, provas S6, código, testes ou dados originais, nem autoriza operações Telegram/RPC, downloads ou publicação Git.

## Decisão formal — aceite da S8 com limites documentados — 2026-10-28

```text
DECISION_ID = S8_FORMAL_ACCEPTANCE_2026-10-28
DECISION_DATE = 2026-10-28 / America/Sao_Paulo
DECISION_AUTHORITY = USER_EXPLICIT / "sim aprovo s8"
S8_ACCEPTANCE = APPROVED_WITH_DOCUMENTED_LIMITATIONS
S8_STATUS = CLOSED_WITH_EXCEPTIONS
IMPLEMENTATION = COMPLETE
OFFLINE_INTEGRATION = PASS
FOCUSED_REGRESSION = 32 PASSED / 0 FAILED
OFFLINE_REGRESSION = 366 PASSED / 11 SUBTESTS PASSED / 0 FAILED
STATIC_CHECKS = RUFF_PASS / COMPILEALL_PASS / GIT_DIFF_CHECK_PASS
S8_A1 = PASS_OFFLINE
S8_A2 = PASS_OFFLINE
S8_A3 = PASS_OFFLINE_WITH_NFR02_QUANTITATIVE_LIMIT_NOT_ESTABLISHED
INT_A = PASS_OFFLINE
INT_B = PASS_OFFLINE_WITH_PRIOR_EXCEPTIONS_PRESERVED
S8_EX_01 = NFR02_NO_FORMAL_MEMORY_THRESHOLD / SYNTHETIC_TRACEMALLOC_NOT_TOTAL_RSS
S8_EX_02 = NO_REAL_TELEGRAM_HOMOLOGATION / REAL_CHANNEL_VALIDATION_RESERVED_FOR_S9
S6_STATUS = CLOSED_WITH_EXCEPTIONS
S7_STATUS = CLOSED_WITH_EXCEPTIONS
V1_ACTIVE = YES
V2_GLOBAL = OFF
S5_BUDGETS_AND_REMOTE_HASH_REQUIRED = PRESERVED
S9_STATUS = PLANNED / NOT_STARTED / IMPLEMENTATION_NOT_AUTHORIZED
S10_STATUS = PLANNED / NOT_STARTED
GIT_STAGE_COMMIT_PUSH = NOT_AUTHORIZED_BY_THIS_DECISION / NOT_EXECUTED
S8_GIT_CHECKPOINT = PENDING_SEPARATE_AUTHORIZATION
```

O usuário aprovou formalmente a S8 após receber o resultado da remediação focalizada,
a regressão offline concluída e os limites técnicos de evidência. O aceite
encerra a unidade S8 **com os limites documentados acima**, sem afirmar
homologação de operação Telegram real nem comprovação quantitativa integral
de NFR-02 (pico de 942.996 bytes em tracemalloc de fluxo sintético de 16 MiB,
payload pré-alocado não rastreado; sem limiar aprovado).

A regressão real no ambiente local Windows/Python 3.14.7 passou
366 testes e 11 subtestes, sem falhas, após a correção da fixture de disk gate,
a proteção contra traceback sensível em falhas do logger e a adequação das
assertivas CLI aos eventos JSON sanitizados. Os gates estáticos passaram.
Registro técnico: [S8 Operational Hardening](../reports/S8_OPERATIONAL_HARDENING_IMPLEMENTATION/REPORT.md).

Esta decisão não elimina exceções S6/S7, não ativa V2, não altera contratos
congelados nem autoriza sessão/Telegram/RPC reais, escrita em dados operacionais,
início da S9, stage, commit ou push. O próximo passo natural é o checkpoint Git
local S8, condicionado a autorização específica do usuário; S9 requer gate
e autorização próprios.
