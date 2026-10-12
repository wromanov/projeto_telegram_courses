# S5 — Course Selection, Download Planner and Queue Contract

```text
DOCUMENT_ROLE = IMPLEMENTATION_CONTRACT
CONTRACT_STATUS = APPROVED / FROZEN WITH S5-REAL-PREP-02 SAFETY-LIMIT ADDENDUM
ACTIVITY = S5-IMPL-01 — Integrated Course Download Selection, Planner and Queue
S5_STATUS = IN_PROGRESS
S5_READINESS = ENTRY_GATE_PASS
S5_IMPLEMENTATION_AUTHORIZATION = YES / SOURCE_CHANGES_WITHIN_THIS_CONTRACT
S5_FORMAL_ACCEPTANCE = PENDING
REAL_TELEGRAM_ACCESS = NO
REAL_SQLITE_ACCESS = NO
REAL_MEDIA_DOWNLOAD = NO
```

## 1. Authorities, objective and boundary

This contract operationalizes S5 in [SPRINTS](../continuity/planning/SPRINTS.md)
and [ROADMAP](../continuity/planning/ROADMAP.md), building on the accepted
[S3 catalog contract](S3_PARSER_CATALOG_CONTRACT.md), frozen
[S4 single-media contract](S4_SINGLE_MEDIA_DOWNLOAD_CONTRACT.md),
[requirements](../product/REQUIREMENTS.md), and
[engineering foundation](../engineering/ENGINEERING_FOUNDATION.md). S4 remains
accepted and closed. This contract authorizes only offline S5 source changes
and synthetic tests. Real Telegram, credentials, session, project SQLite,
media downloads, and Git publication remain unauthorized.

S5 adds explicit Channel/Course/Module/Lesson selection, a read-only planning
pass, bounded in-process queue execution through the S4 application, per-item
and aggregate progress, and safe reruns. Track is retained in lineage and
ordering but is not a selectable scope in this first slice. Offset resume,
incremental synchronization, scheduling, GUI, a second downloader, and
multi-process queue ownership remain out of scope.

## 2. Existing components and required changes

| Area | Existing component and reuse | Change required for S5 |
|---|---|---|
| Catalog/navigation | `SQLiteCatalogRepository`, `CatalogNodeView`, `CatalogChannelView`, `get_catalog_nodes()`, `get_catalog_items()`; current CLI already displays catalog hierarchy and handles terminal text safely. | Add a scoped, bounded read-only query returning active selectable nodes and the catalog/scan completeness summary needed by a plan. Existing item listing is display-oriented and loads a whole channel; do not use it as the batch planner query. |
| Hierarchy/identity | `catalog_nodes`, `catalog_node_identity`, stable `catalog_node_id`, `media_items.id`; catalog lineage is Channel → optional Track → Course → optional Module → Lesson → MediaItem. | Reuse those identities; query and validate the whole active lineage in one repository operation. Do not parse source text or call a parser during selection/planning. |
| Lesson/media association | `media_items.catalog_node_id`; S4 `DownloadRepository.select_candidate()` validates one linked active lesson and its permitted ancestor chain. | Generalize candidate selection to a deterministic multi-item scope query; preserve S4 eligibility rules and reject missing, inactive, ambiguous, or invalid lineage. |
| Canonical media identity | Unique `(channel_id, telegram_message_id, media_ordinal)` and stable `media_items.id`. | Use the canonical triple to deduplicate the plan; retain `media_items.id` as the local persistence key. |
| S4 download application | `SingleMediaDownloadApplication.download()` owns transfer validation, file commit, deduplication/recovery, and S4 state transitions. | Queue calls this application once per selected candidate. Add a read-only inspection/evaluation path that shares S4 validation rules; do not call `download()` to build a preview because it starts transfers for pending items. |
| Download repository | `DownloadRepository` owns candidate SQL, `downloads` reads/writes, unique media row, `BEGIN IMMEDIATE`, process-local locks and owner-PID protection. | Extend only with scoped read-only batch reads and any atomic claim operation proven necessary. Each worker must still pass through S4's unique media ownership and state transitions. |
| Physical deduplication | S4 hashes and checks expected size before reporting `ALREADY_DOWNLOADED`; finalization is no-overwrite and validates before `DOWNLOADED`. | Share this physical-validity rule with planning. Do not treat the state flag, path existence, or size alone as proof of completion. |
| Telegram/streaming | `TelegramGateway.stream_media()` and `TelethonGateway` refetch/verify the selected message and media, then stream bounded chunks; no Telethon type crosses the port. | Planner must not depend on or initialize the gateway. Queue reaches it only through S4. Extend the gateway error value to carry `retry_after_seconds` for FloodWait before implementing queue wait/retry behavior. |
| CLI/progress | Rich, current `catalog` and single-item `download` commands, `--database`, `--download-dir` / `TELEGRAM_COURSES_DOWNLOAD_DIR`, default `downloads`; Windows-safe terminal output is already implemented. | Add selection/preview/queue flow and per-item plus aggregate progress, preserving Unicode handling. Add a finite worker-count setting (default 2); current CLI/config does not expose workers. |
| Configuration | Database and download-root CLI/default behavior exists. `config/settings.toml` currently supports logging only. | Expose `--workers` constrained to 1..2 (default 2); keep the approved three-attempt budget and disk margin as fixed S5 defaults. Do not claim settings-file support for these values. |
| Download states | S4 persists `DOWNLOADING`, `VALIDATED`, `FINALIZATION_PENDING`, `DOWNLOADED`, `FAILED_RETRYABLE`, and `FAILED`; migration 004 has unique `media_item_id`, hash and owner PID. | Queue-only planned/waiting/cancelled presentation can be ephemeral. Do not introduce new persisted states or a migration solely to represent a process-local queue. Map final per-media outcomes to existing S4 records. |

