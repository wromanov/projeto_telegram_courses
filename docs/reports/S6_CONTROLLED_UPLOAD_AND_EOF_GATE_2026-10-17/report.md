# S6 Controlled Upload and EOF Gate Preparation

```text
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_CONTROLLED_UPLOAD_AND_EOF_GATE
STATUS = PREPARED / NO REAL TELEGRAM EXECUTION
CONTRACT = S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT / APPROVED / FROZEN
```

## Pre-flight

- Governance binding parses and identifies `GOVERNANCE_BASELINE V1`; the active authority map points to the S6 contract, which remains approved and frozen.
- Repository: `C:/Users/walac/desenvolvimento/projeto_telegram_courses`; branch `work/s0-bootstrap`; HEAD `98d9d6b9ce152b8d2764a4d160fcbdf4722fb257`; upstream `origin/work/s0-bootstrap`.
- The worktree was already dirty, including the current continuity files, S6 contract, source, tests and reports. Those changes were preserved. No Git staging or publication occurred.
- The existing reference manifest parsed and matched a fresh, read-only streaming SHA-256 pass. Size was `1,119,129,690` bytes, SHA-256 `3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c`, and last-write time `2026-10-17T05:35:28.9950068Z`; before/after size and timestamp were equal.

## Upload procedure (not executed)

Destination supplied for a future operation:

```text
EXPECTED_CHANNEL_TITLE = Clone Pessoal - WRomanov
EXPECTED_CHANNEL_ID = -1002368271467
UPLOAD_TYPE = DOCUMENT
```

Before selecting the file, resolve the destination in the 64Gram client and verify both the displayed title and the resolved peer ID against the expected values. Abort on any mismatch or ambiguity. Send the original file as a document/file, without changing its bytes or name. This task did not connect to Telegram and cannot attest that the channel is currently reachable or that the displayed title maps to the supplied ID.

After a separately approved upload, refetch the newly created message from that channel and verify all of the following before preparing any remote query:

```text
channel_id = -1002368271467
message_id = newly fetched message ID
media_id = newly fetched document identity
ordinal = 0
kind = DOCUMENT
document.size = 1119129690
```

The message ID and media ID are unknown until that future upload/refetch. The filename alone is not identity.

## EOF probe specification

For `E = 1,119,129,690` and alignment `B = 131,072` bytes (128 KiB):

```text
E mod B = 36,954
floor((E - 1) / B) = 8,538
LAST_ALIGNED_RANGE_OFFSET = 8,538 * 131,072 = 1,119,092,736
EXPECTED_FINAL_RANGE_LENGTH = E - LAST_ALIGNED_RANGE_OFFSET = 36,954
```

Once the remote message identity and `document.size` have been verified, a separately approved EOF probe may issue exactly one `upload.getFileHashes` call for the newly refetched document location with `offset=1,119,092,736`. The method accepts an offset and returns a vector of `FileHash`; each entry carries `offset`, `limit` and a SHA-256 digest. The probe has no `GetFile` fallback and no media payload allowance. Do not assume how many ranges the vector contains.

Accept the EOF result only if the returned ranges validate without gaps, overlaps, invalid lengths or digests, start at the requested offset, and end exactly at `document.size`. Do not truncate, pad, clamp, or synthesize a range to make it fit. Empty, partial, rejected, malformed, gapped, overlapping, or EOF-crossing results are sanitized failures and stop the proof before any full download.

The remote digest is compared with a streaming local SHA-256 of exactly the matching reference bytes and kept only in memory. Persist only sanitized geometry and classification: request offset, returned range count, range offsets/lengths, digest length, and result. Never persist or print digest bytes or their hex representation.

