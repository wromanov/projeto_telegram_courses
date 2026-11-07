from __future__ import annotations

import asyncio
import hashlib
import io
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest
from rich.console import Console
from tests.integration.test_interactive_catalog import _seed_interactive_database

from telegram_courses.auth import AuthState
from telegram_courses.cli import _interactive_live_executor
from telegram_courses.config import TelegramCredentials
from telegram_courses.course_download_planning import (
    course_download_selection,
    create_course_plan_review,
)
from telegram_courses.course_execution import ConfirmedCoursePlan
from telegram_courses.course_live_execution import LiveCourseExecutor
from telegram_courses.course_progress_rich import render_execution_summary
from telegram_courses.course_review_context import load_course_review_context
from telegram_courses.database_preparation import create_verified_backup
from telegram_courses.download_repository import DownloadRepository
from telegram_courses.downloads import DownloadError, RemoteFileHash, destination_paths
from telegram_courses.s5_downloads import DownloadPlanner

CHANNEL_ID = -1001
COURSE_ID = 101
IDENTITY = (CHANNEL_ID, 10, 0)
PAYLOAD = b"synthetic payload for live queue"
MEDIA_ID = "synthetic-1"


class _FakeGateway:
    def __init__(
        self,
        *,
        block_after_partial: bool = False,
        hashes_available: bool = True,
        terminal_geometry: bool = False,
        payload: bytes = PAYLOAD,
        restore_state: AuthState = AuthState.AUTHENTICATED,
        fail_close: bool = False,
    ) -> None:
        self.calls: list[tuple[int, int, int]] = []
        self.closed = False
        self.restore_calls = 0
        self.restore_state = restore_state
        self.fail_close = fail_close
        self.started = asyncio.Event()
        self.block_after_partial = block_after_partial
        self.hashes_available = hashes_available
        self.terminal_geometry = terminal_geometry
        self.payload = payload
        self.stream_calls = 0
        self.hash_calls = 0

    async def restore(self) -> AuthState:
        self.restore_calls += 1
        return self.restore_state

    def _require_restored(self) -> None:
        assert self.restore_calls == 1
        assert self.restore_state is AuthState.AUTHENTICATED

    async def stream_media(
        self,
        channel_id: int,
        message_id: int,
        media_ordinal: int,
        *,
        telegram_media_id: str,
        expected_bytes: int,
        reserve_chunk=None,
        offset: int = 0,
    ):
        self._require_restored()
        identity = (channel_id, message_id, media_ordinal)
        assert identity == IDENTITY
        assert telegram_media_id == MEDIA_ID
        assert expected_bytes == len(self.payload)
        self.stream_calls += 1
        self.calls.append(identity)
        data = self.payload[offset:]
        chunk = data[: max(1, len(data) // 2)] if self.block_after_partial else data
        reservation = await reserve_chunk(len(chunk)) if reserve_chunk is not None else None
        if reserve_chunk is not None:
            assert reservation is not None
            reservation.received(len(chunk))
        yield chunk
        self.started.set()
        if self.block_after_partial:
            await asyncio.Event().wait()
        if reservation is not None and not self.block_after_partial:
            # The queue charges the chunk before the consumer sees it; no second
            # reservation is needed for this one-chunk synthetic transfer.
            pass

    async def get_file_hashes(
        self,
        channel_id: int,
        message_id: int,
        media_ordinal: int,
        *,
        telegram_media_id: str,
        expected_bytes: int,
        offset: int = 0,
    ) -> tuple[RemoteFileHash, ...]:
        self._require_restored()
        assert (channel_id, message_id, media_ordinal) == IDENTITY
        assert telegram_media_id == MEDIA_ID
        assert expected_bytes == len(self.payload)
        self.hash_calls += 1
        if not self.hashes_available:
            return ()
        if self.terminal_geometry:
            return tuple(
                RemoteFileHash(
                    start, 128 * 1024,
                    hashlib.sha256(self.payload[start:start + 128 * 1024]).digest(),
                )
                for start in range(offset, expected_bytes, 128 * 1024)
            )
        block = PAYLOAD[offset:]
        if not block:
            return ()
        return (RemoteFileHash(offset, len(block), hashlib.sha256(block).digest()),)

    async def validate_media_identity(self, *args, **kwargs) -> bool:
        self._require_restored()
        return True

    async def close(self) -> None:
        self.closed = True
        if self.fail_close:
            raise RuntimeError("synthetic close failure")


def _prepare(
    tmp_path: Path, *, payload: bytes = PAYLOAD, max_transfer_bytes: int = 1000,
) -> ConfirmedCoursePlan:
    database = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(database))
    with closing(sqlite3.connect(database)) as db:
        db.execute(
            "UPDATE media_items SET file_size_bytes=?, telegram_media_id=?, "
            "remote_observation_state='OBSERVED' WHERE channel_id=? AND telegram_message_id=? AND media_ordinal=?",
            (len(payload), MEDIA_ID, *IDENTITY),
        )
        db.commit()

    download_root = tmp_path / "downloads"
    download_root.mkdir()
    return _confirm_existing_database(
        database, download_root, max_transfer_bytes=max_transfer_bytes,
    )


def _confirm_existing_database(
    database: Path, download_root: Path, *, max_transfer_bytes: int = 1000,
) -> ConfirmedCoursePlan:
    planner = DownloadPlanner(database, download_root)
    selection = course_download_selection(
        CHANNEL_ID, COURSE_ID, media_identities=(IDENTITY,),
    )
    (
        _snapshot,
        _course,
        _options,
        _ambiguous,
        fresh_selection,
        exclusions,
        catalog_context,
    ) = asyncio.run(load_course_review_context(
        planner,
        channel_id=CHANNEL_ID,
        course_id=COURSE_ID,
        selection_mode="SELECTED",
        exact_selection=selection,
    ))
    assert fresh_selection is not None
    plan = asyncio.run(planner.build(fresh_selection))
    review = create_course_plan_review(
        plan,
        selection_mode="SELECTED",
        download_root=download_root,
        integrity_mode="REMOTE_HASH_REQUIRED",
        max_media_items=2,
        max_transfer_bytes=max_transfer_bytes,
        observed_exclusions=exclusions,
        catalog_context=catalog_context,
    )
    assert review.can_confirm
    assert plan.pending
    return ConfirmedCoursePlan(database, review)


def _executor(gateway_factory, *, attempts: int = 3) -> LiveCourseExecutor:
    from telegram_courses.config import TelegramCredentials

    return LiveCourseExecutor(
        gateway_factory,
        lambda: TelegramCredentials(api_id=12345, api_hash="synthetic-api-hash"),
        attempts_per_media=attempts,
    )


def _authorize(
    executor: LiveCourseExecutor,
    confirmation: ConfirmedCoursePlan,
    *,
    answer: str = "s",
):
    backup = create_verified_backup(confirmation.database)
    return executor.authorize(
        confirmation,
        backup,
        selection_prompt=lambda _prompt: answer,
        require_tty=False,
    )


def test_live_authorization_requires_explicit_yes_and_is_single_use(tmp_path: Path) -> None:
    confirmation = _prepare(tmp_path)
    gateways: list[_FakeGateway] = []

    def factory(_credentials, channel_id):
        assert channel_id == CHANNEL_ID
        gateway = _FakeGateway()
        gateways.append(gateway)
        return gateway

    executor = _executor(factory)
    denied = _authorize(executor, confirmation, answer="n")
    assert denied is None
    assert not gateways

    authorization = _authorize(executor, confirmation)
    assert authorization is not None
    summary = asyncio.run(executor.execute(authorization))
    assert summary.status == "CONCLUIDO"
    assert summary.completed == 1
    assert summary.transferred_bytes == len(PAYLOAD)
    assert len(gateways) == 1
    assert gateways[0].restore_calls == 1
    assert gateways[0].calls == [IDENTITY]
    assert gateways[0].closed

    with pytest.raises(DownloadError) as error:
        asyncio.run(executor.execute(authorization))
    assert error.value.category == "LIVE_EXECUTION_NOT_AUTHORIZED"


def test_remote_hash_required_blocks_new_media_without_complete_remote_hash(tmp_path: Path) -> None:
    confirmation = _prepare(tmp_path)
    gateways: list[_FakeGateway] = []

    def factory(_credentials, _channel_id):
        gateway = _FakeGateway(hashes_available=False)
        gateways.append(gateway)
        return gateway

    executor = _executor(factory, attempts=1)
    summary = asyncio.run(executor.execute(_authorize(executor, confirmation)))
    assert summary.status == "FALHA"
    assert summary.completed == 0 and summary.failed == 1
    assert summary.outcomes == ((IDENTITY, "FAILED", "REMOTE_HASHES_INCOMPLETE"),)
    assert len(gateways) == 1 and gateways[0].closed
    with closing(sqlite3.connect(confirmation.database)) as db:
        row = db.execute(
            "SELECT state, downloaded_bytes FROM downloads WHERE media_item_id=("
            "SELECT id FROM media_items WHERE channel_id=? AND telegram_message_id=? AND media_ordinal=?)",
            IDENTITY,
        ).fetchone()
        assert row == ("FAILED_RETRYABLE", len(PAYLOAD))


def test_complete_partial_is_hashed_and_finalized_without_payload(tmp_path: Path) -> None:
    payload = (b"synthetic terminal hash payload" * 300_000)[:8_900_624]
    confirmation = _prepare(tmp_path, payload=payload, max_transfer_bytes=10_000_000)
    candidate = confirmation.review.plan.pending[0].candidate
    assert candidate is not None
    final, partial = destination_paths(
        Path(confirmation.review.download_root), candidate,
    )
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(payload)

    repository = DownloadRepository(confirmation.database)

    async def seed_failed_full_partial():
        await repository.start(candidate, final, partial)
        await repository.checkpoint(candidate.media_item_id, len(payload))
        await repository.transition(
            candidate.media_item_id, "FAILED_RETRYABLE",
            downloaded_bytes=len(payload), failure_category="REMOTE_HASH_RANGE_INVALID",
        )

    asyncio.run(seed_failed_full_partial())
    confirmation = _confirm_existing_database(
        confirmation.database, Path(confirmation.review.download_root),
        max_transfer_bytes=1_000_000,
    )
    gateway = _FakeGateway(payload=payload, terminal_geometry=True)
    executor = _executor(lambda *_args: gateway, attempts=1)
    summary = asyncio.run(executor.execute(_authorize(executor, confirmation)))

    assert summary.status == "CONCLUIDO"
    assert summary.completed == 1
    assert summary.transferred_bytes == 0
    assert summary.validated_bytes == len(payload)
    assert gateway.stream_calls == 0
    assert gateway.hash_calls == 2
    assert final.is_file() and final.read_bytes() == payload
    assert not partial.exists()


def test_live_authorization_rejects_backup_bound_to_other_database(tmp_path: Path) -> None:
    confirmation = _prepare(tmp_path)
    other_database = tmp_path / "other.sqlite3"
    asyncio.run(_seed_interactive_database(other_database))
    backup = create_verified_backup(other_database)
    executor = _executor(lambda *_args: pytest.fail("gateway must not be constructed"))

    with pytest.raises(DownloadError) as error:
        executor.authorize(
            confirmation,
            backup,
            selection_prompt=lambda _prompt: "s",
            require_tty=False,
        )
    assert error.value.category == "OPERATIONAL_BACKUP_UNVERIFIED"


def test_live_authorization_rejects_modified_backup_receipt(tmp_path: Path) -> None:
    confirmation = _prepare(tmp_path)
    backup = create_verified_backup(confirmation.database)
    executor = _executor(lambda *_args: pytest.fail("gateway must not be constructed"))

    with pytest.raises(DownloadError) as error:
        executor.authorize(
            confirmation,
            replace(backup, sha256="0" * 64),
            selection_prompt=lambda _prompt: "s",
            require_tty=False,
        )
    assert error.value.category == "OPERATIONAL_BACKUP_UNVERIFIED"


def test_plan_derivation_blocks_before_gateway_creation(tmp_path: Path, monkeypatch) -> None:
    import telegram_courses.course_live_execution as live

    confirmation = _prepare(tmp_path)
    executor = _executor(lambda *_args: pytest.fail("stale plan must block first"))
    authorization = _authorize(executor, confirmation)
    assert authorization is not None
    original_build = live.DownloadPlanner.build

    async def changed_build(planner, selection):
        current = await original_build(planner, selection)
        return replace(current, scope_title="changed-after-confirmation")

    monkeypatch.setattr(live.DownloadPlanner, "build", changed_build)
    summary = asyncio.run(executor.execute(authorization))
    assert summary.status == "BLOQUEADO"
    assert all(state == "BLOCKED" for _, state, _ in summary.outcomes)


def test_reopen_after_completion_dedupes_without_gateway_or_payload(tmp_path: Path) -> None:
    confirmation = _prepare(tmp_path)
    first_gateways: list[_FakeGateway] = []
    first_executor = _executor(lambda *_args: first_gateways.append(_FakeGateway()) or first_gateways[-1])
    first_auth = _authorize(first_executor, confirmation)
    assert first_auth is not None
    first_result = asyncio.run(first_executor.execute(first_auth))
    assert first_result.status == "CONCLUIDO"
    assert first_gateways[0].calls == [IDENTITY]

    reopened = _prepare_review_on_existing_database(confirmation)
    assert reopened.review.plan.already_valid
    second_gateways: list[object] = []
    second_executor = _executor(lambda *_args: second_gateways.append(object()) or second_gateways[-1])
    second_auth = _authorize(second_executor, reopened)
    assert second_auth is not None
    second_result = asyncio.run(second_executor.execute(second_auth))
    assert second_result.status == "TODOS_JA_VALIDOS"
    assert second_result.already_valid == 1
    assert not second_gateways
    assert first_gateways[0].calls == [IDENTITY]


def _prepare_review_on_existing_database(
    confirmation: ConfirmedCoursePlan,
) -> ConfirmedCoursePlan:
    database = confirmation.database
    download_root = Path(confirmation.review.download_root)
    planner = DownloadPlanner(database, download_root)
    selection = confirmation.review.plan.selection
    (
        _snapshot,
        _course,
        _options,
        _ambiguous,
        fresh_selection,
        exclusions,
        catalog_context,
    ) = asyncio.run(load_course_review_context(
        planner,
        channel_id=CHANNEL_ID,
        course_id=COURSE_ID,
        selection_mode="SELECTED",
        exact_selection=selection,
    ))
    assert fresh_selection is not None
    plan = asyncio.run(planner.build(fresh_selection))
    review = create_course_plan_review(
        plan,
        selection_mode="SELECTED",
        download_root=download_root,
        integrity_mode="REMOTE_HASH_REQUIRED",
        max_media_items=2,
        max_transfer_bytes=1000,
        observed_exclusions=exclusions,
        catalog_context=catalog_context,
    )
    return ConfirmedCoursePlan(database, review)


def test_live_run_uses_one_s5_worker_and_rich_observer(tmp_path: Path, monkeypatch) -> None:
    import telegram_courses.course_execution as execution

    confirmation = _prepare(tmp_path)
    gateways: list[_FakeGateway] = []

    def factory(_credentials, _channel_id):
        gateway = _FakeGateway()
        gateways.append(gateway)
        return gateway

    observed = []
    observed_workers = []
    real_queue = execution.DownloadQueue

    class CapturingQueue(real_queue):
        def __init__(self, *args, **kwargs):
            observed_workers.append(kwargs["workers"])
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(execution, "DownloadQueue", CapturingQueue)
    executor = _executor(factory)
    authorization = _authorize(executor, confirmation)
    assert authorization is not None
    summary = asyncio.run(executor.execute(authorization, observer=observed.append))

    output = io.StringIO()
    render_execution_summary(summary, Console(file=output, force_terminal=False))
    assert summary.status == "CONCLUIDO"
    assert observed_workers == [1]
    assert observed
    assert observed[-1].identity == IDENTITY
    assert "CONCLUIDO" in output.getvalue()
    assert gateways[0].closed


def test_invalid_restored_session_blocks_before_queue_and_closes_gateway(tmp_path: Path) -> None:
    confirmation = _prepare(tmp_path)
    gateway = _FakeGateway(restore_state=AuthState.SESSION_INVALID)
    executor = _executor(lambda *_args: gateway)
    authorization = _authorize(executor, confirmation)
    assert authorization is not None

    summary = asyncio.run(executor.execute(authorization))

    assert summary.status == "BLOQUEADO"
    assert all(reason == "SESSION_INVALID" for _, _, reason in summary.outcomes)
    assert gateway.restore_calls == 1
    assert gateway.calls == []
    assert gateway.closed


def test_gateway_cleanup_failure_is_reported_without_rewriting_queue_result(tmp_path: Path) -> None:
    confirmation = _prepare(tmp_path)
    gateway = _FakeGateway(fail_close=True)
    executor = _executor(lambda *_args: gateway)
    authorization = _authorize(executor, confirmation)
    assert authorization is not None

    summary = asyncio.run(executor.execute(authorization))

    assert summary.status == "CONCLUIDO"
    assert summary.completed == 1
    assert summary.cleanup_failed
    assert gateway.closed


def test_cli_reports_gateway_cleanup_failure_and_returns_sanitized_error(
    tmp_path: Path, capsys,
) -> None:
    confirmation = _prepare(tmp_path)
    gateway = _FakeGateway(fail_close=True)

    result = _interactive_live_executor(
        confirmation,
        selection_prompt=lambda _prompt: "s",
        credentials_loader=lambda: TelegramCredentials(
            api_id=12345, api_hash="synthetic-api-hash",
        ),
        gateway_factory=lambda *_args: gateway,
        attempts_per_media=1,
        require_tty=False,
    )

    output = capsys.readouterr().out
    assert result == 4
    assert "Falha ao encerrar gateway" in output
    assert "Sim" in output
    assert "synthetic close failure" not in output
    assert gateway.calls == [IDENTITY]
    assert gateway.closed


def test_live_cancel_preserves_partial_and_prevents_next_admission(tmp_path: Path) -> None:
    confirmation = _prepare(tmp_path)
    gateway = _FakeGateway(block_after_partial=True)

    def factory(_credentials, _channel_id):
        return gateway

    executor = _executor(factory)
    authorization = _authorize(executor, confirmation)
    assert authorization is not None

    async def run_cancelled():
        cancel_event = asyncio.Event()
        task = asyncio.create_task(
            executor.execute(authorization, cancel_event=cancel_event),
        )
        await asyncio.wait_for(gateway.started.wait(), timeout=5)
        cancel_event.set()
        return await asyncio.wait_for(task, timeout=5)

    summary = asyncio.run(run_cancelled())
    assert summary.status == "CANCELADO"
    assert summary.cancelled == 1
    assert gateway.calls == [IDENTITY]
    assert gateway.closed
    partials = list(Path(confirmation.review.download_root).rglob("*.part"))
    assert len(partials) == 1
    assert 0 < partials[0].stat().st_size < len(PAYLOAD)
    with closing(sqlite3.connect(confirmation.database)) as db:
        state = db.execute(
            "SELECT state, downloaded_bytes FROM downloads WHERE media_item_id=("
            "SELECT id FROM media_items WHERE channel_id=? AND telegram_message_id=? AND media_ordinal=?)",
            IDENTITY,
        ).fetchone()
    assert state is not None
    assert state[0] != "DOWNLOADED"
    assert state[1] == partials[0].stat().st_size


def test_execution_authorization_refuses_non_tty_by_default(tmp_path: Path, monkeypatch) -> None:
    import telegram_courses.course_live_execution as live

    confirmation = _prepare(tmp_path)
    backup = create_verified_backup(confirmation.database)
    monkeypatch.setattr(live.sys, "stdin", io.StringIO(""))
    executor = _executor(lambda *_args: pytest.fail("gateway must not be constructed"))
    with pytest.raises(DownloadError) as error:
        executor.authorize(
            confirmation,
            backup,
            selection_prompt=lambda _prompt: "s",
        )
    assert error.value.category == "LIVE_EXECUTION_REQUIRES_TTY"
