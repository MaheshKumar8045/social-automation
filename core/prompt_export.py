from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from .canonical_visual_bible import build as build_visual_bible
from .character_candidate_gate import build as build_candidate_gate
from .character_canonicalizer import build as build_canonical_characters
from .character_identity_normalizer import build as build_identity_normalizer
from .continuity_state import build_continuity_state
from .generation_planner import build_generation_plan


def _scene_rows(database: str | Path, document_id: int) -> list[dict[str, Any]]:
    with sqlite3.connect(database) as con:
        con.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in con.execute(
                """SELECT id, story_id, scene_order, title, page_start, page_end
                   FROM scenes WHERE document_id=? ORDER BY story_id, scene_order""",
                (document_id,),
            ).fetchall()
        ]


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("plan_status") != "ready":
        errors.append("plan_status is not ready")
    if plan.get("source_grounded") is not True:
        errors.append("source_grounded must be true")
    if plan.get("unknowns_must_remain_unknown") is not True:
        errors.append("unknowns_must_remain_unknown must be true")
    image = plan.get("image_prompt")
    if not isinstance(image, str) or len(image.strip()) < 40:
        errors.append("image prompt is missing or too short")
    short_video = plan.get("short_video_prompt_package")
    if not isinstance(short_video, dict) or not short_video.get("clips"):
        errors.append("short-video clips are missing")
    long_video = plan.get("long_video_prompt_package")
    if not isinstance(long_video, dict) or not long_video.get("shots"):
        errors.append("long-video shots are missing")
    audio = plan.get("audio_prompt")
    if not isinstance(audio, dict) or not audio.get("music_direction"):
        errors.append("audio/music direction is missing")
    evidence = plan.get("source_evidence")
    if not isinstance(evidence, list):
        errors.append("source_evidence is missing")
    return errors


def build_all_prompts(
    database: str | Path,
    document_id: int,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the existing character/visual/continuity layers and export every scene plan."""
    database = Path(database)
    output_dir = Path(output_dir) if output_dir is not None else database.parent / f"{database.stem}_prompts"
    output_dir.mkdir(parents=True, exist_ok=True)

    stages = {
        "candidate_gate": build_candidate_gate(database, document_id),
        "identity_normalization": build_identity_normalizer(database, document_id),
        "canonical_characters": build_canonical_characters(database, document_id),
        "canonical_visual_bible": build_visual_bible(database, document_id),
        "continuity": build_continuity_state(database, document_id),
    }

    scenes = _scene_rows(database, document_id)
    plans: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    jsonl_path = output_dir / "scene_prompts.jsonl"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for scene in scenes:
            plan = build_generation_plan(database, document_id, int(scene["id"]))
            errors = validate_plan(plan)
            record = {
                "scene_id": int(scene["id"]),
                "story_id": int(scene["story_id"]),
                "scene_order": int(scene["scene_order"]),
                "title": scene["title"],
                "page_start": int(scene["page_start"]),
                "page_end": int(scene["page_end"]),
                "qa_status": "pass" if not errors else "fail",
                "qa_errors": errors,
                "plan": plan,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            plans.append(record)
            if errors:
                failures.append({"scene_id": record["scene_id"], "errors": errors})

    package = {
        "schema_version": 1,
        "document_id": document_id,
        "source_database": str(database),
        "scene_count": len(plans),
        "qa_passed": not failures,
        "qa_failures": failures,
        "stages": stages,
        "scenes": plans,
    }
    package_path = output_dir / "all_prompts.json"
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "document_id": document_id,
        "scene_count": len(plans),
        "qa_passed": not failures,
        "qa_failures": len(failures),
        "output_dir": str(output_dir),
        "package": str(package_path),
        "jsonl": str(jsonl_path),
        "stages": stages,
    }
    (output_dir / "prompt_export_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and QA all source-grounded media prompts for a processed PDF")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    result = build_all_prompts(args.database, args.document_id, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["qa_passed"] else 2)


if __name__ == "__main__":
    main()
