from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS canonical_visual_profiles (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    canonical_character_id INTEGER NOT NULL REFERENCES canonical_characters(id) ON DELETE CASCADE,
    canonical_name TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL NOT NULL,
    source_profile_ids_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(document_id, canonical_character_id)
);

CREATE TABLE IF NOT EXISTS canonical_visual_facts (
    id INTEGER PRIMARY KEY,
    canonical_visual_profile_id INTEGER NOT NULL REFERENCES canonical_visual_profiles(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    attribute TEXT NOT NULL,
    value TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'supported',
    confidence REAL NOT NULL,
    source_profile_id INTEGER,
    source_fact_id INTEGER,
    source_entity_id INTEGER,
    scene_id INTEGER,
    page_start INTEGER,
    page_end INTEGER,
    evidence TEXT NOT NULL DEFAULT '',
    UNIQUE(canonical_visual_profile_id, category, attribute, value, source_fact_id)
);

CREATE INDEX IF NOT EXISTS idx_canonical_visual_profiles_doc
ON canonical_visual_profiles(document_id, status);
CREATE INDEX IF NOT EXISTS idx_canonical_visual_facts_profile
ON canonical_visual_facts(canonical_visual_profile_id, category, attribute);
CREATE INDEX IF NOT EXISTS idx_canonical_visual_facts_scene
ON canonical_visual_facts(scene_id);
"""

VALID_STATUSES = {"confirmed", "likely", "singleton"}


def build(db: str | Path, document_id: int) -> dict[str, int]:
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(SCHEMA)

        con.execute(
            "DELETE FROM canonical_visual_facts WHERE canonical_visual_profile_id IN "
            "(SELECT id FROM canonical_visual_profiles WHERE document_id=?)",
            (document_id,),
        )
        con.execute("DELETE FROM canonical_visual_profiles WHERE document_id=?", (document_id,))

        canonical_rows = con.execute(
            """SELECT id, identity_group_id, canonical_name, confidence, status
               FROM canonical_characters
               WHERE document_id=? AND status IN ('confirmed','likely','singleton')
               ORDER BY id""",
            (document_id,),
        ).fetchall()

        counts = {"profiles": 0, "facts": 0, "source_profiles": 0, "contradictions": 0}

        for cc in canonical_rows:
            member_rows = con.execute(
                """SELECT entity_id FROM canonical_character_aliases
                   WHERE canonical_character_id=? ORDER BY id""",
                (cc["id"],),
            ).fetchall()
            entity_ids = [int(r["entity_id"]) for r in member_rows]

            visual_rows = []
            if entity_ids:
                placeholders = ",".join("?" for _ in entity_ids)
                visual_rows = con.execute(
                    f"""SELECT id, entity_id, confidence
                        FROM visual_profiles
                        WHERE document_id=? AND profile_type='character'
                          AND entity_id IN ({placeholders})
                        ORDER BY confidence DESC, id""",
                    (document_id, *entity_ids),
                ).fetchall()

            cur = con.execute(
                """INSERT INTO canonical_visual_profiles
                   (document_id,canonical_character_id,canonical_name,status,confidence,source_profile_ids_json)
                   VALUES(?,?,?,?,?,?)""",
                (
                    document_id,
                    int(cc["id"]),
                    cc["canonical_name"],
                    cc["status"],
                    float(cc["confidence"] or 0),
                    json.dumps([int(r["id"]) for r in visual_rows]),
                ),
            )
            cvp_id = int(cur.lastrowid)
            counts["profiles"] += 1
            counts["source_profiles"] += len(visual_rows)

            fact_groups: dict[tuple[str, str, str], list[sqlite3.Row]] = {}
            for vp in visual_rows:
                facts = con.execute(
                    """SELECT vf.*, vp.entity_id
                       FROM visual_facts vf
                       JOIN visual_profiles vp ON vp.id=vf.profile_id
                       WHERE vf.profile_id=?
                       ORDER BY vf.id""",
                    (int(vp["id"]),),
                ).fetchall()
                for fact in facts:
                    key = (str(fact["category"]), str(fact["attribute"]), str(fact["value"]))
                    fact_groups.setdefault(key, []).append(fact)

            for (category, attribute, value), facts in fact_groups.items():
                support_count = len(facts)
                confidence = min(0.99, max(float(f["confidence"] or 0) for f in facts))
                evidence = next((str(f["evidence"]) for f in facts if str(f["evidence"] or "").strip()), "")
                statuses = {str(f["status"] or "supported") for f in facts}
                sources = {int(f["source_id"]) for f in facts if f["source_id"] is not None}
                scenes = {int(f["scene_id"]) for f in facts if f["scene_id"] is not None}

                # Conflicting values for the same canonical attribute are retained
                # as separate rows rather than silently resolving them.
                same_attribute_values = {
                    k[2]
                    for k in fact_groups
                    if k[0] == category and k[1] == attribute
                }
                status = "supported"
                if len(same_attribute_values) > 1:
                    status = "contradictory"
                    counts["contradictions"] += 1

                primary = facts[0]
                con.execute(
                    """INSERT INTO canonical_visual_facts
                       (canonical_visual_profile_id,category,attribute,value,status,confidence,
                        source_profile_id,source_fact_id,source_entity_id,scene_id,page_start,page_end,evidence)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        cvp_id,
                        category,
                        attribute,
                        value,
                        status,
                        confidence,
                        int(primary["profile_id"]),
                        int(primary["id"]),
                        int(primary["entity_id"]) if primary["entity_id"] is not None else None,
                        int(next(iter(scenes))) if len(scenes) == 1 else None,
                        int(primary["page_start"]) if primary["page_start"] is not None else None,
                        int(primary["page_end"]) if primary["page_end"] is not None else None,
                        evidence,
                    ),
                )
                counts["facts"] += 1

        con.commit()
        return counts


