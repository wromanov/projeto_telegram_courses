"""Offline-only preflight for TELEGRAM-3-RESUME-FINAL-01.

Does not contact Telegram, mutate the catalog, or create any file.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
from pathlib import Path

from telegram_courses.s5_downloads import DownloadPlanner, DownloadSelection

CHANNEL = -1002758699600
MODULE = 44
IDS = (585, 586, 587)
SIZES = (6199635, 11235719, 11028396)
MAX_TOTAL_BYTES = 268435456
MAX_SINGLE_BYTES = 134217728
ROOT = Path(os.environ["LOCALAPPDATA"]) / "telegram_courses_product"
DB = ROOT / "db/catalog.sqlite3"
DESTINATION = ROOT / "downloads"
RECEIPT = ROOT / "db/resume_final_01_stage1.json"
WAVE2_MARKER = ROOT / "db/resume_final_01_wave2_started.json"


async def check(phase: int, *, post: bool = False) -> None:
    if phase not in (1, 2):
        raise ValueError("INVALID_WAVE")
    expected_first_attempts = 1
    if phase == 2 and RECEIPT.is_file():
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        if (
            receipt.get("activity") != "TELEGRAM-3-RESUME-FINAL-01"
            or receipt.get("status") != "WAVE1_COMPLETED"
            or receipt.get("wave") != 1
            or receipt.get("message_id") != 585
            or receipt.get("expected_bytes") != 6199635
        ):
            raise ValueError("WAVE1_RECEIPT_CONTENT_INVALID")
        if receipt.get("recovered_once") is True:
            attempt_count = receipt.get("total_attempts")
            if (
                attempt_count not in (2, 3)
                or not (ROOT / "db/resume_final_01_recover585_once.started").is_file()
            ):
                raise ValueError("RECOVERY585_RECEIPT_MARKER_INVALID")
            third_marker = ROOT / "db/resume_final_01_recover585_third.started"
            if attempt_count == 3:
                if receipt.get("recovered_third") is not True or not third_marker.is_file():
                    raise ValueError("THIRD_ATTEMPT_RECEIPT_MARKER_INVALID")
            elif receipt.get("recovered_third") is not None or third_marker.exists():
                raise ValueError("UNEXPECTED_THIRD_ATTEMPT_MARKER")
            expected_first_attempts = attempt_count
        elif receipt.get("recovered_once") not in (None, False):
            raise ValueError("WAVE1_RECOVERY_FLAG_INVALID")
    if not DB.is_file() or not DESTINATION.is_dir():
        raise ValueError("PRODUCT_WORKSPACE_MISSING")
    db = sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("DB_INTEGRITY")
        module = db.execute(
            "SELECT title, parent_id, kind, is_active FROM catalog_nodes "
            "WHERE id=? AND channel_id=?", (MODULE, CHANNEL),
        ).fetchone()
        if (module is None or module["kind"] != "module"
                or not module["is_active"] or module["title"] != "Competências"):
            raise ValueError("MODULE_MISMATCH")
        course = db.execute(
            "SELECT title, kind, is_active FROM catalog_nodes "
            "WHERE id=? AND channel_id=?", (module["parent_id"], CHANNEL),
        ).fetchone()
        if (course is None or course["kind"] != "course"
                or not course["is_active"]
                or not course["title"].startswith("Candidato de Ouro ")):
            raise ValueError("COURSE_MISMATCH")
        rows = db.execute(
            "SELECT m.telegram_message_id, m.file_size_bytes, m.kind, "
            "m.remote_observation_state, d.state, d.attempts, d.sha256 "
            "FROM media_items m JOIN catalog_nodes n ON n.id=m.catalog_node_id "
            "LEFT JOIN downloads d ON d.media_item_id=m.id "
            "WHERE m.channel_id=? AND n.parent_id=? "
            "AND m.telegram_message_id IN (585,586,587) "
            "ORDER BY m.telegram_message_id", (CHANNEL, MODULE),
        ).fetchall()
        if (len(rows) != len(IDS)
                or tuple(r["telegram_message_id"] for r in rows) != IDS
                or tuple(r["file_size_bytes"] for r in rows) != SIZES
                or sum(SIZES) > MAX_TOTAL_BYTES
                or max(SIZES) > MAX_SINGLE_BYTES
                or any(r["kind"] != "DOCUMENT" or r["remote_observation_state"] != "OBSERVED"
                       for r in rows)):
            raise ValueError("EXACT_MEDIA_IDENTITY_OR_BUDGET_CHANGED")
        if phase == 1 and (RECEIPT.exists() or WAVE2_MARKER.exists()):
            raise ValueError("WAVE_ALREADY_STARTED")
        if phase == 2 and (
            not RECEIPT.is_file() or (WAVE2_MARKER.exists() is not post)
        ):
            raise ValueError("WAVE2_RECEIPT_OR_MARKER_INVALID")
        verified_states = ["DOWNLOADED"] * (3 if phase == 2 and post else 1 if
                                          phase == 2 or post else 0)
        for index, row in enumerate(rows):
            if index < len(verified_states):
                expected_attempts = expected_first_attempts if index == 0 else 1
                if (
                    row["state"] != "DOWNLOADED"
                    or row["attempts"] != expected_attempts
                    or not isinstance(row["sha256"], str) or len(row["sha256"]) != 64
                ):
                    raise ValueError("EXPECTED_COMPLETED_MEDIA_MISSING")
            elif row["state"] is not None:
                raise ValueError("UNEXPECTED_MEDIA_ATTEMPT_OR_COMPLETION")
    finally:
        db.close()
    planner = DownloadPlanner(DB, DESTINATION)
    plan = await planner.build(DownloadSelection(CHANNEL, "module", MODULE))
    selected = [item for item in plan.items if item.identity[1] in IDS]
    statuses = tuple(item.status for item in selected)
    required = (
        ("ALREADY_VALID", "ALREADY_VALID", "ALREADY_VALID")
        if phase == 2 and post else
        ("ALREADY_VALID", "PENDING", "PENDING")
        if phase == 2 or post else
        ("PENDING", "PENDING", "PENDING")
    )
    if len(selected) != 3 or statuses != required:
        raise ValueError("PILOT_PLAN_STATUS_CHANGED")
    print(f"PILOT_RESUME_FINAL_WAVE_{phase}_{'POST' if post else 'PREFLIGHT'}=PASS")
    print(f"AUTHORIZED_NEW_MP4=3 TOTAL_BYTES={sum(SIZES)}")
    print("SCOPED_IDS=585,586,587")
    print("ITEM_STATES=" + ",".join(statuses))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wave", type=int, choices=(1, 2), required=True)
    parser.add_argument("--post", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(check(args.wave, post=args.post))
        return 0
    except Exception as exc:
        print("PILOT_PRECHECK_BLOCKED=" + type(exc).__name__)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
