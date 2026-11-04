# S6 Symlink Gate Final Validation — 2026-10-18

```text
DOCUMENT_ROLE = ACTIVITY_EVIDENCE_REPORT
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_SYMLINK_GATE_FINAL_VALIDATION
RESULT = OFFLINE_ACCEPTANCE_PASS
EXECUTION_CONTEXT = WINDOWS_NATIVE / ROMA_CASA\walac / NON_ELEVATED
WINDOWS_BUILD = 26200
PYTHON = C:\Users\walac\desenvolvimento\projeto_telegram_courses\.venv\Scripts\python.exe / CPython 3.14.7 / 64-bit
DEVELOPER_MODE = ENABLED / AllowDevelopmentWithoutDevLicense=1
SYMLINK_PRIVILEGE = ABSENT_FROM_PROCESS_TOKEN
SYMLINK_EVALUATION = LOCAL_TO_LOCAL ENABLED / LOCAL_TO_REMOTE ENABLED / REMOTE_TO_LOCAL DISABLED / REMOTE_TO_REMOTE DISABLED
CAPABILITY_PROBE = PASS / native file symlink created, target and sentinel verified, link and isolated directory cleaned
REAL_SYMLINK_TEST_1 = PASS / test_resolve_completed_final_path_rejects_symlink_escape
REAL_SYMLINK_TEST_2 = PASS / test_interrupted_planned_final_path_rejects_real_symlink_when_creation_is_available
REAL_SYMLINK_TESTS = 2 passed in 0.36s / no skips
REGRESSION = PASS / tests/manual_proofs/test_s6_v2_proof_harness.py + tests/unit/test_s6_v2.py + tests/unit/test_s6_bounded_target_gateway.py / 166 passed in 81.98s / no failures
TEST_ARTIFACT_CLEANUP = PASS / test-owned external symlinks removed by test assertions; pytest fixture symlinks/junction removed only after no-follow target inspection; isolated roots removed
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
OPERATIONAL_SQLITE_ACCESS = NO
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_OFFLINE_ACCEPTANCE = PASS
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
GIT_ADD_COMMIT_PUSH = NO
PROJECT_STATE_RECONCILIATION = PASS
```

## Result

The probe and both real-filesystem symlink tests ran in the standard Windows
profile as the authorized non-elevated user. The probe verified that the link
resolved to its intended in-root sentinel and that cleanup removed only the
test link and sentinel. Both security tests created actual links to external
sentinels, verified rejection of the escaped destination and preservation of
the sentinel bytes, and asserted cleanup of the link created by each test.

The directly affected offline regression set passed: the S6 V2 proof harness,
S6 V2 unit tests, and bounded-target gateway unit tests (166 passed). The
separately recorded launcher-mediated synthetic two-process offline E2E also
remains PASS. Together these satisfy the offline gates for this validation;
they do not constitute formal S6 acceptance or authorize a real Telegram
proof, V2 adoption, or sprint advancement.

The pytest basetemp left one temporary fixture junction pointing to a sibling
fixture directory within its own isolated root. It was inspected without
following the junction, removed by its link path, and the root was deleted
after verifying no reparse points remained. No source code, Windows policy,
privilege assignment, or operational artifact was changed.
