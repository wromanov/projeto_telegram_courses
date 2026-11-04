"""Native Windows entrypoint for the bounded S9 RASMOO HML activity.

This prepares a private, per-run SQLite backup and manifest before starting
the S9 one-hour deadline. All Telegram calls remain behind the existing G0
TTY prompt; the single-item F queue remains behind the existing G4 prompt.
"""

from __future__ import annotations

import asyncio
import ctypes
import hashlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from telegram_courses.s9_operational_ledger import (
    F_CAP,
    LedgerError,
    S9OperationalLedger,
    _create_private_directory,
    _open_private_directory_guard,
    _verify_private_file,
)
from telegram_courses.s9_real_gate_producers import (
    MAX_MESSAGES_PER_SCAN,
    MAX_SCAN_OBSERVATIONS,
    GateEvidenceError,
    _unique_object,
    canonical_bytes,
    load_approved_manifest,
    read_validated_g5_queue_receipt,
    read_validated_gate_receipt,
    sha256_bytes,
    validate_manifest,
)
from telegram_courses.s9_supervisor import STAGE_TIMEOUTS_SECONDS
from telegram_courses.telethon_session import (
    _ProtectedCredentialsVault,
    _ProtectedSessionVault,
)
from telegram_courses.windows_security import WindowsSecurityApi

ACTIVITY_ID = "TELEGRAM_S9_NATIVE_WINDOWS_HML_02"
EXPECTED_PYTHON = (3, 14, 7)
EXPECTED_CONTRACT_SHA256 = (
    "BD89EEB0B9C76565FD2780926D50D40EC97255302B2A7DA46CE5676828F85EA2"
)
MIB = 1024 * 1024
MAX_SINGLE_F_MEDIA_BYTES = 128 * MIB
MANIFEST_FILENAME = "approved-manifest.json"
METRICS_FILENAME = "native-hml-metrics.json"
_HML_PRIVATE_CHILDREN = ("db", "state", "runs", "downloads", "logs")
_PRIVATE_DACL_SECURITY_INFORMATION = 0x00000004
_PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
_SE_FILE_OBJECT = 1
_FILE_ALL_ACCESS = 0x001F01FF
_OBJECT_INHERIT_ACE = 0x01
_CONTAINER_INHERIT_ACE = 0x02
_SYSTEM_SID = "S-1-5-18"
_ADMINISTRATORS_SID = "S-1-5-32-544"
_PLANNED_CATALOG_EXPECTATION = {
    "state": "PENDING_G3",
    "hierarchy_semantics": "MINIMUMS",
    "unresolved_semantics": "OBSERVE_AND_REVIEW",
}
_EXPECTED_MIGRATIONS = set(range(1, 8))


class LauncherBlocked(RuntimeError):
    """A fail-closed precondition or stage did not pass."""


def _say(key: str, value: object) -> None:
    print(f"{key}={value}", flush=True)


def _require_tty() -> None:
    try:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise LauncherBlocked("INTERACTIVE_TTY_REQUIRED")
    except (AttributeError, OSError):
        raise LauncherBlocked("INTERACTIVE_TTY_REQUIRED") from None


def _private_dir(path: Path, *, create: bool = False) -> None:
    guard = None
    try:
        guard = (
            _create_private_directory(path)
            if create
            else _open_private_directory_guard(path)
        )
        guard.verify(path)
    except (LedgerError, OSError, RuntimeError, ValueError):
        raise LauncherBlocked("PRIVATE_DIRECTORY_CHECK_FAILED") from None
    finally:
        if guard is not None:
            guard.close()


def _private_file(path: Path) -> None:
    try:
        _verify_private_file(path)
    except (LedgerError, OSError, RuntimeError, ValueError):
        raise LauncherBlocked("PRIVATE_FILE_CHECK_FAILED") from None


def _plain_directory_identity(path: Path) -> None:
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        raise LauncherBlocked("DIRECTORY_IDENTITY_CHECK_FAILED") from None
    if (
        not path.is_dir()
        or path.is_symlink()
        or getattr(info, "st_file_attributes", 0) & 0x400
        or os.path.normcase(str(path.absolute()))
        != os.path.normcase(str(resolved))
    ):
        raise LauncherBlocked("DIRECTORY_IDENTITY_CHECK_FAILED")


def _hml_private_directory_sddl(sid: str) -> str:
    return (
        f"D:P(A;OICI;FA;;;{sid})"
        f"(A;OICI;FA;;;{_SYSTEM_SID})"
        f"(A;OICI;FA;;;{_ADMINISTRATORS_SID})"
    )


def _hml_private_acl_matches(
    owner: str,
    protected: bool,
    entries: tuple[tuple[int, int, int, str], ...],
    sid: str,
) -> bool:
    expected = {
        (
            0, _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE,
            _FILE_ALL_ACCESS, sid,
        ),
        (
            0, _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE,
            _FILE_ALL_ACCESS, _SYSTEM_SID,
        ),
        (
            0, _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE,
            _FILE_ALL_ACCESS, _ADMINISTRATORS_SID,
        ),
    }
    return (
        owner == sid and protected and len(entries) == len(expected)
        and set(entries) == expected
    )


def _apply_hml_private_directory_dacl(
    path: Path,
    api: WindowsSecurityApi,
    sid: str,
) -> None:
    """Apply the same protected DACL used by S9's private-directory creator.

    This is called only for the HML root and its named direct children. It does
    not modify their parent or recurse through the tree.
    """
    sddl = _hml_private_directory_sddl(sid)
    descriptor = ctypes.c_void_p()
    try:
        convert = api.advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.restype = wintypes.BOOL
        convert.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
        ]
        if not convert(sddl, 1, ctypes.byref(descriptor), None) or not descriptor.value:
            raise LauncherBlocked("HML_PRIVATE_DACL_BUILD_FAILED")

        dacl_present = ctypes.c_int()
        dacl = ctypes.c_void_p()
        dacl_defaulted = ctypes.c_int()
        if not api.advapi32.GetSecurityDescriptorDacl(
            descriptor, ctypes.byref(dacl_present), ctypes.byref(dacl),
            ctypes.byref(dacl_defaulted),
        ) or not dacl_present.value or not dacl.value:
            raise LauncherBlocked("HML_PRIVATE_DACL_BUILD_FAILED")

        set_named = api.advapi32.SetNamedSecurityInfoW
        set_named.restype = wintypes.DWORD
        set_named.argtypes = [
            wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ]
        result = int(set_named(
            str(path), _SE_FILE_OBJECT,
            _PRIVATE_DACL_SECURITY_INFORMATION | _PROTECTED_DACL_SECURITY_INFORMATION,
            None, None, dacl, None,
        ))
        if result != 0:
            raise LauncherBlocked(f"HML_PRIVATE_DACL_APPLY_FAILED_{result}")
    except LauncherBlocked:
        raise
    except Exception:
        raise LauncherBlocked("HML_PRIVATE_DACL_APPLY_FAILED") from None
    finally:
        if descriptor.value:
            try:
                api.free(descriptor)
            except Exception:
                raise LauncherBlocked("HML_PRIVATE_DACL_DESCRIPTOR_FREE_FAILED") from None


