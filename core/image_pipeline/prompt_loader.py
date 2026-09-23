from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import SceneJob


class PromptPackageError(ValueError):
    pass


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_jobs(path: str | Path) -> list[SceneJob]:
    source = Path(path)
    if not source.exists():
        raise PromptPackageError(f"prompt package does not exist: {source}")
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
