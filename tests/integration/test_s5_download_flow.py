from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import aiosqlite
import pytest

from telegram_courses.auth import AuthState
from telegram_courses.cli import main
from telegram_courses.download_repository import DownloadRepository
from telegram_courses.downloads import SingleMediaDownloadApplication, destination_paths
from telegram_courses.s5_downloads import (
    DownloadPlanner,
    DownloadQueue,
    DownloadSelection,
)

CHANNEL = -100505
CONTENT = {
    101: b"first lesson",
    102: b"second lesson",
    103: b"third lesson",
    201: b"outside course",
}


async def seed_s5_database(path) -> None:
    repo = DownloadRepository(path)
    await repo.migrate()
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT INTO channels(telegram_chat_id,title,created_at,updated_at) VALUES(?,?,?,?)",
            (CHANNEL, "Synthetic courses", "now", "now"),
        )
        node_ids: dict[str, int] = {}
        definitions = (
            ("course-a", None, "course", "Curso A", 1),
            ("module-a", "course-a", "module", "Módulo A", 1),
            ("lesson-1", "module-a", "lesson", "Aula 1", 1),
            ("lesson-2", "module-a", "lesson", "Aula 2", 2),
            ("module-b", "course-a", "module", "Módulo B", 2),
            ("lesson-3", "module-b", "lesson", "Aula 3", 1),
            ("course-b", None, "course", "Curso B", 2),
            ("lesson-outside", "course-b", "lesson", "Aula externa", 1),
        )
        for key, parent, kind, title, ordinal in definitions:
            cursor = await db.execute(
                "INSERT INTO catalog_nodes(channel_id,parent_id,kind,ordinal,title,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (CHANNEL, node_ids.get(parent), kind, ordinal, title, "now", "now"),
            )
            node_ids[key] = cursor.lastrowid
        await db.execute(
            "INSERT INTO catalog_runs(id,channel_id,parser_key,grammar_version,status,started_at,finished_at,"
            "source_message_count,catalog_node_count,unresolved_count) "
            "VALUES('synthetic-catalog',?,'synthetic','v1','COMPLETE','now','now',5,8,0)",
            (CHANNEL,),
        )
        media = (
            (101, "lesson-1", "DOCUMENT", "media-101", CONTENT[101]),
            (102, "lesson-2", "DOCUMENT", "media-102", CONTENT[102]),
            (103, "lesson-3", "DOCUMENT", "media-103", CONTENT[103]),
            (104, "lesson-2", "DOCUMENT", "media-104", None),
            (201, "lesson-outside", "DOCUMENT", "media-201", CONTENT[201]),
        )
        for message_id, lesson, kind, media_id, payload in media:
            await db.execute(
                "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) "
                "VALUES(?,?,?,?,?)",
                (CHANNEL, message_id, "2026-01-01T00:00:00+00:00", "now", "now"),
            )
            await db.execute(
                "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,"
                "telegram_media_id,original_filename,file_size_bytes,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (CHANNEL, message_id, 0, node_ids[lesson], kind, media_id, f"{message_id}.bin",
                 len(payload) if payload is not None else None, "now", "now"),
            )
        await db.execute(
            "INSERT INTO scan_runs(id,channel_id,status,started_at,finished_at,stop_reason) "
            "VALUES('synthetic-run',?,'COMPLETE','now','now',NULL)", (CHANNEL,),
        )
        await db.commit()


class FakeGateway:
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0
        self.calls: dict[int, int] = defaultdict(int)
        self.requested_bytes: list[int] = []

    async def restore(self):
        return AuthState.AUTHENTICATED

    async def stream_media(
        self, channel_id, message_id, ordinal, *, telegram_media_id, expected_bytes,
        reserve_chunk=None,
    ):
        assert channel_id == CHANNEL and ordinal == 0
        payload = CONTENT[message_id]
        assert expected_bytes == len(payload)
        self.calls[message_id] += 1
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            if reserve_chunk is not None:
                request_bytes = min(256 * 1024, expected_bytes)
                self.requested_bytes.append(request_bytes)
                reservation = await reserve_chunk(request_bytes)
                assert reservation is not None
                await asyncio.sleep(0.01)
                reservation.received(len(payload))
            else:
                await asyncio.sleep(0.01)
            yield payload
        finally:
            self.active -= 1

    async def close(self):
        pass


