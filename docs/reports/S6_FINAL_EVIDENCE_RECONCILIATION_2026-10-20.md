# S6 final evidence reconciliation and acceptance recommendation — 2026-10-20

```text
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_FINAL_EVIDENCE_RECONCILIATION
EXECUTION_MODE = DIRECT
RESULT = EVIDENCE_RECONCILED / S6_REMAINS_OPEN
S6_FORMAL_ACCEPTANCE = PENDING
V1_ACTIVE = YES
V2_GLOBAL = OFF
GIT_ADD_COMMIT_PUSH = NO
```

## Scope and sources

This report reconciles existing evidence only. No test, proof, Telegram call,
real download, executor, or runner was started. The preserved receipts and
historical reports were read without modifying them. No application, harness,
test, or runner file was changed.

Sources reviewed: current `PROJECT_STATE.md`, `CONTINUITY_RECORD.md` and
`handoff/LAST_HANDOFF.md`; the latest native regression report; preserved roots
`.s6r/e5fca75a3aa7/` and `.s6r/bcb2a1158934/`; the frozen S6 V1 contract;
`APPROVALS_AND_DECISIONS.md`; the historical aligned and nonaligned common
proof reports; the trusted-reference preflight report; and the S6 stabilization
report.

## Offline regression reconciliation

| Evidence | Focused | Full Harness |
|---|---:|---:|
| Preserved root | `.s6r/e5fca75a3aa7/` | `.s6r/bcb2a1158934/` |
| JUnit | 12 cases; 0 failures, errors, skips | 196 cases; 0 failures, errors, skips |
| stdout | `12 passed in 41.46s` | `196 passed in 78.60s` |
| Worker metadata | No `worker-result.json`; termination metadata unavailable | `profile=Harness`, `exit_code=0`, `termination_confirmed=true`, `xfail=0`, `xpass=0` |
| Node IDs | Not persisted as worker metadata | 196 collected and 196 executed; exact equality |
| stderr | Empty | Empty |
| Source snapshot | Matches current test and harness files | Matches current test and harness files |
| Process-exit receipt | `exit_code=null` | Outer `exit_code=null`; worker result separately records zero |

Both receipts record the same source snapshot SHA-256 values, and read-only
hashing confirmed the current files still match:

```text
tests/manual_proofs/test_s6_v2_proof_harness.py
FD9959C190D59DC2079DBA21766ED14FD95F189C7830C07E7B3A0FD841FFF6EC
tools/manual_proofs/s6_v2_proof_harness.py
11132B2EC6EC9D3DCCCD07536E0834342B8F1432520FA744E5E0C961F1736197
```

### External process exit-code adjudication

```text
EXTERNAL_EXIT = NOT_PERSISTED
```

Both `native-execution-receipt.json` files and both
`execution-reconciliation.json` files leave the outer process exit value null.
The full Harness `worker-result.json` independently supports the child worker
(PID 18636, exit 0, termination confirmed); it does not establish the outer
PowerShell-launched process exit. The available PowerShell transcript records
the procedure and its check, but does not persist an evaluated, independent
outer exit value. The focused root has JUnit and stdout but no worker metadata
file. No existing independent record proves external exit zero, and no record
contradicts the worker's zero exit.

This is an evidence gap, not evidence of a nonzero test result. The strict
native process gate remains `PARTIAL`. No value is inferred from JUnit,
stdout, or the worker exit code.

## Existing proof reconciliation

### OPERATIONAL_ONLY_PROOFS

- **Aligned common proof**, `S6_V2_COMMON_ALIGNED_REAL_PROOF_2026-10-18.md`:
  reports `PASS`; phase 1 was intentionally interrupted at 1,048,576 bytes,
  phase 2 resumed and completed 11,649,955 bytes in `COMPLETED_V2`. Aligned
  overlap was not applicable.
- **Nonaligned common proof**, `S6_V2_COMMON_NONALIGNED_REAL_PROOF_2026-10-18.md`:
  reports `PASS`; it resumed from 1,048,699 bytes, verified a 123-byte overlap,
  continued without a duplicate, and completed 11,649,955 bytes in
  `COMPLETED_V2`.
