# S6 V2 Proof Harness Lifecycle Fixture Path Addendum

```text
CONTRACT_ID = S6_V2_PROOF_HARNESS_LIFECYCLE_FIXTURE_PATH_ADDENDUM_2026_10_18
DOCUMENT_ROLE = ACTIVITY_SCOPED_CORRECTION_ADDENDUM
STATUS = CLOSED_FOR_BOUNDED_OFFLINE_TEST_CORRECTION
ACTIVITY = S6_V2_PROOF_HARNESS_LIFECYCLE_FIXTURE_PATH_REMEDIATION
PARENT_CONTRACT = S6_V2_PROOF_HARNESS_CORRECTION_V1
CANONICAL_S5_OR_S6_CONTRACT_CHANGE = NO
RELATED_ADDENDUM = S6_V2_PROOF_HARNESS_TIMEOUT_RECEIPT_ADDENDUM_2026-10-18
```

## 1. Scope and authority

This is a separate, activity-scoped addendum for the offline lifecycle test
failure described below. It does not modify or replace the timeout receipt
addendum. The root adjudication accepts a fixture-only correction.

Only these files are authorized for this correction:

- `tests/manual_proofs/test_s6_v2_proof_harness.py`
- `docs/contracts/S6_V2_PROOF_HARNESS_LIFECYCLE_FIXTURE_PATH_ADDENDUM_2026-10-18.md`

No production source, timeout implementation, product guard, or other
contract is authorized for change.

## 2. Established failure facts

The offline lifecycle test used the default pytest temporary path. Combined
with its synthetic output path, the resulting path was 241 characters. The
intentional product path guard is 240 characters, so the test failed in
`planner.build` before identity validation or download. The observed request
counters were zero. This was a fixture-path failure, not a timeout: the
requested/effective timeout values were integer `90`/`60`.

## 3. Adjudicated fixture-only correction

In the authorized test file, replace its long `tmp_path` root with
`tmp_path_factory.mktemp('s6')`. Use that same short root consistently for
synthetic bootstrap, execution, and assertions. Keep the test offline and
preserve its purpose and assertions.

Do not change the intentional 240-character product guard, timeout code,
production source, or any source contract.

## 4. Prohibited actions and acceptance boundary

- No real proof, Execute, retry, network access, or Telegram RPC.
- No operational or historical artifact mutation.
- No credentials, protected-session, or message-payload inspection.
- No Git staging, commit, push, reset, restore, clean, or stash.
- Do not modify the prior timeout receipt addendum or any other file outside
  the two-file authorization above.

Acceptance is limited to the authorized offline lifecycle regression passing
with the short fixture root while the product guard and timeout behavior stay
unchanged. This addendum does not authorize another real proof or declare S6
formal acceptance.
