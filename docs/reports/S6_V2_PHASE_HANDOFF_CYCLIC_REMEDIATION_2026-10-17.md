# S6 V2 phase handoff cyclic remediation — 2026-10-17

```text
ACTIVITY = S6_V2_PHASE_HANDOFF_CYCLIC_REMEDIATION
RESULT = PASS / OFFLINE SYNTHETIC TWO-PROCESS GATE
CORRECTION_CYCLES = 4 / 4
TWO_PROCESS_HANDOFF_GATE = PASS / SYNTHETIC OFFLINE ONLY
REAL_TELEGRAM_PROOF = NOT_RUN / PRIOR REAL PROOF REMAINS INCOMPLETE
V1_ACTIVE = YES
V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_ADVANCEMENT = NOT_AUTHORIZED / NOT_PERFORMED
GIT_MUTATION = NONE
```

## Scope and authority

The user authorized four bounded offline correction cycles for the S6 V2 phase
handoff harness and its tests. The activity-specific contract was
`docs/contracts/S6_V2_PHASE_HANDOFF_CORRECTION_CONTRACT.md`. Work remained
limited to `tools/manual_proofs/s6_v2_proof_harness.py` and
`tests/manual_proofs/test_s6_v2_proof_harness.py`. No canonical S5/S6 contract,
downloader, gateway, launcher, or historical proof evidence was changed. The
earlier incomplete real proof root and report remain preserved.

The final end-to-end test used the real harness lifecycle and two Python child
processes, but installed a synthetic gateway and credentials stub from the
test-only child bootstrap. The bootstrap blocks nonlocal sockets, operational
SQLite paths, and historical `.part` access. This is offline synthetic
evidence, not a new Telegram proof or S6 formal acceptance.

## Corrections by cycle

1. **JSON and phase-1 receipt:** recursively normalize tuples to JSON arrays at
   the serialization boundary while rejecting unsupported JSON values; add
   the phase-1 prefix SHA-256; preserve and compare child-declared and observed
   process exit codes, failing closed on disagreement.
2. **SQLite URI guard:** normalize Windows `file:` URIs before containment
   checks, allow only local authorities, reject fragments and path escapes,
   and preserve the original `sqlite3.connect` arguments when an allowed path
   is delegated.
3. **Incomplete aggregation:** reject invalid counters; preserve available
   ledger counts while representing missing aggregate totals as `null`; save
   the incomplete report, preserve the original stop, release the lock, and
   return failure rather than raising during aggregation.
4. **Phase-2 final path:** replace the nonexistent
   `DownloadCandidate.relative_path` access with persisted
   `DownloadRecord.final_path`. Require `COMPLETED_V2`, an absolute existing
   regular file, a safe downloads root, and strict resolved containment before
   hashing or reading it.

## Final offline proof evidence

The native Windows runtime completed the synthetic E2E through the actual
harness lifecycle. Its aggregate report records `result=PASS` and
`two_process_proof=PASS`:

| Gate evidence | Observed result |
|---|---|
| Phase 1 / phase 2 | Distinct PIDs `46440` / `13224` and distinct execution IDs; phase 1 ended before phase 2 started |
| Process exits | Child and supervisor both observed exit 0 for both phases |
| Phase 1 stop | `CONTROLLED_INTERRUPT` at exactly 1,048,576 bytes; physical prefix, SQLite checkpoint, and SHA-256 agreed |
| Handoff | Phase 2 reopened the same proof SQLite and persistent budget ledger; prefix reread began at offset 0 and continuation at 1,048,576 |
| Completion | `COMPLETED_V2`; final file size 11,649,955 bytes; physical file, SQLite, versioned evidence, and final SHA-256 agreed |
| Budget | Ledger stayed within request and payload caps; uncertain bytes remained zero |
| V2 scope | V2 activation was restored after both child calls; V1 remained active and operational V2 remained ineffective |
| Isolation | Synthetic bootstrap observed two synthetic gateway installs and credential blocks, with no network attempt, operational SQLite access, or historical `.part` access |
| Negative gate | Invalid phase-1 evidence prevented any phase-2 child from starting |

The retained test artifact is
`.t/test_two_process_handoff_real_0/s6-v2-real-proof-abb7c25eb4964ddd96e2d9cd798c8baa/`.
It contains the aggregate report and both child reports and supervisor
receipts. The earlier 15-second sandbox attempt timed out before a phase-1
child report existed; it was not counted as a pass. The native rerun above
passed.

## Validation

| Check | Result |
|---|---|
| Complete harness test file | PASS — 50 passed, 1 skipped |
| Pertinent S5/S6 regression set | PASS — 231 passed, 3 skipped |
| Ruff (`src tests tools`) | PASS |
| `compileall` (`src tests tools`) | PASS |
| PowerShell parser for `Invoke-S6V2Proof.ps1` | PASS |
| DryRun `common / OPERATIONAL_ONLY` | PASS |
| DryRun `controlled / TRUSTED_REFERENCE` | PASS |
| `git diff --check` | PASS — line-ending conversion notices only on pre-existing tracked worktree files |
| Whitespace check of the two untracked authorized source files | PASS — `git diff --no-index --check` reported only the expected untracked-file difference status, with no whitespace errors |

Skips were the symlink escape case, unavailable because Windows returned
`WinError 1314`, and two legacy real-evidence tests requiring
`S6_REAL_EVIDENCE_PATH`. These were reported as skips, not passes. Both
DryRuns reported zero Telegram calls, no operational SQLite access, and no
historical `.part` access.

## Final state

The offline synthetic two-process handoff gate passes. The prior
`S6_V2_COMMON_ALIGNED_REPROOF` remains an incomplete real proof that stopped
after phase 1; it was not resumed or repeated. V1 remains active, V2 remains
ineffective, S6 formal acceptance remains pending, and the sprint checkpoint
remains deferred. Any future real proof, V2 adoption, formal acceptance, or
Git publication requires its own authority. No files were staged, committed,
or pushed; pre-existing dirty work was preserved.

```text
G01_G16 = PASS / OFFLINE SYNTHETIC HARNESS GATE
S6_V2_OFFLINE_HANDOFF = PASS
PRIOR_REAL_PROOF = INCOMPLETE / PHASE 1 ONLY / PRESERVED
REAL_TELEGRAM_CALLS_THIS_ACTIVITY = 0
OPERATIONAL_SQLITE_OR_HISTORICAL_PART_ACCESS = NO
V1_ACTIVE = YES / V2_EFFECTIVE = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_ADVANCEMENT = NOT_AUTHORIZED / NOT_PERFORMED
GIT_ADD_COMMIT_PUSH = NO
SAFE_RESUME_POINT = Human review of the offline result. Do not perform a real proof, adopt V2, accept S6, advance the sprint, or publish Git without separate explicit authorization.
```
