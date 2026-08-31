from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .generation_queue import enqueue, ensure_queue_schema


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def autofill(database_path: str | Path, document_id: int, job_type: str = "image", limit: int = 25) -> list[dict[str, Any]]:
    """Queue scenes with canonical visual context that have no queued/completed job."""
    ensure_queue_schema(database_path)
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """SELECT DISTINCT svc.scene_id
               FROM scene_visual_context svc
               WHERE svc.document_id=?
                 AND NOT EXISTS (
                   SELECT 1 FROM generation_queue q
                   WHERE q.document_id=svc.document_id AND q.scene_id=svc.scene_id AND q.job_type=?
                     AND q.status IN ('queued','completed')
                 )
               ORDER BY svc.scene_id LIMIT ?""",
            (document_id, job_type, max(1, limit)),
        ).fetchall()
    return [enqueue(database_path, document_id, row["scene_id"], job_type, _now()) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Automatically queue eligible scenes for generation")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("--type", choices=("image", "video", "audio"), default="image")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    rows = autofill(args.database, args.document_id, args.type, args.limit)
    print(json.dumps({"queued": len(rows), "items": rows}, indent=2))


if __name__ == "__main__":
    main()
