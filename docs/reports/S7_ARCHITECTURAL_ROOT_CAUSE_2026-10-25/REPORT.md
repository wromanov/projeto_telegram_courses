# S7 Architectural Root Cause — 2026-10-25

## Required activity record

~~~text
ACTIVITY_ID = S7_ARCHITECTURAL_ROOT_CAUSE_AND_CORRECTION_CONTRACT_2026-10-25
ACTIVITY_COMPLETION_PERCENT = 100% / audit, correction contract, and requested chat delivery complete
ROUTER_INVOCATION = USER_EXPLICITLY_INVOKED / GATE_PASS
ARCHITECT_STATUS = COMPLETED_READ_ONLY / NO_CODE_CHANGES_OR_TESTS_REPORTED
ARCHITECT_ANALYSIS = Static and documentary audit completed; solution contract delivered; node-level historical reconciliation remains UNRECONCILED
SCRIBE_STATUS = COMPLETED / DOCUMENTS_MATERIALIZED
ENVIRONMENT_ROOT_CAUSE = UNKNOWN / PROXIMATE_HANG_CONFIRMED / EXECUTION_CONTEXT_STRONGLY_SUPPORTED
REGRESSION_CAUSES = DOCUMENTED_RECLASSIFICATION_9_V2_9_CLI_2_MIGRATION / ORIGINAL_RECEIPT_NOT_RECOVERED
HISTORICAL_FAILURE_RECONCILIATION = UNRECONCILED
S7_CONTRACT_CONFORMANCE = PARTIAL / STATIC_DEFECTS_AND_VALIDATION_GAPS
CORRECTION_CONTRACT_STATUS = PROPOSED / IMPLEMENTATION_NOT_AUTHORIZED
CORRECTION_CONTRACT_PATH = docs/contracts/S7_ROOT_CAUSE_CORRECTION_IMPLEMENTATION_CONTRACT_2026-10-25.md
CONTRACT_QUALITY_GATE = PASS / ROOT_POSTWRITE_REVIEW_G1_G10
CODE_CHANGES = NO
TEST_EXECUTIONS = 0
REAL_TELEGRAM_CALLS = 0
GIT_PUBLICATION = NO
S6_STATUS = CLOSED_WITH_EXCEPTIONS
S7_ACCEPTANCE = PENDING
S8_STATUS = DEFERRED
NEXT_EXACT_ACTION = User reviews the correction contract and separately authorizes any implementation; S7 acceptance and S8 entry remain user decisions
DELIVERY_STATUS = SENT / DIRECT_USER_APPROVAL / MESSAGE_SENT=YES / SEND_ATTEMPT_COUNT=2
DELIVERY_EVIDENCE = Native send returned threadId 6add6aa9-12e0-83e8-b02f-870f0a0edaf9 / isError=false
PRIOR_AUTO_REVIEW_BLOCK = FIRST_ATTEMPT_REJECTED_FOR_EXACT_PAYLOAD_AND_DESTINATION_APPROVAL / RESOLVED_BY_DIRECT_USER_APPROVAL_BEFORE_RETRY / NO_BYPASS
~~~

## 1. Executive summary

The Architect completed the required read-only review of the approved S7/S8 contract, current implementation, prior corrections, regression reports, Windows/asyncio history, and S5/S6 compatibility. The approved contract has sound fail-closed protections but leaves material behavior underspecified. Static review found four implementation gaps and two validation/coverage issues requiring a future correction activity.

The prior full regression recorded 301 passed, 20 failed, and 11 subtests passed before the last corrections. The latest documented reclassification is 9 V2, 9 CLI, and 2 migration failures. The original node-level receipt was not recovered, so the numerical classification is documented but the individual cases remain UNRECONCILED. No post-patch assertion result verifies any of the 20 failures as resolved.

The execution-context variation and a hang during Proactor self-pipe/socketpair creation are supported by historical evidence. A specific Windows, socket, loopback, or isolation control is not confirmed. No new probes or tests were run. S7 remains pending; S8 remains deferred.

## 2. Parecer do Architect

### FATO

- The latest documented code has a positive correction in V2 selection: selection may proceed without an existing download row while checking current media identity; any existing snapshot is still checked.
- The CLI filesystem oracle has a reparse-point snapshot correction including getattr(info, "st_reparse_tag", None).
- Migration-version expectations were updated after migration 006.
- Two negative V2 identity controls were added.
- These changes have no post-patch assertion evidence.
- The implementation has static gaps involving baseline monotonicity after FULL runs, legacy physical-download identity provenance, media absence on reobserved messages, and indeterminate process ownership.

