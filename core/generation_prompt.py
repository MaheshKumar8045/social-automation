from __future__ import annotations

import re
from typing import Any


_VISUAL_HINTS = re.compile(
    r"\b(lay|stood|sat|walked|ran|watched|looked|rested|river|lake|sea|mountain|hill|forest|tree|willow|rock|waterfall|mist|cloud|sky|shore|bank|valley|plain|desert|road|house|camp|boat|horse|fire|clothing|wearing|carrying|holding|face|hair|beard)\b",
    re.IGNORECASE,
)


def _clean(value: Any, limit: int = 220) -> str:
    return " ".join(str(value or "").split())[:limit]


def _sentences(text: str) -> list[str]:
    text = _clean(text, 6000)
    return [s.strip(" -—") for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _is_metadata(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in (
        "meridiana;",
        "the adventures of three englishmen and three russians",
        "chapter ",
        "scene ",
    ))


def _strip_exposition(sentence: str) -> str:
    """Remove obvious explanatory tails while preserving visual source facts."""
    # The sample's river sentence continues into alternate names and historical
    # comparison. Those clauses are not useful to an image model.
    cut_markers = (
        " this river,",
        " this stream,",
        " may well vie",
        " is one of",
        " is considered",
        " was known as",
        " is called",
        " are called",
    )
    lowered = sentence.lower()
    positions = [lowered.find(marker) for marker in cut_markers if lowered.find(marker) > 0]
    if positions:
        sentence = sentence[:min(positions)]
    return sentence.strip(" ,.;:")


def _source_visual_phrases(scene_text: str, max_phrases: int = 4) -> list[str]:
    """Extract compact source phrases instead of copying whole sentences."""
    candidates = []
    for sentence in _sentences(scene_text):
        if _is_metadata(sentence) or len(sentence.split()) <= 3:
            continue
        cleaned = _strip_exposition(sentence)
        if cleaned and _VISUAL_HINTS.search(cleaned):
            candidates.append(cleaned)

    if not candidates:
        candidates = [s for s in _sentences(scene_text) if not _is_metadata(s) and len(s.split()) > 3]

    return candidates[:max_phrases]


def _value(fact: dict[str, Any]) -> str:
    attribute = _clean(fact.get("attribute"), 80)
    value = _clean(fact.get("value"), 140)
    if attribute and value:
        return f"{attribute}: {value}"
    return value


def build_visual_scene_spec(plan: dict[str, Any]) -> dict[str, Any]:
    """Build a conservative visual scene specification from source evidence."""
    scene = plan.get("scene") or {}
    scene_text = scene.get("text") or ""
    source_text_lower = str(scene_text).lower()

    characters: list[dict[str, Any]] = []
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
        "source_visual_text": _source_visual_phrases(scene_text),
        "characters": characters,
        "objects": objects,
        "unknowns": list(plan.get("unknowns") or []),
    }


def _compact_source_text(phrases: list[str], max_chars: int = 260) -> str:
    """Condense common narrative wording into image-friendly source language."""
    text = " ".join(phrases)
    replacements = (
        ("lay stretched at the foot of", "resting beneath"),
        ("at the foot of", "beside"),
        ("watching most attentively the waters of", "watching the waters of"),
        ("watching most attentively", "watching"),
        ("at the same time", ""),
        ("chatting, and", "chatting while"),
    )
    for old, new in replacements:
        text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
    text = " ".join(text.split())
    return text[:max_chars].strip(" ,.;:")


def _trim_words(text: str, max_words: int) -> str:
    return " ".join(text.split()[:max_words])


def build_image_prompt(plan: dict[str, Any], max_chars: int = 420) -> str:
    """Compile a compact image prompt from source-grounded visual evidence."""
    spec = build_visual_scene_spec(plan)
    parts: list[str] = []

    source_text = _compact_source_text(spec["source_visual_text"], 280)
    if source_text:
        parts.append(source_text)

    # Structured facts supplement the prose; they never replace it.
    for character in spec["characters"]:
        facts = character["visual_facts"]
        if facts:
            parts.append(f"{character['name']}, " + ", ".join(facts))

    if spec["objects"]:
        parts.append("Objects: " + ", ".join(spec["objects"][:3]))

    parts.append("cinematic historical realism, natural composition")
    prompt = _trim_words(". ".join(parts), 55)
    return prompt[:max_chars].rstrip(" ,.;:")
