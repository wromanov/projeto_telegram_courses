from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from telegram_courses.catalog import (
    CatalogBuilder,
    ParserContext,
    SourceMedia,
    SourceMessage,
)
from telegram_courses.catalog_application import CatalogApplication
from telegram_courses.catalog_repository import SQLiteCatalogRepository
from telegram_courses.rasmoo_parser import RasmooParser

FIXTURES = Path(__file__).parents[1] / "fixtures" / "rasmoo" / "sp02"
CHANNEL = -1007001


def _message(
    message_id: int,
    fixture: str,
    *,
    media_kind: str | None = None,
    filename: str | None = None,
) -> SourceMessage:
    media = (
        (SourceMedia(message_id, 0, media_kind, original_filename=filename),)
        if media_kind is not None
        else ()
    )
    return SourceMessage(
        CHANNEL,
        message_id,
        f"2026-01-{message_id:02d}T00:00:00+00:00",
        None,
        (FIXTURES / fixture).read_text(encoding="utf-8"),
        None,
        media,
    )


def _confirmed_fixture_messages() -> tuple[SourceMessage, ...]:
    return (
        _message(1, "case01_index_fragment_a.txt"),
        _message(2, "case01_index_fragment_b.txt"),
        _message(3, "case02_video_post_from_index.txt", media_kind="video"),
        _message(4, "case02_video_post_01.txt", media_kind="video"),
        _message(5, "case02_video_post_02.txt", media_kind="video"),
        _message(6, "case02_video_post_03.txt", media_kind="video"),
        _message(7, "case02_documents_index.txt"),
        _message(
            8,
            "case02_document_post.txt",
            media_kind="archive",
            filename="DOCUMENTO-901.rar",
        ),
    )


def _context(channel_id: int = CHANNEL) -> ParserContext:
    return ParserContext(channel_id, "rasmoo", "rasmoo-sp02-v1")


def test_parser_uses_confirmed_index_media_and_document_forms() -> None:
    messages = _confirmed_fixture_messages()
    parsed = RasmooParser().parse(_context(), messages)
    plan = CatalogBuilder().build(_context(), messages, parsed)

    assert any(node.kind == "track" and node.code == "04" for node in plan.nodes)
    assert any(node.kind == "course" and node.code == "01" for node in plan.nodes)
    assert any(node.kind == "module" and node.code == "01" for node in plan.nodes)
    lesson = next(node for node in plan.nodes if node.code == "#F501")
    assert lesson.kind == "lesson"
    assert lesson.source_message_id == 3
    assert [(link.telegram_message_id, link.media_ordinal, link.catalog_node_key) for link in plan.media_links] == [
        (3, 0, "lesson:#F501")
    ]
    document = next(node for node in plan.nodes if node.code == "#Doc901")
    assert document.kind == "document"
    assert document.source_message_id == 8
    assert all(link.telegram_message_id != 8 for link in plan.media_links)
    assert any(item.telegram_message_id == 2 for item in plan.unresolved)
    assert any(item.telegram_message_id == 4 for item in plan.unresolved)


def test_orphan_and_conflicting_references_remain_unlinked() -> None:
    orphan = SourceMessage(
        CHANNEL,
        20,
        "2026-01-20T00:00:00+00:00",
        None,
        "#F999 01 AULA\n01 TRILHA\n=01 CURSO\n==01 MODULO",
        None,
        (SourceMedia(20, 0, "video"),),
    )
    other_context = SourceMessage(
        CHANNEL,
        21,
        "2026-01-21T00:00:00+00:00",
        None,
        "#F501 01 AULA\n02 TRILHA\n=01 CURSO\n==01 MODULO",
        None,
        (SourceMedia(21, 0, "video"),),
    )
    index = _message(22, "case01_index_fragment_a.txt")
    parsed = RasmooParser().parse(_context(), (orphan, other_context, index))

    assert not parsed.media_links
    unresolved = {item.telegram_message_id: item.reason for item in parsed.unresolved}
    assert "orphan_media_reference" in unresolved[20]
    assert "conflicting_reference_post" in unresolved[21]
    assert "conflicting_reference_post" in unresolved[22]


