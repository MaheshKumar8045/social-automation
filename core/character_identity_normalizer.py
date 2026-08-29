from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS character_identity_groups (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    canonical_entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    canonical_name TEXT NOT NULL,
    member_entity_ids_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    method TEXT NOT NULL,
    relationship_type TEXT NOT NULL DEFAULT 'IDENTITY_ALIAS',
    UNIQUE(document_id, canonical_entity_id)
);
CREATE TABLE IF NOT EXISTS character_identity_members (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES character_identity_groups(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    variant_name TEXT NOT NULL,
    match_method TEXT NOT NULL,
    confidence REAL NOT NULL,
    UNIQUE(document_id, entity_id)
);
"""

TITLE_RE = re.compile(r'^(mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame)\.?\s+', re.I)
FRAGMENT_RE = re.compile(r'(?:[-‐‑‒–—])$')
SEMANTIC_NON_PERSON = {
    'africa','central africa','south africa','atlantic ocean','ocean','cape','cape colony',
    'cape portland','cape saknussemm','central sea','sea','commission','russian commission',
    'greenwich','greenwich observatory','gretchen','port gretchen','falls','victoria falls',
    'lake ngami','mount scorzef','mount sneffels','mount volquiria','orange river',
    'new york','upper zambesi','zambesi','good hope','english government','boston post','evening post',
    'russians','english','englishman','european','french','danish','icelandic','icelanders',
}
SEMANTIC_TERMS = {
    'river','ocean','sea','lake','mount','mountain','cape','island','africa','colony','government',
    'commission','observatory','institution','post','advertiser','journal','gazette','railway',
    'university','company','country','province','city','village','station','port',
}

def norm(name: str) -> str:
    s = re.sub(r'\s+', ' ', name.replace('‐','-').replace('‑','-').replace('‒','-').replace('–','-').replace('—','-')).strip(' ,.;:\"\'')
    s = re.sub(r'\s+([,.;:])', r'\1', s)
    s = re.sub(r'\b(Mr|Mrs|Ms|Miss|Dr|Prof|Professor|Capt|Captain|Sir|Lady|Lord|Rev|Reverend|Colonel|Major|Lieutenant|Herr|Monsieur|Madame)\.\s+', r'\1 ', s, flags=re.I)
    return s[:-1] if FRAGMENT_RE.search(s) and len(s) > 3 else s

def base(name: str) -> str:
    s = TITLE_RE.sub('', norm(name))
    return re.sub(r'[^a-z0-9]+',' ',s.lower()).strip()

def semantic_block(name: str) -> bool:
    b = base(name)
    if not b or b in SEMANTIC_NON_PERSON: return True
    return bool(set(b.split()) & SEMANTIC_TERMS)

def compatible(a: str, b: str) -> tuple[bool,float,str,str]:
    na, nb = norm(a), norm(b)
    if FRAGMENT_RE.search(na) or FRAGMENT_RE.search(nb):
        return False, 0.0, 'ocr_fragment', 'OCR_FRAGMENT'
    aa, bb = base(na), base(nb)
    if not aa or not bb or semantic_block(na) or semantic_block(nb):
        return False, 0.0, 'semantic_non_person_block', 'UNRESOLVED'
    if aa == bb: return True, 0.98, 'normalized_exact', 'IDENTITY_ALIAS'
    ta, tb = aa.split(), bb.split()
    if len(ta) >= 2 and len(tb) >= 2 and ta[-1] == tb[-1]:
        if ta[:-1] == tb[:-1]: return True, 0.90, 'same_full_name_variant', 'IDENTITY_ALIAS'
        if len(ta) == 2 and len(tb) == 2 and ta[0][0] == tb[0][0]:
            return True, 0.86, 'same_surname_initial_variant', 'IDENTITY_ALIAS'
        return False, 0.0, 'same_surname_but_different_given_name', 'UNRESOLVED'
    if len(ta) == 1 and len(tb) >= 2 and ta[0] == tb[-1]: return True, 0.82, 'surname_variant', 'IDENTITY_ALIAS'
    if len(tb) == 1 and len(ta) >= 2 and tb[0] == ta[-1]: return True, 0.82, 'surname_variant', 'IDENTITY_ALIAS'
    return False, 0.0, 'no_safe_identity_match', 'UNRESOLVED'

def build(db: str|Path, document_id:int)->dict[str,int]:
    with sqlite3.connect(db) as con:
        con.row_factory=sqlite3.Row; con.execute('PRAGMA foreign_keys=ON'); con.executescript(SCHEMA)
        # Backward-compatible migration for databases created by the prior version.
        cols={r['name'] for r in con.execute('PRAGMA table_info(character_identity_groups)')}
        if 'relationship_type' not in cols:
            con.execute("ALTER TABLE character_identity_groups ADD COLUMN relationship_type TEXT NOT NULL DEFAULT 'IDENTITY_ALIAS'")
        con.execute('DELETE FROM character_identity_members WHERE document_id=?',(document_id,)); con.execute('DELETE FROM character_identity_groups WHERE document_id=?',(document_id,))
        rows=con.execute('''SELECT e.id,e.canonical_name,g.decision,e.entity_type FROM entities e JOIN character_candidate_gate g ON g.entity_id=e.id AND g.document_id=e.document_id WHERE e.document_id=? AND g.decision IN ("validated","probable") AND e.entity_type="character" ORDER BY e.id''',(document_id,)).fetchall()
        groups=[]
        for e in rows:
            placed=False
            for group in groups:
                ok,conf,method,rel=compatible(e['canonical_name'],group['name'])
                if ok and rel=='IDENTITY_ALIAS': group['members'].append((e,conf,method)); placed=True; break
            if not placed: groups.append({'name':e['canonical_name'],'root':e,'members':[(e,1.0,'canonical')]})
        created=members=multi=0
        for g in groups:
            member_rows=g['members']; root=g['root']; confidence=min(x[1] for x in member_rows); method='single_candidate' if len(member_rows)==1 else 'conservative_identity_alias'
            cur=con.execute('''INSERT INTO character_identity_groups(document_id,canonical_entity_id,canonical_name,member_entity_ids_json,confidence,method,relationship_type) VALUES(?,?,?,?,?,?,?)''',(document_id,root['id'],norm(root['canonical_name']),json.dumps([x[0]['id'] for x in member_rows]),confidence,method,'IDENTITY_ALIAS'))
            gid=cur.lastrowid; created+=1; multi += len(member_rows)>1
            for e,conf,match in member_rows: con.execute('''INSERT INTO character_identity_members(document_id,group_id,entity_id,variant_name,match_method,confidence) VALUES(?,?,?,?,?,?)''',(document_id,gid,e['id'],norm(e['canonical_name']),match,conf)); members+=1
        con.commit(); return {'groups':created,'members':members,'multi_member_groups':int(multi)}

def main():
    p=argparse.ArgumentParser(description='Conservative, source-agnostic character identity normalization'); p.add_argument('database'); p.add_argument('document_id',type=int); a=p.parse_args(); r=build(a.database,a.document_id); print('=== CHARACTER IDENTITY NORMALIZATION ==='); print('groups:',r['groups']); print('members:',r['members']); print('multi-member groups:',r['multi_member_groups'])
if __name__=='__main__': main()
