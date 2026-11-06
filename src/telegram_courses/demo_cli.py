"""Persistent, explicitly marked synthetic demonstration of the interactive CLI."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Callable

import aiosqlite

from telegram_courses.catalog_repository import SQLiteCatalogRepository
from telegram_courses.course_offline_execution import OfflineCourseSandbox
from telegram_courses.download_repository import DownloadRepository
from telegram_courses.downloads import DownloadError, _reject_reparse_path
from telegram_courses.interactive_catalog_cli import run_interactive_catalog

MARKER = "telegram-courses-demo-v1\n"
PAYLOADS = {
    (-1001, 10, 0): ("synthetic-1", b"a" * (2 * 1024 * 1024)),
    (-1001, 20, 0): ("synthetic-2", b"b" * (2 * 1024 * 1024)),
    (-1001, 30, 0): ("synthetic-3", b"c" * 50),
}


async def _seed(database: Path) -> None:
    await SQLiteCatalogRepository(database).migrate()
    await DownloadRepository(database).migrate()
    async with aiosqlite.connect(database) as db:
        await db.execute(
            "INSERT INTO channels(telegram_chat_id,title,parser_key,created_at,updated_at) "
            "VALUES(-1001,'Canal de demonstração','generic','now','now')"
        )
        for message_id in (10, 20, 30):
            await db.execute(
                "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) "
                "VALUES(-1001,?,'2026-01-01T00:00:00+00:00','now','now')", (message_id,)
            )
        await db.execute(
            "INSERT INTO catalog_runs(id,channel_id,parser_key,grammar_version,status,started_at,finished_at,source_message_count,catalog_node_count,unresolved_count) "
            "VALUES('demo',-1001,'generic','generic-v1','COMPLETE','now','2026-01-01',3,7,0)"
        )
        nodes = (
            (101, None, "course", 1, "Curso demonstração"),
            (102, 101, "module", 1, "Módulo 1"),
            (103, 102, "lesson", 1, "Aula 1"),
            (104, 101, "module", 2, "Módulo 2"),
            (105, 104, "lesson", 1, "Aula 2"),
            (201, None, "course", 2, "Outro curso"),
            (202, 201, "lesson", 1, "Outra aula"),
        )
        for node_id, parent, kind, ordinal, title in nodes:
            await db.execute(
                "INSERT INTO catalog_nodes(id,channel_id,parent_id,kind,ordinal,title,is_active,created_at,updated_at) "
                "VALUES(?,-1001,?,?,?,?,1,'now','now')", (node_id, parent, kind, ordinal, title)
            )
        for message_id, node, name, size in (
            (10, 103, "intro.pdf", len(PAYLOADS[(-1001, 10, 0)][1])),
            (20, 105, "aula.mp4", len(PAYLOADS[(-1001, 20, 0)][1])),
            (30, 202, "outro.pdf", 50),
        ):
            await db.execute(
                "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,original_filename,file_size_bytes,created_at,updated_at) "
                "VALUES(-1001,?,0,?,'DOCUMENT',?,?,'now','now')", (message_id, node, name, size)
            )
        await db.execute(
            "UPDATE media_items SET telegram_media_id='synthetic-' || id, remote_observation_state='OBSERVED'"
        )
        await db.execute(
            "INSERT INTO scan_runs(id,channel_id,status,started_at,finished_at,stop_reason) "
            "VALUES('demo-scan',-1001,'PARTIAL','now','2026-01-02','MESSAGE_LIMIT')"
        )
        await db.commit()


def _open_workspace(value: str) -> OfflineCourseSandbox:
    supplied = Path(value).expanduser()
    if ".." in supplied.parts:
        raise DownloadError("OFFLINE_SANDBOX_INVALID")
    root = supplied.absolute()
    if root.drive.startswith("\\\\"):
        raise DownloadError("OFFLINE_SANDBOX_INVALID")
    if root == Path(root.anchor):
        raise DownloadError("OFFLINE_SANDBOX_INVALID")
    if any(part.casefold() in {".git", ".codex", ".ssh", "session", "sessions", "credentials", "downloads", "data", "db", "telegram_courses_product"} for part in root.parts):
        raise DownloadError("OFFLINE_SANDBOX_INVALID")
    # The nonexistent leaf lets the existing guard check every directory component.
    _reject_reparse_path(Path(root.anchor), root / ".demo-path-check")
    marker = root / ".telegram-courses-demo"
    database = root / "synthetic.sqlite3"
    if not root.exists():
        root.mkdir(parents=True, exist_ok=False)
        asyncio.run(_seed(database))
        with marker.open("x", encoding="utf-8") as output:
            output.write(MARKER)
    else:
        if not root.is_dir() or not marker.is_file() or not database.is_file():
            raise DownloadError("OFFLINE_SANDBOX_INVALID")
    for path in (marker, database, *(Path(str(database) + suffix) for suffix in ("-wal", "-shm", "-journal")), root / "downloads" / ".demo-path-check"):
        _reject_reparse_path(Path(root.anchor), path)
    if marker.stat().st_nlink != 1 or database.stat().st_nlink != 1:
        raise DownloadError("OFFLINE_SANDBOX_INVALID")
    if marker.read_text(encoding="utf-8") != MARKER:
        raise DownloadError("OFFLINE_SANDBOX_INVALID")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        media = db.execute(
            "SELECT channel_id,telegram_message_id,media_ordinal,telegram_media_id,file_size_bytes "
            "FROM media_items ORDER BY telegram_message_id"
        ).fetchall()
        channels = db.execute("SELECT telegram_chat_id FROM channels").fetchall()
    expected = [(*identity, media_id, len(data)) for identity, (media_id, data) in PAYLOADS.items()]
    if channels != [(-1001,)] or media != expected:
        raise DownloadError("OFFLINE_SANDBOX_INVALID")
    sandbox = OfflineCourseSandbox.persistent_demo(root, PAYLOADS)
    sandbox._gateway.delay_seconds = 0.15
    return sandbox


def run_demo(workspace: str, *, selection_prompt: Callable[[str], str] = input) -> int:
    try:
        sandbox = _open_workspace(workspace)
    except (OSError, sqlite3.Error, UnicodeError):
        raise DownloadError("OFFLINE_SANDBOX_INVALID") from None
    print("Demonstração offline: arquivos e canal são sintéticos.")
    return run_interactive_catalog(
        sandbox.database, download_root=sandbox.download_root,
        selection_prompt=selection_prompt, require_tty=False, offline_sandbox=sandbox,
    )
