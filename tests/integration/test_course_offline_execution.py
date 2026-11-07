from __future__ import annotations

import asyncio
import io
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from rich.console import Console
from tests.integration.test_interactive_catalog import _seed_interactive_database

from telegram_courses.catalog_repository import SQLiteCatalogRepository
from telegram_courses.catalog_selection import selectable_courses
from telegram_courses.course_download_planning import course_download_selection
from telegram_courses.course_offline_execution import OfflineCourseSandbox
from telegram_courses.course_progress_rich import run_offline_with_rich
from telegram_courses.downloads import DownloadError
from telegram_courses.interactive_catalog_cli import (
    _review_and_confirm_course_plan,
    run_interactive_catalog,
)
from telegram_courses.s5_downloads import DownloadPlanner


def _prepare(sandbox: OfflineCourseSandbox, *, selection_mode: str = "SELECTED", unknown: bool = False):
    asyncio.run(_seed_interactive_database(sandbox.database))
    with closing(sqlite3.connect(sandbox.database)) as db:
        if not unknown:
            db.execute("UPDATE media_items SET file_size_bytes=80 WHERE telegram_message_id=20")
        db.commit()
    planner = DownloadPlanner(sandbox.database, sandbox.download_root)
    snapshot = asyncio.run(SQLiteCatalogRepository(sandbox.database).load_interactive_snapshot(-1001))
    course = next(item for item in selectable_courses(snapshot) if item.node_id == 101)
    selection = course_download_selection(
        -1001, 101, media_identities=((-1001, 20, 0), (-1001, 10, 0)),
    ) if selection_mode == "SELECTED" else None
    confirmation = _review_and_confirm_course_plan(
        planner=planner, selection=selection, selection_mode=selection_mode,
        snapshot=snapshot, course=course, download_root=sandbox.download_root,
        max_media_items=5, max_transfer_bytes=None if unknown else 1000,
        selection_prompt=lambda _: "s", console=Console(file=io.StringIO(), width=160),
    )
    assert confirmation is not None
    return confirmation


PAYLOADS = {
    (-1001, 10, 0): ("synthetic-1", b"a" * 120),
    (-1001, 20, 0): ("synthetic-2", b"b" * 80),
}


@pytest.fixture(autouse=True)
def cleanup_owned_synthetic_sandboxes(monkeypatch):
    created = []
    original_init = OfflineCourseSandbox.__init__

    def tracked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        created.append(self)

    monkeypatch.setattr(OfflineCourseSandbox, "__init__", tracked_init)
    yield
    temp_root = Path(tempfile.gettempdir()).resolve()
    for sandbox in created:
        if sandbox.root.exists():
            resolved = sandbox.root.resolve()
            assert resolved.parent == temp_root
            assert resolved.name.startswith("telegram-courses-offline-")
            sandbox._directory.cleanup()


def test_sandbox_exit_preserves_existing_partial() -> None:
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        sandbox.download_root.mkdir()
        partial = sandbox.download_root / "fixture.part"
        partial.write_bytes(b"synthetic partial")
    assert partial.read_bytes() == b"synthetic partial"


def test_exact_confirmed_course_runs_once_in_s5_order_and_dedupes() -> None:
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)
        with closing(sqlite3.connect(sandbox.database)) as db:
            schema_before = db.execute(
                "SELECT type,name,sql FROM sqlite_master ORDER BY type,name"
            ).fetchall()
            assert db.execute("SELECT COUNT(*) FROM downloads").fetchone()[0] == 0
        assert not sandbox.gateway_calls
        authorization = sandbox.authorize(confirmation)
        result = asyncio.run(sandbox.execute(authorization))
        assert result.status == "CONCLUIDO"
        assert result.transferred_bytes == 200
        assert result.budget_charged_bytes == 200
        assert result.budget_uncertain_bytes == 0
        with closing(sqlite3.connect(sandbox.database)) as db:
            assert db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall() == schema_before
        assert sandbox.gateway_calls == ((-1001, 10, 0), (-1001, 20, 0))
        assert [item[0] for item in result.outcomes] == list(sandbox.gateway_calls)
        with pytest.raises(DownloadError) as error:
            asyncio.run(sandbox.execute(authorization))
        assert error.value.category == "OFFLINE_EXECUTION_NOT_AUTHORIZED"

        # A fresh confirmation is required for a second run.
        planner = DownloadPlanner(sandbox.database, sandbox.download_root)
        snapshot = asyncio.run(SQLiteCatalogRepository(sandbox.database).load_interactive_snapshot(-1001))
        course = next(item for item in selectable_courses(snapshot) if item.node_id == 101)
        second = _review_and_confirm_course_plan(
            planner=planner, selection=confirmation.review.plan.selection,
            selection_mode="SELECTED", snapshot=snapshot, course=course,
            download_root=sandbox.download_root, max_media_items=5, max_transfer_bytes=1000,
            selection_prompt=lambda _: "s", console=Console(file=io.StringIO()),
        )
        assert second is not None
        again = asyncio.run(sandbox.execute(sandbox.authorize(second)))
        assert again.status == "TODOS_JA_VALIDOS"
        assert again.transferred_bytes == 0
        assert len(sandbox.gateway_calls) == 2


