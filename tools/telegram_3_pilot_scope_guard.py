"""Fail-closed preflight offline para piloto autorizado; nenhuma RPC."""
import os
import sqlite3
from pathlib import Path

CHANNEL_ID = -1002758699600
MODULE_ID = 46
MAX_ITEMS = 5
MAX_SINGLE = 134217728
MAX_BYTES = 536870912
product = Path(os.environ["LOCALAPPDATA"]) / "telegram_courses_product"
dbpath = product / "db" / "catalog.sqlite3"
if not dbpath.is_file() or not (product / "downloads").is_dir():
    raise SystemExit("PILOT_PRECHECK_BLOCKED")
db = sqlite3.connect(dbpath.as_uri() + "?mode=ro", uri=True)
db.row_factory = sqlite3.Row
db.execute("PRAGMA query_only=ON")
try:
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("DB_INTEGRITY")
    module = db.execute("SELECT * FROM catalog_nodes WHERE id=? AND channel_id=?", (MODULE_ID, CHANNEL_ID)).fetchone()
    if module is None or module["kind"] != "module" or module["title"] != "Contagem Regressiva":
        raise ValueError("MODULE_MISMATCH")
    course = db.execute("SELECT * FROM catalog_nodes WHERE id=? AND channel_id=?", (module["parent_id"], CHANNEL_ID)).fetchone()
    if course is None or course["kind"] != "course" or not course["title"].startswith("Candidato de Ouro "):
        raise ValueError("COURSE_MISMATCH")
    lessons = db.execute("SELECT id FROM catalog_nodes WHERE parent_id=? AND kind='lesson' AND is_active=1 AND channel_id=?", (MODULE_ID, CHANNEL_ID)).fetchall()
    lesson_ids = [row["id"] for row in lessons]
    if not lesson_ids:
        raise ValueError("EMPTY_MODULE")
    place = ",".join("?" for _ in lesson_ids)
    media = db.execute("SELECT file_size_bytes, kind FROM media_items WHERE catalog_node_id IN (" + place + ") AND channel_id=?", (*lesson_ids, CHANNEL_ID)).fetchall()
    sizes = [row["file_size_bytes"] for row in media]
    if (len(sizes) != MAX_ITEMS or not all(type(x) is int and 0 < x <= MAX_SINGLE for x in sizes)
            or sum(sizes) > MAX_BYTES):
        raise ValueError("SCOPE_OR_SIZE_LIMIT")
    print("PILOT_SCOPE_OFFLINE=PASS")
    print("AUTHORIZED_MODULE_ID=" + str(MODULE_ID))
    print("MEDIA_ITEMS=" + str(len(sizes)))
    print("EXPECTED_BYTES_TOTAL=" + str(sum(sizes)))
    print("MAX_SINGLE_BYTES=" + str(max(sizes)))
except (sqlite3.Error, ValueError):
    raise SystemExit("PILOT_PRECHECK_BLOCKED") from None
finally:
    db.close()
