# S7 Root Cause Correction Implementation Contract

~~~text
CONTRACT_ID = S7_ROOT_CAUSE_CORRECTION_IMPLEMENTATION_CONTRACT_2026-10-25
SOURCE_ACTIVITY = S7_ARCHITECTURAL_ROOT_CAUSE_AND_CORRECTION_CONTRACT_2026-10-25
STATUS = PROPOSED / IMPLEMENTATION_NOT_AUTHORIZED
ARCHITECT_ANALYSIS = COMPLETED_READ_ONLY
S7_ACCEPTANCE = PENDING
S8_STATUS = DEFERRED
~~~

## 1. Purpose and authority

This document records a future correction specification derived from the read-only S7 architectural audit. It is not implementation authorization, S7 acceptance, or permission to execute tests.

The user retains authority over implementation, validation, phase advancement, acceptance, and Git publication. A future implementation requires separate explicit authorization. This contract does not change the approved S7/S8 contract, S5 limits, S6 status, or frozen proof.

## 2. Fixed project invariants

~~~text
V1_ACTIVE = YES
V2_GLOBAL = OFF
S6_STATUS = CLOSED_WITH_EXCEPTIONS
S5_BUDGETS = UNCHANGED
S7_ACCEPTANCE = PENDING
S8_STATUS = DEFERRED
REAL_TELEGRAM_CALLS = 0
ORIGINAL_SQLITE_CHANGES = NO
PHYSICAL_AUTO_DELETION = FORBIDDEN
S6_PROOF_REWRITE = FORBIDDEN
GIT_PUBLICATION = NO
~~~

No correction may weaken identity checks, permit reuse under divergent identity, invent remote identity, promote V2 data to V1, auto-delete physical files, mutate original SQLite, contact Telegram/RPC, or rewrite S6 evidence.

## 3. Evidence basis and confidence

The Architect reviewed the approved S7/S8 contract, current code and tests, continuity and governance sources, and the chronological S7 implementation report and addenda. The current checkout is branch **work/s0-bootstrap**, HEAD **98d9d6b9ce152b8d2764a4d160fcbdf4722fb257**. Extensive pre-existing changes and artifacts must be preserved.

Historical results are not current post-patch validation. No tests or new probes were run for this audit, and no SQLite corruption was demonstrated.

### 3.1 Windows/asyncio root-cause classification

| Hypothesis or observation | Classification | Basis and limit |
|---|---|---|
| The child can hang while creating the Proactor self-pipe through socketpair fallback and socket.accept | CONFIRMED | Historical stack dumps show this path. They do not identify the underlying control. |
| Execution context affects whether the same Python runtime completes | STRONGLY_SUPPORTED | Python 3.14.7 and the project virtual environment passed natural-exit smokes in a prior escalated/native context and hung in other sessions. No fully controlled comparison of security tokens and OS policy exists. |
| A local socket/loopback restriction is the proximate mechanism | STRONGLY_SUPPORTED as a possibility, not a confirmed root cause | The stack blocks in socket.accept during socketpair fallback. No receipt identifies firewall/WFP, AppContainer, access-denied code, or another specific control. |
| A universal Python 3.14.7 defect caused the hang | DISCARDED | The same runtime completed smoke checks in a different context. |
| Proactor alone is defective | DISCARDED | Historical Proactor and Selector smokes both completed in the prior context. |
| S7 application code caused the isolated minimal smoke hang | DISCARDED for the documented minimal smokes | The hang occurred before application assertions or S7 execution. This does not establish that current S7 behavior is correct. |
| Captured stdout/stderr pipes alone caused the hang | DISCARDED | Historical evidence records the same child-side stack with pipe and file capture variants. |
| TEMP/TMP explains every observed block | DISCARDED for the latest asyncio block | Earlier 83 setup errors involved temporary-directory creation; the later TEMP/TMP write/delete preflight passed while asyncio still timed out. |
| A specific Windows security, firewall, or antivirus control caused the hang | POSSIBLE | Compatible with the observed stack and context variance, but not identified by evidence. |
| Launcher/child PID accounting invalidated some supervisor receipts | POSSIBLE | Some historical records distinguish launcher and child PIDs; this does not explain the child stack or invalidate prior natural Python exits. |
| A permanent configuration change is required | UNKNOWN | A different execution context passed without an application change; no permanent setting is shown necessary. |

