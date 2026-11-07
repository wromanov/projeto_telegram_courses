"""Controlled, synthetic-only composition of the existing S5 queue.

This module has no CLI entry point or real gateway factory. Its sandbox owns
the database and filesystem and its gateway serves only in-memory bytes.
"""

from __future__ import annotations

import asyncio
import hashlib
import sqlite3
import tempfile
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from telegram_courses.catalog import CatalogError
from telegram_courses.course_download_planning import create_course_plan_review
from telegram_courses.course_execution import (
    ConfirmedCoursePlan,
    CourseExecutionSummary,
    ProgressSnapshot,
    execute_queue_with_progress,
    summarize_execution,
)
from telegram_courses.course_review_context import load_course_review_context
from telegram_courses.downloads import (
    DownloadError,
    DownloadGatewayError,
    RemoteFileHash,
    _reject_reparse_path,
)
from telegram_courses.s5_downloads import DownloadPlanner

Identity = tuple[int, int, int]


class _MemoryGateway:
    """Synthetic gateway; data never comes from a session, network or file."""

    def __init__(self, payloads: dict[Identity, tuple[str, bytes]]) -> None:
        self._payloads = {identity: (media_id, bytes(data)) for identity, (media_id, data) in payloads.items()}
        self.calls: list[Identity] = []
        self.delay_seconds = 0.0

    def _data(self, identity: Identity, media_id: str, expected_bytes: int) -> bytes:
        record = self._payloads.get(identity)
        if record is None or record[0] != media_id or len(record[1]) != expected_bytes:
            raise DownloadGatewayError("MEDIA_NOT_OBSERVED")
        return record[1]

    async def stream_media(
        self, channel_id, message_id, media_ordinal, *, telegram_media_id,
        expected_bytes, reserve_chunk=None, offset=0,
    ):
        identity = (channel_id, message_id, media_ordinal)
        data = self._data(identity, telegram_media_id, expected_bytes)
        self.calls.append(identity)
        for start in range(offset, len(data), 256 * 1024):
            chunk = data[start:start + 256 * 1024]
            reservation = await reserve_chunk(len(chunk)) if reserve_chunk is not None else None
            if reserve_chunk is not None and reservation is None:
                raise DownloadGatewayError("TRANSFER_BUDGET_EXHAUSTED")
            try:
                await asyncio.sleep(self.delay_seconds)
            except BaseException:
                if reservation is not None:
                    reservation.release()
                raise
            if reservation is not None:
                reservation.received(len(chunk))
            yield chunk

    async def get_file_hashes(
        self, channel_id, message_id, media_ordinal, *, telegram_media_id,
        expected_bytes, offset=0,
    ):
        data = self._data((channel_id, message_id, media_ordinal), telegram_media_id, expected_bytes)
        block = data[offset:offset + 128 * 1024]
        if not block:
            return ()
        return (RemoteFileHash(offset, len(block), hashlib.sha256(block).digest()),)


@dataclass(frozen=True)
class OfflineExecutionAuthorization:
    """One sandbox's explicit authority, separate from plan confirmation."""

    _sandbox: object
    _confirmation: ConfirmedCoursePlan
    _nonce: object


