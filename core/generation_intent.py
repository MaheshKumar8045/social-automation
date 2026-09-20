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
    """Select visual moments in source order.

    Cinematic salience may annotate moments, but it must never reorder the
    narrative chronology. A high-scoring later event must not displace the
    actual opening moment of a scene.
    """
    source = str(scene.get("text") or "")
    names = [
        str(c.get("canonical_name") or "").strip()
        for c in characters
        if isinstance(c, dict) and c.get("canonical_name")
    ]
    # Some PDF extractors flatten chapter number/title/narrator headings into
    # the first prose sentence, e.g. "1 The end Ravana Tomorrow is my funeral."
    # When a canonical narrator name immediately precedes the first-person prose,
    # remove only that heading prefix for visual-moment extraction.
    moment_source = source
    first_person = re.search(r"\b(?:I|me|my|mine|we|us|our|ours)\b", source, re.I)
    if first_person and names:
        heading_matches = []
        for name in names:
            match = re.search(rf"\b{re.escape(name)}\b", source[:first_person.start()], re.I)
            if match and not re.search(r"[.!?]", source[match.end():first_person.start()]):
                heading_matches.append(match)
        if heading_matches:
            heading = max(heading_matches, key=lambda m: m.end())
            if first_person.start() - heading.end() <= 80:
                moment_source = source[heading.end():].lstrip(" \t:;,-—–")
    source = moment_source
    candidates: list[tuple[int, int, str]] = []
    seen: set[str] = set()

    for order, event in enumerate(events):
        raw = str(event.get("text") or "")
        text = _complete_source_fragment(raw, source)
        if not text or text not in source:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append((source.find(text), order, text))

    sentences = _sentences(source)
    base_order = len(events) + 1
    for offset, sentence in enumerate(sentences):
        key = sentence.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append((source.find(sentence), base_order + offset, sentence))

    if not candidates:
        return [source.strip()] if source.strip() else []

    # Source position is authoritative. Event/keyword salience must never
    # reorder later material ahead of the actual opening of the scene.
    candidates.sort(key=lambda item: (item[0] if item[0] >= 0 else 10**9, item[1]))
    return [text for _, _, text in candidates[:6]]

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

        if has_authoritative_presence:
            if source_presence.get("physical_presence") is True:
                physical = next(
                    (
                        e for e in matching_events
                        if _CHARACTER_PHYSICAL_RE.search(e)
                    ),
                    None,
                )
                if physical is None:
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
                # Never use arbitrary mention context outside the current scene source.
                # Surrounding context may describe later locations or historical events.
                if physical is not None:
                    visible.append({"name": name, "evidence": physical})
                elif matching_events or re.search(rf"\\b{re.escape(name)}\\b", scene_text, re.I):
                    referenced.append(name)
            elif matching_events or any(
                isinstance(m, dict) and _clean(m.get("context"), 320)
                and re.search(rf"\b{re.escape(name)}\b", _clean(m.get("context"), 320), re.I)
                for m in character.get("scene_mentions") or []
            ) or re.search(rf"\b{re.escape(name)}\b", scene_text, re.I):
                referenced.append(name)
            continue

        physical_event = next(
            (e for e in matching_events if _CHARACTER_PHYSICAL_RE.search(e)),
            None,
        )
        source_contexts = []
        for mention in character.get("scene_mentions") or []:
            context = _clean(mention.get("context"), 320)
            if context and context in scene_text and re.search(rf"\b{re.escape(name)}\b", context, re.I):
                source_contexts.append(context)

        def _is_location_description(context: str) -> bool:
            # Names such as Trikota can be canonicalized as characters upstream
            # even when the source sentence is plainly describing a place:
            # "My capital, Trikota..." / "Trikota was ... city" / "Trikota burned".
            # Environmental destruction is not character physical presence.
            return bool(re.search(
                rf"(?:\b(?:capital|city|town|village|kingdom|empire|island|river|mountain|temple|palace|fort|country|province|region|world)\b\s*,\s*\b{re.escape(name)}\b|"
                rf"\b{re.escape(name)}\b\s*,\s*(?:the\s+)?(?:capital|city|town|village|kingdom|empire|island|river|mountain|temple|palace|fort|country|province|region|world)\b|"
                rf"\b{re.escape(name)}\b\s+(?:was|were|is|are)\s+(?:the\s+)?(?:greatest\s+|finest\s+|largest\s+|smallest\s+)?(?:capital|city|town|village|kingdom|empire|island|river|mountain|temple|palace|fort|country|province|region|world)\b|"
                rf"\b{re.escape(name)}\b\s+(?:burned|burnt|burns|burning|was\s+destroyed|were\s+destroyed|is\s+destroyed|was\s+ruined|were\s+ruined)\b)",
                context,
                re.I,
            ))

        physical_context = next(
            (ctx for ctx in source_contexts
             if not _is_location_description(ctx) and _CHARACTER_PHYSICAL_RE.search(ctx)),
            None,
        )
        if physical_event or physical_context:
            visible.append({"name": name, "evidence": physical_event or physical_context or name})
        elif matching_events or source_contexts or re.search(rf"\b{re.escape(name)}\b", scene_text, re.I):
            referenced.append(name)
    return visible[:8], list(dict.fromkeys(referenced))[:10]


