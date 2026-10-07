# S1-A — Protected Session Foundation

`CONTRACT_STATUS = FROZEN`
`SCOPE = S1-A ONLY`

## Objective

Implement and validate offline the adapter-owned foundation that protects,
stores, restores, and explicitly removes the future Telethon `StringSession`
representation. This slice does not authenticate or connect to Telegram.

## Authority references

- [ARCHITECTURE.md — ADR-008](../architecture/ARCHITECTURE.md#adr-008--telegram-session-protection-and-retry-ownership)
- [ENGINEERING_FOUNDATION.md — Telegram session security contract](../engineering/ENGINEERING_FOUNDATION.md#telegram-session-security-contract)
- [ENGINEERING_FOUNDATION.md — logging and error taxonomy](../engineering/ENGINEERING_FOUNDATION.md#logging-contract)
- [REQUIREMENTS.md — FR-01, FR-15/16, NFR-05/06/09/10](../product/REQUIREMENTS.md)
- [SPRINTS.md — S1 and transversal controls](../continuity/planning/SPRINTS.md#s1--authentication--channel-discovery)
- [APPROVALS_AND_DECISIONS.md — S1-A authorization](../governance/APPROVALS_AND_DECISIONS.md#autorização-explícita--implementação-da-s1-a)

This contract freezes implementation details for this slice. It does not amend
or outrank the referenced authorities.

## Scope and ownership

Create only:

- `src/telegram_courses/telethon_session.py`
- `tests/unit/test_telethon_session.py`
- `tests/integration/test_telethon_session_windows.py`

The new module is private to the Telegram adapter boundary. No changes to S0
configuration, CLI, project dependencies, package discovery, or other source
files are authorized by this contract.

## Invariants

- Protect persisted session bytes with Windows DPAPI in `CURRENT_USER` scope.
- Never use `CRYPTPROTECT_LOCAL_MACHINE` or home-grown cryptography.
- Persist only the DPAPI-protected artifact; plaintext exists only in adapter
  memory for the minimum necessary lifecycle.
- Do not automatically back up, export, copy, or print session material.
- A local blob deletion is not Telegram revocation.
- Each machine has its own authorization/session.
- No Telethon session value or type crosses into the application/CLI layer.
- No real credentials, Telegram network, or real session are used in S1-A.

## DPAPI contract

- Use `ctypes` to call `CryptProtectData` and `CryptUnprotectData` from
  `crypt32.dll`; use `LocalFree` for API-owned output buffers.
- `DATA_BLOB` input/output is bytes. The adapter encodes/decodes the session
  string as strict UTF-8 at its private boundary.
- Pass `pPromptStruct = NULL`, `pOptionalEntropy = NULL`, and
  `dwFlags = CRYPTPROTECT_UI_FORBIDDEN (0x1)` for both operations. Do not set
  `CRYPTPROTECT_LOCAL_MACHINE (0x4)` and do not add fixed/custom entropy.
- Do not load a Windows DLL or access the filesystem at module import time.
  Guard operations with `sys.platform == "win32"` before loading DLLs or
  touching session paths.
- Free every DPAPI output buffer with `LocalFree`, including error-safe cleanup.
- Convert API failures to generic project errors. Never expose raw API input,
  output, Windows error text, or exception arguments in logs or user messages.

## Storage contract

- Fixed path for this slice:
  `%LOCALAPPDATA%/telegram_courses/session.dpapi`.
- `LOCALAPPDATA` must be present and absolute. Reject UNC/network-style paths,
  paths inside the repository, reparse-point storage directories/files, and
  path/ACL inspection failures. The `LOCALAPPDATA` directory itself must
  already exist as a local, non-reparse directory. Do not add a configurable
  path override in S1-A.
- The file format is exactly `b"TCS\x01" + dpapi_blob`: three ASCII magic
  bytes followed by one version byte (`0x01`), then the DPAPI result. Reject an
  empty payload, a truncated header, or unknown magic/version as
  `IntegrityError`.
- Do not introduce an arbitrary maximum session/blob size in S1-A; no approved
  numeric limit exists. Strict UTF-8 and DPAPI integrity validation still apply.
- `_save(plaintext: str) -> None` accepts only a non-empty string, protects it,
  and persists only the versioned protected artifact.
- `_load() -> str | None` returns `None` if no blob exists. Otherwise it checks
  the artifact, unprotects it, and returns strict UTF-8 text only to its private
  adapter caller. Invalid envelope, DPAPI failure, or invalid UTF-8 raises
  `IntegrityError`; it must never silently delete or recreate the blob.
- `delete_local() -> bool` explicitly removes a verified local blob; return
  `False` if it is absent and `True` if removed. It makes no remote-revocation
  or secure-erasure claim.
- Write to a random, exclusive temporary file in the same verified directory;
  write protected bytes only, flush and `fsync`, then atomically `os.replace`
  the final path. Clean up the temporary file on failure. Do not create backup
  files. A failed replace preserves the previous final blob.
- Missing load returns `None`; missing delete returns `False`. Storage,
  filesystem, ACL, and protection failures map to `StorageError`.

## Windows access-control contract

- Create a new private directory with `os.mkdir(path, mode=0o700)`. This is the
  Python 3.14 Windows ACL behavior; do not use `os.chmod` to claim or repair an
  ACL. If the directory already exists, inspect it and fail closed if it does
  not satisfy this contract; never silently repair an existing ACL.
- Inspect the owner and DACL of the directory, existing final blob, temporary
  file, and replaced final blob using `GetNamedSecurityInfoW`,
  `GetSecurityDescriptorDacl`, `GetSecurityDescriptorControl`,
  `GetAclInformation`, and `GetAce`. Obtain the current process user SID from
  its token. Match each Win32 output buffer to its declared ABI, including the
  `DWORD` revision output of `GetSecurityDescriptorControl`. Release the
  security descriptor with `LocalFree` and close token handles.
- Directory owner must equal the current user SID; its DACL must be present,
  non-NULL, and protected (`SE_DACL_PROTECTED`). The newly created directory
  DACL must contain exactly ordinary allow ACEs for `OWNER RIGHTS` (`S-1-3-4`),
  `LOCAL SYSTEM` (`S-1-5-18`), and `BUILTIN\Administrators`
  (`S-1-5-32-544`), each with `FILE_ALL_ACCESS` and object/container inherit
  flags. ACE ordering is immaterial.
- Existing directory and file DACLs may include those SIDs and an explicit
  current-user SID only. Require the current user as owner, at least one
  effective owner/current-user allow ACE, a non-NULL DACL, and no unknown
  trustee or ACE type. Reject deny, callback, object, NULL-DACL, or broad
  principal entries. Files created in the protected directory inherit its
  allowed DACL; inspect them before read/delete and after temporary creation
  and final replacement.
- Any unsupported ACL/filesystem, reparse point, unexpected owner/ACE, or ACL
  inspection failure raises `StorageError` before reading or writing session
  bytes. Do not use POSIX mode bits as the Windows ACL oracle.

## Adapter boundary and integration point

`_ProtectedSessionVault` and its `_save`/`_load` methods remain private to
`telethon_session.py`, are not imported by the application or CLI, and are the
only S1-A integration point. The future `TelethonGateway` may consume the
vault inside the adapter. S1-A does not create a public session port, gateway,
composition root, login flow, channel discovery, or connection. Its integration
validation is the offline DPAPI → protected file → DPAPI round-trip through the
adapter-owned vault.

## Error and logging contract

- Unsupported platform or unusable `LOCALAPPDATA`: existing `ConfigurationError`.
- Empty or invalid UTF-8 input to `_save`: `ConfigurationError`.
- DPAPI protect, filesystem, path, or ACL failure: `StorageError`.
- Invalid/corrupt/version-mismatched/unprotectable artifact or invalid UTF-8:
  `IntegrityError`.
- Missing blob: `None` for load and `False` for delete; it is not an error.
- Log no session string, synthetic sentinel, protected blob, encoded blob, API
  credential, path, or raw exception. S1-A may emit no logs; if it emits any,
  they may contain only safe operation/outcome/error-class metadata.

## Exact test contract

`tests/unit/test_telethon_session.py`:

1. DPAPI wrapper calls only UI-forbidden flags and performs bytes round-trip
   through a fake API on any platform.
2. Non-Windows guard fires before DLL loading or filesystem access.
3. Envelope magic/version, truncated and unknown versions, empty payload, and
   invalid UTF-8 map to `IntegrityError`.
4. Missing load/delete behavior is `None`/`False`; explicit delete is
   idempotent and local only.
5. Injected replacement failure leaves the old final artifact unchanged and
   removes the temporary file.
6. Repeated saves leave one final artifact and no automatic backup/export.
7. Captured logs and safe exception text contain neither a synthetic plaintext
   sentinel nor protected bytes/base64.
8. A repository-root `LOCALAPPDATA` value is rejected before writes.

`tests/integration/test_telethon_session_windows.py` (Windows only, synthetic
fixtures only):

1. Real local DPAPI protect/unprotect round-trip with a synthetic string; the
   persisted artifact does not contain that string.
2. Persist/load/delete through `_ProtectedSessionVault`, including missing and
   tampered blobs, without creating a Telegram client or network traffic.
3. Inspect the raw Windows SID/owner/DACL oracle for directory, temp, and final
   files; verify new/reused access boundary and fail-closed behavior for a
   deliberately broad synthetic ACL.
4. Confirm the actual path is under `LOCALAPPDATA` and outside the repository.
5. Confirm the application/CLI has no public API that receives session
   plaintext or imports the private vault.

## Non-goals

Real Telegram login/connection, phone/OTP/2FA, real API credentials/session,
channel discovery/selection, retry/FloodWait behavior, remote revocation,
scanner/catalog/parser/download, automatic backup/export, and the rest of S1.

## Stop conditions

Stop the affected work and return to the root if implementation requires a new
dependency, a changed invariant, a different storage location/format, a broader
application API, repair of an existing unsafe ACL, an unapproved size limit, or
any real Telegram/credential/session operation.

## Acceptance criteria

- DPAPI `CURRENT_USER` protection, storage, and Windows access boundary pass
  the tests above; `CRYPTPROTECT_LOCAL_MACHINE` is absent.
- No plaintext session is persisted or logged; only synthetic fixtures are
  used; session path stays outside the repository.
- Adapter boundary and offline integration round-trip pass.
- No automatic backup/export, Telegram network, real session, or real
  credential is used.
- Full pytest, Ruff, and relevant regression validation pass; the root reviews
  the actual diff and reconciles `PROJECT_STATE` and affected continuity state.
