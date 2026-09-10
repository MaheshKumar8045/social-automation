from __future__ import annotations

import re
from typing import Any

from .media_prompt_compiler import compile_media_prompts


_REALISM_SUFFIX = (
    "photorealistic live-action cinematic still, realistic human proportions, "
    "natural materials and lighting, grounded environmental detail, natural composition"
)


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").split())[:limit]


def _sentences(text: str) -> list[str]:
    text = _clean(text, 10000)
    return [s.strip(" -—") for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def build_visual_scene_spec(plan: dict[str, Any]) -> dict[str, Any]:
    """Return a generic source-grounded visual representation.

    This compatibility helper intentionally contains no book-specific names or
    locations. The canonical media-generation compiler is
    ``core.media_prompt_compiler``; this function exposes a small structured
    representation for older callers without creating a second source of truth.
    """
    scene = plan.get("scene") or {}
    characters = plan.get("characters") or []
    objects = plan.get("objects") or []
    events = plan.get("events") or []
    continuity = plan.get("continuity") or {}

    character_names = [
        _clean(character.get("canonical_name"), 100)
        for character in characters
        if character.get("canonical_name")
    ]
    object_names = [
        _clean(obj.get("canonical_name"), 80)
        for obj in objects
        if obj.get("canonical_name")
    ]
    actions = [
        _clean(event.get("text"), 220)
        for event in events
        if event.get("text")
    ]
    actions = [value for value in actions if value][:5]

    environment: list[str] = []
    state = continuity.get("environment_state") if continuity.get("available") else {}
    if isinstance(state, dict):
        for key, value in state.items():
            if isinstance(value, str) and value.strip():
                environment.append(f"{key}: {_clean(value, 120)}")

    source_sentences = _sentences(scene.get("text") or "")
    return {
        "setting": environment,
        "characters": character_names,
        "actions": actions,
        "environment": environment,
        "objects": object_names[:8],
        "source_excerpt": source_sentences[:3],
        "unknowns": list(plan.get("unknowns") or []),
    }


def _trim(text: str, max_words: int = 55, max_chars: int = 420) -> str:
    text = " ".join(text.split())
    return " ".join(text.split()[:max_words])[:max_chars].rstrip(" ,.;:")


def build_image_prompt(plan: dict[str, Any], max_chars: int = 420) -> str:
    """Compatibility wrapper around the canonical media prompt compiler."""
    media = compile_media_prompts({
        "scene": plan.get("scene") or {},
        "characters": plan.get("characters") or [],
        "objects": plan.get("objects") or [],
        "events": plan.get("events") or [],
        "continuity": plan.get("continuity") or {},
        "generation_constraints": plan.get("generation_constraints") or [],
    })
    prompt = str(media["image"]["prompt"])
    return _trim(prompt, 90, max_chars) if max_chars else prompt
