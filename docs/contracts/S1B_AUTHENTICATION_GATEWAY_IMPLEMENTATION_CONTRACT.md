# S1-B — Offline Authentication Flow & Telegram Gateway

`CONTRACT_STATUS = FROZEN`
`SCOPE = S1-B ONLY`
`NETWORK = OFFLINE TESTS ONLY; NO TELEGRAM CONNECTION`

## Objective and authority

Implement the application-owned authentication model and CLI flow, a
`TelegramGateway` contract, and its Telethon adapter. Validate reuse, OTP and
2FA challenges, invalid sessions, error translation, session protection,
FloodWait handling, and the CLI entirely with fakes/test doubles.

This contract operationalizes, but does not amend, the authorities below:

- [ARCHITECTURE.md — ADR-002, ADR-006 and ADR-008](../architecture/ARCHITECTURE.md)
- [ENGINEERING_FOUNDATION.md — configuration, session, logging, error, retry and test contracts](../engineering/ENGINEERING_FOUNDATION.md)
- [REQUIREMENTS.md — FR-01, FR-02 downstream boundary, FR-15/16, NFR-04/05/06/09/10](../product/REQUIREMENTS.md)
- [SPRINTS.md — S1 and transverse controls](../continuity/planning/SPRINTS.md#s1--authentication--channel-discovery)
- [APPROVALS_AND_DECISIONS.md — session lifecycle, retry ownership and S1-B authorization](../governance/APPROVALS_AND_DECISIONS.md)
- [S1-A protected-session contract](S1A_PROTECTED_SESSION_IMPLEMENTATION_CONTRACT.md)

S1-A remains frozen and must not be reimplemented. The protected vault path
and DPAPI `CURRENT_USER` behavior stay exactly as S1-A defines them.

## Scope, ownership and files

Create:

- `src/telegram_courses/auth.py` — project-owned auth states, results and errors.
- `src/telegram_courses/telegram_gateway.py` — application-facing protocol.
- `src/telegram_courses/auth_application.py` — offline-testable flow orchestration.
- `src/telegram_courses/telethon_gateway.py` — private Telethon implementation.
- `tests/unit/test_auth.py`
- `tests/unit/test_auth_application.py`
- `tests/unit/test_telethon_gateway.py`
- `tests/integration/test_cli_auth.py`

Modify only:

- `src/telegram_courses/config.py` — read and validate API credentials from
  environment variables without returning or displaying their values.
- `src/telegram_courses/cli.py` — add the `auth` command while preserving
  `smoke`; use injectable application/gateway and prompt seams for offline tests.

Do not modify S1-A source/tests, requirements, architecture, engineering
foundation, governance binding, policies, scanner/parser/download code, package
dependencies, or unrelated files. Do not add dependencies. Any necessary
out-of-scope change or unresolved material choice stops the affected work and
returns it to the root.

## Authentication domain model and gateway contract

Define immutable project-owned `AuthState` values:
`AUTHENTICATED`, `AUTH_REQUIRED`, `CODE_REQUIRED`, `PASSWORD_REQUIRED`, and
`SESSION_INVALID`. `AuthOutcome` carries only the state and safe non-secret
metadata. No Telethon class, exception, client, code hash, session value, or
credential may cross the adapter boundary.

Define an asynchronous `TelegramGateway` protocol with these semantics (names
may follow existing repository style while preserving the contract):

- `restore() -> AuthState`: inspect the protected stored session, if present.
- `begin(phone) -> AuthState`: initiate code delivery for an explicit attempt.
- `submit_code(code) -> AuthState`: return authenticated or password required.
- `submit_password(password) -> AuthState`: complete an explicit 2FA attempt.
- `close() -> None`: release client resources; safe to call more than once.

The application owns prompts and workflow. The adapter owns the client, phone,
code hash, StringSession, protected vault, and error translation. Invalid
sequence/state is a controlled project error. Invalid code/password ends the
current submission without an automatic retry; a new human input is a new
explicit submission. Expired code ends the challenge and requires a new
explicit `begin`.

Use the existing `ConfigurationError` and S1-A `StorageError`/
`IntegrityError`. Add project-owned authentication errors for rejected auth,
invalid/expired code, invalid 2FA password, invalid session, network failure,
rate limiting, and unexpected adapter failure. `RateLimited` carries
`retry_after_seconds`; an actual FloodWait has its verified integer duration.
All public/safe exception text is generic and never includes raw causes.

## Application and CLI flow

The application validates configuration before client creation, calls
`restore`, and returns immediately for `AUTHENTICATED`. For
`AUTH_REQUIRED`/`SESSION_INVALID`, it obtains a phone from the user and calls
`begin`; it then obtains an OTP only for `CODE_REQUIRED`, and a 2FA password
only for `PASSWORD_REQUIRED`. Report success only after Telegram confirms
authorization and the protected session save succeeds. Always call `close`
in `finally` and handle close idempotently.

The CLI keeps `smoke` behavior and adds `auth`. API ID and API hash come only
from `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`; require a positive integer ID
and non-empty hash before connecting. No fallback, config-file secret, secret
flag, code/password flag, or session argument is allowed. Phone input may be
visible; OTP and 2FA prompts must not echo. If secret prompts cannot be safely
interactive, fail in a controlled way before starting authentication. Output
uses generic status/error messages and stable exit codes; never interpolate
raw input, credentials, exceptions, paths, or session data.

## Session lifecycle and Telethon adapter

The adapter alone may import/use `_ProtectedSessionVault` and
`telethon.sessions.StringSession`. On restore, load the protected blob,
construct a `StringSession` in memory, connect, and use `get_me()` to establish
authorization. A user result means `AUTHENTICATED`; `None` with an existing
blob means `SESSION_INVALID`; `None` with no blob means `AUTH_REQUIRED`.
Do not use `is_user_authorized()`, because Telethon 1.45.0 catches arbitrary
`RPCError` there and can hide FloodWait/network failures.

For invalid-session reauthentication, disconnect the old client and use a new
empty in-memory `StringSession`. Keep the old protected blob until a new login
has succeeded; do not call `log_out` or `delete_local`, and do not claim remote
revocation. Read the OTP `phone_code_hash` from Telethon's code-send result and
keep it only inside the adapter; reject a missing/empty hash as a controlled
adapter failure. Submit with `sign_in(phone, code, phone_code_hash=hash)` and
`sign_in(password=password)` for 2FA. Do not use `start()` or a Telethon
file-backed session.

Construct `TelegramClient` with the in-memory StringSession, API credentials,
`flood_sleep_threshold=0`, finite `request_retries=1`, finite
`connection_retries=1`, `raise_last_call_error=True`, and
`auto_reconnect=False`. These settings bound library retry/reconnect behavior;
they do not authorize application retries. The verified bounded
`AuthRestartError` restart inside Telethon 1.45.0 `send_code_request` is
protocol behavior, not an application resubmission. Translate FloodWait from
its `.seconds`; do not sleep in the adapter. Save only after final authorization
is confirmed, require `StringSession.save()` to be non-empty, and immediately
pass it to the private vault `_save`. If saving fails, report controlled
failure and never report authentication success.

Map known Telethon auth/config/code/password/session errors to the corresponding
project-owned error/state. Map connection/timeout/transport failures to
`NetworkError`; map FloodWait to `RateLimited(retry_after_seconds)`. Map any
unrecognized Telethon failure to a generic adapter error using exception
suppression (`from None`) at the boundary. No raw Telethon types or details
escape it.

## Retry, logging and secret boundaries

The application owns whether to wait/retry. This slice performs no automatic
application retry or FloodWait sleep during authentication; it surfaces a
safe rate-limit result and lets the user end/restart explicitly. Authentication
and login submission calls are not automatically replayed after ambiguous
timeouts. Any Telethon internal retry is finite and bounded as above.

Never log or print API ID/hash, phone, OTP, code hash, 2FA password,
StringSession, protected bytes, filesystem path, or raw exception text. Keep
Telethon logs disabled for this client's material by supplying a private
non-propagating `NullHandler` logger. Console errors are generic. The app and
CLI never receive a session representation.

## Test contract

All tests are offline and use synthetic canaries only. The normal test suite
must not construct a real Telegram network client or reach a socket. Make the
Telethon client factory injectable; fakes must fail if a real `connect` path
or network attempt is invoked. Use fake prompts, gateway/client, vault, and
captured output/logs.

Validate at minimum:

1. Every auth state/challenge transition, invalid state transition, missing
   configuration, invalid code/password, expired code, and controlled failure.
2. Authenticated session reuse; missing session; invalid stored session;
   reauthentication preserves the old blob until successful replacement.
3. OTP and 2FA inputs are passed only to the adapter and never appear in
   stdout/stderr/logs/exceptions. No secret is accepted via CLI arguments.
4. Telethon constructor settings and methods; private code hash handling;
   no `start`, SQLite/file session, or `is_user_authorized` use.
5. Session save happens only after confirmed authorization, is non-empty, and
   goes directly to the private vault. Save failures do not report success.
6. Known authentication/config/network/FloodWait errors map correctly;
   unknown errors are controlled and expose no Telethon type/details.
7. FloodWait carries the verified duration, with no adapter/application sleep
   or automatic replay. Tests observe actual fake calls.
8. `close` runs in `finally` and is idempotent. CLI `auth` succeeds/fails
   through a fake gateway and `smoke` remains compatible.
9. S1-A tests continue to pass. No test invokes network, real credentials,
   phone, OTP, 2FA, or creates a real session.

Run focused S1-B tests, full pytest, Ruff, import checks, `git diff --check`,
dependency-diff review, secret-pattern inspection, and S1-A regression checks.
Report test evidence separately from any behavior not verifiable offline.

## Non-goals, stop conditions and acceptance

No channel discovery/selection, real Telegram connection, real phone/API
credentials/OTP/2FA/session, scanner, parser, download, catalog, new
configuration surface for session storage, changed policies/requirements,
dependency addition, or Git staging/publication.

Stop the affected work and return to root for any new dependency, unverified
Telethon behavior, authority/product conflict, scope expansion, session
plaintext outside the adapter, or material semantic ambiguity.

Acceptance requires all module, integration, accumulated-flow, regression and
S1-A tests to pass offline; the app-owned auth model and gateway boundary to be
complete; session reuse, OTP/2FA, invalid-session and error/FloodWait behavior
to meet this contract; the CLI flow to work with a fake gateway; no Telethon
types or secrets to cross/log; no real Telegram/network/session/credentials;
and no out-of-scope changes. S1-B PASS does not close S1 or authorize S1-C.
