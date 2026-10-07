# Engineering Foundation — projeto_telegram_courses

**FOUNDATION_STATUS = APPROVED**

The user's Card B, sections 5–6, explicitly reaffirms this approved technical baseline. Reconciled on 2026-10-05 against [REQUIREMENTS.md](../product/REQUIREMENTS.md) and [ARCHITECTURE.md](../architecture/ARCHITECTURE.md). This is not authorization to start S0 or implement product code.

## Runtime and toolchain

| Concern | Baseline |
|---|---|
| Language/runtime | Python, CPython 3.14.x |
| Project metadata | `pyproject.toml` |
| Environment | `venv` |
| Tests | pytest |
| Lint/static quality | Ruff |
| CLI | Rich |
| Async | asyncio |
| Telegram | Telethon 1.45.x via MTProto user account |
| Transfer acceleration | cryptg 0.6.x |
| Database | SQLite with aiosqlite |
| Initial packaging | Source execution / venv |
| Windows executable | Future distribution phase |

Do not add SQLAlchemy, Alembic, Redis, Celery, web frameworks, or distributed architecture in advance of a demonstrated need.

## Persistence schema baseline

- `schema_migrations`: version, applied timestamp.
- `channels`: Telegram chat identity, title/username, parser key, creation/update/scan timestamps.
- `catalog_nodes`: channel, parent, kind, code, ordinal, title, source message, timestamps.
- `messages`: channel/message identity, dates, text, grouped ID, timestamps; unique `(channel_id, telegram_message_id)`.
- `media_items`: message/catalog association, media type, original filename, MIME type, file size, Telegram media identity, timestamps.
- `downloads`: media item, state, final/partial paths, expected/downloaded bytes, attempts, error details, lifecycle timestamps, optional SHA-256.
- `sync_checkpoints`: channel, last message ID/date, scan time/status.
- `scan_runs`: channel, run timestamps, message/media counts, new/updated/error counts, status.

Schema changes use numbered SQL migrations. Alembic is not part of the initial baseline.

## SQLite operating rules

```text
PRAGMA foreign_keys = ON
journal_mode = WAL
busy_timeout = configured
```

Related changes use transactions. Writes are controlled by the repository layer. Raw SQL outside the persistence layer is prohibited. Multi-process execution is out of scope for the first version.

## Download state machine

```text
NEW → QUEUED → DOWNLOADING → DOWNLOADED
                    ├→ PARTIAL → QUEUED
                    ├→ FAILED_RETRYABLE → QUEUED
                    └→ FAILED

Other recorded states: SKIPPED, REMOVED, UPDATED, PARTIAL_INVALID
```

`DOWNLOADED` requires the final file to exist and expected size to be validated. `PARTIAL` requires a `.part` file whose physical size is compatible with persisted progress. Never download directly into the final filename.

## File commit protocol

```text
write *.part
→ validate expected size
→ optional hash validation
→ atomic replace/rename
→ persist DB state = DOWNLOADED
```

Never persist `DOWNLOADED` before finalizing the physical file.

## Resume contract

- Resume is application controlled.
- Re-fetch the original Telegram message before continuing.
- Confirm the referenced media remains the expected item.
- Validate the existing `.part` file; derive offset from its physical size and compatible persisted state.
- Continue using a capability supported by the gateway adapter; do not expose Telethon types above that boundary.
- Validate expected final size; optional/configurable hash validation may be used.
- Atomically finalize, then mark `DOWNLOADED`.
- Before marking resume complete, run the real-large-file interruption/restart/continuation technical validation described above.

Byte-level resume is conditional until that validation passes. Failure recovery still requires controlled retry, explicit partial/invalid state and safe restart. It must not silently claim supported byte-level continuation. Recorded download states are `NEW`, `QUEUED`, `DOWNLOADING`, `PARTIAL`, `DOWNLOADED`, `FAILED_RETRYABLE`, `FAILED`, `SKIPPED`, `REMOVED`, `UPDATED`, and `PARTIAL_INVALID`.

## Windows path policy

