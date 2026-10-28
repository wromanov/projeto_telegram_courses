# Manifesto de publicação proposto — baseline integrada S6→S7

```text
ACTIVITY_ID = S6_S7_INTEGRATED_BASELINE_PREPARATION_2026-10-26
MANIFEST_STATUS = BLOCKED
PUBLICATION_READINESS = BLOCKED
CANDIDATE_RECORDS = 246 / 245 existentes na enumeração nominal e 1 relatório planejado naquele snapshot; agora 246 paths materializados, incluindo este manifesto e REPORT.md
CHECKPOINT_FILES = NONE
GIT_STAGE = NOT_AUTHORIZED / NOT_EXECUTED
GIT_COMMIT = NOT_AUTHORIZED / NOT_EXECUTED
GIT_PUSH = NOT_AUTHORIZED / NOT_EXECUTED
```

## Escopo, autoridade e confiança

Este documento registra a proposta de composição para uma futura baseline S6→S7, sem executar publicação. A classificação não concede autorização de stage, commit, push, implementação S8 ou operações Telegram. O card autoriza preparação do manifesto e documentação; GIT_STAGE, GIT_COMMIT e GIT_PUSH permanecem NOT_AUTHORIZED. A análise do inventário foi nominal/read-only. Conteúdo de candidatos não foi integralmente revisado para secrets ou dados pessoais; por isso, nenhuma afirmação de gate de segurança PASS é feita.

O inventário nominal fechado contém 246 registros: A=7, B=3, C=41, D=7, E=3, F=18, G=70, H=52, I=44, J=1. Totais propostos: INCLUDE=104, REVIEW=45, EXCLUDE=97. INCLUDE indica recomendação de composição futura, não seleção já staged. Status de candidatos preservados conforme enumeração fornecida pelo ROOT/Diagnostic; onde a fonte não informou estado Git/ref por candidato, isso é indicado explicitamente como não observado/não verificado.

## Inventário path-level

Os campos de estado remoto e Git no cabeçalho de cada grupo aplicam-se a todos os paths imediatamente listados. Os perfis de razão, dependência, risco e segurança abaixo completam os campos por candidato; “names-only” significa que o conteúdo não foi aberto nesta análise.

### A — S6_PRODUCTION_REQUIRED (7)

**INCLUDE · M/Y** — componente S6 integrado necessário à aplicação; arquivo integral, sem seleção por hunk. Razão A1, dependências e riscos de mistura S6/S7 descritos adiante. Segurança: names-only, revisão de conteúdo ainda requerida.

- `src/telegram_courses/cli.py`
- `src/telegram_courses/downloads.py`
- `src/telegram_courses/s5_downloads.py`
- `src/telegram_courses/telegram_gateway.py`
- `src/telegram_courses/telethon_gateway.py`

**INCLUDE · ?/N** — módulo requerido por import de produção; segurança de conteúdo não verificada.

- `src/telegram_courses/s6_integrity.py`

**REVIEW · M/Y** — arquivo misto e dependente de migration 005; não incluir até autoridade do migration/ledger ser resolvida.

- `src/telegram_courses/download_repository.py`

### B — S7_PRODUCTION_REQUIRED (3)

**INCLUDE · M/Y** — produção S7 para sincronização incremental; dependências devem estar no snapshot completo. Segurança: names-only.

- `src/telegram_courses/message_scanner.py`
- `src/telegram_courses/scan_application.py`
- `src/telegram_courses/sqlite_repository.py`

### C — TESTS_REQUIRED (41)

Estados C foram confirmados por enumeração read-only: 31 =/Y, 5 M/Y e 3 ?/N entre INCLUDE; um REVIEW é M/Y e o outro ?/N. Risco e dependência: a suíte reproduz regressão S5/S6/S7 e requer imports, fixtures e tooling correspondentes. Segurança de conteúdo não revisada integralmente; privacidade requer revisão dos dois arquivos marcados REVIEW.

**INCLUDE · =/Y (31; paths listados abaixo, exceto os oito identificados em seguida como M/Y ou ?/N)**

- `tests/conftest.py`
- `tests/fixtures/rasmoo/sp02/README.md`
- `tests/fixtures/rasmoo/sp02/case01_index_fragment_a.txt`
- `tests/fixtures/rasmoo/sp02/case01_index_fragment_b.txt`
- `tests/fixtures/rasmoo/sp02/case02_document_post.txt`
- `tests/fixtures/rasmoo/sp02/case02_documents_index.txt`
- `tests/fixtures/rasmoo/sp02/case02_video_post_01.txt`
- `tests/fixtures/rasmoo/sp02/case02_video_post_02.txt`
- `tests/fixtures/rasmoo/sp02/case02_video_post_03.txt`
- `tests/fixtures/rasmoo/sp02/case02_video_post_from_index.txt`
- `tests/fixtures/rasmoo/sp02/case03_index_transitions_synthetic.txt`
- `tests/fixtures/rasmoo/sp02/manifest.json`
- `tests/integration/test_catalog.py`
- `tests/integration/test_cli_auth.py`
- `tests/integration/test_cli_channels.py`
- `tests/integration/test_cli_credentials.py`
- `tests/integration/test_cli_scan.py`
- `tests/integration/test_cli_smoke.py` — M/Y
- `tests/integration/test_credential_vault_windows.py`
- `tests/integration/test_download_flow.py` — M/Y
- `tests/integration/test_rasmoo_parser.py`
- `tests/integration/test_s5_download_flow.py` — M/Y
- `tests/integration/test_sqlite_repository.py` — M/Y
- `tests/integration/test_stack_local.py`
- `tests/integration/test_telethon_session_windows.py`
- `tests/unit/test_auth.py`
- `tests/unit/test_auth_application.py`
- `tests/unit/test_channel_discovery.py`
- `tests/unit/test_config.py`
- `tests/unit/test_credentials.py`
- `tests/unit/test_downloads.py` — M/Y
- `tests/unit/test_message_scanner.py`
- `tests/unit/test_s5_queue_policy.py`
- `tests/unit/test_telethon_discovery.py`
- `tests/unit/test_telethon_session.py`
- `tests/unit/test_test_environment_isolation.py`
- `tests/integration/test_s7_incremental_cli.py` — ?/N
- `tests/integration/test_s7_incremental_sync.py` — ?/N
- `tests/unit/test_s6_v2.py` — ?/N

**REVIEW · M/Y e ?/N respectivamente** — revisão de privacidade necessária; os nomes contêm identificador operacional e não são reproduzidos.

