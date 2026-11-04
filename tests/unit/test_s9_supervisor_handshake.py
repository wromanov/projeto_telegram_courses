from __future__ import annotations

import builtins
import io
import threading
import time
from pathlib import Path

import pytest

from telegram_courses.s9_operational_ledger import (
    LedgerError,
    _create_private_directory,
)
from telegram_courses.s9_supervisor_handshake import (
    CONTINUE_MARKER,
    HANDSHAKE_DIR_ENV,
    HANDSHAKE_NONCE_ENV,
    READY_MARKER,
    ConfirmationHandshakeError,
    confirmation_callbacks,
    supervised_confirmation,
)


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def _private_handshake_directory(tmp_path: Path) -> Path:
    guard = _create_private_directory(tmp_path / "private-handshake")
    path = guard.path
    guard.close()
    return path


def test_without_supervisor_preserves_existing_prompt() -> None:
    prompts: list[str] = []

    def prompt(value: str) -> str:
        prompts.append(value)
        return "n"

    result = supervised_confirmation(
        "Confirmar? ", selection_prompt=prompt, environment={}
    )

    assert result == "n"
    assert prompts == ["Confirmar? "]


def test_supervised_confirmation_waits_for_verified_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _private_handshake_directory(tmp_path)
    nonce = "ab" * 32
    env = {
        HANDSHAKE_DIR_ENV: str(directory),
        HANDSHAKE_NONCE_ENV: nonce,
    }
    is_ready, release = confirmation_callbacks(directory, nonce)
    input_calls: list[tuple[object, ...]] = []

    def input_fn(*args: object) -> str:
        input_calls.append(args)
        return "s"

    monkeypatch.setattr(builtins, "input", input_fn)
    result: list[str] = []
    failures: list[BaseException] = []

    def run_prompt() -> None:
        try:
            result.append(
                supervised_confirmation(
                    "Iniciar? ",
                    selection_prompt=builtins.input,
                    stdin=_Terminal(),
                    stdout=_Terminal(),
                    environment=env,
                )
            )
        except BaseException as error:  # surfaced in the parent test thread
            failures.append(error)

    child = threading.Thread(target=run_prompt)
    child.start()
    deadline = time.monotonic() + 2
    while not is_ready() and time.monotonic() < deadline:
        time.sleep(0.005)

    assert is_ready()
    assert not (directory / CONTINUE_MARKER).exists()
    release()
    child.join(timeout=2)

    assert not child.is_alive()
    assert failures == []
    assert result == ["s"]
    assert input_calls == [()]
    assert (directory / READY_MARKER).read_text(encoding="ascii") == f"{nonce}\n"
    assert (directory / CONTINUE_MARKER).read_text(encoding="ascii") == f"{nonce}\n"


def test_supervised_confirmation_requires_a_tty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _private_handshake_directory(tmp_path)
    nonce = "cd" * 32
    monkeypatch.setattr(builtins, "input", lambda *args: "s")
    with pytest.raises(ConfirmationHandshakeError):
        supervised_confirmation(
            "Iniciar? ",
            selection_prompt=builtins.input,
            stdin=io.StringIO(),
            stdout=_Terminal(),
            environment={
            HANDSHAKE_DIR_ENV: str(directory),
                HANDSHAKE_NONCE_ENV: nonce,
            },
        )
    assert not (directory / READY_MARKER).exists()


def test_supervisor_callbacks_require_matching_nonce_and_ready_marker(
    tmp_path: Path,
) -> None:
    directory = _private_handshake_directory(tmp_path)
    nonce = "ef" * 32
    _ready, release = confirmation_callbacks(directory, nonce)

    with pytest.raises(ConfirmationHandshakeError):
        release()

    (directory / READY_MARKER).write_text("wrong\n", encoding="ascii")
    ready, release = confirmation_callbacks(directory, nonce)
    assert not ready()
    with pytest.raises(ConfirmationHandshakeError):
        release()
    with pytest.raises(ConfirmationHandshakeError):
        confirmation_callbacks(tmp_path, "not-a-nonce")


def test_supervised_confirmation_times_out_without_reading_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _private_handshake_directory(tmp_path)
    nonce = "12" * 32
    monkeypatch.setattr(builtins, "input", lambda *args: pytest.fail("input was read"))

    with pytest.raises(ConfirmationHandshakeError, match="did not release"):
        supervised_confirmation(
            "Iniciar? ",
            selection_prompt=builtins.input,
            stdin=_Terminal(),
            stdout=_Terminal(),
            environment={
                HANDSHAKE_DIR_ENV: str(directory),
                HANDSHAKE_NONCE_ENV: nonce,
            },
            timeout_seconds=0.02,
        )
    assert (directory / READY_MARKER).exists()
    assert not (directory / CONTINUE_MARKER).exists()


def test_handshake_rejects_shared_or_unknown_directory_acl(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    with pytest.raises(ConfirmationHandshakeError, match="private handshake"):
        confirmation_callbacks(shared, "ab" * 32)


def test_marker_acl_validation_failure_is_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _private_handshake_directory(tmp_path)
    marker = directory / READY_MARKER
    monkeypatch.setattr(
        "telegram_courses.s9_supervisor_handshake._verify_private_file",
        lambda _path: (_ for _ in ()).throw(LedgerError("ACL_UNKNOWN")),
    )
    with pytest.raises(LedgerError, match="ACL_UNKNOWN"):
        from telegram_courses.s9_supervisor_handshake import _create_marker

        _create_marker(marker, b"a" * 64 + b"\n")
    assert marker.exists()
