# Estado corrente — projeto_telegram_courses

```text
DOCUMENT_ROLE = PROJECT_STATE
STATE_VERSION = 2.16
STATUS = ACTIVE / S0_CLOSED / S1_IN_PROGRESS / S1-A_PASS / S1-B_PASS / S1-C_PASS / S1-C-OFF-01_PASS / S1-D_IMPLEMENTED / S1-D_REAL_FUNCTIONAL_PASS / S1-D_FINAL_ACCEPTANCE_PENDING / CREDENTIAL_VAULT_PASS / FULL_REGRESSION_NOT_PASS
LAST_UPDATED = 2026-10-09 / America/Sao_Paulo
PROJECT_IDENTITY = projeto_telegram_courses
PROJECT_ROOT = C:\Users\walac\desenvolvimento\projeto_telegram_courses
CURRENT_ENVIRONMENT = HOME_COMPUTER / LOCAL_WORKSPACE
REMOTE_ORIGIN = https://github.com/wromanov/projeto_telegram_courses.git
CURRENT_BRANCH = work/s0-bootstrap
UPSTREAM = origin/work/s0-bootstrap
PRECHECK_HEAD = e947406dbcab8ef593123f079daa279903805d2c / confirmed for S1-TEST-01
PRECHECK_UPSTREAM_DIVERGENCE = 0/0 / local origin/work/s0-bootstrap reference; no fetch performed
BASELINE_TRACEABILITY = S0-SL01/SL02 checkpoint 1cde21d4d0f95b9b190c02f4a69a91c25485428c; SP01-01..10 PASS in evidence; current baseline HEAD confirmed above
CURRENT_PHASE = PHASE_1_TELEGRAM_ACCESS / S1 IN_PROGRESS
CURRENT_DELIVERY_UNIT = S1 / IN_PROGRESS / S1-A PASS / S1-B PASS / S1-C PASS / S1-D IMPLEMENTED / REAL_FUNCTIONAL_PASS / FINAL_ACCEPTANCE_PENDING
CURRENT_ACTIVITY = S1-D — Consolidated Checkpoint & Cross-PC Handoff
CURRENT_ACTIVITY_STATE = CHECKPOINT_RECONCILED / no implementation in this activity; user-reported real discovery, broadcast and megagroup discovery, local selection, and real-scenario adapter correction are PASS; final acceptance remains pending
LAST_COMPLETED_ACTIVITY = S1-D — Consolidated Checkpoint & Cross-PC Handoff
NEXT_ACTIVITY = S1-D — Regression Fix + CLI Numeric Selection
NEXT_ACTIVITY_READINESS = Existing implementation and real functional scenario PASS / regression NOT_PASS / CLI numeric selection approved but not implemented / final acceptance pending
NEXT_ACTIVITY_AUTHORIZATION = This checkpoint records outcomes only; implementation, freeze, Git publication, and phase advancement are not authorized here
S0_SELECTED = YES
S0_STARTED = YES
S0_AUTHORIZED = YES / S0 only, per recorded user decision
S0_COMPLETION_PERCENT = 100%
SP01_01..09 = PASS
SP01_10 = PASS
SP01_RESULT = PASS
SP01_RUNTIME_VALIDATION = PASS / final home replay; see docs/engineering/evidence/SP01_STACK_WINDOWS.md
PROJECT_COMPLETION_PERCENT = NOT_FORMALLY_DEFINED
CURRENT_AUTHORITIES = ACTIVE_AUTHORITY_MAP.md; planning/ROADMAP.md; planning/SPRINTS.md; PROJECT_GOVERNANCE_BINDING.json; domain authorities listed in ACTIVE_AUTHORITY_MAP.md
CURRENT_INVARIANTS = incremental canonical-flow integration; at most one active formal activity; readiness != authorization; implementation != integrated; gateway/adapters; pluggable parsers; three sources of truth; physical commit before DOWNLOADED; conditional resume; bounded workers; legitimate access only
S1_DOR = PASS / DOR_BLOCKERS = NONE; evidence: docs/reports/S1_DOR_GAP_REVIEW_2026-10-07.md
S1_IMPLEMENTATION_AUTHORIZATION = Credential vault implementation explicitly requested and completed offline; earlier bounded S1-D real discovery authorization remains limited to that single validation; no login, freeze, or Git publication authorization inferred
S1_STARTED = YES / first material source file created: src/telegram_courses/telethon_session.py
CURRENT_SLICE = S1-D / IMPLEMENTATION_AND_CREDENTIAL_VAULT_PASS_OFFLINE; S1-A / PASS; S1-B / PASS; S1-C-OFF-01 / PASS; S1-C / PASS
S1A_STATUS = PASS / acceptance criteria met; evidence in the implementation contract and tests
S1B_STATUS = PASS / offline authentication and gateway validated; no live Telegram activity
S1C_STATUS = PASS / original failed attempt preserved; later authorized authentication and protected-session reuse passed on user-provided execution evidence
S1C_ORIGINAL_FIRST_INVOCATION = FAIL / sanitized output: server closed connection, followed by authentication rejected; cause NOT_ESTABLISHED
S1C_ATTEMPT_HISTORY = 1) first real attempt failed; 2) triage found observability gap; 3) S1-C-OFF-01 offline correction passed; 4) later retry preflight initially blocked by missing local configuration; 5) user configured credentials locally; 6) real authentication passed; 7) protected session file was reported present; 8) second invocation passed through session reuse; 9) S1-C formally closed PASS
S1CA02_PREFLIGHT = BLOCKED_PRECHECK / initially stopped before CLI invocation because API environment variables were unavailable; user later configured them locally and supplied successful validation evidence
S1CA02_FIRST_INVOCATION = PASS / user-provided execution evidence: authentication successful after phone, OTP and 2FA prompts
S1CA02_API_CREDENTIALS_PRESENT = YES / configured locally by user; values were not displayed or requested in chat
S1CA02_SECOND_INVOCATION = PASS / user-provided execution evidence: authentication successful in a new process without phone, OTP or 2FA prompts
S1CA02_PROTECTED_SESSION_PERSISTENCE = PASS_USER_PROVIDED_AT_VALIDATION / expected LOCALAPPDATA session.dpapi path was reported present; file content was not inspected
S1CA02_SESSION_REUSE = PASS / second invocation succeeded without reauthentication challenges; user-provided execution evidence
S1CA02_DPAPI_CURRENT_USER = SUPPORTED_BY_IMPLEMENTATION_AND_OFFLINE_UNIT_TESTS / actual runtime protection is NOT_INDEPENDENTLY_VERIFIED; blob was not inspected
S1CA02_CONTROLLED_PROCESS_COMPLETION = PASS / user-provided evidence reports successful CLI completion for both invocations
S1CA02_UNPLANNED_RETRIES = NONE_REPORTED
S1CA02_UNAUTHORIZED_OPERATIONS = NONE_REPORTED / no channel discovery, message reads, downloads or administrative operations
S1CA02_SOURCE_CODE_CHANGES = NONE
S1CA02_CONTINUITY_RECONCILIATION = PASS / PROJECT_STATE, CONTINUITY_RECORD, LAST_HANDOFF and S1 plan summary reconciled
S1CA02_GIT_ACTIONS = NONE
S1C_REAL_AUTHENTICATION = PASS / later controlled invocation passed; original failed attempt remains historical
S1C_PROTECTED_SESSION_PERSISTENCE = PASS_USER_PROVIDED / presence reported after authentication; current task runtime did not find the file, so current presence is NOT_INDEPENDENTLY_VERIFIED
S1C_SECOND_INVOCATION = PASS_USER_PROVIDED
S1C_REAL_SESSION_REUSE = PASS_USER_PROVIDED / no phone, OTP or 2FA challenge on second invocation
S1C_CONTROLLED_PROCESS_COMPLETION = PASS_USER_PROVIDED
S1C_DPAPI_CURRENT_USER = SUPPORTED_BY_SOURCE_AND_OFFLINE_TESTS / runtime use is NOT_INDEPENDENTLY_VERIFIED; blob not inspected; no cryptographic claim is based on the .dpapi extension alone
S1C_DPAPI_LOCAL_MACHINE = PROHIBITED_BY_SOURCE_AND_OFFLINE_TESTS / implementation uses CRYPTPROTECT_UI_FORBIDDEN only; runtime use is NOT_INDEPENDENTLY_VERIFIED
S1C_PLAINTEXT_AT_REST = NOT_INDEPENDENTLY_VERIFIED_FOR_RUNTIME_BLOB / implementation writes protected bytes; offline test verifies synthetic plaintext is absent from artifact
S1C_SESSION_STORAGE_OUTSIDE_REPOSITORY = SUPPORTED_BY_CONTRACT_AND_SOURCE / runtime location is NOT_INDEPENDENTLY_VERIFIED; user reported LOCALAPPDATA path, but current task runtime did not find the file
S1C_SECRET_LOGGING = NOT_INDEPENDENTLY_VERIFIED_FOR_REAL_INVOCATIONS / source and offline tests support sanitized diagnostics; real invocation logs were not inspected
S1C_NO_AUTOMATIC_EXPORT = SUPPORTED_BY_SOURCE_AND_OFFLINE_TESTS / runtime behavior NOT_INDEPENDENTLY_VERIFIED
S1C_NO_AUTOMATIC_BACKUP = SUPPORTED_BY_SOURCE_AND_OFFLINE_TESTS / runtime behavior NOT_INDEPENDENTLY_VERIFIED
S1C_UNAUTHORIZED_TELEGRAM_OPERATIONS = NONE_REPORTED / authentication only; no channel discovery, reads or downloads
S1C_UNPLANNED_RETRIES = NONE_REPORTED / no retry beyond the two authorized invocations
S1COFF01_STATUS = PASS / implementation and validation complete
S1COFF01_ERROR_MAPPING_FIX = PASS / asyncio.IncompleteReadError maps to NetworkError
S1COFF01_SAFE_DIAGNOSTICS = PASS / stage, sanitized exception class, project category only
S1COFF01_FOCUSED_TESTS = PASS / 20 passed
S1COFF01_FULL_PYTEST = PASS / 55 passed, 8 subtests passed
S1COFF01_RUFF = PASS
S1COFF01_DIFF_CHECK = PASS
S1TEST01_STATUS = REVALIDATED / prior restricted-executor diagnosis remains historical; independent local PowerShell run passed
S1TEST01_COLLECTION = PASS / 55 tests collected in 1.66 s
S1TEST01_PYTEST_DIAGNOSIS = BLOCKED / TEST_EXECUTION_HANG + ENVIRONMENT_ISSUE
S1TEST01_ROOT_CAUSE = CONFIRMED / Windows Proactor loop startup blocks in socket._fallback_socketpair accept; underlying OS/venv trigger NOT_ESTABLISHED
S1TEST01_AFFECTED_TEST = tests/unit/test_telethon_gateway.py::test_restore_missing_and_invalid_session_then_replace_only_on_success
S1TEST01_FOCUSED_PYTEST = BLOCKED / faulthandler exited after 15 s; exit code 1
S1TEST01_ASYNCIO_PROBE = BLOCKED / standalone asyncio.run reproduced same stack outside pytest; faulthandler exit after 8 s
S1TEST01_FULL_PYTEST = NOT_RUN / focused test did not pass
S1TEST01_RUFF = NOT_RUN
S1TEST01_DIFF_CHECK = NOT_RUN
S1TEST01_TEST_REVALIDATION = PASS / independent PowerShell context; final S1-D full regression below
S1TEST01_TELEGRAM_NETWORK = NO
S1TEST01_SOURCE_CHANGES = NONE / GIT_ACTIONS = NONE
S1D_ENTRY_REVIEW = PASS_USER_PROVIDED / current user request; independent local entry-review report not located
S1D_STATUS = IMPLEMENTED / REAL_FUNCTIONAL_PASS / FINAL_ACCEPTANCE_PENDING
S1D_CONTRACT_FILE = docs/contracts/S1D_CHANNEL_DISCOVERY_SELECTION_CONTRACT.md
S1D_CONTRACT_STATUS = APPROVED_BY_USER_2026-10-09 / FREEZE_NOT_CONFIRMED / GOV-01_EXTERNAL_DEPENDENCY
S1D_DOR = IMPLEMENTATION_GATE_PASS / acceptance gates remain open
S1D_CONTRACT_DRAFT_ACTIVITY = PASS / prior draft; source/tests unchanged, no pytest or Telegram operation
S1D_DECISION_CLOSEOUT = PASS / DEC-S1D-01/02/03 registered; OPEN-04 architectural decision resolved; numeric baseline approved; operational calibration and real acceptance, GOV-01 freeze adjudication remain pending
S1D_OPEN03_CHOICE = APPROVED_BY_USER_2026-10-09 / preserve approved choice and numeric baseline; do not infer S1-D closure
S1D_OPEN04_CHOICE = D_PLUS_C_APPROVED_BY_DEC-S1D-03 / internal incidental GetDifference and GetChannelDifference allowed only during bounded S1-D lifecycle; application content use prohibited
S1D_OPEN04_ARCHITECTURAL_DECISION = RESOLVED_BY_DEC-S1D-03
S1D_OPEN04_TECHNICAL_VALIDATION = IMPLEMENTATION_GATE_PASS_OFFLINE / synthetic boundary/lifecycle tests passed; authorized real validation remains required for acceptance
S1D_PREVIOUS_ZERO_DIFFERENCE_RESTRICTION = PROVE_ZERO_GET_DIFFERENCE / SUPERSEDED_BY_DEC-S1D-03
S1D_FULL_PYTEST_STATUS = PASS / 96 passed, 8 subtests passed in 158.55s; independent local PowerShell; external timeout 180s not reached; exit code 0
S1D_OPEN04_PROOF_STATUS = EARLIER_FEASIBILITY_PROBE_NOT_DEMONSTRATED / superseded for implementation gate by current synthetic boundary/lifecycle tests PASS; no live Telegram behavior claimed
S1D_OPEN04_EVIDENCE = docs/reports/S1D_OPEN04_OFFLINE_FEASIBILITY_2026-10-08.md / Python 3.14.7, Telethon 1.45.0; local socketpair and asyncio precheck PASS outside restriction; synthetic proof produced no trace and was interrupted after bounded wait; previous static analysis preserved
S1D_OPEN04_AUTHORIZATION_SOURCE = user request 2026-10-08, attachment cc1d0b8b-ef65-4b7e-b914-b88c60161178/Texto colado.txt; offline feasibility only, documentation reconciliation permitted, no implementation/Git/live
S1D_LAST_MESSAGE_POLICY = DEC-S1D-01_APPROVED / incidental getDialogs payload may be received by library/adapter; application processing/persistence/exposure/logging prohibited; NO_MESSAGE_TRANSFER not guaranteed
S1D_CHANNEL_ELIGIBILITY = DEC-S1D-02_APPROVED / BROADCAST_CHANNEL + MEGAGROUP/SUPERGROUP; basic groups, private-user dialogs, bot dialogs and secret chats excluded; ID identity and local selection
S1D_SUPERSEDED_DECISION = BROADCAST_ONLY_PROPOSAL_SUPERSEDED / no FUT-CHDISC-01 created
S1D_RESTORE_ONLY = CLOSED_BY_EXISTING_AUTHORITY / reuse valid session; missing/invalid session directs to existing auth flow; no duplicated login
S1D_DISCOVERY_COMPLETENESS = CLOSED_TECHNICALLY / paginate to exhaustion; explicit partial/cancel/error states; no silent truncation
S1D_POLICY_PIN_DIVERGENCE = FIVE_LOCAL_POLICY_HASHES_MISMATCH / persists with LF normalization; cause and semantic difference NOT_ESTABLISHED; see contract section 11
S1D_POLICY_AUTHORITY_IMPACT = GOVERNANCE_INTEGRITY_NOT_ATTESTED / no material conflict demonstrated for draft; governance adjudication required before freeze
S1D_AUTHORIZATION_SOURCE = explicit user approval/instruction on 2026-10-09; contract, numeric baseline, implementation, and one bounded real validation authorized; no freeze, login, or Git publication authorization inferred
S1D_DECISION_AUTHORIZATION_SOURCE = user request 2026-10-08, attachment 2bb3a3c5-c838-4afe-b184-6bfda45437cc/Texto colado.txt; decision closeout and contract update only
PROJECT_STATE_RECONCILIATION = PASS / current user-reported S1-D outcomes, regression NOT_PASS, approved CLI improvement, and safe resume point reconciled; earlier reports remain historical evidence
S1D_PREVIOUS_PRECHECK = BLOCKED / protected DPAPI session artifact and API environment were absent before the user-provided real attempt; historical checkpoint
S1D_FIRST_REAL_DISCOVERY = FAIL_USER_REPORTED / ADAPTER_FAILURE; PAGES_REQUESTED=1; PAGES_RECEIVED=1; RAW_DIALOGS_RECEIVED=101; CLI list not shown
S1D_ROOT_CAUSE = CODE_PATH_CONFIRMED / adapter rejected response length 101 against requested limit 100 before projection; local ChannelDiscoveryError, no original Telethon exception
S1D_RAW_101_EXPLANATION = Supported pinned-dialog overflow on first exclude_pinned=False response; exact pinned metadata from the reported real response is unavailable, so source-specific attribution remains unverified
S1D_FIX_APPLIED = First-page overflow accepted only when explicit pinned=True metadata accounts for overflow; every row counts against max_raw_dialogs; unsupported overflow and raw-budget excess still fail
S1D_REGRESSION_TESTS = LATEST_USER_REPORTED_RESULT / 109 passed, 1 failed, 11 subtests passed, 183.63s / FULL_REGRESSION=NOT_PASS / no rerun in this activity
FULL_REGRESSION = NOT_PASS
S1D_REGRESSION_FAILURE_FILE = NOT_IDENTIFIED_FROM_AVAILABLE_EVIDENCE
S1D_REGRESSION_FAILURE_TEST = NOT_IDENTIFIED_FROM_AVAILABLE_EVIDENCE
S1D_REGRESSION_FAILURE_MESSAGE = NOT_AVAILABLE
S1D_REGRESSION_FAILURE_CAUSE = UNKNOWN
S1D_CREDENTIALS_VAULT = PASS_OFFLINE / credentials.dpapi distinct from session.dpapi; CurrentUser DPAPI; strict versioned payload; atomic no-overwrite creation; sanitized errors
S1D_CREDENTIALS_SETUP_STATUS = PASS / interactive API ID, hidden API HASH, status reveals only configured/available state
S1D_CREDENTIALS_ENV_RESOLUTION = PASS / complete environment pair precedes vault; incomplete pair errors; no source mixing
S1D_CREDENTIALS_FOCUSED_TESTS = PASS / 29 passed, 11 subtests passed; includes Windows DPAPI integration
S1D_CREDENTIALS_RUFF = PASS / ruff check .
S1D_CREDENTIALS_FULL_PYTEST = PASS / 110 passed, 11 subtests passed in 169.05s; exit code 0; Python 3.14.7 local Windows environment
S1D_CREDENTIALS_REAL_VAULT = NOT_CONFIGURED_BY_AGENT / no real API values read or written
S1D_CREDENTIALS_SESSION_ACCESS = NONE / real DPAPI session not opened or inspected
S1D_CREDENTIALS_TELEGRAM_NETWORK = NONE
S1D_ADAPTER_FAILURE_PREVIOUS_RESULT = PRESERVED / CATEGORY=ADAPTER_FAILURE; PAGES_REQUESTED=1; PAGES_RECEIVED=1; RAW_DIALOGS_RECEIVED=101; the credential vault does not correct or adjudicate this result
S1D_REAL_VALIDATION_STATUS = PASS_USER_REPORTED / final acceptance pending
S1D_CHECKPOINT_SOURCE = CURRENT_USER_INSTRUCTION_2026-10-09 / reported real-functional outcomes; the earlier precheck report remains historical
S1D_REGRESSION_SOURCE = CURRENT_USER_INSTRUCTION_2026-10-09 / failure identity and cause not present in available evidence
S1D_REAL_TELEGRAM_ACCESS = PASS_USER_REPORTED / bounded real discovery scenario
S1D_BROADCAST_DISCOVERY = PASS_USER_REPORTED
S1D_MEGAGROUP_DISCOVERY = PASS_USER_REPORTED
S1D_LOCAL_SELECTION = PASS_USER_REPORTED
S1D_ADAPTER_FAILURE_CORRECTION = VALIDATED_IN_REAL_SCENARIO_USER_REPORTED
S1D_FINAL_ACCEPTANCE = PENDING
S1D_CONTRACT_FREEZE = NOT_CONFIRMED
GOV_01 = EXTERNAL_DEPENDENCY
OPEN-03 = APPROVED
NEXT_APPROVED_CLI_IMPROVEMENT = CLI_NUMERIC_CHANNEL_SELECTION / APPROVED / NOT_IMPLEMENTED / see requirements in current checkpoint handoff
S1D_REAL_VALIDATION_EVIDENCE = docs/reports/S1D_REAL_DISCOVERY_VALIDATION_2026-10-09.md
OPEN_DECISIONS = S1-D final acceptance; identify failure in latest regression when evidence is available; GOV-01 external governance adjudication before freeze
BLOCKERS = S1-D final acceptance pending; regression NOT_PASS; contract freeze not confirmed; GOV-01 external dependency
KNOWN_RISKS = Future-unit risks and entry gates remain in planning/SPRINTS.md and docs/audit/AUDITORIA_TECNICA_2026-10-05.md
DEFERRED_ITEMS = GUI, TDLib and additional support remain deferred; Windows distribution remains S10; other unit-specific items are in planning/SPRINTS.md
IMPLEMENTATION_AUTHORIZATION_STATE = This checkpoint records outcomes only; no new implementation authorization granted
GIT_PUBLICATION_AUTHORIZATION_STATE = NONE / S1-GIT-01 checkpoint is already published; its activity-specific authorization is expired
NEXT_CONTINUITY_CHECKPOINT = S1-D Regression Fix + CLI Numeric Selection; first identify the failure from existing evidence, then correct it and implement approved numbered local channel selection in that next activity; do not rerun regression today
PROJECT_GOVERNANCE_BINDING = ACTIVE / content preserved
SAFE_RESUME_POINT = S1-D implemented and REAL_FUNCTIONAL_PASS for discovery, broadcast and megagroup discovery, local selection, and adapter correction in a real scenario, based on current user-reported results. S1-A/B/C PASS; credential vault PASS. Final S1-D acceptance is pending; do not mark S1-D CLOSED. Latest user-reported regression: 109 passed, 1 failed, 11 subtests passed in 183.63s; FULL_REGRESSION=NOT_PASS. Failure file/test/message and cause are not identified in available evidence; do not rerun the suite today or invent a cause. Contract freeze is NOT_CONFIRMED; GOV-01 is an external dependency. DEC-S1D-01/02/03 and OPEN-03 remain approved; OPEN-03 approval does not close S1-D. Next approved CLI improvement: numbered channel selection by list index while retaining stable Telegram ID internally, with cancel, invalid-input protection, no new Telegram query during choice, no remote action, and offline tests; NOT_IMPLEMENTED. Resume at S1-D Regression Fix + CLI Numeric Selection. No Git publication authorization.
CHAT_HISTORY_REQUIRED_FOR_RESUMPTION = NO
NEW_AGENT_CAN_RESUME_FROM_GOVERNED_PROJECT_ARTIFACTS = YES / verify remote availability at runtime
```