- `tests/unit/test_telethon_gateway.py` — nome/path preservado, identificador contido no nome redigido
- `tests/unit/test_s6_bounded_target_gateway.py` — nome/path preservado, identificador contido no nome redigido

### D — MIGRATIONS_REQUIRED (7)

Migration chain 001→007. Decisões propostas não afirmam coerência de ledger/schema; esta continua um gate técnico. Segurança: conteúdo/schema não revistos nesta atividade.

**INCLUDE · =/Y**
- `src/telegram_courses/migrations/001_initial.sql`
- `src/telegram_courses/migrations/002_catalog.sql`
- `src/telegram_courses/migrations/003_catalog_unresolved.sql`
- `src/telegram_courses/migrations/004_downloads.sql`

**REVIEW · ?/N** — loader/ledger e autoridade S6 precisam ser reconciliados antes de selecionar a baseline.
- `src/telegram_courses/migrations/005_s6_integrity_v2.sql`

**INCLUDE · ?/N** — dependências S7 declaradas; inclusão condicionada à validação da cadeia completa.
- `src/telegram_courses/migrations/006_s7_incremental_sync.sql`
- `src/telegram_courses/migrations/007_s7_corrective_identity_observation.sql`

### E — TOOLING_REQUIRED (3)

**INCLUDE · =/Y** — configuração de projeto/versionamento necessária; conteúdo ainda sujeito a review final de segurança.
- `pyproject.toml`
- `.gitignore`

**REVIEW · ?/N** — prova/tooling manual S6; excluir da composição automática até estabelecer necessidade e risco.
- `tools/manual_proofs/s6_bounded_target_discovery.py`

### F — GOVERNANCE_CONTINUITY_REQUIRED (18)

Base de governança e continuidade necessária para interpretar estados/decisões. Os arquivos existentes devem ser preservados bytewise conforme fontes vigentes; alterações documentais locais não autorizam publicar histórico indiscriminado. Segurança de conteúdo não foi avaliada integralmente.

**INCLUDE · =/Y**
- `AGENTS.md`
- `docs/continuity/PROJECT_GOVERNANCE_BINDING.json`
- `docs/continuity/START_HERE.md`
- `docs/continuity/NEW_AGENT_BOOTSTRAP.md`
- `docs/continuity/policies/AGENTS-Multiagente-Generico-v1.7-R2.3-Roteamento-Economico.md`
- `docs/continuity/policies/Independencia-Analitica-Agente-v1.md`
- `docs/continuity/policies/PM-01-Conducao-de-Projetos-v1.0.md`
- `docs/continuity/policies/Politica-Prompts-Agente-v1.7-R2.6.md`
- `docs/continuity/policies/Politica-de-Uso-de-Skills-e-Plugins-Codex-Work-v1.2.md`

**INCLUDE · M/Y**
- `docs/continuity/planning/SPRINTS.md`
- `docs/continuity/planning/ROADMAP.md`

**REVIEW · M/Y** — material corrente de decisão/estado; revisão de diffs e sincronização final ainda necessária.
- `docs/continuity/ACTIVE_AUTHORITY_MAP.md`
- `docs/continuity/PROJECT_STATE.md`
- `docs/continuity/CONTINUITY_RECORD.md`
- `docs/continuity/handoff/LAST_HANDOFF.md`
- `docs/governance/APPROVALS_AND_DECISIONS.md`

**REVIEW · ?/N ou P/N conforme estado da enumeração** — próprios entregáveis atuais; conteúdo deste manifesto e relatório deve ser revisado antes de qualquer publicação.
- `docs/reports/S6_S7_INTEGRATED_BASELINE_PREPARATION_2026-10-26/PUBLICATION_MANIFEST.md` — ?/N; path existente na enumeração do inventário
- `docs/reports/S6_S7_INTEGRATED_BASELINE_PREPARATION_2026-10-26/REPORT.md` — ?/N após a materialização; era P/N na enumeração anterior

### G — HISTORICAL_DEPENDENCY_REQUIRED (70)

Razão: compatibilidade, arquitetura, contrato ou proveniência histórica necessária à baseline ou sua interpretação. Conteúdo dos documentos não passou por review de secrets nesta atividade; INCLUDE/REVIEW é proposta documental, não aprovação de divulgação. Oito S1 reports já estavam em `=/Y`; não devem gerar novo stage.

**INCLUDE · =/Y — módulos-base compartilhados (12)**
- `src/telegram_courses/__init__.py`
- `src/telegram_courses/__main__.py`
- `src/telegram_courses/auth.py`
- `src/telegram_courses/auth_application.py`
- `src/telegram_courses/catalog.py`
- `src/telegram_courses/catalog_application.py`
- `src/telegram_courses/catalog_repository.py`
- `src/telegram_courses/channel_discovery.py`
- `src/telegram_courses/config.py`
- `src/telegram_courses/credentials.py`
- `src/telegram_courses/rasmoo_parser.py`
- `src/telegram_courses/telethon_session.py`

**INCLUDE · =/Y — docs-base (3)**
- `docs/product/REQUIREMENTS.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/engineering/ENGINEERING_FOUNDATION.md`

**INCLUDE · =/Y para S0–S5; ?/N para S6/S7**
- `docs/contracts/S0_IMPLEMENTATION_CONTRACT.md`
- `docs/contracts/S1A_PROTECTED_SESSION_IMPLEMENTATION_CONTRACT.md`
- `docs/contracts/S1B_AUTHENTICATION_GATEWAY_IMPLEMENTATION_CONTRACT.md`
- `docs/contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md`
- `docs/contracts/S2_MESSAGE_SCANNER_SQLITE_CONTRACT.md`
- `docs/contracts/S3_PARSER_CATALOG_CONTRACT.md`
- `docs/contracts/S4_SINGLE_MEDIA_DOWNLOAD_CONTRACT.md`
- `docs/contracts/S5_COURSE_SELECTION_PLANNER_QUEUE_CONTRACT.md`
- `docs/contracts/S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md`
- `docs/contracts/S6_INTEGRITY_CONTRACT_V2_PROPOSAL_DRAFT.md`
- `docs/contracts/S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_CONTRACT_2026-10-18.md`
- `docs/contracts/S7_S8_INCREMENTAL_SYNC_OPERATIONAL_HARDENING_IMPLEMENTATION_CONTRACT.md`
- `docs/contracts/S7_ROOT_CAUSE_CORRECTION_IMPLEMENTATION_CONTRACT_2026-10-25.md`

