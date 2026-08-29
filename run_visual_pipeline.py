from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

STEPS = [
    ("Visual Knowledge Bible", "core.visual_knowledge_bible"),
    ("Canonical Visual Bible", "core.canonical_visual_bible"),
    ("Visual Fact Reconciliation", "core.visual_fact_reconciler"),
    ("Visual Conflict Classification", "core.visual_conflict_classifier"),
]


def run_module(module: str, db: str, document_id: int) -> None:
    print(f"\n=== RUNNING: {module} ===")
    result = subprocess.run(
        [sys.executable, "-m", module, db, str(document_id)],
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def validate(db: str, document_id: int) -> None:
    with sqlite3.connect(db) as con:
        checks = {}
        checks["canonical_profiles"] = con.execute(
            "SELECT COUNT(*) FROM canonical_visual_profiles WHERE document_id=?", (document_id,)
        ).fetchone()[0]
        checks["canonical_facts"] = con.execute(
            "SELECT COUNT(*) FROM canonical_visual_facts WHERE document_id=?", (document_id,)
        ).fetchone()[0]
        checks["strong_conflicts"] = con.execute(
            "SELECT COUNT(*) FROM visual_conflict_classification WHERE document_id=? AND classification='strong_conflict'",
            (document_id,),
        ).fetchone()[0]
        checks["unsupported"] = con.execute(
            "SELECT COUNT(*) FROM visual_fact_reconciliation WHERE document_id=? AND status='unsupported'",
            (document_id,),
        ).fetchone()[0]
        checks["known_bad_phrase_facts"] = con.execute(
            """SELECT COUNT(*) FROM visual_facts
               WHERE profile_id IN (SELECT id FROM visual_profiles WHERE document_id=? AND profile_type='character')
                 AND (LOWER(evidence) LIKE '%small tongue of platinum%'
                      OR LOWER(evidence) LIKE '%large scale map%'
                      OR LOWER(evidence) LIKE '%serious difficulty%'
                      OR LOWER(value) LIKE '%200 feet%')""",
            (document_id,),
        ).fetchone()[0]

    print("\n=== VISUAL PIPELINE VALIDATION ===")
    for key, value in checks.items():
        print(f"{key}: {value}")

    if checks["canonical_profiles"] != 35:
        raise SystemExit("FAIL: canonical visual profile count is not 35 for the current sample document")
    if checks["canonical_facts"] == 0:
        raise SystemExit("FAIL: canonical visual fact layer is empty")
    if checks["known_bad_phrase_facts"] != 0:
        raise SystemExit("FAIL: known false-positive visual evidence remains")
    if checks["strong_conflicts"] != 0:
        raise SystemExit("FAIL: strong visual conflicts detected")
    if checks["unsupported"] != 0:
        raise SystemExit("FAIL: unsupported reconciled facts detected")

    print("RESULT: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete visual knowledge pipeline and regression checks")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    args = parser.parse_args()

    if not Path(args.database).exists():
        raise SystemExit(f"Database not found: {args.database}")

    for label, module in STEPS:
        run_module(module, args.database, args.document_id)

    validate(args.database, args.document_id)


if __name__ == "__main__":
    main()
