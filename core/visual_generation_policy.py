from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "visual_generation_policy.json"

_GENERIC_ROLES = {
    "person": [
        "natural human proportions",
        "credible posture and body language for the narrative role",
    ],
    "warrior": [
        "physically capable posture appropriate to the narrative role",
        "practical period-appropriate equipment only when source context supports it",
    ],
    "ruler": [
        "composed, authoritative presence appropriate to the story world",
        "status-aware clothing only when supported by the source context",
    ],
    "deity": [
        "commanding presence appropriate to the established belief or mythic context",
        "ceremonial or symbolic styling only where source context supports it",
    ],
    "ascetic": [
        "disciplined, restrained presentation appropriate to the narrative role",
    ],
    "elder": [
        "mature, dignified presence without inventing an exact age",
    ],
}

_FALLBACK_POLICY = {
    "schema_version": 2,
    "default_genre": "general_narrative",
    "allow_controlled_inference": True,
    "inference_rules": {
        "only_fill_missing_attributes": True,
        "never_override_source_facts": True,
        "never_infer_exact_identity_traits": [
            "eye_color",
            "hair_color",
            "height",
            "exact_age",
            "facial_measurements"
        ],
        "lock_inferred_profile_for_continuity": True
    },
    "image_layout": {
        "primary": {
            "aspect_ratio": "9:16",
            "orientation": "vertical",
            "mobile_first": True,
            "safe_margin_percent": 7,
            "critical_subject_safe_area_percent": 86,
            "background_visible_percent": [35, 55],
            "main_subject_height_percent": [45, 65],
            "secondary_subject_height_percent": [25, 50],
            "group_subject_height_percent": [30, 55],
            "dialogue_box_max_width_percent": 68,
            "dialogue_box_max_height_percent": 15,
            "dialogue_box_min_count": 1
        }
    },
    "genre_priors": {
        "general_narrative": {
            "baseline": [
                "cinematic presentation appropriate to the supplied story world",
                "physically plausible anatomy, materials, lighting, and environment",
                "do not introduce culture-, religion-, period-, or country-specific details unless source context supports them"
            ],
            "roles": _GENERIC_ROLES,
        },
        "mythology": {
            "baseline": [
                "cinematic mythic presentation appropriate to the source's identified cultural and religious context",
                "period-appropriate materials and garments only when supported by the world context",
                "no modern objects, architecture, typography, or technology unless source-supported"
            ],
            "roles": _GENERIC_ROLES,
        },
        "historical": {
            "baseline": [
                "historically appropriate visual presentation using the detected region and period",
                "material culture should follow source-supported historical context",
                "avoid anachronistic modern objects or styling unless source-supported"
            ],
            "roles": _GENERIC_ROLES,
        },
        "biography": {
            "baseline": [
                "visual presentation appropriate to the source person's documented time, place, and social context",
                "do not fictionalize unsupported appearance or events"
            ],
            "roles": _GENERIC_ROLES,
        },
        "patriotic": {
            "baseline": [
                "visual presentation appropriate to the detected national, historical, and political context",
                "use flags, uniforms, insignia, or national symbols only when source-supported or strongly established by the world context"
            ],
            "roles": _GENERIC_ROLES,
        },
        "fantasy": {
            "baseline": [
                "cinematic fantasy presentation while preserving the source's established rules and setting",
                "fantastical elements must be source-supported rather than freely invented"
            ],
            "roles": _GENERIC_ROLES,
        },
        "crime_thriller": {
            "baseline": [
                "cinematic thriller presentation appropriate to the detected location and period",
                "realistic contemporary details only when supported by source context"
            ],
            "roles": _GENERIC_ROLES,
        },
        "science_fiction": {
            "baseline": [
                "cinematic science-fiction presentation consistent with the source's technological and temporal rules",
                "do not invent technology beyond the established story world"
            ],
            "roles": _GENERIC_ROLES,
        }
    }
}


def load_visual_policy(path: str | Path | None = None) -> dict[str, Any]:
    candidate = Path(path) if path else DEFAULT_POLICY_PATH
    try:
        loaded: Any = json.loads(candidate.read_text(encoding="utf-8"))
        if isinstance(loaded, str):
            loaded = json.loads(loaded)
        if not isinstance(loaded, dict):
            raise ValueError("visual generation policy must decode to an object")
        merged = json.loads(json.dumps(_FALLBACK_POLICY))
        _deep_merge(merged, loaded)
        return merged
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return json.loads(json.dumps(_FALLBACK_POLICY))


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


_ROLE_PATTERNS = {
    "deity": re.compile(r"\b(lord|deity|god|goddess|shiva|vishnu|indra|brahma|deva|devi)\b", re.I),
    "warrior": re.compile(r"\b(warrior|soldier|fighter|champion|guard)\b", re.I),
    "ruler": re.compile(r"\b(king|queen|ruler|emperor|empress|prince|princess|chief)\b", re.I),
    "ascetic": re.compile(r"\b(ascetic|sage|rishi|guru|mendicant|monk|hermit|yogi)\b", re.I),
    "elder": re.compile(r"\b(elder|aged|ancient|grandfather|grandmother)\b", re.I),
}


