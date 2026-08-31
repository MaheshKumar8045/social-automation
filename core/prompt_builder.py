from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .generation_planner import build_generation_plan


class PromptBuilder:
    """Translate a structured generation plan into grounded image/video instructions."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def build(self, document_id: int, scene_id: int, *, mode: str = "image") -> dict[str, Any]:
        if mode not in {"image", "video"}:
            raise ValueError("mode must be 'image' or 'video'")
        plan = build_generation_plan(self.database_path, document_id, scene_id)
        if plan.get("plan_status") != "ready":
            return {
                "document_id": document_id,
                "scene_id": scene_id,
                "mode": mode,
                "status": "unavailable",
                "reason": plan.get("reason", "generation_plan_unavailable"),
                "source_grounded": True,
                "unknowns_must_remain_unknown": True,
            }

        prompt = self._scene_prompt(plan, mode)
        negative = self._negative_constraints(plan)
        continuity = self._continuity_constraints(plan)
        return {
            "document_id": document_id,
            "scene_id": scene_id,
            "mode": mode,
            "status": "ready",
            "prompt_version": 1,
            "source_grounded": True,
            "unknowns_must_remain_unknown": True,
            "prompt": prompt,
            "negative_constraints": negative,
            "continuity_constraints": continuity,
            "plan": {
                "characters": plan["characters"],
                "objects": plan["objects"],
                "events": plan["events"],
                "continuity": plan["continuity"],
                "neighbors": plan["neighbors"],
            },
        }

    def _scene_prompt(self, plan: dict[str, Any], mode: str) -> str:
        scene = plan["scene"]
        parts = [
            f"Source-grounded {mode} depiction of scene {plan['scene_id']}.",
            f"Scene: {scene['title']}.",
            "Depict the supplied source scene faithfully without adding unsupported visual facts.",
        ]

        event_text = " ".join(str(e.get("text") or "").strip() for e in plan["events"] if e.get("text"))
        if event_text:
            parts.append(f"Narrative action: {self._compact(event_text, 700)}")

        character_parts = []
        for character in plan["characters"]:
            known = []
            for fact in character.get("visual_facts", []):
                known.append(f"{fact['attribute']}={fact['value']}")
            suffix = f" Known visual facts: {', '.join(known)}." if known else " No additional canonical visual attributes are established by the source."
            character_parts.append(
                f"Character {character['canonical_name']} ({character['identity_status']})." + suffix
            )
        if character_parts:
            parts.append("Characters: " + " ".join(character_parts))

        object_names = [str(o.get("canonical_name")) for o in plan["objects"] if o.get("canonical_name")]
        if object_names:
            parts.append("Source-identified objects present: " + ", ".join(object_names) + ".")

        if mode == "video":
            parts.append("Use motion appropriate to the supplied narrative action; do not add unsupported actions or character traits.")
        else:
            parts.append("Use composition and lighting appropriate to the supplied scene text without inventing ungrounded details.")

        return " ".join(parts)

    @staticmethod
    def _negative_constraints(plan: dict[str, Any]) -> list[str]:
        constraints = [
            "Do not invent character hair color, eye color, height, age, body type, clothing, facial features, or accessories unless source evidence is supplied.",
            "Do not merge distinct canonical characters.",
            "Do not replace a canonical identity with an alias as though it were a different person.",
            "Do not add unsupported objects, locations, creatures, costumes, weapons, or environmental details.",
            "Do not contradict source-established visual facts.",
        ]
        return constraints

    @staticmethod
    def _continuity_constraints(plan: dict[str, Any]) -> list[str]:
        continuity = plan.get("continuity") or {}
        rules = [
            "Preserve canonical identity across adjacent scenes.",
            "Carry forward source-supported visual state unless the current scene supplies a change.",
        ]
        for cid in continuity.get("changed_character_ids", []):
            rules.append(f"Apply the source-supported visual state change for canonical character {cid} in this scene.")
        for oid in continuity.get("persistent_object_ids", []):
            rules.append(f"Preserve source continuity for object {oid} when visible in the scene.")
        return rules

    @staticmethod
    def _compact(text: str, limit: int) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def build_prompt(database_path: str | Path, document_id: int, scene_id: int, mode: str = "image") -> dict[str, Any]:
    return PromptBuilder(database_path).build(document_id, scene_id, mode=mode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build grounded image/video prompts from a generation plan")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("scene_id", type=int)
    parser.add_argument("--mode", choices=["image", "video"], default="image")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    result = build_prompt(args.database, args.document_id, args.scene_id, args.mode)
    if args.summary:
        print(json.dumps({
            "document_id": result["document_id"],
            "scene_id": result["scene_id"],
            "mode": result["mode"],
            "status": result["status"],
            "prompt_chars": len(result.get("prompt", "")),
            "negative_constraints": len(result.get("negative_constraints", [])),
            "continuity_constraints": len(result.get("continuity_constraints", [])),
            "unknowns_must_remain_unknown": result.get("unknowns_must_remain_unknown"),
        }, indent=2))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
