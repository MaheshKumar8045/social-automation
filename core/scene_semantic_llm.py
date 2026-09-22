from __future__ import annotations

import os
from typing import Any

from .llm_schemas import SceneSemanticAnalysis, SceneSemanticResult
from .ollama_client import OllamaClient, OllamaSettings, OllamaUnavailable

_SYSTEM_PROMPT = """You are the source-grounding semantic interpreter for a PDF-to-media pipeline.

Your job is to analyze one supplied source scene and return only the requested JSON structure.
Do not invent facts. Use exact source wording as evidence whenever possible.

Character rules:
- visible = the supplied text directly establishes that character physically present, acting, speaking, reacting, or otherwise on scene.
- referenced = the character is mentioned, remembered, described, or acted upon without enough evidence that the character is physically visible in the scene.
- unknown = the source does not establish enough to decide.
- A character being named near another character's speech/action is not evidence that the named character is visible.

Dialogue rules:
- Copy dialogue exactly from the source when it is supportable.
- Do not include chapter/section headings, page labels, speaker labels, OCR debris, or explanatory text inside dialogue text.
- First-person narrative may be treated as dialogue only when the supplied text itself supports that reading; otherwise leave it out.

Visual-moment rules:
- Choose one primary moment and at most one secondary moment directly supported by the source.
- Do not merge unrelated actions into one invented event.

Source facts are direct facts. Inferences must be clearly separated and may not be presented as source facts.
Return JSON only according to the supplied schema."""


def llm_mode() -> str:
    return os.getenv("SOCIAL_AUTOMATION_LLM_MODE", "off").strip().lower()


def _contains_source(text: str, evidence: str) -> bool:
    if not evidence:
        return False
    return evidence.strip().casefold() in text.casefold()


def _validate_analysis(
    analysis: SceneSemanticAnalysis,
    *,
    source_text: str,
    known_character_names: set[str],
    model: str,
) -> SceneSemanticResult:
    reasons: list[str] = []
    source_ok = True

    primary = analysis.primary_visual_moment
    if not _contains_source(source_text, primary.evidence):
        source_ok = False
        reasons.append("primary_visual_moment_evidence_not_in_source")
    if primary.text.strip() and primary.text.strip().casefold() not in source_text.casefold():
        source_ok = False
        reasons.append("primary_visual_moment_text_not_in_source")

    if analysis.secondary_visual_moment is not None:
        secondary = analysis.secondary_visual_moment
        if not _contains_source(source_text, secondary.evidence):
            source_ok = False
            reasons.append("secondary_visual_moment_evidence_not_in_source")
        if secondary.text.strip() and secondary.text.strip().casefold() not in source_text.casefold():
            source_ok = False
            reasons.append("secondary_visual_moment_text_not_in_source")

    for item in analysis.dialogue:
        if item.speaker and item.speaker.casefold() not in {name.casefold() for name in known_character_names}:
            reasons.append(f"unknown_dialogue_speaker:{item.speaker}")
        if not _contains_source(source_text, item.text) or not _contains_source(source_text, item.evidence):
            source_ok = False
            reasons.append("dialogue_not_verbatim_source")

    for item in [*analysis.environment, *analysis.objects, *analysis.source_facts]:
        if not _contains_source(source_text, item.evidence):
            source_ok = False
            reasons.append("source_fact_evidence_not_in_source")

    for item in analysis.inferences:
        if item.basis_evidence and not _contains_source(source_text, item.basis_evidence):
            source_ok = False
            reasons.append("inference_basis_not_in_source")

    for character in analysis.characters:
        if character.name.casefold() not in {name.casefold() for name in known_character_names}:
            reasons.append(f"unknown_character_name:{character.name}")
        if character.physical_presence and character.scene_role == "visible":
            if not _contains_source(source_text, character.evidence):
                source_ok = False
                reasons.append(f"visible_character_evidence_not_in_source:{character.name}")

    if not source_ok:
        return SceneSemanticResult(
            status="rejected",
            model=model,
            llm_used=True,
            source_validated=False,
            analysis=None,
            rejected_reasons=list(dict.fromkeys(reasons)),
        )

    return SceneSemanticResult(
        status="ready",
        model=model,
        llm_used=True,
        source_validated=True,
        analysis=analysis,
        rejected_reasons=list(dict.fromkeys(reasons)),
    )


def build_scene_prompt(
    *,
    source_text: str,
    characters: list[dict[str, Any]],
    events: list[dict[str, Any]],
    world_profile: dict[str, Any],
) -> str:
    known_names = [str(item.get("canonical_name") or "") for item in characters if item.get("canonical_name")]
    event_text = [str(item.get("text") or "") for item in events if item.get("text")]
    return (
        "Analyze exactly this source scene. Treat the source text as authoritative.\n\n"
        f"KNOWN CANONICAL CHARACTER NAMES:\n{known_names}\n\n"
        f"EVENT CANDIDATES ALREADY EXTRACTED:\n{event_text[:12]}\n\n"
        f"WORLD CONTEXT (guidance only; never evidence):\n{world_profile}\n\n"
        f"SOURCE SCENE:\n{source_text}\n\n"
        "Return JSON only. Evidence fields must be exact substrings of SOURCE SCENE."
    )


def interpret_scene(
    *,
    source_text: str,
    characters: list[dict[str, Any]],
    events: list[dict[str, Any]],
    world_profile: dict[str, Any],
    client: OllamaClient | None = None,
) -> SceneSemanticResult:
    settings = client.settings if client is not None else OllamaSettings.from_env()
    interpreter = client or OllamaClient(settings)
    known_names = {
        str(item.get("canonical_name") or "").strip()
        for item in characters
        if str(item.get("canonical_name") or "").strip()
    }
    try:
        analysis = interpreter.analyze_scene(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=build_scene_prompt(
                source_text=source_text,
                characters=characters,
                events=events,
                world_profile=world_profile,
            ),
        )
    except OllamaUnavailable as exc:
        return SceneSemanticResult(
            status="rejected",
            model=settings.model,
            llm_used=False,
            source_validated=False,
            analysis=None,
            rejected_reasons=[f"ollama_unavailable:{exc}"],
        )

    return _validate_analysis(
        analysis,
        source_text=source_text,
        known_character_names=known_names,
        model=settings.model,
    )