- Both reconcile their operational receipts, persistence and budgets. Both
  explicitly classify origin integrity as `UNVERIFIED_ORIGIN`; remote hash
  coverage at EOF is not verifiable. They support the recorded operational
  scenarios, not trusted-origin integrity or full S6 acceptance.

### TRUSTED_REFERENCE_PROOF

The historical `S6_V2_TRUSTED_REFERENCE_REAL_REPROOF_01_PREFLIGHT` result is
`BLOCKED` before launcher confirmation and before Telegram. The launcher did
not surface effective process timeout, aggregate deadline, heartbeat and
termination grace before the required confirmation. The operator never
entered that confirmation. The reference was read-only fingerprinted during
preflight; there was no proof child process, Telegram RPC, remote identity
validation, or download. This is an interrupted preflight, not a failed
integrity comparison and not a completed proof.

No approved exception waiving the mandatory trusted-reference criterion was
found in the canonical decision record. The older stabilization report's
`REAL_PROOF_GATE = PASS_WITH_EXCEPTION` retains the operational-only proofs and
records that no trusted-reference retry would occur in that activity; it is
not a user-approved waiver of the frozen contract. Governance continues to
record `S6_FORMAL_ACCEPTANCE = PENDING`.

### OFFLINE_SYNTHETIC_EVIDENCE

The preserved full Harness JUnit includes the synthetic two-process
trusted-reference E2E and related offline fail-closed checks; that run passed.
Historical offline homologation also reports synthetic trusted-reference
coverage. These records support offline behavior and safety properties; they
do not establish actual Telegram identity, remote hash availability or
coverage, or real trusted-reference operation.

### Contract criteria supported by historical evidence

The historical records support these criteria only within their recorded
scenarios:

| Contract criterion | Existing evidence | Reconciled result |
|---|---|---|
| Resume after interruption / persistence after restart | Both real common proofs record a phase-1 interruption/checkpoint followed by phase-2 continuation and completion. | `SATISFIED FOR RECORDED OPERATIONAL SCENARIOS` |
| Remote identity | Common proof reports record the selected channel/message/document identity and expected media size before streaming. | `SATISFIED FOR RECORDED TARGETS`; no trusted-reference reproof. |
| Aligned physical offset | Aligned common proof completed from its aligned checkpoint. | `SATISFIED FOR RECORDED ALIGNED SCENARIO` |
| Nonaligned physical offset | Nonaligned proof records checkpoint 1,048,699 bytes and comparison of the 123-byte overlap before continuation. | `SATISFIED FOR RECORDED NONALIGNED SCENARIO` |
| Local final size and SHA-256 | Both common proofs report the 11,649,955-byte completed file and reconciled local digest/receipts. | `SATISFIED AS LOCAL RESULT`; independent trusted-reference equality remains unproven. |
| Runtime request/byte budgets | Both common reports reconcile observed counters against their effective and approved caps. | `SATISFIED FOR RECORDED PROOF RUNS` |
| Full remote prefix integrity `[0,P)` | Common proofs explicitly retain `UNVERIFIED_ORIGIN`; EOF coverage is reported unverifiable. | `NOT SATISFIED` |
| Final file byte-identical to an independently fingerprinted reference | No completed trusted-reference real proof; offline synthetic equality is not evidence from Telegram. | `NOT SATISFIED` |
| Duplicate suppression on a later execution; full crash-window matrix; real memory measurement | These outcomes are not established by the two historical common proof reports. Offline Harness cases cover synthetic behaviors only. | `NOT ESTABLISHED BY HISTORICAL REAL PROOFS` |

The 196-case offline Harness passing supports its checked offline and
synthetic assertions, including the synthetic trusted-reference lifecycle.
It cannot convert any row explicitly requiring `REAL_TELEGRAM_TECHNICAL_PROOF`
into a real-service PASS.

## Acceptance matrix

