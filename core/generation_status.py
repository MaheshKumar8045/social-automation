from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from .provider_scheduler import rank_providers


def report(database_path: str | Path, document_id: int, media_type: str = "image") -> dict[str, Any]:
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        def count(sql: str, params: tuple[Any, ...] = ()) -> int:
            return int(con.execute(sql, params).fetchone()[0])
        queue = {
            "queued": count("SELECT COUNT(*) FROM generation_queue WHERE document_id=? AND job_type=? AND status='queued'", (document_id, media_type)),
            "completed": count("SELECT COUNT(*) FROM generation_queue WHERE document_id=? AND job_type=? AND status='completed'", (document_id, media_type)),
            "failed": count("SELECT COUNT(*) FROM generation_queue WHERE document_id=? AND job_type=? AND status='failed'", (document_id, media_type)),
        }
        assets = {
            "total": count("SELECT COUNT(*) FROM generation_assets WHERE document_id=? AND asset_type=?", (document_id, media_type)),
            "pending": count("SELECT COUNT(*) FROM generation_assets WHERE document_id=? AND asset_type=? AND validation_status='pending'", (document_id, media_type)),
            "approved": count("SELECT COUNT(*) FROM generation_assets WHERE document_id=? AND asset_type=? AND validation_status='approved'", (document_id, media_type)),
            "rejected": count("SELECT COUNT(*) FROM generation_assets WHERE document_id=? AND asset_type=? AND validation_status='rejected'", (document_id, media_type)),
        }
        usage = count("SELECT COUNT(*) FROM provider_usage WHERE media_type=?", (media_type,)) if _table_exists(con, "provider_usage") else 0
    providers = rank_providers(media_type)
    return {"document_id": document_id, "media_type": media_type, "providers": [{"name": p.get("name"), "billing": p.get("billing"), "priority": p.get("priority"), "requires_api_key": p.get("requires_api_key", False)} for p in providers], "queue": queue, "assets": assets, "provider_usage_records": usage, "healthy": bool(providers)}


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def main() -> None:
    parser = argparse.ArgumentParser(description="Show generation queue, asset, and provider health")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("--type", choices=("image", "video", "audio"), default="image")
    args = parser.parse_args()
    print(json.dumps(report(args.database, args.document_id, args.type), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
