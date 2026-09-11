
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .generation_planner import build_generation_plan


class PromptBuilder:
    """Compatibility layer exposing the canonical media compiler output."""

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
            }

        if mode == "image":
            prompt = plan["image_prompt"]
        else:
            clips = plan["short_video_prompt_package"].get("clips") or []
            prompt = clips[0]["prompt"] if clips else plan["long_video_prompt_package"]["shots"][0]["prompt"]

        return {
            "document_id": document_id,
            "scene_id": scene_id,
            "mode": mode,
            "status": "ready",
            "prompt_version": plan.get("plan_version"),
            "source_grounded": True,
            "unknowns_must_remain_unknown": True,
            "prompt": prompt,
            "negative_constraints": [
                "Never contradict source-supported facts.",
                "Never replace a canonical identity with a different character.",
                "Do not introduce unsupported story events or objects.",
                "Use controlled production inference only from the configured policy.",
                "Keep inferred identity attributes stable across scenes.",
            ],
            "continuity_constraints": [
                "Preserve identity anchors for recurring canonical characters.",
                "Preserve established subject scale and spatial relationships when the story continues.",
            ],
            "layout": plan.get("image_layout"),
            "visual_inference": plan.get("visual_inference"),
        }


def build_prompt(database_path: str | Path, document_id: int, scene_id: int, mode: str = "image") -> dict[str, Any]:
    return PromptBuilder(database_path).build(document_id, scene_id, mode=mode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build grounded image/video prompts")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("scene_id", type=int)
    parser.add_argument("--mode", choices=["image", "video"], default="image")
    args = parser.parse_args()
    print(json.dumps(build_prompt(args.database, args.document_id, args.scene_id, mode=args.mode), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
