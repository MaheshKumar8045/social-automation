from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

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
DIALOGUE_ATTR = re.compile(r"(?:said|asked|replied|answered|cried|shouted|whispered|exclaimed|remarked|observed|continued|added|returned)\s+(?:the\s+)?(?:said\s+)?(?:[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,3})", re.I)
ACTION_VERB = re.compile(r"\b(?:entered|left|went|came|looked|saw|heard|spoke|said|asked|replied|answered|walked|ran|stood|sat|turned|smiled|laughed|wept|shouted|cried|took|gave|held|carried|followed|follow|returned|arrived|departed|climbed|descended|examined|opened|closed)\b", re.I)
PRONOUN_REF = re.compile(r"\b(?:he|she|him|her|his|hers|himself|herself)\b", re.I)


def classify(name: str, entity_type: str, mentions: list[sqlite3.Row]) -> tuple[str, float, list[str], list[str]]:
    score = 0.0
    reasons: list[str] = []
    evidence: list[str] = []
    low = name.lower().strip()
    if entity_type in {"location", "environment", "organization", "object", "event"}:
        return "non_character", 0.98, [f"upstream_{entity_type}_type"], []
    if PERSONAL_TITLE.search(name):
        score += 0.28; reasons.append("personal_title")
    contexts = [str(m["context"] or "") for m in mentions if str(m["context"] or "").strip()]
    scene_ids = {int(m["scene_id"]) for m in mentions if m["scene_id"] is not None}
    dialogue_hits = 0
    action_hits = 0
    pronoun_hits = 0
    for text in contexts:
        if DIALOGUE_ATTR.search(text):
            dialogue_hits += 1
        if ACTION_VERB.search(text):
            action_hits += 1
        if PRONOUN_REF.search(text):
            pronoun_hits += 1
    if dialogue_hits:
        score += min(0.25, dialogue_hits * 0.08); reasons.append("dialogue_attribution_context")
    if action_hits:
        score += min(0.22, action_hits * 0.035); reasons.append("human_action_context")
    if pronoun_hits:
        score += min(0.10, pronoun_hits * 0.02); reasons.append("human_pronoun_context")
    if len(mentions) >= 5:
        score += 0.12; reasons.append("strong_recurring_mentions")
    elif len(mentions) >= 2:
        score += 0.07; reasons.append("recurring_mentions")
    elif len(mentions) == 1:
        score -= 0.05; reasons.append("single_mention")
    if len(name) > 45:
        score -= 0.30; reasons.append("long_entity_name")
    if re.search(r"[-‐‑‒–—]$", name):
        score -= 0.25; reasons.append("line_break_fragment")
    if any(term in low for term in ("observatory", "institution", "newspaper", "advertiser", "journal", "gazette", "railway", "company", "university")):
        score -= 0.70; reasons.append("institution_or_publication_signal")
    score = max(0.0, min(1.0, score))
    if score >= 0.62:
        label = "validated"
    elif score >= 0.38:
        label = "probable"
    elif score >= 0.18:
        label = "uncertain"
    else:
        label = "reference"
    for m in mentions[:3]:
        text = str(m["context"] or "").strip()
        if text:
            evidence.append(text[:500])
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
                    VALUES(?,?,?,?,?,?,?,?)""", (document_id, entity["id"], label, score, len(mentions), len({m["scene_id"] for m in mentions}), json.dumps(evidence, ensure_ascii=False), json.dumps(reasons)))
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