Nota de authority: `S6_INTEGRITY_CONTRACT_V2_PROPOSAL_DRAFT.md` é DRAFT, não aprovado, canônico ou efetivo; o INCLUDE proposto é histórico e não concede authority nem ativa V2. `S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_CONTRACT_2026-10-18.md` é contexto histórico V2; `V2_GLOBAL=OFF` permanece inalterado.

**INCLUDE · ?/N**
- `docs/reports/S6_FINAL_ACCEPTANCE_DECISION_2026-10-25/REPORT.md`

**INCLUDE · =/Y — S1 reports já remotos, sem novo stage (8)**
- `docs/reports/S1_DOR_GAP_REVIEW_2026-10-07.md`
- `docs/reports/S1_ENTRY_REVIEW_2026-10-07.md`
- `docs/reports/S1_SESSION_PROTECTION_AND_RETRY_OWNERSHIP_2026-10-07.md`
- `docs/reports/S1_TEST_01_PYTEST_ENVIRONMENT_DIAGNOSIS_2026-10-08.md`
- `docs/reports/S1D_CREDENTIALS_VAULT_2026-10-09.md`
- `docs/reports/S1D_OPEN04_OFFLINE_FEASIBILITY_2026-10-08.md`
- `docs/reports/S1D_REAL_DISCOVERY_VALIDATION_2026-10-09.md`
- `docs/reports/S1D_REGRESSION_CLI_NUMERIC_SELECTION_2026-10-09.md`

