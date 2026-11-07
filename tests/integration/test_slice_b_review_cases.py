from __future__ import annotations

import asyncio

import aiosqlite
from rich.console import Console
from tests.integration.test_interactive_catalog import _seed_interactive_database

from telegram_courses.cli import main


def test_missing_ordinal_is_flagged_in_course_review(tmp_path, capsys) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))

    async def remove_ordinal() -> None:
        async with aiosqlite.connect(path) as db:
            await db.execute("UPDATE catalog_nodes SET ordinal=NULL WHERE id=102")
            await db.commit()

    asyncio.run(remove_ordinal())
    answers = iter(("1", "1", "1", "Q", "Q", "Q", "Q"))
    assert main(["interactive", "--database", str(path)], selection_prompt=lambda _: next(answers)) == 0
    output = capsys.readouterr().out
    assert "Aviso: há ordinal ausente ou repetido" in output
    assert "Aula 1" in output


def test_unsupported_media_is_listed_as_exclusion_from_all_course_plan(
    tmp_path, capsys,
) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))

    async def add_unsupported_media() -> None:
        async with aiosqlite.connect(path) as db:
            await db.execute(
                "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) "
                "VALUES(-1001,40,'2026-01-01','now','now')"
            )
            await db.execute(
                "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,"
                "telegram_media_id,original_filename,file_size_bytes,remote_observation_state,created_at,updated_at) "
                "VALUES(-1001,40,0,103,'PHOTO','synthetic-photo','photo.bin',8,'OBSERVED','now','now')"
            )
            await db.commit()

    asyncio.run(add_unsupported_media())
    answers = iter(("1", "1", "1", "B", "n", "Q", "Q", "Q", "Q"))
    assert main(["interactive", "--database", str(path), "--max-media-items", "100", "--max-transfer-bytes", "10000000"], selection_prompt=lambda _: next(answers)) == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "EXCLUDED" in output
    assert "UNSUPPORTED_MEDIA" in output
    assert "id=-1001:40:0" in output
    assert "photo.bin" in output


def test_selection_can_be_removed_by_global_index_from_another_page(tmp_path, capsys) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))

    async def add_course_media() -> None:
        async with aiosqlite.connect(path) as db:
            for message_id in range(100, 120):
                await db.execute(
                    "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) "
                    "VALUES(-1001,?,'2026-01-01','now','now')",
                    (message_id,),
                )
                await db.execute(
                    "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,"
                    "telegram_media_id,original_filename,file_size_bytes,remote_observation_state,created_at,updated_at) "
                    "VALUES(-1001,?,0,103,'DOCUMENT',?,?,8,'OBSERVED','now','now')",
                    (message_id, f"synthetic-{message_id}", f"{message_id}.bin"),
                )
            await db.commit()

    asyncio.run(add_course_media())
    answers = iter(("1", "1", "1", "20", "N", "R", "20", "21", "P", "n", "Q", "Q", "Q", "Q"))
    assert main(["interactive", "--database", str(path), "--max-media-items", "100", "--max-transfer-bytes", "10000000"], selection_prompt=lambda _: next(answers)) == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "Selecionados/considerados: 1" in output
    assert "-1001:118:0" in output
    assert "-1001:117:0" not in output


def test_eof_and_keyboard_interrupt_cancel_interaction(tmp_path, capsys) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))

    interrupted = False

    def eof_prompt(prompt: str) -> str:
        nonlocal interrupted
        if prompt.startswith("Seleção:"):
            interrupted = True
            raise EOFError
        return "Q" if interrupted else "1"

    assert main(["interactive", "--database", str(path)], selection_prompt=eof_prompt) == 0

    interrupted = False

    def interrupt_prompt(prompt: str) -> str:
        nonlocal interrupted
        if prompt.startswith("Seleção:"):
            interrupted = True
            raise KeyboardInterrupt
        return "Q" if interrupted else "1"

    assert main(["interactive", "--database", str(path)], selection_prompt=interrupt_prompt) == 130
    assert "cancelada" not in capsys.readouterr().out.lower()


def test_untrusted_catalog_text_is_sanitized_and_rich_tags_are_literal(
    tmp_path, capsys, monkeypatch,
) -> None:
    import telegram_courses.interactive_catalog_cli as interactive

    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    monkeypatch.setattr(
        interactive, "Console", lambda **kwargs: Console(width=240, **kwargs),
    )

    async def inject_control_text() -> None:
        async with aiosqlite.connect(path) as db:
            await db.execute(
                "UPDATE channels SET title=? WHERE telegram_chat_id=-1001",
                ("[bold red]X[/bold red]",),
            )
            await db.execute(
                "UPDATE media_items SET original_filename=? WHERE telegram_message_id=10 AND media_ordinal=0",
                ("lesson\nFORGED\x1b[31m[bold red]Y[/bold red].bin",),
            )
            await db.commit()

    asyncio.run(inject_control_text())
    answers = iter(("1", "1", "1", "Q", "Q", "Q", "Q"))
    assert main(["interactive", "--database", str(path)], selection_prompt=lambda _: next(answers)) == 0
    output = capsys.readouterr().out
    assert "\x1b" not in output
    assert "\nFORGED" not in output
    assert "[bold red]X[/bold red]" in output
    assert "[bold red]Y[/bold red]" in output