The following pieces can be reused **without changing their behavior**: S3
parser/build logic and catalog identity schema; the S4 per-item transfer path
(`SingleMediaDownloadApplication.download()`), streaming/chunk validation,
path derivation/sanitization, no-overwrite finalization, hash/size rules,
state transitions and per-media ownership; the existing S4 migrations and
unique media row; `TelegramGateway.stream_media()` for normal transfers; Rich
text sanitization/Windows output handling; and the current database/download
root options and defaults. S5 adds selection/planning/queue APIs around these
pieces. The read-only physical evaluation may share S4's existing path and
hash helpers; it must not fork their rules. The FloodWait error payload is the
one required change to the current adapter boundary.

## 3. Selection and catalog rules

Selection is explicit and scoped to one cataloged Channel:

- Channel: every eligible media item under active lessons in that channel.
- Course: eligible media beneath exactly the selected active course.
- Module: eligible media beneath exactly the selected active module.
- Lesson: eligible media linked to exactly the selected active lesson.

Course/Module/Lesson selection uses a contextual interactive menu with stable
one-based display ordering; module and lesson choices include their parent
titles to distinguish repeated names. The CLI does not expose internal SQLite
IDs as user-facing identity. The application resolves a menu choice to its
local `catalog_node_id` and revalidates it in the planning query. The node must
belong to the requested channel, be active, and have one valid active lineage.
A Course may have an optional Track ancestor; a Module may have an optional
parent Course; a Lesson may have an optional Module or a direct Course parent.
Other, missing, cyclic, inactive, or ambiguous ancestry is rejected and
reported. Track is not selectable in S5; supporting it later would require
explicit scope approval, although its existing lineage is preserved.

Only media linked to a selected active Lesson can become a candidate. Reuse
S4's eligibility constraints: supported `DOCUMENT` media, known non-negative
size, Telegram media identity, unique canonical identity, and a valid active
lesson lineage. Unknown sizes, unsupported kinds, and invalid or unresolved
associations appear in the excluded count with stable reasons; they never
become transfer tasks. `catalog_unresolved_sources` and unclassified sources
are diagnostic-only and are never promoted to lesson downloads.

The query returns one row per canonical media identity and orders by catalog
ordinal/path, then Telegram message ID and media ordinal, with stable node/key
tie-breakers. Duplicate identities collapse to one plan entry; conflicting
associations are excluded as ambiguous rather than selected by arbitrary row
order. No item outside the selected node's subtree is included.

