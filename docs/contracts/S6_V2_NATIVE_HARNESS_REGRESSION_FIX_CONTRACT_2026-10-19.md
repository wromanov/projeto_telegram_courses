# S6 V2 native harness regression fix contract — 2026-10-19

```text
DOCUMENT_ROLE = ACTIVITY_SCOPED_TECHNICAL_CONTRACT
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_V2_NATIVE_HARNESS_REGRESSION_FIX
SCOPE = OFFLINE_RUNNER_LAUNCHER_AND_RUNNER_TESTS_ONLY
AUTHORITY = ROOT_ADJUDICATED_ACTIVITY_CONTRACT
CANONICAL_AUTHORITY = NO
IMPLEMENTATION_AUTHORIZATION = BOUNDED_TO_LISTED_FILES
HARNESS_TEST_CHANGES = DEFERRED / REQUIRE_SEPARATE_ROOT_APPROVAL
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_PROOF_EXECUTION = NO
V1_ACTIVE = YES
V2_EFFECTIVE = NO
```

## Purpose and boundary

This contract records the root's adjudication and bounds a correction to the
offline S6 V2 regression runner's temporary-path allocation. The activity may
change only:

- `tools/manual_proofs/Invoke-S6V2OfflineRegression.ps1`
- `tools/manual_proofs/s6_v2_offline_regression_runner.py`
- `tests/manual_proofs/test_s6_v2_offline_regression_runner.py`

Harness functional tests may be changed only after a separate approval by the
Root. Changes to `downloads.py`, downloader behavior, S6/V2 functionality,
proof-harness behavior, V1, or V2 activation are outside this authorization.
This contract does not authorize any Telegram call, download, credential
access, proof execution, environment substitution, Git staging, commit, or
push.

This is activity-scoped guidance. It does not modify or supersede canonical
product requirements, architecture, S6 contracts, or project continuity
authorities. For this runner-path correction, it records the root-adjudicated
80-character `basetemp` constraint and the layout below; the older
activity-scoped offline runner contract's 220-character path limit is not the
constraint for this correction.

## Adjudicated findings and evidence limits

### Finding A — confirmed

The observed pytest `basetemp` path is 105 characters. With the tested path
suffixes, nine derived paths are 241–256 characters, exceeding the 240-character
guard. The root adjudicated this path-length mismatch as confirmed.

### Finding B — probable, high confidence

The same path rejection is the probable cause of the controlled regression
failure: the path is rejected in `planner.build` before `queue.run`. The
bootstrap, seed, restore, and imports were observed to complete. The initial
`DownloadError` was sanitized to `OTHER`, so there is no direct traceback
proving the causal chain. Record this as `PROBABLE / HIGH`, not as a confirmed
root cause.

The missing `attempts` field and proof-record count mismatch are not established
as primary causes. Their presence must not be used to overstate the evidence or
to expand this correction into harness functionality.

### References and provenance

- Root adjudication for this activity, supplied to the SCRIBE stage, is the
  source of the 105-character observation, nine derived paths, 241–256 range,
  and the `planner.build` versus `queue.run` classification.
- [S6 V2 final regression gate](../reports/S6_V2_FINAL_REGRESSION_GATE_2026-10-19.md)
  records the earlier intermittent `KeyError: attempts` and states that its
  run-level evidence did not establish its cause.
- [Offline runner invocation correction](../reports/S6_V2_OFFLINE_REGRESSION_RUNNER_INVOCATION_2026-10-19.md)
  records that the sandbox admission signature blocked post-change collection
  and prohibits environment-substitution relaunch under that activity.
- [Prior offline runner contract](S6_V2_OFFLINE_REGRESSION_RUNNER_CONTRACT_2026-10-19.md)
  records the runner's existing admission, supervision, and outcome-classification
  context. Its prior path-length requirement does not replace the tighter
  adjudicated constraint in this correction.

No new measurement or execution is claimed by this contract.

## Required path allocation and invariants

Allocate each invocation under:

```text
<repo>/.s6r/<12-character-token>/t
```

The pytest `basetemp` path must be no longer than 80 characters. The longest
observed derived `.part` path under the approved layout is 231 characters. Do
not infer that every possible consumer accepts paths of that length; the
contracted bound addresses the observed runner path set and the 240-character
guard involved in Finding A.

The allocator and runner must enforce these invariants:

1. Allocate the token directory with exclusive creation. On collision, choose
   a different token and retry allocation; never reuse, attach to, or overwrite
   a pre-existing invocation directory.
2. Keep `basetemp`, receipts, logs, and other invocation artifacts contained
   under the allocated invocation root after path resolution. Reject paths that
   escape the repository-owned `.s6r` root.
3. Reject symlink or Windows reparse-point redirection for the allocation root
   and relevant path components. Do not follow a redirected path as if it were
   an owned invocation directory.
4. Preserve the full run ID in the receipt and retained history. The 12-character
   directory token is an allocation component and must not truncate the full
   run ID recorded for traceability.
5. Preserve historical artifacts. Do not perform destructive cleanup or delete
   pre-existing invocation roots. If cleanup is implemented, it may target only
   a verified, current-invocation-owned root after containment and ownership
   checks; it must never select a historical or pre-existing root. Cleanup is
   optional and is not required to satisfy this contract.
