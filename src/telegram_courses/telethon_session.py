"""Private Windows DPAPI storage for a future Telethon StringSession."""

from __future__ import annotations

import ctypes
import os
import sys
import tempfile
from pathlib import Path
from typing import Protocol

from telegram_courses.config import ConfigurationError

_MAGIC = b"TCS\x01"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1
_FILE_ALL_ACCESS = 0x001F01FF
_OBJECT_INHERIT_ACE = 0x01
_CONTAINER_INHERIT_ACE = 0x02
_INHERITED_ACE = 0x10
_ACCESS_ALLOWED_ACE_TYPE = 0x00
_SE_DACL_PROTECTED = 0x1000
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_FILE_ATTRIBUTE_DIRECTORY = 0x10
_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
_DRIVE_REMOTE = 4
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_OWNER_RIGHTS_SID = "S-1-3-4"
_SYSTEM_SID = "S-1-5-18"
_ADMINISTRATORS_SID = "S-1-5-32-544"
_TOKEN_QUERY = 0x0008
_TOKEN_USER_INFORMATION = 1
_ACL_SIZE_INFORMATION_CLASS = 2
_SE_FILE_OBJECT = 1
_OWNER_SECURITY_INFORMATION = 0x1
_DACL_SECURITY_INFORMATION = 0x4


class StorageError(Exception):
    """Session storage or Windows protection failed."""


class IntegrityError(Exception):
    """The protected session artifact is invalid or cannot be unprotected."""


class _BytesProtector(Protocol):
    def protect(self, value: bytes) -> bytes: ...

    def unprotect(self, value: bytes) -> bytes: ...


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", ctypes.c_uint32)]


class _TokenUser(ctypes.Structure):
    _fields_ = [("User", _SidAndAttributes)]


class _AclSizeInformation(ctypes.Structure):
    _fields_ = [
        ("AceCount", ctypes.c_uint32),
        ("AclBytesInUse", ctypes.c_uint32),
        ("AclBytesFree", ctypes.c_uint32),
    ]


class _AceHeader(ctypes.Structure):
    _fields_ = [
        ("AceType", ctypes.c_ubyte),
        ("AceFlags", ctypes.c_ubyte),
        ("AceSize", ctypes.c_uint16),
    ]


class _AccessAllowedAce(ctypes.Structure):
    _fields_ = [
        ("Header", _AceHeader),
        ("Mask", ctypes.c_uint32),
        ("SidStart", ctypes.c_uint32),
    ]


def _require_windows() -> None:
    if sys.platform != "win32":
        raise ConfigurationError from None