The plan includes a catalog completeness indicator. If the persisted source
scan/catalog represents a partial or message-limited scan, show that the plan
covers only observed catalog content and require explicit confirmation before
queue execution. An absent or unusable catalog, or a deleted/inactive selected
scope, fails closed. Planning never refreshes Telegram or rebuilds the catalog.

## 4. DownloadPlan contract

The planner is a pure domain/application operation over one consistent,
read-only SQLite snapshot and a read-only filesystem evaluation; it imports no
parser and no Telegram adapter. A `DownloadPlan` contains:

- deterministic `plan_id`, selected scope identity, and catalog completeness;
- ordered canonical media identities and eligible candidates;
- excluded entries with stable reason codes;
- known total bytes, unknown-size count, and counts for already-valid,
  pending, blocked/conflicting, and excluded entries;
- per-item current classification, without volatile timestamps or progress in
  plan identity.

`plan_id` is a digest of normalized selection identity and the ordered canonical
media identities plus stable media identity/size inputs. It omits UUIDs,
timestamps, filesystem observations and live progress. Rebuilding from the same
catalog and scope yields an equivalent plan; a changed membership or relevant
media identity/size changes the digest. It is an invocation-local review token,
not a persisted queue identifier.

An item is **already valid** only when the S4 record is `DOWNLOADED`, its
recorded final path equals the deterministic path under the selected download
root, and the final regular file is verified using expected size and the
persisted SHA-256. Any symlink/reparse path is unsafe. The preview hashes the
file; SQLite state or file existence alone is insufficient. A missing final
file or stale interrupted state is classified pending/recoverable and is
re-evaluated by S4 at execution. A present divergent/foreign file, mismatched
path, or unverified finalization is blocked as a conflict and is never silently
overwritten. The executor rechecks every item to handle changes after preview.

No size-unknown item is executable in S5 because S4 currently requires a known
size. The plan reports it as excluded/unknown rather than estimating bytes.
Before starting a batch, compare known pending bytes with free space plus the
approved margin `MAX(1 GiB, 10% of known pending bytes)`. Reject insufficient
capacity and disclose that the estimate covers only known sizes. Recheck before
each newly reserved item, accounting for active `.part` allocations and
remaining pending bytes. Never remove user files to create space. Tests may
inject available space without relying on host disk capacity.

## 5. Queue, workers and outcomes

Keep the execution shape to `DownloadPlan` → `DownloadQueue` → bounded workers
→ `SingleMediaDownloadApplication`. A worker receives one plan entry and calls
S4; it does not duplicate transfer, path, physical deduplication, or state
logic. A queue invocation is in-process and ephemeral. Default workers: 2; the
only allowed values are 1 or 2, capped by the number of pending entries.
Unlimited/background workers are prohibited.

The planner removes duplicates before enqueue. Queue-local ownership prevents
the same canonical media identity from being scheduled twice in one invocation;
S4's unique media row, locks, owner-PID check and transaction remain the
cross-worker/process guard. A contested item is reported as in progress and is
not transferred a second time.

Queue display states are `PLANNED`, `WAITING`, `RUNNING`, `COMPLETED`,
`ALREADY_VALID`, `FAILED`, `CANCELLED`, and `BLOCKED`. They are derived for the
current invocation, not added to the S4 database. The S4 row remains the durable
per-media result. A crash loses queue ordering but not completed per-media
results; a new invocation rebuilds the selection and S4 safely re-evaluates
each item. This provides safe restart, not byte resume (S6).

One item failure does not fail siblings. Continue independent queued work for
ordinary item failures, collect sanitized stable categories, and return a
nonzero overall result when any item failed or was blocked. On cancellation,
stop scheduling new items, cancel active S4 calls through their existing
cancellation cleanup, await worker shutdown, and preserve completed results.
No item is marked complete before S4 validates and commits its file.

`MAX_ATTEMPTS_PER_MEDIA = 3`, including the initial transfer. Retry only
transient network/transport failures and rate limits; never retry credentials,
permission, media identity, configuration, integrity, disk, unsafe path, or
other terminal failures. The adapter carries `retry_after_seconds` in the
domain error without exposing Telethon types. FloodWait honors the reported
duration, is cancellable, shares a process-local cooldown across workers, and
permits at most 120 seconds of cumulative automatic waiting per item. A wait
that exceeds the remaining budget is recorded as rate limited without an
unbounded delay or retry. No retry policy bypasses Telegram limits.

