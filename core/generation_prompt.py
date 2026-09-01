from __future__ import annotations

from typing import Any


def _clean(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _value(fact: dict[str, Any]) -> str:
    category = _clean(fact.get("category"), 80)
    attribute = _clean(fact.get("attribute"), 80)
    value = _clean(fact.get("value"), 140)
    if attribute and value:
        return f"{attribute}: {value}"
    if value:
        return value
    if category:
        return category
    return ""


def build_image_prompt(plan: dict[str, Any], max_chars: int = 420) -> str:
    """Create a compact, deterministic image prompt from structured plan data.

    The planner retains full evidence separately; this function selects only
    high-value visual facts for legacy 77-token CLIP text encoders.
    """
    parts: list[str] = []

    scene = plan.get("scene") or {}
    scene_title = _clean(scene.get("title"), 120)
    scene_summary = _clean(scene.get("summary"), 180)
    if scene_title:
        parts.append(scene_title)
    if scene_summary:
        parts.append(scene_summary)

    for character in (plan.get("characters") or [])[:3]:
        name = _clean(character.get("canonical_name"), 60)
        facts = [_value(f) for f in (character.get("visual_facts") or [])]
        facts = [f for f in facts if f][:4]
        if name:
            parts.append(name + ("; " + ", ".join(facts) if facts else ""))

    for obj in (plan.get("objects") or [])[:4]:
        name = _clean(obj.get("canonical_name"), 60)
        if name:
            parts.append(name)

    for event in (plan.get("events") or [])[:2]:
        text = _clean(event.get("text"), 120)
        if text:
            parts.append(text)

    # Keep the source-grounding constraint compact. Full evidence remains in
    # the plan and database rather than being sent to CLIP.
    parts.append("source-grounded cinematic still, preserve known identity and scene state")
    prompt = ". ".join(parts)
    return prompt[:max_chars]
