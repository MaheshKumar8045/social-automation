from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from .cinematic_generation import enhance_generation_package
from .generation_context import get_generation_context
from .llm_schemas import SceneSemanticResult
from .media_prompt_compiler import compile_media_prompts
from .scene_semantic_llm import interpret_scene, llm_mode
from .visual_generation_policy import enrich_character

_PROGRESS_STARTED: float | None = None
_PROGRESS_DONE = 0


def _progress_tick(scene_id: int) -> None:
    global _PROGRESS_STARTED, _PROGRESS_DONE
    total = int(os.getenv("SOCIAL_AUTOMATION_PROGRESS_TOTAL", "0") or 0)
    if total <= 0:
        return
    now = time.monotonic()
    if _PROGRESS_STARTED is None:
        _PROGRESS_STARTED = now
    _PROGRESS_DONE += 1
    elapsed = max(0.0, now - _PROGRESS_STARTED)
    average = elapsed / _PROGRESS_DONE if _PROGRESS_DONE else 0.0
    remaining = max(0, total - _PROGRESS_DONE)
    eta = average * remaining
    pct = min(100.0, (_PROGRESS_DONE / total) * 100.0)
    print(
        f"LLM {llm_mode().upper()} | Scene {_PROGRESS_DONE}/{total} (id={scene_id}) | "
        f"{pct:5.1f}% | elapsed {elapsed/60:.1f}m | avg {average:.1f}s/scene | ETA {eta/60:.1f}m",
        file=sys.stderr,
        flush=True,
    )


def _extend_truncated_source_fragment(fragment: str, source: str) -> str:
    value = str(fragment or "").strip()
    if not value or value[-1:] in ".!?" or value not in source:
        return value
    start = source.find(value)
    tail = source[start + len(value):]
    match = re.search(r"[.!?]", tail)
    if not match:
        return value
    return re.sub(r"\s+", " ", source[start:start + len(value) + match.end()]).strip()


