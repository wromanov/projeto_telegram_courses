from __future__ import annotations

import asyncio
import os
import sqlite3
import stat
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegram_courses.database_preparation import (
    DatabasePreparationError,
    apply_database_preparation,
    create_verified_backup,
    inspect_database,
    plan_database_preparation,
    verify_backup_receipt,
)


def _create_legacy_v1(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        sql = files("telegram_courses").joinpath("migrations/001_initial.sql").read_text()
        for statement in sql.split(";"):
            if statement.strip():
                connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES(1, 'synthetic')"
        )
        connection.execute(
            "INSERT INTO channels(telegram_chat_id,title,username,parser_key,created_at,updated_at,last_scanned_at) "
            "VALUES(-1001234567890,'Synthetic channel',NULL,NULL,'created','updated',NULL)"
        )
        connection.execute(
            "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,edit_date_utc,text,grouped_id,created_at,updated_at) "
            "VALUES(-1001234567890,42,'2026-01-01T00:00:00Z',NULL,'Synthetic lesson',NULL,'created','updated')"
        )
        connection.execute(
            "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,kind,telegram_media_id,original_filename,mime_type,file_size_bytes,created_at,updated_at) "
            "VALUES(-1001234567890,42,0,'DOCUMENT','synthetic-media','lesson.bin','application/octet-stream',7,'created','updated')"
        )
        connection.commit()
    finally:
        connection.close()


def _migration_versions(path: Path) -> tuple[int, ...]:
    with sqlite3.connect(path) as connection:
        return tuple(row[0] for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ))


def _create_current_schema(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        for name, version in (
            ("001_initial.sql", 1),
            ("006_s7_incremental_sync.sql", 6),
            ("007_s7_corrective_identity_observation.sql", 7),
            ("002_catalog.sql", 2),
            ("003_catalog_unresolved.sql", 3),
            ("004_downloads.sql", 4),
            ("005_s6_integrity_v2.sql", 5),
        ):
            sql = files("telegram_courses").joinpath(f"migrations/{name}").read_text()
            for statement in sql.split(";"):
                if statement.strip():
                    connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES(?, 'synthetic')",
                (version,),
            )
        connection.commit()
    finally:
        connection.close()


def test_inspection_distinguishes_missing_empty_legacy_current_and_unknown(tmp_path: Path) -> None:
    missing = tmp_path / "new.sqlite3"
    assert inspect_database(missing).kind == "NEW"
    assert not missing.exists()

    empty = tmp_path / "empty.sqlite3"
    sqlite3.connect(empty).close()
    assert inspect_database(empty).kind == "EMPTY"

    legacy = tmp_path / "legacy.sqlite3"
    _create_legacy_v1(legacy)
    assert inspect_database(legacy).kind == "LEGACY"
    assert inspect_database(legacy).migration_versions == (1,)

    current = tmp_path / "current.sqlite3"
    _create_current_schema(current)
    assert inspect_database(current).kind == "CURRENT"
    assert inspect_database(current).migration_versions == (1, 2, 3, 4, 5, 6, 7)

    unknown = tmp_path / "unknown.sqlite3"
    with sqlite3.connect(unknown) as connection:
        connection.execute("CREATE TABLE unrelated(value TEXT)")
    assert inspect_database(unknown).kind == "UNKNOWN"
    with pytest.raises(DatabasePreparationError, match="DATABASE_SCHEMA_UNSUPPORTED"):
        plan_database_preparation(unknown)