Aggregate progress is computed from plan counts and worker events: total,
completed, already valid, failed, blocked, pending, and active; transferred and
known expected bytes; per-item byte progress; elapsed time and speed when
available. Unknown sizes remain separately counted. Progress is observational
and cannot advance persisted state.

## 6. Persistence and recovery decision

Do not create `download_plans`, `download_queue`, or queue-job migrations in
S5. The existing unique per-media row and S4 lifecycle are sufficient for
durable transfer results and recovery. The queue is a single invocation; the
next invocation recomputes it from the same catalog selection and current S4
records. A process-dead `DOWNLOADING` owner is reclaimed by the existing S4
ownership path; live ownership blocks a duplicate. Do not claim resumable byte
offsets or persist queue-level checkpoints.

The preview uses an existing database in SQLite read-only mode and is
read-only: no migrations, schema/WAL setup, parent-directory creation, row
transitions, directory creation, Telegram session restore, or gateway call.
If required migrations are absent, planning fails without applying them.
Filesystem checks only stat/read/hash existing paths. Planning must not take
over S4-owned recovery transitions. Only after confirmation does S4 perform its
existing reconciliation and transfer behavior.

## 7. CLI flow

Retain the current S4 single-item invocation unchanged. Add two batch operations
using the existing command family and shared database/download-root options:

```text
telegram-courses download plan --channel-id N [--scope channel|course|module|lesson]
telegram-courses download queue --channel-id N [--scope channel|course|module|lesson] [--workers N]
```

The scope defaults to the whole channel. For course/module/lesson, the command
prompts for a contextual menu choice and never asks for or displays a SQLite
node ID. `plan` prints the selection, completeness warning, known bytes,
eligible/already-valid/pending/excluded totals and exclusion reasons; it is
read-only. `queue` prints the same freshly evaluated plan and asks for
confirmation before any mutation or Telegram access. Scoped selection and
execution require an interactive terminal in this first CLI slice; partial
catalog plans always display the limitation and require explicit confirmation.
Because plans are not persisted, `queue` recomputes rather than trusting a
stale plan ID.

Rich output uses the existing Windows-safe output path and sanitized text.
During execution show per-item progress plus aggregate completed/already-valid/
failed/pending counts, transferred bytes, and elapsed time/speed when viable.
Finish with each media identity and result category, plus a clear overall
success/partial-failure summary. No credentials, session data, access hashes,
or raw exception strings are displayed.

### S5-REAL-PREP-02 — optional transfer safety profile

Normal S5 downloads remain without a fixed media-count or aggregate-byte cap.
Controlled runs may configure `--max-media-items N` and
`--max-transfer-bytes N` on `download plan|queue`; omitted options remain
unlimited. The preview reports selected, pending, already-valid and excluded
counts, known pending bytes, configured caps and a pass/fail limit check.
Configured caps are checked against the freshly rebuilt plan before a worker,
gateway, SQLite migration, or transfer starts. The count cap covers all
selected plan entries; the byte cap covers pending known-size media. A
controlled byte-capped run fails closed if the selection contains an
unknown-size exclusion.

For byte-capped execution, one invocation-wide budget is shared by every
worker and retry. Before each Telethon `GetFile` request, the adapter reserves
the request's maximum payload size (up to 256 KiB); if that full reservation
does not fit, it sends no request. The adapter uses the pinned Telethon
1.45.x direct iterator (`request_size == chunk_size`), gates its actual request
boundary, disables Telethon's hidden RPC retry loop for the duration of capped
streams, and restores the prior setting when all such streams finish. A
completed response converts its reservation to the returned payload byte
count. Normal end-of-file releases an empty request reservation. An error or
cancellation while a request is in flight charges the whole reservation
conservatively because the adapter cannot prove that no payload arrived.

The accounting invariants are:

```text
RESERVED_BYTES = maximum payload allowance of currently in-flight requests
RECEIVED_BYTES = payload bytes returned by completed requests, across attempts
CONSUMED_BYTES = RECEIVED_BYTES + UNCERTAIN_IN_FLIGHT_BYTES
REMAINING_BUDGET = BUDGET_BYTES - RESERVED_BYTES - CONSUMED_BYTES
```

