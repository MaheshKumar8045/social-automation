from __future__ import annotations

import re
from typing import Any


def _clean(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _sentences(text: str) -> list[str]:
    text = _clean(text, 4000)
    if not text:
        return []
    return [s.strip(" -—") for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _is_metadata(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "meridiana;",
        "the adventures of three englishmen and three russians",
        "chapter ",
        "scene ",
    )
    return any(marker in lowered for marker in markers)


def _source_visual_sentences(scene_text: str, max_sentences: int = 3) -> list[str]:
    """Select meaningful prose from the scene while dropping document metadata."""
    selected: list[str] = []
    for sentence in _sentences(scene_text):
        if _is_metadata(sentence):
            continue
        if len(sentence.split()) <= 3:
            continue
        selected.append(sentence)
        if len(selected) >= max_sentences:
            break
    return selected


def _value(fact: dict[str, Any]) -> str:
    attribute = _clean(fact.get("attribute"), 80)
    value = _clean(fact.get("value"), 140)
    if attribute and value:
        return f"{attribute}: {value}"
    return value


def build_visual_scene_spec(plan: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic visual scene specification from source evidence.

    Missing visual information stays unknown instead of being invented.
    """
    scene = plan.get("scene") or {}
    scene_text = scene.get("text") or ""
    source_sentences = _source_visual_sentences(scene_text)

    characters: list[dict[str, Any]] = []
    source_text_lower = str(scene_text).lower()
    for character in (plan.get("characters") or [])[:4]:
        name = _clean(character.get("canonical_name"), 60)
        if not name or name.lower() not in source_text_lower:
            continue
        facts = [_value(f) for f in (character.get("visual_facts") or [])]
        characters.append({"name": name, "visual_facts": [f for f in facts if f][:3]})

    objects: list[str] = []
    for obj in (plan.get("objects") or [])[:6]:
        name = _clean(obj.get("canonical_name"), 60)
        if name and name.lower() in source_text_lower:
            objects.append(name)

    return {
        "source_visual_text": source_sentences,
        "characters": characters,
        "objects": objects,
        "unknowns": list(plan.get("unknowns") or []),
    }


def _trim_words(text: str, max_words: int) -> str:
    return " ".join(text.split()[:max_words])


def build_image_prompt(plan: dict[str, Any], max_chars: int = 420) -> str:
    """Compile a short image prompt from source-grounded visual evidence."""
    spec = build_visual_scene_spec(plan)
    parts: list[str] = []

    parts.extend(spec["source_visual_text"])

    for character in spec["characters"]:
        facts = character["visual_facts"]
        if facts:
            parts.append(f"{character['name']}, " + ", ".join(facts))

    if spec["objects"]:
        parts.append("Objects: " + ", ".join(spec["objects"][:3]))

    parts.append("cinematic historical realism, natural composition")
    prompt = ". ".join(parts)

    # SD 1.5 uses a legacy 77-token CLIP encoder. Keep this conservative.
    prompt = _trim_words(prompt, 55)
    return prompt[:max_chars].rstrip(" ,.;:")
