from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from dataclasses import replace
from types import SimpleNamespace

import aiosqlite
import pytest

from telegram_courses.catalog import CatalogError
from telegram_courses.catalog_repository import SQLiteCatalogRepository
from telegram_courses.catalog_selection import (
    course_media_options,
    make_course_selection,
    selectable_courses,
)
from telegram_courses.cli import main
from telegram_courses.download_repository import DownloadRepository
from telegram_courses.s5_downloads import DownloadPlanner


async def _seed_interactive_database(path) -> None:
    repository = SQLiteCatalogRepository(path)
    await repository.migrate()
    await DownloadRepository(path).migrate()
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT INTO channels(telegram_chat_id,title,parser_key,created_at,updated_at) "
            "VALUES(-1001,'Canal sintético','generic','now','now')"
        )
        for message_id in (10, 20, 30):
            await db.execute(
                "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) "
                "VALUES(-1001,?,?,?,?)",
                (message_id, "2026-01-01T00:00:00+00:00", "now", "now"),
            )
        await db.execute(
            "INSERT INTO catalog_runs(id,channel_id,parser_key,grammar_version,status,started_at,finished_at,source_message_count,catalog_node_count,unresolved_count) "
            "VALUES('run-1',-1001,'generic','generic-v1','COMPLETE','now','2026-01-01',3,7,1)"
        )
        node_rows = (
            (101, None, "course", 1, "Curso A", 1),
            (102, 101, "module", 1, "Módulo 1", 1),
            (103, 102, "lesson", 1, "Aula 1", 1),
            (104, 101, "module", 1, "Módulo 2", 1),
            (105, 104, "lesson", 1, "Aula 2", 1),
            (201, None, "course", 1, "Curso B", 1),
            (202, 201, "lesson", 1, "Aula B", 1),
            (203, None, "unclassified", 3, "Sem associação", 1),
        )
        for node_id, parent_id, kind, ordinal, title, active in node_rows:
            await db.execute(
                "INSERT INTO catalog_nodes(id,channel_id,parent_id,kind,ordinal,title,is_active,created_at,updated_at) "
                "VALUES( ?,-1001,?,?,?,?,?,'now','now')",
                (node_id, parent_id, kind, ordinal, title, active),
            )
        media_rows = (
            (10, 0, 103, "DOCUMENT", "intro.pdf", 120),
            (20, 0, 105, "DOCUMENT", "lesson.mp4", None),
            (30, 0, 202, "DOCUMENT", "other.pdf", 50),
            (10, 1, 203, "DOCUMENT", "unresolved.pdf", None),
        )
        for message_id, ordinal, node_id, kind, filename, size in media_rows:
            await db.execute(
                "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,original_filename,file_size_bytes,created_at,updated_at) "
                "VALUES(-1001,?,?,?,?,?,?,?,?)",
                (message_id, ordinal, node_id, kind, filename, size, "now", "now"),
            )
        await db.execute(
            "UPDATE media_items SET telegram_media_id='synthetic-' || id, "
            "remote_observation_state='OBSERVED'"
        )
        await db.execute(
            "INSERT INTO scan_runs(id,channel_id,status,started_at,finished_at,stop_reason) "
            "VALUES('scan-1',-1001,'PARTIAL','now','2026-01-02','MESSAGE_LIMIT')"
        )
        await db.commit()


