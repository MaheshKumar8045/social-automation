from __future__ import annotations

import re
from typing import Any


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_ACTION_RE = re.compile(
    r"\b(?:approach\w*|arriv\w*|attack\w*|battle\w*|capture\w*|climb\w*|"
    r"come|cross\w*|cry\w*|die\w*|enter\w*|fall\w*|flee\w*|follow\w*|"
    r"fight\w*|grab\w*|hold\w*|kill\w*|look\w*|move\w*|open\w*|"
    r"reach\w*|return\w*|run\w*|save\w*|sit\w*|stand\w*|take\w*|"
    r"turn\w*|walk\w*|watch\w*|travel\w*|strike\w*|destroy\w*|"
    r"burn\w*|collapse\w*|kneel\w*|rise\w*|speak\w*)\b", re.I
)
_DESTRUCTION_RE = re.compile(r"\b(?:ruin\w*|destroy\w*|destruction|ashes|embers|burnt|burned|fire|smoke|collapse\w*|wreck\w*|dead|dying|death)\b", re.I)
_COMBAT_RE = re.compile(r"\b(?:battle|fight\w*|attack\w*|strike\w*|weapon|sword|kill\w*|capture\w*)\b", re.I)
_TRAVEL_RE = re.compile(r"\b(?:walk\w*|run\w*|travel\w*|arriv\w*|leave\w*|cross\w*|journey)\b", re.I)
_REACTION_RE = re.compile(r"\b(?:fear|afraid|frightened|angry|furious|grief|sad|wept|cried|shocked|astonished|surprised|regret\w*)\b", re.I)


def _clean(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip() if len(text) > limit else text


def _sentences(source: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", source or "").strip()
    return [_clean(s) for s in _SENTENCE_RE.split(normalized) if len(s.split()) >= 4]


def _complete(text: str, source: str) -> str:
    value = _clean(text)
    if not value:
        return ""
    if value[-1:] in ".!?":
        return value
    if value in source:
        start = source.find(value)
        tail = source[start + len(value):]
        match = re.search(r"[.!?]", tail)
        if match:
            return _clean(source[start:start + len(value) + match.end()])
    return value


def _candidate_moments(scene: dict[str, Any], events: list[dict[str, Any]], characters: list[dict[str, Any]]) -> list[str]:
    source = str(scene.get("text") or "")
    names = [str(c.get("canonical_name") or "").casefold() for c in characters]
    candidates: list[tuple[int, str]] = []
    for event in events:
        text = _complete(str(event.get("text") or ""), source)
        if not text or text not in source:
            continue
        score = 50
        if _ACTION_RE.search(text): score += 30
        if _DESTRUCTION_RE.search(text): score += 15
        if _COMBAT_RE.search(text): score += 10
        if _REACTION_RE.search(text): score += 7
        score += sum(12 for name in names if name and name in text.casefold())
        candidates.append((score, text))
    for sentence in _sentences(source):
        score = 12
        if _ACTION_RE.search(sentence): score += 45
        if _DESTRUCTION_RE.search(sentence): score += 15
        if _COMBAT_RE.search(sentence): score += 10
        if _TRAVEL_RE.search(sentence): score += 8
        if _REACTION_RE.search(sentence): score += 7
        score += sum(10 for name in names if name and name in sentence.casefold())
        candidates.append((score, sentence))
    result: list[str] = []
    seen: set[str] = set()
    for _, text in sorted(candidates, key=lambda x: (-x[0], x[1].casefold())):
        key = text.casefold()
        if key not in seen and text in source:
            seen.add(key)
            result.append(text)
    return result[:6]


def _presence(characters: list[dict[str, Any]], events: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[str]]:
    visible: list[dict[str, str]] = []
    referenced: list[str] = []
    event_texts = [_clean(e.get("text")) for e in events if _clean(e.get("text"))]
    for character in characters:
        name = _clean(character.get("canonical_name"), 100)
        if not name:
            continue
        contexts = []
        for mention in character.get("scene_mentions") or []:
            context = _clean(mention.get("context"), 320)
            if re.search(rf"\b{re.escape(name)}\b", context, re.I):
                contexts.append(context)
        matching = [e for e in event_texts if re.search(rf"\b{re.escape(name)}\b", e, re.I)]
        physical = next((e for e in matching if _ACTION_RE.search(e)), None)
        if physical is None:
            physical = next((c for c in contexts if _ACTION_RE.search(c)), None)
        if physical:
            visible.append({"name": name, "evidence": physical})
        elif contexts or matching:
            referenced.append(name)
    return visible[:8], list(dict.fromkeys(referenced))[:10]


def _dialogue_kind(source: str, dialogue: list[str]) -> str:
    if not dialogue:
        return "none"
    speech = re.search(r"\b(?:said|asked|replied|answered|exclaimed|cried|shouted|whispered|remarked|called|murmured|told)\b", source, re.I)
    return "spoken" if speech else "first_person_narration"


def build_generation_intent(*, scene: dict[str, Any], characters: list[dict[str, Any]], objects: list[dict[str, Any]], events: list[dict[str, Any]], continuity: dict[str, Any], dialogue: list[str], genre: str) -> dict[str, Any]:
    source = str(scene.get("text") or "")
    moments = _candidate_moments(scene, events, characters)
    if not moments:
        moments = [_clean(source, 360)] if _clean(source) else ["Preserve the established source scene state without adding an event."]
    visible, referenced = _presence(characters, events)
    destruction = bool(_DESTRUCTION_RE.search(source))
    combat = bool(_COMBAT_RE.search(source))
    travel = bool(_TRAVEL_RE.search(source))
    reaction = bool(_REACTION_RE.search(source))
    if combat:
        arc = ["establish", "action", "reaction"]
    elif destruction:
        arc = ["establish", "consequence", "detail"]
    elif travel:
        arc = ["establish", "movement", "destination"]
    elif reaction:
        arc = ["establish", "reaction", "close"]
    else:
        arc = ["establish", "develop", "close"]
    source_kind = _dialogue_kind(source, dialogue)
    return {
        "schema_version": 1,
        "source_grounded": True,
        "story_purpose": "source-derived scene depiction",
        "primary_visual_moment": moments[0],
        "secondary_visual_moments": moments[1:4],
        "visual_moment_candidates": moments,
        "visible_characters": visible,
        "referenced_characters": referenced,
        "unknown_characters": [],
        "environment": [_clean(o.get("canonical_name"), 100) for o in objects if o.get("canonical_name")][:10],
        "action": moments[0],
        "emotional_signal": "combat" if combat else "destruction" if destruction else "travel" if travel else "reaction" if reaction else "neutral",
        "dialogue": dialogue[:3],
        "dialogue_kind": source_kind,
        "cinematic_arc": arc,
        "continuity": continuity if isinstance(continuity, dict) else {},
        "genre": genre,
        "constraints": [
            "Source evidence controls what exists.",
            "Referenced names do not become visible characters without physical evidence.",
            "Unknown source attributes remain unknown.",
            "Cinematic choices control how established content is photographed, staged, paced, and heard; they do not create new story events.",
        ],
    }
