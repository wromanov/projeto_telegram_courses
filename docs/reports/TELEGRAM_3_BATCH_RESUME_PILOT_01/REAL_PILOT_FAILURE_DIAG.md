# TELEGRAM-3-BATCH-RESUME-PILOT-01 — real failed pilot, read-only diagnosis (2026-11-02/03)

## Native evidence reported by operator
- Queue status FAILED, total=5, completed=0, failed=5, attempts=5, transferred=73071671 bytes, elapsed=88.2s.
- No G5–G9 S9 acceptance implied, this is product pilot not frozen S9.

## Read-only evidence inspected through Remote Desktop Commander
- ROMA_CASA online; database %LOCALAPPDATA%\telegram_courses_product\db\catalog.sqlite3 opened using SQLite mode=ro and query_only=ON; quick_check=ok.
- Five scoped downloads belong to RASMOO, Candidato de Ouro / Contagem Regressiva (module id 46).
- All five are state FAILED_RETRYABLE with identical failure_category=REMOTE_HASH_RANGE_INVALID.
- Downloaded bytes recorded equal expected bytes for all five: 11649955, 12780862, 24492009, 17406384, 6742461.
- Five .part files exist under product root with their full expected byte sizes. Five finalized .mp4 files are absent at recorded final paths. SHA-256 completion digest not stored.
- s6_v2_attempts and s6_v2_evidence tables remain empty.
- No further RPC or download performed during this diagnosis; no changes to part files or database.

## Proven interpretation
- src/telegram_courses/downloads.py::_remote_hashes rejects any server-returned FileHash range with (offset + limit) > candidate.expected_bytes and raises REMOTE_HASH_RANGE_INVALID.
- Since all five failed on this exact category, the remote hash response had at least one range exceeding declared EOF for each item, as handled by the current parser.
- The upstream Telegram FileHash contract defines a digest over exactly offset/limit bytes, not a digest that may be safely truncated. Never clamp a range nor assume zero padding to force equality.
- Therefore full-file independent remote-hash proof is not established and the configured strict fail-closed behavior correctly prevented finalization. This is a contract/evidence geometry problem, not a network transfer failure.
- It is not yet proven whether these terminal remote hash ranges reflect alignment/padding behavior, inconsistent metadata, or other upstream response shape; no raw hash data is retained and no subsequent RPC was authorized.

## Operational decision
- FIVE_ATTEMPTS_CONSUMED=YES; new download prohibited without renewed authorization.
- Preserve five .part files and product database; do not rename, modify, quarantine, delete or force-complete under current authority.
- Strict mode retained: do not silently replace REMOTE_HASH_REQUIRED by local SHA-256, re-fetch, or OPERATIONAL_ONLY.
- Next engineering action: isolate the exact server hash range geometry with sanitized offset/limit metadata from a separately authorized metadata-only probe, or demonstrate an officially supported verification method for EOF without lost coverage. An alternative weaker guarantee would need separate explicit human approval.
- Product pilot state: TRANSFER=5 payloads downloaded but unfinalized; BATCH_ACCEPTANCE=FAILED; RESUME_REAL=NOT_PROVEN; S9_ACCEPTANCE remains PARTIAL.