def _database_digest(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_interactive_snapshot_is_read_only_and_course_scoped(tmp_path) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    before = _database_digest(path)
    repository = SQLiteCatalogRepository(path)
    channels = asyncio.run(repository.list_interactive_channels())
    snapshot = asyncio.run(repository.load_interactive_snapshot(-1001))
    after = _database_digest(path)

    assert [item.channel_id for item in channels] == [-1001]
    assert snapshot.catalog_complete is False
    assert snapshot.scan_stop_reason == "MESSAGE_LIMIT"
    courses = selectable_courses(snapshot)
    assert [item.node_id for item in courses] == [101, 201]
    options = course_media_options(snapshot, 101)
    assert [item.original_filename for item in options] == ["intro.pdf", "lesson.mp4"]
    assert all(item.selectable for item in options)
    assert options[1].file_size_bytes is None
    selection = make_course_selection(
        options, frozenset({options[0].identity, options[1].identity}),
        channel_id=-1001, course_id=101,
    )
    assert selection.identities == tuple(item.identity for item in options)
    assert before == after


def test_interactive_snapshot_rejects_unsupported_schema_without_writing(tmp_path) -> None:
    path = tmp_path / "unsupported.sqlite3"
    with sqlite3.connect(path):
        pass
    before = _database_digest(path)
    repository = SQLiteCatalogRepository(path)
    with pytest.raises(CatalogError) as error:
        asyncio.run(repository.list_interactive_channels())
    assert error.value.category == "CATALOG_SCHEMA_UNSUPPORTED"
    assert _database_digest(path) == before


def test_interactive_catalog_missing_database_does_not_create_it(tmp_path) -> None:
    path = tmp_path / "missing" / "catalog.sqlite3"
    repository = SQLiteCatalogRepository(path)
    with pytest.raises(CatalogError, match="catalog not found"):
        asyncio.run(repository.list_interactive_channels())
    assert not path.parent.exists()


def test_interactive_cli_selects_and_reviews_without_download(tmp_path, capsys) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    answers = iter(("1", "1", "1", "1,2", "V", "R", "1", "V", "Q", "Q", "Q", "Q"))
    result = main(
        ["interactive", "--database", str(path)],
        selection_prompt=lambda _: next(answers),
    )
    output = capsys.readouterr().out
    assert result == 0
    assert "catálogo parcial" in output
    assert "P prepara os marcados" in output
    assert "Tamanho desconhecido não remove o item da seleção." in output
    assert "Tamanho desconhecido; itens permanecem visíveis" in output
    assert "Mídias observadas sem associação" in output
    assert "unresolved.pdf" in output
    assert "Aviso: ordinais ausentes ou repetidos" in output
    assert "Identidade local" in output
    assert "-1001:20:0" in output
    assert "Marcados: 2" in output
    assert "Marcados: 1" in output
    assert "Esta revisão não inicia downloads." in output


def test_interactive_empty_manual_selection_is_not_reported_as_success(tmp_path, capsys) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    answers = iter(("1", "1", "1", "P", "Q", "Q", "Q", "Q"))
    result = main(
        ["interactive", "--database", str(path)],
        selection_prompt=lambda _: next(answers),
    )
    output = capsys.readouterr().out
    assert result == 0
    assert "SEM_SELECAO" in output
    assert "Plano validado" not in output
    assert "Download iniciado" not in output


def test_interactive_all_course_plan_blocks_when_selected_catalog_has_unknown_size(tmp_path, capsys) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    answers = iter(("1", "1", "1", "B", "10", "1000", "s", "Q", "Q", "Q", "Q", "Q"))
    result = main(
        ["interactive", "--database", str(path), "--download-dir", str(tmp_path / "downloads")],
        selection_prompt=lambda _: next(answers),
    )
    output = capsys.readouterr().out
    assert result == 0
    assert "todos os arquivos observados com associação válida a aula neste curso" in output
    assert "Selecionados/considerados: 2" in output
    assert "EXCLUDED / UNKNOWN_SIZE" in output
    assert "-1001:10:0" in output and "-1001:20:0" in output
    assert "Estado da prévia: BLOQUEADO" in output
    assert "UNKNOWN_SIZE" in output
    assert "Download iniciado" not in output
    assert not (tmp_path / "downloads").exists()


def test_interactive_manual_plan_contains_only_exact_selected_identity(tmp_path, capsys) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    answers = iter(("1", "1", "1", "1", "P", "n", "Q", "Q", "Q", "Q"))
    result = main(
        ["interactive", "--database", str(path), "--max-media-items", "1", "--max-transfer-bytes", "1000"],
        selection_prompt=lambda _: next(answers),
    )
    output = capsys.readouterr().out
    assert result == 0
    assert "Modo: arquivos selecionados" in output
    assert "Selecionados/considerados: 1" in output
    assert "-1001:10:0" in output
    assert "-1001:20:0" not in output
    assert "resultado=PASS" in output
    assert "Plano não confirmado" in output
    assert "Download iniciado" not in output


def test_interactive_pagination_keeps_global_indices_and_selection(tmp_path, capsys) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))

    async def add_media():
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
                    "VALUES(-1001,?,0,103,'DOCUMENT',?, ?,1,'OBSERVED','now','now')",
                    (message_id, f"synthetic-{message_id}", f"{message_id}.bin"),
                )
            await db.commit()

    asyncio.run(add_media())
    answers = iter(("1", "1", "1", "N", "21", "P", "1", "1000", "n", "Q", "Q", "Q", "Q"))
    result = main(
        ["interactive", "--database", str(path)],
        selection_prompt=lambda _: next(answers),
    )
    output = capsys.readouterr().out
    assert result == 0
    assert "Página 2 de 2" in output
    assert "opções numeradas globalmente: 1–22" in output
    assert "Selecionados/considerados: 1" in output
    assert "-1001:118:0" in output


