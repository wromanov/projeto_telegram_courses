# S6 Runtime Isolation and Offline Validation — 2026-10-18

```text
DOCUMENT_ROLE = ACTIVITY_EVIDENCE_REPORT
ACTIVITY = S6_RUNTIME_ISOLATION
PROJECT_ID = projeto_telegram_courses
REPO_ROOT = C:\Users\walac\desenvolvimento\projeto_telegram_courses
BRANCH = work/s0-bootstrap
HEAD = 98d9d6b9ce152b8d2764a4d160fcbdf4722fb257
GIT_STAGE_COMMIT_PUSH = NO / pre-existing dirty and untracked work preserved
RESULT = OFFLINE_LAUNCHER_E2E_PASS / SELECTED_REGRESSION_PASS_WITH_SKIPS / SYMLINK_GATE_BLOCKED
V1_ACTIVE = YES / V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING / SPRINT_CHECKPOINT = DEFERRED
```

## Summary

The native launcher-mediated offline lifecycle test completed successfully in
a fresh isolated root. The selected S5/S6 regression set also passed after
using a shorter pytest `--basetemp`. Two real symlink tests could not create
links under the current non-elevated Windows privileges and remain
`BLOCKED_BY_WINDOWS_PRIVILEGE`; two real-compatibility tests were skipped
because `S6_REAL_EVIDENCE_PATH` was unset. These results do not constitute
formal S6 acceptance.

## Runtime isolation evidence

Both contexts used
`C:\Users\walac\desenvolvimento\projeto_telegram_courses\.venv\Scripts\python.exe`
(CPython 3.14.7, 64-bit AMD64), Windows 11 build 10.0.26200, and identity
`ROMA_CASA\walac`.

In context 1, PowerShell 7.6.5 ran from the repository directory. Codex
sandboxing redirected `LOCALAPPDATA` and `TEMP` below
`C:\Users\walac\AppData\Local\Packages\sandbox.{...}\AC`. The socketpair
probe (PID 41216) and asyncio probe (PID 40288) each timed out after four
seconds; the supervisor terminated them, each exited 1, and stderr was empty.

In context 2, `LOCALAPPDATA` and `TEMP` were standard at
`C:\Users\walac\AppData\Local` and the user's standard temporary directory.
The socketpair probe (PID 41948) passed in 0.159 seconds with exit 0; the
asyncio probe (PID 41232) passed in 0.553 seconds with exit 0. The adjudicated
root cause is an environment-only Codex sandbox restriction. No Python
configuration or source correction was made or indicated by these results.

## Launcher-mediated offline lifecycle

`OfflineE2E` passed using the fresh root
`C:\Users\walac\AppData\Local\Temp\s6-v2-offline-e2e-1352424baf804763bf3be5e353893e1f`:
`1 passed in 12.67s`. The two child processes had PIDs 35680 and 39820 and
distinct execution IDs. Phase 1 produced the controlled 1,048,576-byte prefix
and checkpoint. Phase 2 reread the prefix; the aligned overlap was not
applicable (`N/A`). The synthetic file finalized at 11,649,955 bytes. Both
process reports and decimal timeout receipts matched; SQLite reported
`COMPLETED_V2`, and ledger reconciliation passed.

The isolated launcher test was necessary because the full S5/S6 regression
run's 95-character `basetemp` produced a 248-character final path, exceeding
the 240-character guard. That transient run failed. Architect review
confirmed path length as the cause with high confidence; child PIDs matched,
so this was not a PID mismatch. The authorized retry changed only the
`--basetemp` argument to a 70-character path; no source guard was relaxed.

## Regression and static checks

The selected harness, S5/S6 unit, manual, and integration set completed with
`302 passed, 4 skipped in 101.71s`. The skips were:

- two real-filesystem symlink tests, both blocked by Windows `WinError 1314`
  (`BLOCKED_BY_WINDOWS_PRIVILEGE`);
- two real-compatibility cases because `S6_REAL_EVIDENCE_PATH` was not set.

Ruff for `src tests tools`, `compileall` for `src tests tools`, PowerShell
`ParseFile` for `tools/manual_proofs/Invoke-S6V2Proof.ps1`, common
`OPERATIONAL_ONLY` and controlled `TRUSTED_REFERENCE` DryRuns, and
`git diff --check` passed. The diff check emitted existing CRLF notices; the
whitespace check for the target untracked edits passed.

The root-adjudicated lifecycle fixture correction was limited to the
pre-existing untracked `tests/manual_proofs/test_s6_v2_proof_harness.py`:
`probe=True`, default `loop_policy` retained, and
`S6_V2_TEST_PROBE_TIMEOUT_SECONDS=60`. The timeout receipt was derived from
the applied deadline and compared with that deadline. The adjudication is
recorded in section 5 of
[`S6_V2_OFFLINE_E2E_AND_SYMLINK_GATES_ADDENDUM_2026-10-18.md`](../contracts/S6_V2_OFFLINE_E2E_AND_SYMLINK_GATES_ADDENDUM_2026-10-18.md).

## Safety and current boundary

```text
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
CREDENTIAL_OR_PROTECTED_SESSION_ACCESS = NO
SYNTHETIC_BOOTSTRAP = BLOCKS_CREDENTIALS_AND_NETWORK
ORIGINAL_OPERATIONAL_SQLITE_ACCESS = NO
HISTORICAL_PART_ACCESS = NO
```

No credentials or protected session were accessed; no network or Telegram
calls, real downloads, original operational SQLite access, or historical
`.part` access occurred. No source or launcher change is included in this
report. The offline launcher lifecycle criterion is satisfied. The symlink
security gate remains blocked until both real symlink tests can run with the
current non-elevated privileges; do not elevate or change privileges. If
`WinError 1314` recurs, preserve that blocked classification.

`S6_SYMLINK_SECURITY_GATE` was run and is
`BLOCKED_BY_WINDOWS_PRIVILEGE` (`WinError 1314`). Next action is
`BLOCKER_RESOLUTION`; rerun the gate only when the currently permitted
non-elevated context can create links, without elevating or changing
privileges. Safe resume point: resolve the symlink-creation blocker and rerun
the gate only when that context can create links. Runtime A/B, launcher E2E,
and selected regressions are complete.
V1 remains active, V2 remains ineffective, S6 formal acceptance remains
pending, and the sprint checkpoint remains deferred. Git staging, commit, and
push remain unauthorized and were not performed.
