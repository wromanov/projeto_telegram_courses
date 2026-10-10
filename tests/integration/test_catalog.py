from __future__ import annotations

import asyncio
import io
import sys

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


@pytest.mark.parametrize("encoding", ["utf-8", "cp1252", "cp850"])
def test_catalog_cli_writes_unicode_to_redirected_stream(tmp_path, monkeypatch, encoding) -> None:
    path = tmp_path / "unicode.sqlite3"
    asyncio.run(seed_database(path))

    async def update_synthetic_text() -> None:
        async with aiosqlite.connect(path) as db:
            await db.execute("UPDATE channels SET title = 'Ação 🚀' WHERE telegram_chat_id = -1001")
            await db.execute("UPDATE messages SET text = 'Lição 🚀' WHERE telegram_message_id = 10")
            await db.execute("UPDATE media_items SET original_filename = 'lição 🚀.pdf'")
            await db.commit()

    asyncio.run(update_synthetic_text())
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding=encoding, errors="strict")
    stderr = io.StringIO()
    assert not stream.isatty()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", stream)
        patch.setattr(sys, "stderr", stderr)
        for action in ("build", "list", "show", "items"):
            args = ["catalog", action, "--database", str(path)]
            if action != "list":
                args.extend(("--channel-id", "-1001"))
            assert main(args) == 0

    output = buffer.getvalue().decode(encoding)
    assert stderr.getvalue() == ""
    assert "internal error" not in output
    if encoding == "utf-8":
        assert "Ação 🚀" in output
        assert "Lição 🚀" in output
        assert "lição 🚀.pdf" in output
        assert "\\U0001f680" not in output
    else:
        assert "Ação \\U0001f680" in output
        assert "Lição \\U0001f680" in output
        assert "lição \\U0001f680.pdf" in output


def test_catalog_output_without_encoding_and_write_error() -> None:
    from telegram_courses.cli import _CatalogOutput

    class Stream:
        def __init__(self) -> None:
            self.written = ""
            self.flushed = False

        def write(self, value: str) -> int:
            self.written += value
            return len(value)

        def flush(self) -> None:
            self.flushed = True

        def isatty(self) -> bool:
            return False

    stream = Stream()
    output = _CatalogOutput(stream)
    assert output.encoding == "utf-8"
    assert output.isatty() is False
    assert output.write("Ação 🚀") == len("Ação 🚀")
    output.flush()
    assert stream.written == "Ação 🚀"
    assert stream.flushed

    def fail_write(_: str) -> int:
        raise OSError("write failed")

    stream.write = fail_write
    with pytest.raises(OSError, match="write failed"):
        output.write("Lição 🚀")
