# Sprint plan — projeto_telegram_courses

**Delivery unit:** Sprint  
**Execution model:** Incremental vertical slices  
**Maximum active formal activities:** 1  
**Plan status:** Defined from the approved roadmap; no sprint is started or authorized.

DOCUMENT_ROLE = EXECUTION_PLAN  
RECONCILED_AT = 2026-10-05 / America/Sao_Paulo

A sequência S0–S10 vem do baseline do usuário, seção 7. [REQUIREMENTS.md](../product/REQUIREMENTS.md) é a authority dos requisitos; [ROADMAP.md](ROADMAP.md) define as fases. O estado corrente e toda autorização ficam em [PROJECT_STATE.md](../governance/PROJECT_STATE.md). Critérios abaixo são evidências planejadas, não resultados já obtidos.

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
- **DELIVERABLES:** Authenticated gateway path and channel discovery flow.
- **TESTS:** Unit tests without Telegram login for application behavior; separate Telegram integration checks for authentication and channel discovery.
- **ACCEPTANCE_CRITERIA:** FR-01/FR-02 passam pelo gateway com conta própria e canal acessível; falhas de autenticação/acesso são controladas; proteção de credenciais/sessão e testes separados atendem NFR-05/NFR-06/NFR-09/NFR-10.
- **GATES:** Authentication and channel-discovery acceptance.
- **DEFINITION_OF_DONE:** Approved requirement criteria and relevant tests pass; no unresolved failure blocks the next slice.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S1 accepted; channel identity can be supplied to the scanner.
- **STATUS:** PLANNED / NOT_STARTED.

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
- **DEFINITION_OF_DONE:** Requirement criteria and unit/local integration tests pass; migrations run as designed.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S2 accepted; persisted scan input is available for parser work.
- **STATUS:** PLANNED / NOT_STARTED.

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
- **STATUS:** PLANNED / NOT_STARTED.

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
- **STATUS:** PLANNED / NOT_STARTED.

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
- **STATUS:** PLANNED / NOT_STARTED.

## S6 — Partial Download + Resume + Recovery

- **SPRINT_ID:** S6
- **OBJECTIVE:** Recover interrupted downloads and resume safely from validated partial files.
- **SCOPE:** Partial-state detection, Telegram message/media refetch, resume offset, recovery and final validation.
- **OUT_OF_SCOPE:** Incremental catalog synchronization and optimization unrelated to recovery.
- **DEPENDENCIES:** S4 single-download/file-commit contract; S5 queue behavior where applicable.
- **FUNCTIONAL_REQUIREMENTS:** FR-12; related FR-08/FR-09.
- **TECHNICAL_REQUIREMENTS:** Application-controlled resume; `.part` validation; offset from physical partial size; adapter-supported streaming; exact expected-size validation; optional hash; atomic finalization; never falsely mark complete.
- **DELIVERABLES:** Restart-safe partial download recovery and resume path.
- **TESTS:** Unit tests for state transitions; local `.part` recovery integration; technical real-large-file test: interrupt deliberately, restart, refetch message/media, resume, validate, finalize, persist `DOWNLOADED`.
- **ACCEPTANCE_CRITERIA:** Recovery produces the correct complete file and state after a controlled interruption; technical validation passes before declaring resume complete.
- **GATES:** Large-file resume technical validation.
- **DEFINITION_OF_DONE:** Recovery criteria and technical test pass; otherwise FR-12 resume capability remains open.
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S6 accepted; checkpoint/state behavior available for incremental synchronization.
- **STATUS:** PLANNED / NOT_STARTED.

## S7 — Incremental Synchronization

- **SPRINT_ID:** S7
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
- **NEXT_SPRINT_ENTRY_CONDITIONS:** S7 accepted; operational error/retry/logging controls are ready for hardening.
- **STATUS:** PLANNED / NOT_STARTED.

## S8 — Operational Hardening

- **SPRINT_ID:** S8
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
- **STATUS:** PLANNED / NOT_STARTED.

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
- **STATUS:** PLANNED / NOT_STARTED.

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
| S1 | Definir e verificar proteção local de sessão Telegram no Windows antes de criar sessão real; fechar ownership básico de FloodWait/retry e manter credenciais/sessão excluídas e redigidas. | AUD-MED-04/06; NFR-05/NFR-06 |
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
