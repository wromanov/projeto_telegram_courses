"""Offline course execution models and observational progress accounting."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread
from typing import Any

from telegram_courses.course_download_planning import (
    CoursePlanReview,
    ObservedExclusion,
)
from telegram_courses.download_repository import DownloadRepository
from telegram_courses.downloads import (
    DownloadError,
    SingleMediaDownloadApplication,
)
from telegram_courses.s5_downloads import DownloadPlan, DownloadQueue, QueueResult

Identity = tuple[int, int, int]


@dataclass(frozen=True)
class ConfirmedCoursePlan:
    """A reviewed plan, not an authorization to transfer payload."""

    database: Path
    review: CoursePlanReview


@dataclass(frozen=True)
class CourseExecutionSummary:
    status: str
    outcomes: tuple[tuple[Identity, str, str | None], ...]
    selected: int
    eligible: int
    already_valid: int
    completed: int
    pending: int
    excluded: int
    blocked: int
    failed: int
    cancelled: int
    transferred_bytes: int
    validated_bytes: int = 0
    previously_valid_bytes: int = 0
    proof_received_bytes: int | None = None
    overlap_received_bytes: int | None = None
    proof_verified_bytes: int = 0
    planned_overlap_bytes: int = 0
    budget_charged_bytes: int | None = None
    budget_uncertain_bytes: int | None = None
    presentation_failed: bool = False
    presentation_incomplete: bool = False
    cleanup_failed: bool = False
    observed_exclusions: tuple[ObservedExclusion, ...] = ()


def summarize_execution(
    plan: DownloadPlan, result: QueueResult | None = None, *,
    cancelled: bool = False, global_block: str | None = None,
    observed_exclusions: tuple[ObservedExclusion, ...] = (),
) -> CourseExecutionSummary:
    """Derive presentation states from the plan and authoritative queue result."""
    reported: dict[Identity, tuple[str, str | None]] = {}
    valid = {item.identity for item in plan.items}
    if len(valid) != len(plan.items):
        raise ValueError("duplicate plan identities")
    if result is not None:
        by_identity = {item.identity: item for item in plan.items}
        for identity, status, reason in result.outcomes:
            if identity not in valid or identity in reported:
                raise ValueError("invalid queue outcomes")
            item = by_identity[identity]
            if item.status in {"EXCLUDED", "BLOCKED"} and status != item.status:
                raise ValueError("invalid queue outcome for blocked or excluded item")
            reported[identity] = (status, reason)
    outcomes = []
    for item in plan.items:
        if item.identity in reported:
            status, reason = reported[item.identity]
        elif global_block and item in plan.pending:
            status, reason = "BLOCKED", global_block
        elif cancelled and item in plan.pending:
            status, reason = "CANCELLED", "CANCELLED"
        else:
            status, reason = item.status, item.reason
        outcomes.append((item.identity, status, reason))
    statuses = [status for _, status, _ in outcomes]
    already = sum(status in {"ALREADY_VALID", "ALREADY_COMPLETED_V2"} for status in statuses)
    completed = sum(status in {"COMPLETED", "COMPLETED_V2", "RECOVERED_V2"} for status in statuses)
    excluded = statuses.count("EXCLUDED")
    blocked = statuses.count("BLOCKED")
    failed = statuses.count("FAILED")
    cancelled_count = statuses.count("CANCELLED")
    pending = len(statuses) - already - completed - excluded - blocked - failed - cancelled_count
    is_cancelled = cancelled or bool(result and result.cancelled) or bool(cancelled_count)
    if not plan.items:
        status = "SEM_SELECAO"
    elif not plan.eligible and not global_block and not blocked:
        status = "SEM_ELEGIVEIS"
    elif is_cancelled:
        status = "CANCELADO"
    elif failed:
        status = "FALHA"
    elif global_block or blocked:
        status = "BLOQUEADO"
    elif excluded or pending:
        status = "PARCIAL" if already or completed else "BLOQUEADO"
    elif completed:
        status = "CONCLUIDO"
    elif already == len(plan.items):
        status = "TODOS_JA_VALIDOS"
    else:
        status = "BLOQUEADO"
    status_by_id = {identity: item_status for identity, item_status, _ in outcomes}
    validated_bytes = sum(
        item.candidate.expected_bytes for item in plan.eligible
        if status_by_id[item.identity] in {"COMPLETED", "COMPLETED_V2", "RECOVERED_V2"}
    )
    previously_valid_bytes = sum(
        item.candidate.expected_bytes for item in plan.eligible
        if status_by_id[item.identity] in {"ALREADY_VALID", "ALREADY_COMPLETED_V2"}
    )
    return CourseExecutionSummary(
        status, tuple(outcomes), len(plan.items), len(plan.eligible), already,
        completed, pending, excluded, blocked, failed, cancelled_count,
        result.transferred_bytes if result is not None else 0,
        validated_bytes, previously_valid_bytes,
        None, None, 0, sum(item.overlap_bytes for item in plan.pending),
        result.budget_consumed_bytes if result is not None else None,
        result.budget_uncertain_bytes if result is not None and result.budget_consumed_bytes is not None else None,
        observed_exclusions=observed_exclusions,
    )


@dataclass(frozen=True)
class ProgressSnapshot:
    identity: Identity | None
    position: int
    total_files: int
    attempt: int
    file_status: str
    file_bytes: int | None
    file_total: int | None
    received_bytes: int
    budget_charged_bytes: int | None
    budget_uncertain_bytes: int | None
    proof_verified_bytes: int
    proof_received_bytes: int
    overlap_received_bytes: int
    planned_overlap_bytes: int
    completed_files: int
    already_valid_files: int
    batch_validated_bytes: int
    batch_total_bytes: int | None
    elapsed_seconds: float
    speed_mb_s: float | None
    eta_seconds: float | None
    presentation_failed: bool


class CourseProgressTracker:
    """Keep presentation observations separate from queue and budget state."""

    def __init__(self, plan: DownloadPlan, clock: Callable[[], float]) -> None:
        self.plan = plan
        self.clock = clock
        self.started = clock()
        self.attempt_started = self.started
        self.attempt_base_bytes = 0
        self.attempt_base_file: int | None = None
        self.file_sample_started: float | None = None
        self.identity: Identity | None = None
        self.position = 0
        self.attempt = 0
        self.file_status = "PENDENTE"
        self.file_bytes: int | None = None
        self.file_total: int | None = None
        self.received_bytes = 0
        self.budget_charged_bytes: int | None = None
        self.budget_uncertain_bytes: int | None = None
        self.proof_verified_bytes = 0
        self.proof_received_bytes = 0
        self.overlap_received_bytes = 0
        self.planned_overlap_bytes = sum(item.overlap_bytes for item in plan.pending)
        self.completed_files = 0
        self.already_valid_files = 0
        self._validated_ids = {item.identity for item in plan.already_valid}
        self._sizes = {
            item.identity: item.candidate.expected_bytes
            for item in plan.eligible if item.candidate is not None
        }
        self._batch_total_bytes = sum(self._sizes.values()) if self._sizes else None
        self._batch_validated_bytes = sum(self._sizes.get(identity, 0) for identity in self._validated_ids)
        self.failed_files = 0
        self.blocked_files = 0
        self.cancelled_files = 0
        self.presentation_failed = False

    def start_attempt(self, identity: Identity) -> None:
        self.attempt = self.attempt + 1 if identity == self.identity else 1
        self.identity = identity
        self.file_status = "EM ANDAMENTO"
        self.position = next(
            (index for index, item in enumerate(self.plan.pending, 1) if item.identity == identity), 0,
        )
        item = next((item for item in self.plan.pending if item.identity == identity), None)
        self.file_bytes = item.part_bytes if item else None
        self.file_total = item.candidate.expected_bytes if item and item.candidate else None
        self.attempt_started = self.clock()
        self.attempt_base_bytes = self.received_bytes
        self.attempt_base_file = None
        self.file_sample_started = None

    def observe_file(self, current: int, total: int) -> None:
        if type(current) is int and type(total) is int and 0 <= current <= total:
            if self.attempt_base_file is None or (
                self.file_bytes is not None and current < self.file_bytes
            ):
                self.attempt_base_file = current
                self.file_sample_started = self.clock()
            self.file_bytes, self.file_total = current, total
            if total > 0 and current == total:
                self.file_status = "VALIDANDO"

    def observe_queue(self, state: dict[str, int]) -> None:
        previous_completed = self.completed_files
        previous_valid = self.already_valid_files
        previous_failed = self.failed_files
        previous_blocked = self.blocked_files
        previous_cancelled = self.cancelled_files
        received = state.get("bytes_transferred")
        if type(received) is int and received >= self.received_bytes:
            self.received_bytes = received
        for key, attr in (("budget_consumed_bytes", "budget_charged_bytes"), ("budget_uncertain_bytes", "budget_uncertain_bytes")):
            value = state.get(key)
            if type(value) is int and value >= 0:
                setattr(self, attr, value)
        for key, attr in (
            ("completed", "completed_files"), ("already_valid", "already_valid_files"),
            ("failed", "failed_files"), ("blocked", "blocked_files"), ("cancelled", "cancelled_files"),
        ):
            value = state.get(key)
            if type(value) is int and value >= 0:
                setattr(self, attr, value)
        if self.identity is not None and state.get("running") == 0:
            if self.completed_files > previous_completed:
                self.file_status = "CONCLUÍDO"
                self._record_validated(self.identity)
            elif self.already_valid_files > previous_valid:
                self.file_status = "JÁ VÁLIDO"
                self._record_validated(self.identity)
            elif self.failed_files > previous_failed:
                self.file_status = "FALHA"
            elif self.blocked_files > previous_blocked:
                self.file_status = "BLOQUEADO"
            elif self.cancelled_files > previous_cancelled:
                self.file_status = "CANCELADO"

    def observe_verified_prefix(self, verification_bytes: int) -> None:
        if type(verification_bytes) is int and verification_bytes >= 0:
            self.proof_verified_bytes += verification_bytes

    def _record_validated(self, identity: Identity) -> None:
        if identity not in self._validated_ids:
            self._validated_ids.add(identity)
            self._batch_validated_bytes += self._sizes.get(identity, 0)

    def observe_traffic(self, kind: str, byte_count: int) -> None:
        if type(byte_count) is not int or byte_count < 0:
            return
        if kind == "proof":
            self.proof_received_bytes += byte_count
        elif kind == "overlap":
            self.overlap_received_bytes += byte_count

    def snapshot(self) -> ProgressSnapshot:
        now = self.clock()
        elapsed = max(0.0, now - self.started)
        attempt_elapsed = max(0.0, now - self.attempt_started)
        attempt_received = max(0, self.received_bytes - self.attempt_base_bytes)
        speed = attempt_received / attempt_elapsed / 1_000_000 if attempt_elapsed >= 1 and attempt_received else None
        eta = None
        file_elapsed = max(0.0, now - self.file_sample_started) if self.file_sample_started is not None else 0.0
        if (
            file_elapsed >= 1 and self.file_bytes is not None
            and self.file_total is not None and self.attempt_base_file is not None
            and self.file_bytes > self.attempt_base_file and self.file_bytes < self.file_total
        ):
            logical_rate = (self.file_bytes - self.attempt_base_file) / file_elapsed
            eta = (self.file_total - self.file_bytes) / logical_rate
        return ProgressSnapshot(
            self.identity, self.position, len(self.plan.pending), self.attempt, self.file_status,
            self.file_bytes, self.file_total, self.received_bytes,
            self.budget_charged_bytes, self.budget_uncertain_bytes,
            self.proof_verified_bytes, self.proof_received_bytes,
            self.overlap_received_bytes, self.planned_overlap_bytes,
            self.completed_files, self.already_valid_files,
            self._batch_validated_bytes, self._batch_total_bytes, elapsed,
            speed, eta, self.presentation_failed,
        )


class ProgressDispatcher:
    """Bounded latest-value mailbox; a slow renderer never blocks the queue."""

    def __init__(
        self, observer: Callable[[ProgressSnapshot], None], *,
        clock: Callable[[], float], min_interval: float = 0.25,
    ) -> None:
        self.observer = observer
        self.clock = clock
        self.min_interval = min_interval
        self.last_published: float | None = None
        self.failed = False
        self.incomplete = False
        self._mailbox: Queue[ProgressSnapshot] = Queue(maxsize=1)
        self._stop = Event()
        self._thread = Thread(target=self._run, daemon=True, name="course-progress")
        self._thread.start()

    def _run(self) -> None:
        try:
            while not self._stop.is_set() or not self._mailbox.empty():
                try:
                    snapshot = self._mailbox.get(timeout=0.05)
                except Empty:
                    continue
                try:
                    self.observer(snapshot)
                except Exception:
                    self.failed = True
        finally:
            close = getattr(self.observer, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    self.failed = True

    def _offer(self, snapshot: ProgressSnapshot) -> None:
        try:
            self._mailbox.put_nowait(snapshot)
        except Full:
            try:
                self._mailbox.get_nowait()
            except Empty:
                pass
            try:
                self._mailbox.put_nowait(snapshot)
            except Full:
                pass

    def publish(self, snapshot: ProgressSnapshot) -> None:
        if self._stop.is_set():
            return
        now = self.clock()
        if self.last_published is None or now - self.last_published >= self.min_interval:
            self.last_published = now
            self._offer(snapshot)

    def close(self, timeout: float = 0.1) -> None:
        self._stop.set()
        self._thread.join(timeout)
        self.incomplete = self._thread.is_alive()


class ObservedDownloadApplication(SingleMediaDownloadApplication):
    """Adapt S5 transfer callbacks to the shared, presentation-neutral tracker."""

    def __init__(self, *args: Any, tracker: CourseProgressTracker, notify: Callable[[], None], **kwargs: Any) -> None:
        self._tracker = tracker
        self._notify = notify
        super().__init__(*args, **kwargs)

    async def download(self, channel_id: int, message_id: int, media_ordinal: int, **kwargs: Any) -> Any:
        try:
            self._tracker.start_attempt((channel_id, message_id, media_ordinal))
            self._notify()
        except Exception:
            self._tracker.presentation_failed = True
        return await super().download(channel_id, message_id, media_ordinal, **kwargs)


async def execute_queue_with_progress(
    database: str | Path,
    download_root: str | Path,
    plan: DownloadPlan,
    gateway: object,
    *,
    attempts_per_media: int,
    max_media_items: int | None,
    max_transfer_bytes: int | None,
    integrity_mode: str,
    observer: Callable[[ProgressSnapshot], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    cancel_event: asyncio.Event | None = None,
    observed_exclusions: tuple[ObservedExclusion, ...] = (),
) -> CourseExecutionSummary:
    """Run the existing S5 queue and derive presentation from its result."""
    if cancel_event is not None and cancel_event.is_set():
        return summarize_execution(
            plan, cancelled=True, observed_exclusions=observed_exclusions,
        )
    if not plan.pending:
        return summarize_execution(plan, observed_exclusions=observed_exclusions)

    tracker = CourseProgressTracker(plan, clock)
    dispatcher = ProgressDispatcher(observer, clock=clock) if observer is not None else None

    def notify() -> None:
        if dispatcher is not None:
            dispatcher.publish(tracker.snapshot())

    def report_file(current: int, total: int) -> None:
        try:
            tracker.observe_file(current, total)
        except Exception:
            tracker.presentation_failed = True

    def report_queue(state: dict[str, int]) -> None:
        try:
            tracker.observe_queue(state)
            if tracker.identity is not None:
                notify()
        except Exception:
            tracker.presentation_failed = True

    def report_verified_prefix(proof: Any) -> None:
        try:
            tracker.observe_verified_prefix(proof.verification_payload_bytes)
        except Exception:
            tracker.presentation_failed = True

    def report_traffic(kind: str, byte_count: int) -> None:
        try:
            tracker.observe_traffic(kind, byte_count)
        except Exception:
            tracker.presentation_failed = True

    repository = DownloadRepository(database)
    application = ObservedDownloadApplication(
        repository, gateway, download_root,
        tracker=tracker, notify=notify, progress_callback=report_file,
        prefix_proof_observer=report_verified_prefix,
        traffic_observer=report_traffic,
    )
    queue = DownloadQueue(
        repository, application, workers=1, attempts_per_media=attempts_per_media,
        max_media_items=max_media_items, max_transfer_bytes=max_transfer_bytes,
        integrity_mode=integrity_mode, progress_callback=report_queue,
    )
    task = asyncio.create_task(queue.run(plan))
    cancellation = asyncio.create_task(cancel_event.wait()) if cancel_event is not None else None
    try:
        if cancellation is not None:
            done, _ = await asyncio.wait(
                (task, cancellation), return_when=asyncio.FIRST_COMPLETED,
            )
            if cancellation in done and cancel_event.is_set() and not task.done():
                task.cancel()
        result = await task
        summary = summarize_execution(
            plan, result, observed_exclusions=observed_exclusions,
        )
    except asyncio.CancelledError:
        task.cancel()
        try:
            result = await task
        except asyncio.CancelledError:
            summary = summarize_execution(
                plan, cancelled=True, observed_exclusions=observed_exclusions,
            )
        else:
            summary = summarize_execution(
                plan, result, observed_exclusions=observed_exclusions,
            )
    except DownloadError as error:
        summary = summarize_execution(
            plan, global_block=error.category, observed_exclusions=observed_exclusions,
        )
    except OSError:
        summary = summarize_execution(
            plan, global_block="DISK_SPACE_UNVERIFIED",
            observed_exclusions=observed_exclusions,
        )
    finally:
        if cancellation is not None:
            cancellation.cancel()
            await asyncio.gather(cancellation, return_exceptions=True)
        if dispatcher is not None:
            dispatcher.close()
    return replace(
        summary,
        presentation_failed=tracker.presentation_failed or bool(dispatcher and dispatcher.failed),
        presentation_incomplete=bool(dispatcher and dispatcher.incomplete),
        proof_verified_bytes=tracker.proof_verified_bytes,
        proof_received_bytes=tracker.proof_received_bytes,
        overlap_received_bytes=tracker.overlap_received_bytes,
    )
