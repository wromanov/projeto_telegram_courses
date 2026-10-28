from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from telegram_courses.auth import AuthState
from telegram_courses.catalog_application import CatalogApplication
from telegram_courses.cli import main
from telegram_courses.config import TelegramCredentials
from telegram_courses.message_scanner import GatewayMedia, GatewayMessage
from telegram_courses.sqlite_repository import SQLiteMessageRepository

CHAT = -1001234567890


class FakeGateway:
    def __init__(self, message_ids: tuple[int, ...]) -> None:
        self.message_ids = message_ids

    async def restore(self) -> AuthState:
        return AuthState.AUTHENTICATED

    def iter_channel_messages(
        self,
        channel_id: int,
        *,
        through_message_id: int | None,
        before_message_id: int | None,
        min_message_id: int | None,
        limit: int,
    ):
        assert channel_id == CHAT

        async def iterate():
            candidates = [
                message_id
                for message_id in sorted(self.message_ids, reverse=True)
                if (through_message_id is None or message_id <= through_message_id)
                and (before_message_id is None or message_id < before_message_id)
                and (min_message_id is None or message_id >= min_message_id)
            ]
            for message_id in candidates[:limit]:
                yield GatewayMessage(
                    CHAT,
                    message_id,
                    "2026-10-25T12:00:00+00:00",
                    None,
                    f"synthetic lesson {message_id}",
                    None,
                )

        return iterate()

    async def close(self) -> None:
        return None


def _scan_args(database, *, max_messages: int) -> list[str]:
    return [
        "scan",
        "--channel-id",
        str(CHAT),
        "--max-messages",
        str(max_messages),
        "--timeout-seconds",
        "30",
        "--database",
        str(database),
        "--incremental",
        "--reconcile-window",
        "2",
    ]


def _credentials() -> TelegramCredentials:
    return TelegramCredentials(7, "synthetic-hash")


def test_incremental_cli_reports_sync_and_rebuilds_catalog_after_complete(
    tmp_path, capsys, monkeypatch
) -> None:
    database = tmp_path / "incremental-cli.sqlite3"
    original_build = CatalogApplication.build
    build_statuses: list[str] = []

    async def record_build_status(self, channel_id: int):
        async with aiosqlite.connect(database) as db:
            row = await (await db.execute(
                "SELECT status FROM scan_runs WHERE channel_id=? ORDER BY started_at DESC LIMIT 1",
                (channel_id,),
            )).fetchone()
        build_statuses.append(row[0])
        return await original_build(self, channel_id)

    monkeypatch.setattr(CatalogApplication, "build", record_build_status)
    status = main(
        _scan_args(database, max_messages=10),
        scan_gateway_factory=lambda _credentials: FakeGateway((41,)),
        credentials_loader=_credentials,
    )

    output = " ".join(capsys.readouterr().out.split())
    assert status == 0
    assert "channel=" + str(CHAT) in output
    assert "max_messages=10" in output
    assert "reconcile_window=2" in output
    assert "mode=incremental" in output
    assert "status=COMPLETE" in output
    assert "new=1" in output
    assert "updated=0" in output
    assert "unchanged=0" in output
    assert "unverified=0" in output
    assert "checkpoint_confirmed=41" in output
    assert "catalog=COMPLETE parser=generic" in output
    assert build_statuses == ["COMPLETE"]

    second_status = main(
        _scan_args(database, max_messages=10),
        scan_gateway_factory=lambda _credentials: FakeGateway((41,)),
        credentials_loader=_credentials,
    )
    second_output = " ".join(capsys.readouterr().out.split())
    assert second_status == 0
    assert "status=COMPLETE" in second_output
    assert "new=0" in second_output
    assert "checkpoint_confirmed=41" in second_output
    assert "catalog=COMPLETE parser=generic" in second_output
    assert build_statuses == ["COMPLETE", "COMPLETE"]

    async def verify_catalog() -> None:
        async with aiosqlite.connect(database) as db:
            row = await (await db.execute(
                "SELECT status FROM catalog_runs WHERE channel_id=? ORDER BY started_at DESC LIMIT 1",
                (CHAT,),
            )).fetchone()
            assert row[0] == "COMPLETE"

    asyncio.run(verify_catalog())


