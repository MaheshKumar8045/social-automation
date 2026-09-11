
from __future__ import annotations

import argparse
import json
import re
from typing import Any

from .visual_generation_policy import composition_policy, enrich_character, load_visual_policy


_QUOTE_RE = re.compile(r'["“](.*?)[“”"]', re.S)
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')
_SPEECH_CUE_RE = re.compile(
    r"\b(said|asked|replied|answered|exclaimed|cried|shouted|whispered|"
    r"remarked|called|murmured|observed|added|told|said to)\b", re.I
)
_ACTION_RE = re.compile(
    r"\b(approach\w*|arriv\w*|ask\w*|answer\w*|climb\w*|come|cross\w*|"
    r"cry|cried|enter\w*|exclaim\w*|fall\w*|flee\w*|follow\w*|go\w*|"
    r"grab\w*|look\w*|move\w*|open\w*|reach\w*|return\w*|run\w*|"
    r"saw|see\w*|sit\w*|stand\w*|start\w*|stop\w*|take|took|tell\w*|"
    r"turn\w*|walk\w*|watch\w*|whisper\w*|shake\w*|hold\w*|held|"
    r"carry\w*|fight|fought|strike|struck|save\w*|captur\w*|die\w*|"
    r"kill\w*|battle\w*|travel\w*|leave\w*|arrive\w*)\b", re.I
)


