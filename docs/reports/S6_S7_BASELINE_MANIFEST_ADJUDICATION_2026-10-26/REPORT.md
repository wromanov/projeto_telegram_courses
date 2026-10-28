# Adjudicação do manifesto da baseline S6/S7 — 2026-10-26

ACTIVITY_ID: S6_S7_BASELINE_MANIFEST_ADJUDICATION_2026-10-26
ROUTER_INVOCATION: USER_EXPLICIT / GATE_EXECUTED
ARCHITECT_STATUS: COMPLETED_ADVISORY
DIAGNOSTIC_ANALYST: NOT_DISPATCHED
SCRIBE_STATUS: DRAFT_PREPARED / ROOT_MATERIALIZED
MIGRATIONS_CHAIN_STATUS: PASS
OFFLINE_VALIDATION: PASS
REVIEW_ITEMS_ADJUDICATED: 45/45
SECURITY_GATE: BLOCKED
FINAL_INCLUDE_COUNT: 109
FINAL_EXCLUDE_COUNT: 130
FINAL_BLOCKED_COUNT: 8
FINAL_CLASSIFIED_COUNT: 247
MANIFEST_STATUS: BLOCKED
PUBLICATION_READINESS: BLOCKED
S6_STATUS: CLOSED_WITH_EXCEPTIONS
S7_STATUS: CLOSED_WITH_EXCEPTIONS
S8_STATUS: DEFERRED
S8_AUTHORIZATION: NOT_GRANTED
CODE_CHANGES: NO
GIT_STAGE/COMMIT/PUSH: NOT_EXECUTED
REAL_TELEGRAM_CALLS: 0
DELIVERY_STATUS: SENT

## Escopo e resultado

Esta atividade adjudica os 45 candidatos originalmente marcados REVIEW no manifesto integrado, registra a validação offline da cadeia de migrations e corrige duas classificações INCLUDE por segurança. O inventário nominal original de 246 registros e suas justificativas históricas permanecem preservados no manifesto. A classificação final considera este novo relatório como artefato incluído: 247 registros.

INCLUDE é proposta de composição, não autorização para stage, commit, push, aplicar migration em banco real, ativar V2 ou executar operações Telegram. A prontidão permanece BLOCKED. Nenhum documento de continuidade/autoridade foi alterado; o estado do projeto permanece inalterado.

## Adjudicação path-level dos 45 REVIEW

A decisão, justificativa/evidência, segurança, dependência e condição pendente estão discriminadas em cada linha. Itens bloqueados não devem ser publicados até decisão e tratamento correspondentes. Evidências brutas excluídas não foram consultadas nem reproduzidas.

