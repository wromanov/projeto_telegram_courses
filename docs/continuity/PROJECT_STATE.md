# Estado corrente — projeto_telegram_courses

```text
DOCUMENT_ROLE = PROJECT_STATE
STATE_VERSION = 2.0
STATUS = ACTIVE / S0_STOPPED_AT_SP01_10_CREATE_REPLAY_FAILURE
LAST_UPDATED = 2026-10-06 / America/Sao_Paulo
PROJECT_IDENTITY = projeto_telegram_courses
PROJECT_ROOT = C:\Users\walacedelgado\PycharmProjects\projeto_telegram_courses
CURRENT_ENVIRONMENT = LOCAL_WORKSPACE
REMOTE_ORIGIN = https://github.com/wromanov/projeto_telegram_courses.git
CURRENT_BRANCH = work/s0-bootstrap
UPSTREAM = origin/work/s0-bootstrap
EXACT_CURRENT_HEAD = DISCOVER_AT_RUNTIME_WHEN_GIT_AVAILABLE
PRE_CHECKPOINT_HEAD = 6db0d9ae694ee98bc164c7c6a0c08012b1bb8cb7
BASELINE_TRACEABILITY = S0-SL01_AND_SL02_CHECKPOINTS; verified baseline commit 1cde21d4d0f95b9b190c02f4a69a91c25485428c; current HEAD discovered at runtime
CURRENT_PHASE = PHASE_0_PROJECT_FOUNDATION / S0
CURRENT_DELIVERY_UNIT = S0 / SPRINT / IN_PROGRESS / 40%
CURRENT_ACTIVITY = SP-01 / STACK WINDOWS / SP01-10 FAILED AT REPLAY CREATION
CURRENT_ACTIVITY_STATE = SP01-01..09 = PASS / later execution facts supplied in the current authorized request and not re-evaluated; SP01-10 initial inventory, pip check and constraints generation PASS; replay venv creation returned native exit 1 and left a partial .venv-replay. No dependent replay step ran.
ACTIVITY_COMPLETION_PERCENT = 56% / factual correction, initial inventory, pip check and constraints generation completed; replay creation failed and final reconciliation records the stop
LAST_COMPLETED_ACTIVITY = S0-SL02_VERIFIED_CHECKPOINT
NEXT_ACTIVITY = RESOLVE_SP01_10_CREATE_REPLAY_FAILURE
NEXT_ACTIVITY_READINESS = BLOCKED / `.venv-replay` exists partially after native exit 1; do not reuse, remove or retry automatically
NEXT_ACTIVITY_AUTHORIZATION = CURRENT SP01-10 AUTHORIZATION WAS USED; the no-retry stop condition requires a new explicit instruction before recovery or another attempt
CURRENT_SLICE = S0-SL03 implementation artifacts exist; verification is not established
S0_SELECTED = YES
S0_STARTED = YES
S0_AUTHORIZED = YES / S0_ONLY / per recorded user decision
S0_COMPLETION_PERCENT = 40% / last recorded value retained; SL03 is not credited as verified
SP01_RUNTIME_VALIDATION = FAIL / SP01-10-CREATE-REPLAY returned native exit 1 after initial inventory and constraints generation
LAST_VALIDATED_INTEGRATED_BASELINE = S0-SL01_AND_SL02 / CLI acceptance pending / commit 1cde21d4d0f95b9b190c02f4a69a91c25485428c
CURRENT_AUTHORITIES = ACTIVE_AUTHORITY_MAP.md; planning/ROADMAP.md; planning/SPRINTS.md; PROJECT_GOVERNANCE_BINDING.json; domain authorities listed in ACTIVE_AUTHORITY_MAP.md
CURRENT_INVARIANTS = incremental canonical-flow integration; at most one active formal activity; readiness != authorization; implementation != integrated; gateway/adapters; pluggable parsers; three sources of truth; physical commit before DOWNLOADED; conditional resume; bounded workers; legitimate access only; CLI frontend-first rule not applicable
OPEN_DECISIONS = NONE for the current continuity checkpoint; future technical decisions remain assigned to the entry conditions in planning/SPRINTS.md
BLOCKERS = SP01-10-CREATE-REPLAY returned native exit 1 with stderr present; cause not retained in sanitized evidence; partial `.venv-replay` remains and must not be reused, removed or retried automatically
KNOWN_RISKS = S0 runtime compatibility remains unverified; future-unit risks and entry gates are in planning/SPRINTS.md and docs/audit/AUDITORIA_TECNICA_2026-10-05.md
DEFERRED_ITEMS = GUI, TDLib and additional support remain deferred; Windows distribution remains S10; other unit-specific items are in planning/SPRINTS.md
IMPLEMENTATION_AUTHORIZATION_STATE = GRANTED_FOR_S0_ONLY / current request explicitly authorizes SP01-10; no authorization for S1
GIT_PUBLICATION_AUTHORIZATION_STATE = NO_STANDING_AUTHORIZATION / ACTIVITY_SPECIFIC_AUTHORIZATION_REQUIRED
NEXT_CONTINUITY_CHECKPOINT = NONE / future Git publication requires activity-specific authorization
PROJECT_GOVERNANCE_BINDING = ACTIVE / VALIDATED / content preserved; JSON parse revalidated; schema PASS is recorded in OPENING_RECOVERY_VALIDATION.json
SAFE_RESUME_POINT = SP01-10 stopped at replay venv creation: initial constraints were generated and validated; `.venv-replay` is partial after native exit 1. Do not reuse/remove it, retry automatically, or rerun SP01-01..09. Preserve the generated constraints and historical SP01-02 attempt/recovery records. Resume only after a new explicit user instruction authorizes failure recovery; reconcile only this state and SP01_STACK_WINDOWS.md, without changing code, tests or the frozen contract. SL03 artifacts in commits 05b2658 and 0ba4fe5 are present but are not verified by recorded evidence. Discover current HEAD, upstream synchronization, and worktree state at runtime; this document does not hard-code a self-referential checkpoint hash.
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
SP01_EXECUTED = YES / SP01-01..09 PASS per later execution facts supplied in the current request; SP01-10 initial inventory and constraints PASS; replay creation FAIL
```

## Factual basis

The continuity package was published in commit
`2be283f04502ff2b6980831cec6445b0b64da102` on `work/s0-bootstrap`. Runtime Git
facts must still be rediscovered when resuming; the package does not hard-code
an exact current HEAD.

An earlier checkpoint recorded a one-time publication authorization, which
was consumed when the package commit was pushed. The earlier validated S0
baseline and SL02 completion remain supported by project records. Commit
history shows SL03 implementation/test artifacts, but there is no evidence
here that their validation passed; `EXECUTED != VERIFIED`.

`ACTIVITY_COMPLETION_PERCENT` measures this continuity-materialization
activity only. S0's 40% is the last documented delivery-unit measure and is
retained because this activity did not verify additional S0 gates.

`ACTIVITY_COMPLETION_PERCENT = 100%` measures the continuity package
materialization and publication: all required canonical artifacts exist, are
reconciled, and the checkpoint commit is
`2be283f04502ff2b6980831cec6445b0b64da102`.

## Continuity and publication boundary

The continuity package checkpoint is published. Verify current branch, HEAD,
upstream synchronization, and worktree from Git at runtime. Any future Git
publication requires activity-specific authorization.
