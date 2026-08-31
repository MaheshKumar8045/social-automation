from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID = {"pending", "validated", "approved", "rejected"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def inspect_assets(database_path: str | Path, document_id: int, status: str | None = None) -> dict[str, Any]:
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        params: list[Any] = [document_id]
        where = "WHERE document_id=?"
        if status:
            where += " AND validation_status=?"; params.append(status)
        rows = con.execute(f"SELECT id,scene_id,asset_type,provider,validation_status,generation_job_id FROM generation_assets {where} ORDER BY scene_id,id", params).fetchall()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["validation_status"]] = counts.get(row["validation_status"], 0) + 1
    return {"document_id": document_id, "count": len(rows), "by_status": counts, "assets": [dict(r) for r in rows]}


def promote(database_path: str | Path, asset_id: int, target: str, reviewer: str = "system", reason: str | None = None) -> dict[str, Any]:
    if target not in VALID:
        raise ValueError(f"invalid status: {target}")
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM generation_assets WHERE id=?", (asset_id,)).fetchone()
        if row is None:
            raise ValueError(f"asset {asset_id} not found")
        if target == "approved" and not row["validation_status"] in {"validated", "approved"}:
            raise ValueError("asset must be validated before approval")
        con.execute("UPDATE generation_assets SET validation_status=?,validation_reviewer=?,validation_reason=?,validated_at=? WHERE id=?", (target, reviewer, reason, _now(), asset_id))
        con.commit()
        updated = con.execute("SELECT * FROM generation_assets WHERE id=?", (asset_id,)).fetchone()
    return {"asset_id": asset_id, "validation_status": updated["validation_status"], "reviewer": updated["validation_reviewer"], "reason": updated["validation_reason"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect and safely promote generated assets")
    sub = parser.add_subparsers(dest="command", required=True)
    i = sub.add_parser("inspect"); i.add_argument("database"); i.add_argument("document_id", type=int); i.add_argument("--status")
    p = sub.add_parser("promote"); p.add_argument("database"); p.add_argument("asset_id", type=int); p.add_argument("status", choices=sorted(VALID)); p.add_argument("--reviewer", default="system"); p.add_argument("--reason")
    args = parser.parse_args()
    if args.command == "inspect":
        print(json.dumps(inspect_assets(args.database, args.document_id, args.status), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(promote(args.database, args.asset_id, args.status, args.reviewer, args.reason), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