Sanitize reserved characters `< > : " / \\ | ? *`, Windows device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`), trailing dots/spaces, empty names, and excessive path components. Sanitization requires dedicated unit tests. Preserve original filename and logical content code in SQLite. Name collisions must resolve deterministically and must never overwrite silently.

## Configuration contract

The recorded configuration file is `config/settings.toml`, covering download directory/workers/retry limit/hash option, database path, logging level, and Telegram session path. Telegram API credentials use environment secrets such as `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`; no secret has a hardcoded fallback. The stated precedence where applicable is CLI argument → environment/secret → settings file → application default. Do not version credentials or session material.

The Windows session-protection design is recorded in [ARCHITECTURE.md](../architecture/ARCHITECTURE.md), ADR-008. Before creating a real session in S1, verify the implementation and storage/access protection against that design. Session material must be excluded from repository, operational logs and shared artifacts. No session or credentials are created during opening.

### Telegram session security contract

- Store only a DPAPI `CURRENT_USER`-protected representation of Telethon `StringSession` at rest, in a user-scoped application-data location outside the repository with restrictive user-level filesystem access. `DPAPI_LOCAL_MACHINE` scope and plaintext session files are prohibited.
- Plaintext `StringSession` exists only in memory inside the Telethon adapter, for the minimum necessary lifecycle; decrypt the protected representation only when required.
- Never place session material in Git, logs, fixtures, or shared artifacts. Do not provide automatic backup or export.
- Use an independent authorization and session per machine. Local blob deletion is not remote revocation; remote revocation is a separate operation. Reauthenticate when the session is no longer valid.

## Logging contract

- Rich console output is user-oriented; file logs are structured operational records.
- Initial record shape: timestamp, level, component, event, context.
- Never log API hash, login code, 2FA password, session contents, or session string.

## Error taxonomy and retry

Recorded error classes: `AuthenticationError`, `AccessError`, `TelegramRateLimitError`, `NetworkError`, `ParserError`, `DatabaseError`, `StorageError`, `InsufficientDiskSpace`, `DownloadError`, `IntegrityError`, and `ConfigurationError`.

Retry transient timeouts/network failures and selected transient Telegram errors with bounded exponential backoff plus jitter. Handle `FloodWait` through the application-owned policy in the Telegram retry contract below. Do not automatically retry authentication/access failures, invalid configuration, disk full, parser invariant failures, or content-protection restrictions. No infinite retry loops; unexpected failures reach a controlled global boundary.

### Telegram retry contract

- The application owns semantic retry policy, retry budget, cancellation, and the decision to wait or retry an operation. Do not set numeric retry, budget, or cooldown values in this foundation.
- The Telethon adapter owns transport mechanics and translates FloodWait into an application/domain error carrying `retry_after_seconds`; the application decides the wait and cancellation/budget outcome.
- Disable Telethon automatic FloodWait sleep for the S1 design. Any internal Telethon retry path must be finite and bounded, and must not mask FloodWait, authentication, access, or configuration failures. Automatic retries for authentication, access, and configuration failures are prohibited. No unbounded sleep or retry is allowed.
- Keep Telethon-specific types and exception details inside the adapter. Keep DC migration and protocol handling there when application semantics remain transparent.

## Concurrency and disk-capacity gates

- Default download workers: 2; configurable.
- Unlimited concurrency: prohibited.
- Do not set a universal operational maximum without benchmark/evidence.
- Before a batch with known sizes, compare required bytes, available bytes, and safety margin. If capacity is insufficient, block batch start. If size is unknown, disclose that fact.

## Test strategy

- Unit tests without Telegram: parsers, filename sanitizer/path builder, deduplication, state machine, config loading, planner/catalog builder, repositories, migrations.
- Local integration tests: temporary real SQLite and filesystem, `.part` recovery, migrations, and atomic finalization.
- Separate Telegram integration tests: authentication, channel discovery, history scan, message refetch, small media download, large interrupted/resumed download, and FloodWait behavior when reproducible/simulable.
- Offline tests must cover the DPAPI/session wrapper, secret redaction, simulated FloodWait translation, and simulated application retry policy/budget. Keep real Telegram validation separate from these offline tests.
- The normal pytest suite must not require Telegram login.

Streaming must keep memory bounded for large files. Memory acceptance threshold and operational upper worker limit require evidence in the relevant sprint. Respect the Requirements access boundary in every test and operation; no retries/adapters bypass content protection, access restrictions, authentication or antiabuse mechanisms.

## RASMOO acceptance dataset

Use a controlled sample before any mass download. Include one track, two courses, two or more modules, multiple `#Fxxx` items, at least one `#Docxxx` if present, a problematic filename, a message without media, and media not present in the index. Establish parser correctness before mass download.

## Relationship to approval and planned validation

`FOUNDATION_APPROVAL = APPROVED` is reaffirmed by the user's Card B; see [APPROVALS_AND_DECISIONS.md](../governance/APPROVALS_AND_DECISIONS.md). Toolchain, schema, states and file-commit contracts match that baseline. This activity has not installed dependencies, run product tests, authenticated Telegram or demonstrated a working runtime. The present opening review and governance blocker are in [PROJECT_OPENING_GATE.md](../governance/PROJECT_OPENING_GATE.md).