### EVIDÊNCIA

- S7 implementation chronology, including counts and post-patch environment failures: docs/reports/S7_INCREMENTAL_SYNC_IMPLEMENTATION/REPORT.md, especially the historical regression and later addenda (lines 243, 258-259, 322, 374-394, 405-407).
- Baseline queries: src/telegram_courses/sqlite_repository.py, get_confirmed_high_water, start_sync_run, get_sync_run_summary (lines 153, 223, 335).
- Migration backfill: src/telegram_courses/migrations/006_s7_incremental_sync.sql (lines 18-31).
- Identity and ownership guards: src/telegram_courses/download_repository.py (lines 23-55, 98-115, 275-360, 369-395).
- Planner schema fallback and current-identity comparison: src/telegram_courses/s5_downloads.py (lines 240-245, 301-305).
- Reparse-point snapshot: tests/integration/test_cli_smoke.py (line 60).
- User decision preserving S6 with exceptions: docs/governance/APPROVALS_AND_DECISIONS.md (lines 498-534).
- The active authority map still describes S6 acceptance as pending: docs/continuity/ACTIVE_AUTHORITY_MAP.md (line 36). The map description was factually aligned to the existing 2026-10-25 decision; the decision and acceptance were not changed.

### INFERÊNCIA

- A latest-COMPLETE query can regress high-water when a later FULL run has a smaller or null watermark, even though an earlier COMPLETE run had a larger confirmed watermark.
- Migration 006's copied snapshot proves the current metadata at migration time, not the historic identity of bytes already on disk. Equal-size media replacements make this ambiguity material to reuse.
- Preserving a prior media ordinal without recording its absence in a later observation leaves downstream planning unable to distinguish last-known media from currently observed media.
- Treating an indeterminate process query as dead can permit reclaim while another writer may still exist.

### HIPÓTESE / INCERTEZA

- The Windows execution context influences whether asyncio's loop initialization completes: STRONGLY_SUPPORTED.
- Local socket or loopback restrictions may be the proximate mechanism: STRONGLY_SUPPORTED as a possibility, not confirmed.
- A specific firewall, AppContainer, antivirus, or other OS control: POSSIBLE, not identified.
- Universal Python 3.14.7 or Proactor-only defect: DISCARDED by historical successful smokes in a different context.
- Application S7 code causing the minimal asyncio hang: DISCARDED for those smokes because the application did not execute.
- Permanent configuration change required: UNKNOWN.

## 3. Problemas confirmados e pendentes

“Confirmado” abaixo significa que o comportamento do código ou a lacuna de evidência foi verificada estaticamente/documentalmente. Não significa que houve corrupção ou falha dinâmica no banco original.

| ID | Severidade | Diagnóstico | Estado da evidência |
|---|---|---|---|
| S7-RCA-01 | P2 | Consultas por último COMPLETE podem reduzir o high-water depois de FULL | Defeito estático no seletor; cenários FULL posteriores ainda não foram executados |
| S7-RCA-02 | P1 potencial | Migration 006 copia identidade da mídia corrente para row de download antiga sem prova de proveniência física | Cenário de reutilização ambígua é plausível; corrupção real não foi demonstrada |
| S7-RCA-03 | P2 | Mídia ausente na reobservação não recebe estado durável e continua no catálogo/planner | Lacuna estática; ausência não deve ser convertida em exclusão |
| S7-RCA-04 | P1 potencial | Helper de ownership de download pode converter erro OS inconclusivo em “morto” | Código mostra False em erro não conclusivo; ocorrência de writer concorrente não foi demonstrada |
| S7-RCA-05 | P2 | Fixtures não cobrem as combinações requeridas; fixture “legacy” pode iniciar pelo migrador atual | Lacuna de cobertura/fidelidade de fixture |
| S7-RCA-06 | P1 operacional | Correções de identidade V2, oracle CLI e versão de migration ainda não alcançaram assertions após patches | Confirmado pelos relatórios de setup/hang; 0 dos 20 casos está verificado como resolvido |

Não foi constatada evidência de corrupção no SQLite original. Não se propõe alteração de código para corrigir o hang ambiental.