Do not state that a specific socket/loopback restriction is confirmed. The confirmed fact is the proximate hang location; the underlying operating-system cause remains unknown.

### 3.1.1 Respostas às dez perguntas de ambiente

1. **Por que o mesmo Python funciona numa sessão e falha em outra?** O processo foi lançado em contextos diferentes. A influência do contexto é fortemente sustentada; o mecanismo exato não foi provado.
2. **Qual é a diferença material conhecida?** Há execução escalada versus restrita, TEMP sob diretórios Packages/sandbox, variações de supervisão/captura e sessões diferentes. Não há fingerprint completo dos tokens ou da política OS para uma comparação controlada.
3. **Onde está o bloqueio?** Na inicialização do event loop, em código da stdlib antes das assertions. Se a causa última é OS ou isolamento continua desconhecido.
4. **Há evidência de restrição de socket/loopback?** Há indícios fortes pelo bloqueio em socket.accept durante socketpair fallback, sem recibo que identifique o controle responsável.
5. **TEMP/TMP e socketpair são independentes?** Sim. TEMP_IO=PASS não implica socketpair ou asyncio PASS; os gates devem ser separados.
6. **Qual teste discriminante mínimo?** Em dois contextos de lançamento documentados, comparar socketpair bruto e asyncio padrão usando mesmo executável, flags, cwd e parâmetros. Usar Selector somente como diagnóstico adicional se necessário.
7. **É necessária alteração de código?** Nenhuma alteração de aplicação foi demonstrada como solução para o hang.
8. **É necessária configuração permanente?** Não há evidência para isso. Não mudar configuração global.
9. **Como obter validação reproduzível?** Fazer preflight e testes na mesma configuração de lançamento, com processo filho, supervisão limitada, exits naturais e recibos duráveis que identifiquem stdout/stderr, timeout, término e exit do filho.
10. **Qual é a menor solução suportada?** Usar o runtime CPython 3.14.x do projeto no .venv conhecido e um contexto Windows autorizado que passe o preflight; parar após falha. Não adotar Selector global, trocar runtime ou adicionar infraestrutura como tentativa cega.

### 3.2 Historical regression reconciliation

The prior regression reported **301 passed / 20 failed / 11 subtests passed**. The latest documented reclassification is **9 V2 / 9 CLI / 2 migration**. Earlier records also state **10 V2 / 9 CLI / 1 migration**.

~~~text
DOCUMENTED_RECLASSIFICATION = 9_V2 / 9_CLI / 2_MIGRATION
ORIGINAL_NODE_RECEIPTS_RECOVERED = NO
HISTORICAL_FAILURE_RECONCILIATION = UNRECONCILED
POST_PATCH_FAILURES_VERIFIED_RESOLVED = 0
~~~

The reports and continuity copies do not contain original individual node IDs or a raw receipt for the 20-failure run. The two migration tests named in the report are:

- tests/integration/test_download_flow.py::test_offline_download_rerun_is_deduplicated
- tests/unit/test_s6_v2.py::test_additive_migration_leaves_v1_downloaded_rows_unchanged

The report attributes nine V2 failures to download identity and nine CLI failures to pre-existing reparse points. This classification is documentary evidence, not a node-by-node reconciliation. The inspected cache contains failures from other runs and cannot substitute for the missing original receipt.

## 4. Review of the approved S7/S8 contract

Source: **docs/contracts/S7_S8_INCREMENTAL_SYNC_OPERATIONAL_HARDENING_IMPLEMENTATION_CONTRACT.md**.

The approved contract has sound central protections: it separates baseline/checkpoint concepts, protects against unverified absence, retains S5/S6 guards, keeps V2 globally off, and prohibits treating absence as deletion. No logical contradiction requires weakening those protections. The gaps below must be closed in a future implementation contract or retained as explicit open decisions.

