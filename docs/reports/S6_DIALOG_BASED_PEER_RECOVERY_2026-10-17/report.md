# S6 — Dialog-Based Peer Recovery

**Activity:** `S6_BOUNDED_TARGET_DISCOVERY`  
**Continuation:** `DIALOG_BASED_PEER_RECOVERY`  
**Date:** 2026-10-17  
**Status:** `METADATA_COMPLETE / S6_ACCEPTANCE_PENDING`

## Repository preflight

- Repository root: `C:/Users/walac/desenvolvimento/projeto_telegram_courses`
- Branch: `work/s0-bootstrap`
- HEAD: `98d9d6b9ce152b8d2764a4d160fcbdf4722fb257`
- The worktree was already dirty before this continuation. Existing local changes were preserved.
- No formal continuity document or frozen S6 contract was updated by this activity.

## Identity and authorization

- Expected channel ID: `-1002758699600`
- `IDENTITY_GATE = PASS`, based on the user's explicit confirmation that this ID corresponds to RASMOO.
- The protected session must belong to the user-authorized account. Implementation preflight checks for an existing protected session; it does not log in or create a session.
- The user authorized dialog-based peer recovery and the already-authorized bounded metadata discovery, subject to all gates and an explicit confirmation in the native launcher.

## Reused analysis and contract decisions

The previous Diagnostic Analyst and Architect findings were reused; no new specialist investigation was performed. The Architect's analytical contract specifies:

- At most one `GetDialogs` page, capped at 100 entries, with `exclude_pinned=True`.
- `NOT_FOUND_IN_BOUNDED_WINDOW` is inconclusive and must stop without fallback resolution.
- Do not read `response.messages` or inspect remote dialog titles.
- Accept only an exact expected ID represented by a readable `Channel` with a valid `access_hash`; a `ChannelForbidden` result blocks recovery.
- Keep the resulting `InputPeer` and `access_hash` in memory only.
- Do not resolve by username or invite, persist dialogs/messages, or inspect message content.
- Dialog peer recovery and metadata discovery are separate user-authorized steps.

## Implemented scope and offline validation

The bounded implementation adds `recover_selected_channel_peer` to the existing `TelegramGateway` / `TelethonGateway` path and a manual proof runner. The runner's literal confirmation prompt is required before Python starts, session restore occurs, or an RPC is made. Its DryRun uses the native PowerShell path and does not restore a session or issue RPCs.

Exact scoped implementation files reported by the Root for the initial implementation:

- `src/telegram_courses/telegram_gateway.py`
- `src/telegram_courses/telethon_gateway.py`
- `tests/unit/test_s6_bounded_target_gateway.py` (new)
- `tests/unit/test_telethon_gateway.py` (changed)
- `tools/manual_proofs/s6_bounded_target_discovery.py` (new)
- `tools/manual_proofs/Invoke-S6BoundedTargetDiscovery.ps1` (new)

## Historical real execution

The user explicitly confirmed execution in the native launcher. One `GetDialogs` call returned 100 dialogs, which were counted/inspected. The run ended with `ADAPTER_FAILURE` and exit code `2`. A later diagnosis considers rejection of equivalent duplicate `Channel` entities a probable cause, but the original response was discarded and the cause is unconfirmed. No peer or `InputPeer` was confirmed. No message RPC was made (`metadata_rpcs=0`), and no channel messages were inspected.

| Measure | Result |
|---|---:|
| `DIALOGS_INSPECTED` | 100 |
| `DIALOG_RPC_CALLS` | 1 (`GetDialogs`) |
| `EXECUTION_STATUS` | `ADAPTER_FAILURE` (historical; probable cause unconfirmed) |
| `EXIT_CODE` | 2 |
| `VERIFIED_CHANNEL_ID` | `NOT_ESTABLISHED` |
| `INPUT_PEER_AVAILABLE` | `NO` |
| `METADATA_RPCS` | 0 |
| `CHANNEL_MESSAGES_INSPECTED` | 0 |
| `DOCUMENTS_FOUND` | 0 |
| `CANDIDATES_IDENTIFIED` | 0 |
| `GETFILE_CALLS` | 0 |
| `GETFILEHASHES_CALLS` | 0 |
| `MEDIA_PAYLOAD_BYTES` | 0 |
| `SQLITE_PERSISTENCE` | `FALSE` |
| `FLOODWAIT` | `NOT_REPORTED` |