def test_incremental_cli_rebuilds_rasmoo_catalog_idempotently_over_two_runs(
    tmp_path, capsys
) -> None:
    database = tmp_path / "rasmoo-incremental.sqlite3"
    fixture_root = Path(__file__).parents[1] / "fixtures" / "rasmoo" / "sp02"
    fixture_messages = (
        (1, "case01_index_fragment_a.txt", None),
        (2, "case01_index_fragment_b.txt", None),
        (3, "case02_video_post_from_index.txt", ("VIDEO", None)),
        (4, "case02_video_post_01.txt", ("VIDEO", None)),
        (5, "case02_video_post_02.txt", ("VIDEO", None)),
        (6, "case02_video_post_03.txt", ("VIDEO", None)),
        (7, "case02_documents_index.txt", None),
        (8, "case02_document_post.txt", ("ARCHIVE", "synthetic-document.rar")),
    )
    messages = tuple(
        GatewayMessage(
            CHAT,
            message_id,
            f"2026-01-{message_id:02d}T00:00:00+00:00",
            None,
            (fixture_root / filename).read_text(encoding="utf-8"),
            None,
            (
                (GatewayMedia(0, media[0], f"synthetic-{message_id}", media[1], "application/octet-stream", 16),)
                if media is not None and media[1] is not None
                else (
                    (GatewayMedia(0, media[0], f"synthetic-{message_id}", file_size_bytes=16),)
                    if media is not None else ()
                )
            ),
        )
        for message_id, filename, media in fixture_messages
    )

    class RasmooGateway:
        async def restore(self) -> AuthState:
            return AuthState.AUTHENTICATED

        def iter_channel_messages(
            self,
            channel_id: int,
            *,
            through_message_id: int | None,
            before_message_id: int | None,
            min_message_id: int | None,
            limit: int,
        ):
            assert channel_id == CHAT

            async def iterate():
                candidates = [
                    item for item in sorted(messages, key=lambda value: value.telegram_message_id, reverse=True)
                    if (through_message_id is None or item.telegram_message_id <= through_message_id)
                    and (before_message_id is None or item.telegram_message_id < before_message_id)
                    and (min_message_id is None or item.telegram_message_id >= min_message_id)
                ]
                for item in candidates[:limit]:
                    yield item

            return iterate()

        async def close(self) -> None:
            return None

    async def seed_parser() -> None:
        await SQLiteMessageRepository(database).migrate()
        async with aiosqlite.connect(database) as db:
            await db.execute(
                "INSERT INTO channels(telegram_chat_id,title,parser_key,created_at,updated_at) VALUES(?,?,?,?,?)",
                (CHAT, "Synthetic RASMOO", "rasmoo", "now", "now"),
            )
            await db.commit()

    asyncio.run(seed_parser())
    args = _scan_args(database, max_messages=20)
    first_status = main(
        args,
        scan_gateway_factory=lambda _credentials: RasmooGateway(),
        credentials_loader=_credentials,
    )
    first_output = " ".join(capsys.readouterr().out.split())
    assert first_status == 0
    assert "catalog=COMPLETE parser=rasmoo" in first_output
    assert "status=COMPLETE" in first_output

    async def first_catalog_snapshot():
        async with aiosqlite.connect(database) as db:
            nodes = await (await db.execute(
                "SELECT channel_id,parser_key,grammar_version,node_key,catalog_node_id "
                "FROM catalog_node_identity WHERE channel_id=? "
                "ORDER BY channel_id,parser_key,grammar_version,node_key", (CHAT,),
            )).fetchall()
            media = await (await db.execute(
                "SELECT telegram_message_id,media_ordinal,catalog_node_id FROM media_items "
                "WHERE channel_id=? ORDER BY telegram_message_id,media_ordinal", (CHAT,),
            )).fetchall()
        return [tuple(row) for row in nodes], [tuple(row) for row in media]

    first_nodes, first_media = asyncio.run(first_catalog_snapshot())
    second_status = main(
        args,
        scan_gateway_factory=lambda _credentials: RasmooGateway(),
        credentials_loader=_credentials,
    )
    second_output = " ".join(capsys.readouterr().out.split())
    assert second_status == 0
    assert "catalog=COMPLETE parser=rasmoo" in second_output
    assert "new=0" in second_output

    async def second_catalog_snapshot():
        async with aiosqlite.connect(database) as db:
            nodes = await (await db.execute(
                "SELECT channel_id,parser_key,grammar_version,node_key,catalog_node_id "
                "FROM catalog_node_identity WHERE channel_id=? "
                "ORDER BY channel_id,parser_key,grammar_version,node_key", (CHAT,),
            )).fetchall()
            media = await (await db.execute(
                "SELECT telegram_message_id,media_ordinal,catalog_node_id FROM media_items "
                "WHERE channel_id=? ORDER BY telegram_message_id,media_ordinal", (CHAT,),
            )).fetchall()
            count = await (await db.execute(
                "SELECT COUNT(*) FROM messages WHERE channel_id=?", (CHAT,),
            )).fetchone()
        return [tuple(row) for row in nodes], [tuple(row) for row in media], count[0]

    second_nodes, second_media, message_count = asyncio.run(second_catalog_snapshot())
    assert second_nodes == first_nodes
    assert second_media == first_media
    assert message_count == 8


def test_incremental_cli_does_not_rebuild_catalog_for_partial_run(
    tmp_path, capsys, monkeypatch
) -> None:
    database = tmp_path / "incremental-cli-partial.sqlite3"
    build_calls = 0

    async def record_build(self, channel_id: int):
        nonlocal build_calls
        build_calls += 1
        raise AssertionError("catalog must not rebuild before scan completion")

    monkeypatch.setattr(CatalogApplication, "build", record_build)
    status = main(
        _scan_args(database, max_messages=1),
        scan_gateway_factory=lambda _credentials: FakeGateway((52, 51)),
        credentials_loader=_credentials,
    )

    output = " ".join(capsys.readouterr().out.split())
    assert status == 4
    assert "status=PARTIAL" in output
    assert "catalog=NOT_REBUILT" in output
    assert build_calls == 0

    async def verify_no_catalog() -> None:
        async with aiosqlite.connect(database) as db:
            table = await (await db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='catalog_runs'"
            )).fetchone()
            if table is None:
                catalog_count = 0
            else:
                row = await (await db.execute(
                    "SELECT COUNT(channel_id) FROM catalog_runs WHERE channel_id=?", (CHAT,)
                )).fetchone()
                catalog_count = row[0]
            assert catalog_count == 0

    asyncio.run(verify_no_catalog())
