"""SQLite boundary for eligible lesson media and download state."""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

import aiosqlite

from telegram_courses.catalog_repository import SQLiteCatalogRepository


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class DownloadCandidate:
    media_item_id: int
    channel_id: int
    telegram_message_id: int
    media_ordinal: int
    telegram_media_id: str
    expected_bytes: int
    original_filename: str | None
    lineage: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True)
class DownloadRecord:
    media_item_id: int
    state: str
    final_path: str | None
    partial_path: str | None
    expected_bytes: int
    downloaded_bytes: int
    sha256: str | None
    failure_category: str | None
    owner_pid: int | None


class DownloadInProgress(Exception):
    """A different process already owns this media transfer."""


def _process_is_alive(pid: int | None) -> bool:
    if type(pid) is not int or pid <= 0:
        return False
    if os.name == "nt":
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied means the process exists
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class DownloadRepository:
    """Owns download SQL; catalog SQL remains with its existing repository."""

    def __init__(self, database_path: str | Path, *, busy_timeout_ms: int = 5000) -> None:
        if type(busy_timeout_ms) is not int or busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be positive")
        self.database_path = Path(database_path)
        self.busy_timeout_ms = busy_timeout_ms

    async def _connect(self) -> aiosqlite.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(self.database_path, timeout=self.busy_timeout_ms / 1000)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        await db.execute("PRAGMA journal_mode = WAL")
        return db

    async def migrate(self) -> None:
        await SQLiteCatalogRepository(self.database_path, busy_timeout_ms=self.busy_timeout_ms).migrate()
        db = await self._connect()
        try:
            await db.execute("BEGIN IMMEDIATE")
            applied = await (await db.execute(
                "SELECT 1 FROM schema_migrations WHERE version=4"
            )).fetchone()
            if applied is None:
                sql = files("telegram_courses").joinpath("migrations/004_downloads.sql").read_text(encoding="utf-8")
                for statement in sql.split(";"):
                    if statement.strip():
                        await db.execute(statement)
                await db.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(4, ?)",
                    (_now(),),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def select_candidate(
        self, channel_id: int, message_id: int, media_ordinal: int
    ) -> DownloadCandidate | None:
        db = await self._connect()
        try:
            rows = await (await db.execute(
                "WITH RECURSIVE lineage(id, parent_id, kind, title, depth) AS ("
                " SELECT n.id, n.parent_id, n.kind, n.title, 0 FROM media_items m "
                " JOIN catalog_nodes n ON n.id=m.catalog_node_id AND n.channel_id=m.channel_id "
                " WHERE m.channel_id=? AND m.telegram_message_id=? AND m.media_ordinal=? "
                " AND n.kind='lesson' AND n.is_active=1 "
                " UNION ALL SELECT p.id, p.parent_id, p.kind, p.title, l.depth+1 "
                " FROM catalog_nodes p JOIN lineage l ON p.id=l.parent_id "
                " WHERE p.is_active=1 AND l.depth<4) "
                "SELECT m.id AS media_item_id, m.channel_id, m.telegram_message_id, "
                "m.media_ordinal, m.telegram_media_id, m.file_size_bytes, m.original_filename, "
                "l.kind, l.title, l.depth "
                "FROM media_items m JOIN messages msg ON msg.channel_id=m.channel_id "
                "AND msg.telegram_message_id=m.telegram_message_id "
                "JOIN channels c ON c.telegram_chat_id=m.channel_id "
                "JOIN lineage l ON l.id=m.catalog_node_id "
                "WHERE m.channel_id=? AND m.telegram_message_id=? AND m.media_ordinal=? "
                "AND m.kind='DOCUMENT' AND m.file_size_bytes IS NOT NULL "
                "AND m.file_size_bytes>=0 AND m.telegram_media_id IS NOT NULL "
                "ORDER BY l.depth DESC",
                (channel_id, message_id, media_ordinal, channel_id, message_id, media_ordinal),
            )).fetchall()
            if not rows:
                return None
            first = rows[0]
            lineage = tuple((row["kind"], row["title"]) for row in rows)
            if not any(kind == "lesson" for kind, _ in lineage):
                return None
            if any(kind not in {"lesson", "module", "course", "track"} for kind, _ in lineage):
                return None
            kinds = tuple(kind for kind, _ in lineage)
            if kinds not in {
                ("lesson",),
                ("course", "lesson"),
                ("module", "lesson"),
                ("course", "module", "lesson"),
                ("track", "course", "lesson"),
                ("track", "course", "module", "lesson"),
            }:
                return None
            return DownloadCandidate(
                media_item_id=first["media_item_id"], channel_id=first["channel_id"],
                telegram_message_id=first["telegram_message_id"], media_ordinal=first["media_ordinal"],
                telegram_media_id=first["telegram_media_id"], expected_bytes=first["file_size_bytes"],
                original_filename=first["original_filename"], lineage=lineage,
            )
        finally:
            await db.close()

    async def get_record(self, media_item_id: int) -> DownloadRecord | None:
        db = await self._connect()
        try:
            row = await (await db.execute(
                "SELECT media_item_id, state, final_path, partial_path, expected_bytes, "
                "downloaded_bytes, sha256, failure_category, owner_pid FROM downloads WHERE media_item_id=?",
                (media_item_id,),
            )).fetchone()
            return DownloadRecord(**dict(row)) if row else None
        finally:
            await db.close()

    async def start(self, candidate: DownloadCandidate, final_path: Path, partial_path: Path) -> None:
        db = await self._connect()
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            existing = await (await db.execute(
                "SELECT state, owner_pid FROM downloads WHERE media_item_id=?",
                (candidate.media_item_id,),
            )).fetchone()
            if existing is not None and existing["state"] in {
                "DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING"
            } and _process_is_alive(existing["owner_pid"]):
                raise DownloadInProgress
            await db.execute(
                "INSERT INTO downloads(media_item_id,state,final_path,partial_path,expected_bytes,downloaded_bytes,attempts,owner_pid,created_at,updated_at) "
                "VALUES(?, 'DOWNLOADING', ?, ?, ?, 0, 1, ?, ?, ?) "
                "ON CONFLICT(media_item_id) DO UPDATE SET state='DOWNLOADING', final_path=excluded.final_path, "
                "partial_path=excluded.partial_path, expected_bytes=excluded.expected_bytes, downloaded_bytes=0, "
                "sha256=NULL, validated_at=NULL, failure_category=NULL, owner_pid=excluded.owner_pid, "
                "attempts=downloads.attempts+1, updated_at=excluded.updated_at",
                (candidate.media_item_id, str(final_path), str(partial_path), candidate.expected_bytes, os.getpid(), now, now),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def transition(
        self, media_item_id: int, state: str, *, downloaded_bytes: int,
        sha256: str | None = None, failure_category: str | None = None,
    ) -> None:
        if state not in {"DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING", "DOWNLOADED", "FAILED_RETRYABLE", "FAILED"}:
            raise ValueError("invalid download state")
        predecessors = {
            "VALIDATED": ("DOWNLOADING",),
            "FINALIZATION_PENDING": ("VALIDATED",),
            "DOWNLOADED": ("VALIDATED", "FINALIZATION_PENDING"),
            "FAILED_RETRYABLE": ("DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING", "DOWNLOADED"),
            "FAILED": ("DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING"),
        }.get(state, ())
        if not predecessors:
            raise ValueError("invalid transition")
        db = await self._connect()
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            allowed = ",".join("?" for _ in predecessors)
            cursor = await db.execute(
                "UPDATE downloads SET state=?, downloaded_bytes=?, sha256=COALESCE(?,sha256), "
                "validated_at=CASE WHEN ?='VALIDATED' THEN ? ELSE validated_at END, "
                "failure_category=?, error_details=?, "
                "owner_pid=CASE WHEN ? IN ('DOWNLOADING','VALIDATED','FINALIZATION_PENDING') THEN owner_pid ELSE NULL END, "
                f"updated_at=? WHERE media_item_id=? AND state IN ({allowed})",
                (state, downloaded_bytes, sha256, state, now, failure_category,
                 failure_category, state, now, media_item_id, *predecessors),
            )
            if cursor.rowcount != 1:
                raise ValueError("download row missing")
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()
