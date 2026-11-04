from __future__ import annotations

import asyncio
import json
import os

import aiosqlite

from telegram_courses.auth import AuthState
from telegram_courses.cli import main
from telegram_courses.config import TelegramCredentials
from telegram_courses.message_scanner import GatewayMessage
from telegram_courses.operational_logging import finalize_s9_child_exit_code
from telegram_courses.s9_operational_ledger import (
    S9OperationalLedger,
    _create_private_directory,
)
from telegram_courses.s9_supervisor import _creation_time, _windows_api
from telegram_courses.s9_supervisor_handshake import (
    S9_LEDGER_PATH_ENV,
    S9_SUPERVISED_CHILD_ENV,
)


def test_scan_cli_uses_fake_gateway_and_explicit_limits(tmp_path, capsys) -> None:
    chat_id = -1001234567890

    class FakeGateway:
        async def restore(self):
            return AuthState.AUTHENTICATED

        async def iter_channel_messages(
            self, selected_chat_id: int, *, through_message_id: int | None,
            before_message_id: int | None, limit: int,
        ):
            assert selected_chat_id == chat_id
            assert through_message_id is None
            assert limit == 10
            yield GatewayMessage(
                chat_id, 17, "2026-10-09T12:00:00+00:00", None,
                "synthetic CLI text", None,
            )

        async def close(self):
            pass

    database = tmp_path / "cli-scan.sqlite3"
    status = main(
        [
            "scan",
            "--channel-id", str(chat_id),
            "--max-messages", "10",
            "--timeout-seconds", "30",
            "--database", str(database),
        ],
        scan_gateway_factory=lambda _credentials: FakeGateway(),
        credentials_loader=lambda: TelegramCredentials(7, "synthetic-hash"),
    )
    assert status == 0
    assert "status=COMPLETE messages=1" in capsys.readouterr().out

    async def verify() -> None:
        db = await aiosqlite.connect(database)
        try:
            assert (await (await db.execute("SELECT text FROM messages")).fetchone())[0] == "synthetic CLI text"
            assert (await (await db.execute("SELECT status FROM sync_checkpoints")).fetchone())[0] == "COMPLETE"
        finally:
            await db.close()

    asyncio.run(verify())


def test_scan_cli_requires_explicit_timeout(tmp_path, capsys) -> None:
    status = main(
        ["scan", "--channel-id", "-1001234567890", "--max-messages", "10"],
        scan_gateway_factory=lambda _credentials: None,
    )
    assert status == 2
    event_line, message_line = capsys.readouterr().err.splitlines()
    assert json.loads(event_line)["event"] == "configuration.rejected"
    assert message_line == "configuration error"


def test_supervised_scan_reserves_and_reconciles_s9_observation_budget(
    tmp_path, monkeypatch, capsys,
) -> None:
    chat_id = -1001234567890
    run_guard = _create_private_directory(tmp_path / "s9-run")
    ledger_path = run_guard.path / "operational-ledger.sqlite3"
    run_guard.close()
    ledger = S9OperationalLedger.create(ledger_path)
    deadline_ns = ledger.start_global_deadline()
    ledger.update_execution(
        gate="G1", status="RUNNING", elapsed_ms=0,
        deadline_ns=deadline_ns, process_state="RUNNING", result="PASS",
    )
    api = _windows_api()
    ledger.record_critical_event(
        "CHILD_PROCESS_CONFIRMED",
        details={
            "stage": "scan",
            "pid": os.getpid(),
            "process_creation_time": _creation_time(api[13], api[14], api[6], os.getpid()),
        },
        event_id="a" * 32,
    )
    monkeypatch.setenv(S9_LEDGER_PATH_ENV, str(ledger_path))
    monkeypatch.setenv(S9_SUPERVISED_CHILD_ENV, "1")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_STAGE", "scan")

    class FakeGateway:
        async def restore(self):
            return AuthState.AUTHENTICATED

        async def iter_channel_messages(
            self, selected_chat_id: int, *, through_message_id: int | None,
            before_message_id: int | None, limit: int,
        ):
            assert selected_chat_id == chat_id
            assert limit == 10
            yield GatewayMessage(
                chat_id, 17, "2026-10-09T12:00:00+00:00", None,
                "synthetic S9 scan", None,
            )

        async def close(self):
            pass

    status: int | None = None
    try:
        status = main(
            [
                "scan", "--channel-id", str(chat_id), "--max-messages", "10",
                "--timeout-seconds", "30", "--database",
                str(run_guard.path / "catalog.sqlite3"),
            ],
            scan_gateway_factory=lambda _credentials: FakeGateway(),
            credentials_loader=lambda: TelegramCredentials(7, "synthetic-hash"),
        )
    finally:
        finalized_status = finalize_s9_child_exit_code(
            status if status is not None else 1,
        )

    assert status == 0
    assert finalized_status == 0
    assert "status=COMPLETE messages=1" in capsys.readouterr().out
    scans = ledger.snapshot()["scans"]
    assert len(scans) == 1
    assert scans[0]["max_messages"] == 10
    assert scans[0]["observed"] == 1
    assert scans[0]["state"] == "OBSERVED"