def test_legacy_backup_and_migration_require_confirmation_and_preserve_rows(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    _create_legacy_v1(database)
    plan = plan_database_preparation(database)

    assert plan.requires_migration
    assert plan.before.kind == "LEGACY"
    assert plan.backup is not None
    assert plan.backup.path.is_file()
    assert len(plan.backup.sha256) == 64
    assert plan.backup.integrity == "OK"
    assert plan.backup.foreign_key_violations == 0
    assert plan.backup.source_path == database.absolute()
    assert dict(plan.backup.row_counts)["messages"] == 1
    assert dict(plan.backup.row_counts)["media_items"] == 1
    assert plan.backup.path != database

    with pytest.raises(DatabasePreparationError, match="CONFIRMATION_REQUIRED"):
        asyncio.run(apply_database_preparation(plan, confirmed=False))
    assert _migration_versions(database) == (1,)

    result = asyncio.run(apply_database_preparation(plan, confirmed=True))
    assert result.migrated
    assert result.inspection.kind == "CURRENT"
    assert result.backup == plan.backup
    assert dict(result.inspection.row_counts)["messages"] == 1
    assert dict(result.inspection.row_counts)["media_items"] == 1
    assert dict(result.inspection._data_fingerprints) == dict(plan.before._data_fingerprints)


def test_current_database_backup_is_consistent_and_never_overwritten(tmp_path: Path) -> None:
    database = tmp_path / "current.sqlite3"
    _create_current_schema(database)

    first = create_verified_backup(database)
    second = create_verified_backup(database)

    assert first.path.is_file() and second.path.is_file()
    assert first.path != second.path
    assert first.sha256 != ""
    assert first.integrity == second.integrity == "OK"
    assert first.source_migration_versions == (1, 2, 3, 4, 5, 6, 7)
    assert first.row_counts == second.row_counts
    assert inspect_database(database).kind == "CURRENT"
    verify_backup_receipt(first, database)

    with pytest.raises(DatabasePreparationError, match="BACKUP_SOURCE_MISMATCH"):
        verify_backup_receipt(first, tmp_path / "other.sqlite3")


def test_changed_database_after_backup_is_blocked(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    _create_legacy_v1(database)
    plan = plan_database_preparation(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE messages SET text='changed' WHERE telegram_message_id=42"
        )

    assert plan.backup is not None
    with pytest.raises(DatabasePreparationError, match="BACKUP_SOURCE_CHANGED"):
        verify_backup_receipt(plan.backup, database)

    with pytest.raises(DatabasePreparationError, match="DATABASE_CHANGED_AFTER_REVIEW"):
        asyncio.run(apply_database_preparation(plan, confirmed=True))
    assert _migration_versions(database) == (1,)
    assert plan.backup is not None and plan.backup.path.is_file()


def test_corrupt_database_fails_closed(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a sqlite database")

    assert inspect_database(corrupt).kind == "CORRUPT"
    with pytest.raises(DatabasePreparationError):
        plan_database_preparation(corrupt)


def test_modified_backup_is_rejected_before_migration(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    _create_legacy_v1(database)
    plan = plan_database_preparation(database)
    assert plan.backup is not None
    plan.backup.path.write_bytes(b"tampered synthetic backup")

    with pytest.raises(DatabasePreparationError, match="BACKUP_VERIFICATION_FAILED"):
        verify_backup_receipt(plan.backup, database)
    assert _migration_versions(database) == (1,)


def test_hard_link_database_path_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    _create_legacy_v1(database)
    alias = tmp_path / "legacy-alias.sqlite3"
    try:
        alias.hardlink_to(database)
    except OSError as error:
        pytest.skip(f"hard links unavailable in this test filesystem: {type(error).__name__}")

    with pytest.raises(DatabasePreparationError, match="DATABASE_PATH_UNSAFE"):
        inspect_database(alias)


def test_reparse_ancestor_is_rejected_for_existing_database(tmp_path: Path, monkeypatch) -> None:
    from telegram_courses import database_preparation as preparation

    database = tmp_path / "db-dir" / "catalog.sqlite3"
    database.parent.mkdir()
    _create_legacy_v1(database)
    real_lstat = os.lstat

    def reparse_ancestor(path):
        if Path(path) == database.parent:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR | 0o755,
                st_file_attributes=0x400,
                st_nlink=1,
            )
        return real_lstat(path)

    monkeypatch.setattr(preparation.os, "lstat", reparse_ancestor)
    with pytest.raises(DatabasePreparationError, match="DATABASE_PATH_UNSAFE"):
        inspect_database(database)


@pytest.mark.parametrize(
    "missing_shape",
    ["catalog-active", "s6-tables", "s7-v6-column", "s7-v7-column"],
)
def test_current_migration_versions_with_incomplete_schema_are_unknown(
    tmp_path: Path, missing_shape: str,
) -> None:
    database = tmp_path / f"incomplete-{missing_shape}.sqlite3"
    _create_current_schema(database)
    with sqlite3.connect(database) as connection:
        if missing_shape == "catalog-active":
            connection.execute("ALTER TABLE catalog_nodes DROP COLUMN is_active")
        elif missing_shape == "s6-tables":
            connection.execute("DROP TABLE s6_v2_evidence")
            connection.execute("DROP TABLE s6_v2_attempts")
        elif missing_shape == "s7-v6-column":
            connection.execute("ALTER TABLE scan_runs DROP COLUMN sync_mode")
        else:
            connection.execute(
                "ALTER TABLE media_items DROP COLUMN remote_observation_state"
            )

    inspection = inspect_database(database)
    assert inspection.kind == "UNKNOWN"
    with pytest.raises(DatabasePreparationError, match="DATABASE_SCHEMA_UNSUPPORTED"):
        plan_database_preparation(database)
