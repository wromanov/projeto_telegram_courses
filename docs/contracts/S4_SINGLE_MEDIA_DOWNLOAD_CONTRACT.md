# S4 — Single Media Download Contract

```text
DOCUMENT_ROLE = IMPLEMENTATION_CONTRACT
CONTRACT_STATUS = APPROVED / FROZEN_FOR_SINGLE_LESSON_MEDIA_OFFLINE_IMPLEMENTATION
ACTIVITY = S4-IMPL-01 — Single Media Download
IMPLEMENTATION_AUTHORIZATION = GRANTED / OFFLINE ONLY
REAL_TELEGRAM_ACCESS = NO
REAL_CATALOG_SQLITE_MODIFICATION = NO
GIT_PUBLICATION = NOT AUTHORIZED
S4_FORMAL_ACCEPTANCE = PENDING
FIRST_VERTICAL_SLICE_GATE = PENDING
```

## 1. Authorities and boundary

This contract operationalizes the user-authorized first S4 slice under
[PROJECT_STATE](../continuity/PROJECT_STATE.md), [SPRINTS](../continuity/planning/SPRINTS.md),
[ENGINEERING_FOUNDATION](../engineering/ENGINEERING_FOUNDATION.md),
[S2](S2_MESSAGE_SCANNER_SQLITE_CONTRACT.md), [S3](S3_PARSER_CATALOG_CONTRACT.md),
[REQUIREMENTS](../product/REQUIREMENTS.md), and [ARCHITECTURE](../architecture/ARCHITECTURE.md).
It neither expands S5/S6/S7 nor accepts the real Telegram end-to-end gate.

The canonical media identity is `(channel_id, telegram_message_id, media_ordinal)`;
the stable local key is `media_items.id`. A candidate is eligible only when its
channel, message and media rows exist, `kind = DOCUMENT`, expected size is a
known non-negative integer, and exactly one active catalog `lesson` node links
that media. Its active lineage is derived through optional module, course and
track ancestors; missing optional ancestors are omitted. General document nodes,
unclassified nodes, inactive lessons and ambiguous associations are rejected.

## 2. Boundaries and transfer

The repository owns SQL and returns a minimal candidate DTO: media row ID,
Telegram identity, expected size, source filename and active lesson lineage.
The application owns eligibility orchestration, path policy, transfer state,
stream validation, filesystem finalization and recovery. `TelegramGateway`
adds a stream operation accepting the three-part identity and expected media
identity. The Telethon adapter refetches the original message from the selected
channel, checks message identity, ordinal, document kind, media ID and expected
size, then yields asynchronous chunks via Telethon 1.45.x `iter_download` with
an explicit bounded request size. No Telethon type crosses the adapter.
Resume offsets are out of scope. Gateway failures expose only stable categories.

The application consumes one bounded chunk at a time, counts bytes and computes
local SHA-256 incrementally. It rejects bytes beyond expected size and treats
short streams or cancellation as incomplete. Hash means locally received
content integrity; it is not a Telegram-authenticated digest.

## 3. Paths and physical commit

The download root is selected by `--download-dir`, then
`TELEGRAM_COURSES_DOWNLOAD_DIR`, then `downloads`. Organization follows existing
active lineage as Track/Course/Module/Lesson, omitting absent levels. Windows
components replace prohibited characters, trim trailing spaces/dots, avoid
reserved device names, and receive deterministic identity suffixes. Components
are bounded to 100 characters and the absolute destination to 240 characters.
The resolved path must remain under the configured root; existing symlink/reparse
components, directory destinations and any preexisting final file are rejected.
No foreign or divergent file is overwritten.

The `.part` is a sibling of the final file (same volume). The writer flushes and
`fsync`s it, validates byte count and physical size, and persists `VALIDATED`
with size and SHA-256 before atomic no-overwrite finalization. It then confirms
the final file and persists `DOWNLOADED`. A validated final file left by a crash
is reconciled by size and SHA-256 before completion. Incomplete `.part` files
are never treated as complete; a subsequent attempt safely truncates/restarts
only its own recorded partial file. Unknown or foreign files are preserved.

## 4. Persistence and concurrency

Migration 004 is additive: it adds local SHA-256, validation timestamp and a
safe failure category to the existing downloads table, plus a unique index on
`media_item_id`. S0–S3 migrations remain unchanged. States used here are
`DOWNLOADING`, `VALIDATED`, `FINALIZATION_PENDING`, `DOWNLOADED`,
`FAILED_RETRYABLE`, and `FAILED`. Repository transactions own every transition.
A process-local per-media lock and a SQLite owner-PID lease prevent overlapping
transfers across processes; a stale owner is reclaimable after process exit.
`BEGIN IMMEDIATE` plus the unique media key prevents competing rows.
`DOWNLOADED` can only be persisted after confirming a matching final file.

On rerun, a `DOWNLOADED` row is deduplicated only if the final file exists and
size/hash match. A valid final file with a `VALIDATED` or
`FINALIZATION_PENDING` row is reconciled without Telegram access. Any mismatch
is reported and never silently replaced. A partial transfer is restartable from
the beginning; byte resume belongs to S6.

## 5. CLI and acceptance

Command: `telegram-courses download --channel-id N --telegram-message-id N
--media-ordinal N [--database PATH] [--download-dir PATH]`. It reports selected
identity, initial state, bounded progress, completion/already-downloaded, or a
sanitized failure category. The gateway is prepared lazily, only after local
deduplication and recovery checks require a stream; an already-valid second run
does not restore a Telegram session or call Telegram. It never prints
credentials, access hashes or session material. Configuration accepts the
CLI/environment/default root.

Offline unit and temporary SQLite/filesystem integration tests cover eligibility,
identity, chunk bounds, size/hash, stream and disk failures, Windows naming/path
safety, collision, migration/reopen, state ordering, crash-window reconciliation,
deduplication and concurrent selection. A fake-gateway end-to-end rerun must
show zero second-run stream calls and zero new canonical rows/files. Windows
synthetic filesystem validation is separate from real Telegram. Real Telegram,
the real catalog DB, formal S4 acceptance and `FIRST_VERTICAL_SLICE_GATE` remain
pending and unauthorized in this activity.