def download_snapshot(database, root, expected_messages):
    with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert tuple(db.execute(
            "SELECT COUNT(*),COUNT(DISTINCT media_item_id) FROM downloads"
        ).fetchone()) == (len(expected_messages), len(expected_messages))
        assert tuple(db.execute(
            "SELECT COUNT(*),COUNT(DISTINCT channel_id || ':' || "
            "telegram_message_id || ':' || media_ordinal) FROM media_items"
        ).fetchone()) == (5, 5)
        rows = [dict(row) for row in db.execute(
            "SELECT d.*,m.telegram_message_id FROM downloads d "
            "JOIN media_items m ON m.id=d.media_item_id ORDER BY m.telegram_message_id"
        ).fetchall()]
    assert {row["telegram_message_id"] for row in rows} == expected_messages
    files = {path for path in root.rglob("*") if path.is_file()}
    assert files == {Path(row["final_path"]) for row in rows}
    physical = {}
    for row in rows:
        path = Path(row["final_path"])
        payload = CONTENT[row["telegram_message_id"]]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert row["state"] == "DOWNLOADED"
        assert row["expected_bytes"] == row["downloaded_bytes"] == path.stat().st_size == len(payload)
        assert row["sha256"] == digest == hashlib.sha256(payload).hexdigest()
        assert path.read_bytes() == payload
        physical[path] = (path.stat().st_size, digest, path.stat().st_mtime_ns)
    return rows, physical


@pytest.mark.parametrize("scope,expected_messages", [
    ("module", {101, 102}),
    ("course", {101, 102, 103}),
])
def test_s5_course_plan_scope_exclusions_and_queue_rerun(
    tmp_path, monkeypatch, scope, expected_messages,
) -> None:
    database, root = tmp_path / "catalog.sqlite3", tmp_path / "downloads"
    gateway = FakeGateway()

    async def exercise():
        await seed_s5_database(database)
        planner = DownloadPlanner(database, root)
        course_id = next(
            node_id for node_id, label in planner.selectable_nodes(CHANNEL, "course")
            if "Curso A" in label
        )
        course_plan = await planner.build(DownloadSelection(CHANNEL, "course", course_id))
        assert course_plan.lesson_count == 3
        assert {item.identity[1] for item in course_plan.pending} == {101, 102, 103}
        lesson_id = next(
            node_id for node_id, label in planner.selectable_nodes(CHANNEL, "lesson")
            if "Aula 1" in label
        )
        lesson_plan = await planner.build(DownloadSelection(CHANNEL, "lesson", lesson_id))
        assert [item.identity[1] for item in lesson_plan.pending] == [101]
        choices = planner.selectable_nodes(CHANNEL, "module")
        selected_module = next(node_id for node_id, label in choices if "Módulo A" in label)
        plan = await planner.build(DownloadSelection(CHANNEL, "module", selected_module))
        assert plan.lesson_count == 2
        assert len(plan.pending) == 2
        assert len(plan.excluded) == 1
        assert plan.excluded[0].reason == "UNKNOWN_SIZE"
        assert all(item.identity[1] != 103 for item in plan.items)
        if scope == "course":
            plan = course_plan
        assert {item.identity[1] for item in plan.pending} == expected_messages
        assert all(item.identity[1] != 201 for item in plan.items)
        repository = DownloadRepository(database)
        for item in plan.pending:
            candidate = await repository.select_candidate(*item.identity)
            assert candidate == item.candidate
            assert destination_paths(root, candidate) == destination_paths(root, item.candidate)
        reports = []
        app = SingleMediaDownloadApplication(repository, gateway, root)
        queue = DownloadQueue(
            repository, app, workers=2, progress_callback=reports.append,
        )
        first = await queue.run(plan)
        assert sum(status == "COMPLETED" for _, status, _ in first.outcomes) == len(expected_messages)
        before = download_snapshot(database, root, expected_messages)
        assert first.transferred_bytes == sum(len(CONTENT[message]) for message in expected_messages)
        # Per-request reservation telemetry is required for capped and uncapped
        # streams; only the aggregate limit differs between those modes.
        assert sorted(gateway.requested_bytes) == sorted(
            len(CONTENT[message]) for message in expected_messages
        )
        assert first.attempts == len(expected_messages) and first.failed == 0
        assert reports[-1]["completed"] == len(expected_messages)
        assert reports[-1]["pending"] == reports[-1]["running"] == 0
        calls_before = dict(gateway.calls)
        second_plan = await planner.build(plan.selection)
        assert second_plan.plan_id == plan.plan_id
        assert {item.identity[1] for item in second_plan.already_valid} == expected_messages
        assert second_plan.pending == second_plan.blocked == ()
        assert second_plan.pending_bytes == 0
        assert second_plan.excluded == plan.excluded

        async def unexpected_download(*_args):
            raise AssertionError("already-valid item scheduled for download")

        def unexpected_task(*_args):
            raise AssertionError("worker created for an empty pending queue")

        with monkeypatch.context() as rerun_patch:
            rerun_patch.setattr(app, "download", unexpected_download)
            rerun_patch.setattr(asyncio, "create_task", unexpected_task)
            second = await queue.run(second_plan)
        assert dict(gateway.calls) == calls_before
        assert download_snapshot(database, root, expected_messages) == before
        assert second.transferred_bytes == second.attempts == second.failed == 0
        assert not second.cancelled
        assert reports[-1]["already_valid"] == len(expected_messages)
        assert reports[-1]["pending"] == reports[-1]["running"] == reports[-1]["completed"] == 0
        assert reports[-1]["failed"] == reports[-1]["blocked"] == reports[-1]["cancelled"] == 0
        assert reports[-1]["excluded"] == 1
        assert reports[-1]["total"] == len(second_plan.items)
        assert reports[-1]["bytes_transferred"] == 0
        assert reports[-1]["bytes_expected"] == first.transferred_bytes
        return first, second, second_plan

    first, second, second_plan = asyncio.run(exercise())
    assert sum(status == "COMPLETED" for _, status, _ in first.outcomes) == len(expected_messages)
    assert {identity[1] for identity, status, _ in second.outcomes if status == "ALREADY_VALID"} == expected_messages
    assert sum(status == "ALREADY_VALID" for _, status, _ in second.outcomes) == len(expected_messages)
    assert gateway.calls == {message: 1 for message in expected_messages}
    assert 1 <= gateway.maximum_active <= 2
    assert second_plan.pending_bytes == 0


