from __future__ import annotations

import argparse
import json
import re
from typing import Any


_QUOTE_RE = re.compile(r'["“](.*?)["”]', re.S)
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')
_SPEECH_CUE_RE = re.compile(
    r'\b(said|asked|replied|answered|exclaimed|cried|shouted|whispered|remarked|called|murmured|observed|added)\b',
    re.I,
)
_ACTION_RE = re.compile(
    r'\b(approach(?:ed|es|ing)?|arriv(?:ed|es|ing)|ask(?:ed|s|ing)?|answer(?:ed|s|ing)?|'
    r'climb(?:ed|s|ing)?|come|cross(?:ed|es|ing)?|cry|cried|enter(?:ed|s|ing)?|'
    r'exclaim(?:ed|s|ing)?|fall(?:en|ing|s)?|flee(?:d|s|ing)?|follow(?:ed|s|ing)?|'
    r'go(?:es|ing)?|grab(?:bed|s|bing)?|look(?:ed|s|ing)?|move(?:d|s|ing)?|'
    r'open(?:ed|s|ing)?|reach(?:ed|es|ing)?|return(?:ed|s|ing)?|run(?:s|ning)?|'
    r'saw|see(?:s|ing)?|sit(?:s|ting)?|stand(?:s|ing)?|start(?:ed|s|ing)?|'
    r'stop(?:ped|s|ping)?|take|took|tell(?:s|ing)?|turn(?:ed|s|ing)?|'
    r'walk(?:ed|s|ing)?|watch(?:ed|es|ing)?|whisper(?:ed|s|ing)?|'
    r'shake|shook|hold|held|carry|carried|fight|fought|strike|struck|save(?:d|s|ing)?)\b',
    re.I,
)
_METADATA_PREFIX_RE = re.compile(r'^(?:[A-Z][A-Z0-9\s,:;!?\'’\-]{7,})\.\s+')

_EMOTION_PATTERNS = {
    "urgency": re.compile(r'\b(hurry|quick|quickly|urgent|rush|hast|danger|dangerous|escape|flee|alarm|warn|warning|go)\b', re.I),
    "fear": re.compile(r'\b(afraid|fear|fright|terrified|terror|dread|trembl|horror|panic|death)\b', re.I),
    "grief": re.compile(r'\b(grief|griev|sorrow|sad|sadness|mourn|tears|wept|crying|lament|poor)\b', re.I),
    "anger": re.compile(r'\b(angry|anger|rage|furious|fury|threat|threaten|excited)\b', re.I),
    "joy": re.compile(r'\b(joy|glad|happy|laugh|smile|delight|cheer|pleased)\b', re.I),
    "calm": re.compile(r'\b(calm|quiet|peace|peaceful|rest|resting|still|serene|gentle)\b', re.I),
    "awe": re.compile(r'\b(awe|wonder|wondrous|magnificent|immense|astonish|marvel|spectacular)\b', re.I),
}


def _clean(text: Any, limit: int = 240) -> str:
    value = re.sub(r'\s+', ' ', str(text or '')).strip()
    return value[:limit].rstrip() if len(value) > limit else value


def _strip_metadata_prefix(text: str) -> str:
    value = _clean(text, 600)
    previous = None
    while value and value != previous:
        previous = value
        value = _METADATA_PREFIX_RE.sub('', value).strip()
    return value


def _strip_dialogue(text: str) -> str:
    """Remove clearly quoted dialogue before selecting visual/action prose."""
    return re.sub(r'["“].*?["”]', ' ', text, flags=re.S)


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
    text = str(scene.get("text") or "")
    sentences = []
    for raw in _SENTENCE_RE.split(re.sub(r'\s+', ' ', text).strip()):
        value = _strip_metadata_prefix(raw)
        if value:
            sentences.append(value)
    return sentences


