from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_user_credentials_and_storage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep tests away from the invoking user's config, vault, and session."""
    local_app_data = tmp_path / "local-app-data"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    for name in (
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH",
        "TELEGRAM_COURSES_CONFIG",
        "TELEGRAM_COURSES_LOG_LEVEL",
    ):
        monkeypatch.delenv(name, raising=False)
