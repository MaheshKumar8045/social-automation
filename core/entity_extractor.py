from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from core.models import EntityRecord, EntityMentionRecord, EventRecord


class EntityExtractor:
    """
    Source-grounded baseline discovery of reusable entities and event candidates.

    This intentionally avoids inventing facts. It discovers likely proper names
    and setting phrases from existing scene text, retaining source excerpts as
    evidence. A later NER/LLM pass can enrich these records without changing
    the storage contract.
    """

    _TITLE_RE = re.compile(
        r"\b(?:Mr|Mrs|Miss|Ms|Dr|Sir|Captain|Professor|Lord|Lady|King|Queen|Prince|Princess)"
        r"\.?\s+[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,2}"
    )
    _SAID_RE = re.compile(
        r"\b([A-Z][A-Za-z'-]{2,}(?:\s+[A-Z][A-Za-z'-]+){0,2})"
        r"\s+(?:said|replied|asked|cried|shouted|exclaimed|answered|whispered|remarked|observed)\b"
    )
    _PROPER_RE = re.compile(
        r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2}\b"
    )
    _PLACE_RE = re.compile(
        r"\b(?:in|at|from|to|near|on|into|across|through|upon|toward|towards|beside|around)"
        r"\s+(?:the\s+)?([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,3})"
    )
    _ENV_RE = re.compile(
        r"\b(?:the\s+)?([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*)?)"
        r"\s+(river|mountain|mountains|village|town|city|sea|ocean|"
        r"forest|cave|cavern|island|islands|desert|road|roadway|station|"
        r"tunnel|mine|gallery|shaft|shore|bank|banks|camp|room|house|"
        r"valley|lake|hill|hills|coast|plain|plains|stream)\b",
        re.IGNORECASE,
    )

    _STOP = {
        "The", "This", "That", "These", "Those", "And", "But", "Then",
        "When", "Where", "What", "Which", "There", "Their", "They",
        "He", "She", "His", "Her", "It", "I", "We", "You", "Our",
        "Chapter", "Scene", "Page", "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday", "January", "February",
        "March", "April", "May", "June", "July", "August", "September",
        "October", "November", "December",
        "entered", "enter", "went", "go", "came", "come", "left",
        "leave", "crossed", "cross", "reached", "reach", "saw",
        "see", "looked", "look", "found", "find", "passed", "pass",
        "walked", "walk", "rode", "ride", "stood", "stand", "sat",
        "set", "put", "took", "take", "made", "make", "began", "begin",
    }

    def extract(
        self,
        scenes: list[dict[str, Any]],
    ) -> tuple[list[EntityRecord], list[EntityMentionRecord], list[EventRecord]]:
        entities: dict[tuple[str, str], EntityRecord] = {}
        mentions: list[EntityMentionRecord] = []
        events: list[EventRecord] = []

        for scene in scenes:
            text = str(scene.get("text") or "").strip()
            if not text:
                continue

            scene_id = int(scene["id"])
            story_id = int(scene["story_id"])
            page_start = int(scene["page_start"])
            page_end = int(scene["page_end"])

            location_candidates = self._place_candidates(text)
            environment_candidates = self._environment_candidates(text)
            excluded_character_names = {
                name.lower()
                for name in (*location_candidates.keys(), *environment_candidates.keys())
            }

            candidates = self._character_candidates(text)
            for name, confidence in candidates.items():
                if name.lower() in excluded_character_names:
                    continue
                key = ("character", name)
                entities.setdefault(
                    key,
                    EntityRecord(
                        entity_type="character",
                        canonical_name=name,
                        profile_text="",
                        confidence=confidence,
                        discovery_method="proper_name_heuristic",
                    ),
                )
                context = self._context(text, name)
                mentions.append(EntityMentionRecord(
                    entity_type="character",
                    canonical_name=name,
                    scene_id=scene_id,
                    story_id=story_id,
                    page_start=page_start,
                    page_end=page_end,
                    mention_text=name,
                    context=context,
                    confidence=confidence,
                ))

            for name, confidence in location_candidates.items():
                key = ("location", name)
                entities.setdefault(
                    key,
                    EntityRecord(
                        entity_type="location",
                        canonical_name=name,
                        profile_text="",
                        confidence=confidence,
                        discovery_method="location_cue_heuristic",
                    ),
                )
                mentions.append(EntityMentionRecord(
                    entity_type="location",
                    canonical_name=name,
                    scene_id=scene_id,
                    story_id=story_id,
                    page_start=page_start,
                    page_end=page_end,
                    mention_text=name,
                    context=self._context(text, name),
                    confidence=confidence,
                ))

            for name, confidence in environment_candidates.items():
                key = ("environment", name)
                entities.setdefault(
                    key,
                    EntityRecord(
                        entity_type="environment",
                        canonical_name=name,
                        profile_text="",
                        confidence=confidence,
                        discovery_method="setting_phrase_heuristic",
                    ),
                )
                mentions.append(EntityMentionRecord(
                    entity_type="environment",
                    canonical_name=name,
                    scene_id=scene_id,
                    story_id=story_id,
                    page_start=page_start,
                    page_end=page_end,
                    mention_text=name,
                    context=self._context(text, name),
                    confidence=confidence,
                ))

            # Event storage is deliberately scene-grounded rather than an
            # invented semantic summary. The complete scene is the evidence.
            events.append(EventRecord(
                event_order=len(events) + 1,
                title=str(scene.get("title") or f"Scene {scene.get('scene_order', 1)}"),
                page_start=page_start,
                page_end=page_end,
                text=text,
                discovery_method="scene_event",
                confidence=0.4,
            ))

        # Build compact evidence profiles from the first few contexts.
        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
        for mention in mentions:
            if mention.context and len(grouped[(mention.entity_type, mention.canonical_name)]) < 5:
                grouped[(mention.entity_type, mention.canonical_name)].append(mention.context)

        finalized = []
        for key, entity in entities.items():
            evidence = "\n\n".join(grouped.get(key, []))
            finalized.append(EntityRecord(
                entity_type=entity.entity_type,
                canonical_name=entity.canonical_name,
                profile_text=evidence,
                confidence=entity.confidence,
                discovery_method=entity.discovery_method,
            ))

        finalized.sort(key=lambda e: (e.entity_type, e.canonical_name.lower()))
        return finalized, mentions, events

    @classmethod
    def _character_candidates(cls, text: str) -> dict[str, float]:
        result: dict[str, float] = {}
        for match in cls._TITLE_RE.finditer(text):
            result[cls._clean(match.group(0))] = 0.8
        for match in cls._SAID_RE.finditer(text):
            name = cls._clean(match.group(1))
            if cls._valid_name(name):
                result.setdefault(name, 0.75)
        for match in cls._PROPER_RE.finditer(text):
            name = cls._clean(match.group(0))
            if cls._valid_name(name):
                result.setdefault(name, 0.45)
        return result

    @classmethod
    def _place_candidates(cls, text: str) -> dict[str, float]:
        result: dict[str, float] = {}
        for match in cls._PLACE_RE.finditer(text):
            name = cls._clean(match.group(1))
            if cls._valid_name(name):
                result.setdefault(name, 0.6)
        return result

    @classmethod
    def _environment_candidates(cls, text: str) -> dict[str, float]:
        result: dict[str, float] = {}
        for match in cls._ENV_RE.finditer(text):
            phrase = cls._clean(match.group(0))
            result.setdefault(phrase, 0.65)
        return result

    @classmethod
    def _valid_name(cls, value: str) -> bool:
        parts = value.split()
        return bool(parts) and all(
            p not in cls._STOP and len(p) >= 3 for p in parts
        )

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip(" \t\r\n,.;:!?\"'()[]"))

    @staticmethod
    def _context(text: str, term: str, radius: int = 220) -> str:
        pos = text.lower().find(term.lower())
        if pos < 0:
            return text[:radius].strip()
        start = max(0, pos - radius)
        end = min(len(text), pos + len(term) + radius)
        return text[start:end].strip()