All reservations are atomic against the shared balance; a reservation is never
also counted as received. Failed-attempt bytes and uncertain in-flight
allowances remain charged across retries. The budget covers media payload,
not encrypted transport framing. The adapter verifies the remote media
identity and advertised size before streaming and yields chunks of at most
256 KiB. When no complete next-request reservation fits, the queue stops
scheduling payload requests and reports remaining items blocked; completed S4
files and records remain preserved. An uncapped normal S5 invocation retains
the existing S4 stream path.

## 8. Test strategy and acceptance

Offline tests use fixtures, fake gateways, temporary directories, and temporary
SQLite databases only. No test in the normal suite authenticates to Telegram.

| Coverage | Required evidence |
|---|---|
| Course, module, lesson, and channel selection | Exact subtree membership; adjacent siblings and out-of-scope media excluded. |
| Track decision and ordering | Track cannot be selected; optional Track lineage is valid; order stable over repeated plans. |
| Identity and duplicates | Same scope/catalog gives equivalent plan ID; duplicate identity is enqueued once; conflicting association excluded. |
| Unresolved/ineligible | RASMOO unresolved/unclassified, inactive nodes, invalid lineage, unsupported kind, unknown size and missing media identity excluded with reason. |
| Partial catalog | Partial/message-limited warning and confirmation gate; no silent scope expansion or refresh. |
| Physical deduplication | Valid `DOWNLOADED` + matching path/size/SHA-256 is already valid; missing/corrupt/mismatched/foreign/reparse files are pending or blocked as specified. |
| Empty plan | No pending item executes and no Telegram gateway is created. |
| Worker bounds/ownership | Default 2, configured finite bound, queue dedup, same-media contention, existing S4 process ownership. |
| Optional safety limits | Unlimited normal S5 mode; count/byte rejection before workers; concurrent reservations; failed-attempt accounting; no retry/new stream beyond budget; unknown-size rejection. |
| Failure/cancel/retry | Middle-item failure leaves siblings running; terminal failure not retried; FloodWait delay is surfaced/honored with finite budget; cancellation stops new tasks and preserves completed items. |
| Re-execution/persistence | SQLite + filesystem temporary integration; completed items become already valid; failed items are re-evaluated; no duplicate row/file; reopen and interrupted owner recovery. |
| Progress | Individual, aggregate counts/bytes, unknown size, speed/time and terminal summary are coherent. |
| Windows CLI/regression | Unicode safe Rich output, path collision handling, S4 single-item behavior, and relevant S0–S4 regression suite. |

Formal S5 acceptance requires these offline tests and targeted integration
checks to pass, existing regressions to remain green, a bounded-worker
concurrency check, and PROJECT_STATE reconciliation. A later real acceptance
is a separate activity requiring explicit authorization: use a copied/isolated
catalog database and temporary download root, preview one explicitly selected
small course/module scope, cap the approved item count, execute once, verify
each selected physical file and SHA-256 against SQLite, verify no outside item
was added, then perform one bounded rerun to prove no duplicate transfer. Stop
on any mismatch or rate limit. This contract authorizes none of those operations.

## 9. Technical decisions

### D1 — Reuse the current catalog and canonical identity

```text
DECISION = Select by persisted active catalog node through contextual menu ordinals and canonical media triple; keep Track in lineage but out of selectable scopes.
RATIONALE = Stable, parser-independent selection; initial S5 scope is Course/Module/Lesson and Channel without scope expansion.
REUSED_COMPONENT = SQLiteCatalogRepository, catalog_nodes, catalog_node_identity, media_items uniqueness, existing Rich catalog navigation.
CHANGE_REQUIRED = Scoped active-lineage and completeness query; batch candidate query.
RISK = Catalog node IDs are local database identities; selection IDs are not portable between separately rebuilt databases.
```

### D2 — Share S4 evaluation and execution

