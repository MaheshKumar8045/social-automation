from __future__ import annotations

import re
from typing import Any


_QUOTE_RE = re.compile(r'["“](.*?)[“”"]', re.S)
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')
_SPEECH_RE = re.compile(
    r"\b(?:said|asked|replied|answered|exclaimed|cried|shouted|whispered|"
    r"remarked|called|murmured|observed|added|told)\b", re.I
)
_ACTION_RE = re.compile(
    r"\b(?:approach\w*|arriv\w*|attack\w*|battle\w*|capture\w*|climb\w*|"
    r"come|cross\w*|cry\w*|die\w*|enter\w*|fall\w*|flee\w*|follow\w*|"
    r"fight\w*|grab\w*|hold\w*|kill\w*|look\w*|move\w*|open\w*|"
    r"reach\w*|return\w*|run\w*|save\w*|see\w*|sit\w*|stand\w*|"
    r"take\w*|turn\w*|walk\w*|watch\w*|travel\w*|strike\w*|"
    r"destroy\w*|burn\w*|collapse\w*|kneel\w*|rise\w*|speak\w*)\b", re.I
)
_PRESENCE_RE = re.compile(
    r"\b(?:was|were|is|are|stood|sat|lay|remained|waited|rested|"
    r"entered|arrived|appeared|left|returned|looked|watched|"
    r"faced|knelt|rose|walked|ran|fled|followed|held|carried|"
    r"spoke|sang|wept|cried)\b", re.I
)
_DESTRUCTION_RE = re.compile(r"\b(?:ruin|ruined|destroyed|destruction|ashes|ash|embers|burnt|burned|fire|smoke|collapse|collapsed|wreck|wreckage|dead|dying|death)\b", re.I)
_COMBAT_RE = re.compile(r"\b(?:battle|fight|fought|attack|attacked|strike|struck|weapon|sword|kill|killed|capture|captured)\b", re.I)
_TRAVEL_RE = re.compile(r"\b(?:walk|walked|run|ran|travel|travelled|traveled|arrive|arrived|leave|left|cross|crossed|journey)\b", re.I)
_REACTION_RE = re.compile(r"\b(?:fear|afraid|frightened|angry|furious|grief|sad|wept|cried|shocked|astonished|surprised|regret|regretted)\b", re.I)
_DIALOGUE_START_RE = re.compile(
    r"^(?:i|we|my|our|you|your|this|that|it|he|she|they|tomorrow|today|tonight|"
    r"why|how|what|when|where|who|can|could|will|would|shall|should|must|"
    r"let|perhaps|if|there|here)\b",
    re.I,
)
_HEADING_PREFIX_RE = re.compile(r"^\s*(?:[IVXLCDM]+|\d{1,3})[\.)]?\s+", re.I)
_NAME_TOKEN_RE = re.compile(r"^[A-Z][A-Za-z'’-]*$")