@pytest.mark.parametrize("authorize", ["s", "n"])
def test_interactive_offline_fixture_requires_separate_execution_authorization(
    capsys, authorize,
) -> None:
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        asyncio.run(_seed_interactive_database(sandbox.database))
        answers = iter(("1", "1", "1", "P", "s", authorize, "Q", "Q", "Q"))
        result = run_interactive_catalog(
            sandbox.database, download_root=sandbox.download_root,
            max_media_items=5, max_transfer_bytes=1000,
            selection_prompt=lambda _: next(answers), require_tty=False,
            offline_sandbox=sandbox,
        )
        text = capsys.readouterr().out
        assert result == 0
        if authorize == "s":
            assert sandbox.gateway_calls == ((-1001, 10, 0),)
            assert "CONCLUIDO" in text
        else:
            assert not sandbox.gateway_calls
            assert "Execução sintética não autorizada" in text


def test_drift_after_confirmation_prevents_queue_admission() -> None:
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)
        authorization = sandbox.authorize(confirmation)
        with closing(sqlite3.connect(sandbox.database)) as db:
            db.execute("UPDATE media_items SET file_size_bytes=81 WHERE telegram_message_id=20")
            db.commit()
        result = asyncio.run(sandbox.execute(authorization))
        assert result.status == "BLOQUEADO"
        assert not sandbox.gateway_calls


def test_cancel_before_admission_does_not_call_fake_gateway() -> None:
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)

        async def run():
            cancel = asyncio.Event()
            cancel.set()
            return await sandbox.execute(sandbox.authorize(confirmation), cancel_event=cancel)

        result = asyncio.run(run())
        assert result.status == "CANCELADO"
        assert not sandbox.gateway_calls


def test_sandbox_rejects_gateway_substitution() -> None:
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)
        sandbox._gateway = object()
        with pytest.raises(DownloadError) as error:
            sandbox.authorize(confirmation)
        assert error.value.category == "OFFLINE_SANDBOX_INVALID"


def test_sandbox_rejects_confirmation_from_another_sandbox() -> None:
    with OfflineCourseSandbox(PAYLOADS) as first, OfflineCourseSandbox(PAYLOADS) as second:
        confirmation = _prepare(first)
        with pytest.raises(DownloadError) as error:
            second.authorize(confirmation)
        assert error.value.category == "OFFLINE_SANDBOX_INVALID"
        assert not first.gateway_calls and not second.gateway_calls


def test_blocked_item_cannot_be_authorized() -> None:
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)
        item = replace(confirmation.review.plan.items[0], status="BLOCKED", reason="UNSAFE_PATH")
        plan = replace(confirmation.review.plan, items=(item, *confirmation.review.plan.items[1:]))
        blocked = replace(confirmation, review=replace(confirmation.review, plan=plan))
        with pytest.raises(DownloadError) as error:
            sandbox.authorize(blocked)
        assert error.value.category == "OFFLINE_SANDBOX_INVALID"
        assert not sandbox.gateway_calls


def test_disk_failure_after_confirmation_blocks_before_transfer(monkeypatch) -> None:
    import telegram_courses.course_offline_execution as offline

    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)
        authorization = sandbox.authorize(confirmation)
        original = offline.create_course_plan_review

        def no_space(*args, **kwargs):
            return original(*args, **kwargs, disk_usage=lambda _: SimpleNamespace(free=0))

        monkeypatch.setattr(offline, "create_course_plan_review", no_space)
        summary = asyncio.run(sandbox.execute(authorization))
        assert summary.status == "BLOQUEADO"
        assert not sandbox.gateway_calls


