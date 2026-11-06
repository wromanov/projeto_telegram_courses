"""Fail-closed preparation for existing Telegram Courses SQLite databases.

The inspection path is read-only. Existing databases are migrated only after
the caller receives an explicit confirmation and a verified SQLite backup has
been created in a private, no-reparse directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from telegram_courses.download_repository import DownloadRepository

_KNOWN_MIGRATION_STATES = {
    (1,),
    (1, 2, 3),
    (1, 2, 3, 4, 5),
    (1, 2, 3, 4, 5, 6, 7),
    (1, 6, 7),
    (1, 2, 3, 6, 7),
}
_BASE_TABLES = frozenset(
    {"schema_migrations", "channels", "messages", "media_items", "scan_runs", "sync_checkpoints"}
)
_CATALOG_TABLES = frozenset(
    {"catalog_nodes", "catalog_node_identity", "catalog_runs"}
)
_DATA_TABLES = ("channels", "messages", "media_items", "downloads")
_DATA_COLUMNS = {
    "channels": (
        "telegram_chat_id", "title", "username", "parser_key", "created_at",
        "updated_at", "last_scanned_at",
    ),
    "messages": (
        "channel_id", "telegram_message_id", "message_date_utc", "edit_date_utc",
        "text", "grouped_id", "created_at", "updated_at",
    ),
    "media_items": (
        "id", "channel_id", "telegram_message_id", "media_ordinal", "catalog_node_id",
        "kind", "telegram_media_id", "original_filename", "mime_type",
        "file_size_bytes", "created_at", "updated_at",
    ),
    "downloads": (
        "id", "media_item_id", "state", "final_path", "partial_path", "expected_bytes",
        "downloaded_bytes", "attempts", "error_details", "created_at", "updated_at",
    ),
}
_REQUIRED_COLUMNS = {
    "channels": frozenset(_DATA_COLUMNS["channels"]),
    "messages": frozenset(_DATA_COLUMNS["messages"]),
    "media_items": frozenset(_DATA_COLUMNS["media_items"]),
    "scan_runs": frozenset({
        "id", "channel_id", "status", "started_at", "finished_at",
        "watermark_message_id", "messages_seen", "messages_new",
        "messages_updated", "media_seen", "errors", "stop_reason",
        "error_category",
    }),
    "sync_checkpoints": frozenset({
        "scan_run_id", "channel_id", "watermark_message_id", "last_message_id",
        "last_message_date_utc", "status", "updated_at",
    }),
    "catalog_nodes": frozenset({
        "id", "channel_id", "parent_id", "kind", "code", "ordinal", "title",
        "source_message_id", "created_at", "updated_at",
    }),
    "downloads": frozenset(_DATA_COLUMNS["downloads"]),
}
_CATALOG_COLUMNS = {
    "catalog_node_identity": frozenset({
        "channel_id", "parser_key", "grammar_version", "node_key", "catalog_node_id",
    }),
    "catalog_runs": frozenset({
        "id", "channel_id", "parser_key", "grammar_version", "status",
        "started_at", "finished_at", "source_message_count", "catalog_node_count",
        "unresolved_count",
    }),
}
_S6_COLUMNS = {
    "s6_v2_attempts": frozenset({
        "id", "media_item_id", "channel_id", "telegram_message_id",
        "media_ordinal", "telegram_media_id", "expected_bytes", "selected_mode",
        "schema_version", "contract_version", "evidence_version", "plan_id",
        "invocation_id", "reference_manifest_path", "status", "remote_hash_class",
        "evidence_class", "details_json", "requests", "bytes_reserved",
        "bytes_received", "created_at", "updated_at",
    }),
    "s6_v2_evidence": frozenset({
        "media_item_id", "attempt_id", "channel_id", "telegram_message_id",
        "media_ordinal", "telegram_media_id", "expected_bytes", "final_path",
        "final_sha256", "selected_mode", "schema_version", "evidence_class",
        "remote_hash_class", "contract_version", "evidence_version", "plan_id",
        "invocation_id", "details_json", "created_at",
    }),
}
_S7_V6_COLUMNS = {
    "scan_runs": frozenset({
        "sync_mode", "sync_baseline_confirmed", "sync_high_water_before",
        "sync_reconcile_floor_message_id", "sync_reconcile_window",
        "sync_max_messages", "messages_unverified", "owner_pid",
        "sync_snapshot_head_message_id",
    }),
    "messages": frozenset({"last_seen_run_id"}),
    "downloads": frozenset({
        "remote_identity_media_id", "remote_identity_kind", "remote_identity_size",
    }),
}
_S7_V7_COLUMNS = {
    "scan_runs": frozenset({"media_unverified"}),
    "media_items": frozenset({"remote_observation_state"}),
    "downloads": frozenset({"remote_identity_provenance"}),
}

DatabaseKind = Literal["NEW", "EMPTY", "LEGACY", "CURRENT", "UNKNOWN", "CORRUPT"]


class DatabasePreparationError(Exception):
    """Sanitized, stable error for database preparation failures."""

    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


@dataclass(frozen=True)
class DatabaseInspection:
    path: Path
    kind: DatabaseKind
    exists: bool
    migration_versions: tuple[int, ...]
    tables: tuple[str, ...]
    row_counts: tuple[tuple[str, int], ...]
    integrity: str
    foreign_key_violations: int
    file_identity: tuple[int, int, int, int] | None
    _data_fingerprints: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class VerifiedDatabaseBackup:
    path: Path
    source_path: Path
    source_file_identity: tuple[int, int, int, int]
    source_kind: DatabaseKind
    sha256: str
    integrity: str
    foreign_key_violations: int
    source_migration_versions: tuple[int, ...]
    row_counts: tuple[tuple[str, int], ...]
    _source_data_fingerprints: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DatabasePreparationPlan:
    path: Path
    before: DatabaseInspection
    backup: VerifiedDatabaseBackup | None
    requires_migration: bool


@dataclass(frozen=True)
class DatabasePreparationResult:
    inspection: DatabaseInspection
    backup: VerifiedDatabaseBackup | None
    migrated: bool


def _resolved_path(value: str | Path) -> Path:
    path = Path(value).expanduser().absolute()
    if ".." in path.parts:
        raise DatabasePreparationError("DATABASE_PATH_UNSAFE")
    return path


def _check_path_components(path: Path, *, allow_missing_file: bool) -> tuple[int, int, int, int] | None:
    """Reject links, reparse points, non-files and multiply-linked DB files."""
    current = path
    identity: tuple[int, int, int, int] | None = None
    while True:
        if os.path.lexists(current):
            try:
                info = os.lstat(current)
            except OSError:
                raise DatabasePreparationError("DATABASE_PATH_UNSAFE") from None
            if (
                stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400
            ):
                raise DatabasePreparationError("DATABASE_PATH_UNSAFE")
            if current == path:
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise DatabasePreparationError("DATABASE_PATH_UNSAFE")
                identity = (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size)
        elif current == path and not allow_missing_file:
            raise DatabasePreparationError("DATABASE_NOT_FOUND")
        if current.parent == current:
            break
        current = current.parent
    if not path.parent.is_dir():
        raise DatabasePreparationError("DATABASE_PARENT_UNAVAILABLE")
    return identity


def _connect_read_only(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(
            f"{path.as_uri()}?mode=ro", uri=True, timeout=2.0,
        )
        connection.execute("PRAGMA query_only=ON")
        return connection
    except (OSError, sqlite3.Error, ValueError):
        raise DatabasePreparationError("DATABASE_OPEN_FAILED") from None


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _fingerprint_rows(connection: sqlite3.Connection, table: str) -> tuple[int, str]:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({_quote_identifier(table)})")}
    selected = tuple(name for name in _DATA_COLUMNS[table] if name in columns)
    if not selected:
        return 0, hashlib.sha256(b"").hexdigest()
    quoted = ",".join(_quote_identifier(name) for name in selected)
    order = ",".join(_quote_identifier(name) for name in selected)
    digest = hashlib.sha256()
    count = 0
    for row in connection.execute(
        f"SELECT {quoted} FROM {_quote_identifier(table)} ORDER BY {order}"
    ):
        encoded = json.dumps(
            tuple(value.hex() if isinstance(value, bytes) else value for value in row),
            ensure_ascii=True, separators=(",", ":"),
        ).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        count += 1
    return count, digest.hexdigest()


def _classify(
    *,
    exists: bool,
    tables: tuple[str, ...],
    versions: tuple[int, ...],
    columns: dict[str, frozenset[str]],
) -> DatabaseKind:
    if not exists:
        return "NEW"
    if not tables:
        return "EMPTY"
    table_set = set(tables)
    if versions not in _KNOWN_MIGRATION_STATES:
        return "UNKNOWN"
    if not _BASE_TABLES.issubset(table_set):
        return "UNKNOWN"
    for table, required in _REQUIRED_COLUMNS.items():
        if not required.issubset(columns.get(table, frozenset())):
            return "UNKNOWN"
    if 2 in versions and not _CATALOG_TABLES.issubset(table_set):
        return "UNKNOWN"
    if 2 in versions:
        if "is_active" not in columns.get("catalog_nodes", frozenset()):
            return "UNKNOWN"
        if any(
            not required.issubset(columns.get(table, frozenset()))
            for table, required in _CATALOG_COLUMNS.items()
        ):
            return "UNKNOWN"
    if 3 in versions and "catalog_unresolved_sources" not in table_set:
        return "UNKNOWN"
    if 3 in versions and not {
        "run_id", "channel_id", "telegram_message_id", "reason",
    }.issubset(columns.get("catalog_unresolved_sources", frozenset())):
        return "UNKNOWN"
    if (4 in versions or 6 in versions) and "downloads" not in table_set:
        return "UNKNOWN"
    if 5 in versions:
        if not {
            "sha256", "validated_at", "failure_category", "owner_pid",
            "contract_version", "evidence_version",
        }.issubset(columns.get("downloads", frozenset())):
            return "UNKNOWN"
        if any(
            table not in table_set
            or not required.issubset(columns.get(table, frozenset()))
            for table, required in _S6_COLUMNS.items()
        ):
            return "UNKNOWN"
    if 6 in versions and any(
        not required.issubset(columns.get(table, frozenset()))
        for table, required in _S7_V6_COLUMNS.items()
    ):
        return "UNKNOWN"
    if 7 in versions and any(
        not required.issubset(columns.get(table, frozenset()))
        for table, required in _S7_V7_COLUMNS.items()
    ):
        return "UNKNOWN"
    if versions == (1, 2, 3, 4, 5, 6, 7):
        expected = _BASE_TABLES | _CATALOG_TABLES | {
            "catalog_unresolved_sources", "downloads",
        }
        return "CURRENT" if expected.issubset(table_set) else "UNKNOWN"
    return "LEGACY"


def inspect_database(value: str | Path) -> DatabaseInspection:
    """Inspect a known database without migration or content output."""
    path = _resolved_path(value)
    identity = _check_path_components(path, allow_missing_file=True)
    if identity is None:
        return DatabaseInspection(
            path, "NEW", False, (), (), (), "NOT_CHECKED", 0, None,
        )
    connection = _connect_read_only(path)
    try:
        try:
            integrity_rows = tuple(
                row[0] for row in connection.execute("PRAGMA quick_check")
            )
        except sqlite3.DatabaseError:
            return DatabaseInspection(
                path, "CORRUPT", True, (), (), (), "FAILED", 0, identity,
            )
        if integrity_rows != ("ok",):
            return DatabaseInspection(
                path, "CORRUPT", True, (), (), (), "FAILED", 0, identity,
            )
        tables = tuple(sorted(
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ))
        if not tables:
            return DatabaseInspection(
                path, "EMPTY", True, (), (), (), "OK", 0, identity,
            )
        table_set = set(tables)
        if "schema_migrations" not in table_set:
            return DatabaseInspection(
                path, "UNKNOWN", True, (), tables, (), "OK", 0, identity,
            )
        migration_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(schema_migrations)")
        }
        if not {"version", "applied_at"}.issubset(migration_columns):
            return DatabaseInspection(
                path, "UNKNOWN", True, (), tables, (), "OK", 0, identity,
            )
        try:
            versions = tuple(sorted(
                int(row[0]) for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ))
        except (sqlite3.Error, TypeError, ValueError):
            return DatabaseInspection(
                path, "UNKNOWN", True, (), tables, (), "OK", 0, identity,
            )
        if len(set(versions)) != len(versions) or any(v not in range(1, 8) for v in versions):
            return DatabaseInspection(
                path, "UNKNOWN", True, versions, tables, (), "OK", 0, identity,
            )
        columns = {
            table: frozenset(
                row[1]
                for row in connection.execute(
                    f"PRAGMA table_info({_quote_identifier(table)})"
                )
            )
            for table in tables
        }
        kind = _classify(
            exists=True, tables=tables, versions=versions, columns=columns,
        )
        if kind == "UNKNOWN":
            return DatabaseInspection(
                path, kind, True, versions, tables, (), "OK", 0, identity,
            )
        fk_violations = len(tuple(connection.execute("PRAGMA foreign_key_check")))
        counts: list[tuple[str, int]] = []
        fingerprints: list[tuple[str, str]] = []
        for table in _DATA_TABLES:
            if table in table_set:
                count, fingerprint = _fingerprint_rows(connection, table)
                counts.append((table, count))
                fingerprints.append((table, fingerprint))
        if fk_violations:
            kind = "CORRUPT"
        return DatabaseInspection(
            path, kind, True, versions, tables, tuple(counts), "OK",
            fk_violations, identity, tuple(fingerprints),
        )
    except sqlite3.Error:
        raise DatabasePreparationError("DATABASE_INSPECTION_FAILED") from None
    finally:
        connection.close()


def _private_backup_directory(database: Path) -> Path:
    backup_dir = database.parent / ".telegram-courses-backups"
    try:
        from telegram_courses.s9_operational_ledger import (
            LedgerError,
            _create_private_directory,
            _open_private_directory_guard,
        )

        if os.path.lexists(backup_dir):
            guard = _open_private_directory_guard(backup_dir)
        else:
            guard = _create_private_directory(backup_dir)
        try:
            guard.verify(backup_dir)
        finally:
            guard.close()
    except (OSError, RuntimeError, ValueError, LedgerError):
        raise DatabasePreparationError("BACKUP_DIRECTORY_UNSAFE") from None
    return backup_dir


def create_verified_backup(value: str | Path) -> VerifiedDatabaseBackup:
    """Create and verify a consistent, private SQLite backup without overwrite."""
    path = _resolved_path(value)
    before = inspect_database(path)
    if not before.exists or before.kind in {"UNKNOWN", "CORRUPT", "NEW"}:
        raise DatabasePreparationError("BACKUP_SOURCE_UNSUPPORTED")
    backup_dir = _private_backup_directory(path)
    backup_path = backup_dir / (
        f"{path.stem}.backup-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex}.sqlite3"
    )
    try:
        descriptor = os.open(
            backup_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
        os.close(descriptor)
        source = _connect_read_only(path)
        target = sqlite3.connect(backup_path, timeout=2.0)
        try:
            source.backup(target)
            target.commit()
        finally:
            target.close()
            source.close()
        from telegram_courses.s9_operational_ledger import _verify_private_file

        _verify_private_file(backup_path)
        backup_inspection = inspect_database(backup_path)
        after = inspect_database(path)
        if (
            backup_inspection.kind != before.kind
            or backup_inspection.migration_versions != before.migration_versions
            or backup_inspection.row_counts != before.row_counts
            or backup_inspection._data_fingerprints != before._data_fingerprints
            or after.file_identity != before.file_identity
            or after._data_fingerprints != before._data_fingerprints
        ):
            raise DatabasePreparationError("BACKUP_VERIFICATION_FAILED")
        digest = hashlib.sha256()
        with backup_path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return VerifiedDatabaseBackup(
            backup_path, path, before.file_identity, before.kind,
            digest.hexdigest(), backup_inspection.integrity,
            backup_inspection.foreign_key_violations,
            backup_inspection.migration_versions, backup_inspection.row_counts,
            before._data_fingerprints,
        )
    except DatabasePreparationError:
        raise
    except (OSError, sqlite3.Error, RuntimeError, ValueError):
        raise DatabasePreparationError("BACKUP_CREATION_FAILED") from None


def plan_database_preparation(value: str | Path) -> DatabasePreparationPlan:
    """Inspect a database and make a backup when legacy data needs migration."""
    before = inspect_database(value)
    if before.kind in {"UNKNOWN", "CORRUPT"}:
        raise DatabasePreparationError("DATABASE_SCHEMA_UNSUPPORTED")
    backup = (
        create_verified_backup(before.path)
        if before.exists and before.kind in {"LEGACY", "EMPTY"}
        else None
    )
    return DatabasePreparationPlan(
        before.path, before, backup,
        before.kind in {"NEW", "EMPTY", "LEGACY"},
    )


def _verify_backup(plan: DatabasePreparationPlan) -> None:
    if not plan.before.exists:
        if plan.backup is not None:
            raise DatabasePreparationError("BACKUP_PLAN_INVALID")
        return
    if plan.backup is None:
        raise DatabasePreparationError("BACKUP_REQUIRED")
    backup = plan.backup
    try:
        from telegram_courses.s9_operational_ledger import _verify_private_file

        _verify_private_file(backup.path)
        if backup.path.stat().st_nlink != 1:
            raise DatabasePreparationError("BACKUP_PATH_UNSAFE")
        digest = hashlib.sha256(backup.path.read_bytes()).hexdigest()
        inspection = inspect_database(backup.path)
    except DatabasePreparationError:
        raise
    except (OSError, RuntimeError, ValueError):
        raise DatabasePreparationError("BACKUP_VERIFICATION_FAILED") from None
    if (
        digest != backup.sha256
        or inspection.integrity != "OK"
        or inspection.kind != plan.before.kind
        or inspection.migration_versions != plan.before.migration_versions
        or inspection._data_fingerprints != plan.before._data_fingerprints
    ):
        raise DatabasePreparationError("BACKUP_VERIFICATION_FAILED")


def verify_backup_receipt(
    receipt: VerifiedDatabaseBackup,
    database: str | Path,
) -> None:
    """Bind a backup receipt to the exact source database and verify it again."""
    source_path = _resolved_path(database)
    if (
        type(receipt) is not VerifiedDatabaseBackup
        or os.path.normcase(str(source_path)) != os.path.normcase(str(receipt.source_path))
    ):
        raise DatabasePreparationError("BACKUP_SOURCE_MISMATCH")
    current = inspect_database(source_path)
    if (
        not current.exists
        or current.kind != receipt.source_kind
        or current.file_identity != receipt.source_file_identity
        or current.migration_versions != receipt.source_migration_versions
        or current.row_counts != receipt.row_counts
        or current._data_fingerprints != receipt._source_data_fingerprints
    ):
        raise DatabasePreparationError("BACKUP_SOURCE_CHANGED")
    try:
        from telegram_courses.s9_operational_ledger import _verify_private_file

        _check_path_components(receipt.path, allow_missing_file=False)
        _verify_private_file(receipt.path)
        if receipt.path.stat().st_nlink != 1:
            raise DatabasePreparationError("BACKUP_PATH_UNSAFE")
        digest = hashlib.sha256(receipt.path.read_bytes()).hexdigest()
    except DatabasePreparationError:
        raise
    except (OSError, RuntimeError, ValueError):
        raise DatabasePreparationError("BACKUP_VERIFICATION_FAILED") from None
    if digest != receipt.sha256:
        raise DatabasePreparationError("BACKUP_VERIFICATION_FAILED")


async def apply_database_preparation(
    plan: DatabasePreparationPlan,
    *,
    confirmed: bool,
    busy_timeout_ms: int = 1000,
) -> DatabasePreparationResult:
    """Apply known migrations only after explicit confirmation and backup."""
    if type(confirmed) is not bool:
        raise DatabasePreparationError("CONFIRMATION_REQUIRED")
    if not plan.requires_migration:
        current = inspect_database(plan.path)
        if current != plan.before:
            raise DatabasePreparationError("DATABASE_CHANGED_AFTER_REVIEW")
        return DatabasePreparationResult(current, plan.backup, False)
    if not confirmed:
        raise DatabasePreparationError("CONFIRMATION_REQUIRED")
    if plan.before.kind in {"UNKNOWN", "CORRUPT", "CURRENT"}:
        raise DatabasePreparationError("DATABASE_SCHEMA_UNSUPPORTED")
    _verify_backup(plan)
    current = inspect_database(plan.path)
    if (
        current != plan.before
        or current.file_identity != plan.before.file_identity
        or current._data_fingerprints != plan.before._data_fingerprints
    ):
        raise DatabasePreparationError("DATABASE_CHANGED_AFTER_REVIEW")
    try:
        await DownloadRepository(
            plan.path, busy_timeout_ms=busy_timeout_ms,
        ).migrate()
    except Exception:
        # The verified backup is intentionally retained. No automatic overwrite
        # or restore is attempted if one migration transaction fails.
        raise DatabasePreparationError("DATABASE_MIGRATION_FAILED") from None
    after = inspect_database(plan.path)
    if after.kind != "CURRENT":
        raise DatabasePreparationError("DATABASE_MIGRATION_UNVERIFIED")
    before_fingerprints = dict(plan.before._data_fingerprints)
    after_fingerprints = dict(after._data_fingerprints)
    if any(after_fingerprints.get(name) != fingerprint for name, fingerprint in before_fingerprints.items()):
        raise DatabasePreparationError("DATABASE_MIGRATION_DATA_CHANGED")
    return DatabasePreparationResult(after, plan.backup, True)
