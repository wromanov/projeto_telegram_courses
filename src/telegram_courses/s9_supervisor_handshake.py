"""Private fail-closed handshake for supervised S9 queue confirmation."""

from __future__ import annotations

import builtins
import os
import re
import stat
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TextIO

from telegram_courses.s9_operational_ledger import (
    LedgerError,
    _open_private_directory_guard,
    _verify_private_file,
)

HANDSHAKE_DIR_ENV = "TELEGRAM_COURSES_S9_HANDSHAKE_DIR"
HANDSHAKE_NONCE_ENV = "TELEGRAM_COURSES_S9_HANDSHAKE_NONCE"
S9_LEDGER_PATH_ENV = "TELEGRAM_COURSES_S9_LEDGER_PATH"
S9_PROFILE_ENV = "TELEGRAM_COURSES_S9_PROFILE"
S9_SUPERVISED_CHILD_ENV = "TELEGRAM_COURSES_S9_SUPERVISED_CHILD"
READY_MARKER = "preconfirmation.ready"
CONTINUE_MARKER = "preconfirmation.continue"
HANDSHAKE_TIMEOUT_SECONDS = 15.0
_NONCE_PATTERN = re.compile(r"[0-9a-f]{64}\n\Z")


class ConfirmationHandshakeError(RuntimeError):
    """Raised when supervised confirmation cannot be established safely."""


def _regular_file_with_contents(path: Path, expected: bytes) -> bool:
    try:
        info = path.lstat()
        attributes = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attributes & 0x400:
            return False
        if not stat.S_ISREG(info.st_mode):
            return False
        _verify_private_file(path)
        return path.read_bytes() == expected
    except LedgerError:
        return False
    except OSError:
        return False


def _marker_exists(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or attributes & 0x400
    ):
        raise ConfirmationHandshakeError("unsafe handshake marker")
    _verify_private_file(path)
    return True


def _create_marker(path: Path, payload: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    flags |= getattr(os, "O_NOFOLLOW", 0)
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        _verify_private_file(path)
    finally:
        os.close(descriptor)


def confirmation_callbacks(
    handshake_dir: Path, nonce: str
) -> tuple[Callable[[], bool], Callable[[], None]]:
    """Return supervisor callbacks for a child-created prompt-ready marker."""
    if not isinstance(nonce, str) or re.fullmatch(r"[0-9a-f]{64}", nonce) is None:
        raise ConfirmationHandshakeError("invalid handshake nonce")
    if not Path(handshake_dir).is_absolute():
        raise ConfirmationHandshakeError("handshake directory must be absolute")
    try:
        guard = _open_private_directory_guard(handshake_dir)
    except LedgerError as error:
        raise ConfirmationHandshakeError("private handshake directory unavailable") from error
    directory = guard.path

    ready_path = directory / READY_MARKER
    continue_path = directory / CONTINUE_MARKER
    expected = f"{nonce}\n".encode("ascii")

    def ready() -> bool:
        try:
            guard.verify(directory)
            return _regular_file_with_contents(ready_path, expected)
        except LedgerError:
            return False

    def release() -> None:
        guard.verify(directory)
        if not ready():
            raise ConfirmationHandshakeError("prompt-ready marker not verified")
        _create_marker(continue_path, expected)

    return ready, release


def supervised_confirmation(
    prompt: str,
    *,
    selection_prompt: Callable[[str], str],
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    environment: Mapping[str, str] | None = None,
    timeout_seconds: float = HANDSHAKE_TIMEOUT_SECONDS,
) -> str:
    """Show a real TTY prompt, wait for supervisor approval, then read input.

    When the private supervisor environment is absent, preserve the existing
    CLI prompt behavior. In supervised mode the prompt is visible while the
    parent collects the required two-second process-memory baseline. No answer
    is consumed until the parent creates the matching continuation marker.
    """
    env = os.environ if environment is None else environment
    directory_text = env.get(HANDSHAKE_DIR_ENV)
    if directory_text is None:
        return selection_prompt(prompt)

    input_stream = sys.stdin if stdin is None else stdin
    output_stream = sys.stdout if stdout is None else stdout
    nonce = env.get(HANDSHAKE_NONCE_ENV, "")
    handshake_dir = Path(directory_text)
    if (
        selection_prompt is not builtins.input
        or not input_stream.isatty()
        or not output_stream.isatty()
        or not handshake_dir.is_absolute()
        or re.fullmatch(r"[0-9a-f]{64}", nonce) is None
        or not isinstance(timeout_seconds, (int, float))
        or isinstance(timeout_seconds, bool)
        or timeout_seconds <= 0
    ):
        raise ConfirmationHandshakeError("supervised confirmation unavailable")

    try:
        guard = _open_private_directory_guard(handshake_dir)
        resolved = guard.path
        ready_path = resolved / READY_MARKER
        continue_path = resolved / CONTINUE_MARKER
        if _marker_exists(ready_path) or _marker_exists(continue_path):
            raise ConfirmationHandshakeError("stale handshake marker")
        output_stream.write(prompt)
        output_stream.flush()
        expected = f"{nonce}\n".encode("ascii")
        _create_marker(ready_path, expected)
        deadline = time.monotonic() + float(timeout_seconds)
        while time.monotonic() < deadline:
            guard.verify(resolved)
            if _marker_exists(continue_path):
                if not _regular_file_with_contents(continue_path, expected):
                    raise ConfirmationHandshakeError("invalid continuation marker")
                return selection_prompt()
            time.sleep(0.025)
    except ConfirmationHandshakeError:
        raise
    except LedgerError as error:
        raise ConfirmationHandshakeError("private handshake directory unavailable") from error
    except OSError as error:
        raise ConfirmationHandshakeError("confirmation handshake failed") from error
    finally:
        if "guard" in locals():
            guard.close()
    raise ConfirmationHandshakeError("supervisor did not release confirmation")
