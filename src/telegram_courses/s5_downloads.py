"""S5 deterministic planning and bounded execution over the S4 downloader."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import shutil
import sqlite3
import time
import uuid
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
from telegram_courses.operational_logging import emit_operational_event

GIB = 1024**3
MAX_WORKERS = 2
MAX_ATTEMPTS = 3
FLOODWAIT_MAX_SECONDS = 120


@dataclass(frozen=True)
class DownloadSelection:
    channel_id: int
    scope: str = "channel"
    node_id: int | None = None
    # None preserves the frozen S5 scope behavior. A tuple narrows a course
    # plan to these stable catalog identities, in planner order at build time.
    media_identities: tuple[tuple[int, int, int], ...] | None = None


@dataclass(frozen=True)
class PlanItem:
    identity: tuple[int, int, int]
    candidate: DownloadCandidate | None
    status: str
    reason: str | None = None
    part_bytes: int = 0
    wire_offset: int = 0
    overlap_bytes: int = 0
    estimated_payload_bytes: int | None = None
    estimated_additional_disk_bytes: int | None = None
    observed_size_bytes: int | None = None


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
        return tuple(
            item for item in self.eligible
            if item.status in {"PENDING", "CONDITIONAL_RESUME_CANDIDATE"}
        )

    @property
    def already_valid(self) -> tuple[PlanItem, ...]:
        return tuple(item for item in self.eligible if item.status == "ALREADY_VALID")

    @property
    def completed_v2(self) -> tuple[PlanItem, ...]:
        return tuple(item for item in self.eligible if item.status == "COMPLETED_V2")

    @property
    def blocked(self) -> tuple[PlanItem, ...]:
        return tuple(item for item in self.items if item.status == "BLOCKED")

    @property
    def excluded(self) -> tuple[PlanItem, ...]:
        return tuple(item for item in self.items if item.status == "EXCLUDED")

    @property
    def pending_bytes(self) -> int:
        return sum(
            item.estimated_payload_bytes
            if item.estimated_payload_bytes is not None
            else item.candidate.expected_bytes
            for item in self.pending if item.candidate
        )

    @property
    def additional_disk_bytes(self) -> int:
        return sum(
            item.estimated_additional_disk_bytes
            if item.estimated_additional_disk_bytes is not None
            else item.candidate.expected_bytes
            for item in self.pending if item.candidate
        )

    @property
    def safety_margin(self) -> int:
        return max(GIB, int(self.additional_disk_bytes * 0.10))


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
        requested_identities = selection.media_identities
        requested_identity_set: set[tuple[int, int, int]] | None = None
        if requested_identities is not None:
            if (
                selection.scope != "course"
                or type(requested_identities) is not tuple
                or not requested_identities
            ):
                raise DownloadError("INVALID_SELECTION")
            if any(
                type(identity) is not tuple
                or len(identity) != 3
                or any(type(part) is not int for part in identity)
                or identity[0] != selection.channel_id
                or identity[1] <= 0
                or identity[2] < 0
                for identity in requested_identities
            ) or len(set(requested_identities)) != len(requested_identities):
                raise DownloadError("INVALID_SELECTION")
            requested_identity_set = set(requested_identities)
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
            download_columns = {
                column["name"] for column in db.execute("PRAGMA table_info(downloads)")
            }
            media_columns = {
                column["name"] for column in db.execute("PRAGMA table_info(media_items)")
            }
            has_corrective_schema = {
                "remote_identity_media_id", "remote_identity_kind", "remote_identity_size",
                "remote_identity_provenance",
            }.issubset(download_columns) and "remote_observation_state" in media_columns
            evidence_table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='s6_v2_evidence'"
            ).fetchone()
            v2_evidence = {}
            if evidence_table is not None:
                v2_evidence = {row["media_item_id"]: row for row in db.execute(
                    "SELECT e.* FROM s6_v2_evidence e JOIN media_items m "
                    "ON m.id=e.media_item_id WHERE m.channel_id=?",
                    (selection.channel_id,),
                ).fetchall()}
            entries: list[tuple[tuple[object, ...], PlanItem]] = []
            seen: dict[tuple[int, int, int], tuple[int, int | None]] = {}
            observed_identity_counts: dict[tuple[int, int, int], int] = {}
            scoped_identity_counts: dict[tuple[int, int, int], int] = {}
            selected_lesson_ids: set[int] = set()
            for row in media:
                identity = (row["channel_id"], row["telegram_message_id"], row["media_ordinal"])
                if requested_identity_set is not None:
                    if identity not in requested_identity_set:
                        continue
                    observed_identity_counts[identity] = observed_identity_counts.get(identity, 0) + 1
                node_id = row["catalog_node_id"]
                if node_id not in included_nodes:
                    if requested_identity_set is not None:
                        continue
                    if selection.scope == "channel":
                        reason = "INVALID_LINEAGE" if row["node_kind"] == "lesson" else "UNRESOLVED_OR_ORPHAN"
                        entries.append(((1, (), identity[1], identity[2]), PlanItem(
                            identity, None, "EXCLUDED", reason,
                            observed_size_bytes=row["file_size_bytes"],
                        )))
                    continue
                if requested_identity_set is not None:
                    if (
                        node_id not in by_id
                        or by_id[node_id]["kind"] != "lesson"
                        or "catalog_active" in media_columns and row["catalog_active"] is False
                    ):
                        continue
                    scoped_identity_counts[identity] = scoped_identity_counts.get(identity, 0) + 1
                if node_id in by_id and by_id[node_id]["kind"] == "lesson":
                    selected_lesson_ids.add(node_id)
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
                    entries.append(((1, (), identity[1], identity[2]), PlanItem(
                        identity, None, "EXCLUDED", reason,
                        observed_size_bytes=row["file_size_bytes"],
                    )))
                    continue
                prior = seen.get(identity)
                association = (node_id, row["file_size_bytes"])
                if prior is not None:
                    if prior != association:
                        entries.append(((1, (), identity[1], identity[2]), PlanItem(
                            identity, None, "EXCLUDED", "AMBIGUOUS_IDENTITY",
                            observed_size_bytes=row["file_size_bytes"],
                        )))
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
                part_bytes = wire_offset = overlap_bytes = 0
                estimated_payload = candidate.expected_bytes
                estimated_disk = candidate.expected_bytes
                identity_changed = record is not None and has_corrective_schema and record["remote_identity_provenance"] == "CAPTURED_AT_START" and (
                    record["remote_identity_media_id"] != row["telegram_media_id"]
                    or record["remote_identity_kind"] != row["kind"]
                    or record["remote_identity_size"] != row["file_size_bytes"]
                )
                if not has_corrective_schema:
                    status, reason = "BLOCKED", "SCHEMA_MIGRATION_REQUIRED"
                elif row["remote_observation_state"] != "OBSERVED":
                    status, reason = "BLOCKED", "MEDIA_NOT_OBSERVED"
                elif record is not None and record["remote_identity_provenance"] != "CAPTURED_AT_START":
                    status, reason = "BLOCKED", "IDENTITY_SNAPSHOT_UNVERIFIED"
                elif identity_changed:
                    status, reason = "BLOCKED", "MEDIA_IDENTITY_CHANGED"
                elif record is not None and record["state"] in {"DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING"}:
                    owner_state = _process_is_alive(record["owner_pid"])
                    status = "BLOCKED" if record["owner_pid"] is None or owner_state is not False else "PENDING"
                    if status == "BLOCKED":
                        reason = "OWNERSHIP_AMBIGUOUS" if owner_state is None else "TRANSFER_IN_PROGRESS"
                elif record is not None and record["state"] == "FAILED_RETRYABLE" and record["owner_pid"] is not None:
                    owner_state = _process_is_alive(record["owner_pid"])
                    if owner_state is not False:
                        status, reason = "BLOCKED", (
                            "OWNERSHIP_AMBIGUOUS" if owner_state is None else "TRANSFER_IN_PROGRESS"
                        )
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
                elif record is not None and record["state"] == "COMPLETED_V2":
                    evidence = v2_evidence.get(candidate.media_item_id)
                    final, _ = destination_paths(self.download_root, candidate)
                    if (
                        evidence is None
                        or evidence["channel_id"] != candidate.channel_id
                        or evidence["telegram_message_id"] != candidate.telegram_message_id
                        or evidence["media_ordinal"] != candidate.media_ordinal
                        or evidence["telegram_media_id"] != candidate.telegram_media_id
                        or evidence["expected_bytes"] != candidate.expected_bytes
                        or evidence["final_path"] != str(final)
                        or evidence["schema_version"] != 1
                        or evidence["contract_version"] != 2
                        or evidence["evidence_version"] != 1
                        or evidence["evidence_class"] not in {"OPERATIONAL_ONLY", "REFERENCE_MATCH"}
                        or evidence["remote_hash_class"] not in {
                            None, "REMOTE_HASH_FULL", "REMOTE_HASH_PARTIAL",
                            "REMOTE_HASH_ABSENT", "REMOTE_HASH_UNVERIFIABLE_EOF",
                        }
                        or not _matches(final, candidate.expected_bytes, evidence["final_sha256"])
                    ):
                        status, reason = "BLOCKED", "UNKNOWN_LEGACY"
                    else:
                        status, reason = "COMPLETED_V2", evidence["evidence_class"]
                if status == "PENDING":
                    final, partial = destination_paths(self.download_root, candidate)
                    if status == "PENDING":
                        try:
                            _reject_reparse_path(self.download_root, partial)
                        except DownloadError:
                            status, reason = "BLOCKED", "UNSAFE_PATH"
                        else:
                            if partial.exists() and record is None:
                                status, reason = "BLOCKED", "UNOWNED_PARTIAL_EXISTS"
                            elif partial.exists():
                                if (
                                    record["partial_path"] != str(partial)
                                    or record["final_path"] != str(final)
                                    or partial.is_symlink() or not partial.is_file()
                                ):
                                    status, reason = "BLOCKED", "UNOWNED_PARTIAL_EXISTS"
                                elif record["state"] not in {
                                    "FAILED_RETRYABLE", "DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING"
                                }:
                                    status, reason = "BLOCKED", "PARTIAL_STATE_INVALID"
                                else:
                                    part_bytes = partial.stat().st_size
                                    if part_bytes > candidate.expected_bytes:
                                        status, reason = "BLOCKED", "PARTIAL_SIZE_EXCEEDED"
                                    else:
                                        wire_offset = (part_bytes // (256 * 1024)) * (256 * 1024)
                                        overlap_bytes = part_bytes - wire_offset
                                        estimated_payload = candidate.expected_bytes - wire_offset
                                        estimated_disk = candidate.expected_bytes - part_bytes
                                        status, reason = "CONDITIONAL_RESUME_CANDIDATE", None
                lineage_ids = []
                current = node_id
                while current in by_id:
                    lineage_ids.append(current)
                    current = by_id[current]["parent_id"]
                path_order = tuple(
                    by_id[nid]["ordinal"] or 0 for nid in reversed(lineage_ids)
                )
                entries.append(((0, path_order, identity[1], identity[2]), PlanItem(
                    identity, candidate, status, reason, part_bytes, wire_offset,
                    overlap_bytes, estimated_payload, estimated_disk,
                    row["file_size_bytes"],
                )))
            if requested_identity_set is not None and any(
                observed_identity_counts.get(identity, 0) != 1
                or scoped_identity_counts.get(identity, 0) != 1
                for identity in requested_identity_set
            ):
                raise DownloadError("INVALID_SELECTION")
            entries.sort(key=lambda pair: pair[0])
            items = tuple(item for _, item in entries)
            lesson_count = (
                len(selected_lesson_ids)
                if requested_identity_set is not None
                else len(lesson_nodes)
            )
            selection_key: object = [selection.channel_id, selection.scope, selection.node_id]
            if requested_identities is not None:
                selection_key = {
                    "scope": selection_key,
                    "mode": "EXPLICIT_IDENTITIES",
                    "identities": [list(item.identity) for item in items],
                }
            canonical = {
                "selection": selection_key,
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
    budget_consumed_bytes: int | None = None
    budget_uncertain_bytes: int = 0

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
        random_uniform: Callable[[float, float], float] = random.uniform,
        clock: Callable[[], float] = time.monotonic,
        progress_callback: Callable[[dict[str, int]], None] | None = None,
        max_media_items: int | None = None,
        max_transfer_bytes: int | None = None,
        integrity_mode: str = "REMOTE_HASH_REQUIRED",
        reference_manifest_path: str | Path | None = None,
        queue_accounting: object | None = None,
    ) -> None:
        if type(workers) is not int or not 1 <= workers <= MAX_WORKERS:
            raise ValueError("workers must be 1 or 2")
        if type(attempts_per_media) is not int or not 1 <= attempts_per_media <= MAX_ATTEMPTS:
            raise ValueError("attempts_per_media must be between 1 and 3")
        if max_media_items is not None and (type(max_media_items) is not int or max_media_items <= 0):
            raise ValueError("max_media_items must be positive")
        if max_transfer_bytes is not None and (type(max_transfer_bytes) is not int or max_transfer_bytes <= 0):
            raise ValueError("max_transfer_bytes must be positive")
        if integrity_mode not in {"REMOTE_HASH_REQUIRED", "OPERATIONAL_ONLY", "TRUSTED_REFERENCE"}:
            raise ValueError("invalid integrity mode")
        if integrity_mode == "TRUSTED_REFERENCE" and reference_manifest_path is None:
            raise ValueError("TRUSTED_REFERENCE requires a manifest")
        self.repository, self.application = repository, application
        self.workers, self.attempts_per_media = workers, attempts_per_media
        self.free_space = free_space or (lambda path: shutil.disk_usage(path).free)
        self.sleep = sleep
        self.random_uniform = random_uniform
        self.clock = clock
        self.progress_callback = progress_callback
        self.max_media_items = max_media_items
        self.max_transfer_bytes = max_transfer_bytes
        self.integrity_mode = integrity_mode
        self.reference_manifest_path = reference_manifest_path
        self.queue_accounting = queue_accounting
        self._rate_lock = asyncio.Lock()
        self._cooldown_until = 0.0

    async def run(self, plan: DownloadPlan) -> QueueResult:
        if self.queue_accounting is not None:
            if self.max_transfer_bytes is None:
                raise DownloadError("S9_ACCOUNTING_BUDGET_REQUIRED")
            try:
                self.queue_accounting.validate_queue(
                    workers=self.workers,
                    attempts_per_media=self.attempts_per_media,
                )
                self.queue_accounting.validate_plan(plan)
            except Exception:
                raise DownloadError("S9_ACCOUNTING_FAILED") from None
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
        queue_invocation_id = uuid.uuid4().hex
        outcomes: list[tuple[tuple[int, int, int], str, str | None]] = [
            (item.identity, "ALREADY_VALID", None) for item in plan.already_valid
        ]
        completed_v2_states: dict[tuple[int, int, int], str] = {}
        for item in plan.completed_v2:
            if (
                self.integrity_mode == "OPERATIONAL_ONLY"
                and item.reason == "OPERATIONAL_ONLY"
            ):
                status, reason = "ALREADY_COMPLETED_V2", item.reason
            elif (
                self.integrity_mode == "TRUSTED_REFERENCE"
                and item.reason == "REFERENCE_MATCH"
            ):
                status, reason = "BLOCKED", "V2_COMPLETION_REQUIRES_REFERENCE_REVALIDATION"
            else:
                status, reason = "BLOCKED", "V2_COMPLETION_MODE_MISMATCH"
            outcomes.append((item.identity, status, reason))
            completed_v2_states[item.identity] = status
        outcomes.extend((item.identity, "BLOCKED", item.reason) for item in plan.blocked)
        outcomes.extend((item.identity, "EXCLUDED", item.reason) for item in plan.excluded)
        states = {item.identity: item.status for item in plan.items}
        states.update(completed_v2_states)
        last_progress_by_item: dict[tuple[int, int, int], int] = {}
        progress_seen: set[tuple[int, int, int]] = set()
        chunk_seen: set[tuple[int, int, int]] = set()
        total_transferred_bytes = 0
        task_items: dict[asyncio.Task[None], tuple[int, int, int]] = {}
        task_reserved_bytes: dict[asyncio.Task[None], int] = {}
        task_accounting_leases: dict[asyncio.Task[None], set[object]] = {}
        budget_lock = asyncio.Lock()
        budget_consumed = 0
        budget_received = 0
        budget_uncertain = 0
        budget_reserved = 0

        def reserve_accounting(task: asyncio.Task[None], amount: int):
            if self.queue_accounting is None:
                return None
            identity = task_items.get(task)
            if identity is None:
                raise DownloadError("S9_ACCOUNTING_FAILED")
            try:
                lease = self.queue_accounting.reserve(identity, amount)
            except Exception:
                raise DownloadError("S9_ACCOUNTING_FAILED") from None
            if not all(callable(getattr(lease, name, None)) for name in (
                "received", "release", "charge_uncertain",
            )):
                raise DownloadError("S9_ACCOUNTING_FAILED")
            task_accounting_leases.setdefault(task, set()).add(lease)
            return lease

        def settle_accounting(task: asyncio.Task[None], lease: object, method: str, *args: object) -> None:
            if self.queue_accounting is None:
                return
            try:
                getattr(lease, method)(*args)
            except Exception:
                raise DownloadError("S9_ACCOUNTING_FAILED") from None
            leases = task_accounting_leases.get(task)
            if leases is not None:
                leases.discard(lease)
                if not leases:
                    task_accounting_leases.pop(task, None)

        def charge_open_accounting(task: asyncio.Task[None]) -> None:
            leases = tuple(task_accounting_leases.get(task, ()))
            for lease in leases:
                if getattr(lease, "settled", False):
                    task_accounting_leases[task].discard(lease)
                    continue
                try:
                    settle_accounting(task, lease, "charge_uncertain")
                except DownloadError:
                    # The durable ledger has already failed closed; preserve the
                    # original transfer result and prevent subsequent work.
                    nonlocal_stop("S9_ACCOUNTING_FAILED")

        def nonlocal_stop(reason: str) -> None:
            nonlocal stop_reason
            stop_reason = reason
            stop.set()

        def emit_progress() -> None:
            if self.progress_callback is None:
                return
            counts = {
                "total": len(plan.items),
                "pending": sum(state in {"PENDING", "WAITING", "CONDITIONAL_RESUME_CANDIDATE"} for state in states.values()),
                "running": sum(state == "RUNNING" for state in states.values()),
                "completed": sum(state in {"COMPLETED", "COMPLETED_V2", "RECOVERED_V2"} for state in states.values()),
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
            if self.max_transfer_bytes is not None:
                counts["budget_consumed_bytes"] = budget_consumed
                counts["budget_uncertain_bytes"] = budget_uncertain
            self.progress_callback(counts)

        if not pending:
            emit_progress()
            return QueueResult(
                tuple(outcomes), 0, 0, False, self.clock() - started_at,
                0 if self.max_transfer_bytes is not None else None, 0,
            )
        root = self.application.download_root.expanduser().absolute()
        probe = root
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        pending_bytes_left = plan.additional_disk_bytes
        margin = plan.safety_margin
        required = pending_bytes_left + margin
        if self.free_space(probe) < required:
            raise DownloadError("INSUFFICIENT_DISK_SPACE")

        original_progress = self.application.progress_callback
        original_chunk_callback = getattr(self.application, "chunk_callback", None)
        original_chunk_reserver = getattr(self.application, "chunk_reserver", None)
        original_operation_reserver = getattr(self.application, "operation_reserver", None)
        original_pre_append_check = getattr(self.application, "pre_append_check", None)
        completed_for_space: set[tuple[int, int, int]] = set()
        if hasattr(self.application, "pre_append_check"):
            async def recheck_space(additional_bytes: int) -> bool:
                task = asyncio.current_task()
                identity = task_items.get(task) if task is not None else None
                other_bytes = sum(
                    (item.estimated_additional_disk_bytes
                     if item.estimated_additional_disk_bytes is not None
                     else item.candidate.expected_bytes)
                    for item in pending
                    if item.candidate is not None and item.identity != identity
                    and item.identity not in completed_for_space
                )
                probe_path = root if root.exists() else probe
                return self.free_space(probe_path) >= other_bytes + additional_bytes + margin

            self.application.pre_append_check = recheck_space
        if self.max_transfer_bytes is not None:
            budget_limit = self.max_transfer_bytes

            class _Reservation:
                def __init__(self, task: asyncio.Task[None], amount: int, accounting_lease) -> None:
                    self.task = task
                    self.amount = amount
                    self.settled = False
                    self.accounting_lease = accounting_lease

                def settle(self, consumed: int) -> None:
                    nonlocal budget_consumed, budget_received, budget_uncertain
                    nonlocal budget_reserved, stop_reason, total_transferred_bytes
                    if self.settled:
                        return
                    reserved = task_reserved_bytes.get(self.task, 0)
                    if reserved < self.amount or consumed < 0:
                        stop_reason_local = "TRANSFER_BUDGET_STATE_INVALID"
                        states[task_items[self.task]] = "BLOCKED"
                        self.task.cancel()
                        raise DownloadError(stop_reason_local)
                    if self.accounting_lease is not None:
                        try:
                            settle_accounting(
                                self.task, self.accounting_lease, "received", consumed,
                            )
                        except DownloadError:
                            nonlocal_stop("S9_ACCOUNTING_FAILED")
                            raise
                    self.settled = True
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
                    if self.accounting_lease is not None:
                        try:
                            settle_accounting(
                                self.task, self.accounting_lease, "charge_uncertain",
                            )
                        except DownloadError:
                            nonlocal_stop("S9_ACCOUNTING_FAILED")
                            raise
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
                    try:
                        accounting_lease = reserve_accounting(task, amount)
                    except DownloadError:
                        budget_reserved -= amount
                        task_reserved_bytes[task] -= amount
                        nonlocal_stop("S9_ACCOUNTING_FAILED")
                        raise
                return _Reservation(task, amount, accounting_lease)

            self.application.chunk_reserver = reserve_chunk

            class _OperationPool:
                def __init__(self, task: asyncio.Task[None], amount: int) -> None:
                    self.task = task
                    self.remaining = amount
                    self.closed = False

                async def reserve_chunk(self, amount: int):
                    nonlocal budget_reserved, budget_received, budget_uncertain
                    nonlocal budget_consumed, total_transferred_bytes
                    if self.closed or type(amount) is not int or amount <= 0 or amount > self.remaining:
                        return None
                    self.remaining -= amount
                    pool = self

                    class _ChildReservation:
                        settled = False
                        accounting_lease = None

                        def __init__(self) -> None:
                            self.accounting_lease = reserve_accounting(pool.task, amount)

                        def _settle(self, consumed: int, uncertain: bool = False) -> None:
                            nonlocal budget_reserved, budget_received, budget_uncertain
                            nonlocal budget_consumed, total_transferred_bytes
                            if self.settled:
                                return
                            if self.accounting_lease is not None:
                                try:
                                    settle_accounting(
                                        pool.task,
                                        self.accounting_lease,
                                        "charge_uncertain" if uncertain else "received",
                                        *(() if uncertain else (consumed,)),
                                    )
                                except DownloadError:
                                    nonlocal_stop("S9_ACCOUNTING_FAILED")
                                    raise
                            self.settled = True
                            held = task_reserved_bytes.get(pool.task, 0)
                            if held < amount or budget_reserved < amount:
                                raise DownloadError("TRANSFER_BUDGET_STATE_INVALID")
                            task_reserved_bytes[pool.task] = held - amount
                            budget_reserved -= amount
                            if uncertain:
                                budget_uncertain += amount
                            else:
                                budget_received += consumed
                                total_transferred_bytes = budget_received
                            budget_consumed = budget_received + budget_uncertain
                            if budget_consumed + budget_reserved > budget_limit:
                                raise DownloadError("TRANSFER_BUDGET_STATE_INVALID")
                            emit_progress()

                        def received(self, byte_count: int) -> None:
                            if type(byte_count) is not int or not 0 <= byte_count <= amount:
                                self._settle(0, uncertain=True)
                                raise DownloadError("TRANSFER_BUDGET_STATE_INVALID")
                            self._settle(byte_count)

                        def release(self) -> None:
                            self._settle(0)

                        def charge_uncertain(self) -> None:
                            self._settle(0, uncertain=True)

                    return _ChildReservation()

                async def close(self) -> None:
                    nonlocal budget_reserved
                    if self.closed:
                        return
                    self.closed = True
                    held = task_reserved_bytes.get(self.task, 0)
                    if held < self.remaining or budget_reserved < self.remaining:
                        raise DownloadError("TRANSFER_BUDGET_STATE_INVALID")
                    task_reserved_bytes[self.task] = held - self.remaining
                    budget_reserved -= self.remaining
                    self.remaining = 0

            async def reserve_operation(amount: int):
                nonlocal budget_reserved, stop_reason
                task = asyncio.current_task()
                if task is None or type(amount) is not int or amount < 0:
                    raise DownloadError("TRANSFER_BUDGET_STATE_INVALID")
                if amount == 0:
                    return _OperationPool(task, 0)
                async with budget_lock:
                    if budget_consumed + budget_reserved + amount > budget_limit:
                        stop_reason = "BUDGET_BLOCK"
                        stop.set()
                        return None
                    budget_reserved += amount
                    task_reserved_bytes[task] = task_reserved_bytes.get(task, 0) + amount
                return _OperationPool(task, amount)

            self.application.operation_reserver = reserve_operation
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
                    item_disk_bytes = (
                        item.estimated_additional_disk_bytes
                        if item.estimated_additional_disk_bytes is not None
                        else item.candidate.expected_bytes
                    )
                    pending_bytes_left = max(0, pending_bytes_left - item_disk_bytes)
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
                            last_error = DownloadError(
                                "REMOTE_HASH_UNAVAILABLE"
                                if last_error is not None and last_error.failure_phase == "REMOTE_HASH"
                                else "RATE_LIMITED",
                                failure_phase=(
                                    "REMOTE_HASH"
                                    if last_error is not None and last_error.failure_phase == "REMOTE_HASH"
                                    else None
                                ),
                            )
                            break
                        if stop.is_set():
                            outcomes.append((item.identity, "BLOCKED", stop_reason))
                            states[item.identity] = "BLOCKED"
                            emit_progress()
                            return
                        probe_path = root if root.exists() else probe
                        if self.queue_accounting is not None:
                            try:
                                self.queue_accounting.check_disk(
                                    probe_path,
                                    pending_bytes=pending_bytes_left + item_disk_bytes,
                                    free_space=self.free_space,
                                )
                            except Exception as error:
                                failure = (
                                    "INSUFFICIENT_DISK_SPACE"
                                    if str(error) == "INSUFFICIENT_DISK_SPACE"
                                    else "S9_ACCOUNTING_FAILED"
                                )
                                raise DownloadError(failure) from None
                        if self.free_space(probe_path) < pending_bytes_left + margin:
                            raise DownloadError("INSUFFICIENT_DISK_SPACE")
                        if self.queue_accounting is not None:
                            try:
                                self.queue_accounting.begin_attempt(item.identity)
                            except Exception:
                                last_error = DownloadError("S9_ACCOUNTING_FAILED")
                                nonlocal_stop("S9_ACCOUNTING_FAILED")
                                break
                        attempts_total += 1
                        last_progress_by_item.pop(item.identity, None)
                        progress_seen.discard(item.identity)
                        try:
                            if self.integrity_mode == "REMOTE_HASH_REQUIRED":
                                result = await self.application.download(*item.identity)
                            else:
                                result = await self.application.download(
                                    *item.identity, integrity_mode=self.integrity_mode,
                                    plan_id=plan.plan_id, invocation_id=queue_invocation_id,
                                    reference_manifest_path=self.reference_manifest_path,
                                )
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
                                if task is not None:
                                    charge_open_accounting(task)
                        if (
                            self.max_transfer_bytes is None
                            and item.identity not in progress_seen
                            and result.result == "DOWNLOADED"
                        ):
                            total_transferred_bytes += result.transferred_bytes
                        if result.result in {"ALREADY_DOWNLOADED", "ALREADY_COMPLETED_V2"}:
                            item_status = "ALREADY_VALID" if result.result == "ALREADY_DOWNLOADED" else "ALREADY_COMPLETED_V2"
                        elif result.result in {"COMPLETED_V2", "RECOVERED_V2"}:
                            item_status = result.result
                        else:
                            item_status = "COMPLETED"
                        states[item.identity] = item_status
                        completed_for_space.add(item.identity)
                        detail = None
                        result_mode = getattr(result, "integrity_mode", "REMOTE_HASH_REQUIRED")
                        if result_mode != "REMOTE_HASH_REQUIRED":
                            detail = ";".join(filter(None, (
                                result_mode, result.evidence_class,
                                result.remote_hash_class, result.guarantee,
                            )))
                        outcomes.append((item.identity, item_status, detail))
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
                            if self.queue_accounting is not None:
                                stop_reason = "RATE_LIMITED"
                                stop.set()
                                break
                            retry_after = getattr(error, "retry_after_seconds", None)
                            if type(retry_after) is not int or retry_after < 0:
                                break
                            delay = max(1, retry_after)
                            emit_operational_event(
                                "download_floodwait_observed",
                                component="download_queue",
                                level=logging.WARNING,
                                category=error.category,
                                attempt=attempt + 1,
                                retry_after_seconds=delay,
                            )
                            async with self._rate_lock:
                                self._cooldown_until = max(self._cooldown_until, self.clock() + delay)
                            if waits + delay > FLOODWAIT_MAX_SECONDS or attempt + 1 >= self.attempts_per_media:
                                if error.failure_phase == "REMOTE_HASH":
                                    last_error = DownloadError(
                                        "REMOTE_HASH_UNAVAILABLE", failure_phase="REMOTE_HASH"
                                    )
                                break
                            continue
                        if error.category not in {
                            "NETWORK", "GATEWAY_FAILURE", "TRANSFER_FAILED",
                            "REMOTE_HASH_UNAVAILABLE", "REMOTE_HASHES_UNAVAILABLE",
                        } or attempt + 1 >= self.attempts_per_media:
                            break
                        # Full jitter prevents synchronized workers from
                        # repeating transient failures in lockstep. The attempt
                        # budget bounds the exponential window without adding a
                        # separate retry cap or wait budget.
                        delay = self.random_uniform(0.0, float(2**attempt))
                        emit_operational_event(
                            "download_retry_scheduled",
                            component="download_queue",
                            level=logging.WARNING,
                            category=error.category,
                            attempt=attempt + 1,
                        )
                        await self.sleep(delay)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        last_error = DownloadError("TRANSFER_FAILED")
                        break
                if last_error is not None:
                    if last_error.category == "INSUFFICIENT_DISK_SPACE":
                        stop.set()
                    blocked_categories = {
                        "INSUFFICIENT_DISK_SPACE", "TRANSFER_BUDGET_EXHAUSTED", "BUDGET_BLOCK",
                        "S9_ACCOUNTING_FAILED", "RATE_LIMITED",
                        "REMOTE_HASH_UNAVAILABLE", "REMOTE_HASHES_UNAVAILABLE",
                        "REMOTE_HASH_INVALID_RESPONSE", "REMOTE_HASH_DIVERGENT",
                        "BLOCKED_CONTRADICTORY_REMOTE_EVIDENCE", "REFERENCE_ABSENT",
                        "REFERENCE_INVALID", "REFERENCE_PROVENANCE_UNVERIFIED",
                        "REFERENCE_MISMATCH", "REMOTE_IDENTITY_CONFLICT",
                        "IDENTITY_REVALIDATION_UNAVAILABLE", "PREFIX_CONFLICT",
                        "REMOTE_PREFIX_INCOMPLETE", "CHECKPOINT_INCONSISTENT",
                        "HASH_COVERAGE_INVALID",
                    }
                    blocked = (
                        last_error.category in blocked_categories
                        or last_error.failure_phase == "REMOTE_HASH"
                    )
                    final_category = (
                        "RATE_LIMITED"
                        if self.queue_accounting is not None
                        and last_error.category == "RATE_LIMITED"
                        else "REMOTE_HASH_UNAVAILABLE"
                        if last_error.failure_phase == "REMOTE_HASH"
                        and last_error.category in {"RATE_LIMITED", "NETWORK", "GATEWAY_FAILURE", "TRANSFER_FAILED"}
                        else last_error.category
                    )
                    states[item.identity] = "BLOCKED" if blocked else "FAILED"
                    outcomes.append((item.identity, "BLOCKED" if blocked else "FAILED", final_category))
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
                budget_consumed if self.max_transfer_bytes is not None else None,
                budget_uncertain,
            )
        finally:
            self.application.progress_callback = original_progress
            if hasattr(self.application, "chunk_callback"):
                self.application.chunk_callback = original_chunk_callback
            self.application.chunk_reserver = original_chunk_reserver
            self.application.operation_reserver = original_operation_reserver
            if hasattr(self.application, "pre_append_check"):
                self.application.pre_append_check = original_pre_append_check
            task_items.clear()
            task_reserved_bytes.clear()
            task_accounting_leases.clear()
        return QueueResult(
            tuple(outcomes), total_transferred_bytes, attempts_total, False,
            self.clock() - started_at,
            budget_consumed if self.max_transfer_bytes is not None else None,
            budget_uncertain,
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