class _WindowsApi:
    """Lazily loaded Win32 API bindings used only after the platform guard."""

    def __init__(self) -> None:
        _require_windows()
        try:
            self.crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
            self.advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
            self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._configure()
        except (AttributeError, OSError):
            raise StorageError from None

    def _configure(self) -> None:
        void_p = ctypes.c_void_p
        dword = ctypes.c_uint32
        bool_t = ctypes.c_int

        self.crypt32.CryptProtectData.restype = bool_t
        self.crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.c_wchar_p,
            ctypes.POINTER(_DataBlob),
            void_p,
            void_p,
            dword,
            ctypes.POINTER(_DataBlob),
        ]
        self.crypt32.CryptUnprotectData.restype = bool_t
        self.crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(_DataBlob),
            void_p,
            void_p,
            dword,
            ctypes.POINTER(_DataBlob),
        ]
        self.kernel32.LocalFree.restype = void_p
        self.kernel32.LocalFree.argtypes = [void_p]

        self.kernel32.GetCurrentProcess.restype = void_p
        self.advapi32.OpenProcessToken.restype = bool_t
        self.advapi32.OpenProcessToken.argtypes = [
            void_p,
            dword,
            ctypes.POINTER(void_p),
        ]
        self.advapi32.GetTokenInformation.restype = bool_t
        self.advapi32.GetTokenInformation.argtypes = [
            void_p,
            ctypes.c_int,
            void_p,
            dword,
            ctypes.POINTER(dword),
        ]
        self.kernel32.CloseHandle.restype = bool_t
        self.kernel32.CloseHandle.argtypes = [void_p]
        self.advapi32.ConvertSidToStringSidW.restype = bool_t
        self.advapi32.ConvertSidToStringSidW.argtypes = [
            void_p,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        self.advapi32.GetNamedSecurityInfoW.restype = dword
        self.advapi32.GetNamedSecurityInfoW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_int,
            dword,
            ctypes.POINTER(void_p),
            ctypes.POINTER(void_p),
            ctypes.POINTER(void_p),
            ctypes.POINTER(void_p),
            ctypes.POINTER(void_p),
        ]
        self.advapi32.GetSecurityDescriptorDacl.restype = bool_t
        self.advapi32.GetSecurityDescriptorDacl.argtypes = [
            void_p,
            ctypes.POINTER(bool_t),
            ctypes.POINTER(void_p),
            ctypes.POINTER(bool_t),
        ]
        self.advapi32.GetSecurityDescriptorControl.restype = bool_t
        self.advapi32.GetSecurityDescriptorControl.argtypes = [
            void_p,
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(dword),
        ]
        self.advapi32.GetAclInformation.restype = bool_t
        self.advapi32.GetAclInformation.argtypes = [
            void_p,
            void_p,
            dword,
            ctypes.c_int,
        ]
        self.advapi32.GetAce.restype = bool_t
        self.advapi32.GetAce.argtypes = [
            void_p,
            dword,
            ctypes.POINTER(void_p),
        ]
        self.kernel32.GetFileAttributesW.restype = dword
        self.kernel32.GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
        self.kernel32.GetDriveTypeW.restype = dword
        self.kernel32.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]

    def free(self, address: int | ctypes.c_void_p | None) -> None:
        value = address.value if isinstance(address, ctypes.c_void_p) else address
        if value:
            if self.kernel32.LocalFree(ctypes.c_void_p(value)):
                raise StorageError from None

    def protect(self, value: bytes) -> bytes:
        return self._transform(value, protect=True)

    def unprotect(self, value: bytes) -> bytes:
        return self._transform(value, protect=False)

    def _transform(self, value: bytes, *, protect: bool) -> bytes:
        if not value or len(value) > 0xFFFFFFFF:
            raise StorageError from None
        input_buffer = ctypes.create_string_buffer(value, len(value))
        input_blob = _DataBlob(
            len(value),
            ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)),
        )
        output_blob = _DataBlob()
        flags = _CRYPTPROTECT_UI_FORBIDDEN

        if protect:
            success = self.crypt32.CryptProtectData(
                ctypes.byref(input_blob), None, None, None, None, flags,
                ctypes.byref(output_blob),
            )
        else:
            success = self.crypt32.CryptUnprotectData(
                ctypes.byref(input_blob), None, None, None, None, flags,
                ctypes.byref(output_blob),
            )
        try:
            if not success:
                if protect:
                    raise StorageError from None
                raise IntegrityError from None
            if not output_blob.pbData or not output_blob.cbData:
                if protect:
                    raise StorageError from None
                raise IntegrityError from None
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            if output_blob.pbData:
                self.free(ctypes.cast(output_blob.pbData, ctypes.c_void_p))

    def current_user_sid(self) -> str:
        token = ctypes.c_void_p()
        if not self.advapi32.OpenProcessToken(
            self.kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)
        ):
            raise StorageError from None
        try:
            required = ctypes.c_uint32()
            self.advapi32.GetTokenInformation(
                token, _TOKEN_USER_INFORMATION, None, 0, ctypes.byref(required)
            )
            if not required.value:
                raise StorageError from None
            buffer = ctypes.create_string_buffer(required.value)
            if not self.advapi32.GetTokenInformation(
                token,
                _TOKEN_USER_INFORMATION,
                buffer,
                required.value,
                ctypes.byref(required),
            ):
                raise StorageError from None
            token_user = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents
            return self.sid_string(token_user.User.Sid)
        finally:
            self.kernel32.CloseHandle(token)

    def sid_string(self, sid: int | ctypes.c_void_p) -> str:
        output = ctypes.c_wchar_p()
        if not self.advapi32.ConvertSidToStringSidW(
            ctypes.c_void_p(sid) if isinstance(sid, int) else sid,
            ctypes.byref(output),
        ):
            raise StorageError from None
        try:
            if not output.value:
                raise StorageError from None
            return output.value
        finally:
            self.free(ctypes.cast(output, ctypes.c_void_p))

    def inspect_acl(self, path: Path) -> tuple[str, bool, tuple[tuple[int, int, int, str], ...]]:
        owner = ctypes.c_void_p()
        dacl = ctypes.c_void_p()
        descriptor = ctypes.c_void_p()
        result = self.advapi32.GetNamedSecurityInfoW(
            str(path),
            _SE_FILE_OBJECT,
            _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
            ctypes.byref(owner),
            None,
            ctypes.byref(dacl),
            None,
            ctypes.byref(descriptor),
        )
        if result != 0 or not descriptor.value:
            raise StorageError from None
        try:
            if not dacl.value:
                raise StorageError from None
            dacl_present = ctypes.c_int()
            dacl_pointer = ctypes.c_void_p()
            dacl_defaulted = ctypes.c_int()
            if not self.advapi32.GetSecurityDescriptorDacl(
                descriptor,
                ctypes.byref(dacl_present),
                ctypes.byref(dacl_pointer),
                ctypes.byref(dacl_defaulted),
            ):
                raise StorageError from None
            if not dacl_present.value or not dacl_pointer.value:
                raise StorageError from None

            control = ctypes.c_uint16()
            revision = ctypes.c_uint32()
            if not self.advapi32.GetSecurityDescriptorControl(
                descriptor, ctypes.byref(control), ctypes.byref(revision)
            ):
                raise StorageError from None

            info = _AclSizeInformation()
            if not self.advapi32.GetAclInformation(
                dacl_pointer,
                ctypes.byref(info),
                ctypes.sizeof(info),
                _ACL_SIZE_INFORMATION_CLASS,
            ):
                raise StorageError from None
            entries: list[tuple[int, int, int, str]] = []
            for index in range(info.AceCount):
                ace_pointer = ctypes.c_void_p()
                if not self.advapi32.GetAce(
                    dacl_pointer, index, ctypes.byref(ace_pointer)
                ):
                    raise StorageError from None
                header = ctypes.cast(
                    ace_pointer, ctypes.POINTER(_AceHeader)
                ).contents
                if header.AceType != _ACCESS_ALLOWED_ACE_TYPE:
                    entries.append((header.AceType, header.AceFlags, 0, ""))
                    continue
                ace = ctypes.cast(
                    ace_pointer, ctypes.POINTER(_AccessAllowedAce)
                ).contents
                sid_pointer = ctypes.c_void_p(
                    ctypes.addressof(ace) + _AccessAllowedAce.SidStart.offset
                )
                entries.append(
                    (
                        header.AceType,
                        header.AceFlags,
                        int(ace.Mask),
                        self.sid_string(sid_pointer),
                    )
                )
            return (
                self.sid_string(owner),
                bool(control.value & _SE_DACL_PROTECTED),
                tuple(entries),
            )
        finally:
            self.free(descriptor)

    def attributes(self, path: Path) -> int | None:
        value = int(self.kernel32.GetFileAttributesW(str(path)))
        if value == _INVALID_FILE_ATTRIBUTES:
            error = ctypes.get_last_error()
            if error in {_ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND}:
                return None
            raise StorageError from None
        return value

    def drive_type(self, path: Path) -> int:
        return int(self.kernel32.GetDriveTypeW(str(path)))


