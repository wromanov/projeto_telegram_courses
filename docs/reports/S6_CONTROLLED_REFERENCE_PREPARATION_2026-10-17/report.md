# S6 Controlled Reference Preparation

```text
PROJECT_ID = projeto_telegram_courses
ACTIVITY = S6_CONTROLLED_REFERENCE_PREPARATION
REFERENCE_GATE = PASS
CONTRACT = S6_PARTIAL_DOWNLOAD_RESUME_RECOVERY_CONTRACT / APPROVED / FROZEN
MODE = LOCAL_READ_ONLY
```

## Repository and governance preflight

- Governance Baseline: V1, per `docs/continuity/PROJECT_GOVERNANCE_BINDING.json`.
- Active Authority Map points to the approved/frozen S6 contract.
- Repository: `C:/Users/walac/desenvolvimento/projeto_telegram_courses`.
- Branch: `work/s0-bootstrap`.
- HEAD: `98d9d6b9ce152b8d2764a4d160fcbdf4722fb257`.
- The worktree was already dirty. Existing changes were preserved; no Git operation was performed.

## Reference capture

- Source: `C:\Users\walac\Downloads\64Gram Desktop\Teste Telegram.rar`
- Resolved path: same as the supplied path.
- File type: regular file; extension `.rar`; readable.
- Size: `1,119,129,690` bytes.
- SHA-256: `3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c`.
- Last write UTC: `2026-10-17T05:35:28.9950068Z`.
- Reference capture time UTC: `2026-10-17T05:46:45.5079847Z`.
- SHA-256 was computed by streaming a read-only `FileStream` with a 1 MiB buffer (`1,119,129,690` bytes read); file contents were not loaded as one in-memory object.
- Size and `LastWriteTimeUtc` were identical before and after the hash; stability gate passed.
- Provenance recorded: user provided the exact path. Origin/creator was not independently verified.
- The original was not modified, renamed, compressed, extracted, moved, or uploaded.

The JSON manifest beside this report records these fields. It was created before any upload. The source file hash is a local reference only; it does not replace remote `GetFileHashes` coverage required by S6.

## EOF and checkpoint alignment

File EOF alignment is distinct from checkpoint alignment and from remote `FileHash.limit` semantics.

| Quantity | Result |
|---|---:|
| File size modulo 128 KiB | 36,954 bytes; not aligned; 8,539 ceiling blocks |
| File size modulo 256 KiB | 36,954 bytes; not aligned; 4,270 ceiling blocks |
| Proposed aligned checkpoint `P` | 134,217,728 bytes (128 MiB), aligned to 256 KiB |
| Initial aligned interruption | 512 full-size 256 KiB reservations to reach `P`; estimate only |
| Proposed unaligned checkpoint `P` | 134,217,851 bytes (128 MiB + 123) |
| Initial unaligned interruption | 513 full-size 256 KiB reservations to reach/cover `P`; estimate only, with the final response potentially extending past `P` |
| Wire offset `W = floor(P / 256 KiB) × 256 KiB` | 134,217,728 bytes |
| Overlap `O = P - W` | 123 bytes |
| Aligned resume payload | `E-P = 984,911,962` bytes; 3,758 ceiling 256 KiB reservations |
| Unaligned resume payload from `W` | `E-W = 984,911,962` bytes; 3,758 ceiling 256 KiB reservations, including 123 overlap bytes to compare before append |

The reservation counts above assume a maximum 256 KiB payload per `GetFile` reservation. They are not observed RPC counts or a claim about Telegram response geometry. The unaligned proof must keep the existing 123-byte suffix for comparison and append only after it matches.

For the unaligned case, prepare an isolated second proof root with the valid 128 MiB prefix and the 123-byte suffix copied from the reference; label this as a prepared fixture, not a spontaneous process interruption. Process 2 must still establish remote hash coverage for the entire existing prefix and compare the overlap before append.

The file remainders do not predict Telegram hash-range lengths or behavior at EOF. If `GetFileHashes` coverage is incomplete, invalid, or crosses the expected EOF in a way rejected by the validator, preserve the `.part` and stop.

## Controlled proof design and estimates

Use one legitimate Telegram `DOCUMENT`, one media item, one worker, isolated roots and SQLite databases, existing S4/S5 mechanisms, and explicit native confirmation for any future remote execution.

