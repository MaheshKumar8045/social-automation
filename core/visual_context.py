from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from core.visual_knowledge_bible import SCHEMA, VisualKnowledgeBible


class VisualContextStore:
    """Read generation-ready visual continuity context from SQLite.

    This class is intentionally read-only apart from ensuring the visual
    schema exists. It returns source evidence, confidence and explicit
    unknown-state metadata so downstream generation can stay grounded.
    """

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        return connection

    def character_profiles(self, document_id: int) -> list[dict[str, Any]]:
        return self._profiles(document_id, "character")

    def environment_profiles(self, document_id: int) -> list[dict[str, Any]]:
        return self._profiles(document_id, "environment")

    def object_profiles(self, document_id: int) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT id, canonical_name, profile_text, confidence, discovery_method FROM visual_objects WHERE document_id=? ORDER BY canonical_name",
                (document_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def profile(self, document_id: int, canonical_name: str) -> dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute(
                """SELECT id, entity_id, profile_type, canonical_name, summary,
                          metadata_json, confidence
                   FROM visual_profiles
                   WHERE document_id=? AND canonical_name=?
                   ORDER BY confidence DESC, id
                   LIMIT 1""",
                (document_id, canonical_name),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["metadata"] = self._json(result.pop("metadata_json"), {})
            result["facts"] = self._facts(con, int(row["id"]))
            return result

    def scene_context(self, document_id: int, scene_id: int) -> dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM scene_visual_context WHERE document_id=? AND scene_id=?",
                (document_id, scene_id),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            for field in (
                "character_profile_ids",
                "environment_profile_ids",
                "object_mentions",
                "continuity_json",
                "evidence_json",
            ):
                result[field] = self._json(result[field], [] if field.endswith("_ids") or field == "object_mentions" or field == "evidence_json" else {})
            result["characters"] = self._profiles_by_ids(con, result["character_profile_ids"])
            result["environments"] = self._profiles_by_ids(con, result["environment_profile_ids"])
            result["objects"] = self._objects_by_ids(con, result["object_mentions"])
            return result

    def generation_context(self, document_id: int, scene_id: int) -> dict[str, Any]:
        """Return a compact, deterministic payload suitable for a generator."""
        context = self.scene_context(document_id, scene_id)
        if context is None:
            return {
                "document_id": document_id,
                "scene_id": scene_id,
                "source_grounded": True,
                "unknowns_must_remain_unknown": True,
                "characters": [],
                "environments": [],
                "objects": [],
                "continuity": {},
                "evidence": [],
            }
        return {
            "document_id": document_id,
            "scene_id": scene_id,
            "source_grounded": True,
            "unknowns_must_remain_unknown": True,
            "characters": context["characters"],
            "environments": context["environments"],
            "objects": context["objects"],
            "continuity": context["continuity_json"],
            "evidence": context["evidence_json"],
        }

    def _profiles(self, document_id: int, profile_type: str) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                """SELECT id, entity_id, profile_type, canonical_name, summary,
                          metadata_json, confidence
                   FROM visual_profiles
                   WHERE document_id=? AND profile_type=?
                   ORDER BY canonical_name""",
                (document_id, profile_type),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["metadata"] = self._json(item.pop("metadata_json"), {})
                item["facts"] = self._facts(con, int(row["id"]))
                result.append(item)
            return result

    @staticmethod
    def _facts(con: sqlite3.Connection, profile_id: int) -> list[dict[str, Any]]:
        rows = con.execute(
            """SELECT category, attribute, value, status, source_type, source_id,
                      scene_id, page_start, page_end, evidence, confidence,
                      extraction_method
               FROM visual_facts
               WHERE profile_id=?
               ORDER BY category, attribute, id""",
            (profile_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _profiles_by_ids(con: sqlite3.Connection, ids: list[int]) -> list[dict[str, Any]]:
        result = []
        for profile_id in ids:
            row = con.execute(
                "SELECT id, entity_id, profile_type, canonical_name, summary, metadata_json, confidence FROM visual_profiles WHERE id=?",
                (int(profile_id),),
            ).fetchone()
            if row is None:
                continue
            item = dict(row)
            item["metadata"] = VisualContextStore._json(item.pop("metadata_json"), {})
            item["facts"] = VisualContextStore._facts(con, int(row["id"]))
            result.append(item)
        return result

    @staticmethod
    def _objects_by_ids(con: sqlite3.Connection, ids: list[int]) -> list[dict[str, Any]]:
        result = []
        for object_id in ids:
            row = con.execute(
                "SELECT id, canonical_name, profile_text, confidence, discovery_method FROM visual_objects WHERE id=?",
                (int(object_id),),
            ).fetchone()
            if row:
                result.append(dict(row))
        return result

    @staticmethod
    def _json(value: str | None, default: Any) -> Any:
        try:
            return json.loads(value or "")
        except (TypeError, ValueError, json.JSONDecodeError):
            return default


def build_visual_bible(database_path: str | Path, document_id: int) -> dict[str, int]:
    """Convenience wrapper used by the CLI and pipeline integrations."""
    return VisualKnowledgeBible(database_path).build(document_id)


def get_generation_context(database_path: str | Path, document_id: int, scene_id: int) -> dict[str, Any]:
    return VisualContextStore(database_path).generation_context(document_id, scene_id)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Retrieve generation-ready visual context")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("scene_id", type=int)
    args = parser.parse_args()
    print(json.dumps(get_generation_context(args.database, args.document_id, args.scene_id), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