def _repair_truncated_visual_moments(media: dict[str, Any], source: str) -> dict[str, Any]:
    replacements: dict[str, str] = {}

    def collect(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                collect(child, child_key)
        elif isinstance(value, list):
            for child in value:
                collect(child, key)
        elif isinstance(value, str) and key in {"source_visual_focus", "source_visual_moments"}:
            repaired = _extend_truncated_source_fragment(value, source)
            if repaired != value:
                replacements[value] = repaired

    collect(media)
    if not replacements:
        return media

    def rewrite(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        if isinstance(value, str):
            for old, new in replacements.items():
                value = value.replace(old, new)
            return value
        return value

    return rewrite(media)


def _source_participant_line(intent: dict[str, Any]) -> str:
    participants = intent.get("source_participants") or []
    if not participants:
        return "SOURCE-ESTABLISHED ANONYMOUS PARTICIPANTS: none."
    labels = []
    for item in participants:
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
        else:
            label = str(item or "").strip()
        if label and label.casefold() not in {x.casefold() for x in labels}:
            labels.append(label)
    return (
        "SOURCE-ESTABLISHED ANONYMOUS PARTICIPANTS: "
        + ", ".join(labels[:12])
        + ". These are source-established groups/participants, not canonical identities; "
          "they may be depicted only at the action and visual level explicitly supported by the scene text."
    )


def _propagate_source_participants(media: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
    """Make explicit source-established groups visible to media prompting without weakening character identity rules."""
    line = _source_participant_line(intent)
    output = dict(media)
    image = dict(output.get("image") or {})
    image["prompt"] = f"{image.get('prompt', '')} {line}"
    image["source_participants"] = intent.get("source_participants") or []
    output["image"] = image

    short = dict(output.get("short_video") or {})
    short["source_participants"] = intent.get("source_participants") or []
    for clip in short.get("clips") or []:
        clip["prompt"] = f"{clip.get('prompt', '')} {line}"
    output["short_video"] = short

    long = dict(output.get("long_video") or {})
    long["source_participants"] = intent.get("source_participants") or []
    for shot in long.get("shots") or []:
        shot["prompt"] = f"{shot.get('prompt', '')} {line}"
    output["long_video"] = long
    return output


class GenerationPlanner:
    """Convert generation context into a deterministic generation plan."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    @staticmethod
    def _llm_result(context: dict[str, Any]) -> SceneSemanticResult | None:
        mode = llm_mode()
        if mode not in {"shadow", "enhance"}:
            return None
        result = interpret_scene(
            source_text=str((context.get("scene") or {}).get("text") or ""),
            characters=context.get("characters") or [],
            events=context.get("events") or [],
            world_profile=context.get("world_profile") or {},
        )
        if mode == "enhance" and result.status != "ready":
            reasons = "; ".join(result.rejected_reasons) or "unknown local LLM failure"
            raise RuntimeError(f"Local LLM semantic analysis rejected scene: {reasons}")
        return result

    @staticmethod
    def _apply_llm_semantics(media: dict[str, Any], result: SceneSemanticResult | None) -> dict[str, Any]:
        if result is None or result.status != "ready" or result.analysis is None:
            return media
        output = dict(media)
        analysis = result.analysis
        primary = analysis.primary_visual_moment.text
        secondary = analysis.secondary_visual_moment.text if analysis.secondary_visual_moment else ""
        llm_visible = [x.name for x in analysis.characters if x.scene_role == "visible" and x.physical_presence]
        llm_referenced = [x.name for x in analysis.characters if x.scene_role == "referenced"]
        llm_dialogue = [x.text for x in analysis.dialogue]

        image = dict(output.get("image") or {})
        image["prompt"] = (
            f"{image.get('prompt', '')} LLM-VALIDATED SOURCE SEMANTICS: Primary visual moment: {primary}. "
            + (f"Secondary visual moment: {secondary}. " if secondary else "")
            + f"Source-confirmed visible characters only: {', '.join(llm_visible) or 'none'}. "
            + f"Referenced characters that must not be rendered merely from mention: {', '.join(llm_referenced) or 'none'}."
        )
        if llm_dialogue:
            existing = list(image.get("dialogue_overlays") or [])
            overlays = []
            for index, text in enumerate(llm_dialogue[:2], 1):
                base = dict(existing[index - 1]) if index <= len(existing) else {
                    "box_number": index,
                    "box_type": "dialogue_box",
                    "required": True,
                    "placement": "largest protected negative-space region opposite the primary subject/action",
                    "avoid": ["faces", "hands", "important objects", "primary action"],
                }
                base.update(box_number=index, text=text, text_source="llm_verified_source_dialogue")
                overlays.append(base)
            image["dialogue_overlays"] = overlays
        if analysis.characters:
            allowed = {name.casefold() for name in llm_visible}
            image["character_blocking"] = [
                line for line in (image.get("character_blocking") or [])
                if line.split(":", 1)[0].strip().casefold() in allowed
            ]
            image["referenced_characters"] = list(dict.fromkeys([*(image.get("referenced_characters") or []), *llm_referenced]))

        short = dict(output.get("short_video") or {})
        for clip in short.get("clips") or []:
            clip["prompt"] = f"{clip.get('prompt', '')} LLM-validated primary source moment: {primary}. Do not render a referenced-only character as visible without physical source evidence."
        long = dict(output.get("long_video") or {})
        for shot in long.get("shots") or []:
            shot["prompt"] = f"{shot.get('prompt', '')} LLM-validated primary source moment: {primary}. Do not render a referenced-only character as visible without physical source evidence."
        output["image"], output["short_video"], output["long_video"] = image, short, long
        return output

    @staticmethod
    def _prompt_bundle(context, characters, objects, events, constraints):
        media_context = dict(context)
        media_context.update(characters=characters, objects=objects, events=events, generation_constraints=constraints)
        media = compile_media_prompts(media_context)
        media = enhance_generation_package(
            scene=context.get("scene") or {}, characters=characters, objects=objects, events=events,
            continuity=context.get("continuity") or {}, world_profile=context.get("world_profile") or {},
            genre=context.get("visual_genre") or "general_narrative", media=media,
        )
        source = str((context.get("scene") or {}).get("text") or "")
        media = _repair_truncated_visual_moments(media, source)

        if llm_mode() == "enhance":
            media = GenerationPlanner._apply_llm_semantics(media, context.get("llm_scene_semantics_result"))

        # Build the same deterministic intent used by the cinematic package so
        # source-established anonymous groups can be depicted without becoming
        # canonical character identities.
        intent = (media.get("cinematic_scene_intelligence") or {}).get("intent") or {}
        if intent:
            media = _propagate_source_participants(media, intent)

        image = dict(media.get("image") or {})
        prompt = str(image.get("prompt") or "")
        if not any(token in prompt.lower() for token in ("dialogue", "narrative box", "dialogue-or-narrative")):
            prompt += " Include at least one dialogue-or-narrative box inside the protected safe area; never cover faces, hands, important objects, or primary action."
            image["prompt"] = prompt
            media["image"] = image

        return {
            "image_prompt": media["image"]["prompt"],
            "image_dialogue_overlays": media["image"]["dialogue_overlays"],
            "image_layout": media["image"]["layout"],
            "visual_inference": media["visual_inference"],
            "short_video_prompt_package": media["short_video"],
            "long_video_prompt_package": media["long_video"],
            "audio_prompt": media["short_video"]["audio"],
            "media_prompt_package": media,
        }

    def build(self, document_id: int, scene_id: int) -> dict[str, Any]:
        try:
            context = get_generation_context(self.database_path, document_id, scene_id)
            if context.get("error"):
                return {"document_id": document_id, "scene_id": scene_id, "plan_status": "unavailable", "reason": context["error"], "source_grounded": True, "unknowns_must_remain_unknown": True}
            world_profile = context.get("world_profile") or {}
            characters = [enrich_character(c, genre=context.get("visual_genre", "general_narrative"), world_context=world_profile) for c in (context.get("characters") or [])]
            llm_semantics_result = self._llm_result(context)
            context["llm_scene_semantics_result"] = llm_semantics_result
            visual_constraints = [
                "Preserve source-supported visual facts exactly.",
                "Controlled production visual inference is allowed for missing attributes using the dynamically detected story-world context and configured genre policy.",
                "World context is contextual guidance only and must never override a source-supported fact.",
                "Never override, contradict, or silently relabel a source-supported fact as an inference.",
                "Never infer exact eye color, hair color, height, exact age, or facial measurements unless source evidence supplies them.",
                "Lock deterministic inferred profile attributes across scenes for the same canonical identity.",
                "Use mobile-first 9:16 composition for primary image/video output.",
                "At least one dialogue-or-narrative box is required for image composition.",
                "Dialogue/text boxes must stay inside the safe area and never cover faces, hands, important objects, or primary action.",
                "Keep source visual moments focused: one primary moment plus limited secondary context rather than unrelated prose aggregation.",
            ]
            if not characters:
                visual_constraints.append("No canonical character is source-confirmed as present; do not force a character identity into the scene.")
            if llm_semantics_result is not None:
                visual_constraints.append("Local LLM semantics are advisory source interpretation and must pass exact source-evidence validation before influencing generation.")
            prompts = self._prompt_bundle(context, characters, context.get("objects") or [], context.get("events") or [], visual_constraints)
            result = {
                "document_id": document_id, "scene_id": scene_id, "plan_version": 9, "plan_status": "ready",
                "source_grounded": True, "unknowns_must_remain_unknown": True, "world_profile": world_profile,
                "scene": context["scene"], "characters": characters, "objects": context.get("objects") or [],
                "events": context.get("events") or [], "continuity": context.get("continuity") or {},
                "neighbors": context.get("neighbors") or {}, "generation_constraints": context.get("generation_constraints") or [],
                "visual_constraints": visual_constraints, **prompts, "source_evidence": self._evidence(context),
            }
            if llm_semantics_result is not None:
                result["llm_scene_semantics"] = llm_semantics_result.model_dump(mode="json")
                result["llm_mode"] = llm_mode()
            return result
        finally:
            _progress_tick(scene_id)

    @staticmethod
    def _evidence(context: dict[str, Any]) -> list[dict[str, Any]]:
        evidence = []
        for character in context.get("characters") or []:
            for mention in character.get("scene_mentions", []):
                evidence.append({"type": "character_mention", "canonical_character_id": character["canonical_character_id"], "source_name": mention.get("source_name"), "page_start": mention.get("page_start"), "page_end": mention.get("page_end"), "context": mention.get("context"), "confidence": mention.get("confidence")})
            for fact in character.get("visual_facts", []):
                evidence.append({"type": "visual_fact", "canonical_character_id": character["canonical_character_id"], "category": fact.get("category"), "attribute": fact.get("attribute"), "value": fact.get("value"), "scene_id": fact.get("scene_id"), "page_start": fact.get("page_start"), "page_end": fact.get("page_end"), "evidence": fact.get("evidence"), "confidence": fact.get("confidence")})
        for obj in context.get("objects") or []:
            evidence.append({"type": "object_mention", "object_id": obj.get("object_id"), "canonical_name": obj.get("canonical_name"), "page_start": obj.get("page_start"), "page_end": obj.get("page_end"), "evidence": obj.get("evidence"), "confidence": obj.get("confidence")})
        return evidence


def build_generation_plan(database_path: str | Path, document_id: int, scene_id: int) -> dict[str, Any]:
    return GenerationPlanner(database_path).build(document_id, scene_id)