| # | Path | Decisão | Razão, evidência e condição |
|---:|---|---|---|
| 1 | src/telegram_courses/download_repository.py | INCLUDE | Dependência de produção para download e aplicador de migrations; exercitado na validação offline. Depende da cadeia 001–007; publicação condicionada ao desbloqueio geral. |
| 2 | tests/unit/test_telethon_gateway.py | BLOCKED_PENDING_DECISION | Contém o mesmo alvo operacional fixo do gateway. Bloqueado até decisão separada de tratamento e revalidação; valor omitido. |
| 3 | tests/unit/test_s6_bounded_target_gateway.py | BLOCKED_PENDING_DECISION | Contém o alvo operacional que limita descoberta. Bloqueado até decisão separada de tratamento e revalidação; valor omitido. |
| 4 | src/telegram_courses/migrations/005_s6_integrity_v2.sql | INCLUDE | Dependência aprovada da implementação offline S6 V2 pela authority explícita de implementação contra o draft ratificado. Não implica autorização S7 retroativa, aplicação em banco original ou ativação V2. Ver seção Migration 005. |
| 5 | tools/manual_proofs/s6_bounded_target_discovery.py | EXCLUDE | Ferramenta manual direcionada ao alvo, fora da baseline mínima. Excluído por segurança/escopo; conteúdo de prova não aberto. |
| 6 | docs/continuity/ACTIVE_AUTHORITY_MAP.md | BLOCKED_PENDING_DECISION | Authority corrente; requer decisão sobre tratamento seguro. Não editar/publicar nesta atividade; considerar derivado redigido. |
| 7 | docs/continuity/PROJECT_STATE.md | BLOCKED_PENDING_DECISION | Estado corrente requer decisão específica sobre conteúdo publicável. Não editar; considerar derivado redigido. |
| 8 | docs/continuity/CONTINUITY_RECORD.md | BLOCKED_PENDING_DECISION | Registro corrente requer decisão de tratamento. Não editar; considerar derivado redigido. |
| 9 | docs/continuity/handoff/LAST_HANDOFF.md | BLOCKED_PENDING_DECISION | Handoff corrente requer decisão de tratamento. Não editar; considerar derivado redigido. |
| 10 | docs/governance/APPROVALS_AND_DECISIONS.md | BLOCKED_PENDING_DECISION | Authority consultada para 005, mas cópia publicável requer decisão separada. Não incluir sem tratamento. |
| 11 | docs/reports/S6_S7_INTEGRATED_BASELINE_PREPARATION_2026-10-26/PUBLICATION_MANIFEST.md | INCLUDE | Manifesto path-level da baseline, atualizado por adendo; status continua BLOCKED. |
| 12 | docs/reports/S6_S7_INTEGRATED_BASELINE_PREPARATION_2026-10-26/REPORT.md | EXCLUDE | Snapshot supersedido pelo manifesto atualizado e por este relatório; evita versões contraditórias. |
| 13 | docs/reports/S6_TRUSTED_REFERENCE_RECONCILIATION_2026-10-23/REPORT.md | EXCLUDE | Histórico associado a evidência direcionada; não é dependência de produção. Evidência bruta não inspecionada. |
| 14 | docs/reports/S6_GATE_A_EXITCODE_ROOT_CAUSE_AND_B_TARGET_TRIAGE_2026-10-24/REPORT.md | EXCLUDE | Diagnóstico histórico de gate/alvo, não necessário à baseline; evitar exposição de metadados direcionados. |
| 15 | docs/reports/S6_GATE_A_EXITCODE_SYNTHETIC_PROBE_2026-10-25/REPORT.md | EXCLUDE | Relatório de probe histórico; artefato de atividade, sem dependência runtime. |
| 16 | docs/reports/S7_ARCHITECTURAL_ROOT_CAUSE_2026-10-25/REPORT.md | EXCLUDE | Análise intermediária substituída por decisões finais S7; sem dependência runtime. |
| 17 | docs/reports/S7_INCREMENTAL_SYNC_IMPLEMENTATION/REPORT.md | EXCLUDE | Relatório intermediário supersedido por registros finais; sem dependência runtime. |
| 18 | docs/reports/S7_CORRECTIVE_IMPLEMENTATION_2026-10-26/REPORT.md | EXCLUDE | Registro corretivo histórico, não necessário à composição final. |
| 19 | docs/reports/S7_FINAL_ACCEPTANCE_DECISION_2026-10-26/REPORT.md | INCLUDE | Decisão final de aceitação necessária à proveniência S7. Não concede autoridade adicional. |
| 20 | docs/reports/S7_FORMAL_CLOSURE_2026-10-26/REPORT.md | INCLUDE | Fechamento necessário para interpretar estado e exceções S7; não autoriza publicação/Phase 2. |
| 21 | docs/reports/S7_GIT_CHECKPOINT_AND_PUBLICATION_2026-10-26/REPORT.md | INCLUDE | Contexto de checkpoint/publicação relevante; inclusão documental não autoriza operação Git. |
| 22 | docs/contracts/S6_UNIFIED_CORRECTION_CONTRACT_V1.md | EXCLUDE | Contrato de correção de harness/atividade, sem dependência de produção. |
| 23 | docs/contracts/S6_V2_NATIVE_HARNESS_REGRESSION_FIX_CONTRACT_2026-10-19.md | EXCLUDE | Contrato de correção de harness nativo; não dependência runtime. |
| 24 | docs/contracts/S6_V2_NATIVE_MXC_EXECUTOR_RECOVERY_CONTRACT_2026-10-20.md | EXCLUDE | Contrato de recuperação do executor de prova; não dependência runtime. |
| 25 | docs/contracts/S6_V2_OFFLINE_E2E_AND_SYMLINK_GATES_ADDENDUM_2026-10-18.md | EXCLUDE | Aditivo de gates de harness, não necessário à baseline de produção. |
| 26 | docs/contracts/S6_V2_OFFLINE_REGRESSION_RUNNER_CONTRACT_2026-10-19.md | EXCLUDE | Contrato do runner de regressão da atividade; não dependência runtime. |
| 27 | docs/contracts/S6_V2_PHASE_HANDOFF_CORRECTION_CONTRACT.md | EXCLUDE | Contrato de correção de handoff; atividade, sem dependência runtime. |
| 28 | docs/contracts/S6_V2_PROOF_HARNESS_CORRECTION_CONTRACT.md | EXCLUDE | Contrato de correção de harness de prova; sem dependência runtime. |
| 29 | docs/contracts/S6_V2_PROOF_HARNESS_LIFECYCLE_FIXTURE_PATH_ADDENDUM_2026-10-18.md | EXCLUDE | Aditivo de fixture/path do harness; caminho de prova fora da baseline. |
| 30 | docs/contracts/S6_V2_PROOF_HARNESS_TIMEOUT_RECEIPT_ADDENDUM_2026-10-18.md | EXCLUDE | Aditivo de timeout/recibo de prova; sem dependência runtime. |
| 31 | docs/contracts/S6_V2_REFERENCE_PREFLIGHT_AMENDMENT_2026-10-19.md | EXCLUDE | Emenda de preflight de referência de prova; material direcionado fora da baseline. |
| 32 | docs/contracts/S6_V2_STABILIZATION_IMPLEMENTATION_CONTRACT_2026-10-20.md | EXCLUDE | Contrato de estabilização da atividade V2; não dependência de produção, V2 continua OFF. |
| 33 | docs/contracts/S6_V2_TRUSTED_REFERENCE_TIMEOUT_REMEDIATION_ADDENDUM_2026-10-19.md | EXCLUDE | Aditivo de timeout de referência de prova; não dependência runtime. |
| 34 | docs/reports/S6_BOUNDED_TARGET_DISCOVERY_2026-10-16/identity-adjudication/report.md | EXCLUDE | Relatório histórico de descoberta de alvo; prova específica excluída, conteúdo bruto não aberto. |
| 35 | docs/reports/S6_BOUNDED_TARGET_DISCOVERY_2026-10-16/report.md | EXCLUDE | Histórico de descoberta de alvo, fora da baseline. |
| 36 | docs/reports/S6_BOUNDED_TARGET_DISCOVERY_2026-10-17_METADATA_GATEWAY/report.md | EXCLUDE | Metadata gateway histórico direcionado, fora da baseline. |
| 37 | docs/reports/S6_CONTROLLED_REFERENCE_PREPARATION_2026-10-17/report.md | EXCLUDE | Preparação histórica de referência controlada, não dependência de produção. |
| 38 | docs/reports/S6_CONTROLLED_UPLOAD_AND_EOF_GATE_2026-10-17/report.md | EXCLUDE | Prova histórica de upload/EOF; proveniência fora da baseline. |
| 39 | docs/reports/S6_DIALOG_BASED_PEER_RECOVERY_2026-10-17/report.md | EXCLUDE | Recuperação histórica por diálogo; evidências associadas não inspecionadas. |
| 40 | docs/reports/S6_FINAL_CLOSURE_OPERATION_2026-10-20.md | EXCLUDE | Operação histórica de fechamento, fora da baseline mínima. |
| 41 | docs/reports/S6_FINAL_EVIDENCE_RECONCILIATION_2026-10-20.md | EXCLUDE | Reconciliação de evidência histórica; bruto excluído. |
| 42 | docs/reports/S6_FINAL_STABILIZATION_AND_CLOSURE_2026-10-20.md | EXCLUDE | Estabilização/fechamento de atividade, não dependência runtime. |
| 43 | docs/reports/S6_HASH_WINDOW_DIAGNOSTIC_REMEDIATION_2026-10-17/report.md | EXCLUDE | Diagnóstico de prova/hash histórico, fora da baseline. |
| 44 | docs/reports/S6_INTEGRITY_CONTRACT_V2_IMPLEMENTATION_READINESS_PLAN_2026-10-17.md | EXCLUDE | Plano histórico não concede authority nem ativa V2; não dependência runtime. |
| 45 | docs/reports/S6_SYMLINK_GATE_FINAL_VALIDATION_2026-10-18.md | EXCLUDE | Validação histórica de harness, sem dependência de produção. |

