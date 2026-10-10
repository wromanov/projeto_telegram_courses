"""SQLite migration and message scan persistence boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

import aiosqlite

from telegram_courses.message_scanner import GatewayMessage, ScanStatus


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteMessageRepository:
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
        db = await self._connect()
        try:
            sql = files("telegram_courses").joinpath("migrations/001_initial.sql").read_text()
            await db.execute("BEGIN IMMEDIATE")
            for statement in sql.split(";"):
                if statement.strip():
                    await db.execute(statement)
            await db.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(1, ?)",
                (_now(),),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def start_run(
        self, telegram_chat_id: int, watermark: int | None, run_id: str
    ) -> int | None:
        db = await self._connect()
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                "INSERT INTO channels(telegram_chat_id, created_at, updated_at) VALUES(?, ?, ?) "
                "ON CONFLICT(telegram_chat_id) DO UPDATE SET updated_at=excluded.updated_at",
                (telegram_chat_id, now, now),
            )
            await db.execute(
                "INSERT INTO scan_runs(id, channel_id, status, started_at, watermark_message_id) "
                "VALUES(?, ?, 'RUNNING', ?, ?)",
                (run_id, telegram_chat_id, now, watermark),
            )
            await db.execute(
                "INSERT INTO sync_checkpoints(scan_run_id, channel_id, watermark_message_id, status, updated_at) "
                "VALUES(?, ?, ?, 'RUNNING', ?)",
                (run_id, telegram_chat_id, watermark, now),
            )
            await db.commit()
            return None
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def set_watermark(self, run_id: str, watermark: int | None) -> None:
        db = await self._connect()
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                "UPDATE scan_runs SET watermark_message_id=? WHERE id=? AND status='RUNNING'",
                (watermark, run_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("scan run is not active")
            await db.execute(
                "UPDATE sync_checkpoints SET watermark_message_id=?, updated_at=? WHERE scan_run_id=?",
                (watermark, now, run_id),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def resume_run(self, run_id: str, telegram_chat_id: int) -> tuple[int | None, int | None]:
        db = await self._connect()
        try:
            await db.execute("BEGIN IMMEDIATE")
            row = await (await db.execute(
                "SELECT r.watermark_message_id, c.last_message_id, r.status, r.channel_id "
                "FROM scan_runs r JOIN sync_checkpoints c ON c.scan_run_id=r.id WHERE r.id=?",
                (run_id,),
            )).fetchone()
            if row is None or row["channel_id"] != telegram_chat_id or row["status"] not in {"PARTIAL", "INTERRUPTED"}:
                raise ValueError("run cannot be resumed")
            await db.execute(
                "UPDATE scan_runs SET status='RUNNING', finished_at=NULL, stop_reason=NULL WHERE id=?",
                (run_id,),
            )
            await db.execute(
                "UPDATE sync_checkpoints SET status='RUNNING', updated_at=? WHERE scan_run_id=?",
                (_now(), run_id),
            )
            await db.commit()
            return row["watermark_message_id"], row["last_message_id"]
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def persist_batch(
        self,
        run_id: str,
        messages: tuple[GatewayMessage, ...],
    ) -> tuple[int, int]:
        if not messages:
            return 0, 0
        db = await self._connect()
        inserted = updated = 0
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            run = await (await db.execute("SELECT channel_id FROM scan_runs WHERE id=? AND status='RUNNING'", (run_id,))).fetchone()
            if run is None:
                raise ValueError("scan run is not active")
            channel_id = run["channel_id"]
            for message in messages:
                if message.telegram_chat_id != channel_id:
                    raise ValueError("message channel does not match run")
                key = (channel_id, message.telegram_message_id)
                previous = await (await db.execute(
                    "SELECT message_date_utc, edit_date_utc, text, grouped_id FROM messages "
                    "WHERE channel_id=? AND telegram_message_id=?", key,
                )).fetchone()
                values = (message.date_utc, message.edit_date_utc, message.text, message.grouped_id)
                if previous is None:
                    inserted += 1
                    await db.execute(
                        "INSERT INTO messages(channel_id, telegram_message_id, message_date_utc, edit_date_utc, text, grouped_id, created_at, updated_at) "
                        "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                        (*key, *values, now, now),
                    )
                elif tuple(previous) != values:
                    updated += 1
                    await db.execute(
                        "UPDATE messages SET message_date_utc=?, edit_date_utc=?, text=?, grouped_id=?, updated_at=? "
                        "WHERE channel_id=? AND telegram_message_id=?",
                        (*values, now, *key),
                    )
                media_rows = await (await db.execute(
                    "SELECT media_ordinal, kind, telegram_media_id, original_filename, mime_type, file_size_bytes "
                    "FROM media_items WHERE channel_id=? AND telegram_message_id=? ORDER BY media_ordinal",
                    key,
                )).fetchall()
                existing_media = {item[0]: tuple(item) for item in media_rows}
                observed_ordinals: set[int] = set()
                for media in message.media:
                    observed_ordinals.add(media.media_ordinal)
                    metadata = (
                        media.media_ordinal, media.kind, media.telegram_media_id,
                        media.original_filename, media.mime_type, media.file_size_bytes,
                    )
                    previous_media = existing_media.get(media.media_ordinal)
                    if previous_media is None:
                        await db.execute(
                            "INSERT INTO media_items(channel_id, telegram_message_id, media_ordinal, kind, telegram_media_id, original_filename, mime_type, file_size_bytes, created_at, updated_at) "
                            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (*key, media.media_ordinal, media.kind, media.telegram_media_id,
                             media.original_filename, media.mime_type, media.file_size_bytes, now, now),
                        )
                    elif previous_media != metadata:
                        await db.execute(
                            "UPDATE media_items SET kind=?, telegram_media_id=?, original_filename=?, mime_type=?, file_size_bytes=?, updated_at=? "
                            "WHERE channel_id=? AND telegram_message_id=? AND media_ordinal=?",
                            (media.kind, media.telegram_media_id, media.original_filename,
                             media.mime_type, media.file_size_bytes, now, *key, media.media_ordinal),
                        )
                stale_ordinals = set(existing_media) - observed_ordinals
                for ordinal in stale_ordinals:
                    await db.execute(
                        "DELETE FROM media_items WHERE channel_id=? AND telegram_message_id=? AND media_ordinal=?",
                        (*key, ordinal),
                    )
            last_id = min(item.telegram_message_id for item in messages)
            last_date = next(item.date_utc for item in messages if item.telegram_message_id == last_id)
            await db.execute(
                "UPDATE scan_runs SET messages_seen=messages_seen+?, messages_new=messages_new+?, "
                "messages_updated=messages_updated+?, media_seen=media_seen+? WHERE id=?",
                (len(messages), inserted, updated, sum(len(item.media) for item in messages), run_id),
            )
            await db.execute(
                "UPDATE sync_checkpoints SET last_message_id=?, last_message_date_utc=?, updated_at=? WHERE scan_run_id=?",
                (last_id, last_date, now, run_id),
            )
            await db.commit()
            return inserted, updated
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def finish_run(self, run_id: str, status: ScanStatus, reason: str | None) -> None:
        db = await self._connect()
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                "UPDATE scan_runs SET status=?, finished_at=?, stop_reason=? WHERE id=?",
                (status.value, now, reason, run_id),
            )
            await db.execute(
                "UPDATE sync_checkpoints SET status=?, updated_at=? WHERE scan_run_id=?",
                (status.value, now, run_id),
            )
            if status is ScanStatus.COMPLETE:
                await db.execute(
                    "UPDATE channels SET last_scanned_at=?, updated_at=? WHERE telegram_chat_id="
                    "(SELECT channel_id FROM scan_runs WHERE id=?)",
                    (now, now, run_id),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def mark_abandoned_runs_interrupted(self) -> int:
        db = await self._connect()
        try:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                "UPDATE scan_runs SET status='INTERRUPTED', finished_at=?, stop_reason='PROCESS_RESTART' WHERE status='RUNNING'",
                (_now(),),
            )
            await db.execute(
                "UPDATE sync_checkpoints SET status='INTERRUPTED', updated_at=? WHERE status='RUNNING'",
                (_now(),),
            )
            await db.commit()
            return cursor.rowcount
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()
