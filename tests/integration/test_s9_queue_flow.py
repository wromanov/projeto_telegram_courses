from __future__ import annotations

import asyncio
import hashlib
import sqlite3

import aiosqlite

from telegram_courses.download_repository import DownloadRepository
from telegram_courses.downloads import (
    DownloadGatewayError,
    RemoteFileHash,
    SingleMediaDownloadApplication,
)
from telegram_courses.s5_downloads import (
    DownloadPlanner,
    DownloadQueue,
    DownloadSelection,
)
from telegram_courses.s9_operational_ledger import (
    F_CAP,
    S9OperationalLedger,
    S9QueueAccounting,
    _create_private_directory,
)

CHANNEL = -100709
MESSAGE = 709
PAYLOAD = b"s" * 400_001


async def _seed_database(path) -> None:
    repository = DownloadRepository(path)
    await repository.migrate()
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT INTO channels(telegram_chat_id,title,created_at,updated_at) VALUES(?,?,?,?)",
            (CHANNEL, "Synthetic S9", "now", "now"),
        )
        await db.execute(
            "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) "
            "VALUES(?,?,?,?,?)",
            (CHANNEL, MESSAGE, "2026-01-01T00:00:00+00:00", "now", "now"),
        )
        cursor = await db.execute(
            "INSERT INTO catalog_nodes(channel_id,kind,title,source_message_id,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?)",
            (CHANNEL, "lesson", "Synthetic lesson", MESSAGE, "now", "now"),
        )
        await db.execute(
            "INSERT INTO catalog_runs(id,channel_id,parser_key,grammar_version,status,started_at,finished_at,"
            "source_message_count,catalog_node_count,unresolved_count) "
            "VALUES('synthetic-s9-catalog',?,'synthetic','v1','COMPLETE','now','now',1,1,0)",
            (CHANNEL,),
        )
        await db.execute(
            "INSERT INTO scan_runs(id,channel_id,status,started_at,finished_at,stop_reason) "
            "VALUES('synthetic-s9-scan',?,'COMPLETE','now','now',NULL)",
            (CHANNEL,),
        )
        await db.execute(
            "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,"
            "telegram_media_id,original_filename,file_size_bytes,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (CHANNEL, MESSAGE, 0, cursor.lastrowid, "DOCUMENT", "synthetic-media",
             "lesson.bin", len(PAYLOAD), "now", "now"),
        )
        await db.commit()


class _OverlapRetryGateway:
    """Fake Gateway that reports response lengths through S5's request lease."""

    def __init__(self) -> None:
        self.stream_calls = 0
        self.offsets: list[int] = []
        self.received_bytes = 0
        self.hash_calls = 0

    async def validate_media_identity(self, *_args, **_kwargs) -> bool:
        return True

    async def get_file_hashes(
        self, *_args, expected_bytes, offset=0, **_kwargs,
    ) -> tuple[RemoteFileHash, ...]:
        self.hash_calls += 1
        records = (
            RemoteFileHash(0, 256 * 1024, hashlib.sha256(PAYLOAD[:256 * 1024]).digest()),
            RemoteFileHash(
                256 * 1024, expected_bytes - 256 * 1024,
                hashlib.sha256(PAYLOAD[256 * 1024:expected_bytes]).digest(),
            ),
        )
        return tuple(item for item in records if item.offset >= offset)

    async def stream_media(
        self, _channel, _message, _ordinal, *, offset=0, reserve_chunk,
        expected_bytes, **_kwargs,
    ):
        assert expected_bytes == len(PAYLOAD)
        self.stream_calls += 1
        self.offsets.append(offset)
        if self.stream_calls == 1:
            response_ranges = (
                (0, 256 * 1024),
                (256 * 1024, 64 * 1024),
            )
        else:
            response_ranges = ((offset, expected_bytes - offset),)
        for start, count in response_ranges:
            lease = await reserve_chunk(256 * 1024)
            assert lease is not None
            data = PAYLOAD[start:start + count]
            lease.received(len(data))
            self.received_bytes += len(data)
            yield data
        if self.stream_calls == 1:
            raise DownloadGatewayError("NETWORK")

    async def close(self) -> None:
        pass


