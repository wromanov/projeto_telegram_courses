# Sprint plan — projeto_telegram_courses

## Direcao de entrega vigente — CLI V1 Python + Rich (2026-11-03)

CLI_V1_STACK = PYTHON_3_14 + RICH_15 / EXISTING_PROJECT_DEPENDENCY
UI_SCOPE = SIMPLE_INTERACTIVE_CLI / NOT_FULL_SCREEN_TUI
AFTER_CLI = PROVE_COURSE_DOWNLOAD_E2E_GATE
AFTER_E2E = DESIGN_AND_IMPLEMENT_GUI_V2
MIDNIGHT_GLASS = DESIGN_REFERENCE_ONLY_UNTIL_GUI_REVIEW

Critérios de entrega CLI V1, com interface proporcional:
- Mostrar catalogo de cursos e arquivos legivelmente com Rich (Tree/Table/Prompt/Confirm/Progress conforme utilidade).
- Escolher **arquivos especificos** por selecao multipla, inclusive entre modulos, ou **Baixar tudo** do curso escolhido. Nao confundir curso inteiro com canal inteiro.
- A opcao Baixar tudo corresponde a todos os arquivos elegiveis *descobertos* daquele curso, na ordem canonica. Catalogo parcial deve ser identificado claramente, sem chamar o resultado de curso remoto completo.
- Exibir plano antes de executar: total de arquivos, ordem, tamanhos conhecidos, bytes totais e desconhecidos, itens ja validos e limites. Permitir voltar ou cancelar.
- Executar inicialmente com workers=1, sem paralelismo complexo; status por arquivo, barra de progresso, bytes, MB/s decimal e ETA apenas quando estimavel; concluido/falha/pendente devem refletir estado real.
- Preservar confirmacoes de seguranca, identidade de midia, integridade, deduplicacao, retomada e persistencia SQLite. Nenhum downgrade dos contratos existentes.
- **Aceite funcional** requer demonstracao ponta a ponta do curso/escopo selecionado, com execucao real apenas se especificamente autorizada; testes isolados e recuperacao da midia 585 nao substituem o gate.
- **GUI V2** depende do gate aceito; definicao de tecnologia e telas fica para uma nova decisao, sem implementacao automatica agora.

A presente decisao reprioriza a entrega e os criterios do produto; nao altera retroativamente o status formal de S5/S6/S7/S8/S9 nem cria nova autorizacao para acesso real ao Telegram.

**Checkpoint de execução — 2026-11-07:** próxima atividade proposta `TELEGRAM-3-CLI-V1-OPERATOR-ACCEPTANCE-01`, ainda não autorizada, para conferência manual da CLI Rich sem payload inicialmente. Campanha G4 bounded aceita parcialmente, controles essenciais de transferência/retomada validados, dois roteiros compostos incompletos. `COURSE_DOWNLOAD_E2E_GATE` segue `NOT_PROVEN`. Novos downloads exigem autorização separada, sem reutilizar limites G4. Estado e safe resume em [PROJECT_STATE](../PROJECT_STATE.md) e [checkpoint de 07/11](../checkpoints/TELEGRAM_3_DOC_RECONCILIATION_20261107.md).

---

## Estado corrente da S9 — correção P0 do ledger — 2026-11-01

O estado vigente e a autoridade de autorização permanecem em [PROJECT_STATE](../PROJECT_STATE.md). A atividade `TELEGRAM_S9_LEDGER_PERFORMANCE_FIX_01` foi concluída com implementação e validação somente offline/sintéticas: benchmark ledger-only de 1 GiB em 373,02 s, E2E G0–G9 sintético aprovado, regressão com 283 testes aprovados e revisão independente `PASS_WITH_LIMITS`. O contrato S9 v1 permanece congelado e inalterado. Relatório e artefatos: [S9_LEDGER_PERFORMANCE_FIX_01](../../reports/S9_LEDGER_PERFORMANCE_FIX_01/REPORT.md).

Nenhuma chamada Telegram, download real, escrita operacional, S10 ou operação de publicação Git ocorreu. O plano continua sendo referência e não concede nova autorização. A primeira tentativa de envio foi recusada pela revisão automática; após autorização expressa, a ferramenta aceitou o envio do relatório. O readback ainda mostra o snapshot anterior, então confirmar visibilidade antes de qualquer nova tentativa.

## Estado histórico da S9 — 2026-10-30

O estado desta delivery unit é mantido em
[PROJECT_STATE](../PROJECT_STATE.md). A atividade anterior
`TELEGRAM_S9_FINAL_INTEGRATION_01` entregou integração offline **parcial**;
o runner nativo pós-refatoração passou 121 testes S9 focados, 218 testes
afetados S5–S8 e 488 testes offline + 11 subtests na suíte completa, com exit 0
em todas as fases. O teste AST passou e 52 testes do ledger passaram
isoladamente. A revisão de segurança do snapshot offline passou com limites e
sem achados materiais de código. G1 não
tem produtor de PASS, G2/G3 seguem `NOT_ASSESSED` e G6–G9 não foram fechados.
S9 real e S10 não estão autorizados. O usuário autorizou agora a atividade
`TELEGRAM_S9_G1_G9_OFFLINE_COMPLETION_01`, limitada à implementação, validação
offline, revisão independente e relatório para completar G1–G9 sob o contrato
congelado. A implementação sintética foi entregue, mas a revisão de segurança
encontrou um finding alto e dois médios; a regressão nativa expirou em
focused-s9. O estado desta atividade é
`S9_OFFLINE_ORCHESTRATION_PARTIAL`; aguardar autorização humana direta antes de
outro ciclo corretivo. Nenhuma operação Telegram, escrita no banco operacional
ou publicação Git está autorizada. Detalhes em
[REPORT](../../reports/S9_G1_G9_OFFLINE_COMPLETION_01/REPORT.md).
O relatório foi enviado e observado no chat canônico; a resposta confirmou
`S9_OFFLINE_ORCHESTRATION_PARTIAL` sem conceder autorização adicional.

