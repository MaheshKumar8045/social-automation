from __future__ import annotations

import re
from typing import Any

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_ACTION_RE = re.compile(r"\b(?:approach\w*|arriv\w*|attack\w*|battle|capture\w*|climb\w*|come|cross\w*|cry\w*|die\w*|enter\w*|fall\w*|flee\w*|follow\w*|fight\w*|fought|grab\w*|hold\w*|kill\w*|look\w*|move\w*|open\w*|reach\w*|return\w*|run\w*|save\w*|sit\w*|stand\w*|take\w*|turn\w*|walk\w*|watch\w*|travel\w*|strike\w*|destroy\w*|burn\w*|collapse\w*|kneel\w*|rise\w*|speak\w*)\b", re.I)
# This expression is deliberately character-presence-specific. Generic scene words
# such as "battle" or "destroyed" must never establish a named character as visible.
_CHARACTER_PHYSICAL_RE = re.compile(r"\b(?:approach\w*|arriv\w*|attack\w*|capture\w*|climb\w*|come|cross\w*|cry\w*|die\w*|enter\w*|fall\w*|flee\w*|follow\w*|fight\w*|fought|grab\w*|hold\w*|kill\w*|look\w*|move\w*|open\w*|reach\w*|return\w*|run\w*|save\w*|sit\w*|stand\w*|take\w*|turn\w*|walk\w*|watch\w*|travel\w*|strike\w*|kneel\w*|rise\w*|speak\w*|was|were|is|are|stood|sat|lay|remained|waited|rested|entered|arrived|appeared|left|returned|looked|watched|faced|knelt|rose|walked|ran|fled|followed|held|carried|spoke|sang|wept|cried)\b", re.I)
_DESTRUCTION_RE = re.compile(r"\b(?:ruin\w*|destroy\w*|destruction|ashes|embers|burnt|burned|fire|smoke|collapse\w*|wreck\w*|dead|dying|death)\b", re.I)
_COMBAT_RE = re.compile(r"\b(?:battle|fight\w*|fought|attack\w*|strike\w*|weapon|sword|kill\w*|capture\w*)\b", re.I)
_TRAVEL_RE = re.compile(r"\b(?:walk\w*|run\w*|travel\w*|arriv\w*|leave\w*|cross\w*|journey)\b", re.I)
_REACTION_RE = re.compile(r"\b(?:fear|afraid|frightened|angry|furious|grief|sad|wept|cried|shocked|astonished|surprised|regret\w*)\b", re.I)
# Anonymous participants/groups are source-established visual subjects, not canonical identities.
# Keep this allowlist conservative so ordinary nouns do not become invented characters.
_SOURCE_PARTICIPANT_RE = re.compile(r"\b(?:the enemy|the monkey-men|monkey-men|the jackals?|jackals?|the rats?|rats?|the soldiers?|soldiers?|the warriors?|warriors?|the people|my people|the men|the women|the gods|the gods' chosen men|the chosen men)\b", re.I)