## AGENT_HANDOFF_GATE — PM-01 §12.3

```text
CONTINUITY_ROOT_EXISTS = YES
START_HERE_CURRENT = YES
PROJECT_STATE_CURRENT = YES
NEW_AGENT_BOOTSTRAP_CURRENT = YES
ROADMAP_CURRENT = YES
EXECUTION_PLAN_CURRENT = YES
ACTIVE_AUTHORITY_MAP_CURRENT = YES
CONTINUITY_RECORD_CURRENT = YES
LAST_HANDOFF_CURRENT = YES
GOVERNANCE_BINDING_CURRENT = YES
GOVERNANCE_BINDING_PRESENT = YES
CURRENT_STATE_DISCOVERABLE = YES
LAST_COMPLETED_ACTIVITY_DISCOVERABLE = YES
NEXT_ACTIVITY_DISCOVERABLE = YES
NEXT_ACTIVITY_READINESS_DISCOVERABLE = YES
NEXT_ACTIVITY_AUTHORIZATION_DISCOVERABLE = YES
BASELINE_TRACEABLE = YES
CANONICAL_AUTHORITIES_DISCOVERABLE = YES
OPEN_DECISIONS_DISCOVERABLE = YES
BLOCKERS_DISCOVERABLE = YES
KNOWN_RISKS_DISCOVERABLE = YES
DEFERRED_ITEMS_DISCOVERABLE = YES
AUTHORIZATION_STATE_DISCOVERABLE = YES
SAFE_RESUME_POINT_DISCOVERABLE = YES
CURRENT_PHASE_DISCOVERABLE = YES
CURRENT_DELIVERY_UNIT_DISCOVERABLE = YES
CURRENT_INVARIANTS_DISCOVERABLE = YES
LAST_VALIDATED_INTEGRATED_BASELINE_DISCOVERABLE = YES
KNOWN_STALE_STATE = NO
CONTRADICTORY_ACTIVE_STATE = NO
DUPLICATE_ACTIVE_PROJECT_STATE = NO
DUPLICATE_ACTIVE_ROADMAP = NO
DUPLICATE_ACTIVE_EXECUTION_PLAN = NO
SUPERSEDED_AUTHORITY_USED_AS_CURRENT = NO
CHAT_HISTORY_REQUIRED_FOR_RESUMPTION = NO
NEW_AGENT_CAN_RESUME_FROM_GOVERNED_PROJECT_ARTIFACTS = YES
AGENT_HANDOFF_GATE = PASS
SP01_EXECUTED = YES / SP01-01..10 PASS
```

## Factual basis and publication boundary

The final SP01-10 replay PASS on the home computer and S0 completion at 100%
are the authoritative input to this reconciliation. The evidence record holds
the sanitized replay details. The previous partial replay and `ensurepip`
failure are historical observations, without a claimed root cause. Earlier
40% and SL01/SL02 baseline statements described the previous checkpoint and
are superseded by the S0 closure result. Project-wide completion has no
formal percentage.

Git root, HEAD, upstream synchronization and worktree must be rediscovered
at runtime. The S0 contract stays frozen. The S0 closure's Git publication
authorization was limited to that historical checkpoint. The bounded S1-C
authentication and conditional session-reuse authorization was exercised and
is exhausted. No new live authentication, S1-D implementation, channel
discovery, or Git publication is currently authorized.
