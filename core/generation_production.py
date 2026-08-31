from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .asset_registry import register_asset
from .generation_job import create_generation_job, run_generation_job
from .provider_scheduler import rank_providers
from .provider_catalog import load_catalog


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_production_schema(database_path: str | Path) -> None:
    with sqlite3.connect(database_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS provider_usage (id INTEGER PRIMARY KEY, provider TEXT NOT NULL, media_type TEXT NOT NULL, job_id INTEGER, estimated_cost REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL)""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_provider_usage_provider_type ON provider_usage(provider, media_type, created_at)")
        con.commit()


def run_queue_item(database_path: str | Path, queue_id: int) -> dict[str, Any]:
    ensure_production_schema(database_path)
    catalog = load_catalog()
    policy = catalog.get("policy", {})
    max_attempts = int(policy.get("max_attempts", 3) or 3)
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        con.execute("BEGIN IMMEDIATE")
        item = con.execute("SELECT * FROM generation_queue WHERE id=?", (queue_id,)).fetchone()
        if item is None:
            con.rollback(); raise ValueError(f"queue item {queue_id} not found")
        if item["status"] == "completed":
            con.rollback(); return {"queue_id": queue_id, "status": "completed", "message": "already completed"}
        if item["status"] == "processing":
            con.rollback(); return {"queue_id": queue_id, "status": "skipped", "message": "already processing"}
        if int(item["attempts"] or 0) >= max_attempts:
            con.execute("UPDATE generation_queue SET status='failed',last_error=?,updated_at=? WHERE id=?", ("maximum attempts exceeded", _now(), queue_id)); con.commit()
            return {"queue_id": queue_id, "status": "failed", "reason": "maximum attempts exceeded"}
        con.execute("UPDATE generation_queue SET status='processing',updated_at=? WHERE id=? AND status='queued'", (_now(), queue_id)); con.commit()
    providers = rank_providers(item["job_type"])
    if not providers:
        with sqlite3.connect(database_path) as con:
            con.execute("UPDATE generation_queue SET status='blocked',last_error=?,updated_at=? WHERE id=?", ("no eligible provider", _now(), queue_id)); con.commit()
        return {"queue_id": queue_id, "status": "blocked", "reason": "no eligible provider"}
    errors: list[dict[str, str]] = []
    for provider in providers:
        try:
            job = create_generation_job(database_path, item["document_id"], item["scene_id"], item["job_type"], provider["name"])
            result = run_generation_job(database_path, job["job_id"])
            if result["status"] not in {"completed", "submitted", "queued"}:
                raise RuntimeError(f"provider returned status {result['status']}")
            asset = None
            if result["status"] == "completed":
                asset = register_asset(database_path, result["job_id"], item["job_type"], result.get("provider_job_id"), result.get("asset_uri"), {"generation_status": result["status"]})
            with sqlite3.connect(database_path) as con:
                con.execute("UPDATE generation_queue SET status=?,attempts=attempts+1,last_error=NULL,updated_at=? WHERE id=?", ("completed" if result["status"] == "completed" else "queued", _now(), queue_id))
                con.execute("INSERT INTO provider_usage(provider,media_type,job_id,estimated_cost,created_at) VALUES(?,?,?,?,?)", (provider["name"], item["job_type"], result["job_id"], float(provider.get("estimated_cost_per_job", 0) or 0), _now())); con.commit()
            return {"queue_id": queue_id, "status": result["status"], "provider": provider["name"], "job": result, "asset": asset}
        except Exception as exc:
            errors.append({"provider": provider["name"], "error": str(exc)})
    with sqlite3.connect(database_path) as con:
        new_attempts = int(item["attempts"] or 0) + 1
        final_status = "failed" if new_attempts >= max_attempts else "queued"
        con.execute("UPDATE generation_queue SET status=?,attempts=?,last_error=?,updated_at=? WHERE id=?", (final_status, new_attempts, json.dumps(errors, ensure_ascii=False), _now(), queue_id)); con.commit()
    return {"queue_id": queue_id, "status": "failed" if new_attempts >= max_attempts else "retry", "errors": errors, "attempts": new_attempts}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one queued generation item with provider fallback")
    parser.add_argument("database"); parser.add_argument("queue_id", type=int)
    args = parser.parse_args(); print(json.dumps(run_queue_item(args.database, args.queue_id), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
