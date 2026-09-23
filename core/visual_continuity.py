from __future__ import annotations

from typing import Any


DEFAULT_ART_DIRECTION: dict[str, Any] = {
    "look": (
        "cinematic live-action realism with natural skin/material response, restrained film grain, "
        "moderate contrast, soft highlight roll-off, grounded depth, and physically credible optics"
    ),
    "palette": (
        "fixed project grade: cool blue-charcoal shadows (#1E2A30), neutral stone-earth midtones (#6B6258), "
        "restrained amber highlights (#B77A45), natural skin tones; scene light may vary only when motivated by source"
    ),
    "lighting": (
        "motivated source light first, consistent key direction within a scene, controlled fill, readable faces and objects; "
        "warm practicals may appear against the fixed neutral/cool base when the source establishes fire, lamps, sunset, or other warm light"
    ),
    "camera": (
        "natural spherical perspective, disciplined 24–50mm lens family, eye-level by default, restrained depth of field, "
        "stable horizon and coherent spatial geography"
    ),
    "continuity": (
        "same production, same visual language, same color science, same material response, same realism level; "
        "change only scene-required action, pose, expression, framing, and source-motivated lighting"
    ),
    "negative": (
        "no style reset, no anime/cartoon treatment, no glossy fantasy redesign, no random costume redesign, "
        "no face morphing, no duplicate subjects, no modern visual language, no watermark or logo"
    ),
    "overlay": {
        "background": "#111318",
        "background_alpha": 220,
        "text": "#F3EEE3",
        "font_family": "Georgia",
        "font_weight": "regular",
        "corner_radius_percent": 1.2,
        "horizontal_padding_percent": 3.0,
        "vertical_padding_percent": 2.2,
        "max_width_percent": 68,
        "max_height_percent": 15,
        "font_size_percent": 3.4,
        "line_spacing_percent": 0.8,
        "placement": "largest protected negative-space region opposite the primary subject/action",
    },
}


def art_direction(policy: dict[str, Any] | None = None, genre: str = "") -> dict[str, Any]:
    """Return one immutable project visual-language block plus genre metadata."""
    policy = policy if isinstance(policy, dict) else {}
    configured = ((policy.get("production") or {}).get("art_direction") or {})
    result = dict(DEFAULT_ART_DIRECTION)
    for key, value in configured.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            merged = dict(result[key])
            merged.update(value)
            result[key] = merged
        else:
            result[key] = value
    result["genre"] = genre or "general_narrative"
    return result


def _clean(value: Any, limit: int = 220) -> str:
    return " ".join(str(value or "").split())[:limit].rstrip()


def _fact_lines(profile: dict[str, Any], *, source_only: bool = False) -> list[str]:
    facts: list[str] = []
    source_facts = profile.get("source_facts") or []
    inferred_facts = [] if source_only else profile.get("inferred_facts") or []
    for fact in list(source_facts) + list(inferred_facts):
        if not isinstance(fact, dict):
            continue
        if not source_only and fact.get("locked_for_continuity") is False:
            continue
        attribute = _clean(fact.get("attribute"), 70)
        value = _clean(fact.get("value"), 160)
        if attribute and value:
            prefix = "SOURCE" if fact in source_facts else "CONTROLLED"
            facts.append(f"{prefix} {attribute}={value}")
    return list(dict.fromkeys(facts))[:12]


def character_identity_block(character: dict[str, Any]) -> str:
    """Build a frozen identity block for a source-established visible character.

    The block never invents missing exact physical traits. If the source does not
    establish appearance, the prompt explicitly defers identity to an approved
    external character reference rather than silently inventing one.
    """
    name = _clean(character.get("canonical_name"), 120)
    profile = character.get("visual_profile") or {}
    anchor = _clean(profile.get("identity_anchor"), 80) or "unassigned"
    role = _clean(profile.get("visual_role"), 60) or "person"
    source_facts = _fact_lines(profile, source_only=True)
    locked_facts = _fact_lines(profile, source_only=False)
    facts = source_facts + [x for x in locked_facts if x not in source_facts]

    parts = [
        f"CANONICAL CHARACTER IDENTITY LOCK: {name}.",
        f"Identity anchor: {anchor}.",
        f"Production role: {role}.",
        "This identity block is immutable across the project: preserve the same face structure, "
        "hair silhouette, body proportions, distinctive marks, and baseline wardrobe whenever those "
        "attributes are established by source evidence or an approved character reference.",
    ]
    if facts:
        parts.append("Locked visual facts: " + "; ".join(facts) + ".")
    else:
        parts.append(
            "Source appearance facts are not established here. Do not invent exact facial, hair, eye, "
            "age, height, or body measurements. Use the project's approved character reference for identity "
            "when available; otherwise keep unspecified attributes neutral rather than redesigning the character."
        )
    parts.append(
        "Scene variables may change only when source evidence requires them: pose, expression, action, "
        "temporary condition, camera, and source-motivated lighting. Crowns, jewelry, armor, weapons, "
        "headgear, makeup, or other accessories are not implied by rank, title, mythology, or genre alone; "
        "they require source evidence or an approved character reference."
    )
    return " ".join(parts)