def _dialogue(scene: dict[str, Any]) -> list[str]:
    text = str(scene.get("text") or "")
    candidates: list[tuple[int, str]] = []
    for match in _QUOTE_RE.finditer(text):
        value = _clean(match.group(1), 180).strip("'’“” ")
        if not value:
            continue
        words = value.split()
        score = min(len(value), 120)
        before = text[max(0, match.start() - 100):match.start()]
        after = text[match.end():match.end() + 100]
        if _SPEECH_CUE_RE.search(before) or _SPEECH_CUE_RE.search(after):
            score += 60
        if len(value) < 24:
            score -= 45
        if len(words) < 4:
            score -= 25
        if value.lower().rstrip(" ,.!?") in {"thanks", "well", "yes", "no", "thanks from my heart"}:
            score -= 60
        candidates.append((score, value))
    candidates.sort(key=lambda item: (-item[0], item[1].lower()))
    return _unique([value for _, value in candidates if len(value.split()) >= 4], 3)


def _action_candidates(scene: dict[str, Any], events: list[dict[str, Any]]) -> list[str]:
    candidates: list[tuple[int, str]] = []

    for event in events:
        value = _strip_metadata_prefix(_clean(event.get("text"), 220))
        if value:
            score = 45 + (25 if _ACTION_RE.search(value) else 0)
            candidates.append((score, value))

    # Select narrative prose, not dialogue. This prevents quoted speech from becoming
    # the image's "action" while retaining visible narrator-described actions/reactions.
    narrative = _strip_dialogue(str(scene.get("text") or ""))
    for raw in _SENTENCE_RE.split(re.sub(r'\s+', ' ', narrative).strip()):
        sentence = _strip_metadata_prefix(raw)
        if len(sentence) < 25:
            continue
        if sentence.startswith(('"', '“', "'") ):
            continue
        if _SPEECH_CUE_RE.search(sentence) and not _ACTION_RE.search(sentence):
            continue
        score = 20
        if _ACTION_RE.search(sentence):
            score += 50
        if 6 <= len(sentence.split()) <= 35:
            score += 10
        if sentence.endswith(':'):
            score -= 20
        candidates.append((score, sentence))

    candidates.sort(key=lambda item: (-item[0], item[1].lower()))
    return _unique([value for _, value in candidates], 5)


def _character_lines(characters: list[dict[str, Any]]) -> list[str]:
    result = []
    for character in characters:
        name = _clean(character.get("canonical_name"), 100)
        if not name:
            continue
        facts = _visual_facts(character)
        status = str(character.get("status") or "").lower()
        if facts:
            result.append(name + " (" + "; ".join(facts) + ")")
        elif status in {"confirmed", "likely"}:
            result.append(name)
    return _unique(result, 8)


def _environment(objects: list[dict[str, Any]], continuity: dict[str, Any]) -> list[str]:
    result = [_clean(o.get("canonical_name"), 100) for o in objects if o.get("canonical_name")]
    state = continuity.get("environment_state") if continuity.get("available") else {}
    if isinstance(state, dict):
        for key, value in state.items():
            if isinstance(value, str) and value.strip():
                result.append(f"{key}: {value}")
    return _unique(result, 8)


def _emotion_cues(dialogue: list[str], actions: list[str]) -> list[str]:
    source = " ".join(dialogue + actions)
    return [name for name, pattern in _EMOTION_PATTERNS.items() if pattern.search(source)][:3]


def _base_visual_prompt(
    characters: list[dict[str, Any]],
    objects: list[dict[str, Any]],
    actions: list[str],
    continuity: dict[str, Any],
) -> str:
    character_lines = _character_lines(characters)
    environment = _environment(objects, continuity)
    parts = []
    if character_lines:
        parts.append("Subjects: " + ", ".join(character_lines) + ".")
    if actions:
        parts.append("Source-grounded visual moments: " + "; ".join(actions[:3]) + ".")
    if environment:
        parts.append("Source-supported setting/objects: " + ", ".join(environment) + ".")
    parts.append(
        "Ultra-realistic cinematic 3D live-action hero frame, photoreal human proportions, "
        "physically plausible materials and lighting, crisp facial and environmental detail, "
        "strong depth, clear subject separation, natural composition, thumbnail-attention framing."
    )
    parts.append(
        "Reserve clean negative space for a dialogue box when needed. Preserve canonical identity "
        "and continuity; use only supplied source facts and leave unknown appearance or story details unknown."
    )
    return " ".join(parts)


