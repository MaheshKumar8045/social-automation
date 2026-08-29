from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS character_evidence_classification (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    score REAL NOT NULL,
    mention_count INTEGER NOT NULL DEFAULT 0,
    scene_count INTEGER NOT NULL DEFAULT 0,
    evidence_json TEXT NOT NULL DEFAULT '[]',
    reasons_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(document_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_character_evidence_doc_label
 ON character_evidence_classification(document_id, label);
"""

PERSONAL_TITLE = re.compile(r"\b(?:mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame)\.?\b", re.I)
DIALOGUE_VERB = re.compile(r"\b(?:said|asked|replied|answered|cried|shouted|whispered|exclaimed|remarked|observed|continued|added|returned)\b", re.I)
ACTION_VERB = re.compile(r"\b(?:entered|left|went|came|looked|saw|heard|spoke|said|asked|replied|answered|walked|ran|stood|sat|turned|smiled|laughed|wept|shouted|cried|took|gave|held|carried|followed|returned|arrived|departed|climbed|descended|examined|opened|closed)\b", re.I)
PRONOUN_REF = re.compile(r"\b(?:he|she|him|her|his|hers|himself|herself)\b", re.I)
NON_CHARACTER_TERMS = re.compile(r"\b(?:observatory|institution|institute|university|college|academy|newspaper|advertiser|journal|gazette|railway|company|corporation|government|commission|museum|society)\b", re.I)
COMMON_NON_NAMES = {
    "after", "all", "and", "are", "before", "but", "for", "from", "how", "let", "not", "nothing", "now", "one", "some", "still", "suddenly", "that", "the", "then", "this", "while", "with", "yes", "no", "we", "they", "he", "she", "sir", "colonel", "professor", "captain", "mr", "dr", "lady", "lord",
}
PLACE_LIKE_NAMES = {
    "africa", "iceland", "england", "russia", "europe", "europeans", "london", "cape town", "south africa", "greenwich", "zambesi", "kalahari",
}


def name_is_present(text: str, name: str) -> bool:
    compact = re.sub(r"\s+", " ", text).strip()
    target = re.escape(name.strip().rstrip(".,;:"))
    return bool(re.search(rf"(?<!\w){target}(?!\w)", compact, re.I))


def classify(name: str, entity_type: str, mentions: list[sqlite3.Row]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    reasons: list[str] = []
    evidence: list[str] = []
    clean_name = re.sub(r"\s+", " ", name.replace("‐", "-").replace("‑", "-").replace("–", "-").replace("—", "-")).strip(" ,.;:\"'")
    low = clean_name.lower()

    if entity_type in {"location", "environment", "organization", "object", "event"}:
        return "non_character", 0.99, [f"upstream_{entity_type}_type"], []
    if low in COMMON_NON_NAMES:
        return "reference", 0.99, ["common_word_or_title_only"], []
    if low in PLACE_LIKE_NAMES or NON_CHARACTER_TERMS.search(clean_name):
        return "non_character", 0.98, ["place_institution_or_publication_signal"], []
    if len(clean_name) > 45:
        return "reference", 0.95, ["unusually_long_entity_name"], []

    relevant_contexts = []
    for m in mentions:
        text = str(m["context"] or "").strip()
        if text and name_is_present(text, clean_name):
            relevant_contexts.append(text)

    if not relevant_contexts:
        return "reference", 0.90, ["no_exact_name_in_mention_context"], []

    if PERSONAL_TITLE.search(clean_name):
        score += 0.25
        reasons.append("personal_title")
    if len(clean_name.split()) in {2, 3}:
        score += 0.08
        reasons.append("person_name_shape")

    dialogue_hits = sum(bool(DIALOGUE_VERB.search(t)) for t in relevant_contexts)
    action_hits = sum(bool(ACTION_VERB.search(t)) for t in relevant_contexts)
    pronoun_hits = sum(bool(PRONOUN_REF.search(t)) for t in relevant_contexts)
    if dialogue_hits:
        score += min(0.30, dialogue_hits * 0.10)
        reasons.append("dialogue_context_near_entity")
    if action_hits:
        score += min(0.18, action_hits * 0.03)
        reasons.append("human_action_context_near_entity")
    if pronoun_hits:
        score += min(0.08, pronoun_hits * 0.015)
        reasons.append("human_pronoun_context")

    mention_count = len(mentions)
    scene_count = len({m["scene_id"] for m in mentions if m["scene_id"] is not None})
    if mention_count >= 10:
        score += 0.12
        reasons.append("strong_recurring_mentions")
    elif mention_count >= 3:
        score += 0.07
        reasons.append("recurring_mentions")
    elif mention_count == 1:
        score -= 0.08
        reasons.append("single_mention")
    if scene_count >= 5:
        score += 0.08
        reasons.append("multi_scene_presence")

    if re.search(r"[-‐‑‒–—]$", clean_name):
        score -= 0.30
        reasons.append("line_break_fragment")

    score = max(0.0, min(1.0, score))
    if score >= 0.70:
        label = "validated"
    elif score >= 0.45:
        label = "probable"
    elif score >= 0.20:
        label = "uncertain"
    else:
        label = "reference"

    for m in relevant_contexts[:3]:
        evidence.append(m[:500])
    return label, score, reasons, evidence


class CharacterEvidenceClassifier:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def build(self, document_id: int) -> dict[str, int]:
        with sqlite3.connect(self.database_path) as con:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys=ON")
            con.executescript(SCHEMA)
            con.execute("DELETE FROM character_evidence_classification WHERE document_id=?", (document_id,))
            entities = con.execute("SELECT id, entity_type, canonical_name FROM entities WHERE document_id=? ORDER BY id", (document_id,)).fetchall()
            for entity in entities:
                mentions = con.execute("""SELECT scene_id, page_start, page_end, context
                                         FROM entity_mentions WHERE document_id=? AND entity_id=?
                                         ORDER BY page_start, id""", (document_id, entity["id"])).fetchall()
                label, score, reasons, evidence = classify(entity["canonical_name"], entity["entity_type"], mentions)
                con.execute("""INSERT INTO character_evidence_classification
                    (document_id,entity_id,label,score,mention_count,scene_count,evidence_json,reasons_json)
                    VALUES(?,?,?,?,?,?,?,?)""", (document_id, entity["id"], label, score, len(mentions), len({m["scene_id"] for m in mentions}), json.dumps(evidence, ensure_ascii=False), json.dumps(reasons, ensure_ascii=False)))
            con.commit()
            rows = con.execute("SELECT label, COUNT(*) n FROM character_evidence_classification WHERE document_id=? GROUP BY label", (document_id,)).fetchall()
            return {str(r["label"]): int(r["n"]) for r in rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify character candidates using source evidence")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    args = parser.parse_args()
    counts = CharacterEvidenceClassifier(args.database).build(args.document_id)
    print("=== CHARACTER EVIDENCE CLASSIFIER ===")
    for key in ("validated", "probable", "uncertain", "reference", "non_character"):
        print(f"{key}: {counts.get(key, 0)}")


if __name__ == "__main__":
    main()