class OfflineCourseSandbox:
    """Own an isolated temporary fixture and an in-memory-only gateway."""

    def __init__(self, payloads: dict[Identity, tuple[str, bytes]]) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="telegram-courses-offline-", delete=False)
        self.root = Path(self._directory.name).resolve()
        self.database = self.root / "synthetic.sqlite3"
        self.download_root = self.root / "downloads"
        with closing(sqlite3.connect(self.database)):
            pass
        stat = self.database.stat()
        self._identity = (stat.st_dev, stat.st_ino)
        self._gateway = _MemoryGateway(payloads)
        self._active_nonce: object | None = None
        self._preserve_evidence = False

    def __enter__(self) -> OfflineCourseSandbox:
        return self

    @classmethod
    def persistent_demo(cls, root: Path, payloads: dict[Identity, tuple[str, bytes]]) -> OfflineCourseSandbox:
        """Bind a validated demo workspace to the existing fake-only executor."""
        marker = root / ".telegram-courses-demo"
        _reject_reparse_path(Path(root.anchor), marker)
        _reject_reparse_path(Path(root.anchor), root / "synthetic.sqlite3")
        if marker.stat().st_nlink != 1 or marker.read_text(encoding="utf-8") != "telegram-courses-demo-v1\n":
            raise DownloadError("OFFLINE_SANDBOX_INVALID")
        sandbox = cls.__new__(cls)
        sandbox._directory = None
        sandbox.root = root
        sandbox.database = root / "synthetic.sqlite3"
        sandbox.download_root = root / "downloads"
        stat = sandbox.database.stat()
        if stat.st_nlink != 1:
            raise DownloadError("OFFLINE_SANDBOX_INVALID")
        sandbox._identity = (stat.st_dev, stat.st_ino)
        sandbox._gateway = _MemoryGateway(payloads)
        sandbox._active_nonce = None
        sandbox._preserve_evidence = True
        return sandbox

    def __exit__(self, exc_type: object, _exc: object, _traceback: object) -> None:
        try:
            has_partial = next(self.download_root.rglob("*.part"), None) is not None
        except OSError:
            has_partial = True
        if self._directory is not None and exc_type is None and not self._preserve_evidence and not has_partial:
            self._directory.cleanup()

    @property
    def gateway_calls(self) -> tuple[Identity, ...]:
        return tuple(self._gateway.calls)

    def _validate_binding(self, confirmation: ConfirmedCoursePlan) -> None:
        try:
            if self._directory is None:
                marker = self.root / ".telegram-courses-demo"
                _reject_reparse_path(Path(self.root.anchor), marker)
                _reject_reparse_path(Path(self.root.anchor), self.database)
                if marker.stat().st_nlink != 1 or marker.read_text(encoding="utf-8") != "telegram-courses-demo-v1\n":
                    raise DownloadError("OFFLINE_SANDBOX_INVALID")
            stat = self.database.stat()
            valid = (
                not self.database.is_symlink()
                and (stat.st_dev, stat.st_ino) == self._identity
                and stat.st_nlink == 1
                and confirmation.database.resolve() == self.database
                and Path(confirmation.review.download_root).resolve() == self.download_root
                and not self.download_root.is_symlink()
                and type(self._gateway) is _MemoryGateway
                and confirmation.review.integrity_mode == "REMOTE_HASH_REQUIRED"
                and confirmation.review.can_confirm
            )
        except OSError:
            valid = False
        if not valid:
            raise DownloadError("OFFLINE_SANDBOX_INVALID")

    def authorize(self, confirmation: ConfirmedCoursePlan) -> OfflineExecutionAuthorization:
        self._validate_binding(confirmation)
        nonce = object()
        self._active_nonce = nonce
        return OfflineExecutionAuthorization(self, confirmation, nonce)

    async def execute(
        self,
        authorization: OfflineExecutionAuthorization,
        *,
        observer: Callable[[ProgressSnapshot], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        cancel_event: asyncio.Event | None = None,
    ) -> CourseExecutionSummary:
        if (
            type(authorization) is not OfflineExecutionAuthorization
            or authorization._sandbox is not self
            or authorization._nonce is not self._active_nonce
            or self._active_nonce is None
        ):
            raise DownloadError("OFFLINE_EXECUTION_NOT_AUTHORIZED")
        self._active_nonce = None
        confirmation = authorization._confirmation
        self._validate_binding(confirmation)
        prior = confirmation.review
        if cancel_event is not None and cancel_event.is_set():
            return summarize_execution(prior.plan, cancelled=True, observed_exclusions=prior.observed_exclusions)

        planner = DownloadPlanner(self.database, self.download_root)
        selection = prior.plan.selection
        try:
            _, _, _, _, fresh_selection, exclusions, context = await load_course_review_context(
                planner, channel_id=selection.channel_id, course_id=selection.node_id,
                selection_mode=prior.selection_mode,
                exact_selection=selection if prior.selection_mode == "SELECTED" else None,
            )
            if fresh_selection is None:
                return summarize_execution(prior.plan, global_block="PLAN_CHANGED", observed_exclusions=prior.observed_exclusions)
            plan = await planner.build(fresh_selection)
            ids = {item.identity for item in plan.items}
            fresh = create_course_plan_review(
                plan, selection_mode=prior.selection_mode, download_root=self.download_root,
                integrity_mode=prior.integrity_mode, max_media_items=prior.max_media_items,
                max_transfer_bytes=prior.max_transfer_bytes,
                observed_exclusions=tuple(item for item in exclusions if item.identity not in ids),
                catalog_context=context,
            )
        except asyncio.CancelledError:
            return summarize_execution(prior.plan, cancelled=True, observed_exclusions=prior.observed_exclusions)
        except (CatalogError, DownloadError, OSError, sqlite3.Error):
            return summarize_execution(prior.plan, global_block="PLAN_REVALIDATION_FAILED", observed_exclusions=prior.observed_exclusions)
        if not prior.matches_after_confirmation(fresh):
            return summarize_execution(prior.plan, global_block="PLAN_CHANGED", observed_exclusions=prior.observed_exclusions)
        self._validate_binding(confirmation)
        if cancel_event is not None and cancel_event.is_set():
            return summarize_execution(plan, cancelled=True, observed_exclusions=fresh.observed_exclusions)
        summary = await execute_queue_with_progress(
            self.database,
            self.download_root,
            plan,
            self._gateway,
            attempts_per_media=3,
            max_media_items=prior.max_media_items,
            max_transfer_bytes=prior.max_transfer_bytes,
            integrity_mode=prior.integrity_mode,
            observer=observer,
            clock=clock,
            cancel_event=cancel_event,
            observed_exclusions=fresh.observed_exclusions,
        )
        if summary.status in {"CANCELADO", "FALHA", "BLOQUEADO", "PARCIAL"}:
            self._preserve_evidence = True
        return summary
