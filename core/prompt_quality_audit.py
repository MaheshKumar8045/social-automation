from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

_COMMON_NON_CHARACTER_NAMES = {
    "who", "what", "when", "where", "which", "why", "this", "that", "these", "those"
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _top_dimension(plan: dict[str, Any], key: str) -> dict[str, Any] | None:
    world = plan.get("world_profile") or {}
    dimensions = world.get("dimensions") or {}
    block = dimensions.get(key) or {}
    top = block.get("top")
    return top if isinstance(top, dict) else None


def _sample_indices(count: int, sample_count: int) -> list[int]:
    if count <= 0 or sample_count <= 0:
        return []
    sample_count = min(sample_count, count)
    if sample_count == 1:
        return [0]
    return sorted({round(i * (count - 1) / (sample_count - 1)) for i in range(sample_count)})


def audit_package(package_path: str | Path, sample_count: int = 8) -> dict[str, Any]:
    path = Path(package_path)
    package = json.loads(path.read_text(encoding="utf-8"))
    scenes = package.get("scenes") or []
    failures = []
    observations: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    sample_indices = set(_sample_indices(len(scenes), max(1, min(sample_count, 32))))

    for index, record in enumerate(scenes):
        plan = record.get("plan") or {}
        media = plan.get("media_prompt_package") or {}
        image_prompt = _text(plan.get("image_prompt"))
        inference = media.get("visual_inference") or plan.get("visual_inference") or {}

        issues: list[str] = []
        if record.get("qa_status") != "pass":
            issues.append("embedded_qa_failure")
        if not plan.get("world_profile"):
            issues.append("missing_world_profile")
        if not _top_dimension(plan, "narrative_type"):
            observations["missing_narrative_type"] += 1
        if not _top_dimension(plan, "culture"):
            observations["missing_culture"] += 1
        if not _top_dimension(plan, "religious_context"):
            observations["missing_religious_context"] += 1
        if not image_prompt:
            issues.append("missing_image_prompt")
        if "PRIMARY SOURCE VISUAL MOMENT:" not in image_prompt:
            issues.append("missing_primary_visual_moment")
        if "DETECTED STORY WORLD" not in image_prompt:
            issues.append("missing_world_context_in_prompt")
        if not isinstance(inference, dict) or inference.get("enabled") is not True:
            issues.append("invalid_visual_inference_package")

        characters = plan.get("characters") or []
        for character in characters:
            name = _text(character.get("canonical_name"))
            profile = character.get("visual_profile") or {}
            if name.lower() in _COMMON_NON_CHARACTER_NAMES:
                issues.append(f"obvious_non_character_name:{name}")
            if profile and not profile.get("identity_anchor"):
                issues.append(f"missing_identity_anchor:{name or '?'}")
            if profile and "source_facts" not in profile:
                issues.append(f"missing_source_facts:{name or '?'}")
            if profile and "inferred_facts" not in profile:
                issues.append(f"missing_inferred_facts:{name or '?'}")

        if issues:
            failures.append({
                "scene_id": record.get("scene_id"),
                "scene_order": record.get("scene_order"),
                "title": record.get("title"),
                "issues": issues,
            })

        if index in sample_indices:
            samples.append({
                "scene_id": record.get("scene_id"),
                "scene_order": record.get("scene_order"),
                "title": record.get("title"),
                "page_start": record.get("page_start"),
                "page_end": record.get("page_end"),
                "narrative_type": _top_dimension(plan, "narrative_type"),
                "culture": _top_dimension(plan, "culture"),
                "religious_context": _top_dimension(plan, "religious_context"),
                "visual_genre": plan.get("visual_inference", {}).get("genre") if isinstance(plan.get("visual_inference"), dict) else None,
                "characters": [
                    {
                        "canonical_name": c.get("canonical_name"),
                        "identity_anchor": (c.get("visual_profile") or {}).get("identity_anchor"),
                        "source_fact_count": len((c.get("visual_profile") or {}).get("source_facts") or []),
                        "inferred_fact_count": len((c.get("visual_profile") or {}).get("inferred_facts") or []),
                    }
                    for c in characters[:8]
                ],
                "image_prompt_preview": image_prompt[:700],
            })

    return {
        "schema_version": 3,
        "package": str(path),
        "scene_count": len(scenes),
        "embedded_qa_passed": package.get("qa_passed") is True,
        "embedded_qa_failures": len(package.get("qa_failures") or []),
        "audit_failed_scenes": len(failures),
        "audit_failure_details": failures,
        "observations": dict(observations),
        "sample_scenes": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit generated scene prompts for world-context and visual-intelligence propagation")
    parser.add_argument("package")
    parser.add_argument("--sample-count", type=int, default=8)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    result = audit_package(args.package, sample_count=max(1, min(args.sample_count, 32)))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered)
    raise SystemExit(2 if result["audit_failed_scenes"] else 0)


if __name__ == "__main__":
    main()
