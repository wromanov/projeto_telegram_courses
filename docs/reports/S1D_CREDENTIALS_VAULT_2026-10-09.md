# S1-D — Telegram API Credentials Vault

```text
ACTIVITY = S1-D Telegram API Credentials Vault
STATUS = PASS
ACTIVITY_COMPLETION_PERCENT = 100%
EXECUTION_MODE = DIRECT
AGENT = ROOT / requested LUNA model target is not independently verifiable in this runtime
VAULT_IMPLEMENTATION = PASS
DPAPI_ENCRYPTION = PASS / Windows DPAPI CurrentUser; synthetic-value integration roundtrip
CREDENTIALS_SETUP = PASS / interactive API ID and hidden API HASH; overwrite refused
CREDENTIALS_STATUS = PASS / configured and available state only; no value output
ENV_FALLBACK = PASS / complete environment pair > vault; incomplete pair errors without source mixing
CLI_INTEGRATION = PASS / setup, status, auth and channels use the real CLI path with fakes/synthetic values
FOCUSED_TESTS = PASS / 29 passed, 11 subtests passed
DPAPI_INTEGRATION_TEST = PASS / 1 passed; real Windows DPAPI/ACL, synthetic credentials only
FULL_PYTEST = PASS / 110 passed, 11 subtests passed in 169.05s; exit code 0
RUFF = PASS / ruff check .
REAL_SECRETS_ACCESSED = NO
REAL_SESSION_DPAPI_OPENED = NO
TELEGRAM_NETWORK_USED = NO
GIT_ACTIONS = NONE
FILES_CREATED = src/telegram_courses/credentials.py; tests/unit/test_credentials.py; tests/integration/test_cli_credentials.py; tests/integration/test_credential_vault_windows.py; docs/reports/S1D_CREDENTIALS_VAULT_2026-10-09.md
FILES_MODIFIED = src/telegram_courses/cli.py; src/telegram_courses/config.py; src/telegram_courses/telethon_session.py; tests/unit/test_config.py; docs/continuity/PROJECT_STATE.md; docs/continuity/CONTINUITY_RECORD.md; docs/continuity/handoff/LAST_HANDOFF.md; docs/continuity/planning/SPRINTS.md
```

## Delivered behavior

- Stores the versioned, validated credential payload at
  `%LOCALAPPDATA%\telegram_courses\credentials.dpapi`, separate from
  `session.dpapi`, using the existing CurrentUser DPAPI and protected ACL path.
- Protects the payload before writing it. A same-directory temporary file is
  atomically renamed into place; creation fails if the vault already exists.
  Failure paths expose sanitized application errors and do not log values.
- Adds `telegram-courses credentials setup` and `telegram-courses credentials
  status`. Setup prompts for the API ID and hides API HASH input. Status reports
  only configured/available state.
- Resolves credentials from a complete environment pair first, then the vault.
  An incomplete pair fails safely and never combines values from two sources.
  The existing non-empty API HASH acceptance is preserved for compatibility;
  vault encoding/schema and API ID validation are strict.
- Keeps authentication in the existing gateway/application flow. The `auth`,
  `channels`, and `smoke` commands remain available.

## Validation and limits

The Windows DPAPI integration test used only synthetic values, verified the
protected artifact does not contain them, checked the distinct credentials path
and ACLs, and loaded the credentials back through the vault. Other tests cover
missing/corrupt artifacts, decryption errors, no overwrite, environment
precedence, incomplete variables, CLI output sanitization, and auth/channels
integration. Full regression includes the existing session-protection tests.

No actual credential vault was configured by this activity. No real API values
or session contents were read, and no Telegram connection was attempted. DPAPI
protects credentials at rest; a process running as the same authorized Windows
user can decrypt them in memory.

This activity does not address the earlier discovery failure. The user-reported
result remains `CATEGORY=ADAPTER_FAILURE`, `PAGES_REQUESTED=1`,
`PAGES_RECEIVED=1`, `RAW_DIALOGS_RECEIVED=101`; the separate offline correction
is documented in project state and does not change that reported event. The
approved DEC-S1D-01/02/03, OPEN-03 and discovery budgets were not changed. The
contract remains not frozen while GOV-01 is unresolved.

## Next action

The user can configure real values locally in PowerShell, without placing the
API HASH on the command line or in this conversation:

```powershell
telegram-courses credentials setup
telegram-courses credentials status
```

`setup` refuses to overwrite an existing vault. After status reports credentials
available, resume the existing bounded S1-D validation only after confirming a
valid protected session is available. This activity did not open or inspect the
real session artifact.
