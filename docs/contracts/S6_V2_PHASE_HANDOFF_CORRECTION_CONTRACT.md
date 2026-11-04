# S6 V2 Phase Handoff Correction Contract

```text
CONTRACT_ID = S6_V2_PHASE_HANDOFF_CORRECTION_V1
DOCUMENT_ROLE = ACTIVITY_SCOPED_CORRECTION_CONTRACT
STATUS = ROOT_ADJUDICATED / IMPLEMENTATION_AUTHORIZED
ACTIVITY = S6_V2_PHASE_HANDOFF_CYCLIC_REMEDIATION
CANONICAL_S5_OR_S6_CONTRACT_CHANGE = NO
```

## 1. Authority and boundary

This contract authorizes the bounded offline correction of the S6 V2 isolated
proof harness and its tests. It does not replace or amend the approved/frozen
S5 or S6 V1 contracts, or the S6 V2 design authority. V1 remains active and
V2 remains ineffective outside the isolated proof child.

The existing incomplete proof root and historical evidence are immutable
inputs for diagnosis only. Do not retry or resume that proof. No Telegram calls,
real downloads, operational SQLite or historical `.part` access, global V2
activation, sprint checkpoint, S6 formal acceptance, or Git mutation is
authorized.

Implementation ownership is assigned to `mechanical_implementer` for:

- `tools/manual_proofs/s6_v2_proof_harness.py`
- `tests/manual_proofs/test_s6_v2_proof_harness.py`

`tools/manual_proofs/Invoke-S6V2Proof.ps1` is outside the implementation scope
unless a reproduced harness integration defect proves a change necessary; any
such finding must return to Root for adjudication first. Root owns validation,
regression, integration, final documentation, and acceptance decision.

Preserve all unrelated and pre-existing worktree changes. Do not edit product
downloader/gateway code, S5/S6 canonical contracts, governance/continuity
authorities before final reconciliation, or any historical proof evidence.

## 2. Adjudicated diagnosis

The following findings are confirmed by source inspection and the preserved
phase receipts in `S6_V2_COMMON_ALIGNED_REPROOF_2026-10-17.md`:

1. `_atomic_write_json` compares the JSON-decoded publication with the original
   Python object. `QueueResult.outcomes` contains nested tuples; JSON decodes
   them as lists, so the equality check fails after publication. The child
   report declares exit 0, then `_child_main` returns 5 after the writer error.
2. The phase 1 result includes `prefix_bytes` but omits `prefix_sha256`. The
   supervisor independently hashes the physical `.part` and requires the
   child digest to match, so it correctly refuses to confirm the checkpoint.
3. The supervisor observes the actual exit code, but the nonzero-exit path
   obscures the discrepancy with the child's separately declared exit code.
   Preserve both values and report disagreement explicitly; do not accept an
   exit 5 as a planned controlled interruption.

The historical proof observed PID 30596, child-declared exit 0, supervisor
observed exit 5, and a 1,048,576-byte checkpoint with SHA-256
`dee6ef9f3ed4b021b55cefb90d9f03cfbc958cc1dbb6d00238b2a7576ae72a95`. Phase 2
did not start. The original evidence remains preserved and must not be changed.

No root cause was found in the PowerShell launcher. The prior correction
contract and report remain historical records; this contract addresses the
new findings and stricter two-process acceptance requirement.

## 3. Required corrections

### A. JSON boundary

- Normalize tuples recursively to JSON arrays at the serialization boundary,
  preserving order and scalar values.
- Validate object keys and supported JSON values; retain strict serialization
  (`allow_nan=False`) and reject unsupported values rather than coercing with
  `str()` or another lossy default.
- Compare the re-read publication to its normalized representation.
- Preserve same-directory exclusive temporary creation, flush/fsync, atomic
  replace, read-back validation, and fail-closed behavior on write errors.

### B. Prefix evidence

- Compute SHA-256 from the isolated phase 1 `.part` after verifying its exact
  configured size.
- Persist `prefix_sha256` in the phase 1 child result.
- Keep the supervisor's independent physical hash and SQLite checkpoint
  validation. Missing, malformed, or mismatched digest must block phase 2.

### C. Process exits and phase gates

- Keep the child's declared exit code distinct from the supervisor-observed
  subprocess exit code; include both in the supervisor receipt.
- Detect and report any mismatch, including when the observed exit is nonzero.
- A successful planned phase 1 stop is valid only when the child declares and
  the supervisor observes exit 0, the child report validates, stop is
  `CONTROLLED_INTERRUPT`, and independent checkpoint/ledger gates pass.
