from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from .canonical_visual_bible import build as build_visual_bible
from .character_candidate_gate import build as build_candidate_gate
from .character_canonicalizer import build as build_canonical_characters
from .character_evidence_classifier import CharacterEvidenceClassifier
from .character_identity_evidence import build as build_identity_evidence
from .character_identity_normalizer import build as build_identity_normalizer
from .continuity_state import build_continuity_state
from .generation_planner import build_generation_plan
from .mention_identity_resolution import build as build_mention_identity_resolution
from .visual_knowledge_bible import VisualKnowledgeBible


def _scene_rows(database: str | Path, document_id: int) -> list[dict[str, Any]]:
    with sqlite3.connect(database) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(
            """SELECT id, story_id, scene_order, title, page_start, page_end
               FROM scenes WHERE document_id=? ORDER BY story_id, scene_order""",
            (document_id,),
        ).fetchall()]


def _nonempty_text(value: Any, *, minimum: int = 1) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _positive_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def validate_plan(plan: dict[str, Any]) -> list[str]:
    """Validate the canonical generation-plan/media-package contract.

    Validation follows the emitted schema rather than requiring a second,
    subtly different representation in tests. It accepts equivalent canonical
    representations where a derived field can be safely recovered, while still
    rejecting genuinely incomplete production packages.
    """
    errors: list[str] = []
    if plan.get("plan_status") != "ready":
        errors.append("plan_status is not ready")
    if plan.get("source_grounded") is not True:
        errors.append("source_grounded must be true")
    if plan.get("unknowns_must_remain_unknown") is not True:
        errors.append("unknowns_must_remain_unknown must be true")

    image_prompt = plan.get("image_prompt")
    if not _nonempty_text(image_prompt, minimum=240):
        errors.append("image prompt is missing or too short for production use")
    elif "source-grounded" not in image_prompt.lower():
        errors.append("image prompt is missing an explicit source-grounding constraint")
    if image_prompt and "9:16" not in image_prompt:
        errors.append("image prompt is missing the primary 9:16 mobile layout")
    if image_prompt and not any(token in image_prompt.lower() for token in ("dialogue", "narrative box", "dialogue-or-narrative")):
        errors.append("image prompt is missing the required dialogue-or-narrative box instruction")

    characters = plan.get("characters")
    if not isinstance(characters, list):
        errors.append("characters must be a list")
        characters = []

    for idx, character in enumerate(characters, 1):
        if not isinstance(character, dict):
            errors.append(f"character {idx} is invalid")
            continue
        profile = character.get("visual_profile")
        if not isinstance(profile, dict):
            errors.append(f"character {idx} is missing visual_profile")
            continue
        if not profile.get("identity_anchor"):
            errors.append(f"character {idx} is missing a stable identity_anchor")
        if "source_facts" not in profile or "inferred_facts" not in profile:
            errors.append(f"character {idx} visual_profile is missing provenance-separated facts")

    media = plan.get("media_prompt_package")
    if not isinstance(media, dict):
        errors.append("unified media_prompt_package is missing")
        media = {}
    else:
        if media.get("source_grounded") is not True:
            errors.append("unified media package is not source-grounded")

    image = _mapping(media.get("image"))
    if not image:
        errors.append("unified media image package is missing")
    else:
        layout = _mapping(image.get("layout"))
        if not layout:
            errors.append("image layout package is missing")
        else:
            if layout.get("aspect_ratio") != "9:16":
                errors.append("primary image aspect ratio must be 9:16")
            minimum_boxes = _positive_int(
                layout.get("dialogue_box_count_minimum", layout.get("dialogue_box_min_count"))
            )
            overlays = image.get("dialogue_overlays")
            overlay_count = len(overlays) if isinstance(overlays, list) else 0
            if max(minimum_boxes, overlay_count) < 1:
                errors.append("image requires at least one dialogue-or-narrative box")
            if not isinstance(overlays, list) or not overlays:
                errors.append("image dialogue/narrative overlay is missing")

    short_video = _mapping(plan.get("short_video_prompt_package"))
    if not short_video:
        errors.append("short-video prompt package is missing")
    else:
        clips = short_video.get("clips")
        if not isinstance(clips, list) or not clips:
            errors.append("short-video clips are missing")
        else:
            if short_video.get("clip_count") != len(clips):
                errors.append("short-video clip_count does not match clips")
            for index, clip in enumerate(clips, 1):
                if not isinstance(clip, dict) or not _nonempty_text(clip.get("prompt"), minimum=160):
                    errors.append(f"short-video clip {index} prompt is missing or too short")
                elif clip.get("clip_number") != index:
                    errors.append(f"short-video clip {index} has an invalid clip_number")

    long_video = _mapping(plan.get("long_video_prompt_package"))
    if not long_video:
        errors.append("long-video prompt package is missing")
    else:
        shots = long_video.get("shots")
        if not isinstance(shots, list) or not shots:
            errors.append("long-video shots are missing")
        else:
            for index, shot in enumerate(shots, 1):
                if not isinstance(shot, dict) or not _nonempty_text(shot.get("prompt"), minimum=160):
                    errors.append(f"long-video shot {index} prompt is missing or too short")
                elif shot.get("shot_number") != index:
                    errors.append(f"long-video shot {index} has an invalid shot_number")

    audio = _mapping(plan.get("audio_prompt"))
    if not audio:
        errors.append("audio prompt package is missing")
    else:
        music = audio.get("music_direction")
        if not isinstance(music, list) or not any(_nonempty_text(x, minimum=20) for x in music):
            errors.append("audio/music direction is missing or too short")
        if not _nonempty_text(audio.get("sound_design"), minimum=20):
            errors.append("audio sound-design direction is missing or too short")

    visual_inference = media.get("visual_inference")
    if not isinstance(visual_inference, dict):
        visual_inference = _mapping(image.get("visual_inference"))
    if not visual_inference:
        errors.append("visual inference package is missing")

    for key in ("image", "short_video", "long_video"):
        if not isinstance(media.get(key), dict):
            errors.append(f"unified media {key.replace('_', '-')} package is missing")

    evidence = plan.get("source_evidence")
    if not isinstance(evidence, list):
        errors.append("source_evidence is missing")

    if characters and _nonempty_text(image_prompt):
        lowered_prompt = image_prompt.lower()
        names = [
            str(c.get("canonical_name") or "").strip().lower()
            for c in characters if isinstance(c, dict) and c.get("canonical_name")
        ]
        if names and not any(name in lowered_prompt for name in names):
            errors.append("image prompt does not contain any canonical character from the generation plan")
    return errors