| Subject | Finding | Required clarification |
|---|---|---|
| Incremental algorithm | Objective is adequate; baseline selection and completion algorithm are incomplete | Define confirmed baseline, immutable per-run remote-head snapshot, exclusive resume cursor, persisted scan watermark, and exact completion/promotion condition independently. |
| High-water, watermark, cursor, snapshot | Three terms are distinguished, but the remote snapshot lacks an independently precise definition | Define H (confirmed high-water), S (snapshot head), C (run cursor), and persisted watermark; numerical equality does not make meanings interchangeable. |
| Baseline across FULL and INCREMENTAL | Contract does not say how a later FULL affects an earlier larger COMPLETE watermark or empty channel | A baseline exists if any COMPLETE run exists. H is the maximum non-null watermark among every COMPLETE run for the channel; H is None only if COMPLETE runs exist but all have null watermarks. |
| Reconciliation window | Unit is unspecified | Treat it as inclusive width in Telegram message-ID space, not a count of messages: for non-null H, floor=max(1,H-window+1). A zero window produces H+1. |
| Message limit and resume | Contract does not say whether limit is per call or cumulative for a run | Preserve current behavior: limit applies per invocation, resumed calls reuse stored run scope, and counters accumulate. A resumed total may exceed one invocation's limit. |
| Legacy download identity | Compatibility is required, but physical-file provenance is not established for a legacy download | Copying current media metadata into a snapshot does not prove those bytes belong to the historic file. Legacy rows without verifiable provenance must be blocked from reuse and resume. |
| Media replacement | Core protection is correct but the flow needs exact behavior | Preserve old physical files and snapshots. A changed remote identity cannot adopt or overwrite old bytes. |
| Media absent on a reobserved message | No persisted state distinguishes last-known media from media absent in the latest observation | Record NOT_OBSERVED, preserve associations and files, block planning/reuse/resume for that media, and report a separate count. Do not call it deleted. |
| Confirmed deletion | A4 names the distinction but does not define proof source or tombstone policy | Keep S7-A4-C as OPEN_DECISION. Missing, inaccessible, partial, or failed scans cannot prove deletion. No tombstone or deletion behavior may be implemented until evidence and policy are approved. |
| Migration idempotence and rollback | Terms permit interpreting raw SQL rerun as idempotence | Reapplication is through the migration ledger and repository migrator, not raw ALTER TABLE SQL. Exercise rollback only on a temporary copy; never downgrade the original database. |
| CLI/parser integration | Generic and specialized behavior are required, but current S7 CLI tests cover the generic path | Add an offline RASMOO incremental CLI fixture with two runs and stable IDs/associations. |
| Acceptance evidence | Criteria exist but receipt requirements are underspecified | Record exact command, execution context, source fingerprint, node IDs, counts, stdout/stderr, natural process exit, and timeout/termination state. Collect-only is not functional PASS. |

### 4.1 S8 improvements proposed for later specification

These are specification recommendations only. They do not start S8, authorize implementation, or supply unapproved values.

1. Define retry budgets by operation. S5 per-media limits do not automatically govern scanner, authentication, or catalog operations. A future contract should name retryable categories, maximum attempts, total deadline, backoff/jitter, and cancellation behavior. Until then, add no automatic retries outside established S5 behavior.
2. Define a configuration table for TOML, environment, and CLI inputs, including type, unit, range, default, and per-key precedence. Do not invent defaults during implementation.
3. Preserve one to two download workers while S5 budgets are frozen. A benchmark may inform a later proposal but cannot silently expand concurrency.
4. Define mapping from internal progress states to operational states. A COMPLETE scan followed by a failed catalog rebuild must not report global success.
5. Require redaction tests using synthetic sentinels across stdout, stderr, logs, and tracebacks; check UTC timestamps and run/operation correlation.
6. Preserve S5 disk margin and .part accounting. Failure to measure available space blocks before writing.
7. Keep memory thresholds as OPEN_DECISION until dataset, measurement method, and accepted limit are defined.
8. Keep S8 sequenced after S7 acceptance and separate authorization.

## 5. Executable correction issues

### S7-RCA-01 — Confirmed high-water can regress after a FULL run

**Severity:** P2.

**ROOT_CAUSE:** Baseline queries select the latest COMPLETE run by time instead of the maximum confirmed watermark across all COMPLETE runs.

**EVIDENCE:** **src/telegram_courses/sqlite_repository.py:153** (get_confirmed_high_water), **:223** (start_sync_run), and **:335** (get_sync_run_summary) order COMPLETE runs by time and select one row. Incremental completion preserves the maximum of prior high-water and snapshot, but baseline selection can still regress after FULL.

**AFFECTED_FILES/FUNCTIONS:**
- src/telegram_courses/sqlite_repository.py: get_confirmed_high_water, start_sync_run, get_sync_run_summary, finish_run.
- tests/integration/test_s7_incremental_sync.py and tests/integration/test_sqlite_repository.py.

