"""Read-only pre/post guard for the final authorized attempt on MP4 585."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import sqlite3
from pathlib import Path

from telegram_courses.downloads import _reject_reparse_path
from telegram_courses.s5_downloads import DownloadPlanner, DownloadSelection
from telegram_courses.s9_operational_ledger import _open_private_directory_guard

ACTIVITY = "TELEGRAM-3-585-FINAL-CLOSURE-01"
PREVIOUS_ACTIVITY = "TELEGRAM-3-RESUME-FINAL-01"
CHANNEL = -1002758699600
MODULE = 44
MESSAGE = 585
EXPECTED_BYTES = 6_199_635
PREFIX_BYTES = 6_029_312
MAX_WIRE_BUDGET = 6_291_456
EXPECTED_FAILURE = "REMOTE_HASH_RANGE_INVALID"

PRODUCT = Path(os.environ["LOCALAPPDATA"]) / "telegram_courses_product"
DB_DIR = PRODUCT / "db"
DB = DB_DIR / "catalog.sqlite3"
DOWNLOADS = PRODUCT / "downloads"
FIRST_MARKER = DB_DIR / "resume_final_01_recover585_once.started"
THIRD_MARKER = DB_DIR / "resume_final_01_recover585_third.started"
FOURTH_MARKER = DB_DIR / "resume_final_01_recover585_fourth.started"
STAGE1_RECEIPT = DB_DIR / "resume_final_01_stage1.json"
WAVE2_MARKER = DB_DIR / "resume_final_01_wave2_started.json"


class PreflightBlocked(Exception):
    pass


def _fail(code: str) -> None:
    raise PreflightBlocked(code)


def _hash_file(path: Path, *, byte_limit: int | None = None) -> str:
    digest = hashlib.sha256()
    remaining = byte_limit
    with path.open("rb") as stream:
        while remaining is None or remaining:
            size = 262_144 if remaining is None else min(262_144, remaining)
            chunk = stream.read(size)
            if not chunk:
                break
            digest.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    if remaining not in (None, 0):
        _fail("HASH_INPUT_TRUNCATED")
    return digest.hexdigest()


def _marker(path: Path, *, required: bool, status: str, activity: str) -> dict[str, object] | None:
    if not os.path.lexists(path):
        if required:
            _fail("REQUIRED_MARKER_MISSING")
        return None
    if path.is_symlink() or not path.is_file():
        _fail("MARKER_PATH_UNSAFE")
    _reject_reparse_path(DB_DIR.absolute(), path.absolute())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _fail("MARKER_UNREADABLE")
    if (
        not isinstance(data, dict)
        or data.get("activity") != activity
        or data.get("message_id") != MESSAGE
        or data.get("status") != status
    ):
        _fail("MARKER_CONTENT_INVALID")
    return data


def _private_directory(path: Path) -> None:
    guard = _open_private_directory_guard(path)
    try:
        guard.verify(path)
    finally:
        guard.close()


def _read_rows(db: sqlite3.Connection) -> tuple[sqlite3.Row, list[sqlite3.Row]]:
    scope = db.execute(
        "SELECT m.title module_title,m.kind module_kind,c.title course_title,c.kind course_kind "
        "FROM catalog_nodes m JOIN catalog_nodes c ON c.id=m.parent_id "
        "WHERE m.id=? AND m.channel_id=?",
        (MODULE, CHANNEL),
    ).fetchone()
    if (
        scope is None
        or scope["module_title"] != "Competências"
        or scope["module_kind"] != "module"
        or scope["course_kind"] != "course"
        or not str(scope["course_title"]).startswith("Candidato de Ouro ")
    ):
        _fail("CATALOG_SCOPE_CHANGED")
    rows = db.execute(
        "SELECT m.id media_item_id,m.telegram_message_id,m.file_size_bytes,m.kind,"
        "m.remote_observation_state,m.telegram_media_id,d.state,d.attempts,"
        "d.expected_bytes,d.downloaded_bytes,d.failure_category,d.sha256,d.owner_pid,"
        "d.final_path,d.partial_path,d.remote_identity_media_id,d.remote_identity_kind,"
        "d.remote_identity_size,d.remote_identity_provenance "
        "FROM media_items m JOIN catalog_nodes n ON n.id=m.catalog_node_id "
        "LEFT JOIN downloads d ON d.media_item_id=m.id "
        "WHERE m.channel_id=? AND n.parent_id=? AND m.telegram_message_id IN (585,586,587) "
        "ORDER BY m.telegram_message_id",
        (CHANNEL, MODULE),
    ).fetchall()
    if len(rows) != 3 or tuple(row["telegram_message_id"] for row in rows) != (585, 586, 587):
        _fail("MESSAGE_SET_CHANGED")
    return rows[0], rows


def _assert_media_identity(row: sqlite3.Row) -> None:
    if (
        row["file_size_bytes"] != EXPECTED_BYTES
        or row["expected_bytes"] != EXPECTED_BYTES
        or row["kind"] != "DOCUMENT"
        or row["remote_observation_state"] != "OBSERVED"
        or not row["telegram_media_id"]
        or row["remote_identity_media_id"] != row["telegram_media_id"]
        or row["remote_identity_kind"] != "DOCUMENT"
        or row["remote_identity_size"] != EXPECTED_BYTES
        or row["remote_identity_provenance"] != "CAPTURED_AT_START"
    ):
        _fail("CAPTURED_MEDIA_IDENTITY_CHANGED")


def _check(*, post: bool) -> None:
    if not PRODUCT.is_dir() or not DB.is_file() or not DB_DIR.is_dir() or not DOWNLOADS.is_dir():
        _fail("PRIVATE_PRODUCT_WORKSPACE_MISSING")
    for path in (PRODUCT, DB_DIR, DOWNLOADS):
        _private_directory(path)
    _reject_reparse_path(DB_DIR.absolute(), DB.absolute())

    first = _marker(
        FIRST_MARKER, required=True, status="RECOVERY_ONCE_STARTED", activity=PREVIOUS_ACTIVITY,
    )
    third = _marker(
        THIRD_MARKER, required=True, status="THIRD_ATTEMPT_STARTED", activity=PREVIOUS_ACTIVITY,
    )
    fourth = _marker(
        FOURTH_MARKER, required=post, status="FOURTH_ATTEMPT_STARTED", activity=ACTIVITY,
    )
    if not post and fourth is not None:
        _fail("FOURTH_ATTEMPT_ALREADY_CONSUMED")
    if os.path.lexists(STAGE1_RECEIPT) or os.path.lexists(WAVE2_MARKER):
        _fail("PRIOR_SUCCESS_OR_WAVE2_MARKER_EXISTS")
    if first is None or third is None:
        _fail("PREVIOUS_ATTEMPT_MARKERS_INVALID")
    prefix_hash = third.get("prefix_sha256")
    if not isinstance(prefix_hash, str) or re.fullmatch(r"[a-f0-9]{64}", prefix_hash) is None:
        _fail("THIRD_PREFIX_HASH_MISSING")
    if post and (
        fourth is None
        or fourth.get("attempt_number") != 4
        or fourth.get("prior_attempts") != 3
        or fourth.get("prefix_bytes") != PREFIX_BYTES
        or fourth.get("prefix_sha256") != prefix_hash
        or fourth.get("g0_confirmation") != "HUMAN_INTERACTIVE"
    ):
        _fail("FOURTH_ATTEMPT_MARKER_INVALID")

    conn = sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    try:
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            _fail("DB_QUICK_CHECK_FAILED")
        row, rows = _read_rows(conn)
        _assert_media_identity(row)
        for other in rows[1:]:
            if other["state"] is not None or other["attempts"] is not None:
                _fail("OTHER_MEDIA_ATTEMPTED")

        final = Path(row["final_path"])
        part = Path(row["partial_path"])
        if (
            not final.is_relative_to(DOWNLOADS)
            or not part.is_relative_to(DOWNLOADS)
            or str(part) != str(final) + ".part"
        ):
            _fail("PRODUCT_DOWNLOAD_PATH_CHANGED")
        _reject_reparse_path(DOWNLOADS.absolute(), final.absolute())
        _reject_reparse_path(DOWNLOADS.absolute(), part.absolute())

        if not post:
            if (
                row["state"] != "FAILED_RETRYABLE"
                or row["attempts"] != 3
                or row["downloaded_bytes"] != PREFIX_BYTES
                or row["failure_category"] != EXPECTED_FAILURE
                or row["sha256"] is not None
                or row["owner_pid"] is not None
                or os.path.lexists(final)
                or part.is_symlink()
                or not part.is_file()
                or part.stat().st_size != PREFIX_BYTES
            ):
                _fail("FOURTH_ATTEMPT_PRECONDITION_CHANGED")
            current_prefix_hash = _hash_file(part)
            if current_prefix_hash != prefix_hash:
                _fail("PREFIX_HASH_CHANGED")
        else:
            if (
                row["state"] != "DOWNLOADED"
                or row["attempts"] != 4
                or row["downloaded_bytes"] != EXPECTED_BYTES
                or row["failure_category"] is not None
                or row["owner_pid"] is not None
                or not isinstance(row["sha256"], str)
                or re.fullmatch(r"[a-f0-9]{64}", row["sha256"]) is None
                or os.path.lexists(part)
                or final.is_symlink()
                or not final.is_file()
                or final.stat().st_size != EXPECTED_BYTES
                or _hash_file(final) != row["sha256"]
                or _hash_file(final, byte_limit=PREFIX_BYTES) != prefix_hash
            ):
                _fail("FINAL_FILE_OR_PREFIX_INVALID")
    finally:
        conn.close()

    async def check_plan() -> tuple[str, ...]:
        plan = await DownloadPlanner(DB, DOWNLOADS).build(
            DownloadSelection(CHANNEL, "module", MODULE)
        )
        selected = [item for item in plan.items if item.identity[1] in (585, 586, 587)]
        wanted = (
            ("ALREADY_VALID", "PENDING", "PENDING")
            if post else
            ("CONDITIONAL_RESUME_CANDIDATE", "PENDING", "PENDING")
        )
        if len(selected) != 3 or tuple(item.status for item in selected) != wanted:
            _fail("LOCAL_PLANNER_SCOPE_CHANGED")
        if not post and (
            selected[0].part_bytes != PREFIX_BYTES
            or selected[0].wire_offset != PREFIX_BYTES
            or selected[0].overlap_bytes != 0
            or selected[0].estimated_payload_bytes != EXPECTED_BYTES - PREFIX_BYTES
        ):
            _fail("LOCAL_PLANNER_PREFIX_GEOMETRY_CHANGED")
        return tuple(f"{item.identity[1]}:{item.status}" for item in selected)

    plan_state = asyncio.run(check_plan())
    free_bytes = shutil.disk_usage(DOWNLOADS).free
    if free_bytes < MAX_WIRE_BUDGET:
        _fail("DISK_SPACE_BELOW_TRANSFER_BUDGET")
    if post:
        print("RECOVERY585_FOURTH_POST=PASS")
        print("ATTEMPTS=4;STATE=DOWNLOADED;REMOTE_HASH_MODE=REQUIRED")
        print(f"LOCAL_PLAN={','.join(plan_state)}")
    else:
        print("RECOVERY585_FOURTH_PREFLIGHT=PASS")
        print("CURRENT_ATTEMPTS=3;NEXT_ATTEMPT=4;MAX_ATTEMPTS_THIS_RUN=1")
        print(f"PART_SIZE={PREFIX_BYTES};REMAINING_BYTES={EXPECTED_BYTES-PREFIX_BYTES}")
        print(f"GETFILE_RESERVATION_CAP={MAX_WIRE_BUDGET};DISK_FREE_BYTES={free_bytes}")
        print("LOCAL_IDENTITY=PASS;REMOTE_IDENTITY_REVALIDATION=REQUIRED_AFTER_G0")
        print("STRICT_INTEGRITY=REMOTE_HASH_REQUIRED;REMOTE_HASH_FULL_REQUIRED")
        print("NO_RPC_OR_DOWNLOAD_OCCURRED=YES")
        print(f"LOCAL_PLAN={','.join(plan_state)}")
        print("PREFIX_SHA256=" + prefix_hash)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post", action="store_true")
    args = parser.parse_args()
    try:
        _check(post=args.post)
        return 0
    except Exception as exc:
        name = str(exc) if isinstance(exc, PreflightBlocked) else type(exc).__name__
        print("RECOVERY585_FOURTH_BLOCKED=" + name)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
