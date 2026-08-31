from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def recover_stale(database_path: str | Path, stale_minutes: int = 120) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=max(1, stale_minutes))).isoformat()
    with sqlite3.connect(database_path, timeout=30) as con:
        con.execute("PRAGMA busy_timeout=30000")
        cur = con.execute(
            "UPDATE generation_queue SET status='queued', last_error='recovered stale running job', updated_at=? WHERE status='running' AND updated_at<?",
            (datetime.now(timezone.utc).isoformat(), cutoff),
        )
        con.commit()
        return cur.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover stale generation queue items")
    parser.add_argument("database")
    parser.add_argument("--stale-minutes", type=int, default=120)
    args = parser.parse_args()
    print({"recovered": recover_stale(args.database, args.stale_minutes)})


if __name__ == "__main__":
    main()