def test_interactive_all_course_reports_invalid_associations_outside_plan(tmp_path, capsys) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))

    async def deactivate_lesson():
        async with aiosqlite.connect(path) as db:
            await db.execute("UPDATE catalog_nodes SET is_active=0 WHERE id=105")
            await db.commit()

    asyncio.run(deactivate_lesson())
    answers = iter(("1", "1", "1", "B", "s", "Q", "Q", "Q", "Q", "Q"))
    result = main(
        [
            "interactive", "--database", str(path),
            "--max-media-items", "1", "--max-transfer-bytes", "1000",
        ],
        selection_prompt=lambda _: next(answers),
    )
    normalized_output = " ".join(capsys.readouterr().out.split())

    assert result == 0
    assert "Selecionados/considerados: 1" in normalized_output
    assert "fora do plano por associação: 1" in normalized_output
    assert "id=-1001:20:0" in normalized_output
    assert "associação inativa" in normalized_output
    assert "resultado=PASS" in normalized_output
    assert "Plano validado" in normalized_output


def test_interactive_all_course_rebuilds_exact_catalog_set_after_confirmation(
    tmp_path, capsys,
) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    async def set_course_file_size():
        async with aiosqlite.connect(path) as db:
            await db.execute(
                "UPDATE media_items SET file_size_bytes=240 "
                "WHERE channel_id=-1001 AND telegram_message_id=20 AND media_ordinal=0"
            )
            await db.commit()

    asyncio.run(set_course_file_size())
    prompt_answers = iter(("1", "1", "1", "B", "10", "1000", "s", "n", "Q", "Q", "Q", "Q"))
    confirmation_count = 0

    async def add_new_course_media():
        async with aiosqlite.connect(path) as db:
            await db.execute(
                "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) "
                "VALUES(-1001,40,'2026-01-01','now','now')"
            )
            await db.execute(
                "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,"
                "telegram_media_id,original_filename,file_size_bytes,remote_observation_state,created_at,updated_at) "
                "VALUES(-1001,40,0,103,'DOCUMENT','synthetic-40','40.bin',8,'OBSERVED','now','now')"
            )
            await db.commit()

    def selection_prompt(_prompt):
        nonlocal confirmation_count
        answer = next(prompt_answers)
        if _prompt.startswith("Confirmar"):
            confirmation_count += 1
            if confirmation_count == 1:
                asyncio.run(add_new_course_media())
        return answer

    result = main(
        ["interactive", "--database", str(path)],
        selection_prompt=selection_prompt,
    )
    normalized_output = " ".join(capsys.readouterr().out.split())

    assert result == 0
    assert confirmation_count == 2
    assert "A confirmação anterior foi descartada" in normalized_output
    assert "Selecionados/considerados: 3" in normalized_output
    assert "-1001:40:0" in normalized_output
    assert "Plano validado" not in normalized_output


def test_interactive_all_course_without_eligible_media_reports_empty_plan(tmp_path, capsys) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))

    async def deactivate_course_lessons():
        async with aiosqlite.connect(path) as db:
            await db.execute(
                "UPDATE catalog_nodes SET is_active=0 WHERE title IN ('Aula 1','Aula 2')"
            )
            await db.commit()

    asyncio.run(deactivate_course_lessons())
    answers = iter(("1", "1", "1", "B", "Q", "Q", "Q", "Q"))
    result = main(
        ["interactive", "--database", str(path)],
        selection_prompt=lambda _: next(answers),
    )
    normalized_output = " ".join(capsys.readouterr().out.split())

    assert result == 0
    assert "SEM_ELEGIVEIS" in normalized_output
    assert "Plano validado" not in normalized_output
    assert "Download iniciado" not in normalized_output


