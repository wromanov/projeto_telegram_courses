"""Bounded read-only probe. DO NOT run --execute without renewed user authorization."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
from pathlib import Path

from telegram_courses.auth import AuthState
from telegram_courses.config import load_telegram_credentials
from telegram_courses.telethon_gateway import TelethonGateway
from telegram_courses.terminal_hash_candidate import (
    BLOCK_BYTES,
    compare_terminal_hash_hypotheses,
)

CHANNEL = -1002758699600
MODULE = 46
ROOT = Path(os.environ["LOCALAPPDATA"]) / "telegram_courses_product"
DB = ROOT / "db" / "catalog.sqlite3"
REPORT = Path(__file__).parents[1] / "docs/reports/TELEGRAM_3_BATCH_RESUME_PILOT_01/EOF_DIGEST_COMPARE.json"


def select_items():
    db = sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    try:
        module = db.execute(
            "SELECT title,parent_id,kind FROM catalog_nodes WHERE id=? AND channel_id=?",
            (MODULE, CHANNEL),
        ).fetchone()
        if module is None or module["kind"] != "module" or module["title"] != "Contagem Regressiva":
            raise RuntimeError("MODULE_SCOPE_MISMATCH")
        course = db.execute(
            "SELECT title,kind FROM catalog_nodes WHERE id=? AND channel_id=?",
            (module["parent_id"], CHANNEL),
        ).fetchone()
        if course is None or course["kind"] != "course" or not course["title"].startswith("Candidato de Ouro "):
            raise RuntimeError("COURSE_SCOPE_MISMATCH")
        rows = db.execute(
            "SELECT m.telegram_message_id,m.media_ordinal,m.telegram_media_id,"
            "m.file_size_bytes,d.state,d.partial_path "
            "FROM media_items m JOIN catalog_nodes n ON n.id=m.catalog_node_id "
            "JOIN downloads d ON d.media_item_id=m.id "
            "WHERE m.channel_id=? AND n.parent_id=? AND n.kind='lesson' "
            "ORDER BY m.telegram_message_id,m.media_ordinal",
            (CHANNEL, MODULE),
        ).fetchall()
        if len(rows) != 5:
            raise RuntimeError("EXPECTED_FIVE_FILES")
        out = []
        for row in rows:
            size = row["file_size_bytes"]
            partial = Path(row["partial_path"]) if row["partial_path"] else None
            if (row["state"] != "FAILED_RETRYABLE" or not isinstance(size,int)
                    or not 0 < size <= 134217728 or partial is None
                    or not partial.is_relative_to(ROOT) or partial.is_symlink()
                    or not partial.is_file() or partial.stat().st_size != size
                    or row["media_ordinal"] != 0 or not row["telegram_media_id"]):
                raise RuntimeError("PARTIAL_OR_IDENTITY_INVALID")
            out.append((int(row["telegram_message_id"]),str(row["telegram_media_id"]),size,partial))
        if sum(row[2] for row in out) != 73071671:
            raise RuntimeError("AGGREGATE_MEDIA_SIZE_MISMATCH")
        return tuple(out)
    finally:
        db.close()


async def probe(items):
    client = TelethonGateway(
        load_telegram_credentials(),
        bounded_metadata_channel_id=CHANNEL,
        receive_updates=False,
        catch_up=False,
        request_retries=0,
        connection_retries=0,
    )
    results=[]
    attempted=0
    try:
        if await asyncio.wait_for(client.restore(), timeout=30) is not AuthState.AUTHENTICATED:
            return {"session":"NOT_AUTHENTICATED","attempted":0,"results":[]}
        for idx,(message_id,media_id,size,partial) in enumerate(items, 1):
            if attempted >= 5:
                break
            terminal_offset=((size-1)//BLOCK_BYTES)*BLOCK_BYTES
            attempted+=1
            status="NO_TERMINAL_HASH"
            remote_range_count=0
            try:
                response=await asyncio.wait_for(
                    client.get_file_hashes(
                        CHANNEL,message_id,0,telegram_media_id=media_id,
                        expected_bytes=size,offset=terminal_offset
                    ),timeout=30
                )
                remote_range_count=len(response)
                matches=[h for h in response if h.offset == terminal_offset
                         and h.limit == BLOCK_BYTES and h.offset + h.limit > size]
                if len(matches) == 1:
                    status=compare_terminal_hash_hypotheses(
                        partial,expected_bytes=size,offset=matches[0].offset,
                        limit=matches[0].limit,remote_sha256=matches[0].sha256
                    )
                elif len(matches)>1:
                    status="DUPLICATE_TERMINAL_HASH"
            except Exception as exc:
                label=type(exc).__name__
                status="METADATA_CALL_FAILED_"+(label if label.isidentifier() and label.isascii() else "OTHER")
            results.append({
                "item_index":idx,"size_bytes":size,"terminal_offset":terminal_offset,
                "server_ranges":remote_range_count,"comparison":status,
            })
        return {"session":"AUTHENTICATED","attempted":attempted,
                "maximum_authorized_calls":5,"payload_bytes":0,"db_updates":0,
                "results":results}
    finally:
        await client.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--execute-metadata", action="store_true")
    args=parser.parse_args()
    try:
        items=select_items()
        if not args.execute_metadata:
            print("OFFLINE_PRECHECK=PASS; FIVE_PARTIALS_PRESERVED=YES; REMOTE_CALLS=0")
            return 0
        result=asyncio.run(probe(items))
        REPORT.write_text(json.dumps(result,ensure_ascii=True,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,ensure_ascii=True))
        return 0 if result["attempted"] == 5 else 3
    except Exception as exc:
        label=type(exc).__name__
        print("DIAGNOSTIC_BLOCKED="+(label if label.isidentifier() and label.isascii() else "OTHER"))
        return 4


if __name__=="__main__":
    raise SystemExit(main())