def test_s5_selectable_nodes_reject_inactive_ancestor(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"

    async def deactivate_ancestor():
        await seed_s5_database(database)
        async with aiosqlite.connect(database) as db:
            await db.execute(
                "UPDATE catalog_nodes SET is_active=0 WHERE title='Curso A'"
            )
            await db.commit()

    asyncio.run(deactivate_ancestor())
    planner = DownloadPlanner(database, tmp_path / "downloads")

    course_choices = planner.selectable_nodes(CHANNEL, "course")
    lesson_choices = planner.selectable_nodes(CHANNEL, "lesson")
    assert all("Curso A" not in label for _, label in course_choices)
    assert all(
        lesson not in label
        for _, label in lesson_choices
        for lesson in ("Aula 1", "Aula 2", "Aula 3")
    )


def test_s5_preview_exposes_conditional_resume_without_mutating_state(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    async def prepare():
        await seed_s5_database(database)
        repository = DownloadRepository(database)
        candidate = await repository.select_candidate(CHANNEL, 101, 0)
        final, partial = destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        partial.write_bytes(CONTENT[101][:3])
        await repository.start(candidate, final, partial)
        await repository.transition(
            candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=2,
            failure_category="NETWORK",
        )
        return candidate, final, partial

    candidate, _final, partial = asyncio.run(prepare())
    planner = DownloadPlanner(database, root)
    plan = asyncio.run(planner.build(DownloadSelection(CHANNEL)))
    item = next(item for item in plan.items if item.identity[1] == 101)
    before = (partial.read_bytes(), partial.parent.exists(), database.read_bytes())
    replay = asyncio.run(planner.build(DownloadSelection(CHANNEL)))
    after = (partial.read_bytes(), partial.parent.exists(), database.read_bytes())

    assert item.status == "CONDITIONAL_RESUME_CANDIDATE"
    assert item.candidate == candidate
    assert (item.part_bytes, item.wire_offset, item.overlap_bytes) == (3, 0, 3)
    assert item.estimated_payload_bytes == len(CONTENT[101])
    assert item.estimated_additional_disk_bytes == len(CONTENT[101]) - 3
    assert item in plan.pending
    assert replay.plan_id == plan.plan_id
    assert before == after


def test_s5_preview_is_offline_and_disk_gate_blocks_before_transfer(tmp_path, capsys) -> None:
    database, root = tmp_path / "catalog.sqlite3", tmp_path / "downloads"
    asyncio.run(seed_s5_database(database))
    assert main([
        "download", "plan", "--channel-id", str(CHANNEL), "--database", str(database),
        "--download-dir", str(root),
    ], credentials_loader=lambda: (_ for _ in ()).throw(AssertionError("credentials accessed"))) == 0
    preview = capsys.readouterr().out
    assert "pendentes=4" in preview
    normalized_preview = " ".join(preview.split())
    assert "download inicial não comprova hash remoto independente" in normalized_preview
    assert "retomada bloqueia se a prova remota estiver ausente ou inválida" in normalized_preview
    assert "REMOTE_HASH_FULL / V1 fail-closed" not in preview

    gateway = FakeGateway()

    async def exercise():
        planner = DownloadPlanner(database, root)
        plan = await planner.build(DownloadSelection(CHANNEL))
        app = SingleMediaDownloadApplication(DownloadRepository(database), gateway, root)
        queue = DownloadQueue(DownloadRepository(database), app, free_space=lambda _path: 0)
        try:
            await queue.run(plan)
        except Exception as error:
            return getattr(error, "category", None)

    category = asyncio.run(exercise())
    assert category == "INSUFFICIENT_DISK_SPACE"
    assert gateway.calls == {}