**REQUIRED_CHANGE:** Use one shared baseline rule for reads and transactional run creation:

~~~sql
SELECT COUNT(*), MAX(watermark_message_id)
FROM scan_runs
WHERE channel_id=? AND status='COMPLETE';
~~~

has_baseline is completed_count > 0. H is the maximum non-null watermark across all COMPLETE runs. PARTIAL, FAILED, and INTERRUPTED runs never contribute. Preserve (True, None) when COMPLETE runs exist but all have null watermarks. During incremental completion, retain max(H_before,S) and promote only in the COMPLETE transaction.

**PROHIBITED_CHANGE:** Use a partial cursor as baseline; select only the newest COMPLETE run; lower H because a later remote head is lower; infer deletion from absence.

**COMPATIBILITY_IMPACT:** No migration. Preserve existing rows and downloads.

**TEST_CASES:**
- COMPLETE 100 → FULL COMPLETE 90 → incremental still starts at 100.
- COMPLETE 100 → FULL COMPLETE with null head → incremental still starts at 100.
- PARTIAL watermark 999 does not affect H.
- Only COMPLETE empty runs produce (True,None).
- Equal timestamps do not change the aggregate result.
- Close/reopen database and repeat.

**ACCEPTANCE_CRITERIA:** Both lower-head FULL scenarios retain H=100; baseline presence is correct; no ID, download, or checkpoint is lost; no partial run is promoted.

### S7-RCA-02 — Migration 006 gives legacy rows an unproven identity snapshot

**Severity:** P1 potential integrity risk. No actual corruption was demonstrated.

**ROOT_CAUSE:** Migration backfills a snapshot from mutable current media metadata and presents it as the identity represented by an older physical download.

**EVIDENCE:** **src/telegram_courses/migrations/006_s7_incremental_sync.sql:18-31** copies media_items identity into download snapshot fields. persist_batch can update current media metadata in **src/telegram_courses/sqlite_repository.py:441**. Legacy V1 rows do not record provenance of physical bytes.

**STATIC FAILURE SCENARIO:** Historical file A and SHA-A exist; current media metadata was edited to B before migration; 006 snapshots B. If A and B have equal size, metadata comparison B-to-B does not establish that bytes in A are B. The planner can classify the old row as already downloaded while the local hash only proves A against its saved SHA.

**AFFECTED_FILES/FUNCTIONS:**
- src/telegram_courses/sqlite_repository.py: migrate.
- src/telegram_courses/download_repository.py: _assert_media_identity, start, start_resume, record_v2_selection, assert_download_identity.
- src/telegram_courses/s5_downloads.py: DownloadPlanner.build.
- A new additive migration after 006 and offline fixtures.

**REQUIRED_CHANGE:**
1. Add downloads.remote_identity_provenance with values UNKNOWN_LEGACY and CAPTURED_AT_START; default every existing row to UNKNOWN_LEGACY.
2. Preserve every existing field, physical file, hash, and historical evidence. Do not infer provenance from timestamps, path, byte count, local SHA, current media row, or presence of identity columns.
3. A new download row created by DownloadRepository.start() records CAPTURED_AT_START and its identity snapshot in the same transaction.
4. ON CONFLICT must not promote an unknown legacy row or adopt a different identity.
5. Reuse, recovery, resume, and completion operations that depend on an existing download require known provenance and matching snapshot.
6. record_v2_selection still permits no download row; when a row exists, it applies the same provenance and identity guard.
7. The planner requires the provenance schema. If required columns are missing, return stable blocked result SCHEMA_MIGRATION_REQUIRED without writing.
8. An existing UNKNOWN_LEGACY row is blocked as IDENTITY_SNAPSHOT_UNVERIFIED. The per-item start/resume error remains stable as RESUME_IDENTITY_MISMATCH for missing/unverifiable/divergent existing identity. No gateway call or row/file mutation may occur on that block.

**PROHIBITED_CHANGE:** Invent or backfill physical identity; promote V2 to V1; delete evidence; permit reuse on identity mismatch; weaken fail-closed behavior.

**COMPATIBILITY_IMPACT:** Legacy rows remain preserved and inspectable, but reuse/recovery stays blocked until a separately approved proof and recovery procedure. V1 remains active for newly captured downloads. Legacy requalification is outside this contract.

