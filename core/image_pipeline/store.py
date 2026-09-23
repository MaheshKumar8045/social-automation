from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import JobStatus, SceneJob


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GenerationStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path, timeout=30)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA foreign_keys=ON")
        self.con.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                scene_id INTEGER PRIMARY KEY,
                scene_order INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt INTEGER NOT NULL DEFAULT 0,
                prompt_hash TEXT NOT NULL,
                prompt_path TEXT,
                final_path TEXT,
                validation_path TEXT,
                started_at TEXT,
                completed_at TEXT,
                last_error TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scene_id INTEGER NOT NULL,
                attempt_number INTEGER NOT NULL,
                prompt_path TEXT,
                image_path TEXT,
                validation_path TEXT,
                status TEXT NOT NULL,
                failure_reason TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(scene_id) REFERENCES jobs(scene_id)
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_order ON jobs(scene_order);
            CREATE INDEX IF NOT EXISTS idx_attempts_scene ON attempts(scene_id, attempt_number);
            """
        )
        self.con.commit()

    def close(self) -> None:
        self.con.close()

    def ensure_jobs(self, jobs: list[SceneJob], prompt_hashes: dict[int, str]) -> None:
        for job in jobs:
            existing = self.con.execute(
                "SELECT scene_id, prompt_hash FROM jobs WHERE scene_id=?", (job.scene_id,)
            ).fetchone()
            if existing is None:
                self.con.execute(
                    """INSERT INTO jobs
                    (scene_id, scene_order, title, status, attempt, prompt_hash, updated_at)
                    VALUES (?, ?, ?, ?, 0, ?, ?)""",
                    (job.scene_id, job.scene_order, job.title, JobStatus.PENDING,
                     prompt_hashes[job.scene_id], _now()),
                )
            elif existing["prompt_hash"] != prompt_hashes[job.scene_id]:
                self.con.execute(
                    """UPDATE jobs SET scene_order=?, title=?, status=?, attempt=0,
                       prompt_hash=?, prompt_path=NULL, final_path=NULL,
                       validation_path=NULL, started_at=NULL, completed_at=NULL,
                       last_error='prompt changed', updated_at=? WHERE scene_id=?""",
                    (job.scene_order, job.title, JobStatus.PENDING,
                     prompt_hashes[job.scene_id], _now(), job.scene_id),
                )
        self.con.commit()

    def get(self, scene_id: int) -> sqlite3.Row | None:
        return self.con.execute("SELECT * FROM jobs WHERE scene_id=?", (scene_id,)).fetchone()

    def set_status(self, scene_id: int, status: JobStatus, **fields: Any) -> None:
        allowed = {
            "attempt", "prompt_path", "final_path", "validation_path",
            "started_at", "completed_at", "last_error"
        }
        fields = {k: v for k, v in fields.items() if k in allowed}
        fields["status"] = str(status)
        fields["updated_at"] = _now()
        assignments = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [scene_id]
        self.con.execute(f"UPDATE jobs SET {assignments} WHERE scene_id=?", values)
        self.con.commit()

    def begin_attempt(self, scene_id: int, attempt: int, prompt_path: Path) -> None:
        self.con.execute(
            """INSERT INTO attempts(scene_id, attempt_number, prompt_path, status, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (scene_id, attempt, str(prompt_path), "started", _now()),
        )
        self.con.commit()

    def finish_attempt(self, scene_id: int, attempt: int, *, status: str,
                       image_path: Path | None = None,
                       validation_path: Path | None = None,
                       failure_reason: str | None = None) -> None:
        self.con.execute(
            """UPDATE attempts SET status=?, image_path=?, validation_path=?, failure_reason=?
               WHERE scene_id=? AND attempt_number=?""",
            (status, str(image_path) if image_path else None,
             str(validation_path) if validation_path else None,
             failure_reason, scene_id, attempt),
        )
        self.con.commit()

    def pending_or_retry(self, limit: int | None = None,
                         start_order: int | None = None) -> list[int]:
        clauses = ["status IN (?, ?)"]
        args: list[Any] = [JobStatus.PENDING, JobStatus.RETRY]
        if start_order is not None:
            clauses.append("scene_order >= ?")
            args.append(start_order)
        sql = "SELECT scene_id FROM jobs WHERE " + " AND ".join(clauses)
        sql += " ORDER BY scene_order, scene_id"
        if limit:
            sql += " LIMIT ?"
            args.append(limit)
        return [int(row["scene_id"]) for row in self.con.execute(sql, args).fetchall()]

    def summary(self) -> dict[str, int]:
        rows = self.con.execute(
            "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"
        ).fetchall()
        return {str(row["status"]): int(row["n"]) for row in rows}