## Duplicate-response diagnosis and approved correction

The historical `ADAPTER_FAILURE` is **probably** associated with rejection of equivalent duplicate `Channel` entities in the response. This is a probable diagnosis only; the original response was discarded, so the cause is not confirmed. Historical execution counts and outcome above remain unchanged.

The approved contract `S6_PEER_RECOVERY_DUPLICATE_CORRECTION_V1` was applied to these three authorized files:

- `src/telegram_courses/telethon_gateway.py`
- `tools/manual_proofs/s6_bounded_target_discovery.py`
- `tests/unit/test_s6_bounded_target_gateway.py`

Equivalent duplicates may be deduplicated only when every `Channel` entity for the exact target ID validates `hash`/`mimic`/`check_hash` and all resolve to the same ID and hash. Conflicts, any invalid occurrence, or `ChannelForbidden` block resolution according to the established precedence. Failure reasons are allowlisted and sanitized.

Root-reported validation after the correction:

- Focused suite plus regressions (`test_s6_bounded_target_gateway.py`, `test_telethon_gateway.py`, `test_telethon_discovery.py`): 73 passed after the counter-capture hotfix.
- Ruff on `src`, `tests`, and `tools`: PASS in independent Root validation.
- `compileall` on `src`, `tests`, and `tools`: PASS in independent Root validation.
- PowerShell `-Mode DryRun`: PASS in independent Root validation; zero restore/RPC, peer reason null, zero payload/GetFile/GetFileHashes/SQLite.
- The restricted test attempt produced no output and was interrupted; the escalated local synthetic run passed.
- No session restore or Telegram RPC occurred during the correction and offline validation phase before the subsequent real Execute run.
- `git diff --check`: PASS in independent Root validation, with only line-ending warnings.

## Counter-capture hotfix

After the first real Execute run, the runner was hotfixed to copy the message counters and peer-resolution reason into the final JSON after history processing. A synthetic test covers the final JSON output. The 73-test suite and independent Ruff, `compileall`, DryRun, and diff-check validation include this hotfix. The repeat Execute result below then captured the counters correctly and validates the capture hotfix. No further real Telegram call should be made.
## First METADATA_COMPLETE Execute result — stale counters

The first real Execute run was confirmed in the native launcher and restored the protected session. It accessed dialog and channel-history metadata. The attached result reports `status=METADATA_COMPLETE`, `peer_resolution_reason=PEER_RESOLVED`, channel ID `-1002758699600`, and identity authority as the user's explicit confirmation. It records one `GetDialogs` RPC and 100 dialogs inspected. The generated inventory contains 196 distinct document Message IDs; all 196 are `video/mp4`, sized from 4,102,953 to 210,364,212 bytes, with zero at or above 1 GiB. All records are metadata-only. The JSON's `metadata_rpcs=0` and `messages_inspected=0` fields are stale due to a capture bug and are not reported as actual zero counts.

The exact number of channel messages received is unavailable. The 196 distinct document Message IDs prove at least 196 messages were processed; the runner's 200-message cap, page size of 100, and maximum of two history pages bound the compatible count to 196–200. Under that algorithm, this successful run implies two `GetHistory` RPCs; this is derived from the algorithm and inventory, not a captured RPC counter. Combined with the one captured `GetDialogs` call, the derived total for these operations is three RPCs. No other RPC count is asserted.

| Measure | Result |
|---|---|
| `PEER_RESOLUTION` | `PEER_RESOLVED` |
| `VERIFIED_CHANNEL_ID` | `-1002758699600` (user-confirmed RASMOO identity) |
| `DIALOG_RPC_CALLS` | 1 (`GetDialogs`) |
| `DIALOGS_INSPECTED` | 100 |
| `CHANNEL_MESSAGES_INSPECTED` | 196–200 (bounded/derived; exact count unavailable) |
| `GETHISTORY_RPC_CALLS` | 2 (derived from runner pagination and inventory, not directly captured) |
| `DOCUMENTS_FOUND` | 196 |
| `CANDIDATES_IDENTIFIED` | 196 metadata records; none fully eligible |
| `MIME_TYPES` | 196 `video/mp4` |
| `SIZE_RANGE_BYTES` | 4,102,953–210,364,212 |
| `DOCUMENTS_AT_LEAST_1_GIB` | 0 |
| `GETFILE_CALLS` | 0 |
| `GETFILEHASHES_CALLS` | 0 |
| `MEDIA_PAYLOAD_BYTES` | 0 |
| `SQLITE_PERSISTENCE` | `FALSE` |
| `FLOODWAIT` | `NOT_REPORTED` |