def _clean(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip() if len(text) > limit else text


def _unique(values: list[str], limit: int = 8) -> list[str]:
    result, seen = [], set()
    for value in values:
        value = _clean(value, 240)
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
        if len(result) >= limit:
            break
    return result


def _strip_dialogue(text: str) -> str:
    return re.sub(r'["“].*?["”]', " ", text, flags=re.S)


def _dialogue(scene: dict[str, Any]) -> list[str]:
    text = str(scene.get("text") or "")
    ranked: list[tuple[int, str]] = []
    for match in _QUOTE_RE.finditer(text):
        value = _clean(match.group(1), 180).strip(" '’“”")
        if len(value.split()) < 4:
            continue
        before = text[max(0, match.start() - 120):match.start()]
        after = text[match.end():match.end() + 100]
        score = min(len(value), 120)
        if _SPEECH_CUE_RE.search(before) or _SPEECH_CUE_RE.search(after):
            score += 80
        ranked.append((score, value))
    ranked.sort(key=lambda x: (-x[0], x[1].lower()))
    return _unique([x[1] for x in ranked], 3)


def _visual_moments(scene: dict[str, Any], events: list[dict[str, Any]], characters: list[dict[str, Any]]) -> list[str]:
    name_tokens = [
        _clean(c.get("canonical_name"), 100).lower()
        for c in characters
        if c.get("canonical_name")
    ]
    candidates: list[tuple[int, str]] = []
    for event in events:
        text = _clean(event.get("text"), 260)
        if not text:
            continue
        score = 50 + (25 if _ACTION_RE.search(text) else 0)
        score += sum(12 for name in name_tokens if name and name in text.lower())
        candidates.append((score, text))

    narrative = _strip_dialogue(str(scene.get("text") or ""))
    for sentence in _SENTENCE_RE.split(re.sub(r"\s+", " ", narrative).strip()):
        sentence = _clean(sentence, 260)
        if len(sentence.split()) < 5:
            continue
        if _SPEECH_CUE_RE.search(sentence) and not _ACTION_RE.search(sentence):
            continue
        score = 10 + (45 if _ACTION_RE.search(sentence) else 0)
        score += sum(10 for name in name_tokens if name and name in sentence.lower())
        if 6 <= len(sentence.split()) <= 32:
            score += 10
        candidates.append((score, sentence))

    candidates.sort(key=lambda x: (-x[0], x[1].lower()))
    return _unique([x[1] for x in candidates], 3)


def _objects(objects: list[dict[str, Any]], continuity: dict[str, Any]) -> list[str]:
    values = [_clean(o.get("canonical_name"), 100) for o in objects if o.get("canonical_name")]
    state = continuity.get("environment_state") if continuity.get("available") else {}
    if isinstance(state, dict):
        values.extend(
            f"{_clean(k, 80)}: {_clean(v, 120)}"
            for k, v in state.items()
            if isinstance(v, str) and v.strip()
        )
    return _unique(values, 8)


def _character_lines(characters: list[dict[str, Any]]) -> list[str]:
    result = []
    for raw in characters:
        character = raw
        name = _clean(character.get("canonical_name"), 100)
        if not name:
            continue
        profile = character.get("visual_profile") or {}
        source_facts = profile.get("source_facts") or []
        inferred = profile.get("inferred_facts") or []
        source_text = "; ".join(
            f"{_clean(f.get('attribute'), 70)}: {_clean(f.get('value'), 120)}"
            for f in source_facts[:8]
        )
        inferred_text = "; ".join(
            _clean(f.get("value"), 140) for f in inferred[:8]
        )
        line = f"{name} [identity anchor: {profile.get('identity_anchor', 'none')}]"
        if source_text:
            line += f" | SOURCE VISUAL FACTS: {source_text}"
        if inferred_text:
            line += f" | CONTROLLED VISUAL INFERENCE: {inferred_text}"
        result.append(line)
    return _unique(result, 8)


def _overlay(dialogue: list[str], scene: dict[str, Any], layout: dict[str, Any]) -> list[dict[str, Any]]:
    if dialogue:
        boxes = [
            {
                "box_number": 1,
                "box_type": "dialogue_box",
                "text": line,
                "text_source": "source_dialogue",
                "required": True,
                "placement": "auto_safe_zone",
                "max_width_percent": layout["dialogue_box_max_width_percent"],
                "max_height_percent": layout["dialogue_box_max_height_percent"],
                "avoid": ["faces", "hands", "important_objects", "primary_action"],
            }
            for line in dialogue[:2]
        ]
    else:
        title = _clean(scene.get("title"), 120) or "Scene"
        boxes = [{
            "box_number": 1,
            "box_type": "narrative_box",
            "text": title,
            "text_source": "source_scene_title",
            "required": True,
            "placement": "auto_safe_zone",
            "max_width_percent": layout["dialogue_box_max_width_percent"],
            "max_height_percent": layout["dialogue_box_max_height_percent"],
            "avoid": ["faces", "hands", "important_objects", "primary_action"],
        }]
    return boxes


def _layout_prompt(layout: dict[str, Any]) -> str:
    return (
        f"Mobile-first vertical composition at {layout['aspect_ratio']} aspect ratio. "
        f"Keep critical subjects inside the central {layout['critical_subject_safe_area_percent']}% safe area "
        f"with approximately {layout['safe_margin_percent']}% outer margins. "
        f"Keep {layout['background_visible_percent'][0]}-{layout['background_visible_percent'][1]}% of the frame "
        "as meaningful environment/background rather than crowding the frame. "
        f"Primary character scale about {layout['main_subject_height_percent'][0]}-"
        f"{layout['main_subject_height_percent'][1]}% of frame height; secondary characters about "
        f"{layout['secondary_subject_height_percent'][0]}-{layout['secondary_subject_height_percent'][1]}%; "
        f"group compositions about {layout['group_subject_height_percent'][0]}-"
        f"{layout['group_subject_height_percent'][1]}%. "
        "Select the strongest empty safe region for text and never cover faces, hands, primary action, "
        "or important source-identified objects."
    )


def _base_prompt(
    scene: dict[str, Any],
    characters: list[dict[str, Any]],
    objects: list[dict[str, Any]],
    moments: list[str],
    continuity: dict[str, Any],
    layout: dict[str, Any],
    inference_genre: str,
) -> str:
    parts = [
        f"Source-grounded {inference_genre} media depiction.",
        f"Scene {scene.get('scene_order', '')}: {_clean(scene.get('title'), 160)}.",
        _layout_prompt(layout),
        "Preserve canonical identity anchors across every scene. "
        "Source-supported visual facts have priority; controlled visual inference is allowed only "
        "for missing production details and must never contradict source evidence.",
    ]
    lines = _character_lines(characters)
    if lines:
        parts.append("CHARACTER VISUAL PROFILES: " + " || ".join(lines) + ".")
    if moments:
        parts.append(
            "PRIMARY SOURCE VISUAL MOMENT: " + moments[0] + "."
        )
        if len(moments) > 1:
            parts.append("SECONDARY SOURCE CONTEXT: " + moments[1] + ".")
    env = _objects(objects, continuity)
    if env:
        parts.append("SOURCE-IDENTIFIED OBJECTS / ENVIRONMENT STATE: " + ", ".join(env) + ".")
    parts.append(
        "Ultra-realistic cinematic live-action presentation, physically credible anatomy and materials, "
        "cinematic depth, readable subject separation, natural lighting consistent with the scene, "
        "no modern elements unless source-supported."
    )
    return " ".join(parts)


def compile_media_prompts(context: dict[str, Any], clip_count: int = 3) -> dict[str, Any]:
    scene = context.get("scene") or {}
    raw_characters = context.get("characters") or []
    policy = context.get("visual_generation_policy") or load_visual_policy()
    genre = context.get("visual_genre") or policy.get("default_genre", "mythological_epic")
    characters = [
        enrich_character(c, genre=genre, policy=policy)
        for c in raw_characters
        if c.get("canonical_name")
    ]
    objects = context.get("objects") or []
    events = context.get("events") or []
    continuity = context.get("continuity") or {}
    layout = composition_policy(policy)

    dialogue = _dialogue(scene)
    moments = _visual_moments(scene, events, characters)
    if not moments:
        moments = ["Hold the established source scene state without adding a new event."]
    base = _base_prompt(scene, characters, objects, moments, continuity, layout, genre)
    overlays = _overlay(dialogue, scene, layout)

    count = max(1, min(int(clip_count), 8))
    roles = [
        "establish the environment",
        "introduce the principal subject",
        "show the primary source action",
        "capture reaction or dialogue",
        "show a relevant source object/detail",
        "close while preserving established continuity",
    ]
    clips = []
    for i in range(count):
        action = moments[i % len(moments)]
        line = dialogue[i] if i < len(dialogue) else None
        text = (
            f"Clip {i+1} of {count}; {roles[i % len(roles)]}. {base} "
            f"Visual focus: {action}. "
            "Use one clear primary action, restrained camera motion, and a clean transition. "
            "Do not add a new story event."
        )
        if line:
            text += f' Source dialogue: "{line}".'
        clips.append({
            "clip_number": i + 1,
            "duration_seconds": 5,
            "role": roles[i % len(roles)],
            "prompt": text,
            "dialogue": line,
        })

    long_count = min(8, max(4, min(6, len(moments) + 3)))
    long_roles = [
        "wide establishing shot",
        "medium character composition",
        "action-focused shot",
        "reaction or dialogue shot",
        "environment/object detail",
        "continuity close",
    ]
    long_shots = []
    for i in range(long_count):
        action = moments[i % len(moments)]
        line = dialogue[i] if i < len(dialogue) else None
        prompt = (
            f"{base} Shot {i+1}: {long_roles[i % len(long_roles)]}. "
            f"Source-grounded focus: {action}. "
            "Maintain identity anchors, subject scale, environment logic, object state, and spatial continuity. "
            "Do not invent unsupported story progression."
        )
        if line:
            prompt += f' Source dialogue: "{line}".'
        long_shots.append({
            "shot_number": i + 1,
            "purpose": long_roles[i % len(long_roles)],
            "prompt": prompt,
        })

    music = ["Use restrained cinematic instrumental music supporting the source-derived emotional tone."]
    if dialogue:
        music.append("Dialogue remains source-derived; preserve wording and pacing.")
    music.append("Sound design may use only source-compatible environmental/action sounds.")

    inference_summary = {
        "enabled": True,
        "genre": genre,
        "rule": "Source facts override inference; inferred values fill missing production details only.",
        "characters": [
            {
                "canonical_character_id": c.get("canonical_character_id"),
                "canonical_name": c.get("canonical_name"),
                "identity_anchor": (c.get("visual_profile") or {}).get("identity_anchor"),
                "visual_role": (c.get("visual_profile") or {}).get("visual_role"),
                "source_fact_count": len((c.get("visual_profile") or {}).get("source_facts") or []),
                "inferred_fact_count": len((c.get("visual_profile") or {}).get("inferred_facts") or []),
                "unknown_source_attributes": (c.get("visual_profile") or {}).get("unknown_source_attributes", []),
            }
            for c in characters
        ],
    }

    return {
        "schema_version": 4,
        "source_grounded": True,
        "unknowns_must_remain_unknown": True,
        "visual_inference": inference_summary,
        "image": {
            "prompt": base + " Include one required dialogue-or-narrative box in a protected safe region.",
            "dialogue_overlays": overlays,
            "layout": {
                **layout,
                "dialogue_box_count_minimum": layout["dialogue_box_min_count"],
                "text_rendering": "Render readable text as a separate deterministic overlay whenever the production system supports it.",
                "placement_algorithm": "Choose the largest safe negative-space region opposite the main subject/action; never overlap faces, hands, important objects, or the primary action.",
            },
        },
        "short_video": {
            "aspect_ratio": layout["aspect_ratio"],
            "orientation": layout["orientation"],
            "clip_count": count,
            "clips": clips,
            "audio": {
                "music_direction": music,
                "dialogue_source": dialogue,
                "sound_design": "Use only source-compatible environmental and action sounds; do not invent events.",
            },
        },
        "long_video": {
            "aspect_ratio": layout["aspect_ratio"],
            "orientation": layout["orientation"],
            "shots": long_shots,
            "audio": {
                "music_direction": music,
                "dialogue_source": dialogue,
                "sound_design": "Maintain continuity across shots and use only source-compatible environmental/action sound.",
            },
        },
        "constraints": list(context.get("generation_constraints") or []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile mobile-first source-grounded media prompts")
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
