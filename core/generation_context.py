from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


class GenerationContext:
    """Assemble a deterministic, source-grounded package for scene generation.

    This layer is deliberately read-only: it does not infer new facts. It joins
    scene presence, canonical character identity, canonical visual evidence,
    objects, events, and continuity state while preserving explicit unknowns.
    """

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def build(self, document_id: int, scene_id: int) -> dict[str, Any]:
        with sqlite3.connect(self.database_path) as con:
            con.row_factory = sqlite3.Row
            scene = con.execute(
                "SELECT id, story_id, scene_order, title, page_start, page_end, text, segmentation_method, confidence FROM scenes WHERE document_id=? AND id=?",
                (document_id, scene_id),
            ).fetchone()
            if scene is None:
                return self._empty(document_id, scene_id, "scene_not_found")

            characters = self._characters(con, document_id, scene_id)
            objects = self._objects(con, document_id, scene_id)
            events = self._events(con, document_id, scene_id)
            continuity = self._continuity(con, document_id, scene_id)
            previous = self._neighbor(con, document_id, scene_id, -1)
            following = self._neighbor(con, document_id, scene_id, 1)

            return {
                "document_id": document_id,
                "scene_id": scene_id,
                "source_grounded": True,
                "unknowns_must_remain_unknown": True,
                "scene": {
                    "story_id": scene["story_id"],
                    "scene_order": scene["scene_order"],
                    "title": scene["title"],
                    "page_start": scene["page_start"],
                    "page_end": scene["page_end"],
                    "text": scene["text"],
                    "segmentation_method": scene["segmentation_method"],
                    "confidence": scene["confidence"],
                },
                "characters": characters,
                "objects": objects,
                "events": events,
                "continuity": continuity,
                "neighbors": {"previous": previous, "next": following},
                "generation_constraints": [
                    "Use only supplied source-grounded character, object, event, and visual evidence.",
                    "Do not invent visual attributes that are absent or explicitly unknown.",
                    "Scene-specific evidence takes precedence over carried state when both exist.",
                    "Preserve canonical character identity and aliases.",
                ],
            }

    def _characters(self, con: sqlite3.Connection, document_id: int, scene_id: int) -> list[dict[str, Any]]:
        rows = con.execute(
            """SELECT DISTINCT cc.id canonical_character_id, cc.canonical_name, cc.status, cc.confidence
               FROM entity_mentions em
               JOIN canonical_character_aliases cca ON cca.entity_id=em.entity_id
               JOIN canonical_characters cc ON cc.id=cca.canonical_character_id
               WHERE em.document_id=? AND em.scene_id=?
                 AND cc.document_id=?
                 AND cc.status IN ('confirmed','likely','singleton')
               ORDER BY cc.id""",
            (document_id, scene_id, document_id),
        ).fetchall()
        result = []
        for row in rows:
            cid = int(row["canonical_character_id"])
            aliases = [dict(x) for x in con.execute(
                "SELECT alias, relationship, confidence FROM canonical_character_aliases WHERE canonical_character_id=? ORDER BY id",
                (cid,),
            ).fetchall()]
            vp = con.execute(
                "SELECT id FROM canonical_visual_profiles WHERE document_id=? AND canonical_character_id=?",
                (document_id, cid),
            ).fetchone()
            facts: list[dict[str, Any]] = []
            if vp:
                facts = [dict(x) for x in con.execute(
                    """SELECT category, attribute, value, status, confidence, scene_id,
                              page_start, page_end, evidence
                       FROM canonical_visual_facts
                       WHERE canonical_visual_profile_id=?
                         AND (scene_id=? OR scene_id IS NULL)
                       ORDER BY CASE WHEN scene_id=? THEN 0 ELSE 1 END, confidence DESC, id""",
                    (int(vp["id"]), scene_id, scene_id),
                ).fetchall()]
            mentions = [dict(x) for x in con.execute(
                """SELECT em.entity_id, e.canonical_name AS source_name,
                          em.page_start, em.page_end, em.context, em.confidence
                   FROM entity_mentions em JOIN entities e ON e.id=em.entity_id
                   JOIN canonical_character_aliases cca ON cca.entity_id=em.entity_id
                   WHERE em.document_id=? AND em.scene_id=? AND cca.canonical_character_id=?
                   ORDER BY em.page_start, em.id""",
                (document_id, scene_id, cid),
            ).fetchall()]
            result.append({
                "canonical_character_id": cid,
                "canonical_name": row["canonical_name"],
                "status": row["status"],
                "confidence": row["confidence"],
                "aliases": aliases,
                "visual_facts": facts,
                "scene_mentions": mentions,
                "unknown_visual_attributes": True,
            })
        return result

    @staticmethod
    def _objects(con: sqlite3.Connection, document_id: int, scene_id: int) -> list[dict[str, Any]]:
        rows = con.execute(
            """SELECT vom.object_id, vo.canonical_name, vo.profile_text,
                      vo.confidence AS object_confidence, vo.discovery_method,
                      vom.page_start, vom.page_end, vom.evidence, vom.confidence
               FROM visual_object_mentions vom
               JOIN visual_objects vo ON vo.id=vom.object_id
               WHERE vom.document_id=? AND vom.scene_id=?
               ORDER BY vo.canonical_name""",
            (document_id, scene_id),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _events(con: sqlite3.Connection, document_id: int, scene_id: int) -> list[dict[str, Any]]:
        rows = con.execute(
            """SELECT id, event_order, title, page_start, page_end, text,
                      discovery_method, confidence
               FROM events
               WHERE document_id=? AND scene_id=?
               ORDER BY event_order, id""",
            (document_id, scene_id),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _continuity(con: sqlite3.Connection, document_id: int, scene_id: int) -> dict[str, Any]:
        row = con.execute(
            """SELECT previous_scene_id, next_scene_id, carried_character_ids,
                      changed_character_ids, persistent_object_ids,
                      environment_state_json, continuity_notes_json
               FROM visual_scene_continuity
               WHERE document_id=? AND scene_id=?""",
            (document_id, scene_id),
        ).fetchone()
        if row is None:
            return {"available": False, "reason": "continuity_not_built"}
        return {
            "available": True,
            "previous_scene_id": row["previous_scene_id"],
            "next_scene_id": row["next_scene_id"],
            "carried_character_ids": _json(row["carried_character_ids"], []),
            "changed_character_ids": _json(row["changed_character_ids"], []),
            "persistent_object_ids": _json(row["persistent_object_ids"], []),
            "environment_state": _json(row["environment_state_json"], {}),
            "notes": _json(row["continuity_notes_json"], []),
        }

    @staticmethod
    def _neighbor(con: sqlite3.Connection, document_id: int, scene_id: int, direction: int) -> dict[str, Any] | None:
        scene = con.execute("SELECT scene_order FROM scenes WHERE document_id=? AND id=?", (document_id, scene_id)).fetchone()
        if scene is None:
            return None
        target = int(scene["scene_order"]) + direction
        row = con.execute(
            "SELECT id, scene_order, title, page_start, page_end FROM scenes WHERE document_id=? AND scene_order=? LIMIT 1",
            (document_id, target),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _empty(document_id: int, scene_id: int, reason: str) -> dict[str, Any]:
        return {
            "document_id": document_id,
            "scene_id": scene_id,
            "source_grounded": True,
            "unknowns_must_remain_unknown": True,
            "error": reason,
            "scene": None,
            "characters": [],
            "objects": [],
            "events": [],
            "continuity": {"available": False, "reason": reason},
            "neighbors": {"previous": None, "next": None},
            "generation_constraints": ["Do not invent missing source information."],
        }


def _json(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def get_generation_context(database_path: str | Path, document_id: int, scene_id: int) -> dict[str, Any]:
    return GenerationContext(database_path).build(document_id, scene_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a generation-ready source-grounded scene package")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("scene_id", type=int)
    parser.add_argument("--summary", action="store_true", help="Print counts instead of full scene text")
    args = parser.parse_args()
    result = get_generation_context(args.database, args.document_id, args.scene_id)
    if args.summary:
        print(json.dumps({
            "document_id": args.document_id,
            "scene_id": args.scene_id,
            "characters": len(result["characters"]),
            "visual_fact_count": sum(len(c["visual_facts"]) for c in result["characters"]),
            "objects": len(result["objects"]),
            "events": len(result["events"]),
            "continuity_available": result["continuity"].get("available", False),
            "previous_scene": result["neighbors"]["previous"],
            "next_scene": result["neighbors"]["next"],
        }, indent=2))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
