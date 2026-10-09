from __future__ import annotations

from pathlib import Path

import pytest

from telegram_courses import telethon_session as sessions
from telegram_courses.config import ConfigurationError, TelegramCredentials
from telegram_courses.credentials import (
    CredentialVault,
    CredentialVaultError,
    validate_credentials,
)


class _SyntheticProtector:
    def protect(self, value: bytes) -> bytes:
        return b"P" + bytes(byte ^ 0x5A for byte in value)

    def unprotect(self, value: bytes) -> bytes:
        if not value.startswith(b"P"):
            raise ValueError("synthetic decrypt failure")
        return bytes(byte ^ 0x5A for byte in value[1:])


class _SyntheticWindowsApi:
    def __init__(self, local_app_data: Path) -> None:
        self.local_app_data = local_app_data

    def current_user_sid(self) -> str:
        return "S-1-5-21-synthetic"

    def drive_type(self, _path: Path) -> int:
        return 3

    def attributes(self, path: Path) -> int | None:
        if not path.exists():
            return None
        return sessions._FILE_ATTRIBUTE_DIRECTORY if path.is_dir() else 0


def _vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CredentialVault:
    local_app_data = tmp_path / "local-app-data"
    local_app_data.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setattr(sessions.sys, "platform", "win32")
    storage = sessions._ProtectedCredentialsVault(
        _protector=_SyntheticProtector(),
        _api=_SyntheticWindowsApi(local_app_data),
    )
    storage._verify_acl = lambda *_args, **_kwargs: None
    return CredentialVault(_storage=storage)


SYNTHETIC_HASH = "a" * 32


def test_credentials_setup_roundtrip_is_encrypted_and_separate_from_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _vault(tmp_path, monkeypatch)
    credentials = TelegramCredentials(71234, SYNTHETIC_HASH)

    vault.setup(credentials)

    storage = vault._storage
    artifact = storage._path.read_bytes()
    assert storage._path == tmp_path / "local-app-data" / "telegram_courses" / "credentials.dpapi"
    assert artifact.startswith(b"TCC\x01")
    assert b"71234" not in artifact
    assert SYNTHETIC_HASH.encode() not in artifact
    assert vault.load() == credentials
    assert not (storage._path.parent / "session.dpapi").exists()
    assert list(storage._path.parent.iterdir()) == [storage._path]


def test_credentials_vault_missing_invalid_and_decryption_failure_are_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _vault(tmp_path, monkeypatch)
    assert vault.load() is None
    assert vault.status() is False

    vault._storage._path.parent.mkdir()
    vault._storage._path.write_bytes(b"invalid")
    with pytest.raises(CredentialVaultError):
        vault.load()
    vault._storage._path.write_bytes(b"TCC\x01not-encrypted-by-synthetic-protector")
    with pytest.raises(CredentialVaultError):
        vault.load()


def test_credentials_setup_does_not_overwrite_existing_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _vault(tmp_path, monkeypatch)
    first = TelegramCredentials(71234, SYNTHETIC_HASH)
    second = TelegramCredentials(71235, "b" * 32)
    vault.setup(first)
    original = vault._storage._path.read_bytes()

    with pytest.raises(CredentialVaultError):
        vault.setup(second)

    assert vault._storage._path.read_bytes() == original
    assert list(vault._storage._path.parent.iterdir()) == [vault._storage._path]


def test_credential_validation_rejects_malformed_values_without_echoing_them() -> None:
    for api_id, api_hash in (
        ("0", SYNTHETIC_HASH),
        ("not-an-id-secret-sentinel", SYNTHETIC_HASH),
        ("71234", "   "),
    ):
        with pytest.raises(ConfigurationError) as error:
            validate_credentials(api_id, api_hash)
        assert api_id not in str(error.value)
        assert api_hash not in str(error.value)
