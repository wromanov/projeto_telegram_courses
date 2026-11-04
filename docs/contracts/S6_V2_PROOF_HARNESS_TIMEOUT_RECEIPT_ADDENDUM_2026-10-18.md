# S6 V2 Proof Harness Timeout Receipt Addendum

```text
CONTRACT_ID = S6_V2_PROOF_HARNESS_TIMEOUT_RECEIPT_ADDENDUM_2026_10_18
DOCUMENT_ROLE = ACTIVITY_SCOPED_CORRECTION_ADDENDUM
STATUS = CLOSED_FOR_BOUNDED_OFFLINE_IMPLEMENTATION
ACTIVITY = S6_V2_PROOF_HARNESS_TIMEOUT_RECEIPT_REMEDIATION
PARENT_CONTRACT = S6_V2_PROOF_HARNESS_CORRECTION_V1
CANONICAL_S5_OR_S6_CONTRACT_CHANGE = NO
```

## 1. Scope and authority

This addendum records the root-adjudicated correction for the timeout receipt
validation failure observed in the authorized S6 V2 proof. It supplements the
parent activity-scoped correction contract only for the behavior stated here;
all other parent-contract requirements and safety invariants remain in force.

Only these files are authorized for this bounded correction:

- `tools/manual_proofs/s6_v2_proof_harness.py`
- `tests/manual_proofs/test_s6_v2_proof_harness.py`
- `docs/contracts/S6_V2_PROOF_HARNESS_TIMEOUT_RECEIPT_ADDENDUM_2026-10-18.md`

No other source, test, contract, report, continuity record, or historical
evidence file is authorized by this addendum.

## 2. Established execution facts

The first real proof process completed phase 1 with observed exit code `0` and
the planned interruption. The phase 1 identity, checkpoint, SQLite, ledger,
and progress evidence gates passed. Its receipt recorded
`timeout_requested_seconds = 3600` and
`timeout_effective_seconds = 899.9471857000001`. Phase 2 did not start.

The proof was classified `INCOMPLETE`. The observed receipt value is a finite
floating-point number produced from a monotonic deadline. The receipt
validator `_phase_receipt_is_acceptable()` currently requires an integer and
rejects that value. This type rejection is the established immediate cause
of phase 2 not starting; it does not invalidate or rewrite the historical
phase 1 evidence.

## 3. Adjudicated correction

The receipt validator shall accept `timeout_effective_seconds` only when it is
a finite positive `int` or `float`, explicitly excluding `bool`, and no greater
than `timeout_requested_seconds`. The requested timeout remains a positive
integer. Reject missing, non-numeric, boolean, non-finite, zero, negative, or
over-request effective values.

This change is limited to receipt validation and regression coverage. Preserve
the existing deadline calculation, timeout values, child termination and
wait behavior, process limits, S5 budgets, request caps, retry/FloodWait
limits, and all other execution behavior. Add offline regression coverage for
the accepted finite floating-point case and rejected invalid/out-of-bound
cases. Do not run this correction against Telegram.

## 4. Prohibited actions and acceptance boundary

- No `Execute`, real-proof retry, network access, or Telegram RPC.
- No secret, credential, protected-session, or message-payload inspection.
- No historical report or evidence alteration, deletion, or replacement.
- No operational SQLite or historical `.part` mutation.
- No Git staging, commit, push, reset, restore, clean, or stash.
- This addendum does not declare the real proof successful or change S6
  formal acceptance or sprint checkpoint status.

The correction is accepted only when its authorized offline regression
coverage passes and the implementation preserves the limits and invariants
above. A future real proof requires separate, specific authorization; this
addendum does not authorize one.