def get_character_context(db: str | Path, document_id: int, canonical_character_id: int, scene_id: int | None = None) -> dict:
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        profile = con.execute(
            """SELECT id,canonical_character_id,canonical_name,status,confidence
               FROM canonical_visual_profiles
               WHERE document_id=? AND canonical_character_id=?""",
            (document_id, canonical_character_id),
        ).fetchone()
        if not profile:
            return {"found": False, "document_id": document_id, "canonical_character_id": canonical_character_id}

        params = [int(profile["id"])]
        where = "canonical_visual_profile_id=?"
        if scene_id is not None:
            where += " AND (scene_id=? OR scene_id IS NULL)"
            params.append(int(scene_id))

        facts = con.execute(
            f"""SELECT category,attribute,value,status,confidence,scene_id,page_start,page_end,evidence
                FROM canonical_visual_facts
                WHERE {where}
                ORDER BY category,attribute,id""",
            params,
        ).fetchall()

        by_category: dict[str, list[dict]] = {}
        for f in facts:
            by_category.setdefault(str(f["category"]), []).append(dict(f))

        aliases = con.execute(
            """SELECT alias,relationship,confidence
               FROM canonical_character_aliases
               WHERE canonical_character_id=? ORDER BY id""",
            (canonical_character_id,),
        ).fetchall()

        return {
            "found": True,
            "document_id": document_id,
            "canonical_character_id": canonical_character_id,
            "canonical_name": profile["canonical_name"],
            "status": profile["status"],
            "confidence": profile["confidence"],
            "aliases": [dict(a) for a in aliases],
            "facts": by_category,
            "unknowns_must_remain_unknown": True,
        }


def main() -> None:
    p = argparse.ArgumentParser(description="Build and query canonical visual character profiles")
    p.add_argument("database")
    p.add_argument("document_id", type=int)
    p.add_argument("--character-id", type=int)
    p.add_argument("--scene-id", type=int)
    args = p.parse_args()

    result = build(args.database, args.document_id)
    print("=== CANONICAL VISUAL BIBLE ===")
    for key in ("profiles", "facts", "source_profiles", "contradictions"):
        print(f"{key}: {result[key]}")

    if args.character_id is not None:
        print(json.dumps(get_character_context(args.database, args.document_id, args.character_id, args.scene_id), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
