"""Fail-closed read-only gate for exactly the third attempt on message 585.

All state checks are against local product SQLite and existing files. No Telegram
session, remote RPC, downloads, or writes are performed in this module.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path

from telegram_courses.downloads import _reject_reparse_path
from telegram_courses.s5_downloads import DownloadPlanner, DownloadSelection

CHANNEL = -1002758699600
MODULE = 44
MESSAGE = 585
EXPECTED_BYTES = 6199635
PREFIX_BYTES = 6029312
MAX_WIRE_BUDGET = 6291456
ROOT = Path(os.environ["LOCALAPPDATA"]) / "telegram_courses_product"
DB = ROOT / "db/catalog.sqlite3"
DOWNLOADS = ROOT / "downloads"
FIRST_MARKER = ROOT / "db/resume_final_01_recover585_once.started"
THIRD_MARKER = ROOT / "db/resume_final_01_recover585_third.started"
RECEIPT = ROOT / "db/resume_final_01_stage1.json"
WAVE2_MARKER = ROOT / "db/resume_final_01_wave2_started.json"


def digest_file(path: Path, *, first_bytes: int | None = None) -> str:
    digest = hashlib.sha256()
    left = first_bytes
    with path.open("rb") as stream:
        while left is None or left:
            read_size = 262144 if left is None else min(left, 262144)
            data = stream.read(read_size)
            if not data:
                break
            digest.update(data)
            if left is not None:
                left -= len(data)
    if left not in (None, 0):
        raise ValueError("DIGEST_INPUT_TRUNCATED")
    return digest.hexdigest()


def _validate_state(row: sqlite3.Row, *, post: bool) -> None:
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
        or row["owner_pid"] is not None
    ):
        raise ValueError("IDENTITY_OR_OWNER_CHANGED")
    if post:
        if (
            row["state"] != "DOWNLOADED"
            or row["attempts"] != 3
            or row["downloaded_bytes"] != EXPECTED_BYTES
            or row["failure_category"] is not None
            or not isinstance(row["sha256"], str)
            or re.fullmatch(r"[a-f0-9]{64}", row["sha256"]) is None
        ):
            raise ValueError("THIRD_ATTEMPT_NOT_VALIDATED")
    elif (
        row["state"] != "FAILED_RETRYABLE"
        or row["attempts"] != 2
        or row["downloaded_bytes"] != PREFIX_BYTES
        or row["failure_category"] != "GATEWAY_FAILURE"
        or row["sha256"] is not None
    ):
        raise ValueError("THIRD_ATTEMPT_PRECONDITION_CHANGED")


async def check(*, post: bool = False) -> None:
    if RECEIPT.exists() or WAVE2_MARKER.exists():
        raise ValueError("PREVIOUS_SUCCESS_OR_WAVE2_EXISTS")
    if not FIRST_MARKER.is_file() or FIRST_MARKER.is_symlink():
        raise ValueError("SECOND_ATTEMPT_MARKER_MISSING_OR_UNSAFE")
    former = json.loads(FIRST_MARKER.read_text(encoding="utf-8"))
    if (
        former.get("activity") != "TELEGRAM-3-RESUME-FINAL-01"
        or former.get("message_id") != MESSAGE
        or former.get("status") != "RECOVERY_ONCE_STARTED"
    ):
        raise ValueError("SECOND_ATTEMPT_MARKER_INVALID")
    if THIRD_MARKER.exists() is not post:
        raise ValueError("THIRD_ATTEMPT_MARKER_STATE")
    previous_digest = None
    if post:
        if THIRD_MARKER.is_symlink() or not THIRD_MARKER.is_file():
            raise ValueError("THIRD_ATTEMPT_MARKER_UNSAFE")
        mark = json.loads(THIRD_MARKER.read_text(encoding="utf-8"))
        previous_digest = mark.get("prefix_sha256")
        if (
            mark.get("activity") != "TELEGRAM-3-RESUME-FINAL-01"
            or mark.get("message_id") != MESSAGE
            or mark.get("status") != "THIRD_ATTEMPT_STARTED"
            or not isinstance(previous_digest, str)
            or re.fullmatch(r"[a-f0-9]{64}", previous_digest) is None
        ):
            raise ValueError("THIRD_ATTEMPT_MARKER_INVALID")
    if not DB.is_file() or not DOWNLOADS.is_dir():
        raise ValueError("PRIVATE_PRODUCT_WORKSPACE_MISSING")
    db = sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("DB_QUICK_CHECK_FAILED")
        scope = db.execute(
            "SELECT m.title AS module_title, m.kind AS module_kind,"
            "c.title AS course_title, c.kind AS course_kind "
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
            raise ValueError("CATALOG_MODULE_CHANGED")
        rows = db.execute(
            "SELECT m.telegram_message_id, m.file_size_bytes, m.kind,"
            "m.remote_observation_state, m.telegram_media_id, "
            "d.state,d.attempts,d.expected_bytes,d.downloaded_bytes,"
            "d.failure_category,d.sha256,d.owner_pid,d.final_path,d.partial_path,"
            "d.remote_identity_media_id,d.remote_identity_kind,"
            "d.remote_identity_size,d.remote_identity_provenance "
            "FROM media_items m JOIN catalog_nodes n ON n.id=m.catalog_node_id "
            "LEFT JOIN downloads d ON d.media_item_id=m.id "
            "WHERE m.channel_id=? AND n.parent_id=? AND m.telegram_message_id IN (585,586,587) "
            "ORDER BY m.telegram_message_id",
            (CHANNEL, MODULE),
        ).fetchall()
        if len(rows) != 3 or tuple(r["telegram_message_id"] for r in rows) != (585, 586, 587):
            raise ValueError("MESSAGE_SET_CHANGED")
        row = rows[0]
        _validate_state(row, post=post)
        for other in rows[1:]:
            if other["state"] is not None or other["attempts"] is not None:
                raise ValueError("OTHER_MEDIA_ALREADY_ATTEMPTED")
        final_path = Path(row["final_path"])
        part_path = Path(row["partial_path"])
        if (
            not final_path.is_relative_to(DOWNLOADS)
            or not part_path.is_relative_to(DOWNLOADS)
            or str(part_path) != str(final_path) + ".part"
        ):
            raise ValueError("PRODUCT_DOWNLOAD_PATH_CHANGED")
        _reject_reparse_path(DOWNLOADS.absolute(), final_path)
        _reject_reparse_path(DOWNLOADS.absolute(), part_path)
        if post:
            if (
                part_path.exists()
                or final_path.is_symlink()
                or not final_path.is_file()
                or final_path.stat().st_size != EXPECTED_BYTES
                or digest_file(final_path) != row["sha256"]
                or digest_file(final_path, first_bytes=PREFIX_BYTES) != previous_digest
            ):
                raise ValueError("POST_FINAL_FILE_OR_PREFIX_INVALID")
        else:
            if (
                final_path.exists()
                or part_path.is_symlink()
                or not part_path.is_file()
                or part_path.stat().st_size != PREFIX_BYTES
            ):
                raise ValueError("PARTIAL_SIZE_OR_PATH_CHANGED")
            prefix_digest = digest_file(part_path)
    finally:
        db.close()
    planner = DownloadPlanner(DB, DOWNLOADS)
    plan = await planner.build(DownloadSelection(CHANNEL, "module", MODULE))
    selected = [item for item in plan.items if item.identity[1] in (585, 586, 587)]
    statuses = tuple(item.status for item in selected)
    wanted = (
        ("ALREADY_VALID", "PENDING", "PENDING")
        if post else ("CONDITIONAL_RESUME_CANDIDATE", "PENDING", "PENDING")
    )
    if len(selected) != 3 or statuses != wanted:
        raise ValueError("PLANNER_STATES_CHANGED")
    if not post and (
        selected[0].part_bytes != PREFIX_BYTES
        or selected[0].wire_offset != PREFIX_BYTES
        or selected[0].overlap_bytes != 0
        or selected[0].estimated_payload_bytes != EXPECTED_BYTES - PREFIX_BYTES
    ):
        raise ValueError("PREFIX_GEOMETRY_CHANGED")
    print("RECOVERY585_THIRD_POST=PASS" if post else "RECOVERY585_THIRD_PREFLIGHT=PASS")
    print(f"MEDIA=585 EXPECTED={EXPECTED_BYTES} PREFIX={PREFIX_BYTES} REMAINING={EXPECTED_BYTES-PREFIX_BYTES}")
    print(f"GETFILE_RESERVATION_CAP={MAX_WIRE_BUDGET}")
    if not post:
        print("PREFIX_SHA256=" + prefix_digest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(check(post=args.post))
        return 0
    except Exception as exc:
        print("RECOVERY585_THIRD_BLOCKED=" + type(exc).__name__)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
