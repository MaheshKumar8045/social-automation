from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS visual_entity_validation (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    visual_type TEXT NOT NULL,
    decision TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    character_score REAL NOT NULL DEFAULT 0,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(document_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_visual_entity_validation_doc_type
 ON visual_entity_validation(document_id, visual_type, decision);
"""

NAME_FRAGMENT_RE = re.compile(r"(?:[-‐‑‒–—]|\s)(?:[A-Za-z]{1,3})$|^[A-Za-z]{1,3}[-‐‑‒–—]$")
NON_CHARACTER_TERMS = {
    "observatory", "institution", "institute", "university", "college", "academy",
    "newspaper", "advertiser", "journal", "gazette", "times", "news", "north american",
    "company", "corporation", "railway", "station", "river", "mountain", "island",
    "ocean", "sea", "valley", "village", "hotel", "street", "road", "church",
    "museum", "society", "government", "expedition", "thousand", "hundred",
}
REFERENCE_ONLY_NAMES = {
    "christopher columbus", "leonardo da vinci", "galileo", "isaac newton",
}
TITLE_RE = re.compile(r"^(?:mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame)\.?\s+", re.I)


def normalize_name(name: str) -> str:
    value = re.sub(r"\s+", " ", name.replace("‐", "-").replace("‑", "-").replace("‒", "-").replace("–", "-").replace("—", "-")).strip(" ,.;:\"'")
    # OCR line-wrap fragment: "Living-" is not a standalone visual identity.
    if value.endswith("-") and len(value) > 3:
        value = value[:-1]
    return value


def score_entity(name: str, entity_type: str, mention_count: int, profile_text: str) -> tuple[float, str, list[str]]:
    n = normalize_name(name)
    low = n.lower()
    reasons: list[str] = []
    score = 0.0

    if entity_type == "character":
        score += 0.45
        reasons.append("upstream_character_type")
    elif entity_type in {"location", "environment"}:
        return 0.0, "environment", ["upstream_location_or_environment_type"]
    elif entity_type in {"organization", "object", "event"}:
        return 0.0, "reference", [f"upstream_{entity_type}_type"]

    if TITLE_RE.search(n):
        score += 0.20
        reasons.append("personal_title")
    if len(n.split()) in {2, 3}:
        score += 0.10
        reasons.append("person_name_shape")
    if mention_count >= 3:
        score += 0.10
        reasons.append("recurring_mentions")
    elif mention_count == 1:
        score -= 0.05
        reasons.append("single_mention")
    if any(term in low for term in NON_CHARACTER_TERMS):
        score -= 0.75
        reasons.append("institution_publication_or_place_term")
    if low in REFERENCE_ONLY_NAMES:
        score -= 0.30
        reasons.append("known_reference_only_name")
    if len(n) > 45:
        score -= 0.35
        reasons.append("unusually_long_name")
    if len(profile_text or "") > 1500:
        score -= 0.10
        reasons.append("oversized_upstream_profile_evidence")
    if NAME_FRAGMENT_RE.search(n) and len(n) < 8:
        score -= 0.50
        reasons.append("likely_ocr_fragment")

    score = max(0.0, min(1.0, score))
    if score >= 0.60:
        decision = "validated"
        visual_type = "character"
    elif score >= 0.35:
        decision = "review"
        visual_type = "character_candidate"
    else:
        decision = "excluded"
        visual_type = "reference"
    return score, visual_type, reasons


class VisualEntityValidator:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def build(self, document_id: int) -> dict[str, int]:
        with sqlite3.connect(self.database_path) as con:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys=ON")
            con.executescript(SCHEMA)
            con.execute("DELETE FROM visual_entity_validation WHERE document_id=?", (document_id,))
            entities = con.execute(
                "SELECT id, entity_type, canonical_name, profile_text FROM entities WHERE document_id=? ORDER BY id",
                (document_id,),
            ).fetchall()
            for entity in entities:
                mentions = int(con.execute("SELECT COUNT(*) FROM entity_mentions WHERE document_id=? AND entity_id=?", (document_id, entity["id"])).fetchone()[0])
                score, visual_type, reasons = score_entity(entity["canonical_name"], entity["entity_type"], mentions, entity["profile_text"] or "")
                con.execute(
                    "INSERT INTO visual_entity_validation(document_id,entity_id,visual_type,decision,canonical_name,character_score,reasons_json) VALUES(?,?,?,?,?,?,?)",
                    (document_id, entity["id"], visual_type, "validated" if visual_type == "character" else ("review" if visual_type == "character_candidate" else "excluded"), normalize_name(entity["canonical_name"]), score, __import__("json").dumps(reasons)),
                )
            con.commit()
            rows = con.execute("SELECT decision, COUNT(*) n FROM visual_entity_validation WHERE document_id=? GROUP BY decision", (document_id,)).fetchall()
            return {str(r["decision"]): int(r["n"]) for r in rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate entities for visual generation")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    args = parser.parse_args()
    counts = VisualEntityValidator(args.database).build(args.document_id)
    print("=== VISUAL ENTITY VALIDATION ===")
    for key in ("validated", "review", "excluded"):
        print(f"{key}: {counts.get(key, 0)}")


if __name__ == "__main__":
    main()
