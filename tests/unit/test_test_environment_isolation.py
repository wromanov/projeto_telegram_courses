from __future__ import annotations

import os
from pathlib import Path

import pytest

from telegram_courses import credentials as credential_module
from telegram_courses import telethon_session
from telegram_courses.config import ConfigurationError, load_telegram_credentials


def test_default_credential_lookup_cannot_reach_user_vault(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    test_temp_root = tmp_path_factory.getbasetemp().resolve()
    local_app_data = Path(os.environ["LOCALAPPDATA"]).resolve()
    assert local_app_data.is_relative_to(test_temp_root)
    assert "TELEGRAM_API_ID" not in os.environ
    assert "TELEGRAM_API_HASH" not in os.environ

    attempted_paths: list[Path] = []

    class EmptyTestVault:
        def __init__(self) -> None:
            self.path = local_app_data / "telegram_courses" / "credentials.dpapi"

        def load(self) -> None:
            assert self.path.is_relative_to(test_temp_root)
            assert not self.path.exists()
            attempted_paths.append(self.path)
            return None

    monkeypatch.setattr(credential_module, "CredentialVault", EmptyTestVault)

    with pytest.raises(ConfigurationError):
        load_telegram_credentials({})

    assert attempted_paths == [
        local_app_data / "telegram_courses" / "credentials.dpapi"
    ]


def test_default_session_vault_path_is_test_temporary_storage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    test_temp_root = tmp_path_factory.getbasetemp().resolve()
    local_app_data = Path(os.environ["LOCALAPPDATA"]).resolve()
    assert local_app_data.is_relative_to(test_temp_root)

    class SyntheticWindowsApi:
        def current_user_sid(self) -> str:
            return "S-1-5-21-1000000000-2000000000-3000000000-1001"

        def drive_type(self, _path: Path) -> int:
            return 3

        def attributes(self, path: Path) -> int | None:
            if path == local_app_data:
                return telethon_session._FILE_ATTRIBUTE_DIRECTORY
            return None

    monkeypatch.setattr(telethon_session.sys, "platform", "win32")
    vault = telethon_session._ProtectedSessionVault(
        _api=SyntheticWindowsApi(),
        _protector=object(),
    )

    assert vault._path == local_app_data / "telegram_courses" / "session.dpapi"
    assert vault._path.resolve(strict=False).is_relative_to(test_temp_root)
