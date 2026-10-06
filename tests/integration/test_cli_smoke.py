from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from telegram_courses import cli

RepoRoot = Path(__file__).resolve().parents[2]
VenvRoot = Path(sys.prefix).resolve()
PyS0 = VenvRoot / "Scripts" / "python.exe"
CliS0 = VenvRoot / "Scripts" / "telegram-courses.exe"


def _normalized(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _snapshot(root: Path) -> dict[str, tuple[object, ...]]:
    result: dict[str, tuple[object, ...]] = {}
    root_info = root.stat(follow_symlinks=False)
    root_attributes = int(getattr(root_info, "st_file_attributes", 0))
    if root_attributes & 0x400 or stat.S_ISLNK(root_info.st_mode):
        raise AssertionError("reparse point found in filesystem oracle root")
    root_created = datetime.fromtimestamp(
        root_info.st_ctime, timezone.utc
    ).isoformat()
    root_modified = datetime.fromtimestamp(
        root_info.st_mtime, timezone.utc
    ).isoformat()
    result["."] = ("directory", root_attributes, root_created, root_modified)
    pending = [root]
    while pending:
        directory = pending.pop()
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            path = Path(entry.path)
            info = entry.stat(follow_symlinks=False)
            attributes = int(getattr(info, "st_file_attributes", 0))
            is_reparse = bool(attributes & 0x400) or stat.S_ISLNK(info.st_mode)
            if is_reparse:
                raise AssertionError("reparse point found in filesystem oracle root")
            relative = path.relative_to(root).as_posix()
            created = datetime.fromtimestamp(info.st_ctime, timezone.utc).isoformat()
            modified = datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()
            if stat.S_ISDIR(info.st_mode):
                result[relative] = ("directory", attributes, created, modified)
                pending.append(path)
            elif stat.S_ISREG(info.st_mode):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                result[relative] = (
                    "file",
                    attributes,
                    created,
                    modified,
                    info.st_size,
                    digest,
                )
            else:
                result[relative] = ("other", attributes, created, modified)
    return result


def _assert_no_mutation(
    before_repo: dict[str, tuple[object, ...]],
    before_temp: dict[str, tuple[object, ...]],
    tmp_path: Path,
) -> None:
    after_repo = _snapshot(RepoRoot)
    after_temp = _snapshot(tmp_path)
    assert before_repo == after_repo
    assert before_temp == after_temp


def _invoke(
    executable: Path,
    arguments: list[str],
    *,
    cwd: Path,
    tmp_path: Path,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    before_repo = _snapshot(RepoRoot)
    before_temp = _snapshot(tmp_path)
    result = subprocess.run(
        [str(executable), *arguments],
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    _assert_no_mutation(before_repo, before_temp, tmp_path)
    return result


@pytest.fixture(scope="module", autouse=True)
def _require_s0_virtual_environment() -> None:
    expected = RepoRoot / Path(sys.prefix).name
    assert Path(sys.prefix).name in {".venv", ".venv-replay"}
    assert _normalized(VenvRoot) == _normalized(expected)
    assert _normalized(Path(sys.executable)) == _normalized(PyS0)
    assert PyS0.is_file()
    assert CliS0.is_file()


@pytest.fixture
def smoke_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "TELEGRAM_COURSES_CONFIG",
        "TELEGRAM_COURSES_LOG_LEVEL",
        "PYTHONPATH",
        "PYTHONHOME",
    ):
        environment.pop(name, None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _assert_success(
    result: subprocess.CompletedProcess[str], expected: str
) -> None:
    assert result.returncode == 0
    assert result.stdout == expected + "\n"
    assert result.stderr == ""


def _assert_configuration_error(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "configuration error\n"


def test_t10a_smoke_from_repository_root(
    tmp_path: Path, smoke_environment: dict[str, str]
) -> None:
    result = _invoke(
        CliS0,
        ["smoke"],
        cwd=RepoRoot,
        tmp_path=tmp_path,
        environment=smoke_environment,
    )
    _assert_success(result, "telegram-courses 0.1.0 config=file log_level=INFO")


def test_t10b_empty_cwd_uses_defaults_for_console_and_module(
    tmp_path: Path, smoke_environment: dict[str, str]
) -> None:
    smoke_cwd = tmp_path / "cwd"
    smoke_cwd.mkdir()
    assert list(smoke_cwd.iterdir()) == []
    for executable, arguments in (
        (CliS0, ["smoke"]),
        (PyS0, ["-B", "-m", "telegram_courses", "smoke"]),
    ):
        result = _invoke(
            executable,
            arguments,
            cwd=smoke_cwd,
            tmp_path=tmp_path,
            environment=smoke_environment,
        )
        _assert_success(result, "telegram-courses 0.1.0 config=defaults log_level=INFO")


def test_t10c_cli_overrides_environment_and_file(
    tmp_path: Path, smoke_environment: dict[str, str]
) -> None:
    fixture = tmp_path / "warning.toml"
    fixture.write_text('[logging]\nlevel = "WARNING"\n', encoding="utf-8")
    environment = smoke_environment | {"TELEGRAM_COURSES_LOG_LEVEL": "ERROR"}
    result = _invoke(
        CliS0,
        ["smoke", "--config", str(fixture), "--log-level", "DEBUG"],
        cwd=RepoRoot,
        tmp_path=tmp_path,
        environment=environment,
    )
    _assert_success(result, "telegram-courses 0.1.0 config=file log_level=DEBUG")


@pytest.mark.parametrize(
    "contents",
    [
        None,
        "[logging\n",
        '[logging]\nlevel = "INFO"\n',
        "[telegram]\napi_hash = 'x'\n",
    ],
)
def test_t10d_invalid_config_has_generic_error(
    contents: str | None, tmp_path: Path, smoke_environment: dict[str, str]
) -> None:
    fixture = tmp_path / "invalid.toml"
    if contents is not None:
        fixture.write_text(contents, encoding="utf-8")
    result = _invoke(
        CliS0,
        ["smoke", "--config", str(fixture)],
        cwd=RepoRoot,
        tmp_path=tmp_path,
        environment=smoke_environment,
    )
    _assert_configuration_error(result)


def test_t09_configuration_matrix_runs_through_cli(
    tmp_path: Path, smoke_environment: dict[str, str]
) -> None:
    cases = (
        ("", "file", "INFO"),
        ("# s0 fixture\n", "file", "INFO"),
        ("[logging]\n", "file", "INFO"),
        ('[logging]\nlevel = "WARNING"\n', "file", "WARNING"),
    )
    for index, (contents, indicator, level) in enumerate(cases):
        fixture = tmp_path / f"matrix-{index}.toml"
        fixture.write_text(contents, encoding="utf-8")
        for use_environment in (False, True):
            environment = smoke_environment.copy()
            arguments = ["smoke"]
            if use_environment:
                environment["TELEGRAM_COURSES_CONFIG"] = str(fixture)
            else:
                arguments.extend(("--config", str(fixture)))
            result = _invoke(
                CliS0,
                arguments,
                cwd=RepoRoot,
                tmp_path=tmp_path,
                environment=environment,
            )
            _assert_success(
                result,
                f"telegram-courses 0.1.0 config={indicator} log_level={level}",
            )


def test_t10e_internal_error_is_generic_and_has_no_side_effects(
    tmp_path: Path,
) -> None:
    before_repo = _snapshot(RepoRoot)
    before_temp = _snapshot(tmp_path)
    with patch.object(cli, "load_configuration", side_effect=RuntimeError("secret")):
        with patch("sys.stdout") as stdout, patch("sys.stderr") as stderr:
            result = cli.main(["smoke"])
    _assert_no_mutation(before_repo, before_temp, tmp_path)
    assert result == 1
    stdout.write.assert_not_called()
    stderr.write.assert_called_once_with("internal error\n")
