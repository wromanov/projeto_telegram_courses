# S6 V2 Proof Harness Correction Contract

```text
CONTRACT_ID = S6_V2_PROOF_HARNESS_CORRECTION_V1
DOCUMENT_ROLE = ACTIVITY_SCOPED_CORRECTION_CONTRACT
STATUS = CLOSED_FOR_IMPLEMENTATION
ACTIVITY = S6_V2_PROOF_HARNESS_CORRECTION
CANONICAL_S5_OR_S6_CONTRACT_CHANGE = NO
```

## 1. Authority and boundary

This contract is limited to correcting the isolated proof harness and its
offline tests. It does not amend S5, S6 V1, or the ratified S6 V2 design draft.
The existing S6 V2 contract digest remains
`C9C8A59B5F370B67A86D04CE7407517965711AE5E9780A17DED1C56A747BDF52`.

Authorized files:

- `tools/manual_proofs/s6_v2_proof_harness.py`
- `tests/manual_proofs/test_s6_v2_proof_harness.py`
- `docs/contracts/S6_V2_PROOF_HARNESS_CORRECTION_CONTRACT.md`
- one activity report under `docs/reports/`

The PowerShell launcher may be changed only if required to preserve the
existing synchronous native confirmation and child exit propagation. The
S5/S6 downloader, gateway, canonical contracts, operational database,
historical `.part` files, historical proof evidence, and
`.codex/agents/architect.toml` are protected.

The worktree already contains unrelated and pre-existing modifications.
Preserve them. No Telegram operation, download, V2 activation, Git mutation,
S6 formal acceptance, or sprint checkpoint is authorized.

## 2. Adjudicated diagnosis

### A. Phase 1 call cap

**Historical immediate cause confidence: probable / high.** The phase 1 prefix
is 1,048,576 bytes and the chunk is 262,144 bytes, so the local phase cap is
four `GetFile` requests. The ledger separately enforces aggregate request and
reserved-byte caps; S5 supplies the per-request reservation. The historical
phase record shows exactly four `GetFile`, 1,048,576 bytes reserved/received,
zero uncertain bytes, a saved prefix, and `FAILED_RETRYABLE / GATEWAY_FAILURE`.

The observed failure is consistent with the wrapper asking the inner stream
for another chunk before recognizing that the controlled prefix was complete.
The fifth reservation was then rejected by the local phase cap before the
fifth `GetFile` RPC. The checkpoint itself was within budget. No evidence shows
an aggregate cap overrun. The current harness already raises the planned
`CONTROLLED_INTERRUPT` immediately after yielding the exact prefix; this
contract requires a regression test proving no next reservation is requested
at the exact four-chunk boundary. The immutable historical evidence does not
include the original executed source or stack trace, so the historical cause
remains probable rather than proven.

### B. Missing phase 2 JSON

**Structural cause confidence: confirmed / high. Immediate historical cause:
unknown.** `_child_main` writes the phase JSON only after the full async stage
returns. Exceptions in stage finalization, deduplication, gateway cleanup,
event-loop teardown, serialization, or file writing bypass that single write.
The parent also had a bytes/string diagnostic parsing defect on a failed child
path; that defect obscured the child stop reason but does not explain why the
child JSON was absent. The current parent uses text capture, but child
exceptions and abnormal exits still need durable per-phase evidence. No
original child stdout/stderr sufficient to identify the immediate exception
was preserved. Do not attribute it to a specific cleanup or serialization
failure.

## 3. Required behavior

Each child invocation receives a unique `execution_id` and explicit `phase_id`.
The supervisor records the actual child PID from the process handle, its UTC
start/end observations and actual exit code. Phase 2 starts only after phase 1
has exited, its checkpoint and persistent budget ledger validate, and its
individual evidence passes the phase 1 contract.

Phase 1 yields exactly the configured prefix, persists and validates the
checkpoint, and stops before another reservation or remote call. Its planned
stop is a recorded phase outcome, not a generic gateway failure.

