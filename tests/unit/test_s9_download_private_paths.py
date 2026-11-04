from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import pytest
from tools.s9_native_windows_hml_02 import _verify_new_download

from telegram_courses.cli import _prepare_s9_download_directories
from telegram_courses.download_repository import DownloadCandidate
from telegram_courses.downloads import (
    DownloadError,
    _finalize_no_overwrite,
    destination_paths,
)
from telegram_courses.s9_operational_ledger import (
    _create_private_directory,
    _open_private_directory_guard,
    _verify_private_file,
)


def _candidate() -> DownloadCandidate:
    return DownloadCandidate(
        media_item_id=1,
        channel_id=-1001,
        telegram_message_id=10,
        media_ordinal=0,
        telegram_media_id="synthetic",
        expected_bytes=4,
        original_filename="fixture.bin",
        lineage=(("course", "Synthetic"), ("lesson", "Fixture")),
    )


def test_planned_directories_pass_s9_guard_and_final_verification(
    tmp_path: Path,
) -> None:
    root_guard = _create_private_directory(tmp_path / "downloads")
    root = root_guard.path
    root_guard.close()
    candidate = _candidate()
    guards = _prepare_s9_download_directories(root, [candidate, candidate])
    final, partial = destination_paths(root, candidate)
    try:
        assert len(guards) == 3
        partial.write_bytes(b"test")
        _finalize_no_overwrite(partial, final)
        _verify_private_file(final)
    finally:
        for guard in reversed(guards):
            guard.close()
    guards = _prepare_s9_download_directories(root, [candidate])
    try:
        assert final.read_bytes() == b"test"
    finally:
        for guard in reversed(guards):
            guard.close()
    for directory in (final.parent, final.parent.parent):
        guard = _open_private_directory_guard(directory)
        guard.verify(directory)
        guard.close()

    database = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(database) as db:
        db.executescript(
            "CREATE TABLE media_items(id INTEGER,channel_id INTEGER);"
            "CREATE TABLE downloads(media_item_id INTEGER,state TEXT,final_path TEXT,"
            "expected_bytes INTEGER,downloaded_bytes INTEGER,sha256 TEXT);"
        )
        db.execute("INSERT INTO media_items VALUES(1,-1001)")
        db.execute(
            "INSERT INTO downloads VALUES(1,'DOWNLOADED',?,4,4,?)",
            (str(final), hashlib.sha256(b"test").hexdigest()),
        )
    transferred, verified = _verify_new_download(database, root, -1001, set(), 4)
    assert (
        transferred == 4
        and len(verified) == 1
        and verified[0]["sha256_verified"] is True
    )
    assert final.read_bytes() == b"test"


@pytest.mark.skipif(os.name != "nt", reason="Windows inherited ACL test")
def test_existing_inherited_parent_is_blocked_without_acl_or_file_changes(
    tmp_path: Path,
) -> None:
    from telegram_courses.windows_security import WindowsSecurityApi

    root_guard = _create_private_directory(tmp_path / "downloads")
    root = root_guard.path
    root_guard.close()
    parent = root / "Synthetic"
    parent.mkdir()
    marker = parent / "keep.bin"
    marker.write_bytes(b"preserve")
    api = WindowsSecurityApi()
    before = api.inspect_acl(parent)
    assert before[1] is False
    with pytest.raises(DownloadError) as error:
        _prepare_s9_download_directories(root, [_candidate()])
    assert error.value.category == "S9_PRIVATE_DOWNLOAD_DIRECTORY_UNAVAILABLE"
    assert api.inspect_acl(parent) == before
    assert marker.read_bytes() == b"preserve"


def test_private_partial_is_preserved_and_multiple_links_are_blocked(tmp_path: Path) -> None:
    root_guard = _create_private_directory(tmp_path / "downloads")
    root = root_guard.path
    root_guard.close()
    candidate = _candidate()
    guards = _prepare_s9_download_directories(root, [candidate])
    for guard in reversed(guards):
        guard.close()
    _, partial = destination_paths(root, candidate)
    partial.write_bytes(b"keep")
    guards = _prepare_s9_download_directories(root, [candidate])
    for guard in reversed(guards):
        guard.close()
    alias = root / "alias"
    os.link(partial, alias)
    with pytest.raises(DownloadError):
        _prepare_s9_download_directories(root, [candidate])
    assert partial.read_bytes() == alias.read_bytes() == b"keep"


def test_partial_with_unverified_acl_is_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import telegram_courses.s9_operational_ledger as ledger

    root_guard = _create_private_directory(tmp_path / "downloads")
    root = root_guard.path
    root_guard.close()
    candidate = _candidate()
    guards = _prepare_s9_download_directories(root, [candidate])
    for guard in reversed(guards):
        guard.close()
    _, partial = destination_paths(root, candidate)
    partial.write_bytes(b"keep")
    def reject_acl(path: Path) -> None:
        raise ledger.LedgerError("LEDGER_PRIVATE_FILE_UNVERIFIED")
    monkeypatch.setattr(ledger, "_verify_private_file", reject_acl)
    with pytest.raises(DownloadError):
        _prepare_s9_download_directories(root, [candidate])
    assert partial.read_bytes() == b"keep"
