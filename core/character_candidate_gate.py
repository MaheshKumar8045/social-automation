from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS character_candidate_gate (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    score REAL NOT NULL,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(document_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_character_candidate_gate_doc_decision
ON character_candidate_gate(document_id, decision);
"""

STOPWORDS = set('a an and are as at be been but by can could did do does for from had has have he her here him his how i if in is it its just like many more most my never no not now of on one or only or perhaps quite rather said see she so some such than that the their them then there these they this those through to too two under up us very was we were what when where which while why will with without would you your'.split())
NON_PERSON = set('african english englishman european french icelandic icelanders russians danish makololos makololo bochjesmen queen earth orange reykjawik sneffels'.split())
TITLE_ONLY = re.compile(r'^(?:mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame)\.?$', re.I)
PERSON_TITLE = re.compile(r'^(?:mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame)\.?\s+', re.I)
NAME_WORD = re.compile(r"^[A-Z][A-Za-z'’-]+$")


def norm(name: str) -> str:
    s = re.sub(r'\s+', ' ', name.replace('‐','-').replace('‑','-').replace('‒','-').replace('–','-').replace('—','-')).strip(' ,.;:\"\'')
    s = re.sub(r'\s+([,.;:])', r'\1', s)
    if s.endswith('-') and len(s) > 3:
        s = s[:-1]
    return s


def gate(name: str, entity_type: str, mentions: list[sqlite3.Row]) -> tuple[str, float, list[str]]:
    n = norm(name)
    low = n.lower()
    reasons: list[str] = []
    if entity_type != 'character':
        return 'non_character', 1.0, ['upstream_type_not_character']
    if TITLE_ONLY.match(n):
        return 'non_character', 1.0, ['title_only']
    if low in STOPWORDS or low in NON_PERSON:
        return 'non_character', 1.0, ['common_word_or_demographic_term']
    if len(n) < 3 or len(n) > 45:
        return 'review', 0.9, ['name_length_anomaly']
    words = n.replace('-', ' ').split()
    title = bool(PERSON_TITLE.match(n))
    bare_words = [w.strip('.') for w in words if w.lower() not in {'mr','mrs','ms','miss','dr','prof','professor','capt','captain','sir','lady','lord','rev','reverend','colonel','major','lieutenant','herr','monsieur','madame'}]
    if not all(NAME_WORD.match(w) for w in bare_words if w):
        return 'review', 0.65, ['non_name_token']
    contexts = [str(m['context'] or '') for m in mentions]
    exact_hits = sum(1 for x in contexts if n.lower() in x.lower())
    scene_count = len({m['scene_id'] for m in mentions if m['scene_id'] is not None})
    score = 0.25
    if title: score += 0.25; reasons.append('personal_title')
    if len(bare_words) >= 2: score += 0.15; reasons.append('multiword_person_name')
    if exact_hits >= 2: score += 0.15; reasons.append('name_repeated_in_context')
    if len(mentions) >= 3: score += 0.10; reasons.append('recurring_mentions')
    if scene_count >= 2: score += 0.10; reasons.append('multi_scene_presence')
    if any(w.lower() in STOPWORDS for w in bare_words): score -= 0.45; reasons.append('stopword_name_component')
    if n.endswith('-'): score -= 0.4; reasons.append('line_break_fragment')
    score = max(0.0, min(1.0, score))
    if score >= 0.75: decision = 'validated'
    elif score >= 0.48: decision = 'probable'
    else: decision = 'review'
    return decision, score, reasons


def build(db: str | Path, document_id: int) -> dict[str, int]:
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        con.executescript(SCHEMA)
        con.execute('DELETE FROM character_candidate_gate WHERE document_id=?', (document_id,))
        entities = con.execute('SELECT id, entity_type, canonical_name FROM entities WHERE document_id=? ORDER BY id', (document_id,)).fetchall()
        for e in entities:
            mentions = con.execute('SELECT scene_id, context FROM entity_mentions WHERE document_id=? AND entity_id=? ORDER BY page_start, id', (document_id, e['id'])).fetchall()
            decision, score, reasons = gate(e['canonical_name'], e['entity_type'], mentions)
            con.execute('INSERT INTO character_candidate_gate(document_id,entity_id,decision,normalized_name,score,reasons_json) VALUES(?,?,?,?,?,?)', (document_id,e['id'],decision,norm(e['canonical_name']),score,json.dumps(reasons)))
        con.commit()
        return {r['decision']: int(r['n']) for r in con.execute('SELECT decision, COUNT(*) n FROM character_candidate_gate WHERE document_id=? GROUP BY decision', (document_id,)).fetchall()}


def main() -> None:
    p = argparse.ArgumentParser(description='Conservative character candidate gate')
    p.add_argument('database'); p.add_argument('document_id', type=int)
    a = p.parse_args(); counts = build(a.database, a.document_id)
    print('=== CHARACTER CANDIDATE GATE ===')
    for k in ('validated','probable','review','non_character'):
        print(f'{k}: {counts.get(k,0)}')

if __name__ == '__main__': main()
