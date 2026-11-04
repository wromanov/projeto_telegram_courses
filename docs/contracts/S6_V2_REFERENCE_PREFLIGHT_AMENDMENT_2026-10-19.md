# S6 V2 trusted-reference preflight amendment — 2026-10-19

```text
DOCUMENT_ROLE = ACTIVITY_SCOPED_CONTRACT_AMENDMENT
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_V2_REFERENCE_PREFLIGHT_AMENDMENT
USER_DECISION = OPTION_A_APPROVED
REAL_TELEGRAM_CALLS = 0
REAL_DOWNLOADS = NO
REAL_PROOF_EXECUTION = NO
V1_ACTIVE = YES
V2_GLOBAL_EFFECTIVE = NO
```

This amendment implements the user's Option A decision for the
[`TRUSTED_REFERENCE` homologation contract](S6_V2_TRUSTED_REFERENCE_HOMOLOGATION_CONTRACT_2026-10-18.md).
It changes only the admission and evidence rules described here. It does not
change S6 V1, promote the V2 proposal, or authorize another real proof.

## Reference access and integrity

The Windows `IsReadOnly` attribute is descriptive metadata and is not an
admission condition. A reference with either value is accepted only when all
content, identity, path, and safety checks pass. The application must open the
reference exclusively in binary read mode (`rb`); it must never open it for
writing, change attributes or permissions, rename, move, replace, or place
proof artifacts beneath it.

Before a proof can request human confirmation, the native launcher must verify
the fixed local target declaration and reference using no RPC. The checks are:

- regular file exists at the canonical path and is not a symlink, reparse
  point, or multiply linked file;
- canonical path, size, SHA-256, target IDs, media kind, and media size match
  the values already pinned by the controlled-reference manifest and this
  contract;
- the reference and proposed evidence parent are separate;
- the reference identity is stable across the preflight hash read.

The preflight result reports `access_mode=READ_ONLY_BINARY` and `rpc_calls=0`.
It performs no write to the reference. The native PowerShell launcher blocks
confirmation if the result is missing, malformed, or divergent.

After the human confirms, each phase must validate the actual remote channel,
message, media ordinal, media ID, kind, and size before any `GetFile` or
`GetFileHashes` call. A mismatch blocks transfer. Identity `GetMessages`
requests remain within the approved aggregate cap of five. Offline tests use
only synthetic gateways and issue no Telegram queries.

After any controlled run that accessed the reference, including a failed or
interrupted run, the supervisor must verify the reference again against the
pinned path, identity, size, and SHA-256. A completed result also requires the
existing full bytewise comparison. A proven mutation or identity mismatch is
`BLOCKED`; absent or unreadable post-run evidence is `INCOMPLETE`. Neither can
produce `TRUSTED_REFERENCE_MATCH`.

## Native evidence root

The native PowerShell session validates its TEMP path and evidence parent for
containment and reparse points. After confirmation, the harness creates a
fresh, exclusive UUID root under that parent and rejects unsafe path
components, collisions, overlap with the reference, and operational SQLite
reuse. No Codex sandbox check is required for a root that does not exist until
native execution.

## Acceptance and offline validation

Required tests cover both `IsReadOnly` states, digest and size divergence,
missing and inaccessible reference, post-preflight mutation, missing
post-verification, remote identity mismatch before transfer, unsafe evidence
root, and no confirmation before any RPC or root creation. Existing tests are
preserved. Validation is offline only: focused pytest, Ruff, `compileall`,
PowerShell 5.1 parsing, `git diff --check`, and the supported DryRun. No
Telegram operation is authorized by this amendment.

```text
ATTRIBUTE_GATE = REMOVED
READ_MODE = rb
REFERENCE_PREHASH = REQUIRED
REFERENCE_POSTHASH = REQUIRED_WHEN_ACCESSED
FULL_BYTEWISE_COMPARISON = REQUIRED_FOR_MATCH
PRECONFIRMATION_IDENTITY = STATIC_CONTRACT_CHECK / ZERO_RPC
POSTCONFIRMATION_IDENTITY = REMOTE_CHECK_BEFORE_TRANSFER
EVIDENCE_ROOT = FRESH / NATIVE / EXCLUSIVE / CONTAINED
REAL_PROOF_AUTHORIZATION = SEPARATE_EXPLICIT_AUTHORIZATION_REQUIRED
```