Largest metadata record:

- Message ID: `447`
- Media ID: `5175124468544046296`
- Size: `210364212` bytes
- MIME: `video/mp4`
- Sanitized filename: `05 Teste Unit_rio da Service.mp4`
- Message date: `2025-07-18T01:05:30-03:00`
- Classification: `INSUFFICIENT_EVIDENCE` — below the contract's 1 GiB recommendation and no trustworthy byte-identical local reference is available. Remote Channel/Message/Media identifiers are present, but stability and integrity are not established. Metadata does not prove content integrity.

The complete sanitized metadata inventory is in [document_inventory.csv](document_inventory.csv). The input attachment's second line was treated as the PowerShell prompt, not as JSON; it and all non-allowlisted fields were excluded. No credentials, session data, file references, content, or media bytes were copied into the report or CSV.
## Repeat Execute result — post-hotfix counters

A repeated real Execute run completed after the counter-capture hotfix. The launcher-confirmed run reports `METADATA_COMPLETE`, `PEER_RESOLVED`, channel `-1002758699600`, `dialog_rpcs=1`, `dialogs_inspected=100`, `metadata_rpcs=2`, `messages_inspected=200`, and 196 documents across 196 distinct message IDs. The repeat result validates that the hotfix captures the counters and peer-resolution reason after history processing. Its inventory core fields (Message ID, Media ID, size, MIME, filename) match all 196 rows in the existing `document_inventory.csv`; the CSV was not rewritten.

| Measure | Result |
|---|---|
| `REAL_EXECUTION` | `METADATA_COMPLETE` |
| `PEER_RESOLUTION` | `PEER_RESOLVED` |
| `VERIFIED_CHANNEL_ID` | `-1002758699600` (identity explicitly confirmed by user) |
| `DIALOG_RPCS` | 1 |
| `DIALOGS_INSPECTED` | 100 |
| `METADATA_RPCS` | 2 |
| `MESSAGES_INSPECTED` | 200 |
| `DOCUMENTS_FOUND` | 196 (196 distinct Message IDs) |
| `DOCUMENTS_AT_LEAST_1_GIB` | 0 |
| `LARGEST_DOCUMENT_BYTES` | 210,364,212 |
| `GETFILE_CALLS` | 0 |
| `GETFILEHASHES_CALLS` | 0 |
| `MEDIA_PAYLOAD_BYTES` | 0 |
| `SQLITE_PERSISTENCE` | `FALSE` |

No further Telegram call is required or authorized for this repeat-result update. The historical `ADAPTER_FAILURE` cause remains probable (equivalent duplicate rejection), not confirmed.
## Gates and current outcome

- `IDENTITY_GATE = PASS`
- `IMPLEMENTATION_GATE = PASS` (approved correction implemented)
- `OFFLINE_VALIDATION_GATE = PASS`
- `SAFETY_GATE = PASS` for the authorized scope of the latest confirmed run: one `GetDialogs` RPC and two metadata/history RPCs captured by the fixed runner, 200 messages inspected, and no `GetFile`, `GetFileHashes`, media payload, or SQLite persistence.
- `PEER_RESOLUTION = PEER_RESOLVED` (latest Execute result)
- `REAL_EXECUTION = METADATA_COMPLETE`
- `REAL_METADATA_DISCOVERY = METADATA_COMPLETE`
- `S6_FORMAL_ACCEPTANCE = PENDING`
- `SPRINT_CHECKPOINT = DEFERRED`
- `GIT_COMMIT = NO`
- `GIT_PUSH = NO`

## Next action

The repeated metadata-only discovery validates the counter-capture hotfix. Do not make another Telegram call for this activity. No fully eligible candidate was established; the existing inventory remains metadata-only and does not establish stability or integrity. `S6_FORMAL_ACCEPTANCE = PENDING`, `SPRINT_CHECKPOINT = DEFERRED`, `GIT_COMMIT = NO`, and `GIT_PUSH = NO`.