def _ensure_hml_private_directory(path: Path, root: Path, *, create: bool) -> None:
    """Repair or create one HML directory, then require the unchanged S9 guard."""
    target = Path(path).absolute()
    root_path = Path(root).absolute()
    allowed_paths = {os.path.normcase(str(root_path))}
    allowed_paths.update(
        os.path.normcase(str(root_path / name)) for name in _HML_PRIVATE_CHILDREN
    )
    if os.path.normcase(str(target)) not in allowed_paths:
        raise LauncherBlocked("HML_ACL_REPAIR_PATH_OUT_OF_SCOPE")

    if not os.path.lexists(target):
        if not create:
            raise LauncherBlocked("HML_REQUIRED_DIRECTORY_MISSING")
        try:
            created_guard = _create_private_directory(target)
            created_guard.close()
        except (LedgerError, OSError, RuntimeError, ValueError):
            raise LauncherBlocked("HML_PRIVATE_DIRECTORY_CREATE_FAILED") from None

    _plain_directory_identity(target)
    try:
        api = WindowsSecurityApi()
        sid = api.current_user_sid()
        owner, protected, entries = api.inspect_acl(target)
    except Exception:
        raise LauncherBlocked("HML_PRIVATE_DIRECTORY_ACL_INSPECTION_FAILED") from None
    if owner != sid:
        raise LauncherBlocked("HML_PRIVATE_DIRECTORY_OWNER_MISMATCH")

    if not _hml_private_acl_matches(owner, protected, entries, sid):
        _say("HML_ACL_REPAIR", "APPLY_PROTECTED_DACL_TO_SCOPED_DIRECTORY")
        _apply_hml_private_directory_dacl(target, api, sid)

    try:
        guard = _open_private_directory_guard(target)
    except (LedgerError, OSError, RuntimeError, ValueError):
        raise LauncherBlocked("HML_PRIVATE_DIRECTORY_GUARD_FAILED_AFTER_REPAIR") from None
    try:
        guard.verify(target)
    except (LedgerError, OSError, RuntimeError, ValueError):
        raise LauncherBlocked("HML_PRIVATE_DIRECTORY_GUARD_FAILED_AFTER_REPAIR") from None
    finally:
        guard.close()


