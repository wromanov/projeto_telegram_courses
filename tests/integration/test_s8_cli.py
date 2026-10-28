from __future__ import annotations

import ast
from pathlib import Path

from telegram_courses import cli


def test_s8_cli_smoke_uses_explicit_configuration(tmp_path, monkeypatch, capsys) -> None:
    config = tmp_path / "settings.toml"
    config.write_text('[logging]\nlevel = "WARNING"\n', encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_COURSES_LOG_LEVEL", "ERROR")
    assert cli.main(["smoke", "--config", str(config), "--log-level", "DEBUG"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "telegram-courses 0.1.0 config=file log_level=DEBUG\n"
    assert captured.err == ""


def test_s8_download_cli_does_not_report_completion_for_partial_queue() -> None:
    source = Path(cli.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    batch = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_download_batch"
    )
    rendered = ast.get_source_segment(source, batch) or ""
    assert 'if result.cancelled:' in rendered
    assert 'final_status = "CANCELLED"' in rendered
    assert 'elif failed_count:' in rendered
    assert 'final_status = "PARTIAL" if completed_count or counts["ALREADY_VALID"] else "FAILED"' in rendered
    assert 'elif completed_count:' in rendered
    assert 'final_status = "COMPLETED"' in rendered
