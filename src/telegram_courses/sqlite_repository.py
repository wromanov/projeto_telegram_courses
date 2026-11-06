"""SQLite migration and message scan persistence boundary."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

import aiosqlite

from telegram_courses.message_scanner import GatewayMessage, ScanStatus


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _confirmed_baseline(db, telegram_chat_id: int) -> tuple[bool, int | None]:
    row = await (await db.execute(
        "SELECT COUNT(*) AS completed_count, MAX(watermark_message_id) AS high_water "
        "FROM scan_runs WHERE channel_id=? AND status='COMPLETE'",
        (telegram_chat_id,),
    )).fetchone()
    return int(row["completed_count"]) > 0, row["high_water"]


def _process_is_alive(pid: int) -> bool | None:
    """Return false only when the OS positively reports that a PID is absent."""
    if os.name == "nt":
        return _windows_process_is_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _windows_process_is_alive(pid: int) -> bool | None:
    """Query Windows process state without treating API errors as process death."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    get_exit_code = kernel32.GetExitCodeProcess
    close_handle = kernel32.CloseHandle
    try:
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit_code.restype = wintypes.BOOL
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
    except AttributeError:
        # Lightweight API doubles used by offline tests need not expose ctypes
        # function metadata; real WinDLL functions accept these assignments.
        pass

    handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: no process exists for this PID
            return False
        if error == 5:  # ERROR_ACCESS_DENIED: fail closed as possibly active
            return True
        return None

    try:
        exit_code = wintypes.DWORD()
        if not get_exit_code(handle, ctypes.byref(exit_code)):
            error = ctypes.get_last_error()
            return True if error == 5 else None
        return exit_code.value == 259  # STILL_ACTIVE
    finally:
        close_handle(handle)


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
            for version, migration_name in (
                (6, "006_s7_incremental_sync.sql"),
                (7, "007_s7_corrective_identity_observation.sql"),
            ):
                applied = await (await db.execute(
                    "SELECT 1 FROM schema_migrations WHERE version=?", (version,)
                )).fetchone()
                if applied is not None:
                    continue
                migration_sql = files("telegram_courses").joinpath(
                    f"migrations/{migration_name}"
                ).read_text(encoding="utf-8")
                for statement in migration_sql.split(";"):
                    if statement.strip():
                        await db.execute(statement)
                await db.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)",
                    (version, _now()),
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

    async def update_channel_metadata(
        self, telegram_chat_id: int, *, title: str, username: str | None,
    ) -> None:
        """Persist only the metadata of the channel selected from a fresh snapshot."""
        if (
            type(telegram_chat_id) is not int
            or telegram_chat_id > -1_000_000_000_000
            or not isinstance(title, str)
            or len(title) > 1024
            or username is not None and (not isinstance(username, str) or len(username) > 128)
        ):
            raise ValueError("invalid selected channel metadata")
        db = await self._connect()
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                "INSERT INTO channels(telegram_chat_id, title, username, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?) "
                "ON CONFLICT(telegram_chat_id) DO UPDATE SET "
                "title=excluded.title, username=excluded.username, updated_at=excluded.updated_at",
                (telegram_chat_id, title, username, now, now),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def get_confirmed_high_water(
        self, telegram_chat_id: int
    ) -> tuple[bool, int | None]:
        """Return (has_completed_baseline, high_water) for one channel.

        A null watermark is meaningful when a completed scan observed an empty
        channel, so the presence bit must not be inferred from the ID value.
        """
        db = await self._connect()
        try:
            return await _confirmed_baseline(db, telegram_chat_id)
        finally:
            await db.close()

    async def find_resumable_sync_run(self, telegram_chat_id: int) -> str | None:
        db = await self._connect()
        try:
            row = await (await db.execute(
                "SELECT id FROM scan_runs WHERE channel_id=? AND sync_mode='INCREMENTAL' "
                "AND status IN ('PARTIAL','INTERRUPTED','FAILED') "
                "AND NOT EXISTS (SELECT 1 FROM scan_runs c WHERE c.channel_id=scan_runs.channel_id "
                "AND c.status='COMPLETE' AND c.finished_at>scan_runs.started_at) "
                "ORDER BY started_at DESC LIMIT 1",
                (telegram_chat_id,),
            )).fetchone()
            return None if row is None else str(row["id"])
        finally:
            await db.close()

    async def mark_abandoned_sync_runs_interrupted(self) -> int:
        """Recover only incremental runs whose recorded owner is proven dead."""
        db = await self._connect()
        interrupted = 0
        try:
            await db.execute("BEGIN IMMEDIATE")
            rows = await (await db.execute(
                "SELECT id, owner_pid FROM scan_runs "
                "WHERE sync_mode='INCREMENTAL' AND status='RUNNING'"
            )).fetchall()
            for row in rows:
                owner_pid = row["owner_pid"]
                if type(owner_pid) is not int or _process_is_alive(owner_pid) is not False:
                    continue
                now = _now()
                result = await db.execute(
                    "UPDATE scan_runs SET status='INTERRUPTED', finished_at=?, "
                    "stop_reason='PROCESS_RESTART' WHERE id=? AND status='RUNNING'",
                    (now, row["id"]),
                )
                if result.rowcount == 1:
                    interrupted += 1
                    await db.execute(
                        "UPDATE sync_checkpoints SET status='INTERRUPTED', updated_at=? "
                        "WHERE scan_run_id=? AND status='RUNNING'",
                        (now, row["id"]),
                    )
            await db.commit()
            return interrupted
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def start_sync_run(
        self,
        telegram_chat_id: int,
        run_id: str,
        *,
        max_messages: int,
        reconcile_window: int,
    ) -> dict[str, int | str | None | bool]:
        """Create a sync run with its confirmed baseline and bounded scope."""
        db = await self._connect()
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            running = await (await db.execute(
                "SELECT id FROM scan_runs WHERE channel_id=? AND sync_mode='INCREMENTAL' "
                "AND status='RUNNING' LIMIT 1",
                (telegram_chat_id,),
            )).fetchone()
            if running is not None:
                raise ValueError("an incremental sync run is already active")
            await db.execute(
                "INSERT INTO channels(telegram_chat_id, created_at, updated_at) VALUES(?, ?, ?) "
                "ON CONFLICT(telegram_chat_id) DO UPDATE SET updated_at=excluded.updated_at",
                (telegram_chat_id, now, now),
            )
            baseline_confirmed, high_water = await _confirmed_baseline(db, telegram_chat_id)
            floor = (
                max(1, int(high_water) - reconcile_window + 1)
                if baseline_confirmed and high_water is not None
                else (1 if not baseline_confirmed else None)
            )
            await db.execute(
                "INSERT INTO scan_runs(id, channel_id, status, started_at, watermark_message_id, "
                "sync_mode, sync_baseline_confirmed, sync_high_water_before, "
                "sync_reconcile_floor_message_id, sync_reconcile_window, sync_max_messages, owner_pid) "
                "VALUES(?, ?, 'RUNNING', ?, NULL, 'INCREMENTAL', ?, ?, ?, ?, ?, ?)",
                (run_id, telegram_chat_id, now, int(baseline_confirmed), high_water,
                 floor, reconcile_window, max_messages, os.getpid()),
            )
            await db.execute(
                "INSERT INTO sync_checkpoints(scan_run_id, channel_id, watermark_message_id, status, updated_at) "
                "VALUES(?, ?, NULL, 'RUNNING', ?)",
                (run_id, telegram_chat_id, now),
            )
            await db.commit()
            return {
                "run_id": run_id,
                "snapshot_head": None,
                "cursor": None,
                "baseline_confirmed": baseline_confirmed,
                "high_water_before": high_water,
                "reconcile_floor": floor,
                "reconcile_window": reconcile_window,
                "max_messages": max_messages,
            }
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def resume_sync_run(
        self, run_id: str, telegram_chat_id: int
    ) -> dict[str, int | str | None | bool]:
        db = await self._connect()
        try:
            await db.execute("BEGIN IMMEDIATE")
            row = await (await db.execute(
                "SELECT r.sync_snapshot_head_message_id, c.last_message_id, r.status, r.channel_id, "
                "r.sync_baseline_confirmed, r.sync_high_water_before, "
                "r.sync_reconcile_floor_message_id, r.sync_reconcile_window, r.sync_max_messages "
                "FROM scan_runs r JOIN sync_checkpoints c ON c.scan_run_id=r.id WHERE r.id=? "
                "AND r.sync_mode='INCREMENTAL'",
                (run_id,),
            )).fetchone()
            if (
                row is None or row["channel_id"] != telegram_chat_id
                or row["status"] not in {"PARTIAL", "INTERRUPTED", "FAILED"}
            ):
                raise ValueError("sync run cannot be resumed")
            await db.execute(
                "UPDATE scan_runs SET status='RUNNING', finished_at=NULL, stop_reason=NULL, owner_pid=? WHERE id=?",
                (os.getpid(), run_id),
            )
            await db.execute(
                "UPDATE sync_checkpoints SET status='RUNNING', updated_at=? WHERE scan_run_id=?",
                (_now(), run_id),
            )
            await db.commit()
            return {
                "run_id": run_id,
                "snapshot_head": row["sync_snapshot_head_message_id"],
                "cursor": row["last_message_id"],
                "baseline_confirmed": bool(row["sync_baseline_confirmed"]),
                "high_water_before": row["sync_high_water_before"],
                "reconcile_floor": row["sync_reconcile_floor_message_id"],
                "reconcile_window": int(row["sync_reconcile_window"]),
                "max_messages": int(row["sync_max_messages"]),
            }
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def get_sync_run_summary(self, run_id: str) -> dict[str, int | str | None | bool]:
        db = await self._connect()
        try:
            row = await (await db.execute(
                "SELECT r.channel_id, r.status, r.stop_reason, r.messages_seen, r.messages_new, "
                "r.messages_updated, r.media_seen, r.messages_unverified, r.media_unverified, r.watermark_message_id, "
                "r.sync_baseline_confirmed, r.sync_high_water_before, r.sync_reconcile_window, "
                "r.sync_max_messages FROM scan_runs r WHERE r.id=?",
                (run_id,),
            )).fetchone()
            if row is None:
                raise ValueError("sync run does not exist")
            has_baseline, high_water = await _confirmed_baseline(db, row["channel_id"])
            return {
                "channel_id": int(row["channel_id"]),
                "status": str(row["status"]),
                "stop_reason": row["stop_reason"],
                "messages_seen": int(row["messages_seen"]),
                "messages_new": int(row["messages_new"]),
                "messages_updated": int(row["messages_updated"]),
                "messages_unchanged": max(0, int(row["messages_seen"]) - int(row["messages_new"]) - int(row["messages_updated"])),
                "media_seen": int(row["media_seen"]),
                "messages_unverified": None if row["messages_unverified"] is None else int(row["messages_unverified"]),
                "media_unverified": int(row["media_unverified"]),
                "watermark": row["watermark_message_id"],
                "baseline_confirmed": bool(row["sync_baseline_confirmed"]),
                "high_water_before": row["sync_high_water_before"],
                "has_confirmed_high_water": has_baseline,
                "high_water_confirmed": high_water,
                "reconcile_window": int(row["sync_reconcile_window"]),
                "max_messages": row["sync_max_messages"],
            }
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

    async def set_sync_snapshot_head(self, run_id: str, head_message_id: int) -> None:
        db = await self._connect()
        try:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                "UPDATE scan_runs SET sync_snapshot_head_message_id=? "
                "WHERE id=? AND status='RUNNING' AND sync_mode='INCREMENTAL' "
                "AND sync_snapshot_head_message_id IS NULL",
                (head_message_id, run_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("incremental run head is already captured or inactive")
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
                message_changed = False
                if previous is None:
                    inserted += 1
                    await db.execute(
                        "INSERT INTO messages(channel_id, telegram_message_id, message_date_utc, edit_date_utc, text, grouped_id, created_at, updated_at) "
                        "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                        (*key, *values, now, now),
                    )
                elif tuple(previous) != values:
                    message_changed = True
                    await db.execute(
                        "UPDATE messages SET message_date_utc=?, edit_date_utc=?, text=?, grouped_id=?, updated_at=? "
                        "WHERE channel_id=? AND telegram_message_id=?",
                        (*values, now, *key),
                    )
                media_rows = await (await db.execute(
                    "SELECT media_ordinal, kind, telegram_media_id, original_filename, mime_type, "
                    "file_size_bytes, remote_observation_state "
                    "FROM media_items WHERE channel_id=? AND telegram_message_id=? ORDER BY media_ordinal",
                    key,
                )).fetchall()
                existing_media = {item[0]: tuple(item) for item in media_rows}
                for media in message.media:
                    metadata = (
                        media.media_ordinal, media.kind, media.telegram_media_id,
                        media.original_filename, media.mime_type, media.file_size_bytes,
                    )
                    previous_media = existing_media.get(media.media_ordinal)
                    if previous_media is None:
                        if previous is not None:
                            message_changed = True
                        await db.execute(
                            "INSERT INTO media_items(channel_id, telegram_message_id, media_ordinal, kind, telegram_media_id, original_filename, mime_type, file_size_bytes, created_at, updated_at, remote_observation_state) "
                            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OBSERVED')",
                            (*key, media.media_ordinal, media.kind, media.telegram_media_id,
                             media.original_filename, media.mime_type, media.file_size_bytes, now, now),
                        )
                    elif previous_media[:6] != metadata or previous_media[6] != "OBSERVED":
                        message_changed = True
                        await db.execute(
                            "UPDATE media_items SET kind=?, telegram_media_id=?, original_filename=?, mime_type=?, file_size_bytes=?, remote_observation_state='OBSERVED', updated_at=? "
                            "WHERE channel_id=? AND telegram_message_id=? AND media_ordinal=?",
                            (media.kind, media.telegram_media_id, media.original_filename,
                             media.mime_type, media.file_size_bytes, now, *key, media.media_ordinal),
                        )
                # Missing ordinals record only non-observation. Preserve their
                # historical identity and every download artifact.
                observed_ordinals = {media.media_ordinal for media in message.media}
                for ordinal, prior in existing_media.items():
                    if ordinal not in observed_ordinals and prior[6] != "NOT_OBSERVED":
                        await db.execute(
                            "UPDATE media_items SET remote_observation_state='NOT_OBSERVED', updated_at=? "
                            "WHERE channel_id=? AND telegram_message_id=? AND media_ordinal=?",
                            (now, *key, ordinal),
                        )
                        message_changed = True
                if previous is not None and message_changed:
                    updated += 1
                await db.execute(
                    "UPDATE messages SET last_seen_run_id=? WHERE channel_id=? AND telegram_message_id=?",
                    (run_id, *key),
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
            run = await (await db.execute(
                "SELECT sync_mode, sync_high_water_before, sync_snapshot_head_message_id "
                "FROM scan_runs WHERE id=?",
                (run_id,),
            )).fetchone()
            media_unverified = await (await db.execute(
                "SELECT COUNT(*) FROM media_items m JOIN messages msg "
                "ON msg.channel_id=m.channel_id AND msg.telegram_message_id=m.telegram_message_id "
                "WHERE msg.last_seen_run_id=? AND m.remote_observation_state='NOT_OBSERVED'",
                (run_id,),
            )).fetchone()
            await db.execute(
                "UPDATE scan_runs SET media_unverified=? WHERE id=?",
                (int(media_unverified[0]), run_id),
            )
            if status is ScanStatus.COMPLETE and run is not None and run["sync_mode"] == "INCREMENTAL":
                observed_values = [
                    value for value in (
                        run["sync_high_water_before"],
                        run["sync_snapshot_head_message_id"],
                    ) if value is not None
                ]
                confirmed_watermark = max(observed_values) if observed_values else None
                await db.execute(
                    "UPDATE scan_runs SET watermark_message_id=? WHERE id=?",
                    (confirmed_watermark, run_id),
                )
                await db.execute(
                    "UPDATE sync_checkpoints SET watermark_message_id=?, updated_at=? "
                    "WHERE scan_run_id=?",
                    (confirmed_watermark, now, run_id),
                )
            await db.execute(
                "UPDATE scan_runs SET status=?, finished_at=?, stop_reason=?, owner_pid=NULL WHERE id=?",
                (status.value, now, reason, run_id),
            )
            await db.execute(
                "UPDATE sync_checkpoints SET status=?, updated_at=? WHERE scan_run_id=?",
                (status.value, now, run_id),
            )
            if status is ScanStatus.COMPLETE:
                run = await (await db.execute(
                    "SELECT channel_id, sync_mode, sync_baseline_confirmed, "
                    "sync_high_water_before, sync_reconcile_floor_message_id, watermark_message_id "
                    "FROM scan_runs WHERE id=?",
                    (run_id,),
                )).fetchone()
                if run is not None and run["sync_mode"] == "INCREMENTAL":
                    lower = run["sync_reconcile_floor_message_id"]
                    if lower is None:
                        lower = 1
                    upper = run["watermark_message_id"]
                    if upper is None and run["sync_baseline_confirmed"]:
                        upper = run["sync_high_water_before"]
                    query = (
                        "SELECT COUNT(*) FROM messages WHERE channel_id=? "
                        "AND telegram_message_id>=? AND last_seen_run_id IS NOT ?"
                    )
                    params: tuple[object, ...] = (run["channel_id"], lower, run_id)
                    if run["sync_baseline_confirmed"] and upper is not None:
                        query += " AND telegram_message_id<=?"
                        params += (upper,)
                    unverified = await (await db.execute(query, params)).fetchone()
                    await db.execute(
                        "UPDATE scan_runs SET messages_unverified=? WHERE id=?",
                        (int(unverified[0]), run_id),
                    )
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