**TEST_CASES:**
- Construct a true pre-006 database with download bytes A and current media identity B, including equal-size A/B.
- Exercise a database that has 006's copied snapshot but lacks provenance.
- New download through start() captures provenance and snapshot atomically.
- V2 selection with no existing download row remains admissible after current-media validation.
- Existing UNKNOWN_LEGACY row blocks start, planner reuse, recovery, and resume.
- Divergent current/snapshot identity blocks.
- Planner against old schema is read-only and returns SCHEMA_MIGRATION_REQUIRED.

**ACCEPTANCE_CRITERIA:** No ALREADY_DOWNLOADED, ALREADY_VALID, or RECOVERED result for unknown provenance or mismatch; no gateway call on blocked cases; positive newly captured controls pass; all prior bytes, hashes, paths, rows, and evidence remain unchanged.

### S7-RCA-03 — Reobserved media absence has no durable state

**Severity:** P2.

**ROOT_CAUSE:** Persistence preserves prior media ordinals but does not record that they were absent in a later observation, so the planner reads them as current candidates.

**EVIDENCE:** **src/telegram_courses/sqlite_repository.py:441-535** retains media rows on upsert; **src/telegram_courses/catalog_repository.py:175** reads media without a last-observation state; DownloadPlanner.build does not distinguish stale media from currently observed media.

**AFFECTED_FILES/FUNCTIONS:**
- A new additive migration after 006.
- sqlite_repository.py: persist_batch, finish_run, get_sync_run_summary.
- message_scanner.py: ScanOutcome, _incremental_scan.
- Download identity guards in download_repository.py.
- s5_downloads.py: DownloadPlanner.build.
- cli.py: _scan_channel.

**REQUIRED_CHANGE:**
1. Add media_items.remote_observation_state with OBSERVED and NOT_OBSERVED; default existing rows to OBSERVED to preserve their last recorded observation without claiming fresh remote presence.
2. When a message is observed, mark present ordinals OBSERVED and previously stored ordinals absent from that observation NOT_OBSERVED.
3. Preserve old metadata, catalog associations, download rows, partial/final files, and hashes.
4. Count a state transition as a message update; identical repeated observation remains idempotent.
5. Block planning, reuse, start, and resume for NOT_OBSERVED media as BLOCKED / MEDIA_NOT_OBSERVED.
6. A later positive observation may restore OBSERVED; identity mismatch remains subject to RCA-02.
7. Add durable per-run scan_runs.media_unverified count for NOT_OBSERVED media belonging to messages reobserved in that run. Propagate it through ScanOutcome and CLI as media_unverified=N. Do not redefine messages_unverified.
8. Retain historical catalog and associations; add no tombstone.

**PROHIBITED_CHANGE:** Delete absent ordinals, clear associations from unverified absence, mark REMOVED/DELETED, alter .part or final files, or adopt a new identity snapshot.

**COMPATIBILITY_IMPACT:** Conservative block for media absent from a later observation; other persisted records and S5/S6 limits remain intact.

**TEST_CASES:** Document followed by observation without media; repeated absence; media reappears unchanged; media reappears with changed identity; partial/reopen; existing final and .part files preserved.

**ACCEPTANCE_CRITERIA:** NOT_OBSERVED persists, the separate count is correct, blocked cases call no gateway and mutate no download/file, and reappearance does not bypass identity mismatch.

### S7-RCA-04 — Inconclusive process ownership can be treated as dead

**Severity:** P1 potential concurrency/integrity risk.

**ROOT_CAUSE:** **src/telegram_courses/download_repository.py:98** (_process_is_alive) maps inconclusive OS errors and failed GetExitCodeProcess calls to False, which can authorize reclaim. The scan repository already has a tri-state helper that preserves unknown status.

**EVIDENCE:** The download helper is used by start and start_resume; the scanner helper at **src/telegram_courses/sqlite_repository.py:19** returns None for indeterminate OS errors.

**AFFECTED_FILES/FUNCTIONS:**
- download_repository.py: _process_is_alive, start, start_resume.
- downloads.py: _download_locked, _download_v2_locked.
- s5_downloads.py: ownership classification in DownloadPlanner.build.

