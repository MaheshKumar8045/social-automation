from __future__ import annotations

import argparse
import json
import shutil
import os
import tempfile
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .character_candidate_gate import physical_presence_count
from .cinematic_generation import enhance_generation_package
from .media_prompt_compiler import compile_media_prompts
from .visual_continuity import character_identity_block, fixed_style_block
from .visual_generation_policy import enrich_character, load_visual_policy
from .prompt_export import _write_scene_media_files, validate_plan
from .generation_intent import infer_narrative_focus_character


def _prepare_characters(characters: list[Any], events: list[Any] | None = None) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    event_contexts = [
        str(event.get("text") or "")
        for event in (events or [])
        if isinstance(event, dict) and event.get("text")
    ]
    for raw in characters:
        if not isinstance(raw, dict) or not raw.get("canonical_name"):
            continue
        character = dict(raw)
        contexts = [
            str(m.get("context") or "")
            for m in character.get("scene_mentions") or []
            if isinstance(m, dict) and m.get("context")
        ]
        count = physical_presence_count(
            str(character.get("canonical_name")),
            contexts + event_contexts,
        )
        # Recompute this scene-local signal on every refresh. Never trust a stale
        # derived presence flag from an older package revision.
        character["source_presence"] = {
            "physical_presence": count > 0,
            "physical_presence_evidence_count": count,
            "classification": "physical" if count > 0 else "reference_only",
        }
        prepared.append(character)
    return prepared


def refresh_plan(
    plan: dict[str, Any],
    *,
    narrative_focus_character: dict[str, str] | None = None,
) -> dict[str, Any]:
    scene = plan.get("scene") or {}
    characters = _prepare_characters(
        plan.get("characters") or [],
        plan.get("events") or [],
    )
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
        "narrative_focus_character": narrative_focus_character,
    }
    media = compile_media_prompts(context, clip_count=3)
    policy = context.get("visual_generation_policy") or load_visual_policy()
    enriched_characters = [
        enrich_character(
            c,
            genre=context["visual_genre"],
            policy=policy,
            world_context=context["world_profile"],
        )
        for c in characters
    ]
    media = enhance_generation_package(
        scene=scene,
        characters=enriched_characters,
        objects=context["objects"],
        events=context["events"],
        continuity=context["continuity"],
        world_profile=context["world_profile"],
        genre=context["visual_genre"],
        media=media,
        narrative_focus_character=narrative_focus_character,
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


def refresh_package(package_path: Path, output_dir: Path | None = None, *, apply: bool = False) -> dict[str, Any]:
    if not package_path.is_file():
        raise FileNotFoundError(f"Generation package not found: {package_path}")
    package = json.loads(package_path.read_text(encoding="utf-8"))
    scenes = package.get("scenes")
    if not isinstance(scenes, list):
        raise ValueError("all_prompts.json has no scenes list")

    if output_dir is None:
        output_dir = package_path.parent / "_visual_continuity_refresh"
    output_dir.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, Any]] = []
    refreshed: list[dict[str, Any]] = []
    character_refs: dict[str, dict[str, Any]] = {}
    active_narrative_focus: dict[str, str] | None = None
    previous_scene_order: int | None = None

    for record in scenes:
        if not isinstance(record, dict) or not isinstance(record.get("plan"), dict):
            failures.append({"scene_id": record.get("scene_id") if isinstance(record, dict) else None, "errors": ["invalid scene record"]})
            continue
        original_plan = record["plan"]
        scene = original_plan.get("scene") or {}
        scene_order = scene.get("scene_order")
        characters_for_focus = original_plan.get("characters") or []
        source_text = str(scene.get("text") or "")
        local_focus = infer_narrative_focus_character(source_text, characters_for_focus)
        current_focus = local_focus
        if (
            current_focus is None
            and active_narrative_focus is not None
            and previous_scene_order is not None
            and isinstance(scene_order, int)
            and scene_order == previous_scene_order + 1
            and re.search(r"\b(?:I|me|my|mine|we|us|our|ours)\b", source_text, re.I)
        ):
            current_focus = dict(active_narrative_focus)
            current_focus["reason"] = (
                "carried deterministic first-person narrative focus from the immediately preceding scene"
            )

        plan = refresh_plan(original_plan, narrative_focus_character=current_focus)
        if current_focus is not None:
            plan["narrative_focus_character"] = current_focus
        errors = validate_plan(plan)
        active_narrative_focus = current_focus
        previous_scene_order = scene_order if isinstance(scene_order, int) else previous_scene_order
        for character in plan.get("characters") or []:
            if not isinstance(character, dict):
                continue
            presence = character.get("source_presence") or {}
            if presence.get("physical_presence") is not True:
                continue
            key = str(character.get("canonical_character_id") or character.get("canonical_name") or "")
            if not key:
                continue
            if key not in character_refs:
                profile = character.get("visual_profile") or {}
                character_refs[key] = {
                    "canonical_character_id": character.get("canonical_character_id"),
                    "canonical_name": character.get("canonical_name"),
                    "identity_anchor": profile.get("identity_anchor"),
                    "reference_required_for_strong_cross_scene_identity": not bool(profile.get("source_facts")),
                    "identity_prompt": (
                        "Create a neutral production character reference sheet for the canonical character. "
                        "Use the locked identity below, neutral studio lighting, plain uncluttered background, "
                        "front / three-quarter / side / back views plus a face close-up. Do not add scene props, "
                        "story action, text, or dramatic lighting. "
                        + character_identity_block(character)
                    ),
                }
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

    if apply and not failures:
        backup_path = package_path.with_name(package_path.stem + ".pre_visual_continuity.json")
        if not backup_path.exists():
            shutil.copy2(package_path, backup_path)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(package_path.parent),
            prefix=package_path.stem + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(new_package, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
            temp_name = handle.name
        os.replace(temp_name, package_path)
    summary = {
        "scene_count": len(refreshed),
        "qa_passed": not failures,
        "qa_failures": len(failures),
        "qa_failure_counts": new_package["qa_failure_counts"],
        "output_dir": str(output_dir),
        "model_calls": 0,
        "applied": bool(apply and not failures),
        "source_package_modified": bool(apply and not failures),
    }
    (output_dir / "character_reference_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "art_direction": fixed_style_block(load_visual_policy(), "general_narrative"),
                "characters": list(character_refs.values()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "prompt_refresh_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministically refresh media prompts from an existing all_prompts.json without rerunning LLM scene semantics."
    )
    parser.add_argument("package", help="Path to existing all_prompts.json")
    parser.add_argument("--output-dir", default=None, help="Directory for refreshed media files and QA report. Defaults to a sibling refresh directory.")
    parser.add_argument("--apply", action="store_true", help="Replace the source package only when every scene passes QA. Without this flag the source package is never modified.")
    args = parser.parse_args()
    summary = refresh_package(
        Path(args.package),
        Path(args.output_dir) if args.output_dir else None,
        apply=args.apply,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not summary["qa_passed"]:
        print("QA failed; source package was not modified.", flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