class _DpapiProtector:
    def __init__(self, api: _WindowsApi | None = None) -> None:
        self._api = api

    def protect(self, value: bytes) -> bytes:
        api = self._api or _WindowsApi()
        return api.protect(value)

    def unprotect(self, value: bytes) -> bytes:
        api = self._api or _WindowsApi()
        return api.unprotect(value)


class _ProtectedSessionVault:
    """Private DPAPI-backed value vault; plaintext stays at its caller boundary."""

    def __init__(
        self,
        *,
        _protector: _BytesProtector | None = None,
        _api: _WindowsApi | None = None,
        _artifact_name: str = "session.dpapi",
        _magic: bytes = _MAGIC,
        _temp_prefix: str = ".session-",
        _overwrite_existing: bool = True,
    ) -> None:
        _require_windows()
        self._api = _api or _WindowsApi()
        self._protector = _protector or _DpapiProtector(self._api)
        self._current_user_sid = self._api.current_user_sid()
        self._magic = _magic
        self._temp_prefix = _temp_prefix
        self._overwrite_existing = _overwrite_existing
        self._path = self._session_path()
        if _artifact_name != "session.dpapi":
            self._path = self._path.with_name(_artifact_name)

    def _session_path(self) -> Path:
        raw = os.environ.get("LOCALAPPDATA")
        if not raw or raw.startswith(("\\\\", "//")):
            raise ConfigurationError from None
        local_app_data = Path(raw)
        if not local_app_data.is_absolute() or not local_app_data.drive:
            raise ConfigurationError from None
        if self._api.drive_type(Path(local_app_data.anchor)) == _DRIVE_REMOTE:
            raise ConfigurationError from None
        try:
            attributes = self._api.attributes(local_app_data)
        except StorageError:
            raise ConfigurationError from None
        if (
            attributes is None
            or attributes & _FILE_ATTRIBUTE_REPARSE_POINT
            or not attributes & _FILE_ATTRIBUTE_DIRECTORY
        ):
            raise ConfigurationError from None

        directory = local_app_data / "telegram_courses"
        path = directory / "session.dpapi"
        try:
            repository = Path(__file__).resolve().parents[2]
            candidate = path.resolve(strict=False)
            if candidate.is_relative_to(repository):
                raise ConfigurationError from None
        except (OSError, RuntimeError, ValueError):
            raise ConfigurationError from None
        return path

    def _prepare_directory(self) -> Path:
        parent = self._path.parent.parent
        parent_attributes = self._api.attributes(parent)
        if (
            parent_attributes is None
            or parent_attributes & _FILE_ATTRIBUTE_REPARSE_POINT
            or not parent_attributes & _FILE_ATTRIBUTE_DIRECTORY
        ):
            raise StorageError from None

        directory = self._path.parent
        try:
            os.mkdir(directory, mode=0o700)
        except FileExistsError:
            pass
        except OSError:
            raise StorageError from None

        attributes = self._api.attributes(directory)
        if (
            attributes is None
            or attributes & _FILE_ATTRIBUTE_REPARSE_POINT
            or not attributes & _FILE_ATTRIBUTE_DIRECTORY
        ):
            raise StorageError from None
        self._verify_acl(directory, is_directory=True)
        return directory

    def _verify_acl(self, path: Path, *, is_directory: bool) -> None:
        owner, dacl_protected, entries = self._api.inspect_acl(path)
        if owner != self._current_user_sid or not entries:
            raise StorageError from None
        allowed_sids = {
            _OWNER_RIGHTS_SID,
            _SYSTEM_SID,
            _ADMINISTRATORS_SID,
            self._current_user_sid,
        }
        if any(
            ace_type != _ACCESS_ALLOWED_ACE_TYPE
            or sid not in allowed_sids
            or mask != _FILE_ALL_ACCESS
            for ace_type, _flags, mask, sid in entries
        ):
            raise StorageError from None
        if not any(
            sid in {_OWNER_RIGHTS_SID, self._current_user_sid}
            for _ace_type, _flags, _mask, sid in entries
        ):
            raise StorageError from None

        if is_directory:
            expected = {
                (_ACCESS_ALLOWED_ACE_TYPE,
                 _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE,
                 _FILE_ALL_ACCESS,
                 _OWNER_RIGHTS_SID),
                (_ACCESS_ALLOWED_ACE_TYPE,
                 _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE,
                 _FILE_ALL_ACCESS,
                 _SYSTEM_SID),
                (_ACCESS_ALLOWED_ACE_TYPE,
                 _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE,
                 _FILE_ALL_ACCESS,
                 _ADMINISTRATORS_SID),
            }
            if (
                not dacl_protected
                or len(entries) != len(expected)
                or set(entries) != expected
            ):
                raise StorageError from None
        elif any(flags & ~_INHERITED_ACE for _, flags, _, _ in entries):
            raise StorageError from None

    def _existing_blob(self) -> bool:
        attributes = self._api.attributes(self._path)
        if attributes is None:
            return False
        if attributes & (
            _FILE_ATTRIBUTE_REPARSE_POINT | _FILE_ATTRIBUTE_DIRECTORY
        ):
            raise StorageError from None
        self._verify_acl(self._path, is_directory=False)
        return True

    def _load(self) -> str | None:
        if self._api.attributes(self._path.parent) is None:
            return None
        self._prepare_directory()
        if not self._existing_blob():
            return None
        try:
            artifact = self._path.read_bytes()
        except OSError:
            raise StorageError from None
        if len(artifact) <= len(self._magic) or not artifact.startswith(self._magic):
            raise IntegrityError from None
        try:
            plaintext = self._protector.unprotect(artifact[len(self._magic) :])
        except IntegrityError:
            raise IntegrityError from None
        except Exception:
            raise IntegrityError from None
        try:
            value = plaintext.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise IntegrityError from None
        if not value:
            raise IntegrityError from None
        return value

    def _save(self, plaintext: str) -> None:
        if not isinstance(plaintext, str) or not plaintext:
            raise ConfigurationError from None
        try:
            session_bytes = plaintext.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            raise ConfigurationError from None
        try:
            protected = self._protector.protect(session_bytes)
        except Exception:
            raise StorageError from None
        if not protected:
            raise StorageError from None
        artifact = self._magic + protected

        directory = self._prepare_directory()
        self._existing_blob()
        temporary_path: Path | None = None
        descriptor: int | None = None
        try:
            descriptor, name = tempfile.mkstemp(
                prefix=self._temp_prefix, suffix=".tmp", dir=directory
            )
            temporary_path = Path(name)
            self._verify_acl(temporary_path, is_directory=False)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                handle.write(artifact)
                handle.flush()
                os.fsync(handle.fileno())
            if not self._overwrite_existing:
                os.rename(temporary_path, self._path)
            else:
                os.replace(temporary_path, self._path)
            temporary_path = None
            self._verify_acl(self._path, is_directory=False)
        except StorageError:
            raise
        except OSError:
            raise StorageError from None
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def delete_local(self) -> bool:
        if self._api.attributes(self._path.parent) is None:
            return False
        self._prepare_directory()
        if not self._existing_blob():
            return False
        try:
            self._path.unlink()
        except OSError:
            raise StorageError from None
        return True


class _ProtectedCredentialsVault(_ProtectedSessionVault):
    """Separate non-overwriting DPAPI artifact for Telegram API credentials."""

    def __init__(
        self,
        *,
        _protector: _BytesProtector | None = None,
        _api: _WindowsApi | None = None,
    ) -> None:
        super().__init__(
            _protector=_protector,
            _api=_api,
            _artifact_name="credentials.dpapi",
            _magic=b"TCC\x01",
            _temp_prefix=".credentials-",
            _overwrite_existing=False,
        )


__all__ = ["IntegrityError", "StorageError"]
