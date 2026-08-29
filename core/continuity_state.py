from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS visual_entity_state (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    state_order INTEGER NOT NULL,
    presence TEXT NOT NULL DEFAULT 'present',
    appearance_json TEXT NOT NULL DEFAULT '{}',
    clothing_json TEXT NOT NULL DEFAULT '{}',
    condition_json TEXT NOT NULL DEFAULT '{}',
    emotional_json TEXT NOT NULL DEFAULT '{}',
    continuity_status TEXT NOT NULL DEFAULT 'carried',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0,
    UNIQUE(document_id, entity_id, scene_id)
);

CREATE TABLE IF NOT EXISTS visual_state_changes (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    previous_scene_id INTEGER REFERENCES scenes(id) ON DELETE SET NULL,
    category TEXT NOT NULL,
    attribute TEXT NOT NULL,
    previous_value TEXT,
    new_value TEXT,
    change_type TEXT NOT NULL,
    evidence TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0,
    UNIQUE(document_id, entity_id, scene_id, category, attribute, change_type)
);

CREATE TABLE IF NOT EXISTS visual_scene_continuity (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    previous_scene_id INTEGER REFERENCES scenes(id) ON DELETE SET NULL,
    next_scene_id INTEGER REFERENCES scenes(id) ON DELETE SET NULL,
    carried_character_ids TEXT NOT NULL DEFAULT '[]',
    changed_character_ids TEXT NOT NULL DEFAULT '[]',
    persistent_object_ids TEXT NOT NULL DEFAULT '[]',
    environment_state_json TEXT NOT NULL DEFAULT '{}',
    continuity_notes_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(document_id, scene_id)
);

CREATE INDEX IF NOT EXISTS idx_visual_entity_state_entity_order
    ON visual_entity_state(document_id, entity_id, state_order);
CREATE INDEX IF NOT EXISTS idx_visual_state_changes_entity
    ON visual_state_changes(document_id, entity_id, scene_id);
CREATE INDEX IF NOT EXISTS idx_visual_scene_continuity_scene
    ON visual_scene_continuity(document_id, scene_id);