def _dialogue_kind(source: str, dialogue: list[str]) -> str:
    if not dialogue:
        return "none"
    speech = re.search(r"\b(?:said|asked|replied|answered|exclaimed|cried|shouted|whispered|remarked|called|murmured|told)\b", source, re.I)
    return "spoken" if speech else "first_person_narration"


def infer_narrative_focus_character(
    scene_text: str,
    characters: list[dict[str, Any]],
    *,
    dialogue_kind: str | None = None,
) -> dict[str, str] | None:
    """Resolve a deterministic first-person narrative focal character.

    This is separate from source-confirmed physical presence. A first-person
    narrator may be visualized as a controlled production focus only when
    exactly one canonical identity is explicitly named in the scene source.
    """
    if dialogue_kind not in (None, "first_person_narration"):
        return None
    source = re.sub(r"\s+", " ", str(scene_text or "")).strip()
    if not re.search(r"\b(?:I|me|my|mine|we|us|our|ours)\b", source, re.I):
        return None
    # A name merely appearing anywhere in first-person prose is not enough:
    # "I remembered Rama" names someone else. We first look for an explicit
    # self-identification, then for the narrator-heading pattern used by the
    # source extraction: a canonical name immediately before the first-person
    # prose (e.g. "Ravana Tomorrow is my funeral."). This must prefer the
    # nearest name to the first first-person anchor so a later referenced
    # character such as Hanuman cannot steal the narrator identity.
    self_identified: list[tuple[int, int, dict[str, str]]] = []
    first_person = re.search(r"\b(?:I|me|my|mine|we|us|our|ours)\b", source, re.I)
    first_person_pos = first_person.start() if first_person else None

    for character in characters:
        if not isinstance(character, dict):
            continue
        name = _clean(character.get("canonical_name"), 120)
        if not name:
            continue
        name_re = re.escape(name)
        name_matches = list(re.finditer(rf"\b{name_re}\b", source, re.I))
        if not name_matches:
            continue

        # Strong explicit identity forms.
        strong_patterns = (
            rf"\b(?:I|me|my|mine|we|us|our|ours)\b(?:(?![.!?]).){{0,60}}\b(?:am|is|was|are|called|named)\b(?:(?![.!?]).){{0,40}}\b{name_re}\b",
            rf"\bI\s*,\s*{name_re}\b",
            rf"\bmy\s+name\s+is\s+{name_re}\b",
        )
        strong_positions = [
            m.start()
            for pattern in strong_patterns
            for m in [re.search(pattern, source, re.I)]
            if m
        ]
        if strong_positions:
            self_identified.append((
                0,
                min(strong_positions),
                {"canonical_name": name, "reason": "first-person narrative with explicit source self-identification"},
            ))
            continue

        # Chapter/scene extraction commonly flattens a narrator heading into
        # the first prose sentence: "Ravana Tomorrow is my funeral." Treat only
        # a name that occurs immediately before the first-person anchor as the
        # narrator. Do not search the whole scene, because later references
        # ("Hanuman did that to us") are not self-identification.
        if first_person_pos is not None:
            preceding = [
                match for match in name_matches
                if match.end() <= first_person_pos
                and not re.search(r"[.!?]", source[match.end():first_person_pos])
            ]
            if preceding:
                nearest = max(preceding, key=lambda m: m.end())
                distance = first_person_pos - nearest.end()
                if distance <= 80:
                    self_identified.append((
                        1,
                        distance,
                        {"canonical_name": name, "reason": "first-person narrative with source narrator heading"},
                    ))

    if self_identified:
        self_identified.sort(key=lambda item: (item[0], item[1], item[2]["canonical_name"].casefold()))
        best_rank = self_identified[0][0]
        best = [item for item in self_identified if item[0] == best_rank]
        if len(best) == 1:
            return best[0][2]
    return None


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
    dialogue_kind = _dialogue_kind(source, dialogue)
    narrative_focus = infer_narrative_focus_character(source, characters, dialogue_kind=dialogue_kind)
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
        "dialogue_kind": dialogue_kind,
        "narrative_focus_character": narrative_focus,
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
            "A first-person narrative focus may be visualized only as an explicitly labeled controlled production inference; it must never be mistaken for source-confirmed physical presence.",
            "When no source-confirmed subject exists and no narrative focus is resolved, the frame must remain environment/object-led rather than inventing a protagonist.",
        ],
    }