**REQUIRED_CHANGE:** Represent process state as ALIVE, DEAD, or UNKNOWN (or equivalent tri-state). Only positive OS evidence that a PID is absent permits reclaim for a state requiring an owner. Inconclusive query errors block a second writer. Preserve valid FAILED_RETRYABLE with owner_pid=None, which represents explicit writer release after a captured failure.

**PROHIBITED_CHANGE:** Treat None, generic API errors, or failed GetExitCodeProcess as proof of death; broaden worker concurrency; rewrite S6 proofs.

**COMPATIBILITY_IMPACT:** May block recovery when OS ownership cannot be determined; prevents concurrent writers. S6 remains CLOSED_WITH_EXCEPTIONS.

**TEST_CASES:** Windows errors 87, 5, and other errors; failed GetExitCodeProcess; live, dead, and unknown PID; missing owner for active states; explicit FAILED_RETRYABLE with no owner.

**ACCEPTANCE_CRITERIA:** A second writer is admitted only after positive death/release evidence; unknown ownership performs no stream/write; valid retryable recovery remains available.

### S7-RCA-05 — Focused coverage does not prove required combinations

**Severity:** P2.

**ROOT_CAUSE:** Existing tests omit required contract combinations; a test called legacy starts through the current migrator, which may already apply 006.

**EVIDENCE:** Existing S7 integration tests include generic CLI coverage and high-water coverage limited to incremental runs. The legacy migration fixture in **tests/unit/test_s6_v2.py** starts from the current migrator rather than a true pre-006 schema.

**AFFECTED_FILES:** tests/integration/test_s7_incremental_sync.py, tests/integration/test_s7_incremental_cli.py, tests/integration/test_sqlite_repository.py, tests/unit/test_s6_v2.py, and affected download-flow tests.

**REQUIRED_CHANGE:** Add offline cases specified by RCA-01 through RCA-04, including a true 005-to-006-to-next-migration fixture, rollback fault injection on a temporary database, foreign-key/WAL/busy-timeout/reopen checks, and specialized RASMOO incremental CLI behavior over two runs.

**PROHIBITED_CHANGE:** Replace negative fixtures with fabricated positive identity; remove guards/assertions to make tests pass; report setup/hang as assertion failure.

**COMPATIBILITY_IMPACT:** Offline proof only; no change to real Telegram behavior.

**TEST_CASES:** Durable node IDs and receipts; negative controls make no gateway call and mutate no rows/files; specialized and generic CLI routes; stable catalog/media IDs; no V2-to-V1 promotion.

**ACCEPTANCE_CRITERIA:** The RASMOO and generic paths both pass the two-run scenarios; no reparse target is traversed; no path escapes the fixture root; node IDs and receipts are retained; no guard is relaxed.

### S7-RCA-06 — Historical corrections lack post-patch assertions

**Severity:** P1 acceptance risk.

**ROOT_CAUSE:** After the static corrections, available execution contexts failed in setup or hung before assertions.

**EVIDENCE:** The latest implementation report records 83 tmp_path setup errors, a separate Proactor/self-pipe hang, and a later TEMP/TMP write/delete pass followed by asyncio timeout. No assertion ran after relevant patches. Prior 15 focused PASS and 301/20 regression predate those patches.

**AFFECTED_FILES/FUNCTIONS:** Existing corrections in download_repository.py::record_v2_selection, tests/integration/test_cli_smoke.py reparse snapshot (including getattr(info, "st_reparse_tag", None)), and updated migration-version expectations in tests.

**REQUIRED_CHANGE:** Validate current code and preserved static corrections using the separately authorized future gates in section 8. No additional production code change is prescribed for these three historical fixes by this audit.

**PROHIBITED_CHANGE:** Declare 20 failures resolved from static review or pre-patch PASS results; classify setup/hang as assertion FAIL; recreate missing original receipts.

**COMPATIBILITY_IMPACT:** Existing behavior remains pending functional evidence. Any future result must be reported as a new run when original node receipts are unavailable.

**TEST_CASES:** Focused V2/CLI/migration nodes, then S7 suites and offline regression, with exact node IDs and durable receipts.

**ACCEPTANCE_CRITERIA:** Current authorized runs reach and pass assertions with natural process exits and complete receipts. If the environment blocks before assertions, report BLOCKED; no failure is deemed resolved.

## 6. S7-A1 through S7-A6 conformance and acceptance

