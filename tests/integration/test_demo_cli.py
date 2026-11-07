from __future__ import annotations

import os
import subprocess
import sys

import pytest

from telegram_courses.demo_cli import _open_workspace
from telegram_courses.downloads import DownloadError


def test_public_demo_reopens_and_deduplicates(tmp_path):
    workspace = tmp_path / "demo-workspace"
    command = [sys.executable, "-m", "telegram_courses.cli", "demo", "--workspace", str(workspace)]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    answers = "1\n1\nT\nV\nP\ns\ns\nQ\nQ\nQ\n"
    first = subprocess.run(command, input=answers, text=True, encoding="utf-8", capture_output=True, env=env, timeout=90)
    assert first.returncode == 0, first.stderr
    assert "CONCLUIDO" in first.stdout
    assert (workspace / ".telegram-courses-demo").is_file()
    assert len(list((workspace / "downloads").rglob("*.part"))) == 0
    second = subprocess.run(command, input=answers, text=True, encoding="utf-8", capture_output=True, env=env, timeout=90)
    assert second.returncode == 0, second.stderr
    assert "TODOS_JA_VALIDOS" in second.stdout


def test_demo_rejects_existing_unmarked_directory(tmp_path):
    existing = tmp_path / "unmarked"
    existing.mkdir()
    file = existing / "keep.txt"
    file.write_text("preserve", encoding="utf-8")
    with pytest.raises(DownloadError):
        _open_workspace(str(existing))
    assert file.read_text(encoding="utf-8") == "preserve"
    assert list(existing.iterdir()) == [file]


def test_demo_rejects_operational_directory_name(tmp_path):
    with pytest.raises(DownloadError):
        _open_workspace(str(tmp_path / "data" / "demo"))


def test_demo_rejects_parent_traversal(tmp_path):
    with pytest.raises(DownloadError):
        _open_workspace(str(tmp_path / "other" / ".." / "demo"))


def test_demo_revokes_binding_if_marker_disappears(tmp_path):
    sandbox = _open_workspace(str(tmp_path / "marked-demo"))
    (sandbox.root / ".telegram-courses-demo").unlink()
    with pytest.raises(DownloadError):
        sandbox._validate_binding(None)
