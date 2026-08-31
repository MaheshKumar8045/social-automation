from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .generation_planner import build_generation_plan
from .provider_adapter import get_provider


class GenerationProvider(Protocol):
    name: str
    def submit(self, job: dict[str, Any]) -> dict[str, Any]: ...
    def status(self, provider_job_id: str) -> dict[str, Any]: ...


class MockProvider:
    name = "mock"

    def submit(self, job: dict[str, Any]) -> dict[str, Any]:
        return {"provider": self.name, "provider_job_id": f"mock-{uuid.uuid4().hex}", "status": "completed", "asset_uri": None}

    def status(self, provider_job_id: str) -> dict[str, Any]:
        return {"provider": self.name, "provider_job_id": provider_job_id, "status": "completed", "asset_uri": None}


SCHEMA = """
CREATE TABLE IF NOT EXISTS generation_jobs (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL,
    scene_id INTEGER NOT NULL,
    job_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL DEFAULT '{}',
    provider_job_id TEXT,
    asset_uri TEXT,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(document_id, scene_id, job_type, provider)
);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_status ON generation_jobs(document_id, status);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_generation_job(database_path: str | Path, document_id: int, scene_id: int, job_type: str = "image", provider: str = "mock") -> dict[str, Any]:
    if job_type not in {"image", "video"}:
        raise ValueError("job_type must be image or video")
    if not provider or provider.strip() != provider:
        raise ValueError("provider must be a non-empty name without surrounding whitespace")
    plan = build_generation_plan(database_path, document_id, scene_id)
    if plan.get("plan_status") != "ready":
        raise ValueError(f"generation plan unavailable for scene {scene_id}")
    prompt_key = "image_prompt" if job_type == "image" else "video_prompt"
    request = {
        "document_id": document_id,
        "scene_id": scene_id,
        "job_type": job_type,
        "provider": provider,
        "plan": plan,
        "prompt_key": prompt_key,
        "source_grounded": True,
        "unknowns_must_remain_unknown": True,
    }
    now = _now()
    with sqlite3.connect(database_path) as con:
        con.executescript(SCHEMA)
        con.execute("""INSERT OR REPLACE INTO generation_jobs(document_id,scene_id,job_type,provider,status,request_json,response_json,attempts,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""", (document_id, scene_id, job_type, provider, "queued", json.dumps(request, ensure_ascii=False), "{}", 0, now, now))
        row = con.execute("SELECT id,status,attempts,created_at,updated_at FROM generation_jobs WHERE document_id=? AND scene_id=? AND job_type=? AND provider=?", (document_id, scene_id, job_type, provider)).fetchone()
        con.commit()
    return {"job_id": row[0], "document_id": document_id, "scene_id": scene_id, "job_type": job_type, "provider": provider, "status": row[1], "attempts": row[2], "created_at": row[3], "updated_at": row[4]}


def run_generation_job(database_path: str | Path, job_id: int, provider: GenerationProvider | None = None) -> dict[str, Any]:
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM generation_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise ValueError(f"generation job {job_id} not found")
        request = json.loads(row["request_json"])
        configured_provider = row["provider"]
        selected_provider = provider or get_provider(configured_provider)
        if selected_provider.name != configured_provider:
            raise ValueError(f"provider mismatch: job requests '{configured_provider}', adapter is '{selected_provider.name}'")
        con.execute("UPDATE generation_jobs SET status='running', attempts=attempts+1, updated_at=? WHERE id=?", (_now(), job_id))
        con.commit()
    try:
        response = selected_provider.submit(request)
        status = response.get("status", "submitted")
        with sqlite3.connect(database_path) as con:
            con.execute("UPDATE generation_jobs SET status=?,response_json=?,provider_job_id=?,asset_uri=?,error=NULL,updated_at=? WHERE id=?", (status, json.dumps(response, ensure_ascii=False), response.get("provider_job_id"), response.get("asset_uri"), _now(), job_id))
            con.commit()
        return {"job_id": job_id, "status": status, "provider": selected_provider.name, "provider_job_id": response.get("provider_job_id"), "asset_uri": response.get("asset_uri")}
    except Exception as exc:
        with sqlite3.connect(database_path) as con:
            con.execute("UPDATE generation_jobs SET status='failed',error=?,updated_at=? WHERE id=?", (str(exc), _now(), job_id))
            con.commit()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or run a provider-independent generation job")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("scene_id", type=int)
    parser.add_argument("--type", choices=("image", "video"), default="image")
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    job = create_generation_job(args.database, args.document_id, args.scene_id, args.type, args.provider)
    if args.run:
        print(json.dumps(run_generation_job(args.database, job["job_id"]), indent=2))
    else:
        print(json.dumps(job, indent=2))


if __name__ == "__main__":
    main()