## Ajustes de segurança em INCLUDE original

- src/telegram_courses/telethon_gateway.py: INCLUDE → BLOCKED_PENDING_DECISION. Contém identificador operacional de canal que restringe bounded discovery; mesmo valor consta nos dois testes bloqueados e no helper manual excluído. Alterar o valor muda comportamento de código/testes e excede a autorização desta atividade. O valor não é reproduzido. Exige decisão de desenho, mudança autorizada e revalidação.
- docs/contracts/S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_CONTRACT_2026-10-18.md: INCLUDE → EXCLUDE. Registra alvo fixo de prova/identidade de mídia, não é dependência de produção com V2_GLOBAL=OFF. Identificadores omitidos.
- Os 104 textos INCLUDE originais foram legíveis, text-only, 1.621.489 bytes. Dois literais de testes DPAPI foram avaliados como valores sintéticos de fixture, não credenciais; valores omitidos. Documentos herdados S0/S1 com caminhos locais não foram editados nem staged.
- Uma busca delegada ampla alcançou brevemente JSON de prova excluído; foi interrompida. O conteúdo não foi usado ou propagado, e não se registra caminho/conteúdo.

## Migration 005 e validação

Decisão MIGRATION_005_DECISION=INCLUDE_AS_APPROVED_DEPENDENCY. Authority: autorização explícita de implementação offline S6 V2 contra draft ratificado em docs/governance/APPROVALS_AND_DECISIONS.md, linhas 400–429; semântica de migration/legacy em docs/contracts/S6_INTEGRITY_CONTRACT_V2_PROPOSAL_DRAFT.md, linhas 56–60 e 165. O contrato canônico V1 declara migrations fora de seu escopo, docs/contracts/S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT.md, linhas 294–306. S7 não autorizou retroativamente 005.