def build_all_prompts(database: str | Path, document_id: int, output_dir: str | Path | None = None) -> dict[str, Any]:
    database = Path(database)
    output_dir = Path(output_dir) if output_dir is not None else database.parent / f"{database.stem}_prompts"
    output_dir.mkdir(parents=True, exist_ok=True)

    stages: dict[str, Any] = {}
    stages["candidate_gate"] = build_candidate_gate(database, document_id)
    stages["character_evidence"] = CharacterEvidenceClassifier(database).build(document_id)
    stages["identity_normalization"] = build_identity_normalizer(database, document_id)
    stages["identity_evidence"] = build_identity_evidence(database, document_id)
    stages["mention_identity_resolution"] = build_mention_identity_resolution(database, document_id)
    stages["canonical_characters"] = build_canonical_characters(database, document_id)
    stages["visual_knowledge_bible"] = VisualKnowledgeBible(database).build(document_id)
    stages["canonical_visual_bible"] = build_visual_bible(database, document_id)
    stages["continuity"] = build_continuity_state(database, document_id)

    scenes = _scene_rows(database, document_id)
    plans, failures = [], []
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

    failure_counts = Counter(error for item in failures for error in item["errors"])
    package = {
        "schema_version": 2,
        "document_id": document_id,
        "source_database": str(database),
        "scene_count": len(plans),
        "qa_passed": not failures,
        "qa_failures": failures,
        "qa_failure_counts": failure_counts.most_common(),
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
        "qa_failure_counts": failure_counts.most_common(),
        "output_dir": str(output_dir),
        "package": str(package_path),
        "jsonl": str(jsonl_path),
        "stages": stages,
    }
    (output_dir / "prompt_export_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and QA all source-grounded media prompts")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    result = build_all_prompts(args.database, args.document_id, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["qa_passed"] else 2)


if __name__ == "__main__":
    main()