| Criterion | Current implementation/evidence | Gap or defect | Future acceptance |
|---|---|---|---|
| S7-A1 NEW_MESSAGES_IDEMPOTENT | Unique keys and transactional upsert; new runs read current head | Historical positive evidence is limited; COMPLETE baseline can regress after FULL | RCA-01; two runs, replay, and new IDs produce one row per identity |
| S7-A2 CHECKPOINT_DURABLE | Batch cursor transaction, separate snapshot, promotion on COMPLETE | RCA-01 and interruption/provenance combinations remain unproven | Fail/cancel/rollback/reopen cannot skip IDs or promote partial state |
| S7-A3 EDITS_AND_MEDIA_REPLACEMENT_SAFE | Metadata updates; existing snapshot checks mismatch before reuse/recovery | RCA-02 and RCA-03; legacy physical identity has no provenance | UNKNOWN, mismatch, and NOT_OBSERVED all block; rows/files/hashes preserved |
| S7-A4 DELETION_INACCESSIBILITY_DISTINGUISHED | Missing messages remain preserved and counted; access denial does not promote checkpoint | Media absence lacks durable state; positive deletion source/policy is undefined | RCA-03; keep A4-C OPEN_DECISION; no false tombstone |
| S7-A5 SQLITE_COMPATIBLE | Migration 006 is additive; ledger migrator and prior migration smoke exist | True legacy fixture incomplete; RCA-02/03 need later additive migration; post-patch assertions absent | Fresh and true legacy DBs, ledger reapply, rollback, FK check, reopen; no original DB |
| S7-A6 CLI_PARSER_INTEGRATION | Generic incremental CLI path exists | Specialized RASMOO two-run fixture missing; limit/count semantics need explicit proof | RASMOO and generic paths over two runs; stable IDs; partial scan does not rebuild; catalog failure means global failure |

Recommended conformance: **PARTIAL / STATIC_DEFECTS_AND_VALIDATION_GAPS**. S7 remains unaccepted.

## 7. Future implementation sequence

This sequence becomes actionable only after separate user authorization.

1. Record exact source fingerprint and authorized scope; preserve current worktree.
2. Add one additive migration after 006 for provenance, media observation, and per-run count. Use existing migration ledger and transaction boundaries.
3. Implement identity-provenance and NOT_OBSERVED guards before planner reuse, recovery, resume, and completion.
4. Apply the common monotonic COMPLETE high-water rule to queries and transactional run creation.
5. Make download ownership checks tri-state and preserve explicit FAILED_RETRYABLE release semantics.
6. Add focused offline fixtures, including true legacy schemas and specialized CLI.
7. Execute future gates in section 8 in order. Stop at the first failed or blocked gate.
8. Reconcile continuity and results without changing frozen acceptance statuses. S7 acceptance and S8 entry remain user decisions.

No production changes are authorized by this document.

## 8. Future verification and environment gates

All commands and tests here are a proposed plan for a separately authorized activity. None were run during this audit.

### 8.1 Environment gates

| Gate | Input and procedure | PASS evidence | Block condition |
|---|---|---|---|
| E0 — Context | Project virtual environment; CPython 3.14.x; correct cwd. Record executable/version, host, launch configuration, TEMP/TMP, and isolation context without secrets. | Identified runtime/context fingerprint | Runtime differs or launch context cannot be identified |
| E1 — TEMP_IO | New short, user-owned directory with no reparse component; create/read/delete only an isolated synthetic file | Independent TEMP_IO PASS | Any ownership/path/access failure; do not call this an asyncio failure |
| E2 — socketpair | Supervised child performs raw socketpair, closes both ends, prints flushed terminal marker | Natural exit 0 and final marker before timeout | Timeout/kill/error; do not continue to functional tests |
| E3 — asyncio | Same launch configuration; child performs minimal asyncio.run(asyncio.sleep(0.1)) and prints terminal marker | Natural exit 0 and final marker | Timeout/kill is not PASS. Selector is diagnostic only; no permanent global setting |

E1 and E2/E3 are independent. TEMP_IO PASS does not imply asyncio is usable. Do not change application code to work around this environment hang absent new evidence. Do not install a global Selector policy or change Python versions as a blind retry.

Future bounded smoke commands, for an authorized supervisor:

~~~text
<python-do-venv> -I -B -c "import socket; a,b=socket.socketpair(); a.close(); b.close(); print('SOCKETPAIR_PASS', flush=True)"
<python-do-venv> -I -B -c "import asyncio; asyncio.run(asyncio.sleep(0.1)); print('ASYNCIO_PASS', flush=True)"
~~~