def _create_private_file(path: Path, contents: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        _private_file(path)
    except (FileExistsError, OSError, LauncherBlocked):
        raise LauncherBlocked("PRIVATE_NO_OVERWRITE_WRITE_FAILED") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _readonly_connection(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(
            path.resolve(strict=True).as_uri() + "?mode=ro",
            uri=True,
            timeout=5,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection
    except (OSError, sqlite3.Error, RuntimeError, ValueError):
        raise LauncherBlocked("SQLITE_READ_ONLY_OPEN_FAILED") from None


def _check_integrity(connection: sqlite3.Connection) -> None:
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    except sqlite3.Error:
        raise LauncherBlocked("SQLITE_INTEGRITY_QUERY_FAILED") from None
    if integrity is None or integrity[0] != "ok" or foreign_keys:
        raise LauncherBlocked("SQLITE_INTEGRITY_CHECK_FAILED")


def _schema_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        raise LauncherBlocked("SQLITE_SCHEMA_CHECK_FAILED") from None


def _source_database_snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    """Validate only the preserved source's base schema and identity hints."""
    _check_integrity(connection)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required_base = {
            "catalog_nodes", "channels", "downloads", "media_items",
            "messages", "scan_runs", "schema_migrations", "sync_checkpoints",
        }
        if not required_base.issubset(tables):
            raise LauncherBlocked("S9_SQLITE_SCHEMA_INCOMPLETE")
        versions = {
            int(row[0]) for row in connection.execute(
                "SELECT version FROM schema_migrations"
            )
        }
        if 1 not in versions or any(version < 1 or version > 7 for version in versions):
            raise LauncherBlocked("SQLITE_SCHEMA_VERSION_UNSUPPORTED")
        matches = connection.execute(
            "SELECT telegram_chat_id FROM channels "
            "WHERE lower(COALESCE(title,'')) LIKE '%rasmoo%' "
            "OR lower(COALESCE(username,'')) LIKE '%rasmoo%'"
        ).fetchall()
        channel_id = int(matches[0][0]) if len(matches) == 1 else None
        if channel_id is not None and not -(2**63) <= channel_id <= -1_000_000_000_000:
            raise LauncherBlocked("RASMOO_CHANNEL_ID_INVALID")
        return {
            "channel_id": channel_id,
            "channel_id_source": (
                "UNIQUE_LOCAL_RASMOO_MATCH" if channel_id is not None
                else "OPERATOR_PRIVATE_TTY_REQUIRED"
            ),
        }
    except LauncherBlocked:
        raise
    except (sqlite3.Error, TypeError, ValueError, IndexError):
        raise LauncherBlocked("SQLITE_SOURCE_SNAPSHOT_FAILED") from None


def _validate_migrated_schema(connection: sqlite3.Connection) -> None:
    _check_integrity(connection)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {
            "channels", "catalog_nodes", "catalog_node_identity", "catalog_runs",
            "catalog_unresolved_sources", "media_items", "messages", "scan_runs",
            "downloads", "s6_v2_attempts", "s6_v2_evidence", "schema_migrations",
            "sync_checkpoints",
        }
        if not required.issubset(tables):
            raise LauncherBlocked("S9_SQLITE_SCHEMA_INCOMPLETE")
        versions = {
            int(row[0]) for row in connection.execute(
                "SELECT version FROM schema_migrations"
            )
        }
        if versions != _EXPECTED_MIGRATIONS:
            raise LauncherBlocked("S9_SQLITE_SCHEMA_INCOMPLETE")
        media_columns = _schema_columns(connection, "media_items")
        download_columns = _schema_columns(connection, "downloads")
        if "remote_observation_state" not in media_columns:
            raise LauncherBlocked("S9_SQLITE_SCHEMA_INCOMPLETE")
        if not {
            "state", "final_path", "expected_bytes", "downloaded_bytes",
            "sha256", "updated_at",
        }.issubset(download_columns):
            raise LauncherBlocked("S9_DOWNLOAD_SCHEMA_INCOMPLETE")
    except LauncherBlocked:
        raise
    except (sqlite3.Error, TypeError, ValueError):
        raise LauncherBlocked("SQLITE_SCHEMA_CHECK_FAILED") from None


def _migrate_private_run_database(database: Path) -> None:
    """Apply the existing complete migration chain only to the run copy."""
    try:
        from telegram_courses.download_repository import DownloadRepository

        asyncio.run(DownloadRepository(database).migrate())
    except Exception:
        raise LauncherBlocked("PRIVATE_RUN_SQLITE_MIGRATION_FAILED") from None

    _private_file(database)
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(database) + suffix)
        if os.path.lexists(sidecar):
            _private_file(sidecar)
    connection = _readonly_connection(database)
    try:
        _validate_migrated_schema(connection)
    finally:
        connection.close()


def _prompt_channel_id() -> int:
    _require_tty()
    try:
        value = input(
            "Canal autorizado RASMOO — ID Telegram negativo (entrada privada): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        raise LauncherBlocked("RASMOO_CHANNEL_ID_REQUIRED") from None
    if not re.fullmatch(r"-?[0-9]+", value):
        raise LauncherBlocked("RASMOO_CHANNEL_ID_INVALID")
    try:
        channel_id = int(value, 10)
    except ValueError:
        raise LauncherBlocked("RASMOO_CHANNEL_ID_INVALID") from None
    if not -(2**63) <= channel_id <= -1_000_000_000_000:
        raise LauncherBlocked("RASMOO_CHANNEL_ID_INVALID")
    _say("CHANNEL_ID_SOURCE", "OPERATOR_PRIVATE_TTY")
    return channel_id


def _catalog_snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    _check_integrity(connection)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not {
            "channels",
            "catalog_nodes",
            "catalog_runs",
            "catalog_unresolved_sources",
            "media_items",
            "downloads",
        }.issubset(tables):
            raise LauncherBlocked("S9_SQLITE_SCHEMA_INCOMPLETE")
        media_columns = _schema_columns(connection, "media_items")
        download_columns = _schema_columns(connection, "downloads")
        if "remote_observation_state" not in media_columns or not {
            "state",
            "final_path",
            "expected_bytes",
            "downloaded_bytes",
            "sha256",
            "updated_at",
        }.issubset(download_columns):
            raise LauncherBlocked("S9_DOWNLOAD_SCHEMA_INCOMPLETE")
        matches = connection.execute(
            "SELECT telegram_chat_id,title,username FROM channels "
            "WHERE lower(COALESCE(title,'')) LIKE '%rasmoo%' "
            "OR lower(COALESCE(username,'')) LIKE '%rasmoo%'"
        ).fetchall()
        if len(matches) != 1:
            raise LauncherBlocked("RASMOO_CHANNEL_NOT_UNIQUE_IN_SQLITE")
        channel = matches[0]
        channel_id = int(channel[0])
        if channel_id > -1_000_000_000_000:
            raise LauncherBlocked("RASMOO_CHANNEL_ID_INVALID")
        counts = {"TRACK": 0, "COURSE": 0, "MODULE": 0}
        for row in connection.execute(
            "SELECT upper(kind),COUNT(*) FROM catalog_nodes "
            "WHERE channel_id=? AND is_active=1 GROUP BY upper(kind)",
            (channel_id,),
        ):
            if row[0] in counts:
                counts[str(row[0])] = int(row[1])
        latest = connection.execute(
            "SELECT id,status,unresolved_count FROM catalog_runs "
            "WHERE channel_id=? ORDER BY finished_at DESC LIMIT 1",
            (channel_id,),
        ).fetchone()
        if latest is None or latest[1] != "COMPLETE":
            raise LauncherBlocked("RASMOO_CATALOG_RUN_NOT_COMPLETE")
        unresolved = int(connection.execute(
            "SELECT COUNT(*) FROM catalog_unresolved_sources WHERE run_id=?",
            (latest[0],),
        ).fetchone()[0])
        if unresolved != int(latest[2]):
            raise LauncherBlocked("RASMOO_UNRESOLVED_COUNT_DIVERGENCE")
        if (
            counts["TRACK"] < 1
            or counts["COURSE"] < 2
            or counts["MODULE"] < 2
            or any(count < 0 or count > MAX_SCAN_OBSERVATIONS for count in counts.values())
        ):
            raise LauncherBlocked("RASMOO_ACCEPTANCE_SAMPLE_NOT_PRESENT")
        return {
            "channel_id": channel_id,
            "channel_alias": "RASMOO",
            "hierarchy": counts,
            "unresolved_count": unresolved,
        }
    except LauncherBlocked:
        raise
    except (sqlite3.Error, TypeError, ValueError, IndexError):
        raise LauncherBlocked("RASMOO_CATALOG_SNAPSHOT_FAILED") from None


def _check_dpapi_artifact(vault: Any) -> None:
    try:
        path = Path(vault._path)
        parent = path.parent
        for directory in (parent.parent, parent):
            info = directory.lstat()
            resolved = directory.resolve(strict=True)
            if (
                not directory.is_dir()
                or directory.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400
                or os.path.normcase(str(directory.absolute()))
                != os.path.normcase(str(resolved))
            ):
                raise LauncherBlocked("DPAPI_DIRECTORY_UNSAFE")
        parent_attributes = vault._api.attributes(parent)
        if parent_attributes is None or not parent.is_dir():
            raise LauncherBlocked("DPAPI_DIRECTORY_UNAVAILABLE")
        try:
            vault._verify_acl(parent, is_directory=True)
        except Exception:
            raise LauncherBlocked("DPAPI_PARENT_ACL_GUARD_FAILED") from None
        if not vault._existing_blob():
            raise LauncherBlocked("DPAPI_ARTIFACT_MISSING_OR_FILE_ACL_FAILED")
    except LauncherBlocked:
        raise
    except Exception:
        raise LauncherBlocked("DPAPI_ARTIFACT_OR_ACL_CHECK_FAILED") from None


def _preflight(repo_root: Path) -> tuple[Path, Path, Path, dict[str, Any]]:
    if os.name != "nt":
        raise LauncherBlocked("NATIVE_WINDOWS_REQUIRED")
    if sys.version_info[:3] != EXPECTED_PYTHON:
        raise LauncherBlocked("PYTHON_3_14_7_REQUIRED")
    _require_tty()
    contract = repo_root / "docs" / "contracts" / (
        "S9_RASMOO_REAL_CHANNEL_ACCEPTANCE_CONTRACT_2026-10-28.md"
    )
    try:
        contract_hash = hashlib.sha256(contract.read_bytes()).hexdigest().upper()
    except OSError:
        raise LauncherBlocked("S9_CONTRACT_UNAVAILABLE") from None
    if contract_hash != EXPECTED_CONTRACT_SHA256:
        raise LauncherBlocked("S9_CONTRACT_HASH_MISMATCH")
    if (
        F_CAP != 536_870_912
        or MAX_MESSAGES_PER_SCAN != 200
        or MAX_SCAN_OBSERVATIONS != 600
        or STAGE_TIMEOUTS_SECONDS.get("scan") != 120
        or STAGE_TIMEOUTS_SECONDS.get("catalog") != 60
        or STAGE_TIMEOUTS_SECONDS.get("queue_f") != 600
    ):
        raise LauncherBlocked("S9_LIMIT_SOURCE_MISMATCH")

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise LauncherBlocked("LOCALAPPDATA_UNAVAILABLE")
    local_root = Path(local_app_data)
    try:
        resolved_local = local_root.resolve(strict=True)
        repo_resolved = repo_root.resolve(strict=True)
        local_info = local_root.lstat()
    except (OSError, RuntimeError, ValueError):
        raise LauncherBlocked("LOCALAPPDATA_PATH_UNSAFE") from None
    if (
        not local_root.is_absolute()
        or not resolved_local.drive
        or not local_root.is_dir()
        or local_root.is_symlink()
        or getattr(local_info, "st_file_attributes", 0) & 0x400
        or os.path.normcase(str(local_root.absolute()))
        != os.path.normcase(str(resolved_local))
        or resolved_local == repo_resolved
        or repo_resolved in resolved_local.parents
        or local_app_data.startswith(("\\\\", "//"))
    ):
        raise LauncherBlocked("LOCALAPPDATA_PATH_UNSAFE")

    root = resolved_local / "telegram_courses" / "S9-HML-02"
    main_parent = resolved_local / "telegram_courses"
    _plain_directory_identity(main_parent)
    # Validate the DPAPI-owning parent before changing any HML ACL. This is
    # read-only and deliberately does not repair telegram_courses.
    _check_dpapi_artifact(_ProtectedSessionVault())
    _check_dpapi_artifact(_ProtectedCredentialsVault())
    database_directory = root / "db"
    database = database_directory / "catalog.sqlite3"
    state_directory = root / "state"
    _ensure_hml_private_directory(root, root, create=False)
    for child_name in _HML_PRIVATE_CHILDREN:
        _ensure_hml_private_directory(
            root / child_name,
            root,
            create=child_name != "db",
        )
    _say("PRIVATE_DIRECTORY_GUARD", "PASS / S9-HML-02 root and named children")
    _private_file(database)
    _say("PRIVATE_SQLITE_FILE", "PASS / source preserved; read-only validation")
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(database) + suffix)
        if os.path.lexists(sidecar):
            _private_file(sidecar)
    connection = _readonly_connection(database)
    try:
        snapshot = _source_database_snapshot(connection)
    finally:
        connection.close()
    _say("SOURCE_SQLITE", "PASS / read-only base-schema and integrity checks")
    return root, database, state_directory, snapshot


def _load_or_create_manifest(
    state_directory: Path, snapshot: dict[str, Any]
) -> tuple[dict[str, Any], str, str]:
    manifest_path = state_directory / MANIFEST_FILENAME
    if manifest_path.exists():
        _private_file(manifest_path)
        try:
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8"),
                object_pairs_hook=_unique_object,
            )
            validated, manifest_hash, scope_hash = validate_manifest(manifest)
        except (OSError, UnicodeError, json.JSONDecodeError, GateEvidenceError, ValueError):
            raise LauncherBlocked("EXISTING_MANIFEST_INVALID") from None
        if (
            validated.get("channel_alias") != "RASMOO"
            or validated.get("scope", {}).get("target_alias") != "RASMOO"
            or (
                snapshot.get("channel_id") is not None
                and validated.get("channel_id") != snapshot["channel_id"]
            )
        ):
            raise LauncherBlocked("EXISTING_MANIFEST_DOES_NOT_MATCH_SQLITE")
        _say("MANIFEST_SOURCE", "EXISTING_APPROVED_PRIVATE_FILE")
        _say("MANIFEST_STATUS", "G0_RECONFIRMATION_REQUIRED_FOR_THIS_RUN")
        return validated, manifest_hash, scope_hash

    channel_id = snapshot.get("channel_id")
    if channel_id is None:
        channel_id = _prompt_channel_id()
    scope: dict[str, object] = {
        "target_alias": "RASMOO",
        "max_messages_per_scan": MAX_MESSAGES_PER_SCAN,
        "max_scan_observations": MAX_SCAN_OBSERVATIONS,
        "max_media_items": 1,
        "max_single_media_bytes": MAX_SINGLE_F_MEDIA_BYTES,
        "max_transfer_bytes": F_CAP,
        "workers": 1,
        "attempts_per_media": 1,
        "integrity_mode": "REMOTE_HASH_REQUIRED",
    }
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "channel_id": channel_id,
        "channel_alias": "RASMOO",
        "scope": scope,
        "catalog_expectation": dict(_PLANNED_CATALOG_EXPECTATION),
        "hierarchy": {"TRACK": 1, "COURSE": 2, "MODULE": 2},
        "unresolved_count": None,
        "scope_approval": {
            # Frozen S9's loader requires this structural marker. It is not a
            # G0 receipt or approval evidence; the run's TTY G0 remains decisive.
            "decision": "APPROVED",
            "confirmation_source": "G0_HUMAN_CONFIRMATION",
            "scope_sha256": sha256_bytes(canonical_bytes(scope)),
        },
    }
    try:
        validated, manifest_hash, scope_hash = validate_manifest(manifest)
    except (GateEvidenceError, ValueError):
        raise LauncherBlocked("OFFLINE_MANIFEST_PROPOSAL_INVALID") from None
    _say("MANIFEST_PROPOSAL", "private target and S9 limits; no Telegram call")
    _say("MANIFEST_STATUS", "PROPOSAL_ONLY_UNTIL_INTERACTIVE_G0")
    _say("CHANNEL_ALIAS", "RASMOO")
    _say("CATALOG_EXPECTATION", "PENDING_G3 / no observed catalog counts claimed")
    _say("HIERARCHY_MINIMUMS_TRACK_COURSE_MODULE", "/".join(
        str(validated["hierarchy"][key]) for key in ("TRACK", "COURSE", "MODULE")
    ))
    _say("UNRESOLVED_SOURCES", "OBSERVE_AND_REVIEW_AT_G3")
    _say("MANIFEST_SHA256", manifest_hash)
    _say("MANIFEST_SCOPE_APPROVAL", "NOT_GRANTED; review and approval happen at G0")
    _say("S9_SCHEMA_MARKER", "G0_HUMAN_CONFIRMATION_REQUIRED; not gate evidence")
    _create_private_file(manifest_path, canonical_bytes(validated))
    return validated, manifest_hash, scope_hash