005 adiciona duas colunas nullable e duas tabelas; não executa UPDATE, DELETE ou backfill. V2_GLOBAL=OFF. DownloadRepository.migrate() aplica 005 se a versão 5 falta no ledger, inclusive no caminho V1. Publicar source não autoriza aplicar no banco original do usuário nem ativar V2.

Os três aplicadores compartilham schema_migrations e o mesmo caminho. Ordem por chamadas de código: 001→006→007→002→003→004→005. Há três transações sequenciais; falha em 005 reverte somente 005, commits anteriores permanecem. SQL cru 005 não é idempotente; aplicadores reais com ledger são.

| Migration | Efeito relevante verificado | Resultado |
|---|---|---|
| 001 | Inicialização do schema | PASS |
| 002 | Catálogo | PASS |
| 003 | Catálogo não resolvido | PASS |
| 004 | Downloads | PASS |
| 005 | Duas colunas nullable e duas tabelas; sem escrita/backfill de dados | PASS |
| 006 | Snapshot de identidade para legado | PASS |
| 007 | Proveniência antiga marcada UNKNOWN_LEGACY | PASS |

Validação temporária corrigida de ROOT: banco sintético novo aplicado pelo DownloadRepository.migrate(), versões 001–007 presentes; segunda passagem pelos três aplicadores sem delta de schema, ledger ou contagens. Fixture legacy: dados preservados, campos 005 NULL, snapshot 006 correto, provenance 007 UNKNOWN_LEGACY, tabelas V2 vazias. Upgrade pre-006 preservou linhas. Falha após primeiro ALTER de 005 reverteu o ALTER, manteve versão 5 ausente e versões anteriores presentes. foreign_key_check vazio e integrity_check=ok em todas as fixtures. Temporários removidos.

O primeiro checker ordenou ledger por rowid; foi corrigido uma vez porque version INTEGER PRIMARY KEY é alias de rowid, sem defeito da aplicação. Não houve suíte de testes, mudança de código, uso do banco original, chamada Telegram ou rede.

## Contagens, gates e ações pendentes

| Estado | Quantidade | Composição |
|---|---:|---|
| INCLUDE | 109 | 102 INCLUDE originais mantidos + 6 REVIEW promovidos + novo relatório |
| EXCLUDE | 130 | 97 EXCLUDE originais + 1 INCLUDE reclassificado + 32 REVIEW |
| BLOCKED | 8 | 1 INCLUDE reclassificado + 7 REVIEW |
| Total | 247 | 246 originais + este relatório |

| Gate | Estado | Evidência/pendência |
|---|---|---|
| G1 | PASS | Authority explícita para 005 como dependência de implementação offline S6. |
| G2 | PASS | Ordem, ledger, transações e efeitos revisados. |
| G3 | PASS | Validação sintética corrigida passou. |
| G4 | PASS | 45/45 classificados; 7 bloqueios têm condição documentada. |
| G5 | BLOCKED | Gateway de produção requerido está bloqueado pelo identificador operacional fixo. |
| G6 | BLOCKED | Arquivos correntes de autoridade/continuidade sem decisão de publicação segura. |
| G7 | PASS | Evidência bruta e documentos direcionados mantidos fora. |
| G8 | PASS | Conferência final confirma que somente estes dois documentos foram editados; WIP existente preservado. |
| G9 | PASS | Decisões path-level claras, incluindo bloqueios. |
| G10 | PARTIAL | Plano path-specific condicionado a resolver bloqueios. |
| G11 | PASS | Nenhuma operação Git mutável executada. |
| G12 | PASS | Sem alteração de authority; V2 OFF; S8 deferred. |

Próxima ação humana: decidir tratamento seguro ou derivado redigido para os documentos correntes bloqueados; separadamente, autorizar redesenho do identificador operacional, atualizar componentes afetados e revalidar. Phase 2 exige autorização explícita própria antes de qualquer stage/commit/push/publicação. Status S6/S7=CLOSED_WITH_EXCEPTIONS; S8=DEFERRED, autorização NOT_GRANTED. Manifesto e readiness BLOCKED.
