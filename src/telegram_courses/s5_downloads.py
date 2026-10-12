"""S5 deterministic planning and bounded execution over the S4 downloader."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sqlite3
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from telegram_courses.download_repository import (
    DownloadCandidate,
    DownloadRepository,
    _process_is_alive,
)
from telegram_courses.downloads import (
    DownloadError,
    SingleMediaDownloadApplication,
    _matches,
    _reject_reparse_path,
    destination_paths,
)

GIB = 1024**3
MAX_WORKERS = 2
MAX_ATTEMPTS = 3
FLOODWAIT_MAX_SECONDS = 120


@dataclass(frozen=True)
class DownloadSelection:
    channel_id: int
    scope: str = "channel"
    node_id: int | None = None


@dataclass(frozen=True)
class PlanItem:
    identity: tuple[int, int, int]
    candidate: DownloadCandidate | None
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class DownloadPlan:
    plan_id: str
    selection: DownloadSelection
    scope_title: str
    catalog_complete: bool
    lesson_count: int
    items: tuple[PlanItem, ...]

    @property
    def eligible(self) -> tuple[PlanItem, ...]:
        return tuple(item for item in self.items if item.candidate is not None)

    @property
    def pending(self) -> tuple[PlanItem, ...]:
        return tuple(item for item in self.eligible if item.status == "PENDING")

    @property
    def already_valid(self) -> tuple[PlanItem, ...]:
        return tuple(item for item in self.eligible if item.status == "ALREADY_VALID")

    @property
    def blocked(self) -> tuple[PlanItem, ...]:
        return tuple(item for item in self.items if item.status == "BLOCKED")

    @property
    def excluded(self) -> tuple[PlanItem, ...]:
        return tuple(item for item in self.items if item.status == "EXCLUDED")

    @property
    def pending_bytes(self) -> int:
        return sum(item.candidate.expected_bytes for item in self.pending if item.candidate)

    @property
    def safety_margin(self) -> int:
        return max(GIB, int(self.pending_bytes * 0.10))


def _connect_readonly(database: str | Path) -> sqlite3.Connection:
    path = Path(database).absolute()
    if not path.is_file():
        raise DownloadError("CATALOG_NOT_FOUND")
    db = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


class DownloadPlanner:
    def __init__(self, database: str | Path, download_root: str | Path) -> None:
        self.database = Path(database)
        self.download_root = Path(download_root).expanduser().absolute()

    def selectable_nodes(self, channel_id: int, scope: str) -> tuple[tuple[int, str], ...]:
        if scope not in {"course", "module", "lesson"}:
            raise DownloadError("INVALID_SELECTION")
        db = _connect_readonly(self.database)
        try:
            rows = db.execute(
                "SELECT id,parent_id,kind,title,ordinal,is_active FROM catalog_nodes "
                "WHERE channel_id=? ORDER BY COALESCE(ordinal,0),kind,id",
                (channel_id,),
            ).fetchall()
            by_id = {row["id"]: row for row in rows}
            labels: list[tuple[int, str]] = []
            for row in rows:
                if not row["is_active"] or row["kind"] != scope or not self._valid_lineage(row, by_id):
                    continue
                parts = [str(row["title"] or f"{scope.title()} {row['ordinal'] or ''}").strip()]
                parent_id = row["parent_id"]
                while parent_id in by_id:
                    parent = by_id[parent_id]
                    if parent["kind"] in {"course", "module"}:
                        parts.append(str(parent["title"] or parent["kind"].title()))
                    parent_id = parent["parent_id"]
                labels.append((row["id"], " / ".join(reversed(parts))))
            return tuple(labels)
        finally:
            db.close()

    @staticmethod
    def _valid_lineage(node: sqlite3.Row, by_id: dict[int, sqlite3.Row]) -> bool:
        kinds = [node["kind"]]
        parent_id = node["parent_id"]
        seen = {node["id"]}
        while parent_id is not None:
            if parent_id in seen or parent_id not in by_id:
                return False
            seen.add(parent_id)
            parent = by_id[parent_id]
            if not parent["is_active"]:
                return False
            kinds.append(parent["kind"])
            parent_id = parent["parent_id"]
        allowed = {
            "course": {("course",), ("course", "track")},
            "module": {("module",), ("module", "course"), ("module", "course", "track")},
            "lesson": {
                ("lesson",), ("lesson", "course"), ("lesson", "course", "track"),
                ("lesson", "module"), ("lesson", "module", "course"),
                ("lesson", "module", "course", "track"),
            },
        }
        return tuple(kinds) in allowed.get(node["kind"], set())

    async def build(self, selection: DownloadSelection) -> DownloadPlan:
        if selection.scope not in {"channel", "course", "module", "lesson"}:
            raise DownloadError("INVALID_SELECTION")
        if (selection.scope == "channel") != (selection.node_id is None):
            raise DownloadError("INVALID_SELECTION")
        db = _connect_readonly(self.database)
        try:
            db.execute("BEGIN")
            channel = db.execute(
                "SELECT title FROM channels WHERE telegram_chat_id=?", (selection.channel_id,)
            ).fetchone()
            if channel is None:
                raise DownloadError("CHANNEL_NOT_FOUND")
            catalog_run = db.execute(
                "SELECT id FROM catalog_runs WHERE channel_id=? ORDER BY finished_at DESC LIMIT 1",
                (selection.channel_id,),
            ).fetchone()
            if catalog_run is None:
                raise DownloadError("CATALOG_NOT_READY")
            nodes = db.execute(
                "SELECT id,parent_id,kind,ordinal,title,is_active FROM catalog_nodes "
                "WHERE channel_id=?", (selection.channel_id,),
            ).fetchall()
            by_id = {row["id"]: row for row in nodes}
            selected = None
            if selection.node_id is not None:
                selected = by_id.get(selection.node_id)
                if selected is None or not selected["is_active"] or selected["kind"] != selection.scope or not self._valid_lineage(selected, by_id):
                    raise DownloadError("INVALID_SELECTION")
            included_nodes: set[int] = set()
            lesson_nodes: dict[int, int] = {}
            for node in nodes:
                if node["kind"] != "lesson" or not node["is_active"] or not self._valid_lineage(node, by_id):
                    continue
                lineage = {node["id"]}
                parent_id = node["parent_id"]
                while parent_id in by_id:
                    lineage.add(parent_id)
                    parent_id = by_id[parent_id]["parent_id"]
                if selected is None or selected["id"] in lineage:
                    lesson_nodes[node["id"]] = node["id"]
                    included_nodes.update(lineage)
            scope_title = str(selected["title"] if selected else channel["title"] or f"Channel {selection.channel_id}")
            scan = db.execute(
                "SELECT status,stop_reason FROM scan_runs WHERE channel_id=? AND finished_at IS NOT NULL "
                "ORDER BY finished_at DESC LIMIT 1", (selection.channel_id,),
            ).fetchone()
            complete = bool(scan and scan["status"] == "COMPLETE" and not scan["stop_reason"])
            media = db.execute(
                "SELECT m.*,n.kind AS node_kind,n.is_active AS node_active FROM media_items m "
                "LEFT JOIN catalog_nodes n ON n.id=m.catalog_node_id "
                "WHERE m.channel_id=? ORDER BY m.telegram_message_id,m.media_ordinal,m.id",
                (selection.channel_id,),
            ).fetchall()
            records = {r["media_item_id"]: r for r in db.execute(
                "SELECT d.* FROM downloads d JOIN media_items m ON m.id=d.media_item_id WHERE m.channel_id=?",
                (selection.channel_id,),
            ).fetchall()}
            entries: list[tuple[tuple[object, ...], PlanItem]] = []
            seen: dict[tuple[int, int, int], tuple[int, int | None]] = {}
            for row in media:
                identity = (row["channel_id"], row["telegram_message_id"], row["media_ordinal"])
                node_id = row["catalog_node_id"]
                if node_id not in included_nodes:
                    if selection.scope == "channel":
                        reason = "INVALID_LINEAGE" if row["node_kind"] == "lesson" else "UNRESOLVED_OR_ORPHAN"
                        entries.append(((1, (), identity[1], identity[2]), PlanItem(identity, None, "EXCLUDED", reason)))
                    continue
                reason = None
                if row["kind"] != "DOCUMENT":
                    reason = "UNSUPPORTED_MEDIA"
                elif row["file_size_bytes"] is None:
                    reason = "UNKNOWN_SIZE"
                elif row["file_size_bytes"] < 0:
                    reason = "INVALID_SIZE"
                elif not row["telegram_media_id"]:
                    reason = "MISSING_MEDIA_ID"
                if reason:
                    entries.append(((1, (), identity[1], identity[2]), PlanItem(identity, None, "EXCLUDED", reason)))
                    continue
                prior = seen.get(identity)
                association = (node_id, row["file_size_bytes"])
                if prior is not None:
                    if prior != association:
                        entries.append(((1, (), identity[1], identity[2]), PlanItem(identity, None, "EXCLUDED", "AMBIGUOUS_IDENTITY")))
                    continue
                seen[identity] = association
                # S4 select_candidate returns the linked lesson for its physical
                # path. Keep preview paths identical to that accepted behavior;
                # full ancestry still governs scope validation and ordering.
                lesson = by_id[node_id]
                lineage = ((lesson["kind"], lesson["title"]),)
                candidate = DownloadCandidate(
                    media_item_id=row["id"], channel_id=row["channel_id"],
                    telegram_message_id=row["telegram_message_id"], media_ordinal=row["media_ordinal"],
                    telegram_media_id=row["telegram_media_id"], expected_bytes=row["file_size_bytes"],
                    original_filename=row["original_filename"], lineage=lineage,
                )
                record = records.get(candidate.media_item_id)
                status = "PENDING"
                if record is not None and record["state"] in {"DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING"}:
                    status = "BLOCKED" if _process_is_alive(record["owner_pid"]) else "PENDING"
                    if status == "BLOCKED":
                        reason = "TRANSFER_IN_PROGRESS"
                elif record is not None and record["state"] == "DOWNLOADED":
                    final, _ = destination_paths(self.download_root, candidate)
                    try:
                        _reject_reparse_path(self.download_root, final)
                    except DownloadError:
                        status, reason = "BLOCKED", "UNSAFE_PATH"
                    else:
                        if record["final_path"] != str(final):
                            status, reason = "BLOCKED", "DOWNLOAD_ROOT_CHANGED"
                        elif _matches(final, candidate.expected_bytes, record["sha256"]):
                            status = "ALREADY_VALID"
                        elif final.exists():
                            status, reason = "BLOCKED", "DOWNLOADED_FILE_MISMATCH"
                lineage_ids = []
                current = node_id
                while current in by_id:
                    lineage_ids.append(current)
                    current = by_id[current]["parent_id"]
                path_order = tuple(
                    by_id[nid]["ordinal"] or 0 for nid in reversed(lineage_ids)
                )
                entries.append(((0, path_order, identity[1], identity[2]), PlanItem(identity, candidate, status, reason)))
            entries.sort(key=lambda pair: pair[0])
            items = tuple(item for _, item in entries)
            lesson_count = len(lesson_nodes)
            canonical = {
                "selection": [selection.channel_id, selection.scope, selection.node_id],
                "entries": [list(item.identity) + ([item.candidate.telegram_media_id, item.candidate.expected_bytes] if item.candidate else [item.reason]) for item in items],
            }
            plan_id = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]
            db.commit()
            return DownloadPlan(plan_id, selection, scope_title, complete, lesson_count, items)
        finally:
            db.close()


@dataclass(frozen=True)
class QueueResult:
    outcomes: tuple[tuple[tuple[int, int, int], str, str | None], ...]
    transferred_bytes: int
    attempts: int
    cancelled: bool = False
    elapsed_seconds: float = 0.0

    @property
    def failed(self) -> int:
        return sum(status in {"FAILED", "BLOCKED"} for _, status, _ in self.outcomes)


class DownloadQueue:
    def __init__(
        self,
        repository: DownloadRepository,
        application: SingleMediaDownloadApplication,
        *,
        workers: int = 2,
        attempts_per_media: int = 3,
        free_space: Callable[[Path], int] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
        progress_callback: Callable[[dict[str, int]], None] | None = None,
        max_media_items: int | None = None,
        max_transfer_bytes: int | None = None,
    ) -> None:
        if type(workers) is not int or not 1 <= workers <= MAX_WORKERS:
            raise ValueError("workers must be 1 or 2")
        if type(attempts_per_media) is not int or not 1 <= attempts_per_media <= MAX_ATTEMPTS:
            raise ValueError("attempts_per_media must be between 1 and 3")
        if max_media_items is not None and (type(max_media_items) is not int or max_media_items <= 0):
            raise ValueError("max_media_items must be positive")
        if max_transfer_bytes is not None and (type(max_transfer_bytes) is not int or max_transfer_bytes <= 0):
            raise ValueError("max_transfer_bytes must be positive")
        self.repository, self.application = repository, application
        self.workers, self.attempts_per_media = workers, attempts_per_media
        self.free_space = free_space or (lambda path: shutil.disk_usage(path).free)
        self.sleep = sleep
        self.clock = clock
        self.progress_callback = progress_callback
        self.max_media_items = max_media_items
        self.max_transfer_bytes = max_transfer_bytes
        self._rate_lock = asyncio.Lock()
        self._cooldown_until = 0.0

    async def run(self, plan: DownloadPlan) -> QueueResult:
        selected_count = len(plan.items)
        if self.max_media_items is not None and selected_count > self.max_media_items:
            raise DownloadError("MEDIA_LIMIT_EXCEEDED")
        if self.max_transfer_bytes is not None:
            if plan.pending_bytes > self.max_transfer_bytes:
                raise DownloadError("TRANSFER_BUDGET_EXCEEDED")
            if any(item.reason == "UNKNOWN_SIZE" for item in plan.excluded):
                raise DownloadError("UNKNOWN_SIZE")
        started_at = self.clock()
        pending = list(plan.pending)
        outcomes: list[tuple[tuple[int, int, int], str, str | None]] = [
            (item.identity, "ALREADY_VALID", None) for item in plan.already_valid
        ]
        outcomes.extend((item.identity, "BLOCKED", item.reason) for item in plan.blocked)
        outcomes.extend((item.identity, "EXCLUDED", item.reason) for item in plan.excluded)
        states = {item.identity: item.status for item in plan.items}
        last_progress_by_item: dict[tuple[int, int, int], int] = {}
        progress_seen: set[tuple[int, int, int]] = set()
        chunk_seen: set[tuple[int, int, int]] = set()
        total_transferred_bytes = 0
        task_items: dict[asyncio.Task[None], tuple[int, int, int]] = {}
        task_reserved_bytes: dict[asyncio.Task[None], int] = {}
        budget_lock = asyncio.Lock()
        budget_consumed = 0
        budget_received = 0
        budget_uncertain = 0
        budget_reserved = 0

        def emit_progress() -> None:
            if self.progress_callback is None:
                return
            counts = {
                "total": len(plan.items),
                "pending": sum(state in {"PENDING", "WAITING"} for state in states.values()),
                "running": sum(state == "RUNNING" for state in states.values()),
                "completed": sum(state == "COMPLETED" for state in states.values()),
                "already_valid": sum(state == "ALREADY_VALID" for state in states.values()),
                "failed": sum(state == "FAILED" for state in states.values()),
                "blocked": sum(state == "BLOCKED" for state in states.values()),
                "excluded": sum(state == "EXCLUDED" for state in states.values()),
                "cancelled": sum(state == "CANCELLED" for state in states.values()),
                "bytes_transferred": total_transferred_bytes,
                "bytes_expected": sum(item.candidate.expected_bytes for item in plan.eligible if item.candidate),
                "elapsed_seconds": int(self.clock() - started_at),
                "bytes_per_second": int(total_transferred_bytes / max(0.001, self.clock() - started_at)),
            }
            self.progress_callback(counts)

        if not pending:
            emit_progress()
            return QueueResult(
                tuple(outcomes), 0, 0, False, self.clock() - started_at,
            )
        root = self.application.download_root.expanduser().absolute()
        probe = root
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        pending_bytes_left = plan.pending_bytes
        margin = plan.safety_margin
        required = pending_bytes_left + margin
        if self.free_space(probe) < required:
            raise DownloadError("INSUFFICIENT_DISK_SPACE")

        original_progress = self.application.progress_callback
        original_chunk_callback = getattr(self.application, "chunk_callback", None)
        original_chunk_reserver = getattr(self.application, "chunk_reserver", None)
        if self.max_transfer_bytes is not None:
            budget_limit = self.max_transfer_bytes

            class _Reservation:
                def __init__(self, task: asyncio.Task[None], amount: int) -> None:
                    self.task = task
                    self.amount = amount
                    self.settled = False

                def settle(self, consumed: int) -> None:
                    nonlocal budget_consumed, budget_received, budget_uncertain
                    nonlocal budget_reserved, stop_reason, total_transferred_bytes
                    if self.settled:
                        return
                    self.settled = True
                    reserved = task_reserved_bytes.get(self.task, 0)
                    if reserved < self.amount or consumed < 0:
                        stop_reason_local = "TRANSFER_BUDGET_STATE_INVALID"
                        states[task_items[self.task]] = "BLOCKED"
                        self.task.cancel()
                        raise DownloadError(stop_reason_local)
                    task_reserved_bytes[self.task] = reserved - self.amount
                    budget_reserved -= self.amount
                    budget_received += consumed
                    budget_consumed = budget_received + budget_uncertain
                    if budget_consumed + budget_reserved > budget_limit:
                        stop_reason = "TRANSFER_BUDGET_EXHAUSTED"
                        stop.set()
                    total_transferred_bytes = budget_received
                    emit_progress()

                def received(self, byte_count: int) -> None:
                    if byte_count > self.amount:
                        self.settle(byte_count)
                        raise DownloadError("TRANSFER_BUDGET_EXHAUSTED")
                    self.settle(byte_count)

                def release(self) -> None:
                    self.settle(0)

                def charge_uncertain(self) -> None:
                    nonlocal budget_consumed, budget_uncertain
                    nonlocal budget_reserved
                    if self.settled:
                        return
                    self.settled = True
                    reserved = task_reserved_bytes.get(self.task, 0)
                    if reserved < self.amount:
                        raise DownloadError("TRANSFER_BUDGET_STATE_INVALID")
                    task_reserved_bytes[self.task] = reserved - self.amount
                    budget_reserved -= self.amount
                    budget_uncertain += self.amount
                    budget_consumed = budget_received + budget_uncertain

            async def reserve_chunk(amount: int):
                nonlocal budget_reserved, stop_reason
                task = asyncio.current_task()
                if task is None or amount <= 0:
                    raise DownloadError("TRANSFER_BUDGET_STATE_INVALID")
                async with budget_lock:
                    if budget_consumed + budget_reserved + amount > self.max_transfer_bytes:
                        stop_reason = "TRANSFER_BUDGET_EXHAUSTED"
                        stop.set()
                        return None
                    budget_reserved += amount
                    task_reserved_bytes[task] = task_reserved_bytes.get(task, 0) + amount
                return _Reservation(task, amount)

            self.application.chunk_reserver = reserve_chunk
        if self.progress_callback is not None:
            def report_item_progress(current: int, _total: int) -> None:
                nonlocal total_transferred_bytes
                task = asyncio.current_task()
                identity = task_items.get(task) if task is not None else None
                if identity is not None and self.max_transfer_bytes is None and identity not in chunk_seen:
                    previous = last_progress_by_item.get(identity)
                    total_transferred_bytes += current if previous is None or current < previous else current - previous
                    last_progress_by_item[identity] = current
                    progress_seen.add(identity)
                if original_progress is not None:
                    original_progress(current, _total)
                emit_progress()
            self.application.progress_callback = report_item_progress
        if self.max_transfer_bytes is None and hasattr(self.application, "chunk_callback"):
            def report_received_chunk(byte_count: int) -> None:
                nonlocal total_transferred_bytes
                task = asyncio.current_task()
                identity = task_items.get(task) if task is not None else None
                if identity is not None:
                    total_transferred_bytes += byte_count
                    chunk_seen.add(identity)
                    progress_seen.add(identity)
                    emit_progress()
                if original_chunk_callback is not None:
                    original_chunk_callback(byte_count)
            self.application.chunk_callback = report_received_chunk
        emit_progress()
        next_item = 0
        attempts_total = 0
        stop = asyncio.Event()
        stop_reason = "INSUFFICIENT_DISK_SPACE"
        async def worker() -> None:
            nonlocal next_item, attempts_total, pending_bytes_left, total_transferred_bytes
            nonlocal budget_reserved, budget_consumed, budget_received
            nonlocal budget_uncertain, stop_reason
            while not stop.is_set():
                if next_item >= len(pending):
                    return
                item = pending[next_item]
                next_item += 1
                assert item.candidate is not None
                task = asyncio.current_task()
                if task is not None:
                    task_items[task] = item.identity
                states[item.identity] = "RUNNING"
                emit_progress()
                async with self._rate_lock:
                    pending_bytes_left = max(0, pending_bytes_left - item.candidate.expected_bytes)
                last_error: DownloadError | None = None
                waits = 0
                for attempt in range(self.attempts_per_media):
                    if stop.is_set():
                        outcomes.append((item.identity, "BLOCKED", stop_reason))
                        states[item.identity] = "BLOCKED"
                        emit_progress()
                        return
                    try:
                        waited, cooldown_exceeded = await self._wait_for_global_cooldown(
                            stop, FLOODWAIT_MAX_SECONDS - waits
                        )
                        waits += int(waited + 0.999)
                        if cooldown_exceeded:
                            last_error = DownloadError("RATE_LIMITED")
                            break
                        if stop.is_set():
                            outcomes.append((item.identity, "BLOCKED", stop_reason))
                            states[item.identity] = "BLOCKED"
                            emit_progress()
                            return
                        probe_path = root if root.exists() else probe
                        if self.free_space(probe_path) < pending_bytes_left + margin:
                            raise DownloadError("INSUFFICIENT_DISK_SPACE")
                        attempts_total += 1
                        last_progress_by_item.pop(item.identity, None)
                        progress_seen.discard(item.identity)
                        try:
                            result = await self.application.download(*item.identity)
                        finally:
                            if self.max_transfer_bytes is not None:
                                task = asyncio.current_task()
                                async with budget_lock:
                                    unused = task_reserved_bytes.pop(task, 0)
                                    budget_reserved -= unused
                                    if unused:
                                        # An adapter that exits with an open lease cannot prove
                                        # whether the in-flight response delivered payload.
                                        budget_uncertain += unused
                                        budget_consumed = budget_received + budget_uncertain
                        if (
                            self.max_transfer_bytes is None
                            and item.identity not in progress_seen
                            and result.result == "DOWNLOADED"
                        ):
                            total_transferred_bytes += result.transferred_bytes
                        states[item.identity] = "COMPLETED" if result.result != "ALREADY_DOWNLOADED" else "ALREADY_VALID"
                        outcomes.append((item.identity, "COMPLETED" if result.result != "ALREADY_DOWNLOADED" else "ALREADY_VALID", None))
                        emit_progress()
                        last_error = None
                        break
                    except DownloadError as error:
                        last_error = error
                        if error.category == "TRANSFER_BUDGET_EXHAUSTED":
                            stop_reason = error.category
                            stop.set()
                            break
                        if error.category == "RATE_LIMITED":
                            retry_after = getattr(error, "retry_after_seconds", None)
                            if type(retry_after) is not int or retry_after < 0:
                                break
                            delay = max(1, retry_after)
                            async with self._rate_lock:
                                self._cooldown_until = max(self._cooldown_until, self.clock() + delay)
                            if waits + delay > FLOODWAIT_MAX_SECONDS or attempt + 1 >= self.attempts_per_media:
                                break
                            continue
                        if error.category not in {"NETWORK", "GATEWAY_FAILURE", "TRANSFER_FAILED"} or attempt + 1 >= self.attempts_per_media:
                            break
                    except Exception:
                        last_error = DownloadError("TRANSFER_FAILED")
                        break
                    except asyncio.CancelledError:
                        raise
                if last_error is not None:
                    if last_error.category == "INSUFFICIENT_DISK_SPACE":
                        stop.set()
                    blocked = last_error.category in {
                        "INSUFFICIENT_DISK_SPACE", "TRANSFER_BUDGET_EXHAUSTED",
                    }
                    states[item.identity] = "BLOCKED" if blocked else "FAILED"
                    outcomes.append((item.identity, "BLOCKED" if blocked else "FAILED", last_error.category))
                    emit_progress()
        tasks = [asyncio.create_task(worker()) for _ in range(min(self.workers, len(pending)))]
        try:
            await asyncio.gather(*tasks)
            if stop.is_set():
                completed_identities = {identity for identity, _, _ in outcomes}
                for item in pending:
                    if item.identity not in completed_identities:
                        outcomes.append((item.identity, "BLOCKED", stop_reason))
                        states[item.identity] = "BLOCKED"
                emit_progress()
        except asyncio.CancelledError:
            stop.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for item in pending:
                if not any(identity == item.identity for identity, _, _ in outcomes):
                    outcomes.append((item.identity, "CANCELLED", "CANCELLED"))
                    states[item.identity] = "CANCELLED"
            emit_progress()
            return QueueResult(
                tuple(outcomes), total_transferred_bytes, attempts_total, True,
                self.clock() - started_at,
            )
        finally:
            self.application.progress_callback = original_progress
            if hasattr(self.application, "chunk_callback"):
                self.application.chunk_callback = original_chunk_callback
            self.application.chunk_reserver = original_chunk_reserver
            task_items.clear()
            task_reserved_bytes.clear()
        return QueueResult(
            tuple(outcomes), total_transferred_bytes, attempts_total, False,
            self.clock() - started_at,
        )

    async def _wait_for_global_cooldown(
        self, stop: asyncio.Event, remaining_budget: int
    ) -> tuple[float, bool]:
        started = self.clock()
        while not stop.is_set():
            async with self._rate_lock:
                remaining = self._cooldown_until - self.clock()
            if remaining <= 0:
                return self.clock() - started, False
            budget_left = remaining_budget - (self.clock() - started)
            if budget_left <= 0:
                return self.clock() - started, True
            await self.sleep(min(remaining, budget_left, 0.25))
        return self.clock() - started, False
