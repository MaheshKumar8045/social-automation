from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .character_candidate_gate import physical_presence_count
from .cinematic_generation import enhance_generation_package
from .media_prompt_compiler import compile_media_prompts
from .prompt_export import _write_scene_media_files, validate_plan


def _prepare_characters(characters: list[Any]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for raw in characters:
        if not isinstance(raw, dict) or not raw.get("canonical_name"):
            continue
        character = dict(raw)
        contexts = [
            str(m.get("context") or "")
            for m in character.get("scene_mentions") or []
            if isinstance(m, dict) and m.get("context")
        ]
        count = physical_presence_count(str(character.get("canonical_name")), contexts)
        existing = character.get("source_presence")
        if not isinstance(existing, dict) or "physical_presence" not in existing:
            character["source_presence"] = {
                "physical_presence": count > 0,
                "physical_presence_evidence_count": count,
                "classification": "physical" if count > 0 else "reference_only",
            }
        prepared.append(character)
    return prepared


def refresh_plan(plan: dict[str, Any]) -> dict[str, Any]:
    scene = plan.get("scene") or {}
    characters = _prepare_characters(plan.get("characters") or [])
    context = {
        "scene": scene,
        "characters": characters,
        "objects": plan.get("objects") or [],
        "events": plan.get("events") or [],
        "continuity": plan.get("continuity") or {},
        "world_profile": plan.get("world_profile") or {},
        "visual_genre": plan.get("visual_genre") or "general_narrative",
        "visual_generation_policy": plan.get("visual_generation_policy") or {},
        "generation_constraints": plan.get("generation_constraints") or [],
    }
    media = compile_media_prompts(context, clip_count=3)
    media = enhance_generation_package(
        scene=scene,
        characters=media.get("_characters") or characters,
        objects=context["objects"],
        events=context["events"],
        continuity=context["continuity"],
        world_profile=context["world_profile"],
        genre=context["visual_genre"],
        media=media,
    )
    plan = dict(plan)
    plan["characters"] = characters
    plan["media_prompt_package"] = media
    plan["image_prompt"] = media["image"]["prompt"]
    plan["image_dialogue_overlays"] = media["image"]["dialogue_overlays"]
    plan["image_layout"] = media["image"]["layout"]
    plan["visual_inference"] = media["visual_inference"]
    plan["short_video_prompt_package"] = media["short_video"]
    plan["long_video_prompt_package"] = media["long_video"]
    plan["audio_prompt"] = media["short_video"]["audio"]
    plan["generation_intent"] = media.get("generation_intent")
    return plan


def refresh_package(package_path: Path, output_dir: Path | None = None) -> dict[str, Any]:
    package = json.loads(package_path.read_text(encoding="utf-8"))
    scenes = package.get("scenes")
    if not isinstance(scenes, list):
        raise ValueError("all_prompts.json has no scenes list")

    if output_dir is None:
        output_dir = package_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, Any]] = []
    refreshed: list[dict[str, Any]] = []

    for record in scenes:
        if not isinstance(record, dict) or not isinstance(record.get("plan"), dict):
            failures.append({"scene_id": record.get("scene_id") if isinstance(record, dict) else None, "errors": ["invalid scene record"]})
            continue
        plan = refresh_plan(record["plan"])
        errors = validate_plan(plan)
        updated_record = dict(record)
        updated_record["plan"] = plan
        updated_record["qa_status"] = "pass" if not errors else "fail"
        updated_record["qa_errors"] = errors
        refreshed.append(updated_record)
        if errors:
            failures.append({"scene_id": updated_record.get("scene_id"), "errors": errors})
        _write_scene_media_files(output_dir, updated_record)

    new_package = dict(package)
    new_package["schema_version"] = max(2, int(package.get("schema_version") or 2))
    new_package["scene_count"] = len(refreshed)
    new_package["scenes"] = refreshed
    new_package["qa_passed"] = not failures
    new_package["qa_failures"] = failures
    new_package["qa_failure_counts"] = Counter(error for item in failures for error in item["errors"]).most_common()
    stages = dict(package.get("stages") or {})
    stages["media_prompt_refresh"] = {
        "deterministic": True,
        "model_calls": 0,
        "reason": "Refresh derived media prompts from existing source-grounded scene plans without rerunning LLM semantics.",
    }
    new_package["stages"] = stages

    package_path.write_text(json.dumps(new_package, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "scene_count": len(refreshed),
        "qa_passed": not failures,
        "qa_failures": len(failures),
        "qa_failure_counts": new_package["qa_failure_counts"],
        "output_dir": str(output_dir),
        "model_calls": 0,
    }
    (output_dir / "prompt_refresh_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministically refresh media prompts from an existing all_prompts.json without rerunning LLM scene semantics."
    )
    parser.add_argument("package", help="Path to existing all_prompts.json")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    summary = refresh_package(Path(args.package), Path(args.output_dir) if args.output_dir else None)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not summary["qa_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
