from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from .generation_context import get_generation_context


class GenerationPlanner:
    """Convert generation context into a deterministic generation plan.

    This layer never invents missing visual information. It separates source
    evidence from derived instructions so downstream prompt/model adapters can
    remain provider-agnostic.
    """

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def build(self, document_id: int, scene_id: int) -> dict[str, Any]:
        context = get_generation_context(self.database_path, document_id, scene_id)
        if context.get("error"):
            return {
                "document_id": document_id,
                "scene_id": scene_id,
                "plan_status": "unavailable",
                "reason": context["error"],
                "source_grounded": True,
                "unknowns_must_remain_unknown": True,
            }

        characters = []
        for character in context["characters"]:
            characters.append({
                "canonical_character_id": character["canonical_character_id"],
                "canonical_name": character["canonical_name"],
                "identity_status": character["status"],
                "identity_confidence": character["confidence"],
                "aliases": character["aliases"],
                "visual_facts": character["visual_facts"],
                "scene_mentions": character["scene_mentions"],
                "unknown_visual_attributes": character["unknown_visual_attributes"],
            })

        visual_constraints = [
            "Preserve canonical character identity.",
            "Use only source-grounded visual facts supplied in this plan.",
            "Do not infer missing hair, face, body, clothing, age, or other visual attributes.",
            "Preserve scene-specific visual state when present.",
        ]
        if not characters:
            visual_constraints.append("No canonical character is source-confirmed as present in this scene.")

        return {
            "document_id": document_id,
            "scene_id": scene_id,
            "plan_version": 1,
            "plan_status": "ready",
            "source_grounded": True,
            "unknowns_must_remain_unknown": True,
            "scene": context["scene"],
            "characters": characters,
            "objects": context["objects"],
            "events": context["events"],
            "continuity": context["continuity"],
            "neighbors": context["neighbors"],
            "generation_constraints": context["generation_constraints"],
            "visual_constraints": visual_constraints,
            "source_evidence": self._evidence(context),
        }

    @staticmethod
    def _evidence(context: dict[str, Any]) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for character in context["characters"]:
            for mention in character.get("scene_mentions", []):
                evidence.append({
                    "type": "character_mention",
                    "canonical_character_id": character["canonical_character_id"],
                    "source_name": mention.get("source_name"),
                    "page_start": mention.get("page_start"),
                    "page_end": mention.get("page_end"),
                    "context": mention.get("context"),
                    "confidence": mention.get("confidence"),
                })
            for fact in character.get("visual_facts", []):
                evidence.append({
                    "type": "visual_fact",
                    "canonical_character_id": character["canonical_character_id"],
                    "category": fact.get("category"),
                    "attribute": fact.get("attribute"),
                    "value": fact.get("value"),
                    "scene_id": fact.get("scene_id"),
                    "page_start": fact.get("page_start"),
                    "page_end": fact.get("page_end"),
                    "evidence": fact.get("evidence"),
                    "confidence": fact.get("confidence"),
                })
        for obj in context["objects"]:
            evidence.append({
                "type": "object_mention",
                "object_id": obj.get("object_id"),
                "canonical_name": obj.get("canonical_name"),
                "page_start": obj.get("page_start"),
                "page_end": obj.get("page_end"),
                "evidence": obj.get("evidence"),
                "confidence": obj.get("confidence"),
            })
        return evidence


def build_generation_plan(database_path: str | Path, document_id: int, scene_id: int) -> dict[str, Any]:
    return GenerationPlanner(database_path).build(document_id, scene_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic generation plan for one scene")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("scene_id", type=int)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    result = build_generation_plan(args.database, args.document_id, args.scene_id)
    if args.summary:
        print(json.dumps({
            "document_id": args.document_id,
            "scene_id": args.scene_id,
            "plan_status": result.get("plan_status"),
            "characters": len(result.get("characters", [])),
            "visual_fact_count": sum(len(c.get("visual_facts", [])) for c in result.get("characters", [])),
            "objects": len(result.get("objects", [])),
            "events": len(result.get("events", [])),
            "evidence_items": len(result.get("source_evidence", [])),
            "unknowns_must_remain_unknown": result.get("unknowns_must_remain_unknown"),
        }, indent=2))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