The child emits a provisional phase result on normal return and recoverable
exceptions. The supervisor emits the authoritative phase receipt after
observing process termination. Child declaration and supervisor observation
remain separate fields. A hard crash or forced termination may prevent a child
result; the supervisor receipt must say `EVIDENCE_INCOMPLETE` and must not
manufacture child facts.

Each authoritative phase receipt contains:

- schema version, `phase_id`, `execution_id`, phase number, target, mode, case;
- real child PID, observed UTC start/end, observed exit code, and stop condition;
- status: `PROCESS_COMPLETED`, `PROCESS_FAILED`, `PROCESS_INTERRUPTED`, or
  `EVIDENCE_INCOMPLETE`;
- child result presence and validation status;
- physical `.part`/final bytes, SQLite state/checkpoint bytes, checkpoint
  confirmation and SHA-256 when available;
- request counters and reserved/received/uncertain bytes before, after, and
  delta, using the proof ledger and observed phase result;
- V2 scoped state restoration and identity preflight when actually observed;
- explicit `null` plus a reason for any unavailable value.

The `GetFile` and `GetFileHashes` counters are exact from the durable proof
ledger. Identity `GetMessages` and direct `GetMe` counts are reported when the
child reaches those wrapped calls. Telethon's internal RPCs during
`TelegramClient.connect()` are not currently instrumented by the harness and
must be reported as unknown; do not present a derived subtotal as an exact
total Telegram RPC count. This correction does not widen or reinterpret S5
request caps.

Do not infer a PID, timestamp, exit code, RPC count, checkpoint, or successful
phase from final media or a SQLite terminal row alone.

## 4. Atomic reporting and reconciliation

Write JSON to an exclusive temporary file in the destination directory;
serialize strict JSON; flush and `fsync`; close it; then publish with
`os.replace`. Re-read and validate the published JSON. Temporary files never
count as phase evidence. Existing terminal reports are not silently overwritten.

The child result and supervisor receipt use distinct paths. The supervisor
persists a launch receipt as soon as PID is known, then replaces it atomically
with the terminal receipt after observing exit. If termination cannot be
confirmed, leave the phase incomplete and do not start the next phase.

The aggregate report must reconcile, independently:

1. phase 1 child result and supervisor receipt;
2. phase 2 child result and supervisor receipt;
3. proof SQLite status and versioned evidence;
4. physical checkpoint/final file size and SHA-256;
5. request and payload ledger deltas and aggregate S5 caps.

`TWO_PROCESS_PROOF=PASS` requires two valid individual receipts, two distinct
execution IDs, positive real PIDs that differ, phase 1 observed exit before
phase 2 start, expected phase outcomes, valid checkpoint and final state, and
consistent budgets/evidence. Missing, stale, corrupt, partial, mismatched, or
unverifiable evidence yields `TWO_PROCESS_PROOF=INCOMPLETE`; it can never be
promoted to PASS by reconciliation.

## 5. Failure and recovery rules

- Planned interruption: record the planned stop and preserve confirmed
  checkpoint/ledger values.
- Recoverable exception: child reports `PROCESS_FAILED`; supervisor records
  actual exit code and exception classification without replacing the primary
  failure with a cleanup failure.
- Crash or hard termination: supervisor records observed PID/exit if
  available; missing child evidence is `EVIDENCE_INCOMPLETE`.
- Timeout: terminate and wait for the child; record the actual observed exit.
  If it cannot be confirmed, stop with incomplete evidence and do not resume.
- Atomic-write failure, partial JSON, corrupt JSON, or stale report: retain
  the prior complete artifact, emit/retain an incomplete supervisor receipt,
  and fail closed.
- Budget exhaustion: record the gate and current ledger; issue no unreserved
  RPC and do not reset or reconstruct consumed budget.
- Resume: require scoped authorization, confirmed prior-process exit, valid
  phase receipt/checkpoint and the same persistent ledger. Never zero or
  silently repair ledger consumption.