def _create_run_tree(root: Path, database: Path, manifest: dict[str, Any], manifest_hash: str) -> tuple[Path, Path, dict[str, str]]:
    runs_directory = root / "runs"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_directory = runs_directory / f"{stamp}-{secrets.token_hex(6)}"
    _private_dir(run_directory, create=True)
    stage_names = ("work-g1", "work-g2", "work-g3", "work-g5", "downloads")
    stage_directories: dict[str, str] = {}
    try:
        for name in stage_names:
            path = run_directory / name
            _private_dir(path, create=True)
            stage_directories[name] = str(path)
        _say("NEW_RUN_DIRECTORY_GUARD", "PASS / run and child directories were created by the S9 private creator")
        run_database = run_directory / database.name
        if run_database.exists():
            raise LauncherBlocked("RUN_DATABASE_ALREADY_EXISTS")
        source = _readonly_connection(database)
        destination: sqlite3.Connection | None = None
        try:
            destination = sqlite3.connect(str(run_database), timeout=5)
            source.backup(destination)
        except (OSError, sqlite3.Error):
            raise LauncherBlocked("SQLITE_ONLINE_BACKUP_FAILED") from None
        finally:
            source.close()
            if destination is not None:
                destination.close()
        _private_file(run_database)
        _say("RUN_SQLITE_FILE", "PASS / consistent online backup; source database untouched")
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(str(run_database) + suffix)
            if sidecar.exists():
                _private_file(sidecar)
        _migrate_private_run_database(run_database)
        _say(
            "PRIVATE_RUN_SQLITE_MIGRATION",
            "PASS / official migrations 1..7 applied to the private run copy",
        )
        copied_manifest = run_directory / MANIFEST_FILENAME
        _create_private_file(
            copied_manifest,
            (root / "state" / MANIFEST_FILENAME).read_bytes(),
        )
        copied, copied_hash, _scope_hash = load_approved_manifest(run_directory)
        if copied_hash != manifest_hash or copied != manifest:
            raise LauncherBlocked("RUN_MANIFEST_COPY_DIVERGED")
        clone = _readonly_connection(run_database)
        try:
            if manifest.get("catalog_expectation") is not None:
                _validate_migrated_schema(clone)
            else:
                cloned_snapshot = _catalog_snapshot(clone)
        finally:
            clone.close()
        if manifest.get("catalog_expectation") is None and (
            cloned_snapshot["channel_id"] != manifest["channel_id"]
            or cloned_snapshot["hierarchy"] != manifest["hierarchy"]
            or cloned_snapshot["unresolved_count"] != manifest["unresolved_count"]
        ):
            raise LauncherBlocked("RUN_SQLITE_BACKUP_DIVERGED_FROM_MANIFEST")
        _say("LAUNCHER_PREFLIGHT", "PASS / private migrated SQLite, ACL, DPAPI, and limits")
        return run_directory, run_database, stage_directories
    except Exception:
        # Keep the private no-overwrite run directory as forensic evidence.
        raise


