from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .generation_planner import build_generation_plan

ALLOWED = {"pending", "validated", "approved", "rejected", "review"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_registered_asset(database_path: str | Path, asset_id: int, status: str, *, reviewer: str = "system", reason: str | None = None) -> dict[str, Any]:
    if status not in ALLOWED - {"pending"}:
        raise ValueError(f"status must be one of: {', '.join(sorted(ALLOWED - {'pending'}))}")
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        asset = con.execute("SELECT * FROM generation_assets WHERE id=?", (asset_id,)).fetchone()
        if asset is None:
            raise ValueError(f"asset {asset_id} not found")
        job = con.execute("SELECT * FROM generation_jobs WHERE id=?", (asset["generation_job_id"],)).fetchone()
        if job is None:
            raise ValueError(f"generation job {asset['generation_job_id']} not found")
        plan = build_generation_plan(database_path, asset["document_id"], asset["scene_id"])
        if plan.get("plan_status") != "ready":
            raise ValueError("cannot validate asset without a ready generation plan")
        con.execute("""UPDATE generation_assets SET validation_status=?, validation_reviewer=?, validation_reason=?, validated_at=? WHERE id=?""", (status, reviewer, reason, _now(), asset_id))
        con.commit()
    return {"asset_id": asset_id, "generation_job_id": asset["generation_job_id"], "document_id": asset["document_id"], "scene_id": asset["scene_id"], "validation_status": status, "reviewer": reviewer, "reason": reason}


def main() -> None:
    parser = argparse.ArgumentParser(description="Set deterministic validation status for a registered generation asset")
    parser.add_argument("database")
    parser.add_argument("asset_id", type=int)
    parser.add_argument("status", choices=("validated", "approved", "rejected", "review"))
    parser.add_argument("--reviewer", default="system")
    parser.add_argument("--reason")
    args = parser.parse_args()
    print(json.dumps(validate_registered_asset(args.database, args.asset_id, args.status, reviewer=args.reviewer, reason=args.reason), indent=2))


if __name__ == "__main__":
    main()
