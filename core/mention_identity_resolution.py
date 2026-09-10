from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS mention_identity_resolution (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES character_identity_groups(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(document_id, group_id)
);
CREATE INDEX IF NOT EXISTS idx_mention_identity_resolution_doc
ON mention_identity_resolution(document_id, relationship);
"""


def build(db: str | Path, document_id: int) -> dict[str, int]:
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(SCHEMA)
        con.execute("DELETE FROM mention_identity_resolution WHERE document_id=?", (document_id,))

        groups = con.execute(
            """SELECT id, confidence
               FROM character_identity_groups
               WHERE document_id=? ORDER BY id""",
            (document_id,),
        ).fetchall()

        counts = {"confirmed_alias": 0, "likely_alias": 0, "unresolved": 0}
        for group in groups:
            gid = int(group["id"])
            evidence = con.execute(
                """SELECT relationship, confidence, evidence_json
                   FROM character_identity_evidence
                   WHERE document_id=? AND group_id=?
                   ORDER BY confidence DESC, id DESC LIMIT 1""",
                (document_id, gid),
            ).fetchone()

            if evidence is None:
                relationship = "unresolved"
                confidence = 0.0
                evidence_json = ["No identity evidence classification available."]
            else:
                classified = str(evidence["relationship"] or "unresolved")
                if classified == "identity_alias":
                    relationship = "confirmed_alias"
                    confidence = float(evidence["confidence"] or 0.0)
                else:
                    relationship = "unresolved"
                    confidence = float(evidence["confidence"] or 0.0)
                try:
                    evidence_json = json.loads(evidence["evidence_json"] or "[]")
                except json.JSONDecodeError:
                    evidence_json = [str(evidence["evidence_json"] or "")]

            con.execute(
                """INSERT INTO mention_identity_resolution
                   (document_id,group_id,relationship,confidence,evidence_json)
                   VALUES(?,?,?,?,?)""",
                (document_id, gid, relationship, confidence, json.dumps(evidence_json, ensure_ascii=False)),
            )
            counts[relationship] += 1

        con.commit()
        return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize conservative identity evidence into resolution records")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    args = parser.parse_args()
    result = build(args.database, args.document_id)
    print("=== MENTION IDENTITY RESOLUTION ===")
    for key in ("confirmed_alias", "likely_alias", "unresolved"):
        print(f"{key}: {result[key]}")


if __name__ == "__main__":
    main()
