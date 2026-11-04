"""Durable, isolated S9 accounting. This module never performs Telegram I/O.

An operation must be reserved *before* it starts. Unsettled reservations stay
charged on restart; the caller must never infer transferred bytes from files.
The ledger is a building block, not authorization to execute a real run.
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
import stat
import threading
import time
import uuid
import weakref
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Mapping

from telegram_courses.windows_security import WindowsSecurityApi

MIB = 1024 * 1024
GIB = 1024 * MIB
CHUNK = 256 * 1024
F_CAP = 512 * MIB
M_MAX_CAP = 2 * GIB + CHUNK
TOTAL_CAP = F_CAP + M_MAX_CAP
DISK_RESERVE = 256 * MIB
S9_MEASUREMENT_SOURCE_ENV = "TELEGRAM_COURSES_S9_MEASUREMENT_SOURCE"
S9_OPERATIONAL_GATE_ENV = "TELEGRAM_COURSES_S9_OPERATIONAL_GATE"
_MAGIC = "telegram-s9-operational-ledger-v2"
_ALIAS = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[0-9a-f]{32}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_AUDIT_ZERO_HASH = "0" * 64
_TERMINAL = {"COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "BLOCKED"}
_AUDIT_EVENT_TYPES = {
    "LEDGER_CREATED", "RUN_DEADLINE_STARTED", "MEDIA_REGISTERED",
    "SCAN_RESERVED", "SCAN_OBSERVED", "ATTEMPT_STARTED",
    "INTERRUPTION_RECORDED", "BYTES_RESERVED", "BYTES_SETTLED",
    "DISK_CHECKED", "GATE_STATE_UPDATED", "RUN_TERMINAL",
    "RUN_INITIALIZED", "PREFLIGHT_CONFIRMED", "CHILD_PROCESS_CONFIRMED",
    "GATE_STARTED", "GATE_FINISHED", "PROCESS_TIMEOUT", "RUN_CANCELLED",
    "PROCESS_CONTAINMENT", "SECURITY_BLOCK", "RECEIPT_PREPARED",
    "RECEIPT_PERSISTED",
    "SUPERVISOR_RUN_FINISHED",
    "G0_CONFIRMATION_REQUESTED", "G0_CONFIRMATION_CONSUMED",
    "G0_CONFIRMATION_BLOCKED", "G8_DATABASE_BASELINE",
}
_AUDIT_DETAIL_KEYS = {
    "alias", "amount_bytes", "attempt", "available_bytes", "available_origin",
    "cause", "check_id", "checked_ns", "deadline_ns", "elapsed_ms",
    "event_count", "expected_bytes", "extra_bytes", "exit_code", "fresh",
    "evidence_kind", "evidence_origin", "gate", "identity_alias", "incremental",
    "kind", "margin_bytes", "margin_origin",
    "limit_check_result", "measurement_source", "media_count", "observed_bytes",
    "max_messages", "observed_messages", "pending_bytes", "pid",
    "process_creation_time", "process_state",
    "profile", "receipt_sha256", "recovery", "result", "offline_result",
    "real_evidence_status",
    "reservation_id", "scan_id", "seconds", "stage", "status",
    "tree_confirmed", "unknown_bytes", "window_size", "working_set_bytes",
    "peak_working_set_bytes", "private_bytes",
    "channel_ref", "manifest_sha256", "scope_sha256", "nonce_sha256",
    "part_bytes", "database_sha256_before", "database_sha256_after",
    "g7_receipt_sha256", "g6_receipt_sha256", "predecessor_receipts_sha256",
    "database_file", "download_root",
    "confirmation_source", "issued_ns", "expires_ns", "consumed_ns", "reason",
}
_AUDIT_ENUM_FIELDS = {
    "status": {"CREATED", "PLANNED", "RUNNING", "COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "BLOCKED", "UNKNOWN", "MEASURED"},
    "cause": {"NONE", "TIMEOUT", "DEADLINE", "MEMORY", "DISK", "FLOODWAIT", "CANCELLED", "LEDGER", "PROCESS", "OTHER"},
    "process_state": {"UNKNOWN", "RUNNING", "EXITED", "CONTAINED", "UNCONTAINED"},
    "result": {
        "UNKNOWN", "PASS", "FAIL", "PARTIAL", "BLOCKED", "COMPLETED",
        "FAILED", "CANCELLED", "TIMED_OUT", "OFFLINE_SYNTHETIC_PASS",
        "REAL_CONTRACTUAL_PASS", "REAL_EVIDENCE_PENDING",
    },
    "evidence_origin": {"SYNTHETIC", "OFFLINE_SYNTHETIC", "REAL_CONTRACTUAL", "HUMAN_INTERACTIVE", "UNKNOWN"},
    "offline_result": {"UNKNOWN", "PASS", "PARTIAL", "FAIL", "BLOCKED", "OFFLINE_SYNTHETIC_PASS"},
    "real_evidence_status": {
        "NOT_ASSESSED", "REAL_EVIDENCE_PENDING", "REAL_CONTRACTUAL_PASS",
    },
    "profile": {"F", "M"},
    "kind": {"DOCUMENT"},
    "gate": {f"G{i}" for i in range(10)},
    "stage": {"discovery", "scan", "catalog", "inspection", "queue_f", "queue_m", "verification_local", "g8-interruption", "g8-recovery", "unknown"},
    "limit_check_result": {"PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"},
    "measurement_source": {"GATEWAY_RESPONSE", "SYNTHETIC_TEST", "UNKNOWN"},
    "available_origin": {"MEASURED", "UNKNOWN"},
    "margin_origin": {"DERIVED"},
    "evidence_kind": {"S6_V1_PREFIX_PROOF"},
}


class LedgerError(RuntimeError):
    """A ledger or budget failure: the caller must stop the operation."""


_FILE_ATTRIBUTE_DIRECTORY = 0x10
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_FILE_READ_ATTRIBUTES = 0x80
_FILE_LIST_DIRECTORY = 0x01
_FILE_SHARE_READ = 0x1
_FILE_SHARE_WRITE = 0x2
_OPEN_EXISTING = 3
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
_FILE_ALL_ACCESS = 0x001F01FF
_OBJECT_INHERIT_ACE = 0x01
_CONTAINER_INHERIT_ACE = 0x02
_INHERITED_ACE = 0x10
_ACCESS_ALLOWED_ACE_TYPE = 0x00
_SYSTEM_SID = "S-1-5-18"
_ADMINISTRATORS_SID = "S-1-5-32-544"
_DRIVE_REMOTE = 4


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.DWORD),
        ("security_descriptor", ctypes.c_void_p),
        ("inherit_handle", wintypes.BOOL),
    ]


class _FileAttributeTagInfo(ctypes.Structure):
    _fields_ = [("file_attributes", wintypes.DWORD), ("reparse_tag", wintypes.DWORD)]


class _PrivateDirectoryGuard:
    """Pin a validated private directory while path based APIs use its files.

    On Windows the handle deliberately omits FILE_SHARE_DELETE, preventing a
    different process from renaming or replacing the directory while the
    ledger is open. SQLite still opens its files by path; ACL isolation and the
    held directory handle are the supported boundary, not a same-account
    adversary boundary.
    """

    def __init__(
        self,
        path: Path,
        *,
        handle: ctypes.c_void_p | None = None,
        descriptor: int | None = None,
        api: object | None = None,
    ) -> None:
        self.path = path
        self._handle = handle
        self._descriptor = descriptor
        self._api = api

    def close(self) -> None:
        if self._handle is not None:
            try:
                self._api.kernel32.CloseHandle(self._handle)  # type: ignore[attr-defined]
            finally:
                self._handle = None
        if self._descriptor is not None:
            os.close(self._descriptor)
            self._descriptor = None

    def __enter__(self) -> _PrivateDirectoryGuard:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def verify(self, expected_path: Path) -> None:
        expected = Path(expected_path).absolute()
        if (os.name == "nt" and self._handle is None) or (
            os.name != "nt" and self._descriptor is None
        ):
            raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")
        if os.path.normcase(str(expected)) != os.path.normcase(str(self.path)):
            raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")
        if os.name == "nt":
            _verify_windows_guard_path(self.path, self._handle, self._api)
            _verify_windows_private_directory(self.path, self._api)
        else:
            _verify_posix_private_directory(self.path, self._descriptor)


def _windows_api() -> object:
    try:
        return WindowsSecurityApi()
    except Exception as error:
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED") from error


def _verify_windows_guard_path(path: Path, handle: ctypes.c_void_p, api: object | None) -> None:
    if api is None:
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")
    get_final = api.kernel32.GetFinalPathNameByHandleW  # type: ignore[attr-defined]
    get_final.restype = wintypes.DWORD
    get_final.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_final(handle, buffer, len(buffer), 0)
    if not length or length >= len(buffer):
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")
    final_path = buffer.value
    if final_path.startswith("\\\\?\\"):
        final_path = final_path[4:]
    if os.path.normcase(final_path) != os.path.normcase(str(path)):
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")


def _verify_windows_private_directory(path: Path, api: object | None) -> None:
    if api is None:
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")
    try:
        attributes = api.attributes(path)  # type: ignore[attr-defined]
        sid = api.current_user_sid()  # type: ignore[attr-defined]
        owner, protected, entries = api.inspect_acl(path)  # type: ignore[attr-defined]
    except Exception as error:
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED") from error
    expected = {
        (_ACCESS_ALLOWED_ACE_TYPE, _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE,
         _FILE_ALL_ACCESS, sid),
        (_ACCESS_ALLOWED_ACE_TYPE, _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE,
         _FILE_ALL_ACCESS, _SYSTEM_SID),
        (_ACCESS_ALLOWED_ACE_TYPE, _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE,
         _FILE_ALL_ACCESS, _ADMINISTRATORS_SID),
    }
    if (
        attributes is None
        or attributes & _FILE_ATTRIBUTE_REPARSE_POINT
        or not attributes & _FILE_ATTRIBUTE_DIRECTORY
        or owner != sid
        or not protected
        or len(entries) != len(expected)
        or set(entries) != expected
    ):
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")


def _verify_posix_private_directory(path: Path, descriptor: int | None = None) -> None:
    try:
        info = os.fstat(descriptor) if descriptor is not None else path.stat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")
    except OSError as error:
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED") from error


def _open_private_directory_guard(path: str | Path) -> _PrivateDirectoryGuard:
    """Validate an existing private directory and pin it against replacement."""
    target = Path(path).absolute()
    try:
        info = os.lstat(target)
    except OSError as error:
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED") from error
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")

    if os.name == "nt":
        api = _windows_api()
        if not target.drive or api.drive_type(Path(target.anchor)) == _DRIVE_REMOTE:  # type: ignore[attr-defined]
            raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")
        kernel32 = api.kernel32  # type: ignore[attr-defined]
        kernel32.CreateFileW.restype = ctypes.c_void_p
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        ]
        # Attribute-only opens do not participate in normal sharing checks.
        # Listing access makes the missing FILE_SHARE_DELETE effective.
        handle = kernel32.CreateFileW(
            str(target), _FILE_READ_ATTRIBUTES | _FILE_LIST_DIRECTORY,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE, None, _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT, None,
        )
        invalid = ctypes.c_void_p(-1).value
        if handle is None or handle == invalid:
            raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")
        guard = _PrivateDirectoryGuard(target, handle=ctypes.c_void_p(handle), api=api)
        try:
            kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
            kernel32.GetFileInformationByHandleEx.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
            ]
            attributes = _FileAttributeTagInfo()
            if not kernel32.GetFileInformationByHandleEx(
                guard._handle, _FILE_ATTRIBUTE_TAG_INFO_CLASS,
                ctypes.byref(attributes), ctypes.sizeof(attributes),
            ):
                raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")
            if (
                attributes.file_attributes & _FILE_ATTRIBUTE_REPARSE_POINT
                or not attributes.file_attributes & _FILE_ATTRIBUTE_DIRECTORY
            ):
                raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")
            guard.verify(target)
            return guard
        except BaseException:
            guard.close()
            raise

    try:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags)
        guard = _PrivateDirectoryGuard(target, descriptor=descriptor)
        _verify_posix_private_directory(target, descriptor)
        return guard
    except (LedgerError, OSError):
        if "guard" in locals():
            guard.close()
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED") from None


def _create_private_directory(path: str | Path) -> _PrivateDirectoryGuard:
    """Create a new private directory with an explicit Windows DACL."""
    target = Path(path).absolute()
    if os.path.lexists(target) or not target.parent.is_dir():
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_CREATE_FAILED")
    for candidate in (target.parent, *target.parent.parents):
        try:
            info = os.lstat(candidate)
        except OSError as error:
            raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED") from error
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")

    if os.name == "nt":
        api = _windows_api()
        if not target.drive or api.drive_type(Path(target.anchor)) == _DRIVE_REMOTE:  # type: ignore[attr-defined]
            raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")
        sid = api.current_user_sid()  # type: ignore[attr-defined]
        sddl = f"D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;{_SYSTEM_SID})(A;OICI;FA;;;{_ADMINISTRATORS_SID})"
        advapi32 = api.advapi32  # type: ignore[attr-defined]
        kernel32 = api.kernel32  # type: ignore[attr-defined]
        descriptor = ctypes.c_void_p()
        convert = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.restype = wintypes.BOOL
        convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                            ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
        if not convert(sddl, 1, ctypes.byref(descriptor), None) or not descriptor.value:
            raise LedgerError("LEDGER_PRIVATE_DIRECTORY_CREATE_FAILED")
        try:
            attributes = _SecurityAttributes(
                ctypes.sizeof(_SecurityAttributes), descriptor, False,
            )
            kernel32.CreateDirectoryW.restype = wintypes.BOOL
            kernel32.CreateDirectoryW.argtypes = [
                wintypes.LPCWSTR, ctypes.POINTER(_SecurityAttributes),
            ]
            if not kernel32.CreateDirectoryW(str(target), ctypes.byref(attributes)):
                raise LedgerError("LEDGER_PRIVATE_DIRECTORY_CREATE_FAILED")
        finally:
            api.free(descriptor)  # type: ignore[attr-defined]
    else:
        try:
            target.mkdir(mode=0o700)
        except OSError as error:
            raise LedgerError("LEDGER_PRIVATE_DIRECTORY_CREATE_FAILED") from error

    return _open_private_directory_guard(target)


def _verify_private_file(path: Path) -> None:
    """Require files in a private directory to inherit only its trusted DACL."""
    if os.name != "nt":
        return
    try:
        info = os.lstat(path)
        if (
            not stat.S_ISREG(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise LedgerError("LEDGER_PATH_UNSAFE")
        api = _windows_api()
        sid = api.current_user_sid()  # type: ignore[attr-defined]
        owner, _protected, entries = api.inspect_acl(path)  # type: ignore[attr-defined]
        expected_sids = {sid, _SYSTEM_SID, _ADMINISTRATORS_SID}
        if (
            owner != sid
            or len(entries) != len(expected_sids)
            or any(
                ace_type != _ACCESS_ALLOWED_ACE_TYPE
                or not flags & _INHERITED_ACE
                or flags & ~(
                    _INHERITED_ACE | _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE
                )
                or mask != _FILE_ALL_ACCESS
                or entry_sid not in expected_sids
                for ace_type, flags, mask, entry_sid in entries
            )
            or {entry[3] for entry in entries} != expected_sids
        ):
            raise LedgerError("LEDGER_PRIVATE_FILE_UNVERIFIED")
    except LedgerError:
        raise
    except Exception as error:
        raise LedgerError("LEDGER_PRIVATE_FILE_UNVERIFIED") from error


@dataclass(frozen=True)
class AuditAck:
    """Durable acknowledgement for one hash-chained critical audit event."""

    run_id: str
    event_id: str
    sequence: int
    event_hash: str

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "event_id": self.event_id,
            "sequence": self.sequence,
            "event_hash": self.event_hash,
        }


def _integer(value: object, minimum: int = 0, maximum: int = 2**63 - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise LedgerError("INVALID_NUMBER")
    return value


def _enum(value: object, allowed: set[str]) -> str:
    if type(value) is not str or value not in allowed:
        raise LedgerError("INVALID_VALUE")
    return value


def _token(value: object, pattern: re.Pattern[str] = _TOKEN) -> str:
    if type(value) is not str or not pattern.fullmatch(value):
        raise LedgerError("INVALID_IDENTITY")
    return value


def _new_id() -> str:
    return uuid.uuid4().hex


def _check_ledger_paths(
    path: Path,
    *,
    creating: bool = False,
    directory_guard: _PrivateDirectoryGuard | None = None,
) -> None:
    """Require a pinned private parent and reject links/reparse points."""
    if directory_guard is None:
        guard = _open_private_directory_guard(path.parent)
        try:
            guard.verify(path.parent)
        finally:
            guard.close()
    else:
        directory_guard.verify(path.parent)
    for parent in reversed(path.parents):
        try:
            info = os.lstat(parent)
        except OSError as exc:
            raise LedgerError("LEDGER_PATH_INVALID") from exc
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise LedgerError("LEDGER_PATH_UNSAFE")
    quarantine_marker = path.with_name(path.name + ".quarantine")
    candidates = (
        path,
        *(Path(str(path) + suffix) for suffix in ("-wal", "-shm", "-journal")),
        quarantine_marker,
    )
    for candidate in candidates:
        try:
            info = os.lstat(candidate)
        except FileNotFoundError:
            if candidate == path and not creating:
                raise LedgerError("LEDGER_NOT_FOUND_OR_UNSAFE") from None
            continue
        except OSError as exc:
            raise LedgerError("LEDGER_PATH_INVALID") from exc
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise LedgerError("LEDGER_PATH_UNSAFE")
        _verify_private_file(candidate)
        if creating and candidate == quarantine_marker:
            raise LedgerError("LEDGER_QUARANTINED")
        if creating and candidate != path:
            raise LedgerError("LEDGER_SIDECAR_EXISTS")


def _persist_quarantine_marker(
    path: Path,
    *,
    directory_guard: _PrivateDirectoryGuard | None = None,
) -> bool:
    """Create a fixed, secret-free marker that survives ledger re-opening."""
    try:
        _check_ledger_paths(path, directory_guard=directory_guard)
    except LedgerError:
        return False
    marker = path.with_name(path.name + ".quarantine")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(marker, flags, 0o600)
    except FileExistsError:
        return True
    except OSError:
        return False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(b"S9_LEDGER_QUARANTINED_V1\n")
            stream.flush()
            os.fsync(stream.fileno())
        _verify_private_file(marker)
    except (LedgerError, OSError):
        try:
            os.close(descriptor)
        except OSError:
            pass
        # Presence is fail-closed even if the marker's contents were interrupted.
        return False
    return True


def _check_wal(db: sqlite3.Connection) -> None:
    row = db.execute("PRAGMA journal_mode").fetchone()
    if row is None or str(row[0]).lower() != "wal":
        raise LedgerError("LEDGER_WAL_REQUIRED")


class _LedgerWriterLock:
    """Interprocess ownership for one persistent ledger writer epoch."""

    _CONTENT = b"S9WRITER1"

    def __init__(self, ledger_path: Path) -> None:
        self.path = ledger_path.with_name(ledger_path.name + ".writer.lock")
        self.descriptor: int | None = None
        self._locking_module = None

    def acquire(self) -> None:
        if os.path.lexists(self.path):
            info = self.path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise LedgerError("LEDGER_WRITER_LOCK_UNSAFE")
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        try:
            descriptor = os.open(self.path, flags, 0o600)
            _verify_private_file(self.path)
            info = os.fstat(descriptor)
            if info.st_size == 0:
                os.write(descriptor, self._CONTENT)
                os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.read(descriptor, len(self._CONTENT)) != self._CONTENT or os.fstat(descriptor).st_size != len(self._CONTENT):
                raise LedgerError("LEDGER_WRITER_LOCK_INVALID")
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt

                self._locking_module = msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                self._locking_module = fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.descriptor = descriptor
        except LedgerError:
            try:
                os.close(descriptor)
            except (OSError, UnboundLocalError):
                pass
            raise
        except (OSError, ImportError):
            try:
                os.close(descriptor)
            except (OSError, UnboundLocalError):
                pass
            raise LedgerError("LEDGER_WRITER_OWNERSHIP_UNAVAILABLE") from None

    def release(self) -> None:
        descriptor = self.descriptor
        self.descriptor = None
        if descriptor is None:
            return
        try:
            if self._locking_module is not None:
                if os.name == "nt":
                    self._locking_module.locking(descriptor, self._locking_module.LK_UNLCK, 1)
                else:
                    self._locking_module.flock(descriptor, self._locking_module.LOCK_UN)
        except OSError:
            pass
        finally:
            os.close(descriptor)

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            pass


@dataclass
class _LedgerEpoch:
    path: Path
    writer_lock: _LedgerWriterLock
    mutex: threading.RLock
    connection: sqlite3.Connection | None = None
    state: dict[str, object] | None = None
    data_version: int | None = None
    file_identity: tuple[int, int] | None = None
    references: int = 0

    def invalidate(self) -> None:
        self.state = None
        self.data_version = None
        if self.connection is not None:
            try:
                self.connection.close()
            except sqlite3.Error:
                pass
            self.connection = None

    def close(self) -> None:
        self.invalidate()
        self.writer_lock.release()


_EPOCHS: weakref.WeakValueDictionary[str, _LedgerEpoch] = weakref.WeakValueDictionary()
_EPOCHS_LOCK = threading.RLock()


def media_m_cap(expected_bytes: int) -> int:
    """L06 includes the extra request/EOF allowance."""
    expected_bytes = _integer(expected_bytes, GIB, 2 * GIB)
    return ((expected_bytes + CHUNK - 1) // CHUNK) * CHUNK + CHUNK


_SCHEMA = """
CREATE TABLE meta (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1), magic TEXT NOT NULL,
    run_id TEXT NOT NULL, salt BLOB NOT NULL, created_ns INTEGER NOT NULL,
    gate TEXT NOT NULL, status TEXT NOT NULL, deadline_ns INTEGER,
    elapsed_ms INTEGER NOT NULL DEFAULT 0, process_state TEXT NOT NULL,
    result TEXT NOT NULL, cause TEXT NOT NULL,
    working_set INTEGER, peak_working_set INTEGER, private_bytes INTEGER,
    memory_origin TEXT NOT NULL, interruptions INTEGER NOT NULL DEFAULT 0,
    recoveries INTEGER NOT NULL DEFAULT 0, interruption_alias TEXT,
    memory_measured_ns INTEGER
);
CREATE TABLE media (
    alias TEXT PRIMARY KEY, profile TEXT NOT NULL, expected INTEGER NOT NULL,
    kind TEXT NOT NULL, fresh INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE scans (
    scan_id TEXT PRIMARY KEY, max_messages INTEGER NOT NULL,
    incremental INTEGER NOT NULL, window_size INTEGER,
    observed INTEGER, state TEXT NOT NULL
);
CREATE TABLE reservations (
    reservation_id TEXT PRIMARY KEY, alias TEXT NOT NULL REFERENCES media(alias),
    profile TEXT NOT NULL, amount INTEGER NOT NULL, observed INTEGER,
    state TEXT NOT NULL, origin TEXT NOT NULL, owner_token TEXT NOT NULL,
    measurement_source TEXT NOT NULL
);
CREATE TABLE disk_checks (
    check_id TEXT PRIMARY KEY, pending INTEGER NOT NULL, available INTEGER,
    margin INTEGER NOT NULL, extra INTEGER NOT NULL, checked_ns INTEGER NOT NULL,
    available_origin TEXT NOT NULL, margin_origin TEXT NOT NULL
);
CREATE TABLE audit_events (
    sequence INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL, created_ns INTEGER NOT NULL,
    details_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);
"""


def _audit_details(details: object, *, event_type: str | None = None) -> str:
    if type(details) is not dict or set(details) - _AUDIT_DETAIL_KEYS:
        raise LedgerError("AUDIT_EVENT_INVALID")
    for key, value in details.items():
        if type(key) is not str:
            raise LedgerError("AUDIT_EVENT_INVALID")
        if key.endswith("_bytes") or key in {
            "attempt", "deadline_ns", "elapsed_ms", "event_count", "exit_code",
            "max_messages", "media_count", "observed_messages", "pid",
            "process_creation_time", "seconds", "window_size",
            "checked_ns", "issued_ns", "expires_ns", "consumed_ns",
        }:
            if value is not None and type(value) is not int:
                raise LedgerError("AUDIT_EVENT_INVALID")
            if value is not None:
                _integer(value)
        elif key in _AUDIT_ENUM_FIELDS:
            if type(value) is not str:
                raise LedgerError("AUDIT_EVENT_INVALID")
            allowed_values = _AUDIT_ENUM_FIELDS[key]
            g8_baseline_pass = (
                key == "status"
                and event_type == "G8_DATABASE_BASELINE"
                and value == "PASS"
            )
            if value not in allowed_values and not g8_baseline_pass:
                raise LedgerError("AUDIT_EVENT_INVALID")
        elif key == "alias":
            _token(value, _ALIAS)
        elif key == "identity_alias":
            _token(value, _ALIAS)
        elif key in {"reservation_id", "scan_id", "check_id"}:
            _token(value)
        elif key in {
            "receipt_sha256", "database_sha256_before", "database_sha256_after",
            "g7_receipt_sha256", "g6_receipt_sha256",
            "predecessor_receipts_sha256",
        }:
            if type(value) is not str or not _HASH.fullmatch(value):
                raise LedgerError("AUDIT_EVENT_INVALID")
        elif key in {"channel_ref", "manifest_sha256", "scope_sha256", "nonce_sha256"}:
            if type(value) is not str or not _HASH.fullmatch(value):
                raise LedgerError("AUDIT_EVENT_INVALID")
        elif type(value) is bool:
            continue
        elif value is None:
            continue
        elif type(value) is str:
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", value):
                raise LedgerError("AUDIT_EVENT_INVALID")
        else:
            raise LedgerError("AUDIT_EVENT_INVALID")
    return json.dumps(details, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _audit_hash(
    sequence: int, event_id: str, event_type: str, run_id: str,
    created_ns: int, details_json: str, previous_hash: str,
) -> str:
    canonical = json.dumps(
        [sequence, event_id, event_type, run_id, created_ns, details_json, previous_hash],
        ensure_ascii=True, separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def _commit_durable(db: sqlite3.Connection) -> None:
    """Return only after SQLite's configured FULL synchronous commit completes."""
    db.commit()


def _append_audit_event(
    db: sqlite3.Connection, event_type: str, details: dict[str, object], event_id: str,
) -> AuditAck:
    _enum(event_type, _AUDIT_EVENT_TYPES)
    event_id = _token(event_id)
    details_json = _audit_details(details, event_type=event_type)
    run_id = db.execute("SELECT run_id FROM meta WHERE singleton=1").fetchone()[0]
    existing = db.execute(
        "SELECT sequence,event_type,created_ns,details_json,previous_hash,event_hash "
        "FROM audit_events WHERE event_id=?", (event_id,),
    ).fetchone()
    if existing is not None:
        sequence, old_type, _created_ns, old_details, _previous_hash, event_hash = existing
        if old_type != event_type or old_details != details_json:
            raise LedgerError("AUDIT_EVENT_REPLAY_CONFLICT")
        return AuditAck(run_id, event_id, sequence, event_hash)
    row = db.execute(
        "SELECT sequence,event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
    ).fetchone()
    sequence = 1 if row is None else row[0] + 1
    previous_hash = _AUDIT_ZERO_HASH if row is None else row[1]
    created_ns = time.time_ns()
    event_hash = _audit_hash(
        sequence, event_id, event_type, run_id, created_ns, details_json, previous_hash,
    )
    db.execute(
        "INSERT INTO audit_events VALUES(?,?,?,?,?,?,?)",
        (sequence, event_id, event_type, created_ns, details_json, previous_hash, event_hash),
    )
    return AuditAck(run_id, event_id, sequence, event_hash)


def _validate_audit(
    db: sqlite3.Connection, run_id: str,
) -> tuple[list[tuple[str, dict[str, object]]], list[dict[str, object]]]:
    previous_hash = _AUDIT_ZERO_HASH
    expected_sequence = 1
    parsed_events: list[tuple[str, dict[str, object]]] = []
    audit_rows: list[dict[str, object]] = []
    for sequence, event_id, event_type, created_ns, details_json, linked_hash, event_hash in db.execute(
        "SELECT sequence,event_id,event_type,created_ns,details_json,previous_hash,event_hash "
        "FROM audit_events ORDER BY sequence"
    ):
        _integer(sequence, 1)
        if sequence != expected_sequence:
            raise LedgerError("AUDIT_CHAIN_INVALID")
        _token(event_id)
        _enum(event_type, _AUDIT_EVENT_TYPES)
        _integer(created_ns, 1)
        try:
            details = json.loads(details_json)
        except (TypeError, ValueError):
            raise LedgerError("AUDIT_CHAIN_INVALID") from None
        if (
            _audit_details(details, event_type=event_type) != details_json
            or linked_hash != previous_hash
        ):
            raise LedgerError("AUDIT_CHAIN_INVALID")
        expected_hash = _audit_hash(
            sequence, event_id, event_type, run_id, created_ns, details_json, linked_hash,
        )
        if event_hash != expected_hash:
            raise LedgerError("AUDIT_CHAIN_INVALID")
        previous_hash = event_hash
        expected_sequence += 1
        parsed_events.append((event_type, details))
        audit_rows.append({
            "sequence": sequence, "event_id": event_id, "event_type": event_type,
            "created_ns": created_ns, "details_json": details_json,
            "previous_hash": linked_hash, "event_hash": event_hash,
        })
    if expected_sequence == 1:
        raise LedgerError("AUDIT_CHAIN_MISSING")
    return parsed_events, audit_rows


def _validate_reservation_history(
    db: sqlite3.Connection,
    meta: tuple[object, ...],
    events: list[tuple[str, dict[str, object]]],
    actual_reservations: Mapping[str, tuple[object, ...]],
) -> None:
    media_state: dict[str, tuple[object, ...]] = {}
    scans: dict[str, tuple[object, ...]] = {}
    reservations: dict[str, tuple[object, ...]] = {}
    disk_checks: dict[str, tuple[object, ...]] = {}
    deadline_ns: int | None = None
    execution: dict[str, object] = {
        "gate": "G0", "status": "PLANNED", "deadline_ns": None,
        "elapsed_ms": 0, "process_state": "UNKNOWN", "result": "UNKNOWN",
        "cause": "NONE", "working_set": None, "peak_working_set": None,
        "private_bytes": None, "memory_origin": "UNKNOWN",
        "interruptions": 0, "recoveries": 0, "interruption_alias": None,
    }
    for event_type, details in events:
        if event_type == "MEDIA_REGISTERED" and details.get("status") == "CREATED":
            media_state[details["alias"]] = (
                details["profile"], details["expected_bytes"], details["kind"],
                int(details["fresh"]), 0,
            )
        elif event_type == "ATTEMPT_STARTED":
            current = media_state.get(details["alias"])
            if current is None or details["attempt"] != current[4] + 1:
                raise LedgerError("AUDIT_STATE_MISMATCH")
            media_state[details["alias"]] = (
                current[0], current[1], current[2], current[3], details["attempt"],
            )
            if details["recovery"]:
                execution["recoveries"] = int(execution["recoveries"]) + 1
        elif event_type == "INTERRUPTION_RECORDED":
            execution["interruptions"] = int(execution["interruptions"]) + 1
            execution["interruption_alias"] = details["alias"]
        elif event_type == "RUN_DEADLINE_STARTED":
            if deadline_ns is not None:
                raise LedgerError("AUDIT_STATE_MISMATCH")
            deadline_ns = details["deadline_ns"]
            execution["deadline_ns"] = deadline_ns
        elif event_type == "SCAN_RESERVED":
            scan_id = details["scan_id"]
            if scan_id in scans:
                raise LedgerError("AUDIT_STATE_MISMATCH")
            scans[scan_id] = (
                details["max_messages"], int(details["incremental"]),
                details["window_size"], None, "RESERVED",
            )
        elif event_type == "SCAN_OBSERVED":
            scan_id = details["scan_id"]
            current = scans.get(scan_id)
            if current is None or current[4] != "RESERVED":
                raise LedgerError("AUDIT_STATE_MISMATCH")
            scans[scan_id] = (
                current[0], current[1], current[2], details["observed_messages"],
                "OBSERVED",
            )
        elif event_type == "BYTES_RESERVED":
            reservation_id = details["reservation_id"]
            alias = details["alias"]
            profile = details["profile"]
            if reservation_id in reservations or media_state.get(alias, (None,))[0] != profile:
                raise LedgerError("AUDIT_STATE_MISMATCH")
            reservations[reservation_id] = (
                alias, profile, details["amount_bytes"], None,
                "RESERVED", "RESERVED", "NONE",
            )
        elif event_type == "BYTES_SETTLED":
            reservation_id = details["reservation_id"]
            current = reservations.get(reservation_id)
            if current is None or current[4] != "RESERVED":
                raise LedgerError("AUDIT_STATE_MISMATCH")
            if details["status"] == "UNKNOWN":
                reservations[reservation_id] = (
                    current[0], current[1], current[2], None,
                    "UNCERTAIN", "UNKNOWN", "UNKNOWN",
                )
            else:
                reservations[reservation_id] = (
                    current[0], current[1], current[2], details["observed_bytes"],
                    "OBSERVED", "MEASURED", details["measurement_source"],
                )
        elif event_type == "DISK_CHECKED":
            check_id = details["check_id"]
            if check_id in disk_checks:
                raise LedgerError("AUDIT_STATE_MISMATCH")
            disk_checks[check_id] = (
                details["pending_bytes"], details["available_bytes"],
                details["margin_bytes"], details["extra_bytes"],
                details["checked_ns"], details["available_origin"],
                details["margin_origin"],
            )
        elif event_type in {"GATE_STATE_UPDATED", "RUN_TERMINAL"}:
            for key in ("gate", "status", "deadline_ns", "elapsed_ms", "process_state", "result", "cause"):
                execution[key] = details[key]
            if details["working_set_bytes"] is not None:
                execution["working_set"] = details["working_set_bytes"]
                execution["peak_working_set"] = max(
                    details["peak_working_set_bytes"],
                    int(execution["peak_working_set"] or 0),
                )
                execution["private_bytes"] = details["private_bytes"]
                execution["memory_origin"] = "MEASURED"
            if event_type == "RUN_TERMINAL":
                for reservation_id, current in tuple(reservations.items()):
                    if current[4] == "RESERVED":
                        reservations[reservation_id] = (
                            current[0], current[1], current[2], None,
                            "UNCERTAIN", "UNKNOWN", "UNKNOWN",
                        )
                for scan_id, current in tuple(scans.items()):
                    if current[4] == "RESERVED":
                        scans[scan_id] = (current[0], current[1], current[2], None, "UNCERTAIN")
    if actual_reservations != reservations:
        raise LedgerError("AUDIT_STATE_MISMATCH")
    actual_media = {
        row[0]: tuple(row[1:])
        for row in db.execute("SELECT alias,profile,expected,kind,fresh,attempts FROM media")
    }
    actual_scans = {
        row[0]: tuple(row[1:])
        for row in db.execute("SELECT scan_id,max_messages,incremental,window_size,observed,state FROM scans")
    }
    actual_disk = {
        row[0]: tuple(row[1:])
        for row in db.execute("SELECT check_id,pending,available,margin,extra,checked_ns,available_origin,margin_origin FROM disk_checks")
    }
    actual_execution = {
        "gate": meta[5], "status": meta[6], "deadline_ns": meta[7],
        "elapsed_ms": meta[8], "process_state": meta[9], "result": meta[10],
        "cause": meta[11], "working_set": meta[12],
        "peak_working_set": meta[13], "private_bytes": meta[14],
        "memory_origin": meta[15], "interruptions": meta[16],
        "recoveries": meta[17], "interruption_alias": meta[18],
    }
    if (
        actual_media != media_state
        or actual_scans != scans
        or actual_disk != disk_checks
        or actual_execution != execution
    ):
        raise LedgerError("AUDIT_STATE_MISMATCH")


class S9OperationalLedger:
    """SQLite file for one F+M run, distinct from all operational databases.

    Create with :meth:`create`; reopen with the constructor. Existing unknown
    files are inspected read-only and are never initialized or migrated.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        _directory_guard: _PrivateDirectoryGuard | None = None,
    ) -> None:
        self.path = Path(path).absolute()
        self._session_id = _new_id()
        self._critical_audit_failed = False
        self._closed = False
        self._did_fresh_replay = False
        self._requires_child_admission = (
            os.environ.get("TELEGRAM_COURSES_S9_SUPERVISED_CHILD") == "1"
            and bool(os.environ.get("TELEGRAM_COURSES_S9_LEDGER_PATH"))
            and os.path.normcase(os.path.abspath(
                os.environ.get("TELEGRAM_COURSES_S9_LEDGER_PATH", ""),
            )) == os.path.normcase(str(self.path))
        )
        self._child_admission_verified = not self._requires_child_admission
        self._directory_guard = _directory_guard or _open_private_directory_guard(
            self.path.parent
        )
        key = os.path.normcase(str(self.path))
        try:
            _check_ledger_paths(self.path, directory_guard=self._directory_guard)
            if os.path.lexists(self.path.with_name(self.path.name + ".quarantine")):
                self._critical_audit_failed = True
                raise LedgerError("CRITICAL_AUDIT_QUARANTINED")
            with _EPOCHS_LOCK:
                epoch = _EPOCHS.get(key)
                if epoch is not None:
                    with epoch.mutex:
                        if epoch.state is None or epoch.writer_lock.descriptor is None:
                            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
                        epoch.references += 1
                else:
                    writer_lock = _LedgerWriterLock(self.path)
                    writer_lock.acquire()
                    epoch = _LedgerEpoch(
                        path=self.path, writer_lock=writer_lock,
                        mutex=threading.RLock(), references=1,
                    )
                    _EPOCHS[key] = epoch
                    self._epoch = epoch
                    self._fresh_replay()
                    self._did_fresh_replay = True
                self._epoch = epoch
            if not self._did_fresh_replay:
                self._refresh_if_data_version_changed()
            if self._requires_child_admission and not self._child_admission_verified:
                self.verify_current_child_handoff()
        except BaseException:
            if _directory_guard is None:
                self._directory_guard.close()
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        epoch = getattr(self, "_epoch", None)
        if epoch is not None:
            key = os.path.normcase(str(self.path))
            with _EPOCHS_LOCK:
                with epoch.mutex:
                    epoch.references = max(0, epoch.references - 1)
                    if epoch.references == 0:
                        epoch.close()
                        if _EPOCHS.get(key) is epoch:
                            _EPOCHS.pop(key, None)
            self._epoch = None
        self._directory_guard.close()

    def __enter__(self) -> S9OperationalLedger:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _file_id(self) -> tuple[int, int]:
        try:
            info = os.lstat(self.path)
        except OSError as error:
            raise LedgerError("LEDGER_PATH_INVALID") from error
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise LedgerError("LEDGER_PATH_UNSAFE")
        return int(info.st_dev), int(info.st_ino)

    def _guard_epoch(self, *, for_ack: bool = False) -> sqlite3.Connection:
        epoch = self._epoch
        if self._closed or epoch is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        _check_ledger_paths(self.path, directory_guard=self._directory_guard)
        marker = self.path.with_name(self.path.name + ".quarantine")
        if os.path.lexists(marker):
            self._critical_audit_failed = True
            raise LedgerError("CRITICAL_AUDIT_QUARANTINED")
        if epoch.state is None or epoch.connection is None:
            if self._critical_audit_failed:
                raise LedgerError("CRITICAL_AUDIT_QUARANTINED")
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        if epoch.writer_lock.descriptor is None:
            raise LedgerError("LEDGER_WRITER_OWNERSHIP_REQUIRED")
        try:
            _check_wal(epoch.connection)
        except LedgerError:
            self._quarantine()
            raise
        if epoch.file_identity != self._file_id():
            epoch.invalidate()
            self._critical_audit_failed = True
            raise LedgerError("LEDGER_IDENTITY_CHANGED")
        if for_ack and self._critical_audit_failed:
            raise LedgerError("CRITICAL_AUDIT_QUARANTINED")
        return epoch.connection

    def _refresh_if_data_version_changed(self) -> None:
        epoch = self._epoch
        db = self._guard_epoch()
        version = int(db.execute("PRAGMA data_version").fetchone()[0])
        if epoch is not None and epoch.data_version is not None and version != epoch.data_version:
            self._fresh_replay()

    def _fresh_replay(self) -> None:
        """Discard the writer cache, replay on a fresh read connection, then reopen writer."""
        epoch = self._epoch
        if epoch is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        with epoch.mutex:
            epoch.invalidate()
            if epoch.writer_lock.descriptor is None:
                epoch.writer_lock.acquire()
            _check_ledger_paths(self.path, directory_guard=self._directory_guard)
            marker = self.path.with_name(self.path.name + ".quarantine")
            if os.path.lexists(marker):
                self._critical_audit_failed = True
                raise LedgerError("CRITICAL_AUDIT_QUARANTINED")
            file_identity = self._file_id()
            if epoch.file_identity is not None and epoch.file_identity != file_identity:
                raise LedgerError("LEDGER_IDENTITY_CHANGED")
            writer: sqlite3.Connection | None = None
            try:
                writer = sqlite3.connect(
                    self.path, timeout=10, isolation_level=None,
                    check_same_thread=False,
                )
                writer.execute("PRAGMA foreign_keys=ON")
                writer.execute("PRAGMA synchronous=FULL")
                _check_wal(writer)
                replay_start_version = int(
                    writer.execute("PRAGMA data_version").fetchone()[0]
                )
                uri = self.path.as_uri() + "?mode=ro"
                reader = sqlite3.connect(uri, uri=True, timeout=10)
                try:
                    _check_wal(reader)
                    state = self._validate(reader)
                finally:
                    reader.close()
                _check_ledger_paths(self.path, directory_guard=self._directory_guard)
                if os.path.lexists(marker) or self._file_id() != file_identity:
                    raise LedgerError("LEDGER_IDENTITY_CHANGED")
                head = writer.execute(
                    "SELECT sequence,event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1",
                ).fetchone()
                if head != (state["head_sequence"], state["head_hash"]):
                    raise LedgerError("LEDGER_HEAD_CHANGED_DURING_REPLAY")
                replay_end_version = int(
                    writer.execute("PRAGMA data_version").fetchone()[0]
                )
                if replay_end_version != replay_start_version:
                    raise LedgerError("LEDGER_EXTERNAL_WRITER_DURING_REPLAY")
                epoch.connection = writer
                writer = None
                epoch.state = state
                epoch.file_identity = file_identity
                epoch.data_version = replay_start_version
                self._critical_audit_failed = False
            except LedgerError:
                if writer is not None:
                    writer.close()
                epoch.invalidate()
                self._quarantine()
                raise
            except (sqlite3.Error, OSError, ValueError, TypeError, OverflowError, IndexError):
                if writer is not None:
                    writer.close()
                epoch.invalidate()
                self._quarantine()
                raise LedgerError("LEDGER_CORRUPT_OR_UNKNOWN") from None

    def checkpoint(self) -> dict[str, object]:
        """Run a required full replay using a fresh SQLite connection."""
        epoch = self._epoch
        if epoch is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        with epoch.mutex:
            self._guard_epoch()
            self._fresh_replay()
            assert epoch.state is not None
            return dict(epoch.state)

    def release_writer_ownership(self) -> None:
        """Close and invalidate this process epoch before a suspended child resumes."""
        epoch = self._epoch
        if epoch is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        with epoch.mutex:
            self._guard_epoch()
            epoch.invalidate()
            epoch.writer_lock.release()

    def reacquire_writer_ownership(
        self, expected: Mapping[str, object] | None = None,
    ) -> None:
        """Reopen after proven child exit; fresh replay must preserve the handoff ACK."""
        epoch = self._epoch
        if epoch is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        with epoch.mutex:
            if epoch.writer_lock.descriptor is not None:
                raise LedgerError("LEDGER_WRITER_ALREADY_OWNED")
            epoch.writer_lock.acquire()
            self._fresh_replay()
            if expected is not None:
                self.verify_handoff_ack(expected)

    def verify_handoff_ack(self, expected: Mapping[str, object]) -> None:
        epoch = self._epoch
        if epoch is None or epoch.state is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        audit = epoch.state["audit"]
        sequence = expected.get("sequence")
        event_hash = expected.get("event_hash")
        run_id = expected.get("run_id")
        if type(sequence) is not int or sequence < 1 or type(event_hash) is not str:
            raise LedgerError("LEDGER_HANDOFF_ACK_INVALID")
        meta = epoch.state["meta"]
        if meta[2] != run_id or sequence > len(audit):
            raise LedgerError("LEDGER_HANDOFF_ACK_MISMATCH")
        event = audit[sequence - 1]
        if (
            event["sequence"] != sequence or event["event_hash"] != event_hash
            or event["event_type"] != "CHILD_PROCESS_CONFIRMED"
        ):
            raise LedgerError("LEDGER_HANDOFF_ACK_MISMATCH")
        stage = expected.get("stage")
        try:
            details = json.loads(event["details_json"])
        except (TypeError, ValueError):
            raise LedgerError("LEDGER_HANDOFF_ACK_MISMATCH") from None
        if (
            details.get("stage") != stage
            or details.get("pid") != expected.get("child_pid")
            or details.get("process_creation_time") != expected.get("creation_time")
        ):
            raise LedgerError("LEDGER_HANDOFF_ACK_MISMATCH")

    def verify_child_handoff(
        self, *, pid: int, creation_time: int, stage: str,
    ) -> None:
        """Bind a queue child admission to its own confirmed process identity."""
        if (
            not self._requires_child_admission
            or type(pid) is not int or pid != os.getpid()
            or type(creation_time) is not int or creation_time <= 0
            or stage != os.environ.get("TELEGRAM_COURSES_S9_STAGE")
        ):
            raise LedgerError("LEDGER_CHILD_IDENTITY_INVALID")
        epoch = self._epoch
        if epoch is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        with epoch.mutex:
            self._refresh_if_data_version_changed()
            self._guard_epoch()
            state = epoch.state
            assert state is not None
            matches = []
            for event in state["audit"]:
                if event["event_type"] != "CHILD_PROCESS_CONFIRMED":
                    continue
                try:
                    details = json.loads(event["details_json"])
                except (TypeError, ValueError):
                    raise LedgerError("LEDGER_CHILD_IDENTITY_INVALID") from None
                if (
                    details.get("pid") == pid
                    and details.get("process_creation_time") == creation_time
                    and details.get("stage") == stage
                ):
                    matches.append(event)
            if len(matches) != 1:
                raise LedgerError("LEDGER_CHILD_IDENTITY_INVALID")
            self._child_admission_verified = True

    def verify_current_child_handoff(self) -> None:
        """Query the current Windows process identity and bind it to the ACK."""
        if os.name != "nt":
            raise LedgerError("LEDGER_CHILD_IDENTITY_UNAVAILABLE")
        try:
            from telegram_courses.s9_supervisor import _creation_time, _windows_api

            api = _windows_api()
            pid = os.getpid()
            creation_time = _creation_time(api[13], api[14], api[6], pid)
            stage = os.environ.get("TELEGRAM_COURSES_S9_STAGE", "")
            self.verify_child_handoff(
                pid=pid, creation_time=creation_time, stage=stage,
            )
        except LedgerError:
            raise
        except Exception as error:
            raise LedgerError("LEDGER_CHILD_IDENTITY_UNAVAILABLE") from error

    def _quarantine(self) -> bool:
        self._critical_audit_failed = True
        epoch = getattr(self, "_epoch", None)
        if epoch is not None:
            epoch.invalidate()
        return _persist_quarantine_marker(
            self.path, directory_guard=self._directory_guard,
        )

    @classmethod
    def create(cls, path: str | Path) -> S9OperationalLedger:
        target = Path(path).absolute()
        directory_guard = _open_private_directory_guard(target.parent)
        created = False
        try:
            _check_ledger_paths(
                target, creating=True, directory_guard=directory_guard,
            )
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            flags |= getattr(os, "O_NOFOLLOW", 0)
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            try:
                fd = os.open(target, flags, 0o600)
                os.close(fd)
                created = True
            except OSError:
                raise LedgerError("LEDGER_CREATE_FAILED") from None
            db = sqlite3.connect(target, isolation_level=None)
            try:
                if db.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
                    raise LedgerError("LEDGER_WAL_REQUIRED")
                db.execute("PRAGMA synchronous=FULL")
                db.executescript(_SCHEMA)
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "INSERT INTO meta(singleton,magic,run_id,salt,created_ns,gate,status,"
                    "process_state,result,cause,memory_origin) VALUES(1,?,?,?,?,?,?,?,?,?,?)",
                    (_MAGIC, _new_id(), secrets.token_bytes(32), time.time_ns(), "G0",
                     "PLANNED", "UNKNOWN", "UNKNOWN", "NONE", "UNKNOWN"),
                )
                _append_audit_event(
                    db, "LEDGER_CREATED", {}, _new_id(),
                )
                _commit_durable(db)
            finally:
                db.close()
            _check_ledger_paths(target, directory_guard=directory_guard)
            return cls(target, _directory_guard=directory_guard)
        except LedgerError:
            if created:
                _persist_quarantine_marker(
                    target, directory_guard=directory_guard,
                )
            directory_guard.close()
            raise
        except (sqlite3.Error, OSError) as exc:
            # Preserve the newly created file as evidence; never reuse it implicitly.
            if created:
                _persist_quarantine_marker(
                    target, directory_guard=directory_guard,
                )
            directory_guard.close()
            raise LedgerError("LEDGER_CREATE_FAILED") from exc

    def _inspect_readonly(self) -> None:
        self._guard_epoch()

    @contextmanager
    def _transaction(
        self,
        audit_event: tuple[str, dict[str, object], str | None] | None = None,
    ) -> Iterator[sqlite3.Connection]:
        epoch = self._epoch
        if epoch is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        with epoch.mutex:
            if not self._child_admission_verified:
                raise LedgerError("LEDGER_CHILD_IDENTITY_INVALID")
            db = self._guard_epoch()
            try:
                version = int(db.execute("PRAGMA data_version").fetchone()[0])
                if epoch.data_version is not None and version != epoch.data_version:
                    self._fresh_replay()
                    db = self._guard_epoch()
                self._check_cached_head_and_meta(db)
                self._check_touched_projection(db, audit_event)
                db.execute("BEGIN IMMEDIATE")
                try:
                    locked_version = int(db.execute("PRAGMA data_version").fetchone()[0])
                    if epoch.data_version is not None and locked_version != epoch.data_version:
                        db.rollback()
                        self._fresh_replay()
                        db = self._guard_epoch()
                        self._check_cached_head_and_meta(db)
                        self._check_touched_projection(db, audit_event)
                        db.execute("BEGIN IMMEDIATE")
                        locked_version = int(db.execute("PRAGMA data_version").fetchone()[0])
                        if epoch.data_version is not None and locked_version != epoch.data_version:
                            db.rollback()
                            raise LedgerError("LEDGER_EXTERNAL_WRITER_RACE")
                    self._check_cached_head_and_meta(db)
                    self._check_touched_projection(db, audit_event)
                    yield db
                    ack: AuditAck | None = None
                    if audit_event is not None:
                        event_type, details, event_id = audit_event
                        try:
                            ack = _append_audit_event(db, event_type, details, event_id or _new_id())
                        except LedgerError as error:
                            if error.args == ("AUDIT_EVENT_REPLAY_CONFLICT",):
                                self._quarantine()
                            raise
                    self._guard_epoch()
                    _commit_durable(db)
                except BaseException:
                    try:
                        db.rollback()
                    except sqlite3.Error:
                        pass
                    raise
                try:
                    self._guard_epoch(for_ack=audit_event is not None)
                    committed_version = int(db.execute("PRAGMA data_version").fetchone()[0])
                    if epoch.data_version is not None and committed_version != epoch.data_version:
                        self._fresh_replay()
                        db = self._guard_epoch()
                        refreshed = epoch.state
                        if ack is not None and (
                            refreshed is None
                            or refreshed["audit_by_id"].get(ack.event_id, {}).get("event_hash") != ack.event_hash
                        ):
                            raise LedgerError("LEDGER_ACK_LOST_AFTER_REPLAY")
                    else:
                        if ack is not None:
                            self._apply_committed_delta(db, audit_event, ack)
                        # Keep the version captured before publishing the RAM
                        # delta. A later cooperative writer must remain visible
                        # to the next operation instead of being absorbed here.
                        epoch.data_version = committed_version
                    if audit_event is not None:
                        self._last_ack = ack
                except BaseException:
                    epoch.invalidate()
                    raise
            except LedgerError:
                raise
            except (sqlite3.Error, OSError, TypeError, OverflowError, IndexError):
                # A failed COMMIT can be ambiguous; this epoch must never issue
                # another reservation or acknowledgement using its stale cache.
                epoch.invalidate()
                if audit_event is not None:
                    self._quarantine()
                raise LedgerError("LEDGER_IO_OR_CORRUPTION") from None

    def _check_cached_head_and_meta(self, db: sqlite3.Connection) -> None:
        epoch = self._epoch
        state = epoch.state if epoch is not None else None
        if state is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        meta = tuple(db.execute("SELECT * FROM meta").fetchone() or ())
        if meta != state["meta"]:
            self._quarantine()
            raise LedgerError("LEDGER_META_CHANGED")
        head = db.execute(
            "SELECT sequence,event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1",
        ).fetchone()
        if head != (state["head_sequence"], state["head_hash"]):
            self._quarantine()
            raise LedgerError("LEDGER_HEAD_CHANGED")

    def _check_touched_projection(
        self,
        db: sqlite3.Connection,
        audit_event: tuple[str, dict[str, object], str | None] | None,
    ) -> None:
        if audit_event is None:
            return
        event_type, details, _event_id = audit_event
        state = self._epoch.state if self._epoch is not None else None
        if state is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")

        def same_or_absent(table: str, key: str, column_sql: str, values: tuple[object, ...] | None) -> None:
            row = db.execute(f"SELECT {column_sql} FROM {table} WHERE {key}=?", (details.get(key),)).fetchone()
            if (row is None) != (values is None) or row is not None and tuple(row) != values:
                self._quarantine()
                raise LedgerError("LEDGER_TOUCHED_ROW_CHANGED")

        alias = details.get("alias")
        if type(alias) is str and event_type in {
            "MEDIA_REGISTERED", "ATTEMPT_STARTED", "INTERRUPTION_RECORDED",
            "BYTES_RESERVED",
        }:
            same_or_absent(
                "media", "alias", "profile,expected,kind,fresh,attempts",
                state["media"].get(alias),
            )
        scan_id = details.get("scan_id")
        if type(scan_id) is str and event_type in {"SCAN_RESERVED", "SCAN_OBSERVED"}:
            same_or_absent(
                "scans", "scan_id", "max_messages,incremental,window_size,observed,state",
                state["scans"].get(scan_id),
            )
        reservation_id = details.get("reservation_id")
        if type(reservation_id) is str and event_type in {"BYTES_RESERVED", "BYTES_SETTLED"}:
            expected = state["reservations"].get(reservation_id)
            if expected is not None:
                same_or_absent(
                    "reservations", "reservation_id",
                    "alias,profile,amount,observed,state,origin,owner_token,measurement_source",
                    expected,
                )
            elif db.execute(
                "SELECT 1 FROM reservations WHERE reservation_id=?", (reservation_id,),
            ).fetchone() is not None:
                self._quarantine()
                raise LedgerError("LEDGER_TOUCHED_ROW_CHANGED")
        check_id = details.get("check_id")
        if type(check_id) is str and event_type == "DISK_CHECKED":
            if check_id in state["disk_checks"] or db.execute(
                "SELECT 1 FROM disk_checks WHERE check_id=?", (check_id,),
            ).fetchone() is not None:
                self._quarantine()
                raise LedgerError("LEDGER_TOUCHED_ROW_CHANGED")

    def _apply_committed_delta(
        self,
        db: sqlite3.Connection,
        audit_event: tuple[str, dict[str, object], str | None] | None,
        ack: AuditAck,
    ) -> None:
        epoch = self._epoch
        if epoch is None or epoch.state is None or audit_event is None:
            return
        state = epoch.state
        event_type, details, _event_id = audit_event
        if ack.sequence > state["head_sequence"]:
            audit_row = db.execute(
                "SELECT sequence,event_id,event_type,created_ns,details_json,previous_hash,event_hash "
                "FROM audit_events WHERE sequence=?", (ack.sequence,),
            ).fetchone()
            if audit_row is None or audit_row[5] != state["head_hash"]:
                raise LedgerError("LEDGER_APPEND_HEAD_MISMATCH")
            event = dict(zip(
                ("sequence", "event_id", "event_type", "created_ns", "details_json", "previous_hash", "event_hash"),
                audit_row,
            ))
            state["audit"].append(event)
            state["audit_by_id"][event["event_id"]] = event
            state["head_sequence"] = ack.sequence
            state["head_hash"] = ack.event_hash
        alias = details.get("alias")
        if type(alias) is str and event_type in {"MEDIA_REGISTERED", "ATTEMPT_STARTED"}:
            was_registered = alias in state["media"]
            row = db.execute(
                "SELECT profile,expected,kind,fresh,attempts FROM media WHERE alias=?", (alias,),
            ).fetchone()
            if row is not None:
                state["media"][alias] = tuple(row)
                if not was_registered:
                    state["budgets"][row[0]]["planned"] += int(row[1])
        if event_type == "INTERRUPTION_RECORDED":
            state["meta"] = tuple(db.execute("SELECT * FROM meta").fetchone())
        scan_id = details.get("scan_id")
        if type(scan_id) is str and event_type in {"SCAN_RESERVED", "SCAN_OBSERVED"}:
            row = db.execute(
                "SELECT max_messages,incremental,window_size,observed,state FROM scans WHERE scan_id=?",
                (scan_id,),
            ).fetchone()
            if row is not None:
                state["scans"][scan_id] = tuple(row)
        reservation_id = details.get("reservation_id")
        if type(reservation_id) is str and event_type in {"BYTES_RESERVED", "BYTES_SETTLED"}:
            previous = state["reservations"].get(reservation_id)
            row = db.execute(
                "SELECT alias,profile,amount,observed,state,origin,owner_token,measurement_source "
                "FROM reservations WHERE reservation_id=?", (reservation_id,),
            ).fetchone()
            if row is not None:
                if previous is not None:
                    old_profile, old_amount, old_observed, old_status = previous[1], int(previous[2]), previous[3], previous[4]
                    if old_status == "RESERVED":
                        state["budgets"][old_profile]["reserved"] -= old_amount
                    elif old_status == "OBSERVED":
                        state["budgets"][old_profile]["observed"] -= int(old_observed)
                    else:
                        state["budgets"][old_profile]["uncertain"] -= old_amount
                new_profile, new_amount, new_observed, new_status = row[1], int(row[2]), row[3], row[4]
                if new_status == "RESERVED":
                    state["budgets"][new_profile]["reserved"] += new_amount
                elif new_status == "OBSERVED":
                    state["budgets"][new_profile]["observed"] += int(new_observed)
                else:
                    state["budgets"][new_profile]["uncertain"] += new_amount
                state["reservations"][reservation_id] = tuple(row)
        check_id = details.get("check_id")
        if type(check_id) is str and event_type == "DISK_CHECKED":
            row = db.execute(
                "SELECT pending,available,margin,extra,checked_ns,available_origin,margin_origin "
                "FROM disk_checks WHERE check_id=?", (check_id,),
            ).fetchone()
            if row is not None:
                state["disk_checks"][check_id] = tuple(row)
        if event_type in {"RUN_DEADLINE_STARTED", "GATE_STATE_UPDATED", "RUN_TERMINAL", "INTERRUPTION_RECORDED", "ATTEMPT_STARTED"}:
            state["meta"] = tuple(db.execute("SELECT * FROM meta").fetchone())
        if event_type == "RUN_TERMINAL":
            state["budgets"] = {
                "F": {"planned": 0, "reserved": 0, "observed": 0, "uncertain": 0},
                "M": {"planned": 0, "reserved": 0, "observed": 0, "uncertain": 0},
            }
            for media_row in state["media"].values():
                state["budgets"][media_row[0]]["planned"] += int(media_row[1])
            state["reservations"] = {
                row[0]: tuple(row[1:]) for row in db.execute(
                    "SELECT reservation_id,alias,profile,amount,observed,state,origin,owner_token,measurement_source FROM reservations",
                )
            }
            for reservation_row in state["reservations"].values():
                profile, amount, observed, status = reservation_row[1], int(reservation_row[2]), reservation_row[3], reservation_row[4]
                if status == "RESERVED":
                    state["budgets"][profile]["reserved"] += amount
                elif status == "OBSERVED":
                    state["budgets"][profile]["observed"] += int(observed)
                else:
                    state["budgets"][profile]["uncertain"] += amount
            state["scans"] = {
                row[0]: tuple(row[1:]) for row in db.execute(
                    "SELECT scan_id,max_messages,incremental,window_size,observed,state FROM scans",
                )
            }

    @staticmethod
    def _validate(db: sqlite3.Connection) -> dict[str, object]:
        if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise LedgerError("LEDGER_CORRUPT")
        rows = db.execute("SELECT * FROM meta").fetchall()
        if len(rows) != 1 or rows[0][0] != 1 or rows[0][1] != _MAGIC:
            raise LedgerError("LEDGER_IDENTITY_INVALID")
        if not _TOKEN.fullmatch(rows[0][2]) or len(rows[0][3]) != 32:
            raise LedgerError("LEDGER_IDENTITY_INVALID")
        audit_events, audit_rows = _validate_audit(db, rows[0][2])
        _integer(rows[0][4], 1)
        _enum(rows[0][5], {f"G{i}" for i in range(10)})
        _enum(rows[0][6], {"PLANNED", "RUNNING", "COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "BLOCKED"})
        if rows[0][7] is not None:
            _integer(rows[0][7], 1)
        elif rows[0][6] == "RUNNING":
            raise LedgerError("DEADLINE_NOT_STARTED")
        _integer(rows[0][8])
        _enum(rows[0][9], {"UNKNOWN", "RUNNING", "EXITED", "CONTAINED", "UNCONTAINED"})
        _enum(rows[0][10], {
            "UNKNOWN", "PASS", "FAIL", "PARTIAL", "BLOCKED", "CANCELLED",
            "OFFLINE_SYNTHETIC_PASS", "REAL_CONTRACTUAL_PASS",
            "REAL_EVIDENCE_PENDING",
        })
        _enum(rows[0][11], {"NONE", "TIMEOUT", "DEADLINE", "MEMORY", "DISK", "FLOODWAIT", "CANCELLED", "LEDGER", "PROCESS", "OTHER"})
        if rows[0][11] == "FLOODWAIT" and rows[0][6] != "BLOCKED":
            raise LedgerError("FLOODWAIT_STATE_INVALID")
        metrics = rows[0][12:15]
        if all(value is None for value in metrics):
            if rows[0][15] != "UNKNOWN" or rows[0][19] is not None:
                raise LedgerError("MEMORY_MEASUREMENT_INVALID")
        else:
            for value in metrics:
                _integer(value)
            _integer(rows[0][19], 1)
            if rows[0][15] != "MEASURED" or metrics[1] < metrics[0]:
                raise LedgerError("MEMORY_MEASUREMENT_INVALID")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise LedgerError("LEDGER_INTEGRITY_INVALID")
        media = db.execute("SELECT alias,profile,expected,kind,fresh,attempts FROM media").fetchall()
        media_state: dict[str, tuple[object, ...]] = {}
        media_profiles: dict[str, str] = {}
        profiles: dict[str, list[tuple]] = {"F": [], "M": []}
        for alias, profile, expected, kind, fresh, attempts in media:
            _token(alias, _ALIAS)
            _enum(profile, {"F", "M"})
            _integer(expected, 1, 2 * GIB)
            _enum(kind, {"DOCUMENT"})
            _integer(fresh, 0, 1)
            _integer(attempts, 0, 3 if profile == "F" else 1)
            if profile == "F" and expected > 128 * MIB:
                raise LedgerError("MEDIA_LIMIT")
            if profile == "M" and (expected < GIB or not fresh):
                raise LedgerError("MEDIA_LIMIT")
            media_profiles[alias] = profile
            profiles[profile].append((alias, expected))
            media_state[alias] = (profile, expected, kind, fresh, attempts)
        if len(profiles["F"]) > 8 or len(profiles["M"]) > 1:
            raise LedgerError("MEDIA_LIMIT")
        scans = db.execute("SELECT scan_id,max_messages,incremental,window_size,observed,state FROM scans").fetchall()
        scan_state: dict[str, tuple[object, ...]] = {}
        if len(scans) > 3:
            raise LedgerError("SCAN_LIMIT")
        total_obs = 0
        for scan_id, maximum, incremental, window, observed, state in scans:
            _token(scan_id)
            _integer(maximum, 1, 200)
            _integer(incremental, 0, 1)
            if (incremental and window != 50) or (not incremental and window is not None):
                raise LedgerError("SCAN_WINDOW_INVALID")
            _enum(state, {"RESERVED", "OBSERVED", "UNCERTAIN"})
            if state in {"RESERVED", "UNCERTAIN"}:
                if observed is not None:
                    raise LedgerError("SCAN_STATE_INVALID")
                total_obs += maximum
            else:
                total_obs += _integer(observed, 0, maximum)
            scan_state[scan_id] = (maximum, incremental, window, observed, state)
        if total_obs > 600:
            raise LedgerError("SCAN_LIMIT")
        totals = {"F": 0, "M": 0}
        actual_reservations: dict[str, tuple[object, ...]] = {}
        reservation_state: dict[str, tuple[object, ...]] = {}
        for rid, alias, profile, amount, observed, state, origin, owner, measurement_source in db.execute(
            "SELECT reservation_id,alias,profile,amount,observed,state,origin,owner_token,measurement_source FROM reservations"
        ):
            _token(rid)
            _token(owner)
            _token(alias, _ALIAS)
            _enum(profile, {"F", "M"})
            _integer(amount, 1, TOTAL_CAP)
            _enum(state, {"RESERVED", "OBSERVED", "UNCERTAIN"})
            _enum(origin, {"RESERVED", "MEASURED", "UNKNOWN"})
            if media_profiles.get(alias) != profile:
                raise LedgerError("RESERVATION_IDENTITY_INVALID")
            actual_reservations[rid] = (
                alias, profile, amount, observed, state, origin, measurement_source,
            )
            reservation_state[rid] = (
                alias, profile, amount, observed, state, origin, owner,
                measurement_source,
            )
            if state == "OBSERVED":
                _integer(observed, 0, amount)
                if origin != "MEASURED":
                    raise LedgerError("RESERVATION_ORIGIN_INVALID")
                _enum(measurement_source, {"SYNTHETIC_TEST", "GATEWAY_RESPONSE"})
                totals[profile] += observed
            else:
                expected_source = "NONE" if state == "RESERVED" else "UNKNOWN"
                if observed is not None or origin != ("RESERVED" if state == "RESERVED" else "UNKNOWN") or measurement_source != expected_source:
                    raise LedgerError("RESERVATION_STATE_INVALID")
                totals[profile] += amount
        if rows[0][6] in _TERMINAL and (
            db.execute("SELECT 1 FROM reservations WHERE state='RESERVED' LIMIT 1").fetchone()
            or db.execute("SELECT 1 FROM scans WHERE state='RESERVED' LIMIT 1").fetchone()
        ):
            raise LedgerError("TERMINAL_RESERVATION_INVALID")
        _validate_reservation_history(
            db, rows[0], audit_events, actual_reservations,
        )
        m_cap = media_m_cap(profiles["M"][0][1]) if profiles["M"] else 0
        if totals["F"] > F_CAP or totals["M"] > m_cap or sum(totals.values()) > TOTAL_CAP:
            raise LedgerError("BUDGET_EXCEEDED")
        _integer(rows[0][16], 0, 1)
        _integer(rows[0][17], 0, 1)
        if rows[0][16] == 0 and rows[0][18] is not None:
            raise LedgerError("INTERRUPTION_STATE_INVALID")
        if rows[0][16] == 1 and not any(m[0] == rows[0][18] for m in profiles["F"]):
            raise LedgerError("INTERRUPTION_STATE_INVALID")
        if rows[0][17] > rows[0][16]:
            raise LedgerError("RECOVERY_STATE_INVALID")
        disk_state: dict[str, tuple[object, ...]] = {}
        for check_id, pending, available, margin, extra, checked, available_origin, margin_origin in db.execute("SELECT * FROM disk_checks"):
            _token(check_id)
            _integer(pending)
            if available_origin == "MEASURED":
                _integer(available)
            elif available_origin != "UNKNOWN" or available is not None:
                raise LedgerError("DISK_STATE_INVALID")
            _integer(checked, 1)
            if margin != max(GIB, (pending + 9) // 10) or extra != DISK_RESERVE:
                raise LedgerError("DISK_STATE_INVALID")
            if margin_origin != "DERIVED":
                raise LedgerError("DISK_STATE_INVALID")
            disk_state[check_id] = (
                pending, available, margin, extra, checked,
                available_origin, margin_origin,
            )
        head = audit_rows[-1]
        budgets: dict[str, dict[str, int]] = {
            "F": {"planned": 0, "reserved": 0, "observed": 0, "uncertain": 0},
            "M": {"planned": 0, "reserved": 0, "observed": 0, "uncertain": 0},
        }
        for row in media_state.values():
            budgets[row[0]]["planned"] += int(row[1])
        for row in reservation_state.values():
            profile, amount, observed, status = row[1], int(row[2]), row[3], row[4]
            if status == "RESERVED":
                budgets[profile]["reserved"] += amount
            elif status == "OBSERVED":
                budgets[profile]["observed"] += int(observed)
            else:
                budgets[profile]["uncertain"] += amount
        return {
            "meta": tuple(rows[0]), "media": media_state, "scans": scan_state,
            "reservations": reservation_state, "disk_checks": disk_state,
            "audit": audit_rows,
            "audit_by_id": {row["event_id"]: row for row in audit_rows},
            "budgets": budgets, "head_sequence": head["sequence"],
            "head_hash": head["event_hash"],
        }

    @staticmethod
    def _check_deadline(db: sqlite3.Connection, *, require_running: bool = True) -> None:
        deadline, status, cause = db.execute("SELECT deadline_ns,status,cause FROM meta").fetchone()
        if cause == "FLOODWAIT" or status in _TERMINAL:
            raise LedgerError("RUN_NOT_ACTIVE")
        if deadline is None:
            raise LedgerError("DEADLINE_NOT_STARTED")
        if time.time_ns() >= deadline:
            raise LedgerError("DEADLINE_EXPIRED")
        if require_running and status != "RUNNING":
            raise LedgerError("RUN_NOT_RUNNING")

    def start_global_deadline(self, seconds: int = 3600) -> int:
        """Persist an absolute deadline; live supervision must also use monotonic time."""
        _integer(seconds, 1, 3600)
        deadline = time.time_ns() + seconds * 1_000_000_000
        details: dict[str, object] = {"seconds": seconds, "deadline_ns": deadline}
        with self._transaction(("RUN_DEADLINE_STARTED", details, None)) as db:
            previous_deadline, status = db.execute("SELECT deadline_ns,status FROM meta").fetchone()
            if status in _TERMINAL:
                raise LedgerError("RUN_NOT_ACTIVE")
            if previous_deadline is not None:
                raise LedgerError("DEADLINE_ALREADY_STARTED")
            db.execute("UPDATE meta SET deadline_ns=?", (deadline,))
        return deadline

    def active_global_deadline(self) -> int:
        """Return the already-persisted G1 deadline; never start or reset it."""
        snapshot = self.snapshot()
        run = snapshot["run"]
        deadline_ns = run["deadline_ns"]
        if (
            snapshot["critical_audit"]["quarantined"]
            or run["status"] != "RUNNING"
            or run["gate"] not in {f"G{i}" for i in range(1, 9)}
            or type(deadline_ns) is not int
            or deadline_ns <= time.time_ns()
        ):
            raise LedgerError("GLOBAL_RUN_NOT_ACTIVE")
        starts = []
        for event in snapshot["critical_audit"]["events"]:
            if event["event_type"] == "RUN_DEADLINE_STARTED":
                try:
                    details = json.loads(event["details_json"])
                except (TypeError, ValueError):
                    raise LedgerError("GLOBAL_DEADLINE_INVALID") from None
                starts.append(details)
        if (
            len(starts) != 1
            or starts[0].get("seconds") != 3600
            or starts[0].get("deadline_ns") != deadline_ns
        ):
            raise LedgerError("GLOBAL_DEADLINE_INVALID")
        return deadline_ns

    @staticmethod
    def execution_elapsed_ms(snapshot: Mapping[str, object]) -> int:
        """Estimate run elapsed time from its fixed, persisted 3,600 s window."""
        run = snapshot.get("run")
        audit = snapshot.get("critical_audit")
        if not isinstance(run, Mapping) or not isinstance(audit, Mapping):
            raise LedgerError("GLOBAL_DEADLINE_INVALID")
        deadline_ns = run.get("deadline_ns")
        prior_elapsed = run.get("elapsed_ms")
        if type(deadline_ns) is not int or type(prior_elapsed) is not int:
            raise LedgerError("GLOBAL_DEADLINE_INVALID")
        starts = []
        events = audit.get("events")
        if not isinstance(events, list):
            raise LedgerError("GLOBAL_DEADLINE_INVALID")
        for event in events:
            if event.get("event_type") == "RUN_DEADLINE_STARTED":
                try:
                    details = json.loads(event["details_json"])
                except (KeyError, TypeError, ValueError):
                    raise LedgerError("GLOBAL_DEADLINE_INVALID") from None
                starts.append(details)
        if (
            len(starts) != 1 or starts[0].get("seconds") != 3600
            or starts[0].get("deadline_ns") != deadline_ns
        ):
            raise LedgerError("GLOBAL_DEADLINE_INVALID")
        elapsed = max(0, (3600 * 1_000_000_000 - (deadline_ns - time.time_ns())) // 1_000_000)
        return max(prior_elapsed, elapsed)

    def pseudonym(self, identity: str) -> str:
        if type(identity) is not str or not identity or len(identity) > 1024:
            raise LedgerError("INVALID_IDENTITY")
        with self._transaction() as db:
            salt = db.execute("SELECT salt FROM meta WHERE singleton=1").fetchone()[0]
            return hmac.new(salt, identity.encode("utf-8"), hashlib.sha256).hexdigest()

    def register_media(self, identity: str, *, profile: str, expected_bytes: int,
                       kind: str = "DOCUMENT", fresh: bool = True) -> str:
        _enum(profile, {"F", "M"})
        _enum(kind, {"DOCUMENT"})
        if type(fresh) is not bool:
            raise LedgerError("INVALID_VALUE")
        _integer(expected_bytes, 1, 128 * MIB if profile == "F" else 2 * GIB)
        if profile == "M" and (expected_bytes < GIB or not fresh):
            raise LedgerError("MEDIA_LIMIT")
        alias = self.pseudonym(identity)
        details: dict[str, object] = {
            "alias": alias, "profile": profile, "expected_bytes": expected_bytes,
            "kind": kind, "fresh": fresh, "status": "CREATED",
        }
        stable_event_id = hashlib.sha256(
            f"{alias}:{profile}:{expected_bytes}:{kind}:{int(fresh)}".encode("ascii")
        ).hexdigest()[:32]
        with self._transaction(("MEDIA_REGISTERED", details, stable_event_id)) as db:
            row = db.execute("SELECT profile,expected,kind,fresh FROM media WHERE alias=?", (alias,)).fetchone()
            values = (profile, expected_bytes, kind, int(fresh))
            if row is not None:
                if row != values:
                    raise LedgerError("MEDIA_IDENTITY_CONFLICT")
                return alias
            if db.execute("SELECT COUNT(*) FROM media WHERE profile=?", (profile,)).fetchone()[0] >= (8 if profile == "F" else 1):
                raise LedgerError("MEDIA_LIMIT")
            db.execute("INSERT INTO media(alias,profile,expected,kind,fresh) VALUES(?,?,?,?,?)", (alias, *values))
        return alias

    def begin_scan(self, *, max_messages: int, incremental: bool = False,
                   reconcile_window: int | None = None) -> str:
        _integer(max_messages, 1, 200)
        if type(incremental) is not bool or (incremental and reconcile_window != 50) or (not incremental and reconcile_window is not None):
            raise LedgerError("SCAN_WINDOW_INVALID")
        scan_id = _new_id()
        details: dict[str, object] = {
            "scan_id": scan_id, "max_messages": max_messages,
            "incremental": incremental, "window_size": reconcile_window,
        }
        with self._transaction(("SCAN_RESERVED", details, scan_id)) as db:
            self._check_deadline(db)
            scan_state = self._epoch.state["scans"] if self._epoch and self._epoch.state else {}
            if len(scan_state) >= 3:
                raise LedgerError("SCAN_LIMIT")
            total_observed = sum(
                int(row[0]) if row[4] in {"RESERVED", "UNCERTAIN"} else int(row[3])
                for row in scan_state.values()
            )
            if total_observed + max_messages > 600:
                raise LedgerError("SCAN_LIMIT")
            db.execute("INSERT INTO scans VALUES(?,?,?,?,NULL,'RESERVED')", (scan_id, max_messages, int(incremental), reconcile_window))
        return scan_id

    def finish_scan(self, scan_id: str, observed: int) -> None:
        _token(scan_id)
        _integer(observed)
        details: dict[str, object] = {"scan_id": scan_id, "observed_messages": observed}
        with self._transaction(("SCAN_OBSERVED", details, None)) as db:
            row = db.execute("SELECT max_messages,state FROM scans WHERE scan_id=?", (scan_id,)).fetchone()
            if row is None or row[1] != "RESERVED" or observed > row[0]:
                raise LedgerError("SCAN_STATE_INVALID")
            db.execute("UPDATE scans SET observed=?, state='OBSERVED' WHERE scan_id=?", (observed, scan_id))

    @staticmethod
    def validate_queue(*, workers: int, attempts_per_media: int) -> None:
        if type(workers) is not int or type(attempts_per_media) is not int or workers != 1 or attempts_per_media != 1:
            raise LedgerError("QUEUE_LIMIT")

    def begin_attempt(self, alias: str, *, recovery: bool = False) -> int:
        _token(alias, _ALIAS)
        if type(recovery) is not bool:
            raise LedgerError("INVALID_VALUE")
        details: dict[str, object] = {"alias": alias, "recovery": recovery}
        with self._transaction(("ATTEMPT_STARTED", details, None)) as db:
            self._check_deadline(db)
            row = db.execute("SELECT profile,attempts FROM media WHERE alias=?", (alias,)).fetchone()
            if row is None or row[1] >= (3 if row[0] == "F" else 1):
                raise LedgerError("ATTEMPT_LIMIT")
            details["attempt"] = row[1] + 1
            if recovery:
                interruption, recoveries = db.execute("SELECT interruption_alias,recoveries FROM meta").fetchone()
                if row[0] != "F" or row[1] == 0 or interruption != alias or recoveries >= 1:
                    raise LedgerError("RECOVERY_LIMIT")
                db.execute("UPDATE meta SET recoveries=recoveries+1")
            db.execute("UPDATE media SET attempts=attempts+1 WHERE alias=?", (alias,))
            return row[1] + 1

    def record_interruption(
        self,
        alias: str,
        *,
        part_bytes: int | None = None,
        expected_bytes: int | None = None,
    ) -> None:
        _token(alias, _ALIAS)
        if part_bytes is not None:
            _integer(part_bytes, 1)
        if expected_bytes is not None:
            _integer(expected_bytes, 1)
        if (part_bytes is None) != (expected_bytes is None):
            raise LedgerError("INTERRUPTION_EVIDENCE_INVALID")
        if part_bytes is not None and expected_bytes is not None and part_bytes >= expected_bytes:
            raise LedgerError("INTERRUPTION_EVIDENCE_INVALID")
        details: dict[str, object] = {"alias": alias}
        if part_bytes is not None:
            details.update({
                "part_bytes": part_bytes,
                "expected_bytes": expected_bytes,
                "status": "MEASURED",
            })
        with self._transaction(("INTERRUPTION_RECORDED", details, None)) as db:
            row = db.execute("SELECT profile,attempts FROM media WHERE alias=?", (alias,)).fetchone()
            if row is None or row[0] != "F" or row[1] < 1 or db.execute("SELECT interruptions FROM meta").fetchone()[0] >= 1:
                raise LedgerError("INTERRUPTION_LIMIT")
            db.execute("UPDATE meta SET interruptions=interruptions+1,interruption_alias=?", (alias,))

    def reserve_bytes(self, alias: str, amount: int, *, reservation_id: str | None = None) -> str:
        _token(alias, _ALIAS)
        _integer(amount, 1, TOTAL_CAP)
        rid = _token(reservation_id) if reservation_id is not None else _new_id()
        details: dict[str, object] = {
            "reservation_id": rid, "alias": alias, "amount_bytes": amount,
        }
        with self._transaction(("BYTES_RESERVED", details, rid)) as db:
            self._check_deadline(db)
            media = db.execute("SELECT profile,attempts FROM media WHERE alias=?", (alias,)).fetchone()
            if media is None or media[1] < 1:
                raise LedgerError("ATTEMPT_REQUIRED")
            details["profile"] = media[0]
            if db.execute("SELECT 1 FROM reservations WHERE reservation_id=?", (rid,)).fetchone():
                raise LedgerError("DUPLICATE_RESERVATION")
            epoch_state = self._epoch.state if self._epoch is not None else None
            if epoch_state is None:
                raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
            profile_budget = epoch_state["budgets"][media[0]]
            profile_cap = F_CAP
            if media[0] == "M":
                m_item = next(
                    (row for row in epoch_state["media"].values() if row[0] == "M"),
                    None,
                )
                profile_cap = media_m_cap(int(m_item[1])) if m_item is not None else 0
            profile_used = sum(profile_budget[key] for key in ("reserved", "observed", "uncertain"))
            aggregate_used = sum(
                sum(budget[key] for key in ("reserved", "observed", "uncertain"))
                for budget in epoch_state["budgets"].values()
            )
            if profile_used + amount > profile_cap or aggregate_used + amount > TOTAL_CAP:
                raise LedgerError("BUDGET_EXCEEDED")
            db.execute("INSERT INTO reservations VALUES(?,?,?,?,NULL,'RESERVED','RESERVED',?,'NONE')", (rid, alias, media[0], amount, self._session_id))
        return rid

    def settle_bytes(
        self,
        reservation_id: str,
        *,
        observed: int | None = None,
        measurement_source: str | None = None,
    ) -> None:
        _token(reservation_id)
        if observed is not None:
            _integer(observed)
            if measurement_source not in {"SYNTHETIC_TEST", "GATEWAY_RESPONSE"}:
                raise LedgerError("TRUSTED_BYTE_SOURCE_UNAVAILABLE")
        elif measurement_source is not None:
            raise LedgerError("RESERVATION_SOURCE_INVALID")
        details: dict[str, object] = {
            "reservation_id": reservation_id, "observed_bytes": observed,
            "status": "UNKNOWN" if observed is None else "MEASURED",
            "measurement_source": "UNKNOWN" if observed is None else measurement_source,
        }
        with self._transaction(("BYTES_SETTLED", details, None)) as db:
            row = db.execute("SELECT amount,state,owner_token FROM reservations WHERE reservation_id=?", (reservation_id,)).fetchone()
            if row is None or row[1] != "RESERVED" or (observed is not None and observed > row[0]):
                raise LedgerError("RESERVATION_STATE_INVALID")
            if observed is not None and row[2] != self._session_id:
                raise LedgerError("RESERVATION_OWNER_LOST")
            state, origin = ("UNCERTAIN", "UNKNOWN") if observed is None else ("OBSERVED", "MEASURED")
            source = "UNKNOWN" if observed is None else measurement_source
            db.execute("UPDATE reservations SET state=?,origin=?,observed=?,measurement_source=? WHERE reservation_id=?", (state, origin, observed, source, reservation_id))

    def _charge_unresolved_reservations_after_containment(self) -> int:
        """Charge remaining leases uncertain after the supervisor confirms exit."""
        snapshot = self.snapshot()
        if snapshot["critical_audit"]["quarantined"]:
            raise LedgerError("CRITICAL_AUDIT_QUARANTINED")
        unresolved = [
            row["reservation_id"] for row in snapshot["reservations"]
            if row["state"] == "RESERVED"
        ]
        for reservation_id in unresolved:
            self.settle_bytes(reservation_id)
        return len(unresolved)

    def check_disk(self, path: str | Path, *, pending_bytes: int,
                   free_space: Callable[[str | Path], int] | None = None) -> dict[str, int]:
        pending = _integer(pending_bytes)
        margin = max(GIB, (pending + 9) // 10)
        required = pending + margin + DISK_RESERVE
        if required > 2**63 - 1:
            raise LedgerError("INVALID_NUMBER")
        try:
            available = _integer((free_space or (lambda p: shutil.disk_usage(p).free))(path))
        except Exception:
            check_id = _new_id()
            checked_ns = time.time_ns()
            details: dict[str, object] = {
                "pending_bytes": pending, "available_bytes": None,
                "margin_bytes": margin, "extra_bytes": DISK_RESERVE,
                "checked_ns": checked_ns, "check_id": check_id,
                "available_origin": "UNKNOWN", "margin_origin": "DERIVED",
                "status": "UNKNOWN",
            }
            with self._transaction(("DISK_CHECKED", details, check_id)) as db:
                db.execute("INSERT INTO disk_checks VALUES(?,?,?,?,?,?,?,?)", (check_id, pending, None, margin, DISK_RESERVE, checked_ns, "UNKNOWN", "DERIVED"))
            raise LedgerError("DISK_QUERY_FAILED") from None
        check_id = _new_id()
        checked_ns = time.time_ns()
        details = {
            "pending_bytes": pending, "available_bytes": available,
            "margin_bytes": margin, "extra_bytes": DISK_RESERVE,
            "checked_ns": checked_ns, "check_id": check_id,
            "available_origin": "MEASURED", "margin_origin": "DERIVED",
            "status": "MEASURED",
        }
        with self._transaction(("DISK_CHECKED", details, check_id)) as db:
            db.execute("INSERT INTO disk_checks VALUES(?,?,?,?,?,?,?,?)", (check_id, pending, available, margin, DISK_RESERVE, checked_ns, "MEASURED", "DERIVED"))
        if available < required:
            raise LedgerError("INSUFFICIENT_DISK_SPACE")
        return {"available": available, "pending": pending, "margin": margin, "extra": DISK_RESERVE, "required": required}

    def update_execution(self, *, gate: str, status: str, elapsed_ms: int,
                         deadline_ns: int | None = None, process_state: str = "UNKNOWN",
                         result: str = "UNKNOWN", cause: str = "NONE",
                         working_set: int | None = None, peak_working_set: int | None = None,
                         private_bytes: int | None = None,
                         observed_bytes: int | None = None) -> None:
        _enum(gate, {f"G{i}" for i in range(10)})
        _enum(status, {"PLANNED", "RUNNING", "COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "BLOCKED"})
        _enum(process_state, {"UNKNOWN", "RUNNING", "EXITED", "CONTAINED", "UNCONTAINED"})
        _enum(result, {
            "UNKNOWN", "PASS", "FAIL", "PARTIAL", "BLOCKED", "CANCELLED",
            "OFFLINE_SYNTHETIC_PASS", "REAL_CONTRACTUAL_PASS",
            "REAL_EVIDENCE_PENDING",
        })
        _enum(cause, {"NONE", "TIMEOUT", "DEADLINE", "MEMORY", "DISK", "FLOODWAIT", "CANCELLED", "LEDGER", "PROCESS", "OTHER"})
        if cause == "FLOODWAIT" and status != "BLOCKED":
            raise LedgerError("FLOODWAIT_MUST_STOP_RUN")
        _integer(elapsed_ms)
        if deadline_ns is not None:
            _integer(deadline_ns, 1)
        for number in (working_set, peak_working_set, private_bytes):
            if number is not None:
                _integer(number)
        if observed_bytes is not None:
            _integer(observed_bytes)
        if any(x is None for x in (working_set, peak_working_set, private_bytes)) and any(x is not None for x in (working_set, peak_working_set, private_bytes)):
            raise LedgerError("MEMORY_MEASUREMENT_INCOMPLETE")
        if working_set is not None and peak_working_set < working_set:
            raise LedgerError("MEMORY_MEASUREMENT_INVALID")
        event_type = "RUN_TERMINAL" if status in _TERMINAL else "GATE_STATE_UPDATED"
        details: dict[str, object] = {
            "gate": gate, "status": status, "deadline_ns": deadline_ns,
            "elapsed_ms": elapsed_ms,
            "process_state": process_state, "result": result, "cause": cause,
            "working_set_bytes": working_set, "peak_working_set_bytes": peak_working_set,
            "private_bytes": private_bytes, "observed_bytes": observed_bytes,
        }
        with self._transaction((event_type, details, None)) as db:
            previous = db.execute("SELECT elapsed_ms,deadline_ns,status,cause FROM meta").fetchone()
            if elapsed_ms < previous[0] or deadline_ns != previous[1]:
                raise LedgerError("DEADLINE_OR_TIME_INVALID")
            if previous[3] == "FLOODWAIT" and (status != "BLOCKED" or cause != "FLOODWAIT"):
                raise LedgerError("FLOODWAIT_ALREADY_OBSERVED")
            if previous[2] in _TERMINAL and (status != previous[2] or cause != previous[3]):
                raise LedgerError("TERMINAL_STATE_LOCKED")
            if status == "RUNNING":
                self._check_deadline(db, require_running=False)
            if status in _TERMINAL:
                db.execute("UPDATE reservations SET state='UNCERTAIN',origin='UNKNOWN',measurement_source='UNKNOWN' WHERE state='RESERVED'")
                db.execute("UPDATE scans SET state='UNCERTAIN' WHERE state='RESERVED'")
            if working_set is None:
                db.execute("UPDATE meta SET gate=?,status=?,elapsed_ms=?,deadline_ns=?,process_state=?,result=?,cause=?", (gate, status, elapsed_ms, deadline_ns, process_state, result, cause))
            else:
                previous_peak = db.execute("SELECT peak_working_set FROM meta").fetchone()[0]
                db.execute("UPDATE meta SET gate=?,status=?,elapsed_ms=?,deadline_ns=?,process_state=?,result=?,cause=?,working_set=?,peak_working_set=?,private_bytes=?,memory_origin='MEASURED',memory_measured_ns=?", (gate, status, elapsed_ms, deadline_ns, process_state, result, cause, working_set, max(peak_working_set, previous_peak or 0), private_bytes, time.time_ns()))

    def snapshot(self) -> dict[str, object]:
        epoch = self._epoch
        if epoch is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        with epoch.mutex:
            self._refresh_if_data_version_changed()
            self._guard_epoch()
            state = epoch.state
            assert state is not None
            meta_row = state["meta"]
            meta = {
                "run_id": meta_row[2], "created_ns": meta_row[4], "gate": meta_row[5],
                "status": meta_row[6], "deadline_ns": meta_row[7],
                "elapsed_ms": meta_row[8], "process_state": meta_row[9],
                "result": meta_row[10], "cause": meta_row[11],
                "working_set": meta_row[12], "peak_working_set": meta_row[13],
                "private_bytes": meta_row[14], "memory_origin": meta_row[15],
                "memory_measured_ns": meta_row[19], "interruptions": meta_row[16],
                "recoveries": meta_row[17],
            }
            media = [
                dict(zip(("alias", "profile", "expected", "kind", "fresh", "attempts"), (alias, *row)))
                for alias, row in sorted(state["media"].items())
            ]
            scans = [
                dict(zip(("scan_id", "max_messages", "incremental", "window_size", "observed", "state"), (scan_id, *row)))
                for scan_id, row in state["scans"].items()
            ]
            entries = [
                dict(zip(("reservation_id", "alias", "profile", "amount", "observed", "state", "origin", "measurement_source"), (rid, *row[:6], row[7])))
                for rid, row in state["reservations"].items()
            ]
            disk = [
                dict(zip(("check_id", "pending", "available", "margin", "extra", "checked_ns", "available_origin", "margin_origin"), (check_id, *row)))
                for check_id, row in state["disk_checks"].items()
            ]
            audit = [dict(row) for row in state["audit"]]
            budget_state = {key: dict(value) for key, value in state["budgets"].items()}
            head_sequence = int(state["head_sequence"])
            head_hash = str(state["head_hash"])
            quarantined = self._critical_audit_failed
        if self.path.with_name(self.path.name + ".quarantine").is_file():
            quarantined = True
        raw_result = meta["result"]
        result_provenance: dict[str, object] = {
            "evidence_origin": "UNKNOWN",
            "offline_result": "UNKNOWN",
            "real_evidence_status": "REAL_EVIDENCE_PENDING",
        }
        if meta["gate"] == "G9" and meta["status"] in _TERMINAL:
            g9_finished: list[dict[str, object]] = []
            for event in audit:
                if event["event_type"] != "GATE_FINISHED":
                    continue
                try:
                    details = json.loads(event["details_json"])
                except (TypeError, ValueError):
                    continue
                if type(details) is dict and details.get("gate") == "G9":
                    g9_finished.append(details)
            offline_proof = any(
                details.get("result") in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
                and details.get("evidence_origin") in {
                    "OFFLINE_SYNTHETIC", "SYNTHETIC",
                }
                and details.get("offline_result") == "OFFLINE_SYNTHETIC_PASS"
                and details.get("real_evidence_status") == "REAL_EVIDENCE_PENDING"
                for details in g9_finished
            )
            real_proof = any(
                details.get("result") in {"PASS", "REAL_CONTRACTUAL_PASS"}
                and details.get("evidence_origin") == "REAL_CONTRACTUAL"
                and details.get("real_evidence_status") == "REAL_CONTRACTUAL_PASS"
                for details in g9_finished
            )
            if raw_result == "OFFLINE_SYNTHETIC_PASS" and offline_proof:
                result_provenance = {
                    "evidence_origin": "OFFLINE_SYNTHETIC",
                    "offline_result": "OFFLINE_SYNTHETIC_PASS",
                    "real_evidence_status": "REAL_EVIDENCE_PENDING",
                }
            elif raw_result == "REAL_CONTRACTUAL_PASS" and real_proof:
                result_provenance = {
                    "evidence_origin": "REAL_CONTRACTUAL",
                    "offline_result": "UNKNOWN",
                    "real_evidence_status": "REAL_CONTRACTUAL_PASS",
                }
            elif raw_result in {"PASS", "OFFLINE_SYNTHETIC_PASS", "REAL_CONTRACTUAL_PASS"}:
                # Old terminal PASS values have no durable provenance. Keep
                # them from looking like real contractual acceptance to readers.
                meta["result"] = "REAL_EVIDENCE_PENDING"
            else:
                latest = g9_finished[-1] if g9_finished else {}
                result_provenance = {
                    "evidence_origin": latest.get("evidence_origin", "UNKNOWN"),
                    "offline_result": latest.get("offline_result", raw_result),
                    "real_evidence_status": latest.get(
                        "real_evidence_status", "REAL_EVIDENCE_PENDING",
                    ),
                }
        meta["result_provenance"] = result_provenance
        budgets = {}
        for profile in ("F", "M"):
            observed = budget_state[profile]["observed"]
            reserved = budget_state[profile]["reserved"]
            uncertain = budget_state[profile]["uncertain"]
            cap = F_CAP if profile == "F" else media_m_cap(next((m["expected"] for m in media if m["profile"] == "M"), GIB)) if any(m["profile"] == "M" for m in media) else 0
            consumed = observed + uncertain
            budgets[profile] = {"cap": cap, "planned": budget_state[profile]["planned"], "reserved": reserved, "observed": observed, "uncertain": uncertain, "consumed": consumed, "remaining": cap - consumed - reserved}
        return {
            "run": meta, "media": media, "scans": scans, "reservations": entries,
            "disk_checks": disk, "budgets": budgets,
            "aggregate_remaining": TOTAL_CAP - sum(b["consumed"] + b["reserved"] for b in budgets.values()),
            "critical_audit": {
                "event_count": len(audit),
                "head_hash": head_hash,
                "head_sequence": head_sequence,
                "events": audit,
                "quarantined": quarantined,
                "quarantine_durable": self.path.with_name(self.path.name + ".quarantine").is_file(),
            },
        }

    def record_critical_event(
        self, event_type: str, *, details: dict[str, object], event_id: str,
    ) -> dict[str, object]:
        """Persist and sync one idempotent, sanitized event before acknowledging it."""
        if self._critical_audit_failed:
            raise LedgerError("CRITICAL_AUDIT_QUARANTINED")
        _enum(event_type, _AUDIT_EVENT_TYPES)
        event_id = _token(event_id)
        details = json.loads(_audit_details(details, event_type=event_type))
        try:
            with self._transaction((event_type, details, event_id)):
                pass
            return self.audit_ack(event_id).as_dict()
        except LedgerError as error:
            if error.args != ("AUDIT_EVENT_INVALID",):
                self._quarantine()
            raise

    def audit_ack(self, event_id: str) -> AuditAck:
        event_id = _token(event_id)
        epoch = self._epoch
        if epoch is None:
            raise LedgerError("LEDGER_WRITER_EPOCH_INACTIVE")
        with epoch.mutex:
            self._refresh_if_data_version_changed()
            self._guard_epoch(for_ack=True)
            state = epoch.state
            assert state is not None
            row = state["audit_by_id"].get(event_id)
            if row is None:
                raise LedgerError("AUDIT_ACK_UNAVAILABLE")
            return AuditAck(state["meta"][2], event_id, row["sequence"], row["event_hash"])


QueueIdentity = tuple[int, int, int]


@dataclass(frozen=True)
class QueueMediaBinding:
    """In-memory join from a planner identity to its private ledger alias."""

    alias: str
    expected_bytes: int


class S9QueueLease:
    """Persistent accounting lease paired with a single gateway request."""

    def __init__(
        self,
        ledger: S9OperationalLedger,
        reservation_id: str,
        *,
        measurement_source: str,
    ) -> None:
        self._ledger = ledger
        self._reservation_id = reservation_id
        self._measurement_source = measurement_source
        self.settled = False

    def received(self, byte_count: int) -> None:
        if self.settled:
            raise LedgerError("RESERVATION_STATE_INVALID")
        self._ledger.settle_bytes(
            self._reservation_id,
            observed=byte_count,
            measurement_source=self._measurement_source,
        )
        self.settled = True

    def release(self) -> None:
        self.received(0)

    def charge_uncertain(self) -> None:
        if self.settled:
            return
        self._ledger.settle_bytes(self._reservation_id)
        self.settled = True


class S9QueueAccounting:
    """Bridge S5 request leases to the durable S9 ledger.

    The planner identities and byte sizes stay in memory. Only their salted
    aliases and accounting events are written to the ledger. Each reservation
    is created before the gateway request and settled by the request lease's
    ``received`` callback, which the Telethon adapter invokes with the response
    payload length. Unresolved leases are conservatively chargeable.
    """

    def __init__(
        self,
        ledger: S9OperationalLedger,
        bindings: Mapping[QueueIdentity, QueueMediaBinding],
        *,
        measurement_source: str,
        recovery: bool = False,
        idempotent_recheck: bool = False,
        gate: str = "G5",
    ) -> None:
        if not isinstance(bindings, Mapping) or not bindings:
            raise LedgerError("QUEUE_PLAN_INVALID")
        if measurement_source not in {"GATEWAY_RESPONSE", "SYNTHETIC_TEST"}:
            raise LedgerError("TRUSTED_BYTE_SOURCE_UNAVAILABLE")
        if type(recovery) is not bool:
            raise LedgerError("INVALID_VALUE")
        if type(idempotent_recheck) is not bool:
            raise LedgerError("INVALID_VALUE")
        _enum(gate, {"G5", "G8"})
        validated: dict[QueueIdentity, QueueMediaBinding] = {}
        for identity, binding in bindings.items():
            if (
                type(identity) is not tuple or len(identity) != 3
                or any(type(value) is not int for value in identity)
                or not isinstance(binding, QueueMediaBinding)
            ):
                raise LedgerError("QUEUE_PLAN_INVALID")
            _token(binding.alias, _ALIAS)
            _integer(binding.expected_bytes, 1, TOTAL_CAP)
            validated[identity] = binding
        if gate == "G8" and (
            recovery and measurement_source not in {"GATEWAY_RESPONSE", "SYNTHETIC_TEST"}
            or any(
                row["profile"] == "M"
                for row in ledger.snapshot().get("media", [])
                if row.get("alias") in {item.alias for item in validated.values()}
            )
        ):
            raise LedgerError("G8_QUEUE_PLAN_INVALID")
        self.ledger = ledger
        self._bindings = validated
        self.measurement_source = measurement_source
        self.recovery = recovery
        self.idempotent_recheck = idempotent_recheck
        self.gate = gate

    @classmethod
    def register_plan(
        cls,
        ledger: S9OperationalLedger,
        plan: object,
        *,
        profile: str,
        measurement_source: str,
        recovery: bool = False,
        gate: str = "G5",
    ) -> S9QueueAccounting:
        """Register a fresh S9 plan using only salted media aliases."""
        _enum(profile, {"F", "M"})
        _enum(gate, {"G5", "G8"})
        if type(recovery) is not bool:
            raise LedgerError("INVALID_VALUE")
        if gate == "G8" and profile != "F":
            raise LedgerError("G8_PROFILE_MUST_BE_F")
        ledger.active_global_deadline()
        pending = getattr(plan, "pending", None)
        already_valid = getattr(plan, "already_valid", ())
        eligible = getattr(plan, "eligible", None)
        if (
            not isinstance(pending, (tuple, list))
            or not isinstance(already_valid, (tuple, list))
        ):
            raise LedgerError("QUEUE_PLAN_INVALID")
        if not isinstance(eligible, (tuple, list)):
            eligible = (*pending, *already_valid)
        if not eligible:
            raise LedgerError("QUEUE_PLAN_INVALID")
        snapshot = ledger.snapshot()
        run = snapshot.get("run")
        idempotent_recheck = not pending
        if gate == "G8":
            if (
                type(run) is not dict or run.get("gate") != "G8"
                or run.get("status") != "RUNNING"
                or recovery and run.get("result") != "PARTIAL"
                or not recovery and run.get("result") not in {"UNKNOWN", "PARTIAL"}
            ):
                raise LedgerError("G8_STAGE_STATE_INVALID")
            if idempotent_recheck:
                raise LedgerError("G8_IDEMPOTENT_RECHECK_INVALID")
        if idempotent_recheck:
            if (
                recovery
                or len(already_valid) != len(eligible)
                or any(getattr(item, "status", None) != "ALREADY_VALID" for item in eligible)
                or type(run) is not dict
                or run.get("gate") != "G5"
                or run.get("status") != "RUNNING"
                or run.get("result") not in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
                or any(row.get("state") == "RESERVED" for row in snapshot.get("reservations", []))
            ):
                raise LedgerError("IDEMPOTENT_RECHECK_REQUIRES_G5_PASS")
        elif not pending:
            raise LedgerError("QUEUE_PLAN_INVALID")
        if profile == "M" and (
            recovery or len(eligible) != 1
            or idempotent_recheck and len(already_valid) != 1
            or not idempotent_recheck and (
                len(pending) != 1
                or getattr(pending[0], "status", None) != "PENDING"
                or getattr(pending[0], "part_bytes", 0) != 0
            )
        ):
            raise LedgerError("MEDIA_LIMIT")
        if profile == "F" and (
            len(eligible) > 8 or recovery and len(pending) != 1
        ):
            raise LedgerError("MEDIA_LIMIT")
        bindings: dict[QueueIdentity, QueueMediaBinding] = {}
        existing_media = {
            row["alias"]: row for row in snapshot["media"]
        }
        expected_plan_items = already_valid if idempotent_recheck else eligible
        for item in expected_plan_items:
            identity = getattr(item, "identity", None)
            candidate = getattr(item, "candidate", None)
            if (
                type(identity) is not tuple or len(identity) != 3
                or any(type(value) is not int for value in identity)
                or candidate is None
            ):
                raise LedgerError("QUEUE_PLAN_INVALID")
            status = getattr(item, "status", None)
            part_bytes = getattr(item, "part_bytes", None)
            fresh = status == "PENDING" and part_bytes == 0
            if recovery and (profile != "F" or status != "CONDITIONAL_RESUME_CANDIDATE"):
                raise LedgerError("RECOVERY_STATE_INVALID")
            if not recovery and status == "CONDITIONAL_RESUME_CANDIDATE":
                raise LedgerError("RECOVERY_STATE_INVALID")
            identity_text = f"{identity[0]}:{identity[1]}:{identity[2]}"
            expected_bytes = getattr(candidate, "expected_bytes", None)
            if recovery:
                alias = ledger.pseudonym(identity_text)
                row = existing_media.get(alias)
                if (
                    row is None or row["profile"] != profile
                    or row["expected"] != expected_bytes
                    or row["kind"] != "DOCUMENT"
                    or row["attempts"] < 1
                ):
                    raise LedgerError("RECOVERY_STATE_INVALID")
            else:
                alias = ledger.pseudonym(identity_text)
                prior = existing_media.get(alias)
                if idempotent_recheck:
                    if (
                        prior is None
                        or prior["profile"] != profile
                        or prior["expected"] != expected_bytes
                        or prior["kind"] != "DOCUMENT"
                    ):
                        raise LedgerError("IDEMPOTENT_RECHECK_PLAN_MISMATCH")
                else:
                    if prior is not None and prior["attempts"] > 0:
                        raise LedgerError("RECOVERY_STATE_INVALID")
                    alias = ledger.register_media(
                        identity_text,
                        profile=profile,
                        expected_bytes=expected_bytes,
                        kind="DOCUMENT",
                        fresh=fresh,
                    )
            bindings[identity] = QueueMediaBinding(
                alias, expected_bytes,
            )
        if idempotent_recheck:
            registered_for_profile = {
                row["alias"] for row in snapshot["media"]
                if row["profile"] == profile
            }
            if {binding.alias for binding in bindings.values()} != registered_for_profile:
                raise LedgerError("IDEMPOTENT_RECHECK_PLAN_MISMATCH")
        return cls(
            ledger, bindings,
            measurement_source=measurement_source,
            recovery=recovery,
            idempotent_recheck=idempotent_recheck,
            gate=gate,
        )

    def validate_queue(self, *, workers: int, attempts_per_media: int) -> None:
        S9OperationalLedger.validate_queue(
            workers=workers, attempts_per_media=attempts_per_media,
        )
        self.ledger.active_global_deadline()

    def validate_plan(self, plan: object) -> None:
        pending = getattr(plan, "pending", None)
        already_valid = getattr(plan, "already_valid", ())
        if not isinstance(pending, (tuple, list)) or not isinstance(already_valid, (tuple, list)):
            raise LedgerError("QUEUE_PLAN_INVALID")
        selected = already_valid if self.idempotent_recheck else (*pending, *already_valid)
        if self.idempotent_recheck and (
            pending or not selected
            or any(getattr(item, "status", None) != "ALREADY_VALID" for item in selected)
        ):
            raise LedgerError("IDEMPOTENT_RECHECK_PLAN_MISMATCH")
        identities: set[QueueIdentity] = set()
        snapshot = self.ledger.snapshot()
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("media"), list):
            raise LedgerError("QUEUE_PLAN_INVALID")
        registered = {row["alias"]: row for row in snapshot["media"]}
        for item in selected:
            identity = getattr(item, "identity", None)
            candidate = getattr(item, "candidate", None)
            if (
                type(identity) is not tuple or len(identity) != 3
                or any(type(value) is not int for value in identity)
                or identity in identities or candidate is None
            ):
                raise LedgerError("QUEUE_PLAN_INVALID")
            identities.add(identity)
            binding = self._bindings.get(identity)
            if binding is None or getattr(candidate, "expected_bytes", None) != binding.expected_bytes:
                raise LedgerError("QUEUE_PLAN_MISMATCH")
            row = registered.get(binding.alias)
            if row is None or row["expected"] != binding.expected_bytes:
                raise LedgerError("QUEUE_PLAN_MISMATCH")
        if identities != set(self._bindings):
            raise LedgerError("QUEUE_PLAN_MISMATCH")

    def record_preconfirmation_pass(self) -> None:
        """Persist G4 only after the fresh plan was confirmed by the TTY user."""
        snapshot = self.ledger.snapshot()
        if snapshot["critical_audit"]["quarantined"]:
            raise LedgerError("CRITICAL_AUDIT_QUARANTINED")
        deadline_ns = self.ledger.active_global_deadline()
        current_run = snapshot["run"]
        gate_result = current_run.get("result", "UNKNOWN") if self.gate == "G8" else "PASS"
        self.ledger.update_execution(
            gate=self.gate if self.gate == "G8" else "G4", status="RUNNING",
            elapsed_ms=S9OperationalLedger.execution_elapsed_ms(snapshot),
            deadline_ns=deadline_ns, process_state="RUNNING", result=gate_result,
        )

    def begin_attempt(self, identity: QueueIdentity) -> int:
        binding = self._bindings.get(identity)
        if binding is None:
            raise LedgerError("QUEUE_PLAN_MISMATCH")
        return self.ledger.begin_attempt(binding.alias, recovery=self.recovery)

    def record_g8_interruption(
        self,
        identity: QueueIdentity,
        *,
        part_bytes: int,
    ) -> None:
        """Bind a contained interruption to measured partial bytes and F budget."""
        binding = self._bindings.get(identity)
        if self.gate != "G8" or self.recovery or binding is None:
            raise LedgerError("G8_INTERRUPTION_STATE_INVALID")
        _integer(part_bytes, 1, binding.expected_bytes - 1)
        snapshot = self.ledger.snapshot()
        if (
            snapshot["run"].get("gate") != "G8"
            or snapshot["run"].get("status") != "RUNNING"
            or snapshot["critical_audit"].get("quarantined") is not False
        ):
            raise LedgerError("G8_INTERRUPTION_STATE_INVALID")
        self.ledger.record_interruption(
            binding.alias,
            part_bytes=part_bytes,
            expected_bytes=binding.expected_bytes,
        )
        refreshed = self.ledger.snapshot()
        run = refreshed["run"]
        self.ledger.update_execution(
            gate="G8", status="RUNNING",
            elapsed_ms=S9OperationalLedger.execution_elapsed_ms(refreshed),
            deadline_ns=int(run["deadline_ns"]),
            process_state="CONTAINED", result="PARTIAL", cause="OTHER",
        )

    def record_s6_prefix_proof(self, observation: object) -> tuple[Path, str]:
        """Persist the actual typed S6 V1 prefix observation during recovery."""
        if self.gate != "G8" or not self.recovery:
            raise LedgerError("PREFIX_PROOF_OUTSIDE_G8_RECOVERY")
        from telegram_courses.s9_operational_reconciliation import (
            persist_s6_prefix_proof,
        )

        try:
            return persist_s6_prefix_proof(
                self.ledger.path.parent,
                self.ledger,
                observation,
                measurement_source=self.measurement_source,
            )
        except (OSError, TypeError, ValueError) as error:
            raise LedgerError("PREFIX_PROOF_PERSIST_FAILED") from error

    def reserve(self, identity: QueueIdentity, amount: int) -> S9QueueLease:
        binding = self._bindings.get(identity)
        if binding is None:
            raise LedgerError("QUEUE_PLAN_MISMATCH")
        reservation_id = self.ledger.reserve_bytes(binding.alias, amount)
        return S9QueueLease(
            self.ledger, reservation_id,
            measurement_source=self.measurement_source,
        )

    def check_disk(
        self,
        path: str | Path,
        *,
        pending_bytes: int,
        free_space: Callable[[str | Path], int] | None = None,
    ) -> dict[str, int]:
        """Apply the frozen S9 extra disk reserve before each queue attempt."""
        return self.ledger.check_disk(
            path, pending_bytes=pending_bytes, free_space=free_space,
        )

    def record_queue_result(
        self,
        *,
        status: str,
        result: str,
        cause: str,
        observed_bytes: int,
        elapsed_ms: int | None = None,
        process_state: str = "RUNNING",
        working_set_bytes: int | None = None,
        peak_working_set_bytes: int | None = None,
        private_bytes: int | None = None,
    ) -> None:
        """Durably record G5 while keeping the G1-G9 run active."""
        _enum(status, {"COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "BLOCKED"})
        _enum(result, {"PASS", "PARTIAL", "FAIL", "BLOCKED", "CANCELLED", "FAILED"})
        _enum(cause, {"NONE", "TIMEOUT", "DEADLINE", "MEMORY", "DISK", "FLOODWAIT", "CANCELLED", "LEDGER", "PROCESS", "OTHER"})
        _integer(observed_bytes)
        if elapsed_ms is not None:
            _integer(elapsed_ms)
            if elapsed_ms > 3_600_000:
                raise LedgerError("GLOBAL_DEADLINE_INVALID")
        _enum(process_state, {"UNKNOWN", "RUNNING", "EXITED", "CONTAINED", "UNCONTAINED"})
        memory = (working_set_bytes, peak_working_set_bytes, private_bytes)
        if any(value is not None for value in memory):
            if any(type(value) is not int or value < 0 for value in memory):
                raise LedgerError("MEMORY_MEASUREMENT_INCOMPLETE")
            if peak_working_set_bytes < working_set_bytes:
                raise LedgerError("MEMORY_MEASUREMENT_INVALID")
        snapshot = self.ledger.snapshot()
        if (
            snapshot["critical_audit"]["quarantined"]
            or any(row["state"] == "RESERVED" for row in snapshot["reservations"])
        ):
            raise LedgerError("RESERVATION_STATE_INVALID")
        run = snapshot["run"]
        deadline_ns = run["deadline_ns"]
        if run["status"] != "RUNNING" or type(deadline_ns) is not int:
            raise LedgerError("RUN_NOT_ACTIVE")
        global_elapsed_ms = S9OperationalLedger.execution_elapsed_ms(snapshot)
        if elapsed_ms is not None:
            global_elapsed_ms = max(global_elapsed_ms, elapsed_ms)
        actual_observed = sum(
            row["observed"] for row in snapshot["reservations"]
            if row["state"] == "OBSERVED"
        )
        if observed_bytes > actual_observed:
            raise LedgerError("OBSERVED_BYTES_MISMATCH")
        expected_result = {
            "COMPLETED": "PASS", "PARTIAL": "PARTIAL", "FAILED": "FAIL",
            "CANCELLED": "CANCELLED", "BLOCKED": "BLOCKED",
        }[status]
        if result != expected_result:
            raise LedgerError("QUEUE_RESULT_INVALID")
        if deadline_ns <= time.time_ns():
            run_status, execution_result, execution_cause = (
                "PARTIAL", "PARTIAL", "DEADLINE",
            )
        elif cause == "FLOODWAIT":
            run_status = "BLOCKED"
            execution_result, execution_cause = "BLOCKED", "FLOODWAIT"
        elif cause == "DEADLINE":
            run_status = "PARTIAL"
            execution_result, execution_cause = "PARTIAL", "DEADLINE"
        else:
            run_status = "RUNNING"
            execution_result, execution_cause = result, cause
        # This gate update remains nonterminal; G6-G9 still belong to the
        # enclosing run unless the frozen run-stopping causes were observed.
        # The byte field is the queue's Gateway callback total.
        self.ledger.update_execution(
            gate=self.gate, status=run_status, elapsed_ms=global_elapsed_ms,
            deadline_ns=deadline_ns, process_state=process_state,
            result=execution_result, cause=execution_cause,
            working_set=working_set_bytes,
            peak_working_set=peak_working_set_bytes,
            private_bytes=private_bytes, observed_bytes=observed_bytes,
        )
