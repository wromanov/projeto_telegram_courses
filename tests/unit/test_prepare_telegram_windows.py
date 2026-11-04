from __future__ import annotations

import os
from pathlib import Path

import pytest
from tools.prepare_telegram_windows import PreparationError, prepare_product_workspace

from telegram_courses.cli import _parse_arguments
from telegram_courses.config import ConfigurationError
from telegram_courses.s9_operational_ledger import _open_private_directory_guard


def test_private_workspace_is_idempotent_and_preserves_unrelated_data(tmp_path: Path) -> None:
    vault_directory = tmp_path / "telegram_courses"
    vault_directory.mkdir()
    marker = vault_directory / "sentinel"
    marker.write_bytes(b"preserve")
    root = prepare_product_workspace(tmp_path)
    saved = root / "db" / "existing.bin"
    saved.write_bytes(b"existing")
    assert prepare_product_workspace(tmp_path) == root
    for path in (root, root / "db", root / "downloads"):
        guard = _open_private_directory_guard(path)
        guard.verify(path)
        guard.close()
    assert marker.read_bytes() == b"preserve"
    assert saved.read_bytes() == b"existing"


@pytest.mark.skipif(os.name != "nt", reason="Windows inherited ACL behavior")
def test_existing_inherited_root_is_not_repaired_or_modified(tmp_path: Path) -> None:
    from telegram_courses.windows_security import WindowsSecurityApi

    root = tmp_path / "telegram_courses_product"
    root.mkdir()
    marker = root / "sentinel"
    marker.write_bytes(b"preserve")
    api = WindowsSecurityApi()
    before = api.inspect_acl(root)
    assert before[1] is False
    with pytest.raises(PreparationError, match="PRODUCT_DIRECTORY_PRIVATE_CHECK_FAILED"):
        prepare_product_workspace(tmp_path)
    assert api.inspect_acl(root) == before
    assert marker.read_bytes() == b"preserve"
    assert not (root / "db").exists()


def test_relative_local_app_data_is_rejected() -> None:
    with pytest.raises(PreparationError, match="LOCALAPPDATA_INVALID"):
        prepare_product_workspace(Path("relative"))


@pytest.mark.parametrize("extra", [[], ["--download-dir", "downloads", "--confirm"]])
def test_private_queue_requires_explicit_directory_and_interactive_confirmation(extra: list[str]) -> None:
    with pytest.raises(ConfigurationError):
        _parse_arguments(["download", "queue", "--channel-id", "-1001", "--private-downloads", *extra])