1. Keep the source reference immutable. After a separately approved upload, verify the remote peer/channel ID, message ID, media ordinal zero, `DOCUMENT` type, media ID, and exact size against the manifest. Do not use the filename as identity.
2. Aligned run: Process 1 downloads to `P=128 MiB`, flushes/fsyncs and persists a matching checkpoint, then exits. Process 2 must have a distinct PID, refetch the same message, prove remote coverage of `[0,P)`, resume and verify remote coverage of the continuation through EOF.
3. Unaligned run: use a separate proof root and the prepared `P=128 MiB+123` prefix fixture above. Process 2 must validate the prefix and all 123 overlap bytes before appending at `P`.
4. In each run, compare the completed file byte-for-byte with the reference, independently validate complete-file SHA-256 and exact size, verify database state, atomically rename without overwrite, and confirm `DOWNLOADED`. A later dedup invocation must perform zero new payload transfer.
5. A hash gap, invalid range, EOF crossing, identity mismatch, FloodWait or exhausted cap stops the run without promotion. Preserve all `.part` and proof evidence.

For `E=1,119,129,690` and `C=262,144`, a single full payload pass is estimated at `ceil(E/C)=4,270` `GetFile` reservations, with a final returned block of 36,954 bytes. Two proof cases have a baseline of about `8,540` reservations and `2,238,259,380` payload bytes total, before retries or uncertain reservations. Under S5's maximum of three attempts, a conservative preliminary cap is `3 × (E+C) = 3,358,175,502` payload bytes and at most `12,813` full-size `GetFile` reservations per isolated case; both cases together would be capped at `6,716,351,004` payload bytes / `25,626` such reservations. These are planning ceilings, not observed runtime counts; the adapter must reserve 256 KiB before each request and fail closed when the shared cap cannot cover it. Hidden RPC retries must remain disabled under the capped path.

Disk estimate, assuming both final proof outputs are retained and roots share a volume: two files (`2E`) plus the S5 free-space margin (`MAX(1 GiB, 10% of pending bytes)`, therefore 1 GiB) = at least `3,312,001,204` bytes of free capacity for proof artifacts, plus small SQLite/ledger/report overhead. The original reference already occupies its existing space and must remain preserved. `.part` is renamed atomically on the same volume, so do not count a second full-size copy for finalization.

### `GetFileHashes` budget gate

The frozen contract has no numeric RPC cap for `GetFileHashes`, and this activity made no Telegram calls. Do not infer a count of ranges per response from the 128 KiB/256 KiB block sizes. A finite, user-approved maximum `GetFileHashes` RPC count per run and an aggregate ceiling across both runs remain necessary. If that cap is reached before complete coverage, stop; do not substitute local SHA-256, partial coverage, or unbudgeted `GetFile` payload.

```text
GETFILEHASHES_BUDGET = NOT_SET / RESPONSE GEOMETRY UNOBSERVED
RPC_BUDGET_READY = NO
REAL_PROOF_PLAN_READY = NO / target identity and GetFileHashes cap remain pending
CONTROLLED_MEDIA_ELIGIBILITY = CONDITIONAL / local file meets recommended size; remote DOCUMENT identity is pending future upload verification
```

## External size compatibility

The source size is about 1.12 GB. Telegram's official FAQ currently lists 2 GB per file for regular accounts and 4 GB for Premium, so this size is below the published regular-account limit. The actual 64Gram client/account upload must still be verified during a separately authorized upload. Sources: [Telegram FAQ](https://telegram.org/faq) and [Telegram Premium FAQ](https://telegram.org/faq_premium/).

## Safety and outcome

```text
REAL_TELEGRAM_CALLS = 0
UPLOAD_EXECUTED = NO
DOWNLOAD_EXECUTED = NO
SQLITE_OR_HISTORICAL_PART_ACCESS = NO
SOURCE_FILE_MODIFIED = NO
CONTRACT_MODIFIED = NO
FILES_CREATED = THIS ISOLATED REPORT AND REFERENCE MANIFEST ONLY
GIT_ADD = NO
GIT_COMMIT = NO
GIT_PUSH = NO
SPRINT_CHECKPOINT = DEFERRED
S6_FORMAL_ACCEPTANCE = PENDING
NEXT_ACTION = Separately approve the private-channel upload and later proof; after remote identity verification, close a finite GetFileHashes RPC ceiling before any Execute.
```
