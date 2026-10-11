from __future__ import annotations

from pathlib import Path

import pytest

from telegram_courses.download_repository import DownloadCandidate, _process_is_alive
from telegram_courses.downloads import (
    DownloadError,
    _finalize_no_overwrite,
    destination_paths,
    sanitize_component,
)


def candidate(lineage=(("track", "Track"), ("course", "Course"), ("lesson", "Lesson"))):
    return DownloadCandidate(5, -1001, 20, 0, "tg-media-1", 4, "CON: file?.pdf", lineage)


def test_sanitize_windows_reserved_names_and_prohibited_characters() -> None:
    assert sanitize_component("CON", "fallback") == "_CON"
    assert sanitize_component("lesson. ", "fallback") == "lesson"
    assert sanitize_component("A/B:C?.pdf", "fallback") == "A_B_C_.pdf"
    assert sanitize_component("...", "fallback") == "fallback"


def test_destination_has_catalog_lineage_stable_identity_and_sibling_part(tmp_path: Path) -> None:
    final, partial = destination_paths(tmp_path, candidate())
    assert final.parts[-4:-1] == ("Track", "Course", "Lesson")
    assert "[c-1001-m20-o0]" in final.name
    assert partial == final.with_name(final.name + ".part")
    assert partial.parent == final.parent


def test_destination_omits_missing_optional_lineage(tmp_path: Path) -> None:
    final, _ = destination_paths(tmp_path, candidate((("lesson", "Lesson"),)))
    assert final.parent == tmp_path / "Lesson"


def test_destination_collision_names_include_canonical_media_identity(tmp_path: Path) -> None:
    first, _ = destination_paths(tmp_path, candidate())
    second, _ = destination_paths(tmp_path, candidate())
    third, _ = destination_paths(
        tmp_path,
        DownloadCandidate(5, -1001, 21, 0, "tg-media-1", 4, "CON: file?.pdf", candidate().lineage),
    )
    assert first == second
    assert first != third


def test_destination_fails_when_absolute_path_exceeds_limit(tmp_path: Path) -> None:
    long_root = tmp_path / ("r" * 220)
    with pytest.raises(DownloadError, match="path too long"):
        destination_paths(long_root, candidate())


def test_windows_atomic_finalization_never_overwrites_existing_file(tmp_path: Path) -> None:
    partial = tmp_path / "lesson.part"
    final = tmp_path / "lesson.bin"
    partial.write_bytes(b"synthetic")
    _finalize_no_overwrite(partial, final)
    assert final.read_bytes() == b"synthetic"
    assert not partial.exists()

    other = tmp_path / "other.part"
    other.write_bytes(b"foreign")
    with pytest.raises(DownloadError, match="destination exists"):
        _finalize_no_overwrite(other, final)
    assert final.read_bytes() == b"synthetic"
    assert other.read_bytes() == b"foreign"


def test_process_lease_probe_is_read_only() -> None:
    import os

    assert _process_is_alive(os.getpid())
    assert not _process_is_alive(-1)


def test_cli_download_requires_explicit_complete_identity() -> None:
    from telegram_courses.cli import _parse_arguments
    from telegram_courses.config import ConfigurationError

    args = _parse_arguments([
        "download", "--channel-id", "-1001", "--telegram-message-id", "20",
        "--media-ordinal", "0", "--download-dir", "D:/Courses",
    ])
    assert (args.channel_id, args.telegram_message_id, args.media_ordinal) == (-1001, 20, 0)
    assert args.download_dir == "D:/Courses"
    with pytest.raises(ConfigurationError):
        _parse_arguments(["download", "--channel-id", "-1001"])
