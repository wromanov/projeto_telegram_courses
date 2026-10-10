from __future__ import annotations

import asyncio

import aiosqlite

from telegram_courses.auth import AuthState
from telegram_courses.cli import main
from telegram_courses.config import TelegramCredentials
from telegram_courses.message_scanner import GatewayMessage


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
    assert capsys.readouterr().err == "configuration error\n"