def _clean(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip() if len(text) > limit else text


def _sentences(source: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", source or "").strip()
    return [_clean(s) for s in _SENTENCE_RE.split(normalized) if len(s.split()) >= 4]


def _complete_source_fragment(text: str, source: str) -> str:
    value = _clean(text)
    if not value or value[-1:] in ".!?":
        return value
    start = source.find(value)
    if start < 0:
        return ""
    tail = source[start + len(value):]
    match = re.search(r"[.!?]", tail)
    return _clean(source[start:start + len(value) + match.end()]) if match else ""


def _candidate_moments(scene: dict[str, Any], events: list[dict[str, Any]], characters: list[dict[str, Any]]) -> list[str]:
    source = str(scene.get("text") or "")
    # Mention-only characters must not bias visual-moment selection. Only source-confirmed
    # visible canonical identities are allowed to raise a moment's character score.
    names = [
        str(c.get("canonical_name") or "").casefold()
        for c in characters
        if isinstance(c, dict) and (c.get("source_presence") or {}).get("physical_presence") is True
    ]
    event_candidates: list[tuple[int, int, str]] = []
    for order, event in enumerate(events):
        raw = str(event.get("text") or "")
        text = _complete_source_fragment(raw, source)
        if not text or text not in source:
            continue
        score = 50 + (30 if _ACTION_RE.search(text) else 0) + (15 if _DESTRUCTION_RE.search(text) else 0) + (10 if _COMBAT_RE.search(text) else 0) + (7 if _REACTION_RE.search(text) else 0)
        score += sum(12 for name in names if name and name in text.casefold())
        event_candidates.append((score, order, text))
    sentences = _sentences(source)
    # With no trustworthy event extraction, sentence order is the source of truth.
    # Do not rank/reorder prose merely because a keyword scores higher.
    if not event_candidates:
        return sentences[:6] if sentences else ([source.strip()] if source.strip() else [])
    sentence_candidates: list[tuple[int, int, str]] = []
    base_order = len(event_candidates)
    for offset, sentence in enumerate(sentences):
        score = 12 + (45 if _ACTION_RE.search(sentence) else 0) + (15 if _DESTRUCTION_RE.search(sentence) else 0) + (10 if _COMBAT_RE.search(sentence) else 0) + (8 if _TRAVEL_RE.search(sentence) else 0) + (7 if _REACTION_RE.search(sentence) else 0)
        score += sum(10 for name in names if name and name in sentence.casefold())
        sentence_candidates.append((score, base_order + offset, sentence))
    candidates = event_candidates + sentence_candidates
    result: list[str] = []
    seen: set[str] = set()
    for _, _, text in sorted(candidates, key=lambda x: (-x[0], x[1])):
        key = text.casefold()
        if key not in seen and text in source:
            seen.add(key)
            result.append(text)
    return result[:6]


def _source_participants(scene_text: str) -> list[dict[str, str]]:
    """Return only anonymous groups/participants explicitly named by the scene text."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in _sentences(scene_text):
        for match in _SOURCE_PARTICIPANT_RE.finditer(sentence):
            label = _clean(match.group(0), 80)
            key = label.casefold()
            if key in seen:
                continue
            seen.add(key)
            results.append({"label": label, "evidence": sentence})
    return results[:12]


def _presence(scene_text: str, characters: list[dict[str, Any]], events: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[str]]:
    """Only scene-local, character-specific physical evidence can establish visibility.

    source_presence is produced by the deterministic source-evidence gate in
    generation_context. When it says a canonical character is physically present,
    that signal is authoritative. Text matching below is used to recover the
    source evidence fragment, not to override the already-classified presence.
    """
    visible: list[dict[str, str]] = []
    referenced: list[str] = []
    normalized_source = re.sub(r"\s+", " ", scene_text or "").strip()
    event_texts = [_clean(e.get("text")) for e in events if _clean(e.get("text"))]
    for character in characters:
        name = _clean(character.get("canonical_name"), 100)
        if not name:
            continue
        source_presence = character.get("source_presence") or {}
        has_authoritative_presence = isinstance(source_presence, dict) and "physical_presence" in source_presence
        matching_events = [e for e in event_texts if e in scene_text and re.search(rf"\b{re.escape(name)}\b", e, re.I)]
        physical = next((e for e in matching_events if _CHARACTER_PHYSICAL_RE.search(e)), None)
        # Deterministic source physical-presence evidence is authoritative when
        # available. It prevents later prompt logic from re-deriving visibility
        # differently from the canonical generation context.
        if physical is None and source_presence.get("physical_presence") is True:
            physical = next(
                (
                    _clean(m.get("context"), 320)
                    for m in character.get("scene_mentions") or []
                    if isinstance(m, dict)
                    and _clean(m.get("context"), 320)
                    and _clean(m.get("context"), 320) in normalized_source
                    and re.search(rf"\b{re.escape(name)}\b", _clean(m.get("context"), 320), re.I)
                ),
                None,
            )
            if physical is None:
                # The gate already proved physical presence from this scene's
                # canonical mention contexts. Preserve the classification even
                # if OCR/layout whitespace prevents exact substring recovery.
                physical = next(
                    (
                        _clean(m.get("context"), 320)
                        for m in character.get("scene_mentions") or []
                        if isinstance(m, dict)
                        and _clean(m.get("context"), 320)
                        and re.search(rf"\b{re.escape(name)}\b", _clean(m.get("context"), 320), re.I)
                    ),
                    None,
                )
        if physical:
            visible.append({"name": name, "evidence": physical})
            continue
        source_contexts = []
        for mention in character.get("scene_mentions") or []:
            context = _clean(mention.get("context"), 320)
            if context and context in scene_text and re.search(rf"\b{re.escape(name)}\b", context, re.I):
                source_contexts.append(context)
        if has_authoritative_presence:
            # Once the deterministic scene-local gate has supplied a presence
            # classification, do not re-derive visibility with a second heuristic.
            # This keeps validator, prompt compiler, and generation intent aligned.
            if source_contexts or matching_events or re.search(rf"\b{re.escape(name)}\b", scene_text, re.I):
                referenced.append(name)
            continue
        physical_context = next((c for c in source_contexts if _CHARACTER_PHYSICAL_RE.search(c)), None)
        if physical_context:
            visible.append({"name": name, "evidence": physical_context})
        elif matching_events or source_contexts or re.search(rf"\b{re.escape(name)}\b", scene_text, re.I):
            referenced.append(name)
    return visible[:8], list(dict.fromkeys(referenced))[:10]


def _dialogue_kind(source: str, dialogue: list[str]) -> str:
    if not dialogue:
        return "none"
    speech = re.search(r"\b(?:said|asked|replied|answered|exclaimed|cried|shouted|whispered|remarked|called|murmured|told)\b", source, re.I)
    return "spoken" if speech else "first_person_narration"


def _select_arc(signal: str, has_visible: bool, has_dialogue: bool) -> list[str]:
    if signal == "combat":
        return ["establish", "action", "reaction"]
    if signal == "destruction":
        return ["establish", "consequence", "detail"]
    if signal == "travel":
        return ["establish", "movement", "destination"]
    if signal == "reaction":
        return ["establish", "reaction", "close"]
    if has_dialogue and has_visible:
        return ["establish", "develop", "reaction"]
    return ["establish", "develop", "close"]


def build_generation_intent(*, scene: dict[str, Any], characters: list[dict[str, Any]], objects: list[dict[str, Any]], events: list[dict[str, Any]], continuity: dict[str, Any], dialogue: list[str], genre: str) -> dict[str, Any]:
    source = str(scene.get("text") or "")
    moments = _candidate_moments(scene, events, characters)
    if not moments:
        moments = _sentences(source)[:6] if _sentences(source) else ([source.strip()] if source.strip() else ["Preserve the established source scene state without adding an event."])
    visible, referenced = _presence(source, characters, events)
    signal = "combat" if _COMBAT_RE.search(source) else "destruction" if _DESTRUCTION_RE.search(source) else "travel" if _TRAVEL_RE.search(source) else "reaction" if _REACTION_RE.search(source) else "neutral"
    return {
        "schema_version": 2,
        "source_grounded": True,
        "story_purpose": "source-derived scene depiction",
        "primary_visual_moment": moments[0],
        "secondary_visual_moments": moments[1:4],
        "visual_moment_candidates": moments,
        "visible_characters": visible,
        "referenced_characters": referenced,
        "source_participants": _source_participants(source),
        "unknown_characters": [],
        "environment": [_clean(o.get("canonical_name"), 100) for o in objects if o.get("canonical_name")][:10],
        "action": moments[0],
        "emotional_signal": signal,
        "dialogue": dialogue[:3],
        "dialogue_kind": _dialogue_kind(source, dialogue),
        "cinematic_arc": _select_arc(signal, bool(visible), bool(dialogue)),
        "continuity": continuity if isinstance(continuity, dict) else {},
        "genre": genre,
        "constraints": [
            "Source evidence controls what exists.",
            "Referenced names do not become visible canonical characters without physical evidence.",
            "Source-established anonymous participants may be depicted only at the level explicitly supported by the scene text.",
            "Unknown source attributes remain unknown.",
            "Cinematic choices control how established content is photographed, staged, paced, and heard; they do not create new story events.",
            "Every visual focus must be a complete source-grounded sentence or exact source fragment that can be traced to the scene text.",
            "The project visual-language block is immutable; scene lighting may vary only when motivated by source evidence.",
            "Generated artwork must leave typography to the deterministic overlay layer.",
            "When no source-confirmed subject exists, the frame must remain environment/object-led rather than inventing a protagonist.",
        ],
    }