**REVIEW · ?/N — reports com provenance, local metadata/IDs/paths a revisar (9)**
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/REPORT.md`
- `docs/reports/S6_GATE_A_EXITCODE_ROOT_CAUSE_AND_B_TARGET_TRIAGE_2026-10-24/REPORT.md`
- `docs/reports/S6_GATE_A_EXITCODE_SYNTHETIC_PROBE_2026-10-25/REPORT.md`
- `docs/reports/S7_ARCHITECTURAL_ROOT_CAUSE_2026-10-25/REPORT.md`
- `docs/reports/S7_INCREMENTAL_SYNC_IMPLEMENTATION/REPORT.md`
- `docs/reports/S7_CORRECTIVE_IMPLEMENTATION_2026-10-26/REPORT.md`
- `docs/reports/S7_FINAL_ACCEPTANCE_DECISION_2026-10-26/REPORT.md`
- `docs/reports/S7_FORMAL_CLOSURE_2026-10-26/REPORT.md`
- `docs/reports/S7_GIT_CHECKPOINT_AND_PUBLICATION_2026-10-26/REPORT.md`

**REVIEW · ?/N — contracts S6 omitidos; produção de Harness/executor/prova precisa distinção (12)**
- `docs/contracts/S6_UNIFIED_CORRECTION_CONTRACT_V1.md`
- `docs/contracts/S6_V2_NATIVE_HARNESS_REGRESSION_FIX_CONTRACT_2026-10-19.md`
- `docs/contracts/S6_V2_NATIVE_MXC_EXECUTOR_RECOVERY_CONTRACT_2026-10-20.md`
- `docs/contracts/S6_V2_OFFLINE_E2E_AND_SYMLINK_GATES_ADDENDUM_2026-10-18.md`
- `docs/contracts/S6_V2_OFFLINE_REGRESSION_RUNNER_CONTRACT_2026-10-19.md`
- `docs/contracts/S6_V2_PHASE_HANDOFF_CORRECTION_CONTRACT.md`
- `docs/contracts/S6_V2_PROOF_HARNESS_CORRECTION_CONTRACT.md`
- `docs/contracts/S6_V2_PROOF_HARNESS_LIFECYCLE_FIXTURE_PATH_ADDENDUM_2026-10-18.md`
- `docs/contracts/S6_V2_PROOF_HARNESS_TIMEOUT_RECEIPT_ADDENDUM_2026-10-18.md`
- `docs/contracts/S6_V2_REFERENCE_PREFLIGHT_AMENDMENT_2026-10-19.md`
- `docs/contracts/S6_V2_STABILIZATION_IMPLEMENTATION_CONTRACT_2026-10-20.md`
- `docs/contracts/S6_V2_TRUSTED_REFERENCE_TIMEOUT_REMEDIATION_ADDENDUM_2026-10-19.md`

**REVIEW · ?/N — reports S6 com proveniência/referências/metadados locais a revisar (12)**
- `docs/reports/S6_BOUNDED_TARGET_DISCOVERY_2026-10-16/identity-adjudication/report.md`
- `docs/reports/S6_BOUNDED_TARGET_DISCOVERY_2026-10-16/report.md`
- `docs/reports/S6_BOUNDED_TARGET_DISCOVERY_2026-10-17_METADATA_GATEWAY/report.md`
- `docs/reports/S6_CONTROLLED_REFERENCE_PREPARATION_2026-10-17/report.md`
- `docs/reports/S6_CONTROLLED_UPLOAD_AND_EOF_GATE_2026-10-17/report.md`
- `docs/reports/S6_DIALOG_BASED_PEER_RECOVERY_2026-10-17/report.md`
- `docs/reports/S6_FINAL_CLOSURE_OPERATION_2026-10-20.md`
- `docs/reports/S6_FINAL_EVIDENCE_RECONCILIATION_2026-10-20.md`
- `docs/reports/S6_FINAL_STABILIZATION_AND_CLOSURE_2026-10-20.md`
- `docs/reports/S6_HASH_WINDOW_DIAGNOSTIC_REMEDIATION_2026-10-17/report.md`
- `docs/reports/S6_INTEGRITY_CONTRACT_V2_IMPLEMENTATION_READINESS_PLAN_2026-10-17.md`
- `docs/reports/S6_SYMLINK_GATE_FINAL_VALIDATION_2026-10-18.md`

### H — UNRELATED_WIP (52)

Todos EXCLUDE; não pertencem à baseline mínima, dependem de Harness/provas ou são configuração local de agentes. Conteúdo não aberto; excluir não equivale a apagar. Somente o path M/Y tem diff local que deve continuar fora do checkpoint.

**M/Y (1)**
- `.codex/agents/architect.toml`

**?/N — configuração local (2)**
- `.codex/agents/diagnostic_analyst.toml`
- `.codex/agents/principal_architect.toml`

**?/N — testes manuais de prova S6 (6)**
- `tests/manual_proofs/test_s6_controlled_eof_hash_probe.py`
- `tests/manual_proofs/test_s6_real_compat_proof.py`
- `tests/manual_proofs/test_s6_real_resume_proof.py`
- `tests/manual_proofs/test_s6_v2_mxc_host_executor.py`
- `tests/manual_proofs/test_s6_v2_offline_regression_runner.py`
- `tests/manual_proofs/test_s6_v2_proof_harness.py`

**?/N — tooling manual de prova S6 (7 scripts PowerShell)**
- `tools/manual_proofs/Invoke-S6BoundedTargetDiscovery.ps1`
- `tools/manual_proofs/Invoke-S6ControlledEofHashProbe.ps1`
- `tools/manual_proofs/Invoke-S6HashEofProbe.ps1`
- `tools/manual_proofs/Invoke-S6RealCompatProof.ps1`
- `tools/manual_proofs/Invoke-S6RealResumeProof.ps1`
- `tools/manual_proofs/Invoke-S6V2OfflineRegression.ps1`
- `tools/manual_proofs/Invoke-S6V2Proof.ps1`

**?/N — tooling manual de prova S6 (7 módulos Python)**
- `tools/manual_proofs/s6_controlled_eof_hash_probe.py`
- `tools/manual_proofs/s6_real_compat_proof.py`
- `tools/manual_proofs/s6_real_resume_proof.py`
- `tools/manual_proofs/s6_resume_harness.py`
- `tools/manual_proofs/s6_v2_mxc_host_executor.py`
- `tools/manual_proofs/s6_v2_offline_regression_runner.py`
- `tools/manual_proofs/s6_v2_proof_harness.py`

**?/N — relatórios Markdown locais de prova/execução (28)**
- `docs/reports/S6_FINAL_GATE_REMEDIATION_2026-10-24/GATE_A_PATCH.md`
- `docs/reports/S6_FINAL_GATE_REMEDIATION_2026-10-24/REPORT.md`
- `docs/reports/S6_RUNTIME_ISOLATION_2026-10-18.md`
- `docs/reports/S6_V2_COMMON_ALIGNED_FINAL_REPROOF_2026-10-17.md`
- `docs/reports/S6_V2_COMMON_ALIGNED_PROOF_RESUME_2026-10-17.md`
- `docs/reports/S6_V2_COMMON_ALIGNED_REAL_PROOF_2026-10-18.md`
- `docs/reports/S6_V2_COMMON_ALIGNED_REPROOF_2026-10-17.md`
- `docs/reports/S6_V2_COMMON_NONALIGNED_OFFLINE_VALIDATION_PASS_2026-10-18.md`
- `docs/reports/S6_V2_COMMON_NONALIGNED_REAL_PROOF_2026-10-18.md`
- `docs/reports/S6_V2_COMMON_NONALIGNED_REAL_PROOF_PREFLIGHT_BLOCKED_2026-10-18.md`
- `docs/reports/S6_V2_FINAL_REGRESSION_GATE_2026-10-19.md`
- `docs/reports/S6_V2_MXC_ACCESS_DENIED_SUPPORT_PACKAGE_2026-10-20.md`
- `docs/reports/S6_V2_NATIVE_EXECUTION_GATE_2026-10-20/S6_V2_NATIVE_EXECUTION_GATE_2026-10-20.md`
- `docs/reports/S6_V2_NATIVE_EXECUTION_RECOVERY_2026-10-20.md`
- `docs/reports/S6_V2_NATIVE_REGRESSION_7_FAILURES_FIX_2026-10-20.md`
- `docs/reports/S6_V2_OFFLINE_REGRESSION_RUNNER_INVOCATION_2026-10-19.md`
- `docs/reports/S6_V2_OPTION_B_NATIVE_EXECUTOR_FEASIBILITY_2026-10-20.md`
- `docs/reports/S6_V2_PHASE_HANDOFF_CYCLIC_REMEDIATION_2026-10-17.md`
- `docs/reports/S6_V2_PROOF_EXECUTION_UNBLOCK_2026-10-17.md`
- `docs/reports/S6_V2_PROOF_HARNESS_CORRECTION_2026-10-17.md`
- `docs/reports/S6_V2_REFERENCE_PREFLIGHT_AMENDMENT_2026-10-19.md`
- `docs/reports/S6_V2_SECURE_RUNTIME_UNBLOCK_2026-10-17.md`
- `docs/reports/S6_V2_STABILIZATION_STRATEGY_DOCUMENTATION_AND_CONTINUITY_2026-10-19.md`
- `docs/reports/S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_2026-10-18.md`
- `docs/reports/S6_V2_TRUSTED_REFERENCE_PREFLIGHT_2026-10-18.md`
- `docs/reports/S6_V2_TRUSTED_REFERENCE_REAL_REPROOF_01_PREFLIGHT_2026-10-19.md`
- `docs/reports/S6_V2_TRUSTED_REFERENCE_TIMEOUT_REMEDIATION_2026-10-19.md`
- `docs/reports/S6_V2_WINDOWS_BOOTSTRAP_ROOT_CAUSE_2026-10-17.md`

**?/N — script de probe sintético (1)**
- `docs/reports/S6_GATE_A_EXITCODE_SYNTHETIC_PROBE_2026-10-25/run-gate-a.proposed.ps1`

### I — SENSITIVE_LOCAL_DATA (44)

Todos EXCLUDE, ?/N. Inventário por nome/extensão/diretório, sem abrir conteúdo. Motivo por item: evidência bruta, metadados, banco, sidecar, transcript ou mídia local não necessária como fonte versionada da baseline. Não reproduzir o identificador operacional do basename de mídia nem run IDs dos transcripts.

**Paths exatos seguros da enumeração (39)**
- `docs/reports/S6_CONTROLLED_REFERENCE_PREPARATION_2026-10-17/reference_manifest.json`
- `docs/reports/S6_CONTROLLED_UPLOAD_AND_EOF_GATE_2026-10-17/controlled_upload_result.json`
- `docs/reports/S6_DIALOG_BASED_PEER_RECOVERY_2026-10-17/document_inventory.csv`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/MANIFEST.json`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/aligned/budget.sqlite3`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/aligned/phase-1.child.json`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/aligned/phase-1.json`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/aligned/phase-2.child.json`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/aligned/phase-2.json`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/aligned/proof.sqlite3`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/aligned/proof.sqlite3-shm`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/aligned/proof.sqlite3-wal`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/aligned/reference-manifest.v1.json`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/authorization.json`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/execution-progress.jsonl`
- `docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/evidence/s6-v2-proof-report.json`
- `docs/reports/S6_V2_NATIVE_EXECUTION_GATE_2026-10-20/p0-snapshot.json`
- `docs/reports/S6_V2_NATIVE_EXECUTION_GATE_2026-10-20/pre-activity-git-status.txt`
- `docs/reports/S6_V2_NATIVE_EXECUTION_GATE_2026-10-20/pytest-collect-only.txt`
- `docs/reports/s6-v2-real-proof-[run-id redigido]/authorization.json` (basename com run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/budget.sqlite3` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/phase-1.json` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/proof.sqlite3` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/proof.sqlite3-shm` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/proof.sqlite3-wal` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/authorization-initial.json` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/authorization.json` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/s6-v2-proof-reconciliation.json` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/s6-v2-proof-report-initial.json` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/s6-v2-proof-report.json` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/budget.sqlite3` (run ID redigido; segundo diretório)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/phase-1.child.json` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/phase-1.json` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/phase-2.child.json` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/phase-2.json` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/proof.sqlite3` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/authorization-summary.json` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/execution-progress.jsonl` (run ID redigido)
- `docs/reports/s6-v2-real-proof-[run-id redigido]/s6-v2-proof-report.json` (run ID redigido)

**Quatro transcripts — um registro por prefixo; run IDs redigidos**
- `tools/manual_proofs/offline_evidence/s6-real-compat-proof-[run-id redigido].transcript.txt` × 4

**Uma mídia — basename identificador redigido; contada como 1 item**
- `docs/reports/s6-v2-real-proof-[run-id redigido]/aligned/downloads/[nome de mídia/identificador operacional redigido]`

### J — UNKNOWN_OR_UNVERIFIED (1)

**EXCLUDE · ?/N** — artefato grande, origem/necessidade não identificadas; não abrir nem incluir por conveniência. Tamanho histórico anotado: 12,530,544 bytes, não reconfirmado nesta atividade.
- `docs/architecture.zip`

## Matriz de dependências e razões técnicas

| Perfil | Relação observada ou proposta | Risco/gate pendente |
|---|---|---|
| A1 | `downloads.py` importa `s6_integrity.py`; ambos são necessários juntos para a proposta S6 integrada. | O módulo requerido está `?/N`; revisão de conteúdo e dependências internas pendentes. Arquivos M/Y são integrais; não fazer seleção por hunk sem prova de independência. |
| A2 | `download_repository.py` carrega migration 005; S5/S6/S7 compartilham módulos de download/gateway. | Migration 005 está REVIEW/?/N; schema/ledger e cadeia 001–007 não demonstrados coerentes. |
| B1 | `message_scanner.py`, `scan_application.py`, `sqlite_repository.py` formam a superfície S7 incremental. | Dependências C/D necessárias; nenhum teste nesta atividade. |
| C1 | Testes/fixures de parser, CLI, auth, download, SQLite, S5/S6 e S7 dão cobertura offline proposta. | Conteúdo individual e reprodução não realizados; dois paths em REVIEW por identificadores no nome. |
| D1 | Migrations 001–007 devem acompanhar o loader de produção em ordem íntegra. | 005 está REVIEW; 006/007 e 005 são `?/N`; existência e ordem no remoto não bastam para provar compatibilidade de ledger. |
| E1 | `pyproject.toml` e `.gitignore` são config versionada/base; ferramenta S6 manual está separada. | Conteúdo completo de configuração e tooling não revisado neste fechamento. |
| F1/G1 | Binding, políticas, continuidade, contratos e relatórios definem interpretação de authority/histórico. | Revisão de diffs, referências, IDs locais e exposição documental pendente. Não reabrir S6/S7 nem alterar contratos congelados. |
| H/I/J | WIP, provas, dados sensíveis e origem desconhecida não compõem a baseline mínima. | EXCLUDE mantém arquivos locais intactos; não significa remoção nem análise do conteúdo. |

## Totais por categoria e decisão

| Classe | Total | INCLUDE | REVIEW | EXCLUDE |
|---|---:|---:|---:|---:|
| A — S6 production | 7 | 6 | 1 | 0 |
| B — S7 production | 3 | 3 | 0 | 0 |
| C — tests | 41 | 39 | 2 | 0 |
| D — migrations | 7 | 6 | 1 | 0 |
| E — tooling | 3 | 2 | 1 | 0 |
| F — governance/continuity | 18 | 11 | 7 | 0 |
| G — historical dependencies | 70 | 37 | 33 | 0 |
| H — unrelated WIP | 52 | 0 | 0 | 52 |
| I — sensitive local data | 44 | 0 | 0 | 44 |
| J — unknown/unverified | 1 | 0 | 0 | 1 |
| **Total** | **246** | **104** | **45** | **97** |

## Fase 2 — plano proposto; não autorizado nem executado

1. ROOT faz preflight read-only da branch, HEAD, upstream, remoto, index e paths; interrompe se encontrar staged changes inesperadas ou divergência do inventário.
2. Revisar conteúdo e dependências de todos os INCLUDE e resolver cada REVIEW. Fechar cadeia de imports, migrations 001–007, fixtures/tooling e referências documentais; não promover INCLUDE sem prova de autocontenção.
3. Realizar review de segurança de cada arquivo proposto para secrets, sessões, dados pessoais, caminhos locais, bancos, provas, mídias e artefatos temporários. Manter H/I/J fora e revisar os reports/contratos F/G antes da divulgação.
4. Obter autorização humana separada e explícita para qualquer Fase 2. Enquanto os 45 REVIEW persistirem, nenhum comando de stage é seguro ou preparável. Após adjudicação, desbloqueio e autorização, usar apenas paths literais, um por vez; não usar `git add .`, `git add -A` nem wildcard/diretório amplo.
5. Conferir `git diff --cached --name-status`, `--stat`, `--check` e conteúdo integral; provar que o index estava limpo, que dependências estão presentes, que nenhum H/I/J entrou e que WIP excluído permanece intacto.
6. Sob autorização específica, executar testes offline definidos para a composição final, inclusive migrations em banco temporário, S6/S7, S5/S6, CLI/parser/download/identity/SQLite. O resultado histórico 340 PASS / 11 subtests não substitui reexecução se a composição final mudar; nenhum teste foi executado nesta atividade.
7. Se todos os gates passarem e houver autorização específica de commit, preferir um checkpoint integrado simples na branch `work/s0-bootstrap`; não criar commits artificiais. Se a composição exigir vários commits, justificar antes de agir.
8. Push só após autorização específica para `origin/work/s0-bootstrap`, sem force push, merge, rebase, troca de branch ou alteração de upstream. Divergência/non-fast-forward interrompe o procedimento.
9. Confirmar SHA local/remoto e estado residual do worktree; preservar WIP excluído. Relatar somente SHA efetivamente observado.

**Interrupção segura:** path ou diff novo, dependência não resolvida, conteúdo sensível, migration incoerente, teste falho, mudança de HEAD/upstream, staged preexistente ou conflito remoto interrompe a proposta. Preservar worktree/index como encontrados; não usar reset/restore/clean/stash e não alterar histórico.

## Estado atual

```text
MANIFEST_STATUS = BLOCKED / DEPENDENCY_GATE = BLOCKED_BY_BASELINE_DEPENDENCY / 45 REVIEW e dependências técnicas abertas
CHECKPOINT_FILES = NONE
PUBLICATION_READINESS = BLOCKED
GIT_STAGE = NOT_AUTHORIZED / NOT_EXECUTED
GIT_COMMIT = NOT_AUTHORIZED / NOT_EXECUTED
GIT_PUSH = NOT_AUTHORIZED / NOT_EXECUTED
S7_STATUS = CLOSED_WITH_EXCEPTIONS
S8_STATUS = DEFERRED / NOT_STARTED / NOT_GRANTED
GIT_PUBLICATION = BLOCKED
```

---

## Adendo de adjudicação — 2026-10-26

Este adendo preserva integralmente o inventário original de 246 paths e suas justificativas históricas. Ele registra a adjudicação dos 45 REVIEW e os ajustes de segurança. Os totais originais permanecem como fotografia histórica; para a decisão atual, este adendo e docs/reports/S6_S7_BASELINE_MANIFEST_ADJUDICATION_2026-10-26/REPORT.md prevalecem.

ORIGINAL_INVENTORY=246
NEW_REPORT=1
FINAL_CLASSIFIED_COUNT=247
FINAL_INCLUDE_COUNT=109
FINAL_EXCLUDE_COUNT=130
FINAL_BLOCKED_COUNT=8
MANIFEST_STATUS=BLOCKED
PUBLICATION_READINESS=BLOCKED

Dos 104 INCLUDE originais, 102 permanecem INCLUDE; src/telegram_courses/telethon_gateway.py foi reclassificado BLOCKED_PENDING_DECISION devido a identificador operacional fixo que restringe bounded discovery; docs/contracts/S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_CONTRACT_2026-10-18.md foi reclassificado EXCLUDE por registrar alvo/identidade de prova e não ser dependência de produção com V2_GLOBAL=OFF.

Dos 45 REVIEW, 6 foram promovidos a INCLUDE, 32 excluídos e 7 bloqueados. A inclusão do relatório novo como artefato classificado resulta em INCLUDE=109, EXCLUDE=130, BLOCKED=8; total=247. Decisões path-level, razões, evidências, notas de segurança/dependência e condições constam no relatório de adjudicação. Nenhuma justificativa histórica foi removida.

### Migration 005

MIGRATION_005_DECISION=INCLUDE_AS_APPROVED_DEPENDENCY. Authority explícita para implementação offline S6 V2 contra draft ratificado: docs/governance/APPROVALS_AND_DECISIONS.md:400–429; draft: docs/contracts/S6_INTEGRITY_CONTRACT_V2_PROPOSAL_DRAFT.md:56–60,165; escopo V1: docs/contracts/S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md:294–306. Não atribuir autorização retroativa a S7.

005 cria duas colunas nullable e duas tabelas, sem UPDATE/DELETE/backfill. V2 permanece OFF. DownloadRepository.migrate() aplica 005 se não houver versão 5, inclusive no fluxo V1. Publicar o source não autoriza aplicar ao banco original ou ativar V2. Os três aplicadores compartilham ledger e caminho; ordem 001→006→007→002→003→004→005. Transações sequenciais: falha em 005 reverte só 005. SQL cru não é idempotente; aplicadores com ledger são.

Validação temporária corrigida PASS: banco sintético fresco via DownloadRepository.migrate(), versões 001–007; segunda passagem sem delta de schema/ledger/contagens; legado preservado, colunas 005 NULL, snapshot 006 correto, provenance 007 UNKNOWN_LEGACY, tabelas V2 vazias; upgrade pre-006 preservou linhas; falha após primeiro ALTER reverteu 005 e deixou versão 5 ausente com anteriores presentes; foreign_key_check vazio e integrity_check=ok. Temporários removidos. Checker inicial corrigido uma vez porque version INTEGER PRIMARY KEY é alias de rowid, sem defeito da aplicação. Sem suite, mudança de código, banco original, Telegram ou rede.

### Segurança e gates

Todos os 104 textos INCLUDE originais legíveis, text-only, 1.621.489 bytes. Dois literais em testes DPAPI tratados como fixtures sintéticas; valores omitidos. Documentos herdados S0/S1 com caminhos locais não editados nem staged. Busca delegada alcançou brevemente JSON de prova excluído, foi interrompida e o conteúdo não foi usado/propagado.

G1 PASS; G2 PASS; G3 PASS; G4 PASS; G5 BLOCKED; G6 BLOCKED; G7 PASS; G8 PASS; G9 PASS; G10 PARTIAL; G11 PASS; G12 PASS. S6/S7 CLOSED_WITH_EXCEPTIONS; S8 DEFERRED, autorização NOT_GRANTED. Nenhuma authority mudou. Código não alterado; Git stage/commit/push não executados; chamadas Telegram reais 0. Phase 2 requer autorização explícita separada.

Próxima ação humana: decidir tratamento seguro ou derivado redigido dos documentos correntes bloqueados e, separadamente, autorizar redesenho/revalidação do identificador operacional do gateway. Até então, manifesto e readiness permanecem BLOCKED.

---

## Adendo de remediação de segurança da publicação — 2026-10-27

Este adendo reconcilia os oito bloqueios descritos na adjudicação de
2026-10-26. Todos os números e decisões acima permanecem como snapshots
históricos; somente este adendo registra a classificação corrente. O inventário
original foi preservado sem reescrita.

### Oito bloqueios originais

| Path original | Motivo do bloqueio | Correção aplicada | Evidência | Estado final | Substituto público | Risco residual |
|---|---|---|---|---|---|---|
| `src/telegram_courses/telethon_gateway.py` | Alvo operacional fixo codificado no gateway. | Alvo recebido por configuração explícita; ausente/inválido falha fechado, sem fallback a descoberta ampla. | 67/67 testes focados passaram; scan cego contra gateway/testes encontrou zero ocorrência; Architect não encontrou em HEAD/refs locais. | INCLUDE | Mesmo path corrigido. | Ref/objeto remoto indisponível localmente não foi auditado; valor operacional deve permanecer fora do código versionado. |
| `tests/unit/test_telethon_gateway.py` | Fixture repetia a identidade operacional real. | Fixtures com identidades sintéticas. | Parte de 67/67 testes; scan cego encontrou zero ocorrência. | INCLUDE | Mesmo path corrigido. | Histórico remoto indisponível localmente não foi auditado. |
| `tests/unit/test_s6_bounded_target_gateway.py` | Teste bounded codificava o alvo operacional real. | Cobertura sintética de configuração válida, ausente, inválida e divergente; sem fallback e sem helper de prova. | Parte de 67/67; fail-closed antes de RPC; imports de helpers manuais = 0. | INCLUDE | Mesmo path corrigido. | Histórico remoto indisponível localmente não foi auditado. |
| `docs/continuity/ACTIVE_AUTHORITY_MAP.md` | Authority corrente inclui metadados locais não necessários à composição pública. | Original preservado; produzido resumo público delimitado. | Revisão ROOT dos cinco derivados e scan sem caminho absoluto Windows, URL, hash longo ou número operacional. | EXCLUDE_FROM_PUBLICATION | `docs/public/continuity/ACTIVE_AUTHORITY_MAP.md` | Excluir o path da composição não remove cópias anteriores em histórico remoto; refs locais examinadas sem exposição detectada, refs remotos não auditados. |
| `docs/continuity/PROJECT_STATE.md` | Estado corrente contém referências privadas e de checkout. | Original preservado; produzido estado público sem path local, branch, HEAD ou IDs operacionais. | Revisão ROOT dos cinco derivados; campos de authority e omissões corretos. | EXCLUDE_FROM_PUBLICATION | `docs/public/continuity/PROJECT_STATE.md` | Mesmo limite de histórico remoto; nenhuma exposição detectada nos refs locais examinados. |
| `docs/continuity/CONTINUITY_RECORD.md` | Registro contém referências e metadados locais de continuidade. | Original preservado; produzido registro público resumido. | Revisão ROOT dos cinco derivados e scan de padrões sensíveis. | EXCLUDE_FROM_PUBLICATION | `docs/public/continuity/CONTINUITY_RECORD.md` | Mesmo limite de histórico remoto; nenhuma exposição detectada nos refs locais examinados. |
| `docs/continuity/handoff/LAST_HANDOFF.md` | Handoff inclui contexto histórico e metadados de destino internos. | Original preservado; produzido handoff público sintetizado. | Revisão ROOT dos cinco derivados; sem transferência de dados de sessão ou provas brutas. | EXCLUDE_FROM_PUBLICATION | `docs/public/continuity/LAST_HANDOFF.md` | Mesmo limite de histórico remoto; nenhuma exposição detectada nos refs locais examinados. |
| `docs/governance/APPROVALS_AND_DECISIONS.md` | Authority decisória inclui detalhes internos desnecessários à publicação. | Original preservado; produzido resumo público das decisões e exceções S6/S7. | Revisão ROOT dos cinco derivados; exceções/gates parciais mantidos sem promoção a PASS. | EXCLUDE_FROM_PUBLICATION | `docs/public/governance/APPROVALS_AND_DECISIONS.md` | Mesmo limite de histórico remoto; nenhuma exposição detectada nos refs locais examinados. |

### Novos paths classificados

| Path | Classificação | Motivo/evidência | Risco residual |
|---|---|---|---|
| `docs/public/continuity/ACTIVE_AUTHORITY_MAP.md` | INCLUDE | Derivado sanitizado, origem canônica identificada, sem criar authority. Revisado por ROOT. | Informativo; authority local prevalece. |
| `docs/public/continuity/PROJECT_STATE.md` | INCLUDE | Derivado de estado sem path/branch/IDs operacionais; omissões declaradas. Revisado por ROOT. | Não substitui o state local. |
| `docs/public/continuity/CONTINUITY_RECORD.md` | INCLUDE | Derivado delimitado e sem evidência bruta; revisado por ROOT. | Não substitui a continuidade local. |
| `docs/public/continuity/LAST_HANDOFF.md` | INCLUDE | Handoff público registra estado/limites e a próxima ação sem metadados de sessão; revisado por ROOT. | Não substitui o handoff local. |
| `docs/public/governance/APPROVALS_AND_DECISIONS.md` | INCLUDE | Resumo de decisões e exceções S6/S7 preserva seu escopo; revisado por ROOT. | Não é fonte decisória; original local prevalece. |
| `docs/reports/S6_S7_PUBLICATION_SECURITY_REMEDIATION_2026-10-27/REPORT.md` | INCLUDE | Registra evidências da remediação, gates, limites e próxima decisão humana. | Prontidão não autoriza publicação Git; histórico remoto completo não auditado. |
| `tests/manual_proofs/test_s6_bounded_target_discovery_runner.py` | EXCLUDE | Runner local de prova depende do helper manual excluído; não é dependência necessária da baseline pública. | Nenhum; permanece local e fora da composição proposta. |

O helper manual `tools/manual_proofs/s6_bounded_target_discovery.py` permanece
EXCLUDE conforme a classificação histórica. O runner excluído não altera a
contagem de INCLUDE.

### Totais correntes e gates

```text
PREVIOUS_SNAPSHOT = INCLUDE=109 / EXCLUDE=130 / BLOCKED=8 / CLASSIFIED=247
ORIGINAL_BLOCKED_RESOLVED = 8
NEW_INCLUDE = 6 / NEW_EXCLUDE = 1
FINAL_INCLUDE_COUNT = 118
FINAL_EXCLUDE_COUNT = 136
FINAL_BLOCKED_COUNT = 0
FINAL_CLASSIFIED_COUNT = 254
MANIFEST_STATUS = PASS / CURRENT_PATH_LEVEL_RECONCILIATION
PUBLICATION_READINESS = READY_FOR_USER_APPROVAL
GATE_A_CODE_DIFF = PASS
GATE_B_GATEWAY_TESTS = PASS / 67
GATE_C_BOUNDED_DISCOVERY = PASS
GATE_D_OFFLINE_COMPATIBILITY = PASS / 237 DISTINCT TESTS
GATE_E_PUBLIC_DOC_SECURITY = PASS / REMOTE_HISTORY_UNVERIFIED
GATE_F_STATIC_QUALITY = PASS
R1 = PASS
R2 = PASS
R3 = PASS
R4 = PASS / PERTINENT_OFFLINE MODULES; CLI_SMOKE NOT_COMPLETED
R5 = PASS
R6 = PASS
R7 = PASS / LOCAL_REFS_REVIEWED; REMOTE_HISTORY_UNVERIFIED
R8 = PASS
R9 = PASS
R10 = PASS / GIT_MUTATIONS_NOT_EXECUTED
R11 = PASS / S6_S7_CLOSED_WITH_EXCEPTIONS
R12 = PASS / S8_NOT_STARTED
GIT_STAGE = NOT_EXECUTED
GIT_COMMIT = NOT_EXECUTED
GIT_PUSH = NOT_EXECUTED
REAL_TELEGRAM_CALLS = 0
S8_AUTHORIZATION = NOT_GRANTED
DELIVERY_STATUS = SENT / TOOL_CONFIRMED
DELIVERY_HISTORY = Previous attempt rejected; direct user authorization received; retry succeeded.
```

Os grupos offline aprovados somaram 237 testes distintos. Um primeiro run
focado falhou no setup do tempdir sob sandbox e a repetição passou 67/67. Um
run combinado amplo foi interrompido sem resumo e não foi declarado PASS. O
teste genérico `tests/integration/test_cli_smoke.py` foi interrompido por
percorrer/hashificar o repositório inteiro, incluindo WIP/evidências locais; não
foi repetido nem usado como gate. Os módulos pertinentes de CLI/configuração
passaram separadamente. Não houve Harness manual S6 nem acesso Telegram/RPC.

O scan cego do alvo e forma raw contra gateway/testes encontrou zero
ocorrências. A revisão do Architect não encontrou o alvo em HEAD nem no
histórico Git local alcançável dos três paths de código/teste e cinco
authorities. Não houve acesso de rede nem consulta a refs/objetos remotos
ausentes localmente; não se afirma auditoria completa de histórico remoto.

S6 e S7 permanecem `CLOSED_WITH_EXCEPTIONS`; V1 continua ativa, V2 global
permanece desligada e os controles S5/S6 permanecem obrigatórios. S8 continua
`DEFERRED` / `NOT_GRANTED`. `READY_FOR_USER_APPROVAL` indica apenas prontidão
técnica desta composição proposta. A Fase 2 requer autorização humana específica
antes de stage, commit, push ou publicação Git.

---

## Adendo de Opção A — remediação segura do HEAD público — 2026-10-27

Este adendo registra a decisão atual do usuário e o escopo autorizado para a
atividade `S6_S7_SAFE_HEAD_REMEDIATION_AND_PUBLICATION_2026-10-27`. Ele não
altera os inventários nem as classificações históricas acima.

```text
USER_DECISION = OPTION_A_APPROVED
ACTIVITY_STATUS = AUTHORIZED_WITH_GATES / IN_PROGRESS
MANIFEST_INCLUDE = 118
MANIFEST_EXCLUDE = 136
MANIFEST_BLOCKED = 0
MANIFEST_CLASSIFIED = 254
HEAD_SANITIZATION_REMOVALS = 5
GITIGNORE_PROTECTION = REQUIRED
NEW_INCLUDE_FOR_REMOVALS = 0
MANIFEST_COUNTS_EXPANDED = NO
GIT_STAGE = AUTHORIZED_WITH_GATES
GIT_COMMIT = AUTHORIZED_WITH_GATES
GIT_PUSH = AUTHORIZED_WITH_GATES
HISTORY_REWRITE = NOT_AUTHORIZED
FORCE_PUSH = NOT_AUTHORIZED
HISTORICAL_EXPOSURE = ACCEPTED_RESIDUAL_LOCAL_PATH_METADATA
HISTORY_SANITIZED = NO
S8_STATUS = DEFERRED / NOT_STARTED
S8_AUTHORIZATION = NOT_GRANTED
REAL_TELEGRAM_CALLS = 0
PRECOMMIT_GATES = IN_PROGRESS
GIT_PUBLICATION = NOT_YET_CONFIRMED
```

Os cinco paths abaixo são remoções explícitas do próximo HEAD, não novos
`INCLUDE`. Seus arquivos físicos e conteúdos canônicos permanecem preservados
no workspace local. O `.gitignore` deve protegê-los por regras específicas na
raiz, sem excluir genericamente a documentação:

- `docs/continuity/ACTIVE_AUTHORITY_MAP.md`
- `docs/continuity/PROJECT_STATE.md`
- `docs/continuity/CONTINUITY_RECORD.md`
- `docs/continuity/handoff/LAST_HANDOFF.md`
- `docs/governance/APPROVALS_AND_DECISIONS.md`

Os cinco derivados sanitizados já classificados como `INCLUDE` permanecem no
inventário sem nova contagem. A alteração pontual de `.gitignore` é necessária
à proteção da Opção A e não amplia as 118 inclusões do inventário. As classes
`INCLUDE=118`, `EXCLUDE=136` e `BLOCKED=0` continuam inalteradas.

Os contratos congelados permanecem inalterados e podem referenciar as
authorities PROJECT_STATE e APPROVALS_AND_DECISIONS, cujos originais permanecem
locais e fora da baseline pública. Os derivados públicos informam esse estado,
mas não substituem essas authorities; portanto, a interpretação normativa
pública não é autossuficiente para esses pontos. Este registro explicita essa
limitação, não cria nem altera authority e não muda os gates nem os totais do
manifesto.

`HISTORICAL_EXPOSURE=ACCEPTED_RESIDUAL_LOCAL_PATH_METADATA` registra a aceitação
exclusiva do risco residual conhecido de metadados de caminhos locais que
permanecerão no histórico existente. Isso não aceita segredos ou novos dados
sensíveis e não significa que o histórico foi sanitizado. Não estão autorizadas
reescrita de histórico, force push, implementação funcional ou S8.

O stage, commit e push permanecem condicionados à revisão do snapshot staged e a
todos os gates materiais. Este adendo não declara gate final, commit, push ou
publicação remota concluídos. A publicação só poderá ser registrada como sucesso
após confirmação do SHA e do tree remoto.