def test_offline_rich_execution_reports_authoritative_summary() -> None:
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)
        output = io.StringIO()
        console = Console(file=output, width=180, force_terminal=False)
        summary = asyncio.run(run_offline_with_rich(sandbox, sandbox.authorize(confirmation), console))
        text = output.getvalue()
        assert summary.status == "CONCLUIDO"
        assert summary.validated_bytes == 200
        assert "CONCLUIDO" in text
        assert "Bytes recebidos" in text
        assert "Indisponível" in text
        assert ("Módulo 1" in text and "intro.pdf" in text) or (
            "Módulo 2" in text and "lesson.mp4" in text
        )


def test_broken_rich_console_does_not_mask_queue_result() -> None:
    class BrokenConsole(Console):
        def print(self, *args, **kwargs):
            raise OSError("synthetic console failure")

    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)
        console = BrokenConsole(file=io.StringIO(), force_terminal=False)
        result = asyncio.run(run_offline_with_rich(sandbox, sandbox.authorize(confirmation), console))
        assert result.status == "CONCLUIDO"
        assert result.completed == 2
        assert result.presentation_failed or result.presentation_incomplete


@pytest.mark.parametrize("cancel_mode", ["event", "task"])
def test_cancel_during_transfer_preserves_partial_and_stops_next_item(monkeypatch, cancel_mode) -> None:
    from telegram_courses.course_offline_execution import _MemoryGateway

    started = None
    original_stream = _MemoryGateway.stream_media

    async def fake_stream(self, channel_id, message_id, media_ordinal, *,
                          telegram_media_id, expected_bytes, reserve_chunk=None, offset=0):
        identity = (channel_id, message_id, media_ordinal)
        data = self._data(identity, telegram_media_id, expected_bytes)
        self.calls.append(identity)
        chunk = data[offset:offset + 60]
        reservation = await reserve_chunk(len(chunk))
        assert reservation is not None
        reservation.received(len(chunk))
        yield chunk
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(_MemoryGateway, "stream_media", fake_stream)
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)

        async def run():
            nonlocal started
            started = asyncio.Event()
            cancel = asyncio.Event()
            task = asyncio.create_task(sandbox.execute(sandbox.authorize(confirmation), cancel_event=cancel))
            await asyncio.wait_for(started.wait(), timeout=5)
            if cancel_mode == "event":
                cancel.set()
            else:
                task.cancel()
            return await asyncio.wait_for(task, timeout=5)

        summary = asyncio.run(run())
        assert summary.status == "CANCELADO"
        assert sandbox.gateway_calls == ((-1001, 10, 0),)
        partials = list(sandbox.download_root.rglob("*.part"))
        assert len(partials) == 1
        assert partials[0].read_bytes() == b"a" * 60

        monkeypatch.setattr(_MemoryGateway, "stream_media", original_stream)
        planner = DownloadPlanner(sandbox.database, sandbox.download_root)
        snapshot = asyncio.run(SQLiteCatalogRepository(sandbox.database).load_interactive_snapshot(-1001))
        course = next(item for item in selectable_courses(snapshot) if item.node_id == 101)
        resumed = _review_and_confirm_course_plan(
            planner=planner, selection=confirmation.review.plan.selection,
            selection_mode="SELECTED", snapshot=snapshot, course=course,
            download_root=sandbox.download_root, max_media_items=5, max_transfer_bytes=1000,
            selection_prompt=lambda _: "s", console=Console(file=io.StringIO()),
        )
        assert resumed is not None
        assert resumed.review.plan.pending[0].part_bytes == 60
        result = asyncio.run(sandbox.execute(sandbox.authorize(resumed)))
        assert result.status == "CONCLUIDO"
        assert result.planned_overlap_bytes == 60
        assert result.proof_verified_bytes == 120
        assert result.proof_received_bytes == 120
        assert result.overlap_received_bytes == 60
        assert result.transferred_bytes == 320
        assert result.validated_bytes == 200
        assert result.budget_charged_bytes == 320