def test_s9_f_queue_recovery_charges_retry_and_overlap_gateway_responses(
    tmp_path,
) -> None:
    database = tmp_path / "catalog.sqlite3"
    download_root = tmp_path / "downloads"
    ledger_guard = _create_private_directory(tmp_path / "private-ledger")
    ledger_path = ledger_guard.path / "operational-ledger.sqlite3"
    ledger_guard.close()

    async def exercise():
        await _seed_database(database)
        ledger = S9OperationalLedger.create(ledger_path)
        deadline = ledger.start_global_deadline()
        ledger.update_execution(
            gate="G1", status="RUNNING", elapsed_ms=0,
            deadline_ns=deadline, process_state="RUNNING",
        )
        gateway = _OverlapRetryGateway()
        repository = DownloadRepository(database)
        application = SingleMediaDownloadApplication(repository, gateway, download_root)
        planner = DownloadPlanner(database, download_root)
        plan = await planner.build(DownloadSelection(CHANNEL))
        accounting = S9QueueAccounting.register_plan(
            ledger, plan, profile="F", measurement_source="GATEWAY_RESPONSE",
        )
        first_queue = DownloadQueue(
            repository, application, workers=1, attempts_per_media=1,
            max_media_items=8, max_transfer_bytes=F_CAP,
            queue_accounting=accounting,
        )
        first = await first_queue.run(plan)
        assert first.failed == 1
        assert first.transferred_bytes == 320 * 1024
        assert ledger.snapshot()["budgets"]["F"]["observed"] == 320 * 1024

        alias = ledger.pseudonym(f"{CHANNEL}:{MESSAGE}:0")
        ledger.record_interruption(alias)
        resume_plan = await planner.build(DownloadSelection(CHANNEL))
        candidate = resume_plan.pending[0]
        assert candidate.status == "CONDITIONAL_RESUME_CANDIDATE"
        accounting = S9QueueAccounting.register_plan(
            ledger, resume_plan, profile="F",
            measurement_source="GATEWAY_RESPONSE", recovery=True,
        )
        resume_queue = DownloadQueue(
            repository, application, workers=1, attempts_per_media=1,
            max_media_items=8, max_transfer_bytes=F_CAP,
            queue_accounting=accounting,
        )
        resumed = await resume_queue.run(resume_plan)
        accounting.record_queue_result(
            status="COMPLETED", result="PASS", cause="NONE",
            observed_bytes=resumed.transferred_bytes,
        )
        return ledger, gateway, resumed

    ledger, gateway, resumed = asyncio.run(exercise())
    snapshot = ledger.snapshot()
    assert resumed.failed == 0
    # Recovery refetches the overlapping continuation once for remote hash
    # validation and again for the actual append. Both GetFile callbacks count.
    assert resumed.transferred_bytes == 2 * (len(PAYLOAD) - 256 * 1024)
    assert gateway.offsets == [0, 256 * 1024, 256 * 1024]
    assert gateway.received_bytes == 320 * 1024 + resumed.transferred_bytes
    assert gateway.hash_calls >= 1
    assert snapshot["budgets"]["F"]["observed"] == gateway.received_bytes
    assert snapshot["budgets"]["F"]["uncertain"] == 0
    assert snapshot["budgets"]["F"]["reserved"] == 0
    assert all(
        item["measurement_source"] == "GATEWAY_RESPONSE"
        for item in snapshot["reservations"]
    )
    assert snapshot["run"]["gate"] == "G5"
    assert snapshot["run"]["result"] == "PASS"
    with sqlite3.connect(tmp_path / "catalog.sqlite3") as db:
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        row = db.execute(
            "SELECT state,downloaded_bytes FROM downloads"
        ).fetchone()
    assert row == ("DOWNLOADED", len(PAYLOAD))
    files = [
        item for item in (tmp_path / "downloads").rglob("*")
        if item.is_file()
    ]
    assert len(files) == 1
    assert files[0].read_bytes() == PAYLOAD
