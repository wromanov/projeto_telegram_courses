from __future__ import annotations

import sys
from pathlib import Path

import pytest

from telegram_courses.config import TelegramCredentials
from telegram_courses.credentials import CredentialVault

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="requires Windows DPAPI and ACLs"
)


def test_credential_vault_real_dpapi_roundtrip_uses_only_synthetic_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local_app_data = tmp_path / "local-app-data"
    local_app_data.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    vault = CredentialVault()
    credentials = TelegramCredentials(71234, "d" * 32)

    vault.setup(credentials)

    storage = vault._storage
    artifact = storage._path.read_bytes()
    assert storage._path == local_app_data / "telegram_courses" / "credentials.dpapi"
    assert artifact.startswith(b"TCC\x01")
    assert b"71234" not in artifact
    assert credentials.api_hash.encode() not in artifact
    assert vault.status() is True
    assert vault.load() == credentials
    storage._verify_acl(storage._path.parent, is_directory=True)
    storage._verify_acl(storage._path, is_directory=False)