Telegram documents `upload.getFileHashes(location, offset)` as returning a vector of `FileHash`, and defines each hash range by its offset, length and digest. The API documentation does not establish the response geometry for this particular uploaded document, so the one-call budget bounds requests while incomplete coverage remains a stop condition. [Method reference](https://core.telegram.org/method/upload.getFileHashes) · [FileHash fields](https://core.telegram.org/constructor/fileHash).

## Finite RPC budgets for a later proof

These are proposed hard ceilings for a later, separately authorized proof. They do not authorize execution and do not guarantee that remote coverage will finish within the caps.

| Budget | Proposed ceiling | Derivation / stop condition |
|---|---:|---|
| EOF probe | 1 `GetFileHashes`; 0 `GetFile`; 0 payload bytes | User-specified one-call diagnostic. Any incomplete or invalid EOF response stops. |
| Full download, aligned case | 4,270 `GetFile` reservations per attempt; 12,810 across three attempts; 3,358,064,640 reserved bytes | `ceil(E / 262,144) = 4,270`; reserve 256 KiB before each request; three S5 attempts maximum. |
| Full download, unaligned case | 4,271 reservations per attempt; 12,813 across three attempts; 3,358,851,072 reserved bytes | Initial checkpoint `P=134,217,851`; wire offset `W=134,217,728`; overlap `O=123`; first pass needs at most 513 reservations and resumed stream from `W` at most 3,758. |
| Full download, both cases | 25,623 reservations; 6,716,915,712 reserved bytes | Sum of aligned and unaligned caps above; no hidden retries; uncertain reservations remain charged. |
| Remote coverage, each full proof case | At most 8,539 `GetFileHashes` calls | Hard stop threshold `ceil(E / 131,072)`. It does not presume one or multiple hashes per response, or that this cap suffices. Stop as soon as contiguous coverage is complete; fail closed if the cap is reached first. |
| Remote coverage, both cases | At most 17,078 calls | Sum of two isolated proof cases; EOF probe's separate one-call allowance is not included. |

Reservations are rounded to the full 256 KiB request size. The prior reference-preparation note used `3 × (E + 256 KiB)` for a payload ceiling; that byte formula is below the full-size reservation total for 4,271 requests. This report supersedes it with request-quantized ceilings. Each proof case still needs a separately approved aggregate `GetFileHashes` cap and `GetFile` cap before execution. An incomplete response, rejected range, FloodWait, exhausted call/byte cap or insufficient disk space stops without promotion. No response cardinality is assumed.

The EOF probe is only a last-range compatibility and integrity check. It does not prove that the whole remote document matches the local file. Full S6 acceptance still requires complete remote coverage, aligned and unaligned restart cases, byte-for-byte final comparison, correct size and local SHA-256, SQLite/checkpoint validation, and no-overwrite finalization under the frozen contract.

## Validation and safety

```text
REFERENCE_GATE = PASS
UPLOAD_PLAN_READY = YES / destination-ID check is a mandatory pre-upload gate
TARGET_IDENTITY_PLAN = READY / remote message and media IDs remain unknown until future upload/refetch
EOF_PROBE_READY = CONDITIONAL / geometry and strict caps prepared; existing executable is bound to a different target
INITIAL_HASH_RPC_BUDGET = 1 GetFileHashes / 0 GetFile / 0 payload bytes
REAL_TELEGRAM_CALLS = 0
UPLOAD_EXECUTED = NO
DOWNLOAD_EXECUTED = NO
S6_FORMAL_ACCEPTANCE = PENDING
SPRINT_CHECKPOINT = DEFERRED
```

The existing `Invoke-S6HashEofProbe.ps1 -Mode DryRun` passed with zero Telegram calls, zero payload and no session restore, but its hard-coded target is channel `-1002758699600`, message `598`, offset `11,534,336`, and two hash calls. It is not the prepared probe for this upload. It was not changed or used for an Execute.

Offline verification: 13 deterministic range, EOF-classification, sanitization and DryRun tests passed. A broader selected run stalled in the sandbox's Windows asyncio/temporary-directory environment and was stopped; the first attempt also could not create pytest temp directories under `%TEMP%`. Ruff passed for `src`, `tests` and `tools/manual_proofs`; `compileall` passed for `src` and `tools/manual_proofs`; `git diff --check` passed, with only existing LF/CRLF notices.

```text
NEXT_ACTION = REQUEST_CONTROLLED_UPLOAD_APPROVAL
```