def subject_policy(intent: dict[str, Any]) -> str:
    visible = intent.get("visible_characters") or []
    participants = intent.get("source_participants") or []
    narrative_focus = intent.get("narrative_focus_character") or {}
    if visible:
        names = ", ".join(str(x.get("name") or "").strip() for x in visible if isinstance(x, dict))
        return (
            f"SUBJECT POLICY: mandatory source-confirmed visible canonical characters: {names or 'none'}. "
            "They are the only canonical render targets. Do not replace, gender-swap, omit, or substitute "
            "a mandatory canonical character with another human or humanoid subject. Source-established "
            "anonymous participants may appear only when required by the visual moment. Referenced-only "
            "canonical names are context, never render targets."
        )
    if narrative_focus:
        name = str(narrative_focus.get("canonical_name") or "").strip()
        return (
            "SUBJECT POLICY: no canonical character is source-confirmed physically visible. "
            f"NARRATIVE FOCAL CHARACTER (CONTROLLED PRODUCTION INFERENCE): {name}. "
            "This focal character may be visualized because the scene is first-person and the narrator "
            "was deterministically resolved; this is not a claim of source-confirmed physical presence. "
            "Do not replace this focal character with another person, woman, man, bystander, or generic portrait. "
            "Do not add other human or humanoid subjects unless the source establishes them."
        )
    if participants:
        labels = ", ".join(str(x.get("label") or "").strip() for x in participants if isinstance(x, dict))
        return (
            f"SUBJECT POLICY: no canonical character is source-confirmed visible. Anonymous source "
            f"participants may appear only if required by the source moment: {labels or 'source-established groups'}. "
            "Do not turn referenced canonical names into characters."
        )
    return (
        "SUBJECT POLICY: this is an environment/object-led frame with no source-confirmed visible canonical "
        "character, narrative focal character, or anonymous participant. Keep the frame free of human or humanoid "
        "subjects; do not add a protagonist, portrait, bystander, crowd, silhouette, or substitute character."
    )


def overlay_contract(style: dict[str, Any]) -> str:
    overlay = style.get("overlay") or DEFAULT_ART_DIRECTION["overlay"]
    return (
        "TEXT / OVERLAY POLICY: TEXT RENDERING IS DISABLED IN THE IMAGE MODEL. "
        "Create clean artwork only. Leave the protected negative-space region empty for post-processing. "
        "Do not draw, spell, simulate, or invent dialogue/caption text. Do not generate words, letters, subtitles, signs, logos, watermarks, or typography. "
        "Do not copy prompt instructions into the artwork. "
        "The exact source text is rendered later by the deterministic overlay renderer using the fixed "
        f"{overlay.get('font_family', 'Georgia')} regular serif, warm-white text "
        f"({overlay.get('text', '#F3EEE3')}) on a near-black translucent panel "
        f"({overlay.get('background', '#111318')}, alpha {overlay.get('background_alpha', 220)}), "
        f"maximum width {overlay.get('max_width_percent', 68)}% and maximum height {overlay.get('max_height_percent', 15)}%. "
        "COMPOSITION CONTRACT: reserve the largest visually quiet negative-space region for this post-processing overlay. "
        "Keep that region low-detail and free of faces, hands, important source objects, and the primary action. "
        "The overlay will be composited after generation; the image model must not render the panel or text itself. "
        "Maintain enough local contrast for the near-black panel and keep the main subject/action outside the protected overlay region."
    )


def fixed_style_block(policy: dict[str, Any] | None = None, genre: str = "") -> str:
    style = art_direction(policy, genre)
    return (
        "GLOBAL CINEMATIC ART DIRECTION (LOCKED FOR EVERY SCENE): "
        f"{style['look']}. {style['palette']}. {style['lighting']}. {style['camera']}. "
        f"{style['continuity']}. {style['negative']}."
    )
