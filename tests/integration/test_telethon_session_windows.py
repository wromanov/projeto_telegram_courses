from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from telegram_courses import telethon_session as sessions

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="requires Windows DPAPI and ACLs"
)


def _vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sessions._ProtectedSessionVault:
    local_app_data = tmp_path / "local-app-data"
    local_app_data.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    return sessions._ProtectedSessionVault()


def test_real_dpapi_storage_roundtrip_is_adapter_local_and_outside_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _vault(tmp_path, monkeypatch)
    secret = "synthetic-dpapi-session-marker-61e2"
    acl_checks: list[tuple[Path, bool, tuple[str, bool, tuple[tuple[int, int, int, str], ...]]]] = []
    verify_acl = vault._verify_acl

    def record_acl(path: Path, *, is_directory: bool) -> None:
        verify_acl(path, is_directory=is_directory)
        acl_checks.append((path, is_directory, vault._api.inspect_acl(path)))

    vault._verify_acl = record_acl

    vault._save(secret)
    artifact = vault._path.read_bytes()
    assert artifact.startswith(b"TCS\x01")
    assert secret.encode() not in artifact
    assert vault._load() == secret
    assert vault._path.is_relative_to(tmp_path)
    assert not vault._path.is_relative_to(Path(__file__).resolve().parents[2])

    owner, protected, entries = vault._api.inspect_acl(vault._path.parent)
    assert owner == vault._current_user_sid
    assert protected is True
    assert {entry[3] for entry in entries} == {
        sessions._OWNER_RIGHTS_SID,
        sessions._SYSTEM_SID,
        sessions._ADMINISTRATORS_SID,
    }
    assert any(path.name.startswith(".session-") for path, _, _ in acl_checks)
    assert any(path == vault._path for path, _, _ in acl_checks)
    for path, is_directory, (checked_owner, _, checked_entries) in acl_checks:
        assert checked_owner == vault._current_user_sid
        assert checked_entries
        if path.name.startswith(".session-"):
            assert not is_directory
    vault._verify_acl(vault._path.parent, is_directory=True)
    vault._verify_acl(vault._path, is_directory=False)
    assert vault.delete_local() is True


def test_application_and_cli_do_not_expose_session_plaintext_api() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src" / "telegram_courses"

    for source_path in source_root.glob("*.py"):
        if source_path.name == "telethon_session.py":
            continue
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    alias.name != "telegram_courses.telethon_session"
                    for alias in node.names
                )
            if isinstance(node, ast.ImportFrom):
                assert node.module != "telegram_courses.telethon_session"
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                assert not any(
                    argument.arg.casefold() in {"session", "string_session"}
                    for argument in args
                )


def test_tampered_dpapi_blob_fails_without_creating_telegram_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    telethon_client_module = sys.modules.get("telethon.client")
    vault = _vault(tmp_path, monkeypatch)
    vault._save("synthetic-session-for-tamper-test")
    vault._path.write_bytes(b"TCS\x01not-a-valid-dpapi-blob")

    with pytest.raises(sessions.IntegrityError):
        vault._load()
    assert sys.modules.get("telethon.client") is telethon_client_module


def test_broad_synthetic_dacl_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _vault(tmp_path, monkeypatch)
    vault._save("synthetic-session-for-acl-test")
    result = subprocess.run(
        [
            "icacls",
            str(vault._path.parent),
            "/grant",
            "*S-1-1-0:(OI)(CI)F",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0

    with pytest.raises(sessions.StorageError):
        vault._load()
