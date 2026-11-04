from __future__ import annotations

import asyncio
import sqlite3
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import pytest
from tools import s9_native_windows_hml_02 as launcher

from telegram_courses.download_repository import DownloadRepository
from telegram_courses.s9_operational_ledger import _create_private_directory


def test_launcher_releases_ledger_for_supervisor_process(tmp_path: Path) -> None:
    guard = _create_private_directory(tmp_path / "run")
    run = guard.path
    guard.close()
    ledger, _, _ = launcher._start_ledger(run)
    command = [sys.executable, "-B", "-c", (
        "import sys; from telegram_courses.s9_supervisor_cli import "
        "load_supervised_run_context; load_supervised_run_context(sys.argv[1])"
    ), str(run)]
    try:
        blocked_cli = subprocess.run(
            [sys.executable, "-B", "-m", "telegram_courses.s9_supervisor_cli",
             "g1", "--run-directory", str(run), "--output-directory", str(run / "work-g1")],
            capture_output=True, text=True, timeout=30,
        )
        assert blocked_cli.returncode == 2
        assert blocked_cli.stderr.strip() == "offline supervisor blocked"
        assert not (run / "queue-run.lock").exists()
        blocked = subprocess.run(command, capture_output=True, text=True, timeout=30)
        assert blocked.returncode != 0
        assert "LEDGER_WRITER" in blocked.stderr
        launcher._run_stage(command, label="G1", ledger=ledger)
        assert ledger.snapshot()["run"]["gate"] == "G1"
    finally:
        ledger.close()


def _create_v1_database(path: Path) -> None:
    database = sqlite3.connect(path)
    try:
        migration = files("telegram_courses").joinpath(
            "migrations/001_initial.sql",
        ).read_text(encoding="utf-8")
        for statement in migration.split(";"):
            if statement.strip():
                database.execute(statement)
        database.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES(1, 'fixture')",
        )
        database.commit()
    finally:
        database.close()


def _readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def test_source_v1_empty_is_accepted_for_private_copy_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.sqlite3"
    run_copy = tmp_path / "run" / "catalog.sqlite3"
    run_copy.parent.mkdir()
    _create_v1_database(source)
    source_bytes = source.read_bytes()

    source_connection = _readonly(source)
    try:
        snapshot = launcher._source_database_snapshot(source_connection)
        source_tables = {
            row[0] for row in source_connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'",
            )
        }
    finally:
        source_connection.close()
    assert snapshot == {
        "channel_id": None,
        "channel_id_source": "OPERATOR_PRIVATE_TTY_REQUIRED",
    }
    assert "catalog_runs" not in source_tables
    assert source.read_bytes() == source_bytes

    source_connection = sqlite3.connect(source)
    destination = sqlite3.connect(run_copy)
    try:
        source_connection.backup(destination)
    finally:
        source_connection.close()
        destination.close()

    monkeypatch.setattr(launcher, "_private_file", lambda _path: None)
    launcher._migrate_private_run_database(run_copy)
    launcher._migrate_private_run_database(run_copy)

    migrated = _readonly(run_copy)
    try:
        versions = {
            row[0] for row in migrated.execute(
                "SELECT version FROM schema_migrations",
            )
        }
        assert versions == set(range(1, 8))
        assert migrated.execute("SELECT COUNT(*) FROM catalog_nodes").fetchone()[0] == 0
        assert migrated.execute("SELECT COUNT(*) FROM catalog_runs").fetchone()[0] == 0
        assert migrated.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert migrated.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        migrated.close()

    assert source.read_bytes() == source_bytes


def test_new_empty_database_receives_complete_official_schema(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "new.sqlite3"
    repository = DownloadRepository(database_path)

    asyncio.run(repository.migrate())
    asyncio.run(repository.migrate())

    migrated = _readonly(database_path)
    try:
        launcher._validate_migrated_schema(migrated)
        assert migrated.execute("SELECT COUNT(*) FROM catalog_nodes").fetchone()[0] == 0
        assert migrated.execute("SELECT COUNT(*) FROM catalog_runs").fetchone()[0] == 0
    finally:
        migrated.close()


def test_incomplete_source_schema_fails_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "incomplete.sqlite3"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("CREATE TABLE schema_migrations(version INTEGER)")
        connection.execute("INSERT INTO schema_migrations VALUES(1)")
        connection.commit()
    finally:
        connection.close()

    source = _readonly(database_path)
    try:
        with pytest.raises(
            launcher.LauncherBlocked,
            match="S9_SQLITE_SCHEMA_INCOMPLETE",
        ):
            launcher._source_database_snapshot(source)
    finally:
        source.close()


@pytest.mark.parametrize("value", ["0", "123", "-42", "-9223372036854775809", "nope"])
def test_private_channel_id_prompt_rejects_invalid_ids(
    value: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(launcher, "_require_tty", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt: value)

    with pytest.raises(launcher.LauncherBlocked, match="RASMOO_CHANNEL_ID_INVALID"):
        launcher._prompt_channel_id()


def test_private_channel_id_prompt_does_not_log_entered_id(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    channel_id = "-1000000000123"
    monkeypatch.setattr(launcher, "_require_tty", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt: channel_id)

    assert launcher._prompt_channel_id() == int(channel_id)
    assert channel_id not in capsys.readouterr().out


def test_manifest_proposal_contains_only_planned_acceptance_requirements(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    channel_id = -1000000000123
    monkeypatch.setattr(launcher, "_prompt_channel_id", lambda: channel_id)
    monkeypatch.setattr(launcher, "_create_private_file", lambda path, data: path.write_bytes(data))

    manifest, manifest_hash, scope_hash = launcher._load_or_create_manifest(
        state,
        {"channel_id": None, "channel_id_source": "OPERATOR_PRIVATE_TTY_REQUIRED"},
    )

    assert manifest["channel_id"] == channel_id
    assert manifest["catalog_expectation"]["state"] == "PENDING_G3"
    assert manifest["hierarchy"] == {"TRACK": 1, "COURSE": 2, "MODULE": 2}
    assert manifest["unresolved_count"] is None
    assert manifest_hash == launcher.sha256_bytes(launcher.canonical_bytes(manifest))
    assert scope_hash == launcher.sha256_bytes(
        launcher.canonical_bytes(manifest["scope"]),
    )
    output = capsys.readouterr().out
    assert str(channel_id) not in output
    assert "PENDING_G3" in output
