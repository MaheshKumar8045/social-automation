from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import SceneJob


class PromptPackageError(ValueError):
    pass


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_image_prompt_txt(path: Path) -> SceneJob:
    """Load one exported per-scene image prompt as the authoritative prompt source."""
    text = path.read_text(encoding="utf-8")
    header, separator, remainder = text.partition("=== IMAGE GENERATION PROMPT ===")
    if not separator:
        raise PromptPackageError(
            f"image prompt text file is missing IMAGE GENERATION PROMPT section: {path}"
        )
    prompt_part, separator, remainder = remainder.partition("=== IMAGE LAYOUT ===")
    if not separator:
        raise PromptPackageError(f"image prompt text file is missing IMAGE LAYOUT section: {path}")
    layout_part, separator, overlay_part = remainder.partition("=== DIALOGUE / NARRATIVE OVERLAYS ===")
    if not separator:
        raise PromptPackageError(
            f"image prompt text file is missing DIALOGUE / NARRATIVE OVERLAYS section: {path}"
        )

    def _header_value(name: str) -> str:
        match = re.search(rf"(?m)^{re.escape(name)}:\s*(.+?)\s*$", header)
        return match.group(1).strip() if match else ""

    try:
        scene_id = int(_header_value("SCENE ID"))
        scene_order = int(_header_value("SCENE ORDER"))
    except ValueError as exc:
        raise PromptPackageError(f"image prompt text file has invalid scene id/order: {path}") from exc

    title = _header_value("TITLE")
    # The exported TXT section is the authoritative Google payload. Keep the
    # section marker itself to match the successful manual copy/paste boundary.
    prompt_body = prompt_part.strip()
    if not prompt_body:
        raise PromptPackageError(f"scene {scene_id} text prompt is empty: {path}")
    prompt = "=== IMAGE GENERATION PROMPT ===\n" + prompt_body

    try:
        overlays = json.loads(overlay_part.strip() or "[]")
    except json.JSONDecodeError as exc:
        raise PromptPackageError(
            f"scene {scene_id} has invalid dialogue/narrative overlay JSON: {path}: {exc}"
        ) from exc
    if not isinstance(overlays, list):
        overlays = []

    try:
        layout = json.loads(layout_part.strip() or "{}")
    except json.JSONDecodeError as exc:
        raise PromptPackageError(
            f"scene {scene_id} has invalid image layout JSON: {path}: {exc}"
        ) from exc

    record = {
        "scene_id": scene_id,
        "scene_order": scene_order,
        "title": title,
        "source_prompt_file": str(path),
        "source_prompt_format": "image_scene_txt",
        "plan": {
            "image_prompt": prompt,
            "media_prompt_package": {
                "image": {
                    "prompt": prompt,
                    "dialogue_overlays": overlays,
                    "layout": layout,
                }
            },
        },
    }
    return SceneJob(
        scene_id=scene_id,
        scene_order=scene_order,
        title=title,
        prompt=prompt,
        overlays=[x for x in overlays if isinstance(x, dict)],
        record=record,
    )


def _load_text_jobs(source: Path) -> list[SceneJob]:
    if source.is_file():
        return [_parse_image_prompt_txt(source)]

    files = sorted(source.glob("scene_*.txt"))
    if not files:
        raise PromptPackageError(f"no scene_*.txt image prompts found in: {source}")

    jobs = [_parse_image_prompt_txt(path) for path in files]
    seen: set[int] = set()
    for job in jobs:
        if job.scene_id in seen:
            raise PromptPackageError(f"duplicate scene_id in text prompts: {job.scene_id}")
        seen.add(job.scene_id)
    jobs.sort(key=lambda x: (x.scene_order, x.scene_id))
    return jobs


def load_jobs(path: str | Path) -> list[SceneJob]:
    source = Path(path)
    if not source.exists():
        raise PromptPackageError(f"prompt package does not exist: {source}")
    if source.is_dir() or source.suffix.lower() == ".txt":
        return _load_text_jobs(source)
    try:
        package = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PromptPackageError(f"invalid prompt package JSON: {source}: {exc}") from exc

    scenes = package.get("scenes")
    if not isinstance(scenes, list):
        raise PromptPackageError("prompt package has no scenes list")

    jobs: list[SceneJob] = []
    seen: set[int] = set()
    for record in scenes:
        if not isinstance(record, dict):
            continue
        try:
            scene_id = int(record["scene_id"])
            scene_order = int(record["scene_order"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PromptPackageError(f"scene record has invalid id/order: {record!r}") from exc
        if scene_id in seen:
            raise PromptPackageError(f"duplicate scene_id in prompt package: {scene_id}")
        seen.add(scene_id)

        plan = _mapping(record.get("plan"))
        media = _mapping(plan.get("media_prompt_package"))
        image = _mapping(media.get("image"))
        prompt = str(plan.get("image_prompt") or image.get("prompt") or "").strip()
        if not prompt:
            raise PromptPackageError(f"scene {scene_id} has no image prompt")

        overlays = image.get("dialogue_overlays")
        if not isinstance(overlays, list):
            overlays = plan.get("image_dialogue_overlays")
        if not isinstance(overlays, list):
            overlays = []

        jobs.append(SceneJob(
            scene_id=scene_id,
            scene_order=scene_order,
            title=str(record.get("title") or "").strip(),
            prompt=prompt,
            overlays=[x for x in overlays if isinstance(x, dict)],
            record=record,
        ))

    jobs.sort(key=lambda x: (x.scene_order, x.scene_id))
    return jobs