Record launcher PID separately from child-reported PID; capture stdout, stderr, timeout, termination, and child exit. A shell exit or launcher PID is not a substitute for the Python process result.

### 8.2 Functional and static gates

| Gate | Input/procedure | Expected result | Block/evidence requirement |
|---|---|---|---|
| V1 — Defect cases | Execute focused cases for RCA-01 through RCA-05 and existing V2/CLI/migration corrections | Assertions pass | First assertion failure blocks broader run; setup/hang reported as BLOCKED |
| V2 — Identity fixtures | Positive identity captured at start; negative current-media, snapshot, provenance, and observation cases; keep V1 and V2 separate | Zero gateway calls for blocked cases; rows and bytes preserved | Any ambiguous reuse blocks |
| V3 — S7 suites | Run both S7 integration files, including RASMOO | Expected counts and durable node IDs | A4-C remains open until decision; no deletion inference |
| V4 — Migration | Fresh and genuine legacy schemas; call repository migrate twice; inject rollback; reopen and check FK/invariants | Expected schema and preserved H; clean FK | Raw SQL rerun is not proof; do not use MAX(version) alone |
| V5 — Offline regression | Run unit and integration suites using a fresh isolated basetemp; exclude manual S6 proofs/Harness | Complete offline suite with no unexpected failure | Individualize skips/errors; preserve all receipts |
| V6 — QA | Ruff on changed files and git diff --check | Both pass | Static QA cannot replace functional gates |

Functional PASS requires assertions to execute, expected statuses, durable node IDs/receipts, and natural child exits. Collect-only and static review are not functional PASS.

## 9. Open decisions and boundaries

1. **S7-A4-C:** Approve the evidence source and policy for confirmed deletion, or formally accept the exception. Until then, keep unverified absence distinct and do not tombstone.
2. **Legacy identity requalification:** A dedicated proof and authority are required to re-enable UNKNOWN legacy downloads. This contract does not provide that procedure.
3. **Replacing an old download with a new identity:** If desired, define a versioning/reselection policy separately. This contract preserves old bytes and blocks identity substitution.
4. **S8 retry/configuration/thresholds:** Define per-operation budgets, configuration keys/precedence, and memory thresholds before S8 implementation. This document supplies no unapproved defaults.
5. S8 remains sequenced after S7 acceptance and separate authorization.

If any choice is required to implement a specific path, stop that path and request user deliberation. Do not let an implementer infer policy.

## 10. Non-required changes

The audit does not support:
- changing S7 application code to fix the environment hang;
- changing asyncio policy globally to Selector;
- removing historical reparse points or relaxing path protections;
- rewriting migrations 001–006;
- changing S5 budgets, worker limits, or S6 proofs;
- recreating the original 20-failure baseline;
- declaring the 20 failures fixed without post-patch assertions;
- starting S8 or changing acceptance.

## 11. Contract quality gates

The ROOT reviewed the solution contract before materialization. This table records that review; final materialized files remain subject to ROOT post-write verification.

| Gate | Status | Basis |
|---|---|---|
| G1 Evidence linkage | PASS | Each correction issue cites code, report, or test evidence. |
| G2 Fact/hypothesis separation | PASS | Environment classifications and unreconciled historical IDs are explicit. |
| G3 File/function identification | PASS | Affected paths and entry points are listed per issue. |
| G4 Unambiguous expected behavior | PASS | Algorithms, guards, blocked results, and acceptance conditions are specified; remaining choices are OPEN_DECISION. |
| G5 S5/S6 compatibility | PASS | Frozen limits, fail-closed behavior, and S6 status are preserved. |
| G6 Verifiable environment strategy | PASS | TEMP, socketpair, and asyncio gates are independent with natural-exit evidence. |
| G7 Objective tests | PASS | Focused cases and exact outcomes are listed. |
| G8 No implementation | PASS | This is a proposed document; code changes and tests are not authorized here. |
| G9 Frozen authorities unchanged | PASS | S7 acceptance remains pending; S8 deferred; no frozen contract or proof is changed. |
| G10 Implementer need not repeat audit | PASS | Issue IDs, files/functions, sequence, tests, gates, and boundaries are explicit. |