def test_interactive_discards_confirmation_when_fresh_item_status_changes(
    tmp_path, capsys, monkeypatch,
) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    original_build = DownloadPlanner.build
    calls = 0

    async def build_with_status_drift(self, selection):
        nonlocal calls
        plan = await original_build(self, selection)
        calls += 1
        if calls >= 2:
            changed_item = replace(
                plan.items[0], status="BLOCKED", reason="MEDIA_NOT_OBSERVED",
            )
            return replace(plan, items=(changed_item, *plan.items[1:]))
        return plan

    monkeypatch.setattr(DownloadPlanner, "build", build_with_status_drift)
    answers = iter(("1", "1", "1", "1", "P", "1", "1000", "s", "Q", "Q", "Q", "Q"))
    result = main(
        ["interactive", "--database", str(path)],
        selection_prompt=lambda _: next(answers),
    )
    output = capsys.readouterr().out
    normalized_output = " ".join(output.split())

    assert result == 0
    assert calls == 3
    assert "A confirmação anterior foi descartada" in normalized_output
    assert "Estado da prévia: BLOQUEADO" in normalized_output
    assert "Plano validado" not in normalized_output
    assert "Download iniciado" not in normalized_output


@pytest.mark.parametrize("delta,expected_confirmations", [
    (1024**3 - 1, 1), (1024**3, 2), (1024**3 + 1, 2),
])
def test_interactive_reconfirms_at_gib_boundary(
    tmp_path, capsys, monkeypatch, delta, expected_confirmations,
) -> None:
    import telegram_courses.interactive_catalog_cli as interactive

    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    original_review = interactive.create_course_plan_review
    calls = 0

    def review_with_disk_change(*args, **kwargs):
        nonlocal calls
        calls += 1
        free = 10**12 if calls == 1 else 10**12 - delta
        return original_review(*args, **kwargs, disk_usage=lambda _: SimpleNamespace(free=free))

    monkeypatch.setattr(interactive, "create_course_plan_review", review_with_disk_change)
    answers = iter(("1", "1", "1", "1", "P", "10", "1000", *(["s"] * expected_confirmations), "Q", "Q", "Q", "Q", "Q"))
    confirmations = []

    def prompt(message):
        if message.startswith("Confirmar"):
            confirmations.append(message)
        return next(answers)

    assert main(["interactive", "--database", str(path)], selection_prompt=prompt) == 0
    output = " ".join(capsys.readouterr().out.split())
    assert len(confirmations) == expected_confirmations
    assert ("A confirmação anterior foi descartada" in output) is (expected_confirmations == 2)
    assert "Plano validado" in output


@pytest.mark.parametrize("fresh_free", [0, None])
def test_interactive_discards_confirmation_when_fresh_disk_is_unusable(
    tmp_path, capsys, monkeypatch, fresh_free,
) -> None:
    import telegram_courses.interactive_catalog_cli as interactive

    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    original_review = interactive.create_course_plan_review
    calls = 0

    def review_with_disk_change(*args, **kwargs):
        nonlocal calls
        calls += 1
        free = 10**12 if calls == 1 else fresh_free
        return original_review(*args, **kwargs, disk_usage=lambda _: SimpleNamespace(free=free))

    monkeypatch.setattr(interactive, "create_course_plan_review", review_with_disk_change)
    answers = iter(("1", "1", "1", "1", "P", "10", "1000", "s", "Q", "Q", "Q", "Q"))
    assert main(["interactive", "--database", str(path)], selection_prompt=lambda _: next(answers)) == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "A confirmação anterior foi descartada" in output
    assert "Estado da prévia: BLOQUEADO" in output
    assert "Plano validado" not in output


def test_interactive_blocks_confirmation_when_disk_probe_fails(tmp_path, capsys, monkeypatch) -> None:
    import telegram_courses.interactive_catalog_cli as interactive

    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    original_review = interactive.create_course_plan_review

    def unavailable(_path):
        raise OSError("synthetic disk failure")

    def review_without_disk(*args, **kwargs):
        return original_review(*args, **kwargs, disk_usage=unavailable)

    monkeypatch.setattr(interactive, "create_course_plan_review", review_without_disk)
    answers = iter(("1", "1", "1", "1", "P", "10", "1000", "Q", "Q", "Q", "Q"))

    def prompt(message):
        assert not message.startswith("Confirmar")
        return next(answers)

    assert main(["interactive", "--database", str(path)], selection_prompt=prompt) == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "DISK_SPACE_UNVERIFIED" in output
    assert "Plano validado" not in output


def test_interactive_cli_requires_tty_without_prompt_injection(tmp_path, monkeypatch, capsys) -> None:
    path = tmp_path / "catalog.sqlite3"
    asyncio.run(_seed_interactive_database(path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    result = main(["interactive", "--database", str(path)])
    assert result == 2
    assert "requer um terminal" in capsys.readouterr().err
