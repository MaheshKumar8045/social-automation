from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS character_identity_evidence (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES character_identity_groups(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(document_id, group_id, relationship)
);
CREATE INDEX IF NOT EXISTS idx_character_identity_evidence_doc
ON character_identity_evidence(document_id, relationship);
"""

TITLE_RE = re.compile(r'^(?:mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame)\.?\s+', re.I)


def clean(s: str) -> str:
    s = re.sub(r'\s+', ' ', s or '').strip()
    return s


def build(db: str | Path, document_id: int) -> dict[str, int]:
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        con.executescript(SCHEMA)
        con.execute('DELETE FROM character_identity_evidence WHERE document_id=?', (document_id,))
        groups = con.execute('''SELECT id, canonical_entity_id, canonical_name
                               FROM character_identity_groups
                               WHERE document_id=? ORDER BY id''', (document_id,)).fetchall()
        counts = {'identity_alias': 0, 'ocr_fragment': 0, 'unresolved': 0}
        for g in groups:
            members = con.execute('''SELECT e.id,e.canonical_name,m.variant_name,m.match_method
                                     FROM character_identity_members m
                                     JOIN entities e ON e.id=m.entity_id
                                     WHERE m.document_id=? AND m.group_id=? ORDER BY m.id''', (document_id, g['id'])).fetchall()
            if len(members) <= 1:
                continue
            names = [clean(m['variant_name']) for m in members]
            fragments = [n for n in names if n.endswith('-') or len(TITLE_RE.sub('', n).split()) == 1 and len(n) <= 4]
            if fragments:
                relationship = 'ocr_fragment'
                confidence = 0.99
                evidence = ['short or hyphenated OCR fragment: ' + n for n in fragments]
            elif all(m['match_method'] in {'normalized_exact','same_full_name_variant','surname_variant','same_surname_initial_variant'} for m in members):
                relationship = 'identity_alias'
                confidence = min(float(con.execute('SELECT confidence FROM character_identity_members WHERE id=?',(m['id'],)).fetchone()[0]) for m in members)
                evidence = ['name-form compatibility: ' + ' | '.join(names)]
            else:
                relationship = 'unresolved'
                confidence = 0.0
                evidence = ['insufficient evidence for identity merge: ' + ' | '.join(names)]
            con.execute('INSERT INTO character_identity_evidence(document_id,group_id,relationship,confidence,evidence_json) VALUES(?,?,?,?,?)', (document_id,g['id'],relationship,confidence,json.dumps(evidence,ensure_ascii=False)))
            counts[relationship] += 1
        con.commit()
        return counts


def main() -> None:
    p=argparse.ArgumentParser(description='Audit identity groups using evidence categories')
    p.add_argument('database'); p.add_argument('document_id',type=int)
    a=p.parse_args(); r=build(a.database,a.document_id)
    print('=== CHARACTER IDENTITY EVIDENCE ===')
    for k in ('identity_alias','ocr_fragment','unresolved'):
        print(f'{k}: {r[k]}')

if __name__=='__main__': main()