def test_all_course_excludes_unknown_size_without_transfer() -> None:
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox, selection_mode="ALL_CATALOGED", unknown=True)
        summary = asyncio.run(sandbox.execute(sandbox.authorize(confirmation)))
        assert summary.status == "PARCIAL"
        assert summary.excluded == 1
        assert ((-1001, 20, 0), "EXCLUDED", "UNKNOWN_SIZE") in summary.outcomes
        assert sandbox.gateway_calls == ((-1001, 10, 0),)


@pytest.mark.parametrize("changed_cap", ["items", "bytes"])
def test_changed_limits_after_confirmation_block_without_transfer(changed_cap) -> None:
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)
        if changed_cap == "items":
            changed_review = replace(confirmation.review, max_media_items=1)
        else:
            changed_review = replace(confirmation.review, max_transfer_bytes=1)
        changed = replace(confirmation, review=changed_review)
        summary = asyncio.run(sandbox.execute(sandbox.authorize(changed)))
        assert summary.status == "BLOQUEADO"
        assert not sandbox.gateway_calls


@pytest.mark.parametrize("terminal", [False, True])
def test_fake_gateway_failure_uses_existing_retry_policy(monkeypatch, terminal) -> None:
    from telegram_courses.course_offline_execution import _MemoryGateway
    from telegram_courses.downloads import DownloadGatewayError

    original = _MemoryGateway.stream_media
    attempts = []

    async def failing_stream(self, *args, **kwargs):
        attempts.append(args[1])
        if terminal or len(attempts) == 1:
            raise DownloadGatewayError("ACCESS_DENIED" if terminal else "NETWORK")
        async for chunk in original(self, *args, **kwargs):
            yield chunk

    monkeypatch.setattr(_MemoryGateway, "stream_media", failing_stream)
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)
        summary = asyncio.run(sandbox.execute(sandbox.authorize(confirmation)))
        if terminal:
            assert summary.status == "FALHA"
            assert attempts == [10, 20]
            assert summary.failed == 2
        else:
            assert summary.status == "CONCLUIDO"
            assert attempts == [10, 10, 20]
            assert summary.completed == 2


def test_offline_queue_never_runs_more_than_one_media_at_once(monkeypatch) -> None:
    from telegram_courses.course_offline_execution import _MemoryGateway

    original = _MemoryGateway.stream_media
    active = 0
    maximum = 0

    async def observed_stream(self, *args, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        try:
            await asyncio.sleep(0.01)
            async for chunk in original(self, *args, **kwargs):
                yield chunk
        finally:
            active -= 1

    monkeypatch.setattr(_MemoryGateway, "stream_media", observed_stream)
    with OfflineCourseSandbox(PAYLOADS) as sandbox:
        confirmation = _prepare(sandbox)
        result = asyncio.run(sandbox.execute(sandbox.authorize(confirmation)))
        assert result.status == "CONCLUIDO"
        assert maximum == 1


@pytest.mark.parametrize("slow", [False, True])
def test_visual_observer_failure_or_delay_does_not_stop_queue(monkeypatch, slow) -> None:
    from telegram_courses.course_offline_execution import _MemoryGateway

    original = _MemoryGateway.stream_media
    entered, release = Event(), Event()

    def observer(_snapshot):
        entered.set()
        if slow:
            release.wait(3)
        else:
            raise RuntimeError("synthetic presentation failure")

    async def wait_for_observer(self, *args, **kwargs):
        while not entered.is_set():
            await asyncio.sleep(0.005)
        async for chunk in original(self, *args, **kwargs):
            yield chunk

    monkeypatch.setattr(_MemoryGateway, "stream_media", wait_for_observer)
    try:
        with OfflineCourseSandbox(PAYLOADS) as sandbox:
            confirmation = _prepare(sandbox)
            summary = asyncio.run(sandbox.execute(sandbox.authorize(confirmation), observer=observer))
            assert summary.status == "CONCLUIDO"
            assert summary.transferred_bytes == 200
            if slow:
                assert summary.presentation_incomplete
            else:
                assert summary.presentation_failed
    finally:
        release.set()


def test_offline_execution_import_does_not_load_session_module() -> None:
    result = subprocess.run(
        [sys.executable, "-B", "-c",
         "import sys; import telegram_courses.course_offline_execution; "
         "assert 'telegram_courses.telethon_session' not in sys.modules"],
        capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
