from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .generation_queue import enqueue, ensure_queue_schema
from .generation_production import run_queue_item


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_scenes(database_path: str | Path, document_id: int, job_type: str, start_scene: int | None = None, end_scene: int | None = None, interval_minutes: int = 0) -> list[dict[str, Any]]:
    ensure_queue_schema(database_path)
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        query = "SELECT DISTINCT scene_id FROM scene_context WHERE document_id=?"
        params: list[Any] = [document_id]
        if start_scene is not None:
            query += " AND scene_id>=?"; params.append(start_scene)
        if end_scene is not None:
            query += " AND scene_id<=?"; params.append(end_scene)
        query += " ORDER BY scene_id"
        scenes = con.execute(query, params).fetchall()
    base = _now()
    result = []
    for index, row in enumerate(scenes):
        scheduled = (base + timedelta(minutes=index * interval_minutes)).isoformat()
        result.append(enqueue(database_path, document_id, row["scene_id"], job_type, scheduled))
    return result


def run_due_batch(database_path: str | Path, limit: int = 10) -> list[dict[str, Any]]:
    ensure_queue_schema(database_path)
    now = _now().isoformat()
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT id FROM generation_queue WHERE status='queued' AND scheduled_at<=? ORDER BY scheduled_at,id LIMIT ?", (now, limit)).fetchall()
    return [run_queue_item(database_path, row["id"]) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch schedule and execute scene generation")
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("enqueue-scenes")
    e.add_argument("database"); e.add_argument("document_id", type=int); e.add_argument("--type", choices=("image", "video", "audio"), default="image"); e.add_argument("--start-scene", type=int); e.add_argument("--end-scene", type=int); e.add_argument("--interval-minutes", type=int, default=0)
    r = sub.add_parser("run-due")
    r.add_argument("database"); r.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.command == "enqueue-scenes":
        rows = enqueue_scenes(args.database, args.document_id, args.type, args.start_scene, args.end_scene, max(0, args.interval_minutes))
        print(json.dumps({"queued": len(rows), "items": rows}, indent=2))
    else:
        print(json.dumps({"processed": len(run_due_batch(args.database, args.limit)), "items": run_due_batch(args.database, args.limit)}, indent=2))


if __name__ == "__main__":
    main()