def _clip_prompt(index: int, total: int, base: str, action: str, dialogue: str | None, role: str) -> dict[str, Any]:
    prompt = (
        f"Clip {index} of {total}, {role}. {base} Focus on this source-grounded moment: {action}. "
        "Use one readable primary action, restrained cinematic camera movement, natural pacing, "
        "and a clear visual handoff into the next clip. Do not add new story events."
    )
    if dialogue:
        prompt += f' Spoken dialogue source: "{dialogue}". Preserve the wording; do not invent dialogue.'
    return {
        "clip_number": index,
        "duration_seconds": 5,
        "role": role,
        "prompt": prompt,
        "dialogue": dialogue,
    }


def _shot_roles(count: int) -> list[str]:
    roles = [
        "establish the source setting",
        "show the principal subject",
        "focus on the source action",
        "capture dialogue or reaction",
        "show a relevant visual detail",
        "close on the established moment",
        "hold continuity",
        "final reaction/detail",
    ]
    return [roles[i % len(roles)] for i in range(count)]


def compile_media_prompts(context: dict[str, Any], clip_count: int = 3) -> dict[str, Any]:
    scene = context.get("scene") or {}
    characters = context.get("characters") or []
    objects = context.get("objects") or []
    events = context.get("events") or []
    continuity = context.get("continuity") or {}
    constraints = context.get("generation_constraints") or []

    dialogue = _dialogue(scene)
    actions = _action_candidates(scene, events)
    emotion_cues = _emotion_cues(dialogue, actions)
    base = _base_visual_prompt(characters, objects, actions, continuity)

    count = max(1, min(int(clip_count), 8))
    if not actions:
        actions = ["Maintain the established source scene state without adding an event."]
    roles = _shot_roles(count)
    clips = []
    for i in range(count):
        action = actions[i % len(actions)]
        line = dialogue[i] if i < len(dialogue) else None
        clips.append(_clip_prompt(i + 1, count, base, action, line, roles[i]))

    music_direction = [
        "Use restrained cinematic instrumental music that supports the source-derived emotional cues without changing the story."
    ]
    if emotion_cues:
        music_direction.append("Source-derived emotional cues: " + ", ".join(emotion_cues) + ".")
    music_direction.append("Use only source-compatible environmental/action sound; do not invent voices, events, or off-screen actions.")

    long_count = min(8, max(4, len(actions) + 2))
    long_roles = _shot_roles(long_count)
    long_shots = []
    for i in range(long_count):
        action = actions[i % len(actions)]
        dialogue_line = dialogue[i] if i < len(dialogue) else None
        prompt = (
            f"{base} Shot {i + 1}: {long_roles[i]}. Source-grounded focus: {action}. "
            "Keep character identity, established environment, object state, lighting logic, and spatial continuity consistent. "
            "Do not invent unsupported appearance, dialogue, events, or progression."
        )
        if dialogue_line:
            prompt += f' Dialogue source for this shot: "{dialogue_line}".'
        long_shots.append({
            "shot_number": i + 1,
            "purpose": long_roles[i],
            "prompt": prompt,
        })

    overlay = [
        {
            "text": line,
            "purpose": "key source dialogue only",
            "placement": "safe dialogue-box area, away from faces and primary action",
        }
        for line in dialogue
    ]

    return {
        "schema_version": 3,
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
                "music_direction": music_direction,
                "dialogue_source": dialogue,
                "sound_design": "Use only source-compatible environmental and action sounds; do not invent events.",
            },
        },
        "long_video": {
            "shots": long_shots,
            "audio": {
                "music_direction": music_direction,
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