def test_multiline_references_and_synthetic_hierarchy_transitions() -> None:
    transitions = _message(30, "case03_index_transitions_synthetic.txt")
    multiline = SourceMessage(
        CHANNEL,
        31,
        "2026-01-31T00:00:00+00:00",
        None,
        "= 03 TRACK-03\n== 01 COURSE-04\n=== 02 MODULE-05\n"
        "#F801\n#F802 #F803\n",
        None,
    )
    parsed = RasmooParser().parse(_context(), (multiline, transitions))
    plan = CatalogBuilder().build(_context(), (multiline, transitions), parsed)

    assert sum(node.kind == "track" for node in plan.nodes) == 3
    assert sum(node.kind == "course" for node in plan.nodes) == 4
    assert sum(node.kind == "module" for node in plan.nodes) == 5
    assert sum(node.kind == "lesson" for node in plan.nodes) == 8
    assert {node.code for node in plan.nodes if node.kind == "lesson"} >= {
        "#F701",
        "#F705",
        "#F801",
        "#F802",
        "#F803",
    }


async def _seed_catalog(
    path: Path, messages: tuple[SourceMessage, ...], channel_id: int = CHANNEL
) -> None:
    repository = SQLiteCatalogRepository(path)
    await repository.migrate()
    db = await aiosqlite.connect(path)
    try:
        await db.execute(
            "INSERT INTO channels(telegram_chat_id,title,created_at,updated_at) "
            "VALUES(?,?,?,?)",
            (channel_id, f"Synthetic RASMOO {channel_id}", "now", "now"),
        )
        for message in messages:
            await db.execute(
                "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,"
                "edit_date_utc,text,grouped_id,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    channel_id,
                    message.telegram_message_id,
                    message.date_utc,
                    message.edit_date_utc,
                    message.text,
                    message.grouped_id,
                    "now",
                    "now",
                ),
            )
            for media in message.media:
                await db.execute(
                    "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,"
                    "kind,original_filename,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        channel_id,
                        media.telegram_message_id,
                        media.media_ordinal,
                        media.kind,
                        media.original_filename,
                        "now",
                        "now",
                    ),
                )
        await db.commit()
    finally:
        await db.close()


def test_integrated_build_is_idempotent_and_rich_cli_navigates(tmp_path, capsys) -> None:
    path = tmp_path / "rasmoo.sqlite3"
    messages = _confirmed_fixture_messages()

    async def build_twice():
        await _seed_catalog(path, messages)
        repository = SQLiteCatalogRepository(path)
        application = CatalogApplication(repository)
        first = await application.build(CHANNEL, explicit_parser_key="rasmoo")
        nodes_first = await repository.get_catalog_nodes(CHANNEL)
        db = await aiosqlite.connect(path)
        try:
            first_node_updates = await (
                await db.execute(
                    "SELECT updated_at FROM catalog_nodes WHERE channel_id=? ORDER BY id",
                    (CHANNEL,),
                )
            ).fetchall()
            first_media_updates = await (
                await db.execute(
                    "SELECT telegram_message_id, media_ordinal, catalog_node_id, updated_at "
                    "FROM media_items WHERE channel_id=? ORDER BY telegram_message_id, media_ordinal",
                    (CHANNEL,),
                )
            ).fetchall()
        finally:
            await db.close()
        second = await application.build(CHANNEL, explicit_parser_key="rasmoo")
        nodes_second = await repository.get_catalog_nodes(CHANNEL)
        items = await repository.get_catalog_items(CHANNEL)
        db = await aiosqlite.connect(path)
        try:
            second_node_updates = await (
                await db.execute(
                    "SELECT updated_at FROM catalog_nodes WHERE channel_id=? ORDER BY id",
                    (CHANNEL,),
                )
            ).fetchall()
            second_media_updates = await (
                await db.execute(
                    "SELECT telegram_message_id, media_ordinal, catalog_node_id, updated_at "
                    "FROM media_items WHERE channel_id=? ORDER BY telegram_message_id, media_ordinal",
                    (CHANNEL,),
                )
            ).fetchall()
        finally:
            await db.close()
        return (
            first,
            second,
            nodes_first,
            nodes_second,
            items,
            first_node_updates,
            second_node_updates,
            first_media_updates,
            second_media_updates,
        )

    (
        first,
        second,
        nodes_first,
        nodes_second,
        items,
        first_node_updates,
        second_node_updates,
        first_media_updates,
        second_media_updates,
    ) = asyncio.run(build_twice())
    assert first.parser_key == second.parser_key == "rasmoo"
    assert first.catalog_node_count == second.catalog_node_count
    assert [(node.node_id, node.kind, node.code) for node in nodes_first] == [
        (node.node_id, node.kind, node.code) for node in nodes_second
    ]
    assert first_node_updates == second_node_updates
    assert first_media_updates == second_media_updates
    assert any(node.kind == "document" and node.code == "#Doc901" for node in nodes_second)
    assert next(item for item in items if item.telegram_message_id == 3).media[0].catalog_kind == "lesson"
    assert next(item for item in items if item.telegram_message_id == 8).media[0].catalog_kind is None
    assert next(item for item in items if item.telegram_message_id == 2).unresolved_reason

    from telegram_courses.cli import main

    assert main(["catalog", "show", "--channel-id", str(CHANNEL), "--database", str(path)]) == 0
    output = capsys.readouterr().out
    assert "track" in output and "lesson" in output and "document" in output
    assert main(["catalog", "items", "--channel-id", str(CHANNEL), "--database", str(path)]) == 0
    assert "não resolvido" in capsys.readouterr().out


