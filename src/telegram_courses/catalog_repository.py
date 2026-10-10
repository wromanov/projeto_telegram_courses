"""SQLite persistence and query boundary for catalog data."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

import aiosqlite

from telegram_courses.catalog import (
    CatalogError,
    CatalogPlan,
    SourceMedia,
    SourceMessage,
    source_fingerprint,
)
from telegram_courses.sqlite_repository import SQLiteMessageRepository


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class CatalogInput:
    channel_id: int
    channel_title: str | None
    configured_parser_key: str | None
    messages: tuple[SourceMessage, ...]

    @property
    def fingerprint(self) -> str:
        return source_fingerprint(self.messages)


@dataclass(frozen=True)
class CatalogBuildRecord:
    run_id: str
    channel_id: int
    parser_key: str
    grammar_version: str
    source_message_count: int
    catalog_node_count: int
    unresolved_count: int


@dataclass(frozen=True)
class CatalogChannelView:
    channel_id: int
    title: str | None
    parser_key: str | None
    catalog_status: str
    source_message_count: int
    active_node_count: int
    unclassified_count: int


@dataclass(frozen=True)
class CatalogNodeView:
    node_id: int
    parent_id: int | None
    kind: str
    code: str | None
    ordinal: int | None
    title: str | None
    source_message_id: int | None
    is_active: bool


@dataclass(frozen=True)
class CatalogMediaView:
    media_ordinal: int
    kind: str
    telegram_media_id: str | None
    original_filename: str | None
    mime_type: str | None
    file_size_bytes: int | None
    catalog_kind: str | None
    catalog_active: bool | None


@dataclass(frozen=True)
class CatalogItemView:
    telegram_message_id: int
    date_utc: str
    edit_date_utc: str | None
    text: str | None
    node_kinds: tuple[str, ...]
    unresolved_reason: str | None
    media: tuple[CatalogMediaView, ...]


class SQLiteCatalogRepository:
    """Owns all S3 SQL and preserves the S2 schema and source rows."""

    def __init__(self, database_path: str | Path, *, busy_timeout_ms: int = 5000) -> None:
        if type(busy_timeout_ms) is not int or busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be positive")
        self.database_path = Path(database_path)
        self.busy_timeout_ms = busy_timeout_ms

    async def _connect(self) -> aiosqlite.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(
            self.database_path, timeout=self.busy_timeout_ms / 1000
        )
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        await db.execute("PRAGMA journal_mode = WAL")
        return db

    async def migrate(self) -> None:
        await SQLiteMessageRepository(
            self.database_path, busy_timeout_ms=self.busy_timeout_ms
        ).migrate()
        db = await self._connect()
        try:
            await db.execute("BEGIN IMMEDIATE")
            for version, migration_name in (
                (2, "002_catalog.sql"),
                (3, "003_catalog_unresolved.sql"),
            ):
                applied = await (
                    await db.execute(
                        "SELECT 1 FROM schema_migrations WHERE version=?", (version,)
                    )
                ).fetchone()
                if applied is not None:
                    continue
                sql = (
                    files("telegram_courses")
                    .joinpath(f"migrations/{migration_name}")
                    .read_text(encoding="utf-8")
                )
                for statement in sql.split(";"):
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

    async def load_catalog_input(self, channel_id: int) -> CatalogInput:
        db = await self._connect()
        try:
            channel = await (
                await db.execute(
                    "SELECT telegram_chat_id, title, parser_key FROM channels "
                    "WHERE telegram_chat_id=?",
                    (channel_id,),
                )
            ).fetchone()
            if channel is None:
                raise CatalogError("CHANNEL_NOT_FOUND")
            messages, _ = await self._read_source_messages(db, channel_id)
            return CatalogInput(
                channel_id=channel_id,
                channel_title=channel["title"],
                configured_parser_key=channel["parser_key"],
                messages=messages,
            )
        finally:
            await db.close()

    async def _read_source_messages(
        self, db: aiosqlite.Connection, channel_id: int
    ) -> tuple[tuple[SourceMessage, ...], str | None]:
        message_rows = await (
            await db.execute(
                "SELECT telegram_message_id, message_date_utc, edit_date_utc, text, grouped_id "
                "FROM messages WHERE channel_id=? ORDER BY telegram_message_id",
                (channel_id,),
            )
        ).fetchall()
        media_rows = await (
            await db.execute(
                "SELECT telegram_message_id, media_ordinal, kind, telegram_media_id, "
                "original_filename, mime_type, file_size_bytes FROM media_items "
                "WHERE channel_id=? ORDER BY telegram_message_id, media_ordinal",
                (channel_id,),
            )
        ).fetchall()
        media_by_message: dict[int, list[SourceMedia]] = {}
        for row in media_rows:
            media_by_message.setdefault(row["telegram_message_id"], []).append(
                SourceMedia(
                    telegram_message_id=row["telegram_message_id"],
                    media_ordinal=row["media_ordinal"],
                    kind=row["kind"],
                    telegram_media_id=row["telegram_media_id"],
                    original_filename=row["original_filename"],
                    mime_type=row["mime_type"],
                    file_size_bytes=row["file_size_bytes"],
                )
            )
        messages = tuple(
            SourceMessage(
                channel_id=channel_id,
                telegram_message_id=row["telegram_message_id"],
                date_utc=row["message_date_utc"],
                edit_date_utc=row["edit_date_utc"],
                text=row["text"],
                grouped_id=row["grouped_id"],
                media=tuple(media_by_message.pop(row["telegram_message_id"], ())),
            )
            for row in message_rows
        )
        if media_by_message:
            raise CatalogError("INVALID_SOURCE")
        return messages, source_fingerprint(messages)

    async def save_catalog(
        self,
        plan: CatalogPlan,
        *,
        expected_source_fingerprint: str,
        expected_configured_parser_key: str | None,
        explicit_parser_key: str | None = None,
    ) -> CatalogBuildRecord:
        db = await self._connect()
        now = _now()
        run_id = str(uuid.uuid4())
        try:
            await db.execute("BEGIN IMMEDIATE")
            channel = await (
                await db.execute(
                    "SELECT parser_key FROM channels WHERE telegram_chat_id=?",
                    (plan.context.channel_id,),
                )
            ).fetchone()
            if channel is None:
                raise CatalogError("CHANNEL_NOT_FOUND")
            if channel["parser_key"] != expected_configured_parser_key:
                raise CatalogError("SOURCE_CHANGED")
            _, current_fingerprint = await self._read_source_messages(
                db, plan.context.channel_id
            )
            if current_fingerprint != expected_source_fingerprint:
                raise CatalogError("SOURCE_CHANGED")

            node_ids: dict[str, int] = {}
            if not plan.unresolved:
                node_keys = tuple(node.node_key for node in plan.nodes)
                node_exclusion = ""
                node_parameters: tuple[object, ...] = ()
                if node_keys:
                    placeholders = ",".join("?" for _ in node_keys)
                    node_exclusion = (
                        " AND NOT (parser_key=? AND grammar_version=? "
                        f"AND node_key IN ({placeholders}))"
                    )
                    node_parameters = (
                        plan.context.parser_key,
                        plan.context.grammar_version,
                        *node_keys,
                    )
                await db.execute(
                    "UPDATE catalog_nodes SET is_active=0 WHERE channel_id=? AND id IN "
                    "(SELECT catalog_node_id FROM catalog_node_identity WHERE channel_id=?"
                    + node_exclusion
                    + ")",
                    (
                        plan.context.channel_id,
                        plan.context.channel_id,
                        *node_parameters,
                    ),
                )
                desired_media = tuple(
                    (link.telegram_message_id, link.media_ordinal)
                    for link in plan.media_links
                )
                media_exclusion = ""
                media_parameters: tuple[object, ...] = ()
                if desired_media:
                    value_groups = ",".join("(?, ?)" for _ in desired_media)
                    media_exclusion = (
                        " AND (telegram_message_id, media_ordinal) NOT IN "
                        f"({value_groups})"
                    )
                    media_parameters = tuple(
                        value for media_key in desired_media for value in media_key
                    )
                await db.execute(
                    "UPDATE media_items SET catalog_node_id=NULL, updated_at=? "
                    "WHERE channel_id=? AND catalog_node_id IN "
                    "(SELECT catalog_node_id FROM catalog_node_identity WHERE channel_id=?)"
                    + media_exclusion,
                    (
                        now,
                        plan.context.channel_id,
                        plan.context.channel_id,
                        *media_parameters,
                    ),
                )
            rank = {
                "track": 0,
                "course": 1,
                "module": 2,
                "lesson": 3,
                "document": 4,
                "unclassified": 5,
            }
            ordered_nodes = sorted(
                plan.nodes, key=lambda node: (rank[node.kind], node.ordinal, node.node_key)
            )
            for node in ordered_nodes:
                parent_id = (
                    node_ids[node.parent_key]
                    if node.parent_key is not None
                    else None
                )
                identity = await (
                    await db.execute(
                        "SELECT catalog_node_id FROM catalog_node_identity WHERE "
                        "channel_id=? AND parser_key=? AND grammar_version=? AND node_key=?",
                        (
                            plan.context.channel_id,
                            plan.context.parser_key,
                            plan.context.grammar_version,
                            node.node_key,
                        ),
                    )
                ).fetchone()
                if identity is None:
                    cursor = await db.execute(
                        "INSERT INTO catalog_nodes(channel_id, parent_id, kind, code, ordinal, "
                        "title, source_message_id, created_at, updated_at, is_active) "
                        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                        (
                            plan.context.channel_id,
                            parent_id,
                            node.kind,
                            node.code,
                            node.ordinal,
                            node.title,
                            node.source_message_id,
                            now,
                            now,
                        ),
                    )
                    catalog_node_id = int(cursor.lastrowid)
                    await db.execute(
                        "INSERT INTO catalog_node_identity(channel_id, parser_key, grammar_version, "
                        "node_key, catalog_node_id) VALUES(?, ?, ?, ?, ?)",
                        (
                            plan.context.channel_id,
                            plan.context.parser_key,
                            plan.context.grammar_version,
                            node.node_key,
                            catalog_node_id,
                        ),
                    )
                else:
                    catalog_node_id = identity["catalog_node_id"]
                    previous = await (
                        await db.execute(
                            "SELECT channel_id, parent_id, kind, code, ordinal, title, "
                            "source_message_id, is_active FROM catalog_nodes WHERE id=?",
                            (catalog_node_id,),
                        )
                    ).fetchone()
                    desired = (
                        plan.context.channel_id,
                        parent_id,
                        node.kind,
                        node.code,
                        node.ordinal,
                        node.title,
                        node.source_message_id,
                        1,
                    )
                    if previous is None or previous["channel_id"] != plan.context.channel_id:
                        raise CatalogError("INVALID_CATALOG")
                    if tuple(previous) != desired:
                        await db.execute(
                            "UPDATE catalog_nodes SET parent_id=?, kind=?, code=?, ordinal=?, "
                            "title=?, source_message_id=?, updated_at=?, is_active=1 WHERE id=?",
                            (
                                parent_id,
                                node.kind,
                                node.code,
                                node.ordinal,
                                node.title,
                                node.source_message_id,
                                now,
                                catalog_node_id,
                            ),
                        )
                node_ids[node.node_key] = catalog_node_id
                if identity is None:
                    continue
                await db.execute(
                    "UPDATE catalog_nodes SET is_active=1 WHERE id=?",
                    (catalog_node_id,),
                )

            for link in plan.media_links:
                await db.execute(
                    "UPDATE media_items SET catalog_node_id=?, updated_at=? "
                    "WHERE channel_id=? AND telegram_message_id=? AND media_ordinal=? "
                    "AND catalog_node_id IS NOT ?",
                    (
                        node_ids[link.catalog_node_key],
                        now,
                        plan.context.channel_id,
                        link.telegram_message_id,
                        link.media_ordinal,
                        node_ids[link.catalog_node_key],
                    ),
                )

            if explicit_parser_key is not None and explicit_parser_key != channel["parser_key"]:
                await db.execute(
                    "UPDATE channels SET parser_key=?, updated_at=? WHERE telegram_chat_id=?",
                    (explicit_parser_key, now, plan.context.channel_id),
                )
            await db.execute(
                "INSERT INTO catalog_runs(id, channel_id, parser_key, grammar_version, status, "
                "started_at, finished_at, source_message_count, catalog_node_count, unresolved_count) "
                "VALUES(?, ?, ?, ?, 'COMPLETE', ?, ?, ?, ?, ?)",
                (
                    run_id,
                    plan.context.channel_id,
                    plan.context.parser_key,
                    plan.context.grammar_version,
                    now,
                    _now(),
                    plan.message_count,
                    len(plan.nodes),
                    len(plan.unresolved),
                ),
            )
            await db.executemany(
                "INSERT INTO catalog_unresolved_sources(run_id, channel_id, "
                "telegram_message_id, reason) VALUES(?, ?, ?, ?)",
                (
                    (
                        run_id,
                        plan.context.channel_id,
                        item.telegram_message_id,
                        item.reason,
                    )
                    for item in plan.unresolved
                ),
            )
            await db.commit()
            return CatalogBuildRecord(
                run_id=run_id,
                channel_id=plan.context.channel_id,
                parser_key=plan.context.parser_key,
                grammar_version=plan.context.grammar_version,
                source_message_count=plan.message_count,
                catalog_node_count=len(plan.nodes),
                unresolved_count=len(plan.unresolved),
            )
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def list_catalog_channels(self) -> tuple[CatalogChannelView, ...]:
        db = await self._connect()
        try:
            rows = await (
                await db.execute(
                    "SELECT c.telegram_chat_id, c.title, c.parser_key, "
                    "(SELECT r.status FROM catalog_runs r WHERE r.channel_id=c.telegram_chat_id "
                    "ORDER BY r.finished_at DESC LIMIT 1) AS catalog_status, "
                    "(SELECT r.source_message_count FROM catalog_runs r WHERE r.channel_id=c.telegram_chat_id "
                    "ORDER BY r.finished_at DESC LIMIT 1) AS source_message_count, "
                    "(SELECT COUNT(*) FROM catalog_nodes n WHERE n.channel_id=c.telegram_chat_id "
                    "AND n.is_active=1) AS active_node_count, "
                    "(SELECT COUNT(*) FROM catalog_nodes n WHERE n.channel_id=c.telegram_chat_id "
                    "AND n.is_active=1 AND n.kind='unclassified') AS unclassified_count "
                    "FROM channels c WHERE EXISTS(SELECT 1 FROM catalog_runs r "
                    "WHERE r.channel_id=c.telegram_chat_id) ORDER BY c.title COLLATE NOCASE, "
                    "c.telegram_chat_id"
                )
            ).fetchall()
            return tuple(
                CatalogChannelView(
                    channel_id=row["telegram_chat_id"],
                    title=row["title"],
                    parser_key=row["parser_key"],
                    catalog_status=row["catalog_status"],
                    source_message_count=row["source_message_count"],
                    active_node_count=row["active_node_count"],
                    unclassified_count=row["unclassified_count"],
                )
                for row in rows
            )
        finally:
            await db.close()

    async def get_catalog_nodes(
        self, channel_id: int, *, include_inactive: bool = True
    ) -> tuple[CatalogNodeView, ...]:
        db = await self._connect()
        try:
            active_filter = "" if include_inactive else " AND is_active=1"
            rows = await (
                await db.execute(
                    "SELECT id, parent_id, kind, code, ordinal, title, source_message_id, is_active "
                    f"FROM catalog_nodes WHERE channel_id=?{active_filter} "
                    "ORDER BY is_active DESC, COALESCE(ordinal, 0), kind, id",
                    (channel_id,),
                )
            ).fetchall()
            return tuple(
                CatalogNodeView(
                    node_id=row["id"],
                    parent_id=row["parent_id"],
                    kind=row["kind"],
                    code=row["code"],
                    ordinal=row["ordinal"],
                    title=row["title"],
                    source_message_id=row["source_message_id"],
                    is_active=bool(row["is_active"]),
                )
                for row in rows
            )
        finally:
            await db.close()

    async def get_catalog_items(self, channel_id: int) -> tuple[CatalogItemView, ...]:
        db = await self._connect()
        try:
            message_rows = await (
                await db.execute(
                    "SELECT telegram_message_id, message_date_utc, edit_date_utc, text "
                    "FROM messages WHERE channel_id=? ORDER BY telegram_message_id",
                    (channel_id,),
                )
            ).fetchall()
            node_rows = await (
                await db.execute(
                    "SELECT source_message_id, kind FROM catalog_nodes WHERE channel_id=? "
                    "AND is_active=1 AND source_message_id IS NOT NULL ORDER BY kind",
                    (channel_id,),
                )
            ).fetchall()
            kinds_by_message: dict[int, list[str]] = {}
            for row in node_rows:
                kinds_by_message.setdefault(row["source_message_id"], []).append(row["kind"])
            media_rows = await (
                await db.execute(
                    "SELECT m.telegram_message_id, m.media_ordinal, m.kind, m.telegram_media_id, "
                    "m.original_filename, m.mime_type, m.file_size_bytes, n.kind AS catalog_kind, "
                    "n.is_active AS catalog_active FROM media_items m LEFT JOIN catalog_nodes n "
                    "ON n.id=m.catalog_node_id AND n.channel_id=m.channel_id "
                    "WHERE m.channel_id=? ORDER BY m.telegram_message_id, m.media_ordinal",
                    (channel_id,),
                )
            ).fetchall()
            unresolved_rows = await (
                await db.execute(
                    "SELECT telegram_message_id, reason FROM catalog_unresolved_sources "
                    "WHERE run_id=(SELECT id FROM catalog_runs WHERE channel_id=? "
                    "ORDER BY finished_at DESC, rowid DESC LIMIT 1)",
                    (channel_id,),
                )
            ).fetchall()
            unresolved_by_message = {
                row["telegram_message_id"]: row["reason"] for row in unresolved_rows
            }
            media_by_message: dict[int, list[CatalogMediaView]] = {}
            for row in media_rows:
                media_by_message.setdefault(row["telegram_message_id"], []).append(
                    CatalogMediaView(
                        media_ordinal=row["media_ordinal"],
                        kind=row["kind"],
                        telegram_media_id=row["telegram_media_id"],
                        original_filename=row["original_filename"],
                        mime_type=row["mime_type"],
                        file_size_bytes=row["file_size_bytes"],
                        catalog_kind=row["catalog_kind"],
                        catalog_active=(
                            None
                            if row["catalog_active"] is None
                            else bool(row["catalog_active"])
                        ),
                    )
                )
            return tuple(
                CatalogItemView(
                    telegram_message_id=row["telegram_message_id"],
                    date_utc=row["message_date_utc"],
                    edit_date_utc=row["edit_date_utc"],
                    text=row["text"],
                    node_kinds=tuple(kinds_by_message.get(row["telegram_message_id"], ())),
                    unresolved_reason=unresolved_by_message.get(row["telegram_message_id"]),
                    media=tuple(media_by_message.get(row["telegram_message_id"], ())),
                )
                for row in message_rows
            )
        finally:
            await db.close()

    async def get_channel_parser_key(self, channel_id: int) -> str | None:
        db = await self._connect()
        try:
            row = await (
                await db.execute(
                    "SELECT parser_key FROM channels WHERE telegram_chat_id=?",
                    (channel_id,),
                )
            ).fetchone()
            if row is None:
                raise CatalogError("CHANNEL_NOT_FOUND")
            return row["parser_key"]
        finally:
            await db.close()