def _run_context(run_directory: Path):
    from telegram_courses.s9_supervisor_cli import load_supervised_run_context

    try:
        return load_supervised_run_context(run_directory)
    except Exception:
        raise LauncherBlocked("S9_RUN_CONTEXT_INVALID") from None


def _run_stage(arguments: list[str], *, label: str, ledger: S9OperationalLedger) -> None:
    _say("STAGE", label)
    ledger.release_writer_ownership()
    try:
        completed = subprocess.run(arguments, cwd=Path(__file__).resolve().parents[1])
    except OSError:
        raise LauncherBlocked(f"{label}_PROCESS_START_FAILED") from None
    if completed.returncode != 0:
        raise LauncherBlocked(f"{label}_DID_NOT_PASS_EXIT_{completed.returncode}")
    ledger.reacquire_writer_ownership()


class _TransferMonitor:
    """Read-only 200 ms sampler for the one new S4 download row."""

    def __init__(self, database: Path, channel_id: int) -> None:
        self.database = database
        self.channel_id = channel_id
        self.baseline: dict[int, tuple[str, int, str | None]] = {}
        self.active_started: dict[int, float] = {}
        self.active_finished: dict[int, float] = {}
        self.connection: sqlite3.Connection | None = None
        try:
            self.connection = sqlite3.connect(
                database.resolve(strict=True).as_uri() + "?mode=ro",
                uri=True,
                timeout=0.25,
            )
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA query_only=ON")
            self.connection.execute("PRAGMA busy_timeout=250")
            for row in self._rows():
                self.baseline[int(row["id"])] = (
                    str(row["state"]), int(row["downloaded_bytes"]), row["updated_at"]
                )
        except (OSError, sqlite3.Error, TypeError, ValueError):
            self.close()
            raise LauncherBlocked("TRANSFER_MONITOR_READ_ONLY_SETUP_FAILED") from None

    def _rows(self) -> list[sqlite3.Row]:
        if self.connection is None:
            return []
        return self.connection.execute(
            "SELECT m.id,d.state,d.downloaded_bytes,d.expected_bytes,d.updated_at "
            "FROM media_items m JOIN downloads d ON d.media_item_id=m.id "
            "WHERE m.channel_id=?",
            (self.channel_id,),
        ).fetchall()

    def sample(self) -> None:
        try:
            now = time.perf_counter()
            for row in self._rows():
                media_id = int(row["id"])
                state = str(row["state"])
                baseline = self.baseline.get(media_id)
                changed = baseline is None or state != baseline[0] or row["updated_at"] != baseline[2]
                if changed and state == "DOWNLOADING":
                    self.active_started.setdefault(media_id, now)
                elif changed and state in {"VALIDATED", "FINALIZATION_PENDING"}:
                    self.active_started.setdefault(media_id, now)
                if media_id in self.active_started and state in {
                    "DOWNLOADED", "FAILED_RETRYABLE", "FAILED_PERMANENT", "CANCELLED",
                }:
                    self.active_finished.setdefault(media_id, now)
        except sqlite3.Error:
            # A busy WAL sample is skipped; it never delays or writes to S9.
            return

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def durations(self) -> list[float]:
        return [
            self.active_finished[media_id] - started
            for media_id, started in self.active_started.items()
            if media_id in self.active_finished
            and self.active_finished[media_id] >= started
        ]