```text
DECISION = Add a read-only S4-compatible physical evaluation for planning; invoke the existing SingleMediaDownloadApplication.download() unchanged for every pending item.
RATIONALE = Preview cannot call a method that starts transfer; a second downloader or second deduplication rule would diverge from S4.
REUSED_COMPONENT = DownloadRepository, SingleMediaDownloadApplication, destination_paths, S4 size/SHA-256/no-overwrite checks and persisted lifecycle.
CHANGE_REQUIRED = Read-only batch inspection and scoped batch query; share existing physical validity helpers; recheck at execution.
RISK = Preview can become stale; mandatory execution recheck and S4 ownership checks close the race.
```

### D3 — Keep the queue ephemeral and media state durable

```text
DECISION = Do not persist plan or queue rows in S5.
RATIONALE = Each media already has a unique durable S4 lifecycle; a queue can be recomputed without S6 resume semantics or a schema migration.
REUSED_COMPONENT = downloads unique media row, owner PID, failure category, file path, expected/downloaded bytes and SHA-256.
CHANGE_REQUIRED = Queue-local state aggregation and rerun planning.
RISK = Queue order and invocation-level summary are lost on process exit; per-media outcomes remain and the next invocation reconstructs safely.
```

### D4 — Bounded in-process workers

```text
DECISION = Allow one or two workers only, default to two, capped by pending item count.
RATIONALE = Matches SPRINTS and ENGINEERING_FOUNDATION while prohibiting unbounded task creation.
REUSED_COMPONENT = S4 per-media lock, SQLite unique ownership and process-owner guard.
CHANGE_REQUIRED = Worker CLI validation, bounded scheduler, three-attempt budget and cancellation coordination.
RISK = Two active media can increase disk pressure; known-byte preflight includes a one-GiB-or-ten-percent margin.
```

### D5 — Carry FloodWait duration across the gateway boundary

```text
DECISION = Translate FloodWait to a stable domain error carrying retry_after_seconds; queue owns cancellable wait and finite retry budget.
RATIONALE = Current adapter emits RATE_LIMITED without duration, while the approved engineering foundation requires the application to own a bounded wait/retry decision.
REUSED_COMPONENT = TelethonGateway error translation, DownloadGatewayError boundary, existing S4 execution path.
CHANGE_REQUIRED = Add safe retry-after data to gateway/application errors; enforce three attempts, 120-second cumulative wait per media, and shared process cooldown.
RISK = A missing retry duration cannot be safely waited or retried; the item ends as rate limited.
```

### D6 — No queue schema

```text
DECISION = Represent planned/waiting/running/cancelled only in current invocation; preserve existing downloads states as source of durable truth.
RATIONALE = Avoid duplicating media state and migration complexity; planned is not a transfer lifecycle transition.
REUSED_COMPONENT = Migration 004 and S4 state machine.
CHANGE_REQUIRED = Outcome mapping from in-memory queue state to existing per-media records.
RISK = There is no persisted batch audit record; adding one requires evidence that per-media recovery is insufficient.
```

## 10. Contract freeze and implementation gate

The user approved the fixed operating parameters for this activity:

```text
WORKERS_DEFAULT = 2
WORKERS_ALLOWED = 1..2
MAX_ATTEMPTS_PER_MEDIA = 3 / initial attempt included
FLOODWAIT_MAX_CUMULATIVE_WAIT_PER_MEDIA = 120 seconds
DISK_SAFETY_MARGIN = MAX(1 GiB, 10% of known pending bytes)
UNKNOWN_MEDIA_SIZE = EXCLUDE_FROM_INITIAL_TRANSFER_QUEUE
QUEUE_PERSISTENCE = EPHEMERAL
DOWNLOAD_STATE_PERSISTENCE = REUSE_S4
SELECTION = CONTEXTUAL_MENUS
CONTRACT_STATUS = APPROVED / FROZEN
```

The authorized implementation gate is offline only: synthetic fixtures, fake
gateway, temporary SQLite, and temporary filesystem. It does not authorize
Telegram, credentials, session, project SQLite, real media, or Git publication.
The implementation reuses the S4 transfer application and records and does not
expand into S6/S7/S8 or GUI. Formal S5 acceptance remains pending until the
requested focused tests, offline end-to-end, full regression, Ruff, diff check,
and continuity reconciliation pass. Real validation is a separate activity
requiring explicit authorization and remains not authorized.