- Re-entry or concurrent invocation for the same evidence root: fail closed.

Keep existing aggregate caps, per-GetFile S5 reservation, retries, FloodWait,
and worker limits unchanged. Do not add retries in the supervisor.

## 6. Safety invariants

- `V1_ACTIVE=YES`; operational `V2_EFFECTIVE=NO` outside the one authorized
  proof child.
- The scoped V2 switch returns to false in `finally`; a child process exit
  cannot activate V2 in another process.
- Proof SQLite and media paths remain confined to the fresh isolated root.
- The operational SQLite, historical `.part` files, prior proof evidence, and
  existing unrelated worktree changes remain untouched.
- Zero Telegram calls and zero downloads during this correction activity.
- No canonical contract, downloader product, or governance changes.
- No Git add, commit, push, reset, restore, clean, stash, or other mutation.

## 7. Binary acceptance and regression matrix

All required cases run offline with isolated fixtures and fail-closed
synthetic gateways. Every applicable case must PASS; skipped, blocked, or
interrupted tests are not passes.

| ID | Binary acceptance |
|---|---|
| T01 | Planned phase 1 interruption persists exactly the configured prefix and returns `CONTROLLED_INTERRUPT`. |
| T02 | Four-chunk local phase cap rejects any extra reservation before the gateway RPC. |
| T03 | Aggregate GetFile, GetFileHashes, and payload caps reject before the remote call; exact authorized caps remain unchanged. |
| T04 | Phase 1 child result and supervisor receipt record execution ID, real PID, times, exit, checkpoint and ledger. |
| T05 | Phase 2 child result and supervisor receipt record completion, final bytes/hash, evidence and ledger. |
| T06 | Two real offline subprocesses have distinct execution IDs and actual distinct PIDs; phase 1 exits before phase 2 starts. |
| T07 | Recoverable exception before child JSON still yields a supervisor receipt marked failed/incomplete, never PASS. |
| T08 | Partial/corrupt JSON and atomic replace failure preserve fail-closed reconciliation. |
| T09 | Child crash/forced exit and parent reconciliation preserve observed exit and classify missing child evidence incomplete. |
| T10 | Checkpoint bytes/state/hash survive interruption and resume; existing ledger consumption is retained. |
| T11 | Ledger-backed `GetFile`/`GetFileHashes` and payload counters reconcile by phase and remain within unchanged S5 ceilings; uninstrumented connection RPC totals remain explicitly unknown. |
| T12 | Missing, stale, or mismatched individual evidence yields `TWO_PROCESS_PROOF=INCOMPLETE`. |
| T13 | Scoped V2 activation is restored after normal completion and exception. |
| T14 | V1 stays active and operational V2 stays blocked. |
| T15 | All correction tests make zero Telegram calls and touch no operational SQLite or historical `.part`. |

Also run the targeted S5/S6 regressions, Ruff, compileall, PowerShell parser,
DryRun, and `git diff --check`. Git checks are read-only; no Git mutation is
permitted. If asyncio cannot run in the sandbox, use an authorized Windows
native offline runner and report the environment boundary.

## 8. Root adjudication and implementation decision

The independent `diagnostic_analyst` returned `GO_FOR_ROOT_IMPLEMENTATION=YES`
for this bounded contract, with the uncertainty in B preserved. Root
adjudication: **ACCEPT**. The structural report defect and phase-1 stop-order
defect are within the harness; no canonical contract change is required. The
unknown immediate phase-2 exception is a recorded limitation and must not be
filled by inference.

```text
ROOT_CAUSE_A = PROBABLE / HIGH; current stream wrapper contains the fix, tests to be strengthened
ROOT_CAUSE_B_STRUCTURAL = CONFIRMED / HIGH
ROOT_CAUSE_B_IMMEDIATE = UNKNOWN / original child output not retained
IMPLEMENTATION_OWNER = ROOT ONLY
GO_FOR_ROOT_IMPLEMENTATION = YES
```