## 4. Análise do ambiente Windows/asyncio

O histórico combina execuções em que CPython 3.14.7 concluiu naturalmente em contexto descrito como nativo/escalado e execuções posteriores em que TEMP/TMP e o asyncio se comportaram de forma diferente. Numa execução, 83 casos falharam no setup de tmp_path. Noutra, a stack parou em socket.accept, fallback de socketpair e criação do self-pipe Proactor antes do corpo async. Um preflight posterior aprovou escrita/exclusão em TEMP/TMP, mas o smoke asyncio ainda excedeu o timeout.

Isso separa dois bloqueios: falha de diretório temporário no setup e hang na criação do loop. O sucesso de TEMP_IO não prova sucesso de socketpair/asyncio. O hang é confirmado; a causa subjacente do sistema operacional ou isolamento permanece UNKNOWN.

O teste discriminante mínimo futuro é comparar socketpair bruto e asyncio padrão com o mesmo executável, flags, cwd e parâmetros em dois contextos de lançamento documentados. Selector pode ser diagnóstico adicional; não há base para adotá-lo permanentemente. A menor solução suportada pelas evidências é usar um contexto Windows autorizado que passe os gates independentes e interromper se qualquer preflight falhar.

Nenhuma probe foi executada nesta atividade.

## 5. Análise dos 20 casos históricos

Cronologia documentada:

1. Antes dos últimos patches: 15 testes focados passaram e a regressão registrou 301 passed / 20 failed / 11 subtests passed.
2. Correções estáticas posteriores alteraram record_v2_selection, oracle de reparse points e expectativas de migration; dois controles negativos V2 foram adicionados.
3. As execuções posteriores não chegaram a assertions: houve 83 erros de setup tmp_path e depois hang no Proactor/self-pipe. O preflight TEMP/TMP posterior passou, mas asyncio continuou bloqueado.
4. Portanto, pós-patch resolvido = 0; também não foi provado que os casos continuem funcionalmente falhando.

Reconciliação numérica:

~~~text
DOCUMENTED_RECLASSIFICATION = 9 V2 / 9 CLI / 2 migration
EARLIER_CLASSIFICATION = 10 V2 / 9 CLI / 1 migration
ORIGINAL_NODE_IDS_AND_RECEIPT = NOT RECOVERED
HISTORICAL_FAILURE_RECONCILIATION = UNRECONCILED
~~~

Os dois nodes de migration escritos no relatório são:

- tests/integration/test_download_flow.py::test_offline_download_rerun_is_deduplicated
- tests/unit/test_s6_v2.py::test_additive_migration_leaves_v1_downloaded_rows_unchanged

A mudança documental de 1 para 2 casos de migration é sustentada por esses nomes e pela expectativa antiga de MAX=5 diante de schema version 6. Não há recibo bruto para individualizar as nove falhas V2 e as nove do oracle CLI. A classificação 9/9/2 permanece documental, não reconciliada por node ID.

### Grupo A — V2/download identity

A falha histórica estava relacionada a exigir row de download antes de registrar uma nova seleção V2. A mudança atual em DownloadRepository.record_v2_selection usa validação com require_download=False; a ausência da row é permitida, mas a mídia corrente e qualquer snapshot existente continuam validados. Os controles negativos existentes cobrem mismatch atual e snapshot.

**Correção de código adicional prescrita:** nenhuma para esse sintoma histórico.  
**Correções de fixture/prova:** validar controles positivos e negativos, zero gateway e row/arquivo preservados após autorização futura. Não inventar row ou identidade.

### Grupo B — CLI/reparse points

A causa histórica foi o oracle que percorria o worktree inteiro e encontrava reparse points preexistentes. A correção atual trata a raiz como objeto a rejeitar quando reparse/symlink e folhas descendentes sem atravessar o destino; inclui getattr(info, "st_reparse_tag", None). Essa mudança não comprova todos os tags Windows. Não desabilitar proteção de caminhos.

**Correção de código adicional prescrita:** nenhuma para o oráculo histórico.  
**Correções de fixture/prova:** isolamento dos fixtures, testes de junction/symlink e comprovação de que nenhum escape de diretório é possível.

### Grupo C — Migration 006

