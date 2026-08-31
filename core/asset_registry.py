from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS generation_assets (
    id INTEGER PRIMARY KEY,
    generation_job_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    scene_id INTEGER NOT NULL,
    asset_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_asset_id TEXT,
    asset_uri TEXT,
    validation_status TEXT NOT NULL DEFAULT 'pending',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_generation_assets_scene ON generation_assets(document_id, scene_id);
CREATE INDEX IF NOT EXISTS idx_generation_assets_validation ON generation_assets(validation_status);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def register_asset(database_path: str | Path, job_id: int, asset_type: str, provider_asset_id: str | None = None, asset_uri: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    if asset_type not in {"image", "video", "audio"}:
        raise ValueError("asset_type must be image, video, or audio")
    with sqlite3.connect(database_path) as con:
        con.executescript(SCHEMA)
        con.row_factory = sqlite3.Row
        job = con.execute("SELECT id,document_id,scene_id,provider FROM generation_jobs WHERE id=?", (job_id,)).fetchone()
        if job is None:
            raise ValueError(f"generation job {job_id} not found")
        existing = con.execute("SELECT id FROM generation_assets WHERE generation_job_id=?", (job_id,)).fetchone()
        if existing is not None:
            return {"asset_id": existing[0], "generation_job_id": job[0], "document_id": job[1], "scene_id": job[2], "asset_type": asset_type, "provider": job[3], "validation_status": con.execute("SELECT validation_status FROM generation_assets WHERE id=?", (existing[0],)).fetchone()[0]}
        now = _now()
        cur = con.execute("""INSERT INTO generation_assets(generation_job_id,document_id,scene_id,asset_type,provider,provider_asset_id,asset_uri,metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""", (job[0], job[1], job[2], asset_type, job[3], provider_asset_id, asset_uri, json.dumps(metadata or {}, ensure_ascii=False), now, now))
        con.commit()
        return {"asset_id": cur.lastrowid, "generation_job_id": job[0], "document_id": job[1], "scene_id": job[2], "asset_type": asset_type, "provider": job[3], "validation_status": "pending"}


def set_validation_status(database_path: str | Path, asset_id: int, status: str, metadata_patch: dict[str, Any] | None = None) -> dict[str, Any]:
    allowed = {"pending", "approved", "rejected", "review"}
    if status not in allowed:
        raise ValueError(f"validation status must be one of {sorted(allowed)}")
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT metadata_json FROM generation_assets WHERE id=?", (asset_id,)).fetchone()
        if row is None:
            raise ValueError(f"asset {asset_id} not found")
        metadata = json.loads(row[0] or "{}")
        metadata.update(metadata_patch or {})
        con.execute("UPDATE generation_assets SET validation_status=?,metadata_json=?,updated_at=? WHERE id=?", (status, json.dumps(metadata, ensure_ascii=False), _now(), asset_id))
        con.commit()
    return {"asset_id": asset_id, "validation_status": status, "metadata": metadata}


def main() -> None:
    parser = argparse.ArgumentParser(description="Register and validate generated assets")
    parser.add_argument("database")
    parser.add_argument("job_id", type=int)
    parser.add_argument("--type", choices=("image", "video", "audio"), required=True)
    parser.add_argument("--provider-asset-id")
    parser.add_argument("--asset-uri")
    args = parser.parse_args()
    print(json.dumps(register_asset(args.database, args.job_id, args.type, args.provider_asset_id, args.asset_uri), indent=2))


if __name__ == "__main__":
    main()