def _clean(value: Any, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip() if len(text) > limit else text


def _normalize_for_match(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _strip_scene_heading(text: str, scene: dict[str, Any] | None = None) -> str:
    value = _clean(text, 2000)
    title = _clean((scene or {}).get("title"), 160)
    if title:
        title_norm = _normalize_for_match(title)
        value_norm = _normalize_for_match(value)
        if value_norm.startswith(title_norm):
            value = value[len(value.split(title.split()[-1], 1)[0]) if title.split()[-1] in value else 0 :].strip()
            if value.lower().startswith(title.lower()):
                value = value[len(title):].lstrip(" -:;,.\t")
    value = _HEADING_PREFIX_RE.sub("", value, count=1)
    return value.strip()


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    return [_clean(x, 320) for x in _SENTENCE_RE.split(normalized) if len(x.split()) >= 4]


def _clean_dialogue_candidate(sentence: str, scene: dict[str, Any] | None = None) -> str:
    value = _clean(sentence, 220).strip(" '’“”")
    if not value:
        return ""

    # Remove an OCR-leaked chapter/section heading before considering dialogue.
    value = _HEADING_PREFIX_RE.sub("", value, count=1)
    title = _clean((scene or {}).get("title"), 160)
    if title:
        title_norm = _normalize_for_match(title)
        value_norm = _normalize_for_match(value)
        if value_norm.startswith(title_norm):
            # Preserve the original punctuation while removing the normalized heading prefix.
            match = re.match(r"^\s*" + re.escape(title), value, re.I)
            if match:
                value = value[match.end():].lstrip(" -:;,.\t")

    # Handle OCR such as: "1 The end Ravana Tomorrow is my funeral."
    # Once a dialogue-leading word is reached, discard preceding name/title tokens.
    words = value.split()
    for index, word in enumerate(words):
        token = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", word)
        if index > 0 and _DIALOGUE_START_RE.match(token):
            prefix = words[:index]
            if all(_NAME_TOKEN_RE.match(re.sub(r"[^A-Za-z'’-]", "", item)) for item in prefix if item):
                value = " ".join(words[index:])
            break

    return _clean(value, 220)


def _source_dialogue(scene_text: str, scene: dict[str, Any] | None = None) -> list[str]:
    quoted: list[str] = []
    for match in _QUOTE_RE.finditer(scene_text or ""):
        value = _clean_dialogue_candidate(match.group(1), scene)
        if len(value.split()) >= 3:
            quoted.append(value)
    if quoted:
        return list(dict.fromkeys(quoted))[:3]

    candidates: list[str] = []
    for sentence in _sentences(_strip_scene_heading(scene_text, scene)):
        value = _clean_dialogue_candidate(sentence, scene)
        if not value:
            continue
        # Speech verbs are strong evidence. First-person clauses are only a fallback,
        # and heading/speaker-label fragments are removed before returning the text.
        if _SPEECH_RE.search(value):
            candidates.append(value)
            continue
        if re.search(r"\b(?:I|we|my|our)\b", value, re.I) and len(value.split()) <= 28:
            candidates.append(value)
    return list(dict.fromkeys(candidates))[:2]


def _visual_moments(scene_text: str, events: list[dict[str, Any]], characters: list[dict[str, Any]]) -> list[str]:
    names = [str(c.get("canonical_name") or "").lower() for c in characters]
    candidates: list[tuple[int, str]] = []
    for event in events:
        text = _clean(event.get("text"), 300)
        if not text:
            continue
        score = 50
        if _ACTION_RE.search(text):
            score += 35
        if _DESTRUCTION_RE.search(text):
            score += 10
        if any(name and name in text.lower() for name in names):
            score += 10
        candidates.append((score, text))
    for sentence in _sentences(_strip_scene_heading(scene_text)):
        if _SPEECH_RE.search(sentence) and not _ACTION_RE.search(sentence):
            continue
        score = 10
        if _ACTION_RE.search(sentence):
            score += 50
        if _DESTRUCTION_RE.search(sentence):
            score += 12
        if _COMBAT_RE.search(sentence):
            score += 8
        if _REACTION_RE.search(sentence):
            score += 6
        if any(name and name in sentence.lower() for name in names):
            score += 12
        candidates.append((score, sentence))
    candidates.sort(key=lambda item: (-item[0], item[1].lower()))
    return list(dict.fromkeys(text for _, text in candidates))[:4]


def _character_blocking(scene_text: str, characters: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    visible: list[str] = []
    referenced: list[str] = []
    for character in characters:
        name = _clean(character.get("canonical_name"), 100)
        if not name:
            continue
        local_contexts = []
        for mention in character.get("scene_mentions") or []:
            context = _clean(mention.get("context"), 280)
            if re.search(rf"\b{re.escape(name)}\b", context, re.I):
                local_contexts.append(context)
        local_contexts = list(dict.fromkeys(local_contexts))
        physical_context = next(
            (c for c in local_contexts if _ACTION_RE.search(c) or _PRESENCE_RE.search(c)),
            None,
        )
        if physical_context:
            visible.append(f"{name}: {physical_context}")
        elif local_contexts:
            referenced.append(name)
    return visible[:6], referenced[:8]


def _camera_direction(scene_text: str, moments: list[str], dialogue: list[str], characters: list[dict[str, Any]]) -> dict[str, str]:
    source = " ".join([scene_text or "", *moments]).lower()
    if _DESTRUCTION_RE.search(source):
        shot = "wide establishing shot with a slow controlled push-in toward the primary source moment"
        lens = "cinematic wide-to-medium perspective; preserve readable environment scale"
        lighting = "naturalistic low-key light with atmospheric haze, smoke, embers, and motivated highlights only where source-compatible"
    elif _COMBAT_RE.search(source):
        shot = "dynamic medium-wide action framing with restrained tracking movement"
        lens = "moderate wide/normal perspective with clear spatial separation between subjects"
        lighting = "motivated directional light with grounded contrast and visible environmental depth"
    elif _TRAVEL_RE.search(source):
        shot = "environment-led establishing shot followed by a measured tracking or dolly move"
        lens = "wide perspective that preserves geography and travel direction"
        lighting = "naturalistic scene lighting consistent with the source environment"
    elif dialogue:
        shot = "medium dialogue framing or over-the-shoulder composition held long enough for readable source dialogue"
        lens = "natural perspective with shallow-to-moderate depth of field"
        lighting = "soft motivated key with natural fill and restrained background separation"
    elif characters:
        shot = "medium-wide character composition anchored in the environment"
        lens = "natural perspective with enough depth to preserve location context"
        lighting = "motivated cinematic lighting consistent with the detected world and source moment"
    else:
        shot = "wide environment-led composition with a restrained forward drift"
        lens = "wide perspective prioritizing location readability"
        lighting = "naturalistic motivated lighting"
    camera_height = "eye-level by default; vary only when the source moment or visual purpose supports it"
    if _DESTRUCTION_RE.search(source):
        camera_height = "slightly low camera height to give the ruined environment scale without inventing heroic spectacle"
    return {"framing": shot, "lens": lens, "camera_height": camera_height, "lighting": lighting}


def enhance_generation_package(
    *,
    scene: dict[str, Any],
    characters: list[dict[str, Any]],
    objects: list[dict[str, Any]],
    events: list[dict[str, Any]],
    continuity: dict[str, Any],
    world_profile: dict[str, Any],
    genre: str,
    media: dict[str, Any],
) -> dict[str, Any]:
    text = str(scene.get("text") or "")
    dialogue = _source_dialogue(text, scene)
    moments = _visual_moments(text, events, characters)
    if not moments:
        moments = ["Preserve the established source scene state without adding a new event."]
    visible_blocking, referenced_characters = _character_blocking(text, characters)
    camera = _camera_direction(text, moments, dialogue, visible_blocking)

    world_lines = []
    dims = (world_profile or {}).get("dimensions") or {}
    for key in ("culture", "religious_context", "region", "period"):
        top = (dims.get(key) or {}).get("top") or {}
        if top.get("label"):
            world_lines.append(f"{key.replace('_', ' ')}={top['label']}")

    char_lines = []
    visible_names = {line.split(":", 1)[0] for line in visible_blocking}
    for character in characters:
        name = _clean(character.get("canonical_name"), 90)
        if name not in visible_names:
            continue
        profile = character.get("visual_profile") or {}
        source_facts = profile.get("source_facts") or []
        fact_text = "; ".join(
            f"{_clean(f.get('attribute'),60)}: {_clean(f.get('value'),120)}"
            for f in source_facts[:6]
        )
        char_lines.append(
            f"{name} [identity anchor: {profile.get('identity_anchor','none')}]"
            + (f"; source visual facts: {fact_text}" if fact_text else "; no explicit source visual facts extracted for this scene")
        )

    cinematic = (
        "CINEMATIC DIRECTION (controlled production inference): "
        f"{camera['framing']}; {camera['lens']}; {camera['camera_height']}; {camera['lighting']}. "
        "Use restrained depth of field, physically credible materials, motivated movement, and deliberate visual hierarchy. "
        "Do not introduce unsupported props, costumes, anatomy, architecture, weather, or supernatural effects."
    )
    source_block = "SOURCE-ANCHORED SCENE INTERPRETATION: " + moments[0]
    if len(moments) > 1:
        source_block += " SECONDARY CONTEXT: " + moments[1]
    if visible_blocking:
        source_block += " VISIBLE CHARACTER BLOCKING: " + " | ".join(visible_blocking) + "."
    if referenced_characters:
        source_block += " REFERENCED BUT NOT VISUALLY ESTABLISHED: " + ", ".join(referenced_characters) + ". Do not render these references as visible characters."
    if world_lines:
        source_block += " WORLD CONTEXT FOR PRODUCTION CONSISTENCY ONLY: " + ", ".join(world_lines) + "."

    layout = ((media.get("image") or {}).get("layout") or {})
    image_prompt = (
        f"Create a source-grounded {genre} cinematic image for scene {scene.get('scene_order', '')}: "
        f"{_clean(scene.get('title'), 140)}. {source_block} "
        f"Characters: {' | '.join(char_lines) if char_lines else 'no visible canonical characters are source-confirmed in this scene'}. "
        f"Source-identified objects/environment: {', '.join(_clean(o.get('canonical_name'),80) for o in objects if o.get('canonical_name')) or 'none explicitly identified'}. "
        f"{cinematic} "
        "Preserve every canonical identity anchor and continuity state. Unknown source attributes remain unknown. "
        f"Compose for mobile-first {layout.get('aspect_ratio','9:16')} with a clear foreground/midground/background hierarchy, "
        "one dominant visual moment, readable subject separation, and negative space reserved for the deterministic text overlay. "
        "Do not flatten the scene into a character portrait when the environment is materially part of the source moment."
    )

    overlays = []
    if dialogue:
        for i, line in enumerate(dialogue[:2], 1):
            overlays.append({
                "box_number": i,
                "box_type": "dialogue_box",
                "text": line,
                "text_source": "source_dialogue_or_first_person_source_sentence",
                "required": True,
                "placement": "largest protected negative-space region opposite the primary subject/action",
                "avoid": ["faces", "hands", "important objects", "primary action"],
            })
    else:
        narrative_text = _clean(moments[0], 150)
        overlays.append({
            "box_number": 1,
            "box_type": "narrative_box",
            "text": narrative_text,
            "text_source": "source_visual_moment",
            "required": True,
            "placement": "largest protected negative-space region opposite the primary subject/action",
            "avoid": ["faces", "hands", "important objects", "primary action"],
        })

    short = dict(media.get("short_video") or {})
    old_clips = short.get("clips") or []
    clips = []
    for index, clip in enumerate(old_clips[:8], 1):
        focus = moments[(index - 1) % len(moments)]
        prompt = (
            f"Scene {scene.get('scene_order')}, clip {index}. {source_block} {cinematic} "
            f"Primary visual focus: {focus}. Use the clip purpose '{clip.get('role','scene progression')}' only as production structure, "
            "not as permission to invent an event. Preserve identity, geography, object state, and source dialogue exactly where supplied. "
            "Camera motion is deliberate and restrained; the shot must remain visually legible on a vertical mobile frame."
        )
        if index <= len(dialogue):
            prompt += f' Use source dialogue exactly: "{dialogue[index-1]}".'
        clips.append({**clip, "prompt": prompt, "source_visual_focus": focus})
    short["clips"] = clips
    short["cinematic_direction"] = camera
    short["source_visual_moments"] = moments

    long = dict(media.get("long_video") or {})
    old_shots = long.get("shots") or []
    shots = []
    for index, shot in enumerate(old_shots[:8], 1):
        focus = moments[(index - 1) % len(moments)]
        prompt = (
            f"Scene {scene.get('scene_order')}, shot {index}, {shot.get('purpose','continuity shot')}. "
            f"{source_block} {cinematic} Source-grounded focus: {focus}. "
            "Maintain 180-degree spatial logic unless the source clearly changes orientation, preserve continuity state between shots, "
            "and progress visually without fabricating unsupported story events or character traits."
        )
        if index <= len(dialogue):
            prompt += f' Source dialogue when this shot carries dialogue: "{dialogue[index-1]}".'
        shots.append({**shot, "prompt": prompt, "source_visual_focus": focus})
    long["shots"] = shots
    long["cinematic_direction"] = camera
    long["source_visual_moments"] = moments

    inference = dict(media.get("visual_inference") or {})
    inference["cinematic_scene_intelligence"] = {
        "enabled": True,
        "camera": camera,
        "source_visual_moments": moments,
        "character_blocking": visible_blocking,
        "referenced_characters": referenced_characters,
        "dialogue_candidates": dialogue,
        "rule": "Source evidence controls what exists; referenced names do not become visible characters; cinematic choices control how established content is photographed or staged; unsupported facts remain unknown.",
    }

    return {
        **media,
        "visual_inference": inference,
        "image": {
            **(media.get("image") or {}),
            "prompt": image_prompt,
            "dialogue_overlays": overlays,
            "cinematic_direction": camera,
            "source_visual_moments": moments,
            "character_blocking": visible_blocking,
            "referenced_characters": referenced_characters,
        },
        "short_video": short,
        "long_video": long,
    }
