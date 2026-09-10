from __future__ import annotations

import argparse
import json
import re
from typing import Any


_QUOTE_RE = re.compile(r'(["“”\u201c\u201d])(.*?)(["”\u201d])', re.S)
_SPEECH_CUE_RE = re.compile(
    r'\b(said|asked|replied|answered|exclaimed|cried|shouted|whispered|remarked|called|murmured|observed|added)\b',
    re.I,
)
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')


def _clean(text: Any, limit: int = 240) -> str:
    value = re.sub(r'\s+', ' ', str(text or '')).strip()
    return value[:limit].rstrip() if len(value) > limit else value


def _unique(values: list[str], limit: int = 8) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = _clean(value, 180)
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
        if len(result) >= limit:
            break
    return result


def _visual_facts(character: dict[str, Any]) -> list[str]:
    facts: list[str] = []
    for fact in character.get("visual_facts", []):
        status = str(fact.get("status") or "").lower()
        value = _clean(fact.get("value"), 120)
        attribute = _clean(fact.get("attribute"), 80)
        if not value or status in {"unknown", "rejected", "conflict"}:
            continue
        facts.append(f"{attribute}: {value}" if attribute else value)
    return _unique(facts, 10)


def _source_sentences(scene: dict[str, Any]) -> list[str]:
    text = _clean(scene.get("text"), 6000)
    return [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]


def _dialogue(scene: dict[str, Any]) -> list[str]:
    text = str(scene.get("text") or "")
    matches = []
    for match in _QUOTE_RE.finditer(text):
        value = _clean(match.group(2), 180)
        if value:
            matches.append(value)
    return _unique(matches, 5)


def _action_sentences(scene: dict[str, Any], events: list[dict[str, Any]]) -> list[str]:
    actions = [_clean(e.get("text"), 220) for e in events if e.get("text")]
    if actions:
        return _unique(actions, 5)
    sentences = _source_sentences(scene)
    return _unique(sentences[:5], 5)


def _character_lines(characters: list[dict[str, Any]]) -> list[str]:
    result = []
    for character in characters:
        name = _clean(character.get("canonical_name"), 100)
        if not name:
            continue
        facts = _visual_facts(character)
        result.append(name + (" (" + "; ".join(facts) + ")" if facts else ""))
    return _unique(result, 8)


def _environment(objects: list[dict[str, Any]], continuity: dict[str, Any]) -> list[str]:
    result = [_clean(o.get("canonical_name"), 100) for o in objects if o.get("canonical_name")]
    state = continuity.get("environment_state") if continuity.get("available") else {}
    if isinstance(state, dict):
        for key, value in state.items():
            if isinstance(value, str) and value.strip():
                result.append(f"{key}: {value}")
    return _unique(result, 8)


def _base_visual_prompt(
    scene: dict[str, Any],
    characters: list[dict[str, Any]],
    objects: list[dict[str, Any]],
    events: list[dict[str, Any]],
    continuity: dict[str, Any],
) -> str:
    title = _clean(scene.get("title"), 140)
    character_lines = _character_lines(characters)
    actions = _action_sentences(scene, events)
    environment = _environment(objects, continuity)
    parts = []
    if title:
        parts.append(f"Scene: {title}.")
    if character_lines:
        parts.append("Characters: " + ", ".join(character_lines) + ".")
    if actions:
        parts.append("Action: " + "; ".join(actions) + ".")
    if environment:
        parts.append("Environment/objects: " + ", ".join(environment) + ".")
    parts.append(
        "Ultra-realistic cinematic 3D live-action visual, detailed natural materials, "
        "physically plausible lighting, realistic human proportions, strong composition, "
        "high visual clarity, thumbnail-attention framing."
    )
    parts.append(
        "Use only supplied source facts; preserve identity and continuity; do not invent "
        "unprovided appearance, clothing, age, location details, props, or events."
    )
    return " ".join(parts)


def _clip_prompt(index: int, total: int, base: str, action: str, dialogue: str | None) -> dict[str, Any]:
    prompt = (
        f"Clip {index} of {total}. {base} Focus on this moment: {action}. "
        "Use natural camera motion, readable subject action, temporal continuity with adjacent clips, "
        "and a visually clear beginning and ending."
    )
    if dialogue:
        prompt += f' Spoken dialogue source: "{dialogue}". Preserve the wording; do not invent dialogue.'
    return {
        "clip_number": index,
        "duration_seconds": 5,
        "prompt": prompt,
        "dialogue": dialogue,
    }


def compile_media_prompts(context: dict[str, Any], clip_count: int = 3) -> dict[str, Any]:
    scene = context.get("scene") or {}
    characters = context.get("characters") or []
    objects = context.get("objects") or []
    events = context.get("events") or []
    continuity = context.get("continuity") or {}
    constraints = context.get("generation_constraints") or []

    dialogue = _dialogue(scene)
    actions = _action_sentences(scene, events)
    base = _base_visual_prompt(scene, characters, objects, events, continuity)

    count = max(1, min(int(clip_count), 8))
    if not actions:
        actions = ["Maintain the source scene state and establish the moment clearly."]
    clips = []
    for i in range(count):
        action = actions[i % len(actions)]
        line = dialogue[i] if i < len(dialogue) else None
        clips.append(_clip_prompt(i + 1, count, base, action, line))

    music_cues = []
    if dialogue:
        music_cues.append("Shape the musical mood around the supplied dialogue and its dramatic context; do not invent narrative facts.")
    if actions:
        music_cues.append("Support the supplied action with restrained cinematic pacing and transitions.")
    music_cues.append("Use source-compatible instrumental music and environmental sound; avoid unsupported voices or events.")

    long_shots = []
    shot_actions = actions[:8]
    for i, action in enumerate(shot_actions, 1):
        long_shots.append({
            "shot_number": i,
            "purpose": "source-grounded scene progression",
            "prompt": f"{base} Establish shot {i}: {action}. Preserve continuity from the preceding shot and leave unknown attributes unspecified.",
        })

    overlay = [
        {
            "text": line,
            "purpose": "key dialogue/story information only",
            "placement": "safe dialogue-box area with unobstructed faces and action",
        }
        for line in dialogue
    ]

    return {
        "schema_version": 1,
        "source_grounded": True,
        "unknowns_must_remain_unknown": True,
        "image": {
            "prompt": base,
            "dialogue_overlays": overlay,
            "dialogue_rendering_note": "Render dialogue as a separate deterministic overlay; do not require the image model to draw readable text.",
        },
        "short_video": {
            "clip_count": count,
            "clips": clips,
            "audio": {
                "music_direction": music_cues,
                "dialogue_source": dialogue,
                "sound_design": "Use only source-compatible environmental and action sounds; do not invent events.",
            },
        },
        "long_video": {
            "shots": long_shots,
            "audio": {
                "music_direction": music_cues,
                "dialogue_source": dialogue,
                "sound_design": "Maintain continuity across shots and use only source-compatible environmental/action sound.",
            },
        },
        "constraints": constraints,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile source-grounded image, short-video, and long-video prompts")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("scene_id", type=int)
    parser.add_argument("--clips", type=int, default=3)
    args = parser.parse_args()

    from .generation_context import get_generation_context

    context = get_generation_context(args.database, args.document_id, args.scene_id)
    if context.get("error"):
        print(json.dumps({"status": "unavailable", "reason": context["error"]}, indent=2))
        return
    print(json.dumps(compile_media_prompts(context, args.clips), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