def _run_queue_monitored(arguments: list[str], monitor: _TransferMonitor) -> tuple[int, float]:
    _say("STAGE", "G5 F queue — G4 será solicitado interativamente")
    started = time.perf_counter()
    try:
        process = subprocess.Popen(arguments, cwd=Path(__file__).resolve().parents[1])
    except OSError:
        raise LauncherBlocked("G5_PROCESS_START_FAILED") from None
    try:
        while process.poll() is None:
            monitor.sample()
            time.sleep(0.2)
        return_code = process.wait()
        monitor.sample()
    except KeyboardInterrupt:
        process.wait()
        raise LauncherBlocked("G5_INTERRUPTED_BY_OPERATOR") from None
    finally:
        monitor.close()
    return return_code, max(0.0, time.perf_counter() - started)


def _readonly_download_snapshot(database: Path, channel_id: int) -> list[sqlite3.Row]:
    connection = _readonly_connection(database)
    try:
        return connection.execute(
            "SELECT m.id,d.state,d.final_path,d.expected_bytes,d.downloaded_bytes,d.sha256 "
            "FROM media_items m JOIN downloads d ON d.media_item_id=m.id "
            "WHERE m.channel_id=? AND d.state='DOWNLOADED'",
            (channel_id,),
        ).fetchall()
    except sqlite3.Error:
        raise LauncherBlocked("FINAL_DOWNLOAD_SNAPSHOT_FAILED") from None
    finally:
        connection.close()


def _verify_new_download(
    database: Path,
    download_root: Path,
    channel_id: int,
    previous_ids: set[int],
    observed_bytes: int,
) -> tuple[int, list[dict[str, object]]]:
    connection = _readonly_connection(database)
    verified: list[dict[str, object]] = []
    try:
        _check_integrity(connection)
        rows = connection.execute(
            "SELECT m.id,d.state,d.final_path,d.expected_bytes,d.downloaded_bytes,d.sha256 "
            "FROM media_items m JOIN downloads d ON d.media_item_id=m.id "
            "WHERE m.channel_id=? AND d.state='DOWNLOADED'",
            (channel_id,),
        ).fetchall()
        for row in rows:
            media_id = int(row["id"])
            if media_id in previous_ids:
                continue
            expected = row["expected_bytes"]
            downloaded = row["downloaded_bytes"]
            path_value = row["final_path"]
            digest = row["sha256"]
            if (
                type(expected) is not int
                or not 0 < expected <= MAX_SINGLE_F_MEDIA_BYTES
                or type(downloaded) is not int
                or downloaded != expected
                or type(path_value) is not str
                or type(digest) is not str
                or len(digest) != 64
            ):
                raise LauncherBlocked("DOWNLOADED_ROW_INCOMPLETE")
            file_path = Path(path_value)
            try:
                resolved_root = download_root.resolve(strict=True)
                resolved_file = file_path.resolve(strict=True)
                resolved_file.relative_to(resolved_root)
                info = file_path.lstat()
            except (OSError, RuntimeError, ValueError):
                raise LauncherBlocked("DOWNLOADED_FILE_PATH_UNSAFE") from None
            if (
                not file_path.is_file()
                or file_path.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400
                or info.st_size != expected
                or os.path.normcase(str(file_path.absolute()))
                != os.path.normcase(str(resolved_file))
            ):
                raise LauncherBlocked("DOWNLOADED_FILE_SIZE_OR_TYPE_INVALID")
            parent = resolved_file.parent
            while parent != resolved_root:
                try:
                    _private_dir(parent)
                    parent = parent.parent
                except LauncherBlocked:
                    raise LauncherBlocked("DOWNLOADED_PARENT_ACL_OR_PATH_INVALID") from None
            _private_file(file_path)
            hasher = hashlib.sha256()
            try:
                with file_path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        hasher.update(block)
            except OSError:
                raise LauncherBlocked("DOWNLOADED_FILE_HASH_READ_FAILED") from None
            actual_hash = hasher.hexdigest()
            if actual_hash != digest:
                raise LauncherBlocked("DOWNLOADED_FILE_HASH_MISMATCH")
            verified.append({
                "payload_bytes": expected,
                "sha256_verified": True,
                "file_path_alias": "private-run/downloads",
            })
        if observed_bytes < 0 or observed_bytes > F_CAP:
            raise LauncherBlocked("G5_OBSERVED_BYTES_OUTSIDE_F_CAP")
        return observed_bytes, verified
    finally:
        connection.close()


def _ledger_storage_bytes(run_directory: Path) -> int:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(run_directory / "operational-ledger.sqlite3") + suffix)
        try:
            if path.exists():
                _private_file(path)
                total += path.stat().st_size
        except OSError:
            raise LauncherBlocked("LEDGER_STORAGE_MEASUREMENT_FAILED") from None
    return total


def _write_metrics(run_directory: Path, metrics: dict[str, object]) -> None:
    path = run_directory / METRICS_FILENAME
    _create_private_file(path, canonical_bytes(metrics))


def _start_ledger(run_directory: Path) -> tuple[S9OperationalLedger, int, str]:
    ledger_path = run_directory / "operational-ledger.sqlite3"
    try:
        ledger = S9OperationalLedger.create(ledger_path)
        deadline_ns = ledger.start_global_deadline(3600)
        ledger.update_execution(
            gate="G1",
            status="RUNNING",
            elapsed_ms=0,
            deadline_ns=deadline_ns,
            process_state="RUNNING",
            result="UNKNOWN",
        )
        run_id = str(ledger.snapshot()["run"]["run_id"])
    except (LedgerError, OSError, ValueError):
        raise LauncherBlocked("S9_LEDGER_OR_DEADLINE_START_FAILED") from None
    _private_file(ledger_path)
    return ledger, deadline_ns, run_id