As expectativas que limitavam a versão a 5 ficaram obsoletas depois de 006; o schema atual é versão 6. O SQL bruto de migration 006 não é projetado para reexecução direta; a idempotência é do migrador via ledger. O teste chamado legacy não comprova sozinho um upgrade verdadeiro de schema 005 para 006 porque pode iniciar pelo migrador atual.

**Correção de expectativa:** necessária nas fixtures antigas de versão máxima; já aplicada estaticamente, sem pós-patch assertion.  
**Correção de migration 006:** não prescrita; não reescrever migrations 001–006.  
**Correção de fixture:** criar banco real 005 a partir de SQL histórico, sem aplicar previamente o migrador atual, e validar a migration aditiva futura em cópia temporária.

## 6. Conformidade da implementação aos critérios S7

| Critério | Implementação/evidência | Lacuna/defeito | Aceite futuro |
|---|---|---|---|
| S7-A1 NEW_MESSAGES_IDEMPOTENT | Chaves únicas e upsert transacional | Baseline pode regredir após FULL; prova histórica positiva limitada | RCA-01; replay e novos IDs mantêm uma row por identidade |
| S7-A2 CHECKPOINT_DURABLE | Cursor transacional, snapshot separado, promoção somente em COMPLETE | Mistura de runs, interrupção e proveniência precisam de prova adicional | Falha/cancelamento/rollback/reopen sem salto nem promoção parcial |
| S7-A3 EDITS_AND_MEDIA_REPLACEMENT_SAFE | Mismatch do snapshot bloqueia reuse/recovery | Proveniência legado e mídia ausente não estão modeladas | UNKNOWN, mismatch e NOT_OBSERVED bloqueados; dados/arquivos preservados |
| S7-A4 DELETION_INACCESSIBILITY_DISTINGUISHED | Mensagens ausentes são preservadas/contadas; acesso negado não promove checkpoint | Mídia não observada não tem estado; fonte de prova de exclusão positiva não definida | RCA-03; A4-C continua OPEN_DECISION; nenhum tombstone |
| S7-A5 SQLITE_COMPATIBLE | Migration 006 aditiva e ledger do repository | Fixture legado incompleta; RCA-02/03 exigem migration aditiva; pós-patch sem assertions | Banco novo e legacy real, ledger, rollback, FK, reopen; sem banco original |
| S7-A6 CLI_PARSER_INTEGRATION | Caminho genérico incremental presente | Fixture RASMOO incremental de duas execuções ausente | CLI genérica e especializada, IDs estáveis, partial sem rebuild, falha de catálogo propaga erro |

Parecer: **PARTIAL / STATIC_DEFECTS_AND_VALIDATION_GAPS**. O aceite S7 permanece pendente.

## 7. Riscos P0/P1/P2/P3

- **P0:** nenhum incidente crítico ou corrupção de dados foi comprovado nesta auditoria.
- **P1:** identidade física legada sem proveniência pode permitir reutilização ambígua; erro OS inconclusivo pode permitir reclaim indevido; ausência de assertions pós-patch impede aceitar as correções existentes. Os dois primeiros são riscos potenciais, não incidentes confirmados.
- **P2:** regressão possível do high-water após FULL; ausência de estado NOT_OBSERVED; cobertura/fixture insuficientes.
- **P3:** melhorias de especificação S8 permanecem dívida futura e não bloqueiam a correção S7 presente.

## 8. Correções necessárias e não necessárias

### Necessárias numa atividade futura, após autorização

1. Aplicar a regra de high-water monotônico em todas as consultas e criação transacional de run.
2. Adicionar proveniência de identidade legada, sem inferir identidade de bytes antigos; bloquear UNKNOWN legado.
3. Registrar NOT_OBSERVED sem exclusão física/lógica automática e impedir planejamento/reuso dessa mídia.
4. Tornar consulta de ownership tri-state; só morte comprovada permite reclaim de estados que exigem owner.
5. Completar fixtures verdadeiras de schema legado, RASMOO em duas execuções, rollback e cenários de falha.
6. Validar correções estáticas já aplicadas; não presumir resolução dos 20 casos.

### Não necessárias ou sem suporte de evidência

- Alteração do código S7 para resolver o hang asyncio.
- Mudança global para Selector.
- Remoção de junctions/symlinks históricos ou relaxamento de proteção de caminho.
- Reescrita de migrations 001–006.
- Alteração de budgets S5, provas S6 ou estado global V2.
- Recriação fictícia do baseline dos 20 nodes.
- Exclusão automática, tombstone ou requalificação de downloads legados sem autoridade própria.