| Gate | Requirement | Actual evidence | Status | Remaining exception and risk | User approval required? |
|---|---|---|---|---|---|
| `GATE_1_OFFLINE_FUNCTIONAL` | Focused regression and full offline Harness pass with consistent case evidence. | Focused JUnit 12/12; full JUnit 196/196; no failures/errors/skips; full worker metadata and node IDs agree; source snapshots match. | `PASS` | None identified in these preserved runs. | Formal S6 acceptance still belongs to the user. |
| `GATE_2_NATIVE_PROCESS_EVIDENCE` | Persist an independently reconcilable native process exit and termination record. | Full worker exit 0 and termination confirmed; outer receipt exit null. Focused stage has no worker metadata. | `PARTIAL` | External exit `NOT_PERSISTED`. Accepting could conceal a wrapper/process failure despite passing worker output. No existing acceptance rule resolves it. | Yes, if accepting this evidence gap as an exception. |
| `GATE_3_INTEGRITY` | Establish source/evidence integrity and required remote prefix integrity. | Test/harness source snapshot hashes match. Common real proofs are `UNVERIFIED_ORIGIN`; offline synthetic reference checks pass. | `PARTIAL` | Full remote prefix/hash coverage has not been established on the real source. Accepting could treat an unverified prefix as trusted and permit unsafe resume. | Yes for any exception; contract requires evidence and no waiver is recorded. |
| `GATE_4_REAL_PROOF` | Mandatory real technical proof, including trusted-reference behavior, under S6 V1. | Two historical `OPERATIONAL_ONLY` proofs pass their scenarios. `TRUSTED_REFERENCE` preflight was blocked before confirmation; no Telegram action followed. | `PARTIAL / MANDATORY CRITERION NOT SATISFIED` | Trusted-reference real proof is absent. Treating operational-only or synthetic evidence as equivalent would overstate what was proven. No approved exception found. | Yes for formal acceptance; any waiver must also be permitted by the governing contract. |
| `GATE_5_CONTINUITY` | Reconcile project state, historical evidence and a safe next step without rewriting history. | This report and the requested continuity files record evidence, limits, status, invariants and next action; historical receipts are unchanged. | `PASS` | None after this reconciliation is recorded. | No separate approval for factual continuity; formal acceptance remains user-owned. |
| `GATE_6_USER_ACCEPTANCE` | Explicit user decision accepting S6. | No acceptance decision has been recorded. | `PENDING` | S6 remains open until the user decides after mandatory gates are resolved or an applicable exception is authorized. | Yes. |

## Recommendation

```text
ACCEPTANCE_RECOMMENDATION = C / S6_REMAINS_OPEN
UNRESOLVED_MANDATORY_GATES = GATE_2_NATIVE_PROCESS_EVIDENCE; GATE_3_INTEGRITY; GATE_4_REAL_PROOF
S6_STATUS = OPEN / FORMAL ACCEPTANCE PENDING
```

The strict native process evidence remains partial because the external exit
was not persisted. The frozen S6 V1 contract makes
`REAL_TELEGRAM_TECHNICAL_PROOF` a separate mandatory acceptance gate, and the
trusted-reference proof did not occur. The two operational-only proofs and
offline synthetic evidence do not meet that requirement. Current governing
records do not allow this report to substitute an exception. Option B is not
recommended under the present contract and approval record; no exception is
approved here.

Any future work to resolve the native receipt gap or complete a
trusted-reference proof requires its applicable authority and must retain the
existing safety limits. This activity did not request or execute that work.

```text
ACTIVITY_COMPLETION_PERCENT = 100%
ACTIVITY_RESULT = EVIDENCE RECONCILED / DECISION PACKAGE READY / S6 OPEN
NEXT_ACTION = USER DECISION ON RECOMMENDATION; KEEP S6 OPEN WHILE MANDATORY GATES ARE UNRESOLVED
NO_TESTS_OR_PROOFS_EXECUTED = YES
NO_TELEGRAM_CALLS_OR_REAL_DOWNLOADS = YES
V1_ACTIVE = YES / V2_GLOBAL = OFF
GIT_ADD_COMMIT_PUSH = NO
```