6. Preserve the current sandbox admission behavior. If the sandbox signature
   is present, return the existing blocked outcome without relaunching under a
   substituted environment. Do not alter `TEMP`, `LOCALAPPDATA`, or other
   inherited environment values to bypass admission.
7. Keep execution offline and synthetic. The runner and its tests must not call
   Telegram, access credentials, download real media, or enter proof execution.

## Authorized implementation and test scope

Within the three listed files, implementation may add or adjust only the
runner allocation, launcher plumbing needed to pass/use that allocation, and
runner infrastructure regression coverage for the invariants above. Tests
should cover the short `basetemp` bound, the observed maximum derived path,
exclusive creation and collision retry, non-reuse, resolved containment,
symlink/reparse rejection, full run-ID retention, historical-artifact
preservation, and unchanged sandbox admission behavior.

The runner's own infrastructure tests may validate path construction and
failure handling with temporary fixtures. They are not substitutes for the
full harness functional regression. Do not edit harness tests in this activity
unless the Root separately approves that scope.

## Gates and result states

Report each gate using only evidence obtained for this activity:

| Gate | PASS condition | FAIL / BLOCKED condition |
|---|---|---|
| Change boundary | Diff is confined to the three authorized files | Any out-of-scope file or behavior change is present: `FAIL` and stop affected scope |
| Allocation | Exclusive fresh allocation satisfies the 80-character `basetemp` limit and derived-path bound | Collision reuse, excess length, or unsafe path resolution: `FAIL` |
| Containment and redirection | Resolved artifacts remain inside the allocated `.s6r` root; symlink/reparse redirection is rejected | Escape, redirection acceptance, or unverified ownership: `FAIL` |
| History and identity | Receipt retains the full run ID; historical artifacts are preserved | Truncated identity, overwrite, or historical deletion: `FAIL` |
| Sandbox admission | Existing environment admission blocks without relaunch or environment substitution | Admission bypass or environment mutation: `FAIL` |
| Offline runner infrastructure tests | Authorized runner tests exercise the invariants and pass | Assertion failure: `FAIL`; sandbox admission prevents a permitted run: `BLOCKED` |
| Native full harness profile | Separately authorized native Windows execution completes the complete selected profile with valid artifacts, exit status zero, and no skip/xfail | Test failures: `FAIL`; timeout with confirmed process-tree exit: `INCOMPLETE`; unconfirmed exit or admission/setup block: `BLOCKED`; missing or contradictory evidence: `INCOMPLETE` |

The complete native harness profile requires a separate, explicit user
authorization and a native Windows execution context that passes admission.
This contract alone does not authorize that execution. Do not relaunch by
changing the environment. A prior test result, static inspection, or runner
infrastructure test cannot be reported as a current full-harness `PASS`.

For the full harness profile, `PASS` additionally requires a valid receipt,
collection/JUnit evidence consistent with process output, confirmed normal
supervisor completion, and zero skips and xfails. A skip or xfail is never
`PASS`. Missing evidence remains missing and cannot be synthesized from a
partial log or later process-list observation.

## Risks and limitations

- Finding B remains inferential until a permitted run or direct diagnostic
  evidence establishes the causal chain. Sanitized `DownloadError=OTHER` does
  not prove the path rejection caused the observed application-level result.
- The 231-character `.part` observation is bounded to the adjudicated derived
  paths. Other Windows APIs or unobserved suffixes may impose additional path
  constraints; this contract makes no broader platform guarantee.
- A blocked sandbox admission leaves the native functional profile unverified.
  The environment must not be altered to convert that blocked result into a
  pass.
- Runner tests establish runner-infrastructure behavior only. They do not
  establish S6 V2 harness functionality, proof readiness, formal S6 acceptance,
  or V2 effectiveness.

## Closure criteria and current status

This activity's implementation may be reported complete only when the change
boundary, allocation, containment/redirection, history/identity, sandbox, and
authorized runner infrastructure-test gates have evidence-backed results and
no unresolved violation. Do not claim any test, parse, or execution result
without a corresponding observed artifact or command result.

The full native harness profile remains a separate user-authorized gate. Until
that gate is completed, report its state as `NOT_RUN`, `BLOCKED`, or
`INCOMPLETE` according to the observed condition; do not infer `PASS` from
runner-infrastructure validation. This contract records no implementation or
test execution.

```text
FINDING_A = CONFIRMED / 105-CHAR BASETEMP / 9 DERIVED PATHS / 241-256 > 240
FINDING_B = PROBABLE_HIGH / REJECTION BEFORE QUEUE / NO DIRECT TRACEBACK
RUNNER_PATH = <repo>/.s6r/<12-CHAR-TOKEN>/t
BASETEMP_MAX = 80 CHARACTERS
OBSERVED_MAX_DERIVED_PART_PATH = 231 CHARACTERS
SANDBOX_ADMISSION = PRESERVE / NO ENVIRONMENT-SUBSTITUTION RELAUNCH
NATIVE_FULL_HARNESS = SEPARATE EXPLICIT USER AUTHORIZATION REQUIRED
CONTRACT_EXECUTION_EVIDENCE = NONE
```