## 9. Contrato corretivo, gates e qualidade

O contrato completo está em **docs/contracts/S7_ROOT_CAUSE_CORRECTION_IMPLEMENTATION_CONTRACT_2026-10-25.md**. Contém os seis issues S7-RCA-01…06, arquivos/funções, causas e evidências, comportamentos requeridos/proibidos, impacto de compatibilidade, fixtures, aceites, matriz S7-A1…A6, ordem futura, estratégia de ambiente, gates E0–E3/V1–V6 e decisões abertas.

O contrato critica o escopo aprovado S7/S8: baseline e snapshot carecem de algoritmo, a janela de reconciliação não define unidade, os limites/resume não dizem se a contagem é por chamada ou run, a migration não prova identidade física de legado, falta estado para mídia ausente, A4 não define prova de exclusão, idempotência/rollback precisam de mecanismo explícito, falta fixture especializada RASMOO, e recibos/aceite não requerem evidência individual suficiente.

As propostas S8 sobre budgets por operação, configuração, workers, estados globais, redaction, disco e memória são recomendações documentais. Não fornecem defaults, não autorizam implementação e não iniciam S8.

### Gate de qualidade G1–G10

O ROOT revisou a solução do Architect antes da materialização e registrou aprovação preliminar. O ROOT ainda deve conferir os documentos finais.

| Gate | Resultado da revisão da solução | Evidência |
|---|---|---|
| G1 Correções ligadas a evidência | PASS | Cada issue referencia código, relatório ou testes existentes |
| G2 Fatos e hipóteses separados | PASS | Classificação ambiental e reconciliação UNRECONCILED explícitas |
| G3 Arquivos/funções identificados | PASS | Matriz e issues nomeiam arquivos e funções |
| G4 Comportamento inequívoco | PASS | Algoritmos, bloqueios e aceites especificados; decisões abertas ficam marcadas |
| G5 S5/S6 preservados | PASS | Budgets, fail-closed, S6 status e provas congeladas preservados |
| G6 Ambiente verificável | PASS | TEMP_IO, socketpair e asyncio são gates independentes |
| G7 Testes objetivos | PASS | Casos e resultados esperados explícitos |
| G8 Sem implementação | PASS | Mudanças de código=NO; testes=0; probes=0 |
| G9 Authorities congeladas | PASS | S7 pending; S8 deferred; nenhum aceite alterado |
| G10 Implementador não refaz auditoria | PASS | Issue IDs, sequência, casos, gates e limites definidos |

**CONTRACT_QUALITY_GATE = PASS / ROOT_POSTWRITE_REVIEW_G1_G10.** The ROOT reviewed the materialized contract and report against all ten required gates.

## 10. Continuidade e autoridade

A auditoria atualiza apenas a continuidade factual. S6 permanece **CLOSED_WITH_EXCEPTIONS**, V1 ativo, V2 global OFF, budgets S5 sem alteração, S7 acceptance pendente e S8 deferred.

Foi corrigida no ACTIVE_AUTHORITY_MAP a descrição factual do contrato S6, que ainda dizia “aceite formal permanece pendente”. A fonte vigente é a decisão do usuário de 2026-10-25 em APPROVALS_AND_DECISIONS.md, que registra S6_ACCEPTANCE=ACCEPTED_WITH_EXCEPTIONS e S6_STATUS=CLOSED_WITH_EXCEPTIONS. Nenhuma decisão ou autoridade foi alterada.

O PROJECT_STATE corrente registra a nova auditoria, os artefatos, os bloqueios e o próximo passo sem mudar status de aceite.

## 11. Próxima ação

1. QA pós-escrita ROOT concluído; G1–G10 = PASS.
2. A primeira tentativa foi rejeitada pelo auto-review por exigir autorização explícita para o payload e destino específicos. O usuário autorizou diretamente esse envio; a mesma ferramenta nativa concluiu a entrega, com retorno do threadId registrado acima. Nenhuma rota alternativa foi usada.
3. Próxima ação: o usuário revisa o contrato e decide, em atividade separada, se autoriza a implementação corretiva.
4. Após autorização de implementação, executar os gates do contrato; se o preflight falhar, interromper e manter a validação bloqueada.

Não iniciar S8, não aceitar S7, não publicar Git e não executar esta validação futura nesta atividade.