def _require_real_gate(
    run_directory: Path,
    ledger: S9OperationalLedger,
    gate: str,
    run_id: str,
    manifest_hash: str,
) -> dict[str, Any]:
    try:
        evidence = read_validated_gate_receipt(
            run_directory,
            ledger.snapshot(),
            gate,
            run_id=run_id,
            manifest_sha256=manifest_hash,
        )
    except (GateEvidenceError, LedgerError, OSError, ValueError):
        raise LauncherBlocked(f"{gate}_RECEIPT_REVALIDATION_FAILED") from None
    real_origin = evidence.get("evidence_origin") == "REAL_CONTRACTUAL"
    human_g0_origin = gate == "G0" and evidence.get("evidence_origin") == "HUMAN_INTERACTIVE"
    if evidence.get("status") != "PASS" or not (real_origin or human_g0_origin):
        raise LauncherBlocked(f"{gate}_REAL_EVIDENCE_NOT_PASS")
    return evidence


def _require_g4_pass(
    run_directory: Path,
    ledger: S9OperationalLedger,
    queue_receipt: dict[str, Any],
) -> None:
    """G4 is the TTY-confirmed ledger transition inside the G5 queue."""
    snapshot = ledger.snapshot()
    audit = snapshot.get("critical_audit", {})
    events = audit.get("events", []) if isinstance(audit, dict) else []
    g4_passes: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict) or event.get("event_type") != "GATE_STATE_UPDATED":
            continue
        try:
            details = json.loads(str(event.get("details_json")))
        except (TypeError, ValueError):
            continue
        if (
            isinstance(details, dict)
            and details.get("gate") == "G4"
            and details.get("status") == "RUNNING"
            and details.get("result") == "PASS"
            and details.get("process_state") == "RUNNING"
        ):
            g4_passes.append(details)
    if len(g4_passes) != 1:
        raise LauncherBlocked("G4_INTERACTIVE_LEDGER_PASS_MISSING")
    receipt_path = run_directory / str(queue_receipt["supervisor_receipt_file"])
    try:
        supervisor_receipt = json.loads(
            receipt_path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, GateEvidenceError):
        raise LauncherBlocked("G4_SUPERVISOR_RECEIPT_UNREADABLE") from None
    if (
        not isinstance(supervisor_receipt, dict)
        or supervisor_receipt.get("limit_check_result") != "PASS"
        or supervisor_receipt.get("tty_required") is not True
        or supervisor_receipt.get("tty_available") is not True
    ):
        raise LauncherBlocked("G4_LIMIT_OR_TTY_ATTESTATION_FAILED")


