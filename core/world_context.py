from __future__ import annotations

import re
import sqlite3
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any


# Lightweight, dependency-free evidence rules. They are intentionally broad:
# the source remains authoritative and low-confidence classifications are
# reported as uncertain rather than forced into a single category.
SIGNALS: dict[str, dict[str, tuple[str, ...]]] = {
    "narrative_type": {
        "mythology": ("mythology", "mythological", "epic", "deity", "god", "goddess", "asura", "rakshasa", "demigod"),
        "historical": ("history", "historical", "revolution", "independence", "empire", "kingdom", "king", "queen", "colonial"),
        "biography": ("biography", "autobiography", "memoir", "life of", "born", "died"),
        "patriotic": ("patriot", "patriotic", "nation", "nationalist", "freedom fighter", "martyr", "country", "homeland"),
        "fantasy": ("fantasy", "wizard", "dragon", "magic", "sorcery", "enchanted"),
        "crime_thriller": ("murder", "detective", "police", "crime", "investigation", "criminal", "mystery"),
        "science_fiction": ("spaceship", "planet", "galaxy", "android", "robot", "cyber", "space station"),
    },
    "religious_context": {
        "hindu": ("hindu", "shiva", "vishnu", "krishna", "rama", "sita", "ravana", "ganesha", "hanuman", "devi", "asura", "veda", "upanishad", "dharma", "puja", "mandir", "yajna"),
        "christian": ("christian", "jesus", "christ", "bible", "church", "gospel", "christianity"),
        "islamic": ("islam", "islamic", "muslim", "quran", "allah", "mosque", "ramadan", "imam"),
        "buddhist": ("buddhist", "buddha", "sangha", "monastery", "sutra", "bodhisattva"),
        "jewish": ("jewish", "judaism", "torah", "synagogue", "rabbi", "israelite"),
        "sikh": ("sikh", "sikhism", "guru nanak", "gurdwara", "khalsa", "grantha"),
    },
    "culture": {
        "indic": ("india", "indian", "lanka", "ayodhya", "mithila", "hastinapur", "kurukshetra", "sanskrit", "dharma", "asura", "rakshasa", "maharaja"),
        "japanese": ("japan", "japanese", "tokyo", "kyoto", "samurai", "shogun", "ninja", "kimono", "shinto"),
        "greek": ("greek", "greece", "athena", "zeus", "hera", "olympus", "sparta", "athens"),
        "roman": ("roman", "rome", "latin", "caesar", "senate", "gladiator"),
        "norse": ("norse", "odin", "thor", "loki", "asgard", "valhalla", "viking"),
        "chinese": ("china", "chinese", "beijing", "dynasty", "emperor", "daoist", "confucian"),
        "korean": ("korea", "korean", "seoul", "joseon", "goryeo", "hanbok"),
    },
    "region": {
        "india": ("india", "indian", "delhi", "mumbai", "kolkata", "varanasi", "hyderabad", "ayodhya", "mithila", "lanka"),
        "japan": ("japan", "tokyo", "kyoto", "osaka", "hokkaido"),
        "china": ("china", "beijing", "shanghai", "nanjing", "sichuan"),
        "greece": ("greece", "athens", "sparta", "crete"),
        "rome": ("rome", "italy", "roman"),
        "korea": ("korea", "seoul", "busan", "joseon"),
    },
    "period": {
        "ancient": ("ancient", "archaic", "bronze age", "iron age", "classical", "epic age"),
        "medieval": ("medieval", "middle ages", "kingdom", "sultanate", "feudal", "castle", "knight"),
        "early_modern": ("renaissance", "mughal", "tokugawa", "colonial", "early modern", "mercantile"),
        "modern": ("modern", "20th century", "21st century", "telephone", "automobile", "radio", "television"),
        "contemporary": ("contemporary", "smartphone", "internet", "social media", "laptop", "2020", "2021", "2022", "2023", "2024", "2025", "2026"),
    },
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _score_dimension(text: str, rules: dict[str, tuple[str, ...]]) -> list[dict[str, Any]]:
    normalized = _normalize(text)
    scores: Counter[str] = Counter()
    evidence: dict[str, list[str]] = {}
    for label, phrases in rules.items():
        for phrase in phrases:
            if phrase in normalized:
                scores[label] += 1
                evidence.setdefault(label, []).append(phrase)
    total = sum(scores.values())
    ranked = []
    for label, score in scores.most_common():
        confidence = round(min(0.99, score / max(total, 1) * 0.75 + min(score, 5) * 0.05), 3)
        ranked.append({"label": label, "confidence": confidence, "evidence": evidence.get(label, [])[:12]})
    return ranked


def analyze_text(text: str) -> dict[str, Any]:
    dimensions: dict[str, Any] = {}
    for dimension, rules in SIGNALS.items():
        ranked = _score_dimension(text, rules)
        top = ranked[0] if ranked else None
        dimensions[dimension] = {"top": top, "candidates": ranked[:5]}

    notes: list[str] = []
    for key, message in (
        ("narrative_type", "Narrative-type evidence is mixed; treat classification as provisional."),
        ("religious_context", "Religious-context evidence is mixed; do not force a religion-specific visual policy."),
        ("culture", "Cultural evidence is mixed; prefer source-described details and keep broad culture uncertain."),
    ):
        top = dimensions[key]["top"]
        if top and top["confidence"] < 0.55:
            notes.append(message)

    return {
        "schema_version": 1,
        "method": "deterministic_source_signal_analysis",
        "llm_used": False,
        "dimensions": dimensions,
        "notes": notes,
    }


@lru_cache(maxsize=16)
def _build_world_profile_cached(database_path: str, document_id: int) -> dict[str, Any]:
    with sqlite3.connect(database_path) as con:
        page_text = [str(row[0] or "") for row in con.execute(
            "SELECT text FROM pages WHERE document_id=? ORDER BY page_number", (document_id,)
        ).fetchall()]
        section_titles = [str(row[0] or "") for row in con.execute(
            "SELECT title FROM sections WHERE document_id=? ORDER BY page_number", (document_id,)
        ).fetchall()]
        entity_text = [str(row[0] or "") for row in con.execute(
            "SELECT canonical_name FROM entities WHERE document_id=? ORDER BY id", (document_id,)
        ).fetchall()]

    text = " ".join(page_text + section_titles + entity_text)
    analysis = analyze_text(text)
    return {
        "source": {
            "document_id": document_id,
            "evidence_scope": "document-wide",
            "method": analysis["method"],
        },
        **analysis,
    }


def build_world_profile(database_path: str | Path, document_id: int) -> dict[str, Any]:
    return _build_world_profile_cached(str(Path(database_path).resolve()), int(document_id))


__all__ = ["analyze_text", "build_world_profile"]
