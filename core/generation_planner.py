from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .generation_context import get_generation_context
from .media_prompt_compiler import compile_media_prompts
from .visual_generation_policy import enrich_character


class GenerationPlanner:
    """Convert generation context into a deterministic generation plan."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    @staticmethod
    def _prompt_bundle(context, characters, objects, events, constraints):
        media_context = dict(context)
        media_context.update({
            "characters": characters,
            "objects": objects,
            "events": events,
            "generation_constraints": constraints,
        })
        media = compile_media_prompts(media_context)
        return {
            "image_prompt": media["image"]["prompt"],
            "image_dialogue_overlays": media["image"]["dialogue_overlays"],
            "image_layout": media["image"]["layout"],
            "visual_inference": media["visual_inference"],
            "short_video_prompt_package": media["short_video"],
            "long_video_prompt_package": media["long_video"],
            "audio_prompt": media["short_video"]["audio"],
            "media_prompt_package": media,
        }

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

        characters = [
            enrich_character(
                character,
                genre=context.get("visual_genre", "mythological_epic"),
            )
            for character in (context.get("characters") or [])
        ]

        visual_constraints = [
            "Preserve source-supported visual facts exactly.",
            "Controlled production visual inference is allowed for missing attributes using the configured genre policy.",
            "Never override, contradict, or silently relabel a source-supported fact as an inference.",
            "Never infer exact eye color, hair color, height, exact age, or facial measurements unless source evidence supplies them.",
            "Lock deterministic inferred profile attributes across scenes for the same canonical identity.",
            "Use mobile-first 9:16 composition for primary image/video output.",
            "At least one dialogue-or-narrative box is required for image composition.",
            "Dialogue/text boxes must stay inside the safe area and never cover faces, hands, important objects, or primary action.",
            "Keep source visual moments focused: one primary moment plus limited secondary context rather than unrelated prose aggregation.",
        ]
        if not characters:
            visual_constraints.append("No canonical character is source-confirmed as present; do not force a character identity into the scene.")

        prompts = self._prompt_bundle(
            context,
            characters,
            context.get("objects") or [],
            context.get("events") or [],
            visual_constraints,
        )
        return {
            "document_id": document_id,
            "scene_id": scene_id,
            "plan_version": 5,
            "plan_status": "ready",
            "source_grounded": True,
            "unknowns_must_remain_unknown": True,
            "scene": context["scene"],
            "characters": characters,
            "objects": context.get("objects") or [],
            "events": context.get("events") or [],
            "continuity": context.get("continuity") or {},
            "neighbors": context.get("neighbors") or {},
            "generation_constraints": context.get("generation_constraints") or [],
            "visual_constraints": visual_constraints,
            **prompts,
            "source_evidence": self._evidence(context),
        }

    @staticmethod
    def _evidence(context: dict[str, Any]) -> list[dict[str, Any]]:
        evidence = []
        for character in context.get("characters") or []:
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
        for obj in context.get("objects") or []:
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("scene_id", type=int)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    result = build_generation_plan(args.database, args.document_id, args.scene_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