def _clean(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip() if len(text) > limit else text


def _source_facts(character: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for fact in character.get("visual_facts", []):
        if not isinstance(fact, dict):
            continue
        status = str(fact.get("status") or "").lower()
        value = _clean(fact.get("value"), 140)
        if value and status not in {"unknown", "rejected", "conflict", "contradictory"}:
            result.append({
                "category": _clean(fact.get("category"), 60),
                "attribute": _clean(fact.get("attribute"), 80),
                "value": value,
                "basis": "source",
                "confidence": fact.get("confidence"),
                "scene_id": fact.get("scene_id"),
                "page_start": fact.get("page_start"),
                "page_end": fact.get("page_end"),
                "evidence": fact.get("evidence", ""),
            })
    return result


def _source_attributes(facts: list[dict[str, Any]]) -> set[str]:
    aliases = {
        "build": "physique",
        "body_type": "physique",
        "clothing": "costume_direction",
        "attire": "costume_direction",
        "garments": "costume_direction",
        "eyes": "eye_color",
        "face": "face_geometry",
        "expression": "presentation",
    }
    result = set()
    for fact in facts:
        attribute = str(fact.get("attribute") or "").strip().lower()
        result.add(aliases.get(attribute, attribute))
    return result


def classify_visual_role(character: dict[str, Any]) -> str:
    name = _clean(character.get("canonical_name"), 120)
    mentions = " ".join(
        _clean(m.get("context"), 220)
        for m in character.get("scene_mentions", [])
        if isinstance(m, dict)
    )
    haystack = f"{name} {mentions}"
    for role, pattern in _ROLE_PATTERNS.items():
        if pattern.search(haystack):
            return role
    return "person"


def build_inferred_visual_profile(
    character: dict[str, Any],
    *,
    genre: str = "general_narrative",
    policy: dict[str, Any] | None = None,
    world_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_visual_policy()
    name = _clean(character.get("canonical_name"), 120)
    facts = _source_facts(character)
    known = _source_attributes(facts)
    role = classify_visual_role(character)
    genre_block = (policy.get("genre_priors") or {}).get(genre)
    if not isinstance(genre_block, dict):
        genre_block = (policy.get("genre_priors") or {}).get(policy.get("default_genre", "general_narrative"), {})
    if not isinstance(genre_block, dict):
        genre_block = _FALLBACK_POLICY["genre_priors"]["general_narrative"]

    baseline = list(genre_block.get("baseline") or [])
    role_priors = list((genre_block.get("roles") or {}).get(role) or [])

    context_labels: list[str] = []
    if isinstance(world_context, dict):
        dimensions = world_context.get("dimensions") or {}
        for key in ("culture", "religious_context", "region", "period"):
            top = (dimensions.get(key) or {}).get("top") or {}
            label = top.get("label")
            if label:
                context_labels.append(f"detected {key.replace('_', ' ')}: {label}")

    inferred_values = context_labels + baseline + role_priors
    forbidden_phrases = {"eye color", "hair color", "exact age", "exact height", "facial measurements"}

    inferred = []
    seen = set()
    for value in inferred_values:
        lowered = value.lower()
        if any(token in lowered for token in forbidden_phrases):
            continue
        attribute = (
            "physique" if "physique" in lowered or "anatomy" in lowered
            else "presentation" if (
                "presence" in lowered or "presentation" in lowered or "styling" in lowered
                or "body language" in lowered or "posture" in lowered
            )
            else "costume_direction" if "garment" in lowered or "clothing" in lowered
            else "world_context" if lowered.startswith("detected ")
            else "environment_rules" if (
                "modern" in lowered or "materials" in lowered or "technology" in lowered
            )
            else "visual_style"
        )
        if attribute in known:
            continue
        key = (attribute, value.lower())
        if key in seen:
            continue
        seen.add(key)
        inferred.append({
            "attribute": attribute,
            "value": _clean(value, 180),
            "basis": "world_context" if lowered.startswith("detected ") else "genre_prior",
            "genre": genre,
            "locked_for_continuity": bool(
                policy.get("inference_rules", {}).get("lock_inferred_profile_for_continuity", True)
            ),
        })

    world_seed = json.dumps(world_context or {}, ensure_ascii=False, sort_keys=True)
    seed = f"{character.get('canonical_character_id')}|{name}|{genre}|{world_seed}".encode("utf-8")
    return {
        "schema_version": 2,
        "canonical_character_id": character.get("canonical_character_id"),
        "canonical_name": name,
        "identity_anchor": "vib-" + hashlib.sha256(seed).hexdigest()[:12],
        "visual_role": role,
        "source_facts": facts,
        "inferred_facts": inferred,
        "unknown_source_attributes": sorted({
            "eye_color", "hair_color", "exact_height", "exact_age", "facial_measurements"
        } - known),
        "inference_enabled": bool(policy.get("allow_controlled_inference", True)),
        "continuity_rule": (
            "Keep identity_anchor and all locked inferred attributes stable across scenes "
            "unless source evidence requires a change."
        ),
    }


def enrich_character(character: dict[str, Any], *, genre: str = "general_narrative", policy: dict[str, Any] | None = None, world_context: dict[str, Any] | None = None) -> dict[str, Any]:
    enriched = dict(character)
    enriched["visual_profile"] = build_inferred_visual_profile(
        character,
        genre=genre,
        policy=policy,
        world_context=world_context,
    )
    enriched["unknown_visual_attributes"] = bool(enriched["visual_profile"]["unknown_source_attributes"])
    return enriched


def composition_policy(policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_visual_policy()
    fallback = _FALLBACK_POLICY["image_layout"]["primary"]
    primary = ((policy.get("image_layout") or {}).get("primary") or {})
    result = dict(fallback)
    result.update(primary)
    return result
