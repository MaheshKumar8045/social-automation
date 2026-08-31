from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def claim_queue_item(database_path: str | Path, queue_id: int) -> bool:
    """Atomically move a queued item to running; only one scheduler wins."""
    with sqlite3.connect(database_path, timeout=30) as con:
        con.execute("PRAGMA busy_timeout=30000")
        cur = con.execute(
            "UPDATE generation_queue SET status='running', attempts=attempts+1, updated_at=? WHERE id=? AND status='queued'",
            (now(), queue_id),
        )
        con.commit()
        return cur.rowcount == 1


def finish_queue_item(database_path: str | Path, queue_id: int, status: str, error: str | None = None) -> None:
    if status not in {"queued", "completed", "failed", "blocked"}:
        raise ValueError(status)
    with sqlite3.connect(database_path, timeout=30) as con:
        con.execute("PRAGMA busy_timeout=30000")
        con.execute("UPDATE generation_queue SET status=?, last_error=?, updated_at=? WHERE id=?", (status, error, now(), queue_id))
        con.commit()
