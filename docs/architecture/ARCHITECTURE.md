# Architecture — projeto_telegram_courses

**ARCHITECTURE_STATUS = APPROVED**

This document materializes the approved architecture reaffirmed by the user's Card B, sections 3–6, and reconciled on 2026-10-05. It describes the target architecture; it does not authorize implementation. The product is generic across multiple Telegram course channels; RASMOO is the first real validation target. See [REQUIREMENTS.md](../product/REQUIREMENTS.md) for the baseline and access boundary.

## Product shape and technology baseline

- Product: Python CLI for cataloging and selectively downloading course media from Telegram.
- Runtime: Python / CPython 3.14.x.
- Telegram protocol: MTProto using a Telegram user account.
- Telegram client: Telethon 1.45.x, isolated as an adapter.
- Transfer accelerator: cryptg 0.6.x.
- Async runtime: asyncio.
- CLI: Rich.
- Persistence: SQLite, accessed asynchronously through aiosqlite.
- Initial packaging: source execution in a virtual environment; Windows executable is a later roadmap phase.
- GUI is outside initial scope. TDLib remains a possible future migration path, not an initial implementation dependency. Pyrogram is rejected by the approved project decision; this records that decision without making a new claim about its current upstream status.

## High-level component flow

```text
Telegram (MTProto / user account)
  → TelegramGateway
  → TelethonGateway adapter
  → Channel Discovery / Message Scanner
  → Content Parser (RasmooParser or GenericParser)
  → Catalog Builder
  → SQLite Repository
  → Download Planner
  → Download Queue
  → bounded workers
  → File Storage
  → Organized Library
```

The diagram is a logical flow, not a finalized package layout. Formal responsibilities and persistence contracts are defined in [ENGINEERING_FOUNDATION.md](../engineering/ENGINEERING_FOUNDATION.md).

## Boundaries

### Telegram gateway

`TelegramGateway` is the application-facing boundary for authentication, channel listing/resolution, message iteration/refetch, and media streaming. `TelethonGateway` is the initial adapter. Telethon client/message/document/photo types remain inside the adapter; the domain and application layers use project-owned models/contracts.

### Pluggable parser architecture

Parser selection is independent of Telegram transport and download execution. `RasmooParser` is the first specialized parser. `GenericParser` is the fallback when no specialized parser matches. A parser detects/reads supported catalog structures and produces catalog nodes and message associations. A parser cannot download media or directly control storage, persistence, retries, or CLI behavior.

The `= / == / === / #Fxxx` convention is one supported structure, never a universal prerequisite. Inconsistent channels and unsupported media must expose their limits. Access is restricted to content normally accessible to the user's own account and allowed by the legitimate interface; no content-protection, authentication or antiabuse bypass is part of the architecture.

### Persistence and filesystem

Repositories own SQLite reads/writes. Raw SQL outside the persistence layer is prohibited. The filesystem owns physical file facts; SQLite owns the local catalog and operational state. A completed database status does not prove that a file physically exists, and an existing path does not prove that it contains the intended Telegram media. Reconciliation uses Telegram + SQLite + filesystem evidence.

### Download execution

Planning, queueing, bounded workers, resume/recovery, file validation, finalization, and persisted status transitions are coordinated in the application layer. Downloads write to partial files, validate, atomically finalize, and only then persist `DOWNLOADED`.

## Domain model

```text
Channel
└── Track?                 (optional by channel/parser)
    └── Course
        └── Module?        (optional by channel/parser)
            └── Lesson
                └── MediaItem
```

Additional operational concepts include `DownloadTask` and `SyncCheckpoint`. The domain is not RASMOO-specific. Track and Module are optional; the course parser requires a Course where applicable.

## Source-of-truth contracts

| System | Authoritative facts |
|---|---|
| Telegram | Remote message existence/content, associated media, Telegram-provided size/metadata, and account-accessible history |
| SQLite | Local catalog, course/module/lesson associations, sync/download state, attempts/failures, checkpoints, known local paths |
| Filesystem | Physical file existence/size, `.part` files, finalized files |

`DB_STATUS = DOWNLOADED` does not guarantee a physical file. `FILE_EXISTS` does not guarantee correct media identity. Reconciliation must use all three systems.

## Initial storage model

The initial schema contains `schema_migrations`, `channels`, `catalog_nodes`, `messages`, `media_items`, `downloads`, `sync_checkpoints`, and `scan_runs`. Schema detail and operating rules are in [ENGINEERING_FOUNDATION.md](../engineering/ENGINEERING_FOUNDATION.md).

## Architecture Decision Records

### ADR-001 — Telegram client

**Decision:** Use Telethon 1.45.x through the MTProto user-account protocol for the initial implementation; use cryptg 0.6.x as the transfer accelerator. Pyrogram is rejected for this project. Preserve a possible TDLib migration path without adding TDLib now. This is the approved target, not a claim of runtime/dependency compatibility already tested.

### ADR-002 — Telegram adapter boundary

**Decision:** Application/domain code depends on `TelegramGateway` contracts and project-owned models. Telethon-specific types and APIs remain in `TelethonGateway`.

### ADR-003 — SQLite persistence

**Decision:** Use local SQLite with aiosqlite and explicit SQL migrations; do not add SQLAlchemy or Alembic initially. Keep raw SQL inside the persistence layer. Multi-process execution is out of initial scope.

### ADR-004 — Pluggable parser architecture

**Decision:** Define a parser contract with `RasmooParser` as the first specialized parser and `GenericParser` as fallback. Parsers interpret catalog structure and never perform downloads or own infrastructure.

### ADR-005 — Application-layer resume

**Decision:** Resume is controlled by the application using a validated `.part` size and persisted state. Refetch the Telegram message/media before continuing; derive the offset from the partial file; stream via the adapter's supported capability; validate final size and optional configured hash; atomically finalize before marking complete. Real large-file interruption/resume remains a technical acceptance gate.

### ADR-006 — CLI first

**Decision:** The initial product is a CLI using Rich. GUI and web frameworks are out of initial scope. CLI usability still has acceptance criteria.

### ADR-007 — Bounded concurrency

**Decision:** Default to two download workers and allow configuration. Unlimited concurrency is prohibited. Establish any operational maximum from benchmark/evidence rather than an invented universal cap.

## Approval and reconciliation

The user's Card B explicitly reaffirms `ARCHITECTURE_APPROVAL = APPROVED` and the decisions above; see [APPROVALS_AND_DECISIONS.md](../governance/APPROVALS_AND_DECISIONS.md). The baseline is reconciled with Requirements and Engineering Foundation. Dependency compatibility, large-file behavior, session protection and live Telegram acceptance remain future validation work. Governance integrity and the opening result are in [PROJECT_OPENING_GATE.md](../governance/PROJECT_OPENING_GATE.md).
