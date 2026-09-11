from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS canonical_characters (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    identity_group_id INTEGER NOT NULL REFERENCES character_identity_groups(id) ON DELETE CASCADE,
    canonical_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    UNIQUE(document_id, identity_group_id)
);
CREATE TABLE IF NOT EXISTS canonical_character_aliases (
    id INTEGER PRIMARY KEY,
    canonical_character_id INTEGER NOT NULL REFERENCES canonical_characters(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    relationship TEXT NOT NULL,
    confidence REAL NOT NULL,
    UNIQUE(canonical_character_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_canonical_characters_doc ON canonical_characters(document_id, status);
"""


def build(db: str | Path, doc: int) -> dict[str, int]:
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(SCHEMA)
        con.execute(
            "DELETE FROM canonical_character_aliases WHERE canonical_character_id IN (SELECT id FROM canonical_characters WHERE document_id=?)",
            (doc,),
        )
        con.execute("DELETE FROM canonical_characters WHERE document_id=?", (doc,))
        groups = con.execute(
            """SELECT g.id,g.canonical_entity_id,g.canonical_name,g.confidence,
                      COALESCE(r.relationship,'unresolved') relationship,
                      COALESCE(r.confidence,0) rconf
               FROM character_identity_groups g
               LEFT JOIN mention_identity_resolution r
                 ON r.group_id=g.id AND r.document_id=g.document_id
               WHERE g.document_id=? ORDER BY g.id""",
            (doc,),
        ).fetchall()
        counts = {"confirmed": 0, "likely": 0, "singleton": 0, "excluded": 0}
        for g in groups:
            members = con.execute(
                """SELECT m.entity_id,m.variant_name,m.confidence,
                          COALESCE(cg.decision,'unknown') decision,
                          COALESCE(cg.score,0) gate_score
                   FROM character_identity_members m
                   LEFT JOIN character_candidate_gate cg
                     ON cg.document_id=m.document_id AND cg.entity_id=m.entity_id
                   WHERE m.document_id=? AND m.group_id=?
                   ORDER BY m.id""",
                (doc, g["id"]),
            ).fetchall()
            validated_members = [m for m in members if m["decision"] == "validated"]
            eligible_members = [m for m in members if m["decision"] in {"validated", "probable"}]
            if g["relationship"] == "confirmed_alias" and eligible_members:
                status = "confirmed"
                counts["confirmed"] += 1
                canonical_name = g["canonical_name"]
            elif g["relationship"] == "likely_alias" and eligible_members:
                status = "likely"
                counts["likely"] += 1
                canonical_name = g["canonical_name"]
            elif validated_members:
                status = "confirmed"
                counts["confirmed"] += 1
                canonical_name = validated_members[0]["variant_name"]
            elif len(members) == 1 and members[0]["decision"] in {"validated", "probable"}:
                status = "singleton"
                counts["singleton"] += 1
                canonical_name = g["canonical_name"]
            else:
                counts["excluded"] += 1
                continue

            conf = min(
                float(g["confidence"]),
                max(float(g["rconf"]), 0.5) if g["relationship"] != "unresolved" else float(g["confidence"]),
            )
            if validated_members:
                conf = max(conf, float(validated_members[0]["gate_score"]))
            cur = con.execute(
                "INSERT INTO canonical_characters(document_id,identity_group_id,canonical_name,confidence,status) VALUES(?,?,?,?,?)",
                (doc, g["id"], canonical_name, conf, status),
            )
            cid = cur.lastrowid
            canonical_entity_id = validated_members[0]["entity_id"] if validated_members else g["canonical_entity_id"]
            for m in members:
                rel = "canonical" if m["entity_id"] == canonical_entity_id else (
                    "alias" if status in {"confirmed", "likely"} else "variant"
                )
                con.execute(
                    "INSERT INTO canonical_character_aliases(canonical_character_id,entity_id,alias,relationship,confidence) VALUES(?,?,?,?,?)",
                    (cid, m["entity_id"], m["variant_name"], rel, m["confidence"]),
                )
        con.commit()
        return counts


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("db")
    p.add_argument("document_id", type=int)
    a = p.parse_args()
    r = build(a.db, a.document_id)
    print("=== CANONICAL CHARACTER LAYER ===")
    for k in ("confirmed", "likely", "singleton", "excluded"):
        print(k + ":", r[k])


if __name__ == "__main__":
    main()
