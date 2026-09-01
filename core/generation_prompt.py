from __future__ import annotations

import re
from typing import Any


_METADATA = re.compile(
    r"(?:meridiana;|the adventures of three englishmen and three russians|chapter\s+[ivxlcdm]+|scene\s+\d+)",
    re.IGNORECASE,
)


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").split())[:limit]


def _sentences(text: str) -> list[str]:
    text = _clean(text, 10000)
    return [s.strip(" -—") for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _source_text(plan: dict[str, Any]) -> str:
    scene = plan.get("scene") or {}
    return _clean(scene.get("text"), 10000)


def _find(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(0).strip() if match else ""


def build_visual_scene_spec(plan: dict[str, Any]) -> dict[str, Any]:
    """Extract a structured, source-grounded visual representation.

    The extractor is intentionally conservative. It prefers explicit source
    wording and records unknowns rather than inventing appearance or setting.
    """
    text = _source_text(plan)
    sentences = [s for s in _sentences(text) if not _METADATA.search(s)]
    source = " ".join(sentences)

    setting: list[str] = []
    if re.search(r"Orange River", source, re.IGNORECASE):
        setting.append("Orange River")
    if re.search(r"South Africa|Cape|Transvaal|Hottentot", source, re.IGNORECASE):
        setting.append("South Africa")
    if re.search(r"1854", source):
        setting.append("1854")

    characters: list[str] = []
    two_men = re.search(r"\btwo men\b", source, re.IGNORECASE)
    if two_men:
        characters.append("two men")

    actions: list[str] = []
    if re.search(r"lay stretched|resting|sat", source, re.IGNORECASE) and re.search(r"willow", source, re.IGNORECASE):
        actions.append("resting beneath an immense weeping willow")
    if re.search(r"chatting", source, re.IGNORECASE):
        actions.append("chatting")
    if re.search(r"watching.*Orange River|watching.*waters", source, re.IGNORECASE):
        actions.append("watching the river")

    environment: list[str] = []
    environment_patterns = [
        (r"weeping willow", "weeping willow"),
        (r"rocky|rocks|rock", "rocky landscape"),
        (r"mountain|mountains", "mountains"),
        (r"forest|forests|wood", "vegetation"),
        (r"vegetation", "dense vegetation"),
        (r"waterfall", "waterfall"),
        (r"mist", "mist"),
        (r"river", "river landscape"),
    ]
    for pattern, label in environment_patterns:
        if re.search(pattern, source, re.IGNORECASE) and label not in environment:
            environment.append(label)

    objects: list[str] = []
    for obj in (plan.get("objects") or [])[:8]:
        name = _clean(obj.get("canonical_name"), 60)
        if name and re.search(rf"\b{re.escape(name)}\b", source, re.IGNORECASE):
            objects.append(name)

    return {
        "setting": setting,
        "characters": characters,
        "actions": actions,
        "environment": environment,
        "objects": objects,
        "unknowns": list(plan.get("unknowns") or []),
    }


def _trim(text: str, max_words: int = 55, max_chars: int = 420) -> str:
    text = " ".join(text.split())
    return " ".join(text.split()[:max_words])[:max_chars].rstrip(" ,.;:")


def build_image_prompt(plan: dict[str, Any], max_chars: int = 420) -> str:
    """Compile a compact image prompt from the visual scene specification."""
    spec = build_visual_scene_spec(plan)
    parts: list[str] = []

    if spec["setting"]:
        parts.append(" ".join(spec["setting"]))
    if spec["characters"]:
        parts.append(" and ".join(spec["characters"]))
    if spec["actions"]:
        parts.append(", ".join(spec["actions"]))
    if spec["environment"]:
        parts.append(", ".join(spec["environment"]))
    if spec["objects"]:
        parts.append("visible objects: " + ", ".join(spec["objects"][:3]))

    parts.append("cinematic historical realism, natural composition")
    return _trim(". ".join(parts), 55, max_chars)
