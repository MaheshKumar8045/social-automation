from __future__ import annotations

import re
import sqlite3
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

# Weighted evidence rules. Specific world markers are stronger than generic
# words such as "king", "empire", or "church" that occur across genres.
SIGNALS: dict[str, dict[str, dict[str, int]]] = {
    "narrative_type": {
        "mythology": {"mythology": 8, "mythological": 8, "deity": 7, "goddess": 7, "demigod": 7, "asura": 7, "rakshasa": 7, "epic": 3, "rama": 8, "sita": 8, "ravana": 8, "shiva": 8, "vishnu": 8, "krishna": 8, "hanuman": 8, "indra": 8, "brahma": 8},
        "historical": {"history": 5, "historical": 5, "revolution": 5, "independence": 5, "colonial": 5, "empire": 2, "kingdom": 2, "king": 1, "queen": 1, "emperor": 1, "war": 1},
        "biography": {"biography": 8, "autobiography": 8, "memoir": 8, "life of": 7, "born": 3, "died": 3},
        "patriotic": {"patriot": 6, "patriotic": 8, "nationalist": 7, "freedom fighter": 8, "martyr": 7, "homeland": 6, "nation": 2, "country": 1, "independence movement": 8},
        "fantasy": {"fantasy": 8, "wizard": 7, "dragon": 7, "magic": 7, "sorcery": 7, "enchanted": 7},
        "crime_thriller": {"murder": 6, "detective": 7, "police": 6, "crime": 6, "investigation": 6, "criminal": 5, "mystery": 5},
        "science_fiction": {"spaceship": 8, "planet": 4, "galaxy": 6, "android": 7, "robot": 6, "cyber": 6, "space station": 8},
    },
    "religious_context": {
        "hindu": {"hindu": 8, "shiva": 8, "vishnu": 8, "krishna": 8, "rama": 8, "sita": 8, "ravana": 8, "ganesha": 8, "hanuman": 8, "devi": 7, "asura": 7, "veda": 7, "upanishad": 7, "dharma": 5, "puja": 6, "mandir": 6, "yajna": 6},
        "christian": {"christian": 8, "jesus": 8, "christ": 8, "bible": 7, "gospel": 7, "christianity": 8},
        "islamic": {"islam": 8, "islamic": 8, "muslim": 8, "quran": 8, "allah": 8, "mosque": 6, "ramadan": 7, "imam": 6},
        "buddhist": {"buddhist": 8, "buddha": 8, "sangha": 7, "monastery": 5, "sutra": 6, "bodhisattva": 7},
        "jewish": {"jewish": 8, "judaism": 8, "torah": 8, "synagogue": 6, "rabbi": 6, "israelite": 7},
        "sikh": {"sikh": 8, "sikhism": 8, "guru nanak": 8, "gurdwara": 7, "khalsa": 7, "grantha": 7},
    },
    "culture": {
        "indic": {"india": 6, "indian": 6, "lanka": 6, "ayodhya": 7, "mithila": 7, "hastinapur": 7, "kurukshetra": 7, "sanskrit": 6, "dharma": 4, "asura": 6, "rakshasa": 6, "maharaja": 6},
        "japanese": {"japan": 6, "japanese": 6, "tokyo": 5, "kyoto": 5, "samurai": 7, "shogun": 7, "ninja": 7, "kimono": 7, "shinto": 7},
        "greek": {"greek": 6, "greece": 6, "athena": 7, "zeus": 7, "hera": 7, "olympus": 7, "sparta": 7, "athens": 6},
        "roman": {"roman": 6, "rome": 6, "latin": 5, "caesar": 7, "senate": 5, "gladiator": 7},
        "norse": {"norse": 6, "odin": 7, "thor": 7, "loki": 7, "asgard": 7, "valhalla": 7, "viking": 7},
        "chinese": {"china": 6, "chinese": 6, "beijing": 5, "dynasty": 5, "emperor": 2, "daoist": 7, "confucian": 7},
        "korean": {"korea": 6, "korean": 6, "seoul": 5, "joseon": 7, "goryeo": 7, "hanbok": 7},
    },
    "region": {
        "india": {"india": 6, "indian": 6, "delhi": 6, "mumbai": 6, "kolkata": 6, "varanasi": 7, "hyderabad": 6, "ayodhya": 7, "mithila": 7, "lanka": 5},
        "japan": {"japan": 6, "tokyo": 6, "kyoto": 6, "osaka": 6, "hokkaido": 6},
        "china": {"china": 6, "beijing": 6, "shanghai": 6, "nanjing": 6, "sichuan": 6},
        "greece": {"greece": 6, "athens": 6, "sparta": 6, "crete": 6},
        "rome": {"rome": 6, "italy": 6, "roman": 5},
        "korea": {"korea": 6, "seoul": 6, "busan": 6, "joseon": 6},
    },
    "period": {
        "ancient": {"ancient": 5, "archaic": 5, "bronze age": 7, "iron age": 7, "classical": 5, "epic age": 7},
        "medieval": {"medieval": 6, "middle ages": 6, "sultanate": 5, "feudal": 5, "castle": 3, "knight": 3},
        "early_modern": {"renaissance": 7, "mughal": 7, "tokugawa": 7, "colonial": 5, "early modern": 7, "mercantile": 4},
        "modern": {"modern": 4, "20th century": 7, "21st century": 7, "telephone": 4, "automobile": 4, "radio": 4, "television": 4},
        "contemporary": {"contemporary": 6, "smartphone": 7, "internet": 7, "social media": 7, "laptop": 6, "2020": 6, "2021": 6, "2022": 6, "2023": 6, "2024": 6, "2025": 6, "2026": 6},
    },
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _score_dimension(text: str, rules: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    normalized = _normalize(text)
    scores: Counter[str] = Counter()
    evidence: dict[str, list[str]] = {}
    for label, phrases in rules.items():
        for phrase, weight in phrases.items():
            if phrase in normalized:
                scores[label] += weight
                evidence.setdefault(label, []).append(phrase)
    total = sum(scores.values())
    ranked = []
    for label, score in scores.most_common():
        confidence = round(min(0.995, 0.5 + 0.45 * (score / max(score + total, 1))), 3)
        ranked.append({"label": label, "score": score, "confidence": confidence, "evidence": evidence[label][:12]})
    return ranked


def analyze_text(text: str) -> dict[str, Any]:
    dimensions: dict[str, Any] = {}
    for dimension, rules in SIGNALS.items():
        ranked = _score_dimension(text, rules)
        dimensions[dimension] = {"top": ranked[0] if ranked else None, "candidates": ranked[:5]}
    notes = []
    for key in ("narrative_type", "religious_context", "culture"):
        top = dimensions[key]["top"]
        if top and top["confidence"] < 0.62:
            notes.append(f"{key.replace('_', ' ').capitalize()} evidence is mixed; treat classification as provisional.")
    return {"schema_version": 3, "method": "weighted_deterministic_source_signal_analysis", "llm_used": False, "dimensions": dimensions, "notes": notes}


@lru_cache(maxsize=16)
def _build_world_profile_cached(database_path: str, document_id: int) -> dict[str, Any]:
    with sqlite3.connect(database_path) as con:
        page_text = [str(row[0] or "") for row in con.execute("SELECT text FROM pages WHERE document_id=? ORDER BY page_number", (document_id,)).fetchall()]
        section_titles = [str(row[0] or "") for row in con.execute("SELECT title FROM sections WHERE document_id=? ORDER BY page_number", (document_id,)).fetchall()]
        entity_text = [str(row[0] or "") for row in con.execute("SELECT canonical_name FROM entities WHERE document_id=? ORDER BY id", (document_id,)).fetchall()]
    return {"source": {"document_id": document_id, "evidence_scope": "document-wide"}, **analyze_text(" ".join(page_text + section_titles + entity_text))}


def build_world_profile(database_path: str | Path, document_id: int) -> dict[str, Any]:
    return _build_world_profile_cached(str(Path(database_path).resolve()), int(document_id))


__all__ = ["analyze_text", "build_world_profile"]
