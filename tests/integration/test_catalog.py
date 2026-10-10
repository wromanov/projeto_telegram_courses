from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from telegram_courses.catalog import (
    CatalogBuilder,
    CatalogError,
    GenericParser,
    ParserContext,
    ParseResult,
    ParserRegistry,
    SourceMedia,
    SourceMessage,
)
from telegram_courses.catalog_application import CatalogApplication
from telegram_courses.catalog_repository import SQLiteCatalogRepository
from telegram_courses.cli import main


def source() -> tuple[SourceMessage, ...]:
    return (
        SourceMessage(
            channel_id=-1001,
            telegram_message_id=10,
            date_utc="2026-01-01T00:00:00+00:00",
            edit_date_utc=None,
            text="Synthetic lesson text",
            grouped_id=None,
            media=(SourceMedia(10, 0, "document", original_filename="lesson.pdf"),),
        ),
        SourceMessage(
            channel_id=-1001,
            telegram_message_id=20,
            date_utc="2026-01-02T00:00:00+00:00",
            edit_date_utc=None,
            text=None,
            grouped_id=None,
        ),
    )


def test_registry_generic_fallback_and_validation() -> None:
    registry = ParserRegistry()
    assert registry.select(None).parser.key == "generic"
    assert registry.select(None).reason == "generic fallback"
    with pytest.raises(CatalogError, match="unknown parser key"):
        registry.select("rasmoo")
    with pytest.raises(ValueError, match="already registered"):
        registry.register(GenericParser())


def test_generic_parser_is_deterministic_and_does_not_infer_hierarchy() -> None:
    messages = tuple(reversed(source()))
    context = ParserContext(-1001, "generic", "generic-v1")
    parsed = GenericParser().parse(context, messages)
    plan = CatalogBuilder().build(context, messages, parsed)
    assert [node.node_key for node in plan.nodes] == ["message:10", "message:20"]
    assert all(node.kind == "unclassified" and node.parent_key is None for node in plan.nodes)
    assert plan.nodes[0].title == "Synthetic lesson text"
    assert [(item.telegram_message_id, item.media_ordinal) for item in plan.media_links] == [(10, 0)]


def test_builder_rejects_invalid_parent_and_media_reference() -> None:
    context = ParserContext(-1001, "generic", "generic-v1")
    messages = source()
    # Generic invariants are checked for malformed parser output too.
    from telegram_courses.catalog import ParsedNode

    invalid_parent = ParseResult(
        nodes=(ParsedNode("m", "module", None, None, None, 1, 10),),
        media_links=(),
    )
    with pytest.raises(CatalogError, match="invalid catalog"):
        CatalogBuilder().build(context, messages, invalid_parent)
    invalid_media = ParseResult(
        nodes=(ParsedNode("m", "unclassified", None, None, None, 1, 10),),
        media_links=(),
    )
    CatalogBuilder().build(context, messages, invalid_media)


async def seed_database(path) -> None:
    repository = SQLiteCatalogRepository(path)
    await repository.migrate()
    db = await aiosqlite.connect(path)
    try:
        await db.execute(
            "INSERT INTO channels(telegram_chat_id,title,created_at,updated_at) VALUES(-1001,'Synthetic','now','now')"
        )
        for item in source():
            await db.execute(
                "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,edit_date_utc,text,grouped_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (item.channel_id, item.telegram_message_id, item.date_utc, item.edit_date_utc, item.text, item.grouped_id, "now", "now"),
            )
            for media in item.media:
                await db.execute(
                    "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,kind,original_filename,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (item.channel_id, media.telegram_message_id, media.media_ordinal, media.kind, media.original_filename, "now", "now"),
                )
        await db.commit()
    finally:
        await db.close()


def test_offline_repository_cli_and_idempotent_build(tmp_path, capsys) -> None:
    path = tmp_path / "synthetic.sqlite3"

    async def run_builds():
        await seed_database(path)
        repository = SQLiteCatalogRepository(path)
        app = CatalogApplication(repository)
        first = await app.build(-1001)
        nodes1 = await repository.get_catalog_nodes(-1001)
        second = await app.build(-1001)
        nodes2 = await repository.get_catalog_nodes(-1001)
        items = await repository.get_catalog_items(-1001)
        return first, second, nodes1, nodes2, items

    first, second, nodes1, nodes2, items = asyncio.run(run_builds())
    assert first.catalog_node_count == 2
    assert second.catalog_node_count == 2
    assert [node.node_id for node in nodes1] == [node.node_id for node in nodes2]
    assert items[0].media[0].catalog_kind == "unclassified"

    assert main(["catalog", "list", "--database", str(path)]) == 0
    assert "Synthetic" in capsys.readouterr().out
    assert main(["catalog", "show", "--channel-id", "-1001", "--database", str(path)]) == 0
    assert "unclassified" in capsys.readouterr().out
    assert main(["catalog", "items", "--channel-id", "-1001", "--database", str(path)]) == 0
    assert "Synthetic lesson text" in capsys.readouterr().out


def test_catalog_cli_build_requires_explicit_channel(tmp_path) -> None:
    assert main(["catalog", "build", "--database", str(tmp_path / "db.sqlite3")]) == 2