def _activity_main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    root, source_database, state_directory, snapshot = _preflight(repo_root)
    manifest, manifest_hash, _scope_hash = _load_or_create_manifest(
        state_directory, snapshot,
    )
    if manifest.get("scope", {}).get("target_alias") != "RASMOO":
        raise LauncherBlocked("MANIFEST_TARGET_ALIAS_MISMATCH")
    _say("CONTRACT_SHA256", "PASS")
    _say("DPAPI_SESSION", "PRESENT_ACL_VERIFIED_CONTENT_NOT_READ")
    _say("DPAPI_CREDENTIALS", "PRESENT_ACL_VERIFIED_CONTENT_NOT_READ")
    _say("S9_LIMITS", "scan=200/120s; F=1 item; aggregate=536870912 bytes; 1 worker; 1 attempt")
    _say("SOURCE_SQLITE", "READ_ONLY_INTEGRITY_AND_FK_PASS")

    run_directory, run_database, stages = _create_run_tree(
        root, source_database, manifest, manifest_hash,
    )
    _say("LAUNCHER_READY", "YES")
    download_root = run_directory / "downloads"
    previous = _readonly_download_snapshot(run_database, int(manifest["channel_id"]))
    previous_ids = {int(row["id"]) for row in previous}
    ledger, _deadline_ns, run_id = _start_ledger(run_directory)
    _say("G0_READY", "YES")
    _say("G0_REVIEW_STATUS", "manifest scope is still unapproved; approval happens at this TTY gate")
    _say("G0_REVIEW_MANIFEST_SHA256", manifest_hash)
    _say("G0_REVIEW_CHANNEL_ALIAS", "RASMOO")
    if manifest.get("catalog_expectation") is not None:
        _say("G0_REVIEW_CATALOG_EXPECTATION", "PENDING_G3")
        _say("G0_REVIEW_HIERARCHY_MINIMUMS_TRACK_COURSE_MODULE", "/".join(
            str(manifest["hierarchy"][key]) for key in ("TRACK", "COURSE", "MODULE")
        ))
        _say("G0_REVIEW_UNRESOLVED_SOURCES", "OBSERVE_AND_REVIEW_AT_G3")
    else:
        _say("G0_REVIEW_HIERARCHY_TRACK_COURSE_MODULE", "/".join(
            str(manifest["hierarchy"][key]) for key in ("TRACK", "COURSE", "MODULE")
        ))
        _say("G0_REVIEW_UNRESOLVED_COUNT", manifest["unresolved_count"])
    _say("RUN_ID", run_id)
    _say("GLOBAL_DEADLINE_SECONDS", 3600)
    _say("PREPARATION", "PASS; deadline started only after private SQLite/manifest/ACL preparation")

    python = sys.executable
    supervisor_module = [python, "-B", "-m", "telegram_courses.s9_supervisor_cli"]
    _run_stage(
        supervisor_module + [
            "g1", "--run-directory", str(run_directory),
            "--output-directory", stages["work-g1"],
        ],
        label="G1",
        ledger=ledger,
    )
    g0 = _require_real_gate(run_directory, ledger, "G0", run_id, manifest_hash)
    if g0.get("confirmation_source") != "INTERACTIVE_TTY":
        raise LauncherBlocked("G0_DID_NOT_USE_INTERACTIVE_TTY")
    _require_real_gate(run_directory, ledger, "G1", run_id, manifest_hash)
    _say("G0_READY", "PASS — confirmation was entered in the native TTY before RPC")

    channel_id = str(manifest["channel_id"])
    _run_stage(
        supervisor_module + [
            "stage", "--run-directory", str(run_directory),
            "--output-directory", stages["work-g2"], "--",
            "scan", "--channel-id", channel_id,
            "--database", str(run_database),
            "--max-messages", "200", "--timeout-seconds", "120",
        ],
        label="G2",
        ledger=ledger,
    )
    _require_real_gate(run_directory, ledger, "G2", run_id, manifest_hash)
    _run_stage(
        supervisor_module + [
            "stage", "--run-directory", str(run_directory),
            "--output-directory", stages["work-g3"], "--",
            "catalog", "build", "--channel-id", channel_id,
            "--database", str(run_database), "--parser-key", "rasmoo",
        ],
        label="G3",
        ledger=ledger,
    )
    _require_real_gate(run_directory, ledger, "G3", run_id, manifest_hash)

    monitor = _TransferMonitor(run_database, int(manifest["channel_id"]))
    queue_arguments = supervisor_module + [
        "queue", "--run-directory", str(run_directory),
        "--output-directory", stages["work-g5"], "--profile", "F", "--",
        "download", "queue",
        "--channel-id", channel_id,
        "--database", str(run_database),
        "--download-dir", str(download_root),
        "--scope", "lesson",
        "--workers", "1",
        "--attempts-per-media", "1",
        "--max-media-items", "1",
        "--max-transfer-bytes", str(F_CAP),
        "--integrity-mode", "REMOTE_HASH_REQUIRED",
    ]
    _say("G4_REQUIRED", "YES")
    _say("G4_PROMPT", "review the fresh plan and confirm in the native TTY")
    ledger.release_writer_ownership()
    queue_exit, queue_wall_seconds = _run_queue_monitored(queue_arguments, monitor)
    ledger.reacquire_writer_ownership()
    if queue_exit != 0:
        raise LauncherBlocked(f"G5_OR_G4_DID_NOT_PASS_EXIT_{queue_exit}")

    try:
        queue_receipt = read_validated_g5_queue_receipt(
            run_directory,
            ledger.snapshot(),
            run_id=run_id,
            manifest_sha256=manifest_hash,
            profile="F",
            pass_index=1,
        )
    except (GateEvidenceError, LedgerError, OSError, ValueError):
        raise LauncherBlocked("G5_QUEUE_RECEIPT_REVALIDATION_FAILED") from None
    if (
        queue_receipt.get("status") != "PASS"
        or queue_receipt.get("evidence_origin") != "REAL_CONTRACTUAL"
        or queue_receipt.get("measurement_source") != "GATEWAY_RESPONSE"
        or queue_receipt.get("max_media_items") != 1
        or queue_receipt.get("max_transfer_bytes") != F_CAP
    ):
        raise LauncherBlocked("G4_OR_G5_RECEIPT_NOT_CONTRACTUAL")
    _require_g4_pass(run_directory, ledger, queue_receipt)

    observed_bytes = int(queue_receipt["observed_bytes"])
    observed_bytes, verified_files = _verify_new_download(
        run_database,
        download_root,
        int(manifest["channel_id"]),
        previous_ids,
        observed_bytes,
    )
    if len(verified_files) > 1:
        raise LauncherBlocked("F_ITEM_CAP_EXCEEDED")
    active_durations = monitor.durations()
    active_seconds = sum(active_durations) if active_durations else None
    payload_bytes = sum(int(item["payload_bytes"]) for item in verified_files)
    active_mib_s = (
        payload_bytes / MIB / active_seconds
        if active_seconds and active_seconds > 0
        else None
    )
    snapshot_after = ledger.snapshot()
    ledger_storage = _ledger_storage_bytes(run_directory)
    ledger_events = len(snapshot_after.get("critical_audit", {}).get("events", []))
    metrics: dict[str, object] = {
        "activity_id": ACTIVITY_ID,
        "channel_alias": "RASMOO",
        "run_id": run_id,
        "g0": "PASS",
        "g4": "PASS",
        "g5": "PASS",
        "profile": "F",
        "item_cap": 1,
        "aggregate_cap_bytes": F_CAP,
        "observed_transfer_bytes": observed_bytes,
        "verified_payload_bytes": payload_bytes,
        "verified_files": verified_files,
        "queue_wall_seconds_including_g4_prompt": round(queue_wall_seconds, 3),
        "s4_active_span_seconds_approx_200ms_sampling": (
            round(active_seconds, 3) if active_seconds is not None else None
        ),
        "s4_active_span_mib_per_second_approx": (
            round(active_mib_s, 3) if active_mib_s is not None else None
        ),
        "non_transfer_queue_seconds_including_plan_prompt_supervisor_and_ledger": (
            round(max(0.0, queue_wall_seconds - active_seconds), 3)
            if active_seconds is not None
            else None
        ),
        "ledger_storage_bytes_including_wal_shm": ledger_storage,
        "ledger_critical_audit_event_count": ledger_events,
        "ledger_time_overhead_isolated": "NO — would require S9 instrumentation",
        "final_sqlite_integrity": "ok",
        "final_sqlite_foreign_key_check": "PASS",
        "final_local_file_size_and_sha256": "PASS" if verified_files else "NO_NEW_PAYLOAD",
        "s5_queue_console_metrics": "The live queue prints its own elapsed seconds and bytes per second.",
    }
    _write_metrics(run_directory, metrics)
    _say("G4", "PASS — fresh-plan TTY approval attested")
    _say("G5", "PASS — bounded F queue receipt revalidated")
    _say("OBSERVED_TRANSFER_BYTES", observed_bytes)
    _say("VERIFIED_PAYLOAD_BYTES", payload_bytes)
    _say("S4_ACTIVE_SPAN_SECONDS_APPROX", active_seconds if active_seconds is not None else "NOT_OBSERVED")
    _say("S4_ACTIVE_SPAN_MIB_PER_SECOND_APPROX", active_mib_s if active_mib_s is not None else "NOT_OBSERVED")
    _say("QUEUE_WALL_SECONDS_INCLUDING_G4_PROMPT", round(queue_wall_seconds, 3))
    _say("LEDGER_STORAGE_BYTES_INCLUDING_WAL_SHM", ledger_storage)
    _say("LEDGER_AUDIT_EVENT_COUNT", ledger_events)
    _say("LEDGER_TIME_OVERHEAD", "NOT_ISOLATED_WITHOUT_S9_INSTRUMENTATION")
    _say("FINAL_SQLITE_AND_FILE_VERIFICATION", "PASS" if verified_files else "NO_NEW_PAYLOAD")
    _say("PRIVATE_METRICS_FILE", str(run_directory / METRICS_FILENAME))
    real_download_pass = bool(verified_files and payload_bytes > 0 and observed_bytes > 0)
    _say("REAL_DOWNLOAD", "PASS" if real_download_pass else "NO_NEW_PAYLOAD")
    return 0 if real_download_pass else 4


def main() -> int:
    try:
        return _activity_main()
    except LauncherBlocked as error:
        _say("LAUNCHER_STATUS", "BLOCKED")
        _say("REASON", str(error))
        return 4
    except KeyboardInterrupt:
        _say("LAUNCHER_STATUS", "STOPPED_BY_OPERATOR")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
