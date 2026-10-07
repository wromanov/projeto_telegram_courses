from __future__ import annotations

import ctypes
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegram_courses import telethon_session as sessions
from telegram_courses.config import ConfigurationError


class _TestProtector:
    """Reversible test double; never used by production code."""

    def protect(self, value: bytes) -> bytes:
        return bytes(byte ^ 0xA5 for byte in value)

    def unprotect(self, value: bytes) -> bytes:
        return bytes(byte ^ 0xA5 for byte in value)


class _FakeCrypt32:
    def __init__(self) -> None:
        self.flags: list[int] = []
        self.buffers: list[ctypes.Array[ctypes.c_char]] = []

    def _transform(
        self,
        input_blob: object,
        flags: int,
        output_blob: object,
    ) -> int:
        self.flags.append(flags)
        input_value = ctypes.cast(
            input_blob, ctypes.POINTER(sessions._DataBlob)
        ).contents
        source = ctypes.string_at(input_value.pbData, input_value.cbData)
        transformed = bytes(byte ^ 0xA5 for byte in source)
        buffer = ctypes.create_string_buffer(transformed, len(transformed))
        self.buffers.append(buffer)
        output_value = ctypes.cast(
            output_blob, ctypes.POINTER(sessions._DataBlob)
        ).contents
        output_value.cbData = len(transformed)
        output_value.pbData = ctypes.cast(
            buffer, ctypes.POINTER(ctypes.c_ubyte)
        )
        return 1

    def CryptProtectData(
        self,
        input_blob: object,
        _description: object,
        _entropy: object,
        _reserved: object,
        _prompt: object,
        flags: int,
        output_blob: object,
    ) -> int:
        return self._transform(input_blob, flags, output_blob)

    def CryptUnprotectData(
        self,
        input_blob: object,
        _description: object,
        _entropy: object,
        _reserved: object,
        _prompt: object,
        flags: int,
        output_blob: object,
    ) -> int:
        return self._transform(input_blob, flags, output_blob)


def _test_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sessions._ProtectedSessionVault:
    local_app_data = tmp_path / "local-app-data"
    local_app_data.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    return sessions._ProtectedSessionVault(_protector=_TestProtector())


def test_dpapi_wrapper_uses_current_user_flags_with_fake_api() -> None:
    api = object.__new__(sessions._WindowsApi)
    crypt32 = _FakeCrypt32()
    api.crypt32 = crypt32
    api.kernel32 = SimpleNamespace(LocalFree=lambda _pointer: None)

    protected = api.protect(b"synthetic-session")
    restored = api.unprotect(protected)

    assert restored == b"synthetic-session"
    assert crypt32.flags == [sessions._CRYPTPROTECT_UI_FORBIDDEN] * 2
    assert sessions._CRYPTPROTECT_UI_FORBIDDEN == 0x1


def test_dpapi_output_is_freed_when_protection_fails() -> None:
    class _FailingCrypt32(_FakeCrypt32):
        def _transform(
            self,
            input_blob: object,
            flags: int,
            output_blob: object,
        ) -> int:
            super()._transform(input_blob, flags, output_blob)
            return 0

    api = object.__new__(sessions._WindowsApi)
    crypt32 = _FailingCrypt32()
    freed: list[object] = []
    api.crypt32 = crypt32
    api.kernel32 = SimpleNamespace(
        LocalFree=lambda pointer: freed.append(pointer) and None
    )

    with pytest.raises(sessions.StorageError):
        api.protect(b"synthetic-failure-session")

    assert len(freed) == 1


def test_non_windows_guard_precedes_dll_and_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sessions.sys, "platform", "linux")
    monkeypatch.setattr(
        sessions,
        "_WindowsApi",
        lambda: pytest.fail("Windows API loaded before platform guard"),
    )

    with pytest.raises(ConfigurationError):
        sessions._ProtectedSessionVault()


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows ACLs")
def test_save_load_format_missing_and_explicit_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _test_vault(tmp_path, monkeypatch)
    assert vault._load() is None
    assert vault.delete_local() is False

    plaintext = "synthetic-session-marker-7c9e"
    vault._save(plaintext)
    artifact = vault._path.read_bytes()
    assert artifact.startswith(b"TCS\x01")
    assert plaintext.encode() not in artifact
    assert vault._load() == plaintext

    assert vault.delete_local() is True
    assert vault.delete_local() is False
    assert vault._load() is None


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows ACLs")
def test_invalid_envelope_utf8_and_empty_input_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _test_vault(tmp_path, monkeypatch)
    with pytest.raises(ConfigurationError):
        vault._save("")

    vault._save("synthetic-session")
    for invalid in (b"", b"TCS", b"BAD\x01protected", b"TCS\x02protected"):
        vault._path.write_bytes(invalid)
        with pytest.raises(sessions.IntegrityError):
            vault._load()

    vault._path.write_bytes(b"TCS\x01" + _TestProtector().protect(b"\xff"))
    with pytest.raises(sessions.IntegrityError):
        vault._load()


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows ACLs")
def test_failed_replace_preserves_previous_blob_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _test_vault(tmp_path, monkeypatch)
    vault._save("synthetic-old-session")
    old_artifact = vault._path.read_bytes()

    def fail_replace(_source: object, _destination: object) -> None:
        raise OSError("synthetic replacement failure")

    monkeypatch.setattr(sessions.os, "replace", fail_replace)
    with pytest.raises(sessions.StorageError):
        vault._save("synthetic-new-session")

    assert vault._path.read_bytes() == old_artifact
    assert list(vault._path.parent.glob(".session-*.tmp")) == []


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows ACLs")
def test_repeated_saves_create_no_backup_export_or_secret_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    vault = _test_vault(tmp_path, monkeypatch)
    secret = "synthetic-session-log-sentinel-128f"
    with caplog.at_level(logging.DEBUG):
        vault._save(secret)
        vault._save("synthetic-session-replacement")
        vault._load()

    assert len(list(vault._path.parent.iterdir())) == 1
    assert [entry.name for entry in vault._path.parent.iterdir()] == [
        "session.dpapi"
    ]
    assert secret not in caplog.text
    assert vault._path.read_bytes().hex() not in caplog.text

    class _SecretFailureProtector:
        def protect(self, value: bytes) -> bytes:
            raise RuntimeError(value.decode("utf-8"))

        def unprotect(self, value: bytes) -> bytes:
            raise RuntimeError(value.decode("utf-8"))

    vault._protector = _SecretFailureProtector()
    with caplog.at_level(logging.DEBUG), pytest.raises(
        sessions.StorageError
    ) as error:
        vault._save(secret)

    assert secret not in str(error.value)
    assert secret not in caplog.text


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows ACLs")
def test_repository_local_app_data_path_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("LOCALAPPDATA", str(repository))

    with pytest.raises(ConfigurationError):
        sessions._ProtectedSessionVault(_protector=_TestProtector())