- Any writer failure, crash, nonzero observed exit, exit mismatch, or
  incomplete evidence fails closed and prevents phase 2 from starting.
- Preserve existing S5 request/reservation ceilings, process identity checks,
  PID/time observations, prefix recovery, overlap checks, and V2 restoration.

## 4. Required end-to-end acceptance

The principal gate is `S6_V2_TWO_PROCESS_HANDOFF_READY`. It must be exercised
offline through the real harness lifecycle using two distinct Python child
processes, a synthetic gateway installed only by test bootstrap, isolated
directories, proof SQLite, and the persistent proof budget ledger. Do not
replace this gate with unit tests or synthetic child scripts that bypass the
harness phase lifecycle.

All of the following must pass:

| ID | Required result |
|---|---|
| G01 | Two independent real child processes with distinct execution IDs and positive, distinct PIDs. |
| G02 | Phase 1 observed exit completes before phase 2 starts; actual start/end observations are persisted. |
| G03 | Phase 1 stops deliberately at the configured prefix with `CONTROLLED_INTERRUPT` and consistent child/observed exit 0. |
| G04 | Each child result and supervisor receipt is strict, valid JSON, durably persisted, and independently reconciled. |
| G05 | Phase 1 physical `.part`, SQLite state/bytes, and independently verified prefix SHA-256 agree. |
| G06 | Phase 2 starts only after all phase 1 report, checkpoint, process-exit, and ledger gates pass. |
| G07 | The second process reopens the same proof SQLite and ledger and recovers the checkpoint. |
| G08 | Prefix reread and overlap evidence are checked against expected content. |
| G09 | Phase 2 individual child result and supervisor receipt validate and reconcile. |
| G10 | Aggregate report reconciles both phases, SQLite/evidence, physical files, and ledger deltas. |
| G11 | The completed synthetic proof reaches aggregate `TWO_PROCESS_PROOF=PASS` only with all required evidence. |
| G12 | Missing, corrupt, stale, mismatched digest, exit mismatch, or incomplete evidence is rejected and never yields PASS. |
| G13 | Negative phase 1 evidence prevents any phase 2 process from starting. |
| G14 | S5 request and payload budgets remain within their existing caps and are not reset between processes. |
| G15 | Scoped V2 activation is restored; V1 remains active and operational V2 remains ineffective. |
| G16 | Test bootstrap proves zero Telegram calls, zero downloads, and no access to operational SQLite or historical `.part` files. |

No synthetic test gateway, offline override, or test-only switch may be added
to production runtime behavior merely to satisfy this gate.

## 5. Bounded cyclic process

Maximum correction cycles: four. Each cycle addresses one material finding:
Root records a reproducible result, diagnostic analyst reviews only the new
finding, Root adjudicates a bounded correction, and the implementer changes
only the authorized files. Root runs the targeted tests and integration checks
before deciding whether another cycle is needed.

Stop at complete gate pass, four cycles, a required canonical contract change,
a required out-of-scope change, or a safety/material environment blocker. Do
not start a fifth cycle automatically. Do not repeat a real proof.

## 6. Root validation and final regression

After the main gate passes, Root runs the pertinent S5/S6 regression suite and
the requested checks: pytest, Ruff, compileall, PowerShell parser, DryRun, and
`git diff --check`. Report PASS, FAIL, SKIPPED, and BLOCKED separately. An
environment-blocked check is not a pass. Tests must use isolated temporary
roots; use a Windows runtime with functional local sockets when asyncio
subprocess validation requires it.

## 7. Root adjudication

The read-only diagnostic analyst confirmed the three failure causes and found
no required canonical contract change. Root adjudicates the bounded proposal
as **ACCEPTED**. Implementation is authorized only within Section 1. The
explicit current user authorization supersedes the prior project-state entry
that awaited permission for offline correction; it does not authorize a new
real Telegram proof, V2 adoption, formal acceptance, sprint advancement, or
Git publication.

```text
ROOT_CAUSE_A = CONFIRMED / JSON tuple-list mismatch
ROOT_CAUSE_B = CONFIRMED / phase 1 prefix digest omitted
ROOT_CAUSE_C = CONFIRMED / declared/observed exit discrepancy obscured
CANONICAL_CONTRACT_CHANGE = NO
IMPLEMENTATION_OWNER = MECHANICAL_IMPLEMENTER / harness and tests only
ROOT_OWNS = VALIDATION / INTEGRATION / DOCUMENTATION / FINAL DECISION
```
