from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .generation_job import create_generation_job, run_generation_job
from .provider_scheduler import choose_provider


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_queue_schema(database_path: str | Path) -> None:
    with sqlite3.connect(database_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS generation_queue (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL, scene_id INTEGER NOT NULL, job_type TEXT NOT NULL, scheduled_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_generation_queue_due ON generation_queue(status, scheduled_at)")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_generation_queue_scene_type ON generation_queue(document_id, scene_id, job_type)")
        con.commit()


def enqueue(database_path: str | Path, document_id: int, scene_id: int, job_type: str, scheduled_at: str | None = None) -> dict[str, Any]:
    ensure_queue_schema(database_path)
    when = scheduled_at or _now()
    with sqlite3.connect(database_path) as con:
        existing = con.execute("SELECT id,document_id,scene_id,job_type,scheduled_at,status FROM generation_queue WHERE document_id=? AND scene_id=? AND job_type=?", (document_id, scene_id, job_type)).fetchone()
        if existing:
            return {"queue_id": existing[0], "document_id": existing[1], "scene_id": existing[2], "job_type": existing[3], "scheduled_at": existing[4], "status": existing[5], "deduplicated": True}
        cur = con.execute("INSERT INTO generation_queue(document_id,scene_id,job_type,scheduled_at,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (document_id, scene_id, job_type, when, "queued", _now(), _now()))
        con.commit()
        return {"queue_id": cur.lastrowid, "document_id": document_id, "scene_id": scene_id, "job_type": job_type, "scheduled_at": when, "status": "queued", "deduplicated": False}


def _claim_due(database_path: str | Path, limit: int) -> list[sqlite3.Row]:
    now = _now()
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        con.execute("BEGIN IMMEDIATE")
        rows = con.execute("SELECT * FROM generation_queue WHERE status='queued' AND scheduled_at<=? ORDER BY scheduled_at,id LIMIT ?", (now, limit)).fetchall()
        for row in rows:
            con.execute("UPDATE generation_queue SET status='processing',updated_at=? WHERE id=? AND status='queued'", (_now(), row["id"]))
        con.commit()
    return rows


def run_due(database_path: str | Path, limit: int = 1) -> list[dict[str, Any]]:
    ensure_queue_schema(database_path)
    results: list[dict[str, Any]] = []
    rows = _claim_due(database_path, max(1, limit))
    for row in rows:
        provider = choose_provider(row["job_type"])
        if provider is None:
            with sqlite3.connect(database_path) as con:
                con.execute("UPDATE generation_queue SET status='blocked',last_error=?,updated_at=? WHERE id=?", ("no eligible provider", _now(), row["id"]))
                con.commit()
            results.append({"queue_id": row["id"], "status": "blocked", "reason": "no eligible provider"})
            continue
        try:
            job = create_generation_job(database_path, row["document_id"], row["scene_id"], row["job_type"], provider["name"])
            result = run_generation_job(database_path, job["job_id"])
            with sqlite3.connect(database_path) as con:
                con.execute("UPDATE generation_queue SET status='completed',attempts=attempts+1,last_error=NULL,updated_at=? WHERE id=?", (_now(), row["id"]))
                con.commit()
            results.append({"queue_id": row["id"], "status": "completed", "provider": provider["name"], "job": result})
        except Exception as exc:
            with sqlite3.connect(database_path) as con:
                con.execute("UPDATE generation_queue SET status='queued',attempts=attempts+1,last_error=?,updated_at=? WHERE id=?", (str(exc), _now(), row["id"]))
                con.commit()
            results.append({"queue_id": row["id"], "status": "failed", "error": str(exc)})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue and execute scheduled generation jobs")
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("enqueue")
    e.add_argument("database"); e.add_argument("document_id", type=int); e.add_argument("scene_id", type=int); e.add_argument("--type", choices=("image", "video", "audio"), default="image"); e.add_argument("--at")
    r = sub.add_parser("run-due")
    r.add_argument("database"); r.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    if args.command == "enqueue":
        print(json.dumps(enqueue(args.database, args.document_id, args.scene_id, args.type, args.at), indent=2))
    else:
        print(json.dumps(run_due(args.database, args.limit), indent=2))


if __name__ == "__main__":
    main()
