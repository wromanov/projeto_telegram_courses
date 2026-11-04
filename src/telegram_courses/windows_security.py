"""Narrow Win32 identity, ACL, and path-security primitives."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

_TOKEN_QUERY = 0x0008
_TOKEN_USER_INFORMATION = 1
_ACL_SIZE_INFORMATION_CLASS = 2
_SE_FILE_OBJECT = 1
_OWNER_SECURITY_INFORMATION = 0x1
_DACL_SECURITY_INFORMATION = 0x4
_ACCESS_ALLOWED_ACE_TYPE = 0x00
_SE_DACL_PROTECTED = 0x1000
_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3


class WindowsSecurityError(Exception):
    """A Windows identity or ACL operation failed closed."""


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


class WindowsSecurityApi:
    """Load only Win32 identity/ACL APIs; it has no DPAPI session methods."""

    def __init__(self, *, error_type: type[Exception] = WindowsSecurityError) -> None:
        self._error_type = error_type
        if os.name != "nt":
            raise self._error_type() from None
        try:
            self.advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
            self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._configure()
        except (AttributeError, OSError):
            raise self._error_type() from None

    def _configure(self) -> None:
        void_p = ctypes.c_void_p
        dword = ctypes.c_uint32
        bool_t = ctypes.c_int

        self.kernel32.LocalFree.restype = void_p
        self.kernel32.LocalFree.argtypes = [void_p]
        self.kernel32.GetCurrentProcess.restype = void_p
        self.advapi32.OpenProcessToken.restype = bool_t
        self.advapi32.OpenProcessToken.argtypes = [
            void_p, dword, ctypes.POINTER(void_p),
        ]
        self.advapi32.GetTokenInformation.restype = bool_t
        self.advapi32.GetTokenInformation.argtypes = [
            void_p, ctypes.c_int, void_p, dword, ctypes.POINTER(dword),
        ]
        self.kernel32.CloseHandle.restype = bool_t
        self.kernel32.CloseHandle.argtypes = [void_p]
        self.advapi32.ConvertSidToStringSidW.restype = bool_t
        self.advapi32.ConvertSidToStringSidW.argtypes = [
            void_p, ctypes.POINTER(ctypes.c_wchar_p),
        ]
        self.advapi32.GetNamedSecurityInfoW.restype = dword
        self.advapi32.GetNamedSecurityInfoW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_int, dword,
            ctypes.POINTER(void_p), ctypes.POINTER(void_p),
            ctypes.POINTER(void_p), ctypes.POINTER(void_p), ctypes.POINTER(void_p),
        ]
        self.advapi32.GetSecurityDescriptorDacl.restype = bool_t
        self.advapi32.GetSecurityDescriptorDacl.argtypes = [
            void_p, ctypes.POINTER(bool_t), ctypes.POINTER(void_p),
            ctypes.POINTER(bool_t),
        ]
        self.advapi32.GetSecurityDescriptorControl.restype = bool_t
        self.advapi32.GetSecurityDescriptorControl.argtypes = [
            void_p, ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(dword),
        ]
        self.advapi32.GetAclInformation.restype = bool_t
        self.advapi32.GetAclInformation.argtypes = [
            void_p, void_p, dword, ctypes.c_int,
        ]
        self.advapi32.GetAce.restype = bool_t
        self.advapi32.GetAce.argtypes = [
            void_p, dword, ctypes.POINTER(void_p),
        ]
        self.kernel32.GetFileAttributesW.restype = dword
        self.kernel32.GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
        self.kernel32.GetDriveTypeW.restype = dword
        self.kernel32.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]

    def free(self, address: int | ctypes.c_void_p | None) -> None:
        value = address.value if isinstance(address, ctypes.c_void_p) else address
        if value and self.kernel32.LocalFree(ctypes.c_void_p(value)):
            raise self._error_type() from None

    def current_user_sid(self) -> str:
        token = ctypes.c_void_p()
        if not self.advapi32.OpenProcessToken(
            self.kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)
        ):
            raise self._error_type() from None
        try:
            required = ctypes.c_uint32()
            self.advapi32.GetTokenInformation(
                token, _TOKEN_USER_INFORMATION, None, 0, ctypes.byref(required)
            )
            if not required.value:
                raise self._error_type() from None
            buffer = ctypes.create_string_buffer(required.value)
            if not self.advapi32.GetTokenInformation(
                token, _TOKEN_USER_INFORMATION, buffer,
                required.value, ctypes.byref(required),
            ):
                raise self._error_type() from None
            token_user = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents
            return self.sid_string(token_user.User.Sid)
        finally:
            self.kernel32.CloseHandle(token)

    def sid_string(self, sid: int | ctypes.c_void_p) -> str:
        output = ctypes.c_wchar_p()
        sid_value = ctypes.c_void_p(sid) if isinstance(sid, int) else sid
        if not self.advapi32.ConvertSidToStringSidW(sid_value, ctypes.byref(output)):
            raise self._error_type() from None
        try:
            if not output.value:
                raise self._error_type() from None
            return output.value
        finally:
            self.free(ctypes.cast(output, ctypes.c_void_p))

    def inspect_acl(self, path: Path) -> tuple[str, bool, tuple[tuple[int, int, int, str], ...]]:
        owner = ctypes.c_void_p()
        dacl = ctypes.c_void_p()
        descriptor = ctypes.c_void_p()
        result = self.advapi32.GetNamedSecurityInfoW(
            str(path), _SE_FILE_OBJECT,
            _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
            ctypes.byref(owner), None, ctypes.byref(dacl), None,
            ctypes.byref(descriptor),
        )
        if result != 0 or not descriptor.value:
            raise self._error_type() from None
        try:
            if not dacl.value:
                raise self._error_type() from None
            dacl_present = ctypes.c_int()
            dacl_pointer = ctypes.c_void_p()
            dacl_defaulted = ctypes.c_int()
            if not self.advapi32.GetSecurityDescriptorDacl(
                descriptor, ctypes.byref(dacl_present),
                ctypes.byref(dacl_pointer), ctypes.byref(dacl_defaulted),
            ) or not dacl_present.value or not dacl_pointer.value:
                raise self._error_type() from None
            control = ctypes.c_uint16()
            revision = ctypes.c_uint32()
            if not self.advapi32.GetSecurityDescriptorControl(
                descriptor, ctypes.byref(control), ctypes.byref(revision)
            ):
                raise self._error_type() from None
            info = _AclSizeInformation()
            if not self.advapi32.GetAclInformation(
                dacl_pointer, ctypes.byref(info), ctypes.sizeof(info),
                _ACL_SIZE_INFORMATION_CLASS,
            ):
                raise self._error_type() from None
            entries: list[tuple[int, int, int, str]] = []
            for index in range(info.AceCount):
                ace_pointer = ctypes.c_void_p()
                if not self.advapi32.GetAce(
                    dacl_pointer, index, ctypes.byref(ace_pointer)
                ):
                    raise self._error_type() from None
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
                entries.append((
                    header.AceType, header.AceFlags, int(ace.Mask),
                    self.sid_string(sid_pointer),
                ))
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
            raise self._error_type() from None
        return value

    def drive_type(self, path: Path) -> int:
        return int(self.kernel32.GetDriveTypeW(str(path)))