"""


class ContinuityStateBuilder:
    """Build deterministic, source-grounded state across adjacent scenes."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def build(self, document_id: int) -> dict[str, int]:
        with sqlite3.connect(self.database_path) as con:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys = ON")
            con.executescript(SCHEMA)
            self._clear(con, document_id)

            scenes = con.execute(
                "SELECT id, story_id, scene_order, page_start, page_end, text FROM scenes WHERE document_id=? ORDER BY id",
                (document_id,),
            ).fetchall()
            if not scenes:
                return {"entity_states": 0, "state_changes": 0, "scene_continuity": 0}

            scene_order = {int(r["id"]): i for i, r in enumerate(scenes)}
            profile_lookup = self._profile_lookup(con, document_id)
            entity_rows = con.execute(
                "SELECT id, entity_type, canonical_name FROM entities WHERE document_id=? ORDER BY id",
                (document_id,),
            ).fetchall()
            character_ids = {int(r["id"]) for r in entity_rows if r["entity_type"] == "character"}

            per_entity_seen: dict[int, dict[str, Any]] = {}
            states = 0
            changes = 0

            for idx, scene in enumerate(scenes):
                sid = int(scene["id"])
                prev_scene_id = int(scenes[idx - 1]["id"]) if idx else None
                next_scene_id = int(scenes[idx + 1]["id"]) if idx + 1 < len(scenes) else None
                mentioned = con.execute(
                    """SELECT DISTINCT em.entity_id, e.entity_type, e.canonical_name
                       FROM entity_mentions em JOIN entities e ON e.id=em.entity_id
                       WHERE em.document_id=? AND em.scene_id=? ORDER BY em.entity_id""",
                    (document_id, sid),
                ).fetchall()

                carried: list[int] = []
                changed: list[int] = []
                for row in mentioned:
                    eid = int(row["entity_id"])
                    if eid not in character_ids:
                        continue
                    facts = self._scene_facts(con, document_id, eid, sid)
                    current = self._normalize_state(facts)
                    prev = per_entity_seen.get(eid)
                    continuity = "introduced" if prev is None else "carried"
                    entity_changes = []
                    if prev is not None:
                        entity_changes = self._diff_states(prev["state"], current, sid, prev["scene_id"], eid, con, document_id)
                        if entity_changes:
                            continuity = "changed"
                            changed.append(eid)
                        else:
                            carried.append(eid)
                    else:
                        carried.append(eid)

                    evidence = facts.get("evidence", [])
                    con.execute(
                        """INSERT INTO visual_entity_state
                           (document_id,entity_id,scene_id,state_order,presence,
                            appearance_json,clothing_json,condition_json,emotional_json,
                            continuity_status,evidence_json,confidence)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            document_id, eid, sid, idx + 1, "present",
                            json.dumps(current["appearance"], ensure_ascii=False, sort_keys=True),
                            json.dumps(current["clothing"], ensure_ascii=False, sort_keys=True),
                            json.dumps(current["condition"], ensure_ascii=False, sort_keys=True),
                            json.dumps(current["emotional"], ensure_ascii=False, sort_keys=True),
                            continuity,
                            json.dumps(evidence, ensure_ascii=False),
                            current["confidence"],
                        ),
                    )
                    states += 1
                    per_entity_seen[eid] = {"scene_id": sid, "state": current}
                    changes += len(entity_changes)

                environment_state = self._environment_state(con, document_id, sid)
                persistent_objects = self._persistent_objects(con, document_id, sid)
                notes = []
                if idx:
                    notes.append({"type": "previous_scene", "scene_id": prev_scene_id})
                if next_scene_id is not None:
                    notes.append({"type": "next_scene", "scene_id": next_scene_id})
                con.execute(
                    """INSERT INTO visual_scene_continuity
                       (document_id,scene_id,previous_scene_id,next_scene_id,
                        carried_character_ids,changed_character_ids,persistent_object_ids,
                        environment_state_json,continuity_notes_json)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        document_id, sid, prev_scene_id, next_scene_id,
                        json.dumps(sorted(carried)), json.dumps(sorted(changed)),
                        json.dumps(sorted(persistent_objects)),
                        json.dumps(environment_state, ensure_ascii=False, sort_keys=True),
                        json.dumps(notes, ensure_ascii=False),
                    ),
                )

            con.commit()
            return {
                "entity_states": states,
                "state_changes": changes,
                "scene_continuity": len(scenes),
            }

    @staticmethod
    def _clear(con: sqlite3.Connection, document_id: int) -> None:
        con.execute("DELETE FROM visual_scene_continuity WHERE document_id=?", (document_id,))
        con.execute("DELETE FROM visual_state_changes WHERE document_id=?", (document_id,))
        con.execute("DELETE FROM visual_entity_state WHERE document_id=?", (document_id,))

    @staticmethod
    def _profile_lookup(con: sqlite3.Connection, document_id: int) -> dict[int, int]:
        rows = con.execute("SELECT id, entity_id FROM visual_profiles WHERE document_id=? AND profile_type='character'", (document_id,)).fetchall()
        return {int(r["entity_id"]): int(r["id"]) for r in rows if r["entity_id"] is not None}

    @staticmethod
    def _scene_facts(con: sqlite3.Connection, document_id: int, entity_id: int, scene_id: int) -> dict[str, Any]:
        profile = con.execute(
            "SELECT id FROM visual_profiles WHERE document_id=? AND entity_id=? AND profile_type='character' LIMIT 1",
            (document_id, entity_id),
        ).fetchone()
        if profile is None:
            return {"appearance": {}, "clothing": {}, "condition": {}, "emotional": {}, "evidence": [], "confidence": 0.0}
        rows = con.execute(
            """SELECT attribute,value,category,evidence,confidence
               FROM visual_facts
               WHERE profile_id=? AND (scene_id=? OR scene_id IS NULL)
               ORDER BY confidence DESC, id""",
            (int(profile["id"]), scene_id),
        ).fetchall()
        state = {"appearance": {}, "clothing": {}, "condition": {}, "emotional": {}, "evidence": [], "confidence": 0.0}
        for row in rows:
            attr = str(row["attribute"])
            category = str(row["category"])
            bucket = "appearance"
            if category == "clothing":
                bucket = "clothing"
            elif attr in {"distinctive_mark", "injury", "condition", "wound"}:
                bucket = "condition"
            elif category == "expression":
                bucket = "emotional"
            state[bucket].setdefault(attr, []).append(str(row["value"]))
            if row["evidence"]:
                state["evidence"].append({"attribute": attr, "evidence": str(row["evidence"]), "scene_id": scene_id, "confidence": float(row["confidence"] or 0)})
            state["confidence"] = max(state["confidence"], float(row["confidence"] or 0))
        return state

    @staticmethod
    def _normalize_state(raw: dict[str, Any]) -> dict[str, Any]:
        return {k: raw.get(k, {}) for k in ("appearance", "clothing", "condition", "emotional")} | {
            "evidence": raw.get("evidence", []),
            "confidence": raw.get("confidence", 0.0),
        }

    def _diff_states(self, previous: dict[str, Any], current: dict[str, Any], scene_id: int, previous_scene_id: int, entity_id: int, con: sqlite3.Connection, document_id: int) -> list[dict[str, Any]]:
        diffs = []
        for category in ("appearance", "clothing", "condition", "emotional"):
            before = previous.get(category, {})
            after = current.get(category, {})
            attrs = set(before) | set(after)
            for attr in sorted(attrs):
                old = before.get(attr)
                new = after.get(attr)
                if old == new:
                    continue
                change_type = "introduced" if old is None else ("removed" if new is None else "updated")
                evidence = ""
                for item in current.get("evidence", []):
                    if item.get("attribute") == attr:
                        evidence = str(item.get("evidence") or "")
                        break
                con.execute(
                    """INSERT OR IGNORE INTO visual_state_changes
                       (document_id,entity_id,scene_id,previous_scene_id,category,attribute,
                        previous_value,new_value,change_type,evidence,confidence)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        document_id, entity_id, scene_id, previous_scene_id, category, attr,
                        json.dumps(old, ensure_ascii=False) if old is not None else None,
                        json.dumps(new, ensure_ascii=False) if new is not None else None,
                        change_type, evidence, float(current.get("confidence", 0.0)),
                    ),
                )
                diffs.append({"category": category, "attribute": attr, "change_type": change_type})
        return diffs

    @staticmethod
    def _environment_state(con: sqlite3.Connection, document_id: int, scene_id: int) -> dict[str, Any]:
        profiles = con.execute(
            "SELECT id, canonical_name FROM visual_profiles WHERE document_id=? AND profile_type='environment'",
            (document_id,),
        ).fetchall()
        result: dict[str, Any] = {}
        for profile in profiles:
            facts = con.execute(
                "SELECT attribute,value,confidence FROM visual_facts WHERE profile_id=? AND scene_id=? ORDER BY confidence DESC,id",
                (int(profile["id"]), scene_id),
            ).fetchall()
            if facts:
                result[str(profile["canonical_name"])] = [
                    {"attribute": str(f["attribute"]), "value": str(f["value"]), "confidence": float(f["confidence"] or 0)}
                    for f in facts
                ]
        return result

    @staticmethod
    def _persistent_objects(con: sqlite3.Connection, document_id: int, scene_id: int) -> list[int]:
        rows = con.execute("SELECT object_id FROM visual_object_mentions WHERE document_id=? AND scene_id=?", (document_id, scene_id)).fetchall()
        return [int(r[0]) for r in rows]


def build_continuity_state(database_path: str | Path, document_id: int) -> dict[str, int]:
    return ContinuityStateBuilder(database_path).build(document_id)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Build scene-to-scene visual continuity state")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    args = parser.parse_args()
    print(json.dumps(build_continuity_state(args.database, args.document_id), indent=2))


if __name__ == "__main__":
    main()
