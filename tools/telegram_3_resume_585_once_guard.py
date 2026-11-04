"""Read-only authorization pre/post gate for exactly one extra attempt on MP4 585."""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
from pathlib import Path

from telegram_courses.downloads import _reject_reparse_path
from telegram_courses.s5_downloads import DownloadPlanner, DownloadSelection

CHANNEL = -1002758699600
MODULE = 44
MSG = 585
EXPECTED = 6199635
PARTIAL = 6029312
EXPECTED_ATTEMPTS = 1
ROOT = Path(os.environ["LOCALAPPDATA"]) / "telegram_courses_product"
DB = ROOT / "db/catalog.sqlite3"
DOWNLOADS = ROOT / "downloads"
RECEIPT = ROOT / "db/resume_final_01_stage1.json"
MARKER = ROOT / "db/resume_final_01_recover585_once.started"
NEXT = ROOT / "db/resume_final_01_wave2_started.json"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(262144):
            digest.update(chunk)
    return digest.hexdigest()


def check(*, post: bool = False) -> None:
    if RECEIPT.exists() or NEXT.exists():
        raise ValueError("PREVIOUS_STAGE_OR_WAVE2_ALREADY_STARTED")
    if MARKER.exists() != post:
        raise ValueError("RECOVERY_ONCE_MARKER_STATE")
    db = sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("DB_INTEGRITY_FAILED")
        scope = db.execute(
            "SELECT n.title AS module_title,c.title AS course_title,"
            "n.kind AS module_kind,c.kind AS course_kind "
            "FROM catalog_nodes n JOIN catalog_nodes c ON c.id=n.parent_id "
            "WHERE n.id=? AND n.channel_id=?",
            (MODULE, CHANNEL),
        ).fetchone()
        if (scope is None or scope["module_title"] != "Competências"
            or scope["module_kind"] != "module"
            or scope["course_kind"] != "course"
            or not str(scope["course_title"]).startswith("Candidato de Ouro ")):
            raise ValueError("COURSE_MODULE_SCOPE_INVALID")
        rows = db.execute(
            "SELECT m.id,m.telegram_message_id,m.file_size_bytes,"
            "m.kind,m.remote_observation_state,m.telegram_media_id,"
            "d.state,d.attempts,d.expected_bytes,d.downloaded_bytes,"
            "d.failure_category,d.sha256,d.owner_pid,d.final_path,d.partial_path,"
            "d.remote_identity_media_id,d.remote_identity_kind,"
            "d.remote_identity_size,d.remote_identity_provenance "
            "FROM media_items m JOIN catalog_nodes n ON m.catalog_node_id=n.id "
            "LEFT JOIN downloads d ON m.id=d.media_item_id "
            "WHERE m.channel_id=? AND n.parent_id=? "
            "AND m.telegram_message_id IN (585,586,587) "
            "ORDER BY m.telegram_message_id",
            (CHANNEL, MODULE),
        ).fetchall()
        if len(rows) != 3 or tuple(r["telegram_message_id"] for r in rows) != (585,586,587):
            raise ValueError("THREE_MESSAGE_SCOPE_MISMATCH")
        item = rows[0]
        if (item["file_size_bytes"] != EXPECTED or item["expected_bytes"] != EXPECTED
            or item["kind"] != "DOCUMENT" or item["remote_observation_state"] != "OBSERVED"
            or not item["telegram_media_id"]
            or item["remote_identity_media_id"] != item["telegram_media_id"]
            or item["remote_identity_kind"] != "DOCUMENT"
            or item["remote_identity_size"] != EXPECTED
            or item["remote_identity_provenance"] != "CAPTURED_AT_START"
            or item["owner_pid"] is not None):
            raise ValueError("MEDIA_IDENTITY_OR_OWNER_CHANGED")
        if any(r["state"] is not None or r["attempts"] is not None for r in rows[1:]):
            raise ValueError("OTHER_MEDIA_ALREADY_ATTEMPTED")
        final = Path(item["final_path"])
        partial = Path(item["partial_path"])
        if (not partial.is_relative_to(DOWNLOADS)
            or not final.is_relative_to(DOWNLOADS)
            or str(partial) != str(final) + ".part"):
            raise ValueError("DOWNLOAD_LOCATION_MISMATCH")
        _reject_reparse_path(DOWNLOADS.absolute(), final)
        _reject_reparse_path(DOWNLOADS.absolute(), partial)
        if post:
            if (item["state"] != "DOWNLOADED" or item["attempts"] != 2
                or item["downloaded_bytes"] != EXPECTED
                or item["failure_category"] is not None
                or partial.exists() or final.is_symlink() or not final.is_file()
                or final.stat().st_size != EXPECTED
                or not isinstance(item["sha256"], str)
                or len(item["sha256"]) != 64
                or file_hash(final) != item["sha256"]):
                raise ValueError("POST_RECOVERY_UNVERIFIED")
        else:
            if (item["state"] != "FAILED_RETRYABLE"
                or item["attempts"] != EXPECTED_ATTEMPTS
                or item["downloaded_bytes"] != PARTIAL
                or item["failure_category"] != "TRANSFER_BUDGET_EXHAUSTED"
                or not partial.is_file() or partial.is_symlink()
                or partial.stat().st_size != PARTIAL or final.exists()
                or item["sha256"] is not None):
                raise ValueError("RECOVERY_PRECONDITION_CHANGED")
    finally:
        db.close()
    import asyncio
    planner = DownloadPlanner(DB, DOWNLOADS)
    plan = asyncio.run(planner.build(DownloadSelection(CHANNEL, "module", MODULE)))
    selected = [r for r in plan.items if r.identity[1] in (585,586,587)]
    expected_status = (
        ("ALREADY_VALID", "PENDING", "PENDING")
        if post else
        ("CONDITIONAL_RESUME_CANDIDATE", "PENDING", "PENDING")
    )
    if len(selected) != 3 or tuple(r.status for r in selected) != expected_status:
        raise ValueError("PILOT_PLANNER_STATES_CHANGED")
    if not post and (
        selected[0].part_bytes != PARTIAL
        or selected[0].wire_offset != PARTIAL
        or selected[0].overlap_bytes != 0
    ):
        raise ValueError("PILOT_PREFIX_CHECKPOINT_CHANGED")
    print("RECOVERY585_POST=PASS" if post else "RECOVERY585_PREFLIGHT=PASS")
    print("MESSAGE_ID=585; PREFIX_BYTES=6029312; EXPECTED_BYTES=6199635")
    print("REMAINING_USEFUL_BYTES=170323; REQUEST_RESERVATION_CAP=6291456")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post", action="store_true")
    args = parser.parse_args()
    try:
        check(post=args.post)
        return 0
    except Exception as exc:
        print("RECOVERY585_BLOCKED=" + type(exc).__name__)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