def test_unresolved_rebuild_does_not_inactivate_prior_catalog(tmp_path) -> None:
    path = tmp_path / "rasmoo-partial.sqlite3"
    messages = _confirmed_fixture_messages()
    partial = SourceMessage(
        CHANNEL,
        9,
        "2026-01-09T00:00:00+00:00",
        None,
        "#F501 without a supported hierarchy",
        None,
        (),
    )

    async def run():
        await _seed_catalog(path, messages + (partial,))
        repository = SQLiteCatalogRepository(path)
        application = CatalogApplication(repository)
        await application.build(CHANNEL, explicit_parser_key="rasmoo")
        before = await repository.get_catalog_nodes(CHANNEL)
        await application.build(CHANNEL, explicit_parser_key="rasmoo")
        after = await repository.get_catalog_nodes(CHANNEL)
        return before, after

    before, after = asyncio.run(run())
    active_before = {node.node_id for node in before if node.is_active}
    active_after = {node.node_id for node in after if node.is_active}
    assert active_before <= active_after


def test_identity_and_media_association_are_scoped_to_channel(tmp_path) -> None:
    path = tmp_path / "rasmoo-multichannel.sqlite3"
    messages = _confirmed_fixture_messages()
    second_channel = -1007002

    async def run():
        await _seed_catalog(path, messages)
        await _seed_catalog(path, messages, second_channel)
        repository = SQLiteCatalogRepository(path)
        application = CatalogApplication(repository)
        await application.build(CHANNEL, explicit_parser_key="rasmoo")
        await application.build(second_channel, explicit_parser_key="rasmoo")
        db = await aiosqlite.connect(path)
        try:
            rows = await (
                await db.execute(
                    "SELECT channel_id, catalog_node_id FROM catalog_node_identity "
                    "WHERE parser_key='rasmoo' AND node_key='lesson:#F501' ORDER BY channel_id"
                )
            ).fetchall()
            media_rows = await (
                await db.execute(
                    "SELECT channel_id, catalog_node_id FROM media_items "
                    "WHERE telegram_message_id=3 ORDER BY channel_id"
                )
            ).fetchall()
            return rows, media_rows
        finally:
            await db.close()

    rows, media_rows = asyncio.run(run())
    identity_by_channel = {row[0]: row[1] for row in rows}
    assert set(identity_by_channel) == {CHANNEL, second_channel}
    assert len(set(identity_by_channel.values())) == 2
    assert {row[0]: row[1] for row in media_rows} == {
        CHANNEL: identity_by_channel[CHANNEL],
        second_channel: identity_by_channel[second_channel],
    }