**Delivery unit:** Sprint
**Execution model:** Incremental vertical slices
**Maximum active formal activities:** 1
**Plan status:** Defined from the approved roadmap. Current state and authorization are recorded only in PROJECT_STATE. S1–S10 are not authorized by this plan.

DOCUMENT_ROLE = EXECUTION_PLAN
RECONCILED_AT = 2026-10-09 / America/Sao_Paulo

A sequência S0–S10 vem do baseline do usuário, seção 7. [REQUIREMENTS.md](../../product/REQUIREMENTS.md) é a authority dos requisitos; [ROADMAP.md](ROADMAP.md) define as fases. O estado corrente e toda autorização ficam em PROJECT_STATE.md (authority canônica mantida localmente e omitida da baseline pública). Critérios abaixo são evidências planejadas, não resultados já obtidos.

## S0 — Repository / Project Bootstrap

- **SPRINT_ID:** S0
- **OBJECTIVE:** Estabelecer repositório e ambiente executável de desenvolvimento a partir da abertura aceita.
- **SCOPE:** Bootstrap futuro do repositório, ambiente Python, pyproject.toml, pytest/Ruff e ponto inicial da CLI; preservar documentos e excluir segredos, sessões e artefatos locais indicados nesta seção.
- **OUT_OF_SCOPE:** Implementação de capacidades Telegram, catálogo ou download. Nesta atividade de abertura, S0 e qualquer operação Git mutável são proibidos.
- **DEPENDENCIES:** Project Opening Gate PASS; binding/pins verificados; arquitetura/fundação aprovadas; DoR e autorização específica de S0. Autorização de ações Git deve identificar operação e escopo.
- **FUNCTIONAL_REQUIREMENTS:** Nenhuma capacidade de produto entregue em S0; FR-16 terá seu contrato de configuração preservado.
- **TECHNICAL_REQUIREMENTS:** CPython 3.14.x, pyproject.toml, venv, pytest, Ruff; limites de adapters/repositórios conhecidos; proteção de segredos e sessão.
- **DELIVERABLES:** Repositório governado, toolchain configurada, entrada mínima da CLI e instruções de desenvolvimento.
- **TESTS:** Spike SP-01 de stack Windows; smoke da entrada em Windows, carregamento de configuração básica e execução de pytest/Ruff; inspeção das exclusões Git; nenhuma conexão Telegram.
- **ACCEPTANCE_CRITERIA:** Root e metadados Git verificáveis; estrutura Python e de testes válida; ambiente reproduzível a partir de `pyproject.toml` e dependências-base instaláveis; imports mínimos, pytest e Ruff executáveis; configuração-base carregada; entrada mínima da CLI responde em smoke Windows; documentos preservados; `.gitignore` exclui `.env`, `.env.*`, `*.session`, `*.session-journal`, `data/session/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `logs/` e `*.log` antes do primeiro commit.
- **GATES:** Opening Gate e DoR como predecessores; gates aplicáveis de módulo, integração, fluxo acumulado, regressão e handoff para fechamento.
- **DEFINITION_OF_DONE:** Aceite e evidências de bootstrap concluídos, estado reconciliado e handoff verificável. Fechamento técnico não concede commit/push.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S0 aceito; DoR e autorização de S1 verificados.
- **STATUS:** Ver PROJECT_STATE; o plano não inicia S0.

## S1 — Authentication + Channel Discovery

- **SPRINT_ID:** S1
- **OBJECTIVE:** Authenticate to Telegram and discover/select accessible channels.
- **SCOPE:** TelegramGateway authentication and channel discovery through the Telethon adapter.
- **OUT_OF_SCOPE:** Message cataloging, parsing, downloading, GUI, and unrelated Telegram administration.
- **DEPENDENCIES:** S0 accepted; Telegram credentials/session setup governed by the requirements; gateway boundary available.
- **FUNCTIONAL_REQUIREMENTS:** FR-01, FR-02.
- **TECHNICAL_REQUIREMENTS:** MTProto user account; Telethon 1.45.x adapter; asyncio; protect credentials/session; keep Telethon types inside adapter.
- **SESSION_PROTECTION_DESIGN:** APPROVED; `DESIGN_DEFINED = YES`; S1-A offline implementation and DPAPI/ACL verification PASS. S1-C real authentication and session reuse later passed on user-provided evidence; see `PROJECT_STATE` for adjudication and verification limits.
- **FLOODWAIT_RETRY_OWNERSHIP:** APPROVED (design decision only; no implementation evidence).
- **S1_DOR:** PASS; evidence: `docs/reports/S1_DOR_GAP_REVIEW_2026-10-07.md`; S1-B offline implementation authorization and result are recorded in `docs/governance/APPROVALS_AND_DECISIONS.md` and `PROJECT_STATE.md`.
- **S1-B_OFFLINE_AUTHENTICATION_GATEWAY:** PASS; frozen contract: `docs/contracts/S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT.md`; offline full pytest and Ruff PASS; no real Telegram authentication, credential or session.
- **NEXT_CANDIDATE:** S2 — Message Scanner + SQLite Persistence; S1 has been formally accepted and closed after GOV-01 resolution (see PROJECT_STATE (authority canônica mantida localmente e omitida da baseline pública) and the S1-D contract). S2 remains PLANNED / NOT_STARTED and requires its own entry review and implementation authorization.
- **S1-C_ENTRY_REVIEW:** PASS / READINESS_BLOCKERS = NONE; read-only review result supplied for the S1 checkpoint; readiness does not grant execution authorization.
- **DELIVERABLES:** Authenticated gateway path and channel discovery flow.
- **TESTS:** Unit tests without Telegram login for application behavior; separate Telegram integration checks for authentication and channel discovery.
- **ACCEPTANCE_CRITERIA:** FR-01/FR-02 passam pelo gateway com conta própria e canal acessível; falhas de autenticação/acesso são controladas; proteção de credenciais/sessão e testes separados atendem NFR-05/NFR-06/NFR-09/NFR-10.
- **GATES:** Authentication and channel-discovery acceptance.
- **DEFINITION_OF_DONE:** Approved requirement criteria and relevant tests pass; no unresolved failure blocks the next slice.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S1 accepted; channel identity can be supplied to the scanner.
- **STATUS:** S1 CLOSED / S1-A PASS / S1-B PASS / S1-C PASS / S1-D formally accepted and closed; see PROJECT_STATE for evidence and current authorization. S2 is IMPLEMENTED_OFFLINE / REAL_VALIDATION_PENDING / NOT_CLOSED.

## S2 — Message Scanner + SQLite Persistence

- **SPRINT_ID:** S2
- **OBJECTIVE:** Scan channel messages and persist the message/catalog source data in SQLite.
- **SCOPE:** Message iteration/refetch boundary, scanner, initial migrations/repositories, message persistence and scan-run/checkpoint records as defined by Foundation.
- **OUT_OF_SCOPE:** Specialized RASMOO parsing, media download, and full-channel bulk download.
- **DEPENDENCIES:** S1 accepted; TelegramGateway; SQLite repository and migration foundation.
- **FUNCTIONAL_REQUIREMENTS:** FR-03, FR-09.
- **TECHNICAL_REQUIREMENTS:** SQLite + aiosqlite; migrations; foreign keys; WAL; configured busy timeout; transactions for related writes; raw SQL only in persistence layer.
- **DELIVERABLES:** Scanner and initial persisted message/catalog storage.
- **TESTS:** Unit tests without Telegram; local SQLite integration tests using temporary databases; Telegram integration test for history scanning.
- **ACCEPTANCE_CRITERIA:** FR-03/FR-09: varredura preserva identidade e mídias, unicidade por canal/mensagem e registros sobrevivem ao reinício; migrations/transactions são verificadas em SQLite temporário.
- **GATES:** Scanner and persistence acceptance.
- **DEFINITION_OF_DONE:** Requirement criteria, unit/local integration tests and migrations pass. S2 closure also requires separately authorized Telegram history acceptance; offline validation alone does not close this sprint.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S2 accepted; persisted scan input is available for parser work. S3 remains NOT_STARTED and implementation requires separate authorization.
- **STATUS:** ACCEPTED / CLOSED. Offline evidence: 140 pytest tests + 11 subtests, Ruff and diff check PASS. Real scan SQLite acceptance: PARTIAL / MESSAGE_LIMIT, 10 messages, 5 media; checkpoint, foreign keys, uniqueness, integrity, no downloads, and close/reopen PASS. See PROJECT_STATE (authority canônica mantida localmente e omitida da baseline pública) and CONTINUITY_RECORD (authority canônica mantida localmente e omitida da baseline pública).

## S3 — RASMOO Parser + Catalog CLI

- **SPRINT_ID:** S3
- **OBJECTIVE:** Parse RASMOO catalog structures and expose the catalog through the CLI.
- **SCOPE:** Pluggable parser contract, first specialized RasmooParser, GenericParser fallback, catalog builder, pre-scan/catalog CLI behavior.
- **OUT_OF_SCOPE:** Media transfer, GUI, broad parser coverage beyond approved initial model, mass download.
- **DEPENDENCIES:** S2 accepted; persisted messages available; domain/catalog model established.
- **FUNCTIONAL_REQUIREMENTS:** FR-04, FR-05, FR-13; FR-03 as parser input.
- **TECHNICAL_REQUIREMENTS:** Parser independent of Telegram transport, filesystem, database, retries, downloads, and CLI; Channel → optional Track → Course → optional Module → Lesson → MediaItem.
- **DELIVERABLES:** Parser contract and implementations; catalog builder and CLI view; controlled RASMOO sample set.
- **TESTS:** Unit tests for RasmooParser, GenericParser, catalog builder; unit tests do not require Telegram. Parser sample includes the documented RASMOO acceptance cases as available.
- **ACCEPTANCE_CRITERIA:** FR-04/FR-05/FR-13 passam em fixtures controladas: hierarquia com Track/Module opcionais, parser selecionado, catálogo/pre-scan visíveis; = / == / === / #Fxxx não é dependência universal.
- **GATES:** Catalog/parser acceptance; parser correctness before mass download.
- **DEFINITION_OF_DONE:** Approved parser/catalog criteria and corresponding tests pass; no parser performs infrastructure work.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S3 accepted; catalog can identify a selectable lesson/media item.
- **STATUS:** ACCEPTED / CLOSED. `S3-MAG-01` PASS; generic core and RasmooParser PASS; real catalog validation PASS_WITH_SCOPE; idempotency PASS; Windows CLI PASS; full regression 167 passed + 11 subtests; Ruff and diff check PASS. See PROJECT_STATE (authority canônica mantida localmente e omitida da baseline pública) and CONTINUITY_RECORD (authority canônica mantida localmente e omitida da baseline pública).

O scan real limitou-se a 30 mensagens e 26 mídias, encerrando por
`MESSAGE_LIMIT`; não cobre o canal inteiro. A gramática aprovada limita-se aos
formatos comprovados. S3 não validou downloads; a validação integral do produto
no canal real permanece planejada para S9.

## S4 — Single Media Download + Local Organization + Deduplication

- **SPRINT_ID:** S4
- **OBJECTIVE:** Deliver the first end-to-end user value by downloading one selected lesson media item and safely rerunning the flow.
- **SCOPE:** Single-item selection/download, bounded transfer path, file validation, organized local path, persisted status and second-run deduplication.
- **OUT_OF_SCOPE:** Course-wide queue, mass download, advanced concurrency optimization, GUI, scheduling, packaging, and resume acceptance reserved for later slices.
- **DEPENDENCIES:** S1 authentication/channel discovery; S2 catalog persistence; S3 RASMOO parsing/catalog CLI; download and filesystem contracts.
- **FUNCTIONAL_REQUIREMENTS:** FR-06, FR-07, FR-08, FR-09, FR-11; relevant FR-14 progress behavior.
- **TECHNICAL_REQUIREMENTS:** Stream large media without loading entire files into memory; bounded workers; `.part` file; validate size; optional configured hash; atomic finalization before DB `DOWNLOADED`; deterministic sanitized Windows path; reconcile Telegram + SQLite + filesystem.
- **DELIVERABLES:** Single media download flow, organized file, persisted download record and rerunnable deduplication behavior.
- **TESTS:** Unit tests for path sanitization/deduplication/state; local filesystem/SQLite integration for `.part` and atomic finalize; Telegram integration for a small real media item.
- **ACCEPTANCE_CRITERIA:** `FIRST_VERTICAL_SLICE_GATE = PASS` only when every criterion below passes:

  ```text
  AUTH = PASS
  CHANNEL_DISCOVERY = PASS
  RASMOO_PARSE = PASS
  CATALOG_PERSISTENCE = PASS
  SINGLE_DOWNLOAD = PASS
  FILE_VALIDATION = PASS
  PATH_ORGANIZATION = PASS
  DEDUPLICATION = PASS
  SECOND_RUN_NO_DUPLICATE = PASS
  ```

- **GATES:** `FIRST_VERTICAL_SLICE_GATE`.
- **DEFINITION_OF_DONE:** All nine milestone checks pass end-to-end; isolated component tests alone do not satisfy this gate.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S4 and `FIRST_VERTICAL_SLICE_GATE` accepted; course-level selection/queue can build on proven single-item behavior.
- **STATUS:** ACCEPTED / CLOSED / formal acceptance and `FIRST_VERTICAL_SLICE_GATE` passed under S4-CLOSE-01.
- **IMPLEMENTATION_AUTHORIZATION:** GRANTED for the bounded offline implementation and one real single-media validation; Git publication separately authorized by S4-CLOSE-01. No scope expansion is implied.
- **CONTRACT:** [S4_SINGLE_MEDIA_DOWNLOAD_CONTRACT](../../contracts/S4_SINGLE_MEDIA_DOWNLOAD_CONTRACT.md), frozen for the first lesson media scope.

## S5 — Course/Module Selection + Download Planner + Download Queue

- **SPRINT_ID:** S5
- **OBJECTIVE:** Extend the proven single-item flow to course/module selection and queued downloads.
- **SCOPE:** User selection at course/module/lesson level, download planning and queue orchestration.
- **OUT_OF_SCOPE:** Resume/recovery, incremental synchronization, unbounded/multi-process workers, GUI.
- **DEPENDENCIES:** S4 and First Vertical Slice Gate accepted; catalog and single-item download flow stable.
- **FUNCTIONAL_REQUIREMENTS:** FR-06, FR-07, FR-14; FR-11 for already-known items.
- **TECHNICAL_REQUIREMENTS:** DownloadPlanner, queue, bounded/configurable workers; parser-independent domain selection.
- **DELIVERABLES:** Course/module selection, planner, queue, user-facing progress path.
- **TESTS:** Unit tests for planner/queue and selection; local persistence/filesystem integration; separate Telegram integration where queue execution is required.
- **ACCEPTANCE_CRITERIA:** Seleção de curso/módulo gera plano e fila apenas dos itens escolhidos; itens já válidos são deduplicados; progresso diferencia sucesso/falha; workers configuráveis permanecem limitados (padrão 2).
- **GATES:** Course selection and queue acceptance.
- **DEFINITION_OF_DONE:** Approved selection/planning/queue criteria and relevant tests pass; no duplicate or conflicting state is introduced.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S5 accepted; partial transfer state can be recovered by the next slice.
- **STATUS:** CLOSED / FORMAL ACCEPTANCE APPROVED / CLOSURE PASS. Offline validation PASS (206 passed + 11 subtests; 56 focused tests) and S5-REAL-PROOF-01 PASS; evidence covers five observed media only (CATALOG_SCOPE = PARTIAL), and gateway calls were not directly observable. Historical failure, correction, recovery and deduplication checkpoints are preserved; see PROJECT_STATE (authority canônica mantida localmente e omitida da baseline pública).
- **IMPLEMENTATION_AUTHORIZATION:** Historical bounded authorizations are recorded in PROJECT_STATE and continuity checkpoints; this plan does not grant new authority or formal acceptance.

## S6 — Partial Download + Resume + Recovery

- **SPRINT_ID:** S6
- **OBJECTIVE:** Recover interrupted downloads and resume safely from validated partial files.
- **SCOPE:** Partial-state detection, Telegram message/media refetch, resume offset, recovery and final validation.
- **OUT_OF_SCOPE:** Incremental catalog synchronization and optimization unrelated to recovery.
- **DEPENDENCIES:** S4 single-download/file-commit contract; S5 queue behavior where applicable.
- **FUNCTIONAL_REQUIREMENTS:** FR-12; related FR-08/FR-09.
- **TECHNICAL_REQUIREMENTS:** As frozen in the S6 contract: physical offset authority; SHA-256 remote range coverage for the complete prefix; aligned stream plus validated overlap; fsync before SQLite checkpoint; existing state recovery; S5 queue/budget/disk reuse; no schema migration; atomic no-overwrite finalization.
- **DELIVERABLES:** Restart-safe partial download recovery and resume path.
- **TESTS:** Unit tests for state transitions; local `.part` recovery integration; technical real-large-file test: interrupt deliberately, restart, refetch message/media, resume, validate, finalize, persist `DOWNLOADED`.
- **ACCEPTANCE_CRITERIA:** Recovery produces the correct complete file and state after a controlled interruption; technical validation passes before declaring resume complete.
- **GATES:** Large-file resume technical validation.
- **DEFINITION_OF_DONE:** Recovery criteria and technical test pass; otherwise FR-12 resume capability remains open.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S6 accepted; checkpoint/state behavior available for incremental synchronization.
- **STATUS:** ACCEPTED / CLOSED_WITH_EXCEPTIONS on 2026-10-25 by explicit user approval of Option B. The V1 technical gates remain Gate A PARTIAL and Gate B BLOCKED_BY_REMOTE_EVIDENCE; this is not V1 full conformity. See decision (authority canônica mantida localmente e omitida da baseline pública) and [final matrix](../../reports/S6_FINAL_ACCEPTANCE_DECISION_2026-10-25/REPORT.md). S7 entry review pending; implementation not authorized.
- **CONTRACT_STATUS:** APPROVED / FROZEN by formal user acceptance on 2026-10-12; see [S6 contract](../../contracts/S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md) and PROJECT_STATE (authority canônica mantida localmente e omitida da baseline pública).
- **IMPLEMENTATION_AUTHORIZATION:** GRANTED by direct user request for S6-IMPL-01 / OFFLINE ONLY. No real Telegram access, schema changes or Git publication.
- **OFFLINE_VALIDATION:** PASS / previous baseline: 65 focused S6/S4/S5 tests and full pytest 215 passed + 11 subtests. Current A2 remediation: 82 focused S4/S5/S6 tests and one full pytest run with 247 passed + 11 subtests (251.16s); Ruff and compileall PASS. `git diff --check` reports inherited historical whitespace in `CONTINUITY_RECORD.md` (trailing whitespace at line 106 and a blank line at EOF); not cleaned to preserve that checkpoint.
- **REAL_TELEGRAM_TECHNICAL_PROOF:** PARTIAL / aligned common OPERATIONAL_ONLY two-process proof PASS on 2026-10-18; nonaligned proof not accepted. Formal S6 scope-revised acceptance granted 2026-10-25 with technical proof exceptions; no V1 full conformance implied.
- **S6-A2_PREFIX_BOUNDARY_REMEDIATION:** OFFLINE PASS / existing S6-D02 applied without contract change. Crossing variable-length remote hash ranges are checked using local `[a,P)` plus remote complement `[P,b)` before any write; the aligned stream begins at `W=floor(P/262144)*262144`, and overlap `O=P-W` is compared before append. Validation replies count toward runtime byte totals; `.part` length remains the physical checkpoint. Existing S5 reservations, queue, retry, SQLite checkpoint/fsync and no-overwrite behavior remain in force.
- **S6-A2_VALIDATION:** PASS / 82 focused S4/S5/S6 tests; one full offline pytest run, 247 passed + 11 subtests in 251.16s; Ruff and compileall PASS. `git diff --check` WARNING / trailing whitespace at `CONTINUITY_RECORD.md:106` and blank line at EOF, apparently inherited from a preserved historical checkpoint; left unchanged. Independent Validator static review PASS; its own pytest was not run after its sandbox asyncio smoke failure. Root ran tests outside sandbox under Python 3.14.7 after asyncio smoke PASS.
- **S6-A2_REAL_RESUME:** ALIGNED_PROOF_PASS / one user-authorized common aligned proof completed with full-file and SQLite/checkpoint validation. No nonaligned proof was executed or authorized; obtain a separate user decision before any further real operation. Formal acceptance remains pending and this plan does not authorize another real operation.

## S7 — Incremental Synchronization

- **INTEGRATED_IMPLEMENTATION_CONTRACT:** [S7 + S8 contract v1.0](../../contracts/S7_S8_INCREMENTAL_SYNC_OPERATIONAL_HARDENING_IMPLEMENTATION_CONTRACT.md) / APPROVED_FROZEN 2026-10-25; does not authorize execution.

- **SPRINT_ID:** S7
- **STATUS:** CLOSED_WITH_EXCEPTIONS / APPROVED_WITH_EXCEPTIONS by explicit user decision on 2026-10-26 (OPTION_B). A1/A3/A5 are proven only in the documented offline scope; A2/A4/A6 remain PARTIAL under accepted EX-01/02/03. EX-04 is accepted; historical failure IDs/receipts remain unreconciled. This is not full S7 conformity and does not positively homologate remote deletion. See the [formal closure report](../../reports/S7_FORMAL_CLOSURE_2026-10-26/REPORT.md), [acceptance decision](../../reports/S7_FINAL_ACCEPTANCE_DECISION_2026-10-26/REPORT.md), [corrective implementation report](../../reports/S7_CORRECTIVE_IMPLEMENTATION_2026-10-26/REPORT.md), approval record (authority canônica mantida localmente e omitida da baseline pública), and PROJECT_STATE (authority canônica mantida localmente e omitida da baseline pública).
- **ACCEPTANCE_CRITERIA_STATUS:** S7_A1=PROVEN_OFFLINE; S7_A2=PARTIAL / EX-01 ACCEPTED; S7_A3=PROVEN_OFFLINE; S7_A4=PARTIAL / EX-02 ACCEPTED; S7_A5=PROVEN_OFFLINE; S7_A6=PARTIAL / EX-03 ACCEPTED; S7_EX_04=ACCEPTED; HISTORICAL_NODE_IDS=UNRECONCILED (9 V2 / 9 CLI / 2 migration).
- **REGRESSION_EVIDENCE:** 340_PASS_11_SUBTESTS / historical result from corrective implementation report; not executed during formal closure.
- **OBJECTIVE:** Synchronize newly available/changed channel messages incrementally using persisted checkpoints.
- **SCOPE:** Incremental scanner/checkpoint handling and reconciliation with the persisted catalog.
- **OUT_OF_SCOPE:** Full redesign of parser/download flows or scheduling not defined by requirements.
- **DEPENDENCIES:** S2 persisted scans/checkpoints; S3 catalog parser; S6 recovery state if synchronization touches in-flight items.
- **FUNCTIONAL_REQUIREMENTS:** FR-10, FR-09, FR-11.
- **TECHNICAL_REQUIREMENTS:** Telegram remains remote source of truth; SQLite checkpoint/catalog state and filesystem are reconciled; scan runs remain auditable.
- **DELIVERABLES:** Incremental synchronization path and checkpoint updates.
- **TESTS:** Unit tests for checkpoint decisions and deduplication; local SQLite integration; Telegram integration for history changes where available.
- **ACCEPTANCE_CRITERIA:** Execuções incrementais e checkpoints atendem FR-10 sem duplicar catálogo/downloads; definir e validar o alcance de detecção de edições/remoções antes do início de S7, com fixtures de mudança e recuperação de scan incompleto.
- **GATES:** Incremental synchronization acceptance.
- **DEFINITION_OF_DONE:** Approved sync criteria and related tests pass; repeated runs are consistent.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S7 formally closed with exceptions; S8 Definition of Ready/readiness and separate express implementation authorization are required before starting.

## S8 — Operational Hardening

- **INTEGRATED_IMPLEMENTATION_CONTRACT:** [S7 + S8 contract v1.0](../../contracts/S7_S8_INCREMENTAL_SYNC_OPERATIONAL_HARDENING_IMPLEMENTATION_CONTRACT.md) / APPROVED_FROZEN 2026-10-25; S8 implementation dependent on S7 acceptance and separate authorization.

- **SPRINT_ID:** S8
- **STATUS:** CLOSED_WITH_EXCEPTIONS / FORMALLY_ACCEPTED_BY_USER_2026-10-28 / OFFLINE_REGRESSION_PASS_366_PLUS_11_SUBTESTS; limits on NFR-02 quantitative memory proof and real Telegram validation remain documented. Implementation authorization was provided by separate S8 Card; S9 remains not authorized.
- **OBJECTIVE:** Harden failures, retries, logging, disk safety, progress, and configuration for normal operation.
- **SCOPE:** Error taxonomy, bounded retry, FloodWait handling, structured operational logs, disk-capacity gate, configuration validation, bounded concurrency review.
- **OUT_OF_SCOPE:** GUI, distributed execution, unlimited workers, new product capabilities not in the approved requirements.
- **DEPENDENCIES:** Core scanner/catalog/download/sync flows from S1–S7.
- **FUNCTIONAL_REQUIREMENTS:** FR-12, FR-14, FR-15, FR-16; related FR-06/FR-10.
- **TECHNICAL_REQUIREMENTS:** Recorded error taxonomy; bounded exponential backoff plus jitter for transient errors; respect FloodWait; do not auto-retry terminal/configuration/access/disk failures; no secrets in logs; compare known bytes to available space and safety margin; workers remain bounded.
- **DELIVERABLES:** Operational hardening across existing flows, with user-oriented CLI progress and structured logs.
- **TESTS:** Unit tests for config/error/retry/path logic; local integration for disk and persistence failure behavior; Telegram integration for reproducible/simulable rate-limit behavior.
- **ACCEPTANCE_CRITERIA:** FR-12/FR-14/FR-15/FR-16 e NFR-02–NFR-07 passam nos fluxos existentes: configuração/progresso/logs seguros, falhas terminais controladas, retries/FloodWait limitados e evidência de memória/paralelismo.
- **GATES:** Operational hardening acceptance; disk-capacity and credential/session protection checks.
- **DEFINITION_OF_DONE:** Approved operational requirements and relevant tests pass; unresolved security/operational blockers are absent.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S8 accepted; real-channel RASMOO validation can be performed with bounded scope.
- **STATUS:** CLOSED_WITH_EXCEPTIONS / APPROVED_WITH_DOCUMENTED_LIMITATIONS. Evidência e decisão: [relatório S8](../../reports/S8_OPERATIONAL_HARDENING_IMPLEMENTATION/REPORT.md) e [aceite formal S8](../../governance/APPROVALS_AND_DECISIONS.md#decisão-formal--aceite-da-s8-com-limites-documentados--2026-10-28). A validação real permanece planejada para S9, não iniciada.

## S9 — RASMOO Real-Channel Acceptance

- **SPRINT_ID:** S9
- **OBJECTIVE:** Validate the integrated product against the real RASMOO channel and controlled acceptance dataset.
- **SCOPE:** Real-channel authentication, discovery, scanning, parsing, catalog, media selection/download, organization, persistence, synchronization and recovery checks as required by the approved baseline.
- **OUT_OF_SCOPE:** Unbounded mass download; expansion to unrelated channels/parser families; new features introduced only for the test.
- **DEPENDENCIES:** S1–S8 accepted; test account/channel access and controlled dataset available.
- **FUNCTIONAL_REQUIREMENTS:** FR-01–FR-16 e NFR-01–NFR-10 conforme matriz de cobertura da amostra controlada; condições de suporte/resume permanecem explícitas.
- **TECHNICAL_REQUIREMENTS:** Separate Telegram integration suite; RASMOO dataset includes the approved representative structures and edge cases; no test credentials/session material are versioned/logged.
- **DELIVERABLES:** Real-channel acceptance evidence and defects/limitations record.
- **TESTS:** Separate Telegram integration/acceptance checks against the controlled RASMOO sample, not as a dependency of normal unit suite.
- **ACCEPTANCE_CRITERIA:** Dataset checks pass and the integrated behavior matches canonical functional/non-functional requirements; no mass-download operation is assumed by acceptance.
- **GATES:** RASMOO real-channel acceptance gate.
- **DEFINITION_OF_DONE:** Acceptance results are recorded; blocking discrepancies are resolved or explicitly remain release blockers.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S9 accepted for the agreed distribution scope; packaging documentation inputs are known.
- **STATUS:** CONTRACT_APPROVED_FROZEN_V1.0 / RAT-01..RAT-05_APPROVED_2026-10-28 / S9_EXECUTION_NOT_STARTED_NOT_AUTHORIZED. O supervisor/ledger com validação offline é pré-requisito G0 antes de operações reais. Ver [contrato S9](../../contracts/S9_RASMOO_REAL_CHANNEL_ACCEPTANCE_CONTRACT_2026-10-28.md).

## S10 — Windows Packaging + Operational Documentation

- **SPRINT_ID:** S10
- **OBJECTIVE:** Package the validated application for Windows and document operation.
- **SCOPE:** Windows distribution packaging and operational documentation.
- **OUT_OF_SCOPE:** GUI, unsupported platforms, new download features, publishing/releasing without the required separate authorization.
- **DEPENDENCIES:** S9 real-channel acceptance; Windows compatibility and operational requirements reconciled.
- **FUNCTIONAL_REQUIREMENTS:** FR-15/FR-16 where operational docs/configuration depend on them.
- **TECHNICAL_REQUIREMENTS:** Windows compatibility; safe configuration, credentials and session handling; packaging follows validated runtime dependencies.
- **DELIVERABLES:** Windows package and operational documentation.
- **TESTS:** Windows packaging/runtime smoke and documented operational checks after a supported test environment exists.
- **ACCEPTANCE_CRITERIA:** Pacote inicia em Windows e executa os fluxos aceitos/documentados de catálogo e download; configuração, segredos/sessões e logs preservam contratos; evidência de NFR-01/NFR-05/NFR-06.
- **GATES:** Distribution/release acceptance.
- **DEFINITION_OF_DONE:** Approved packaging and documentation criteria pass; no release/publish action occurs without its authority.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** None in the approved roadmap.
- **STATUS:** PLANNED / NOT_STARTED.

## Planning limitations

- Sprint durations, dates, capacity, and staffing were not approved in the recovered baseline and are intentionally omitted.
- Os critérios operacionalizam o Card B junto à arquitetura/fundação; thresholds de memória, máximo de workers, proteção Windows da sessão e alcance de sync exigem definição/evidência antes das unidades pertinentes.
- Estado de seleção, prontidão e autorização está somente em PROJECT_STATE; plano e aprovação de fundação não concedem execução.

## Future sprint entry conditions

Estas condições limitam apenas as unidades afetadas pelos findings técnicos; não são blockers globais do projeto nem autorização de execução.

| Unidade | Condição de entrada/decisão a fechar | Evidência relacionada |
|---|---|---|
| S0 | Executar SP-01 em Windows e registrar versões efetivamente usadas, imports, async, SQLite/versão SQLite e compatibilidade do toolchain. | AUD-MED-07; SP-01 |
| S1 | Verificar a implementação da proteção local de sessão Telegram já definida antes de criar sessão real; manter credenciais/sessão excluídas e redigidas. O ownership básico de FloodWait/retry foi fechado no desenho aprovado. | AUD-MED-04/06; NFR-05/NFR-06 |
| S2 | Fechar identidade/revisão de mídia, semântica de checkpoint, cardinalidades, constraints, índices e estratégia de paginação antes de schema/migrations/checkpoints definitivos; declarar formatos iniciais suportados quando pertinentes. | AUD-HIGH-01/03; AUD-MED-01/02/07; SP-02/SP-05 |
| S3 | Validar amostra RASMOO representativa e associações determinísticas, incluindo órfãos/edições, antes de fechar parser e schema relacionados. | AUD-MED-01; SP-02 |
| S4 | Fechar matriz de reconciliação filesystem↔SQLite, ownership/concorrência da transferência, transições de estado, política de destino existente e limites de path; exercitar falhas entre rename e commit. Fazer prova pequena de streaming/resume antes de congelar o adapter. | AUD-HIGH-02; AUD-MED-03/04/05/07; SP-03/SP-04 |
| S6 | Concluir spike de interrupção, refetch, offsets alinhados/não alinhados e comparação com download de referência antes de declarar resume aceito. | SP-03; contrato de resume da fundação |
| S7 | Definir alcance de sincronização para mensagens novas, edições antigas, mídia substituída, exclusão/perda de acesso e scan interrompido; validar a matriz integrada e separar estado remoto do estado de transferência. | AUD-HIGH-01/03; AUD-MED-03; SP-05 |
| S8–S9 | Definir cenários e thresholds mensuráveis de mídia, memória, catálogo, tarefas e workers para o aceite operacional/real; fechar redaction e proteção transversal sem secrets em DB/logs. | AUD-MED-04/06/07 |
| S10 | Verificar política de path e proteção de sessão no ambiente empacotado; CLI operacional adicional pode ser fechada progressivamente conforme cada fluxo for introduzido. | AUD-MED-05/06; AUD-LOW-01 |

### Spikes técnicos

| Spike | Alocação | Decisão |
|---|---|---|
| SP-01 — Stack Windows | S0 | EXECUTE_IN_S0 |
| SP-02 — RASMOO representativo | Antes de fechar schema/parser em S2–S3 | EXECUTE_BEFORE_SPRINT_S2 |
| SP-03 — Streaming e resume | Prova pequena antes de congelar adapter em S4; validação completa antes do aceite de S6 | EXECUTE_BEFORE_SPRINT_S4_AND_COMPLETE_BEFORE_S6 |
| SP-04 — Commit Windows | S4, antes do aceite de reconciliação/finalização | EXECUTE_IN_S4 |
| SP-05 — Sync e mídia revisada | Definições antes de S2; validação integrada em S7 | EXECUTE_BEFORE_SPRINT_S2_AND_VALIDATE_IN_S7 |

## Controles transversais e rastreabilidade NFR

Toda unidade futura exige DoR e autorização; fechamento exige validação de módulo, integração no fluxo canônico, fluxo acumulado, regressão pertinente, reconciliação documental e AGENT_HANDOFF_GATE sob PM-01 §§6–8 e 12. Nenhum status PLANNED implica autorização. FRONTEND_FIRST_RULE = NOT_APPLICABLE para a CLI sem GUI; fluxos CLI têm critérios de experiência e integração.

Controles básicos de credenciais/sessão, streaming, workers limitados, caminhos, validação física e rate limit são aplicados desde a primeira unidade que os utiliza. S8 consolida/hardens esses controles; não autoriza adiá-los.

| NFR | Primeira unidade pertinente | Validação acumulada |
|---|---|---|
| NFR-01 | S0 | S9–S10 |
| NFR-02 | S4 | S6/S8/S9 |
| NFR-03 | S4/S5 | S8/S9 |
| NFR-04 | S1 | S4/S8/S9 |
| NFR-05 | S0/S1 | S8–S10 |
| NFR-06 | S1 | S8–S10 |
| NFR-07 | S4 | S8/S9 |
| NFR-08 | S0 | S1–S10 |
| NFR-09 | S0 | S1–S10 |
| NFR-10 | S1 | S2–S9 |

FR-14/FR-15/FR-16 são transversais desde a primeira operação/configuração que os utiliza; o endurecimento em S8 não é seu primeiro uso. FR-13 em S3 fornece inspeção de catálogo; S5 estende a pré-varredura ao plano/fila.

## Gate de prontidao do produto — COURSE_DOWNLOAD_E2E_GATE — 2026-11-03

GATE_ID = COURSE_DOWNLOAD_E2E_GATE
PRIORITY = P0 / BEFORE_TUI_AND_S10
STATUS = NOT_PROVEN / REVIEW_REQUIRED
TYPE = CROSS_SPRINT_PRODUCT_READINESS / NOT_NEW_RETROACTIVE_S5_OR_S9_ACCEPTANCE
REAL_TELEGRAM_AUTHORIZATION = NOT_GRANTED_BY_THIS_DOCUMENT

**Fluxo central (dois modos equivalentes):** (A) escolher no catalogo multiplos arquivos especificos de um curso, inclusive de modulos diferentes; ou (B) selecionar **Baixar tudo** para o curso escolhido, com execucao dos arquivos na sequencia canonica catalogada. O modo B NAO significa baixar todo o canal ou conteudo fora do curso selecionado. Preservar a ordem do catalogo/mensagens e criterio de desempate estavel. Ao reiniciar, manter estado. Arquivo fisicamente valido e deduplicado.

**Gates de avaliacao, proporcionais e sem repeticao automatica de suites historicas:**
- G1 CATALOGO: canal e curso corretos, modulos/aulas/midias e quantidade identificados; scan incompleto destacado. Nao prometer 'tudo' fora dos arquivos conhecidos do catalogo.
- G2 SELECAO: selecionar/desmarcar arquivos individuais (multi-select), selecionar todos do curso, visualizar quantidade/tamanho, alterar selecao e cancelar sem iniciar transferencia.
- G3 ORDEM E PLANO: ordem deterministica entre modulos/aulas/arquivos, lista exata, bytes por arquivo/lote, limites, disponibilidade de espaco, itens ja validos e tamanhos desconhecidos; nenhuma midia externa a selecao.
- G4 EXECUCAO: com autorizacao operacional propria e confirmacoes de seguranca vigentes, fila executa na ordem especificada, progresso e velocidade reais exibidos, estados e falhas evidenciados; no primeiro ciclo usar workers=1, sem paralelismo nao solicitado.
- G5 INTEGRIDADE E PERSISTENCIA: tamanho/identidade/hash conforme contrato, organizacao no filesystem, reconciliacao SQLite/arquivos, reinicio/reentrada, nao duplicacao e retomada segura quando cabivel.
- G6 ACEITE: uma execucao completa de curso elegivel com escopo aprovado demonstra os dois modos (o modo nao escolhido pode ser demonstrado offline com o mesmo catalogo); sem mascarar itens ausentes/nao suportados, bloqueios ou falhas. Resultado PASS somente se os arquivos planejados estiverem validos ou os itens nao concluidos forem explicitamente relatados e tratados no escopo aceito; caso contrario PARTIAL/FAIL. Nao declarar 'curso completo' com scan parcial.

**Indicadores obrigatorios da CLI:** nome de curso/modulo/aula, identificador da midia, status, tamanho real ou desconhecido, total de bytes do lote, bytes baixados/restantes, progresso por arquivo e do lote, velocidade em MB/s (decimal), ETA fundamentado ou indisponivel, concluido/pendente/falhou, quantidade selecionada. Ordem visivel no plano antes de confirmar.

**Entrega imediata:** auditoria curta do codigo e prova offline read-only para inventariar G1-G5; proposta de patch apenas onde necessario; execucao real unicamente apos autorizacao explicita e com limites. A TUI Midnight Glass tem APPROVED_VISUAL, IMPLEMENTATION_DEFERRED. Nao criar novo ciclo extenso de homologacao para o video 585, nao aumentar o escopo de S9 por inferencia, nao iniciar S10.
