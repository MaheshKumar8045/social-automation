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

TITLE_RE = re.compile(r'^(mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame)\\.?\\s+', re.I)
STOP = {'the','a','an','and','or','but','here','why','during','perhaps','such','look','was','besides','very','never','thus','come','two','good','about','towards','had','certainly','english','earth','orange','south','new','russian','central','atlantic','evening','post','boston'}

def norm(name: str) -> str:
    s = re.sub(r'\\s+', ' ', name.replace('‐','-').replace('‑','-').replace('‒','-').replace('–','-').replace('—','-')).strip(' ,.;:\"\'')
    s = re.sub(r'\\s+([,.;:])', r'\\1', s)
    s = re.sub(r'\\b(Mr|Mrs|Ms|Miss|Dr|Prof|Professor|Capt|Captain|Sir|Lady|Lord|Rev|Reverend|Colonel|Major|Lieutenant|Herr|Monsieur|Madame)\\.\\s+', r'\\1 ', s, flags=re.I)
    if s.endswith('-') and len(s)>3: s=s[:-1]
    return s

def base(name: str) -> str:
    s = TITLE_RE.sub('', norm(name))
    return re.sub(r'[^a-z0-9]+',' ',s.lower()).strip()

def compatible(a: str, b: str) -> tuple[bool,float,str]:
    aa,bb=base(a),base(b)
    if not aa or not bb or aa in STOP or bb in STOP: return False,0,'blocked_token'
    if aa==bb: return True,0.98,'normalized_exact'
    ta,tb=aa.split(),bb.split()
    if len(ta)>=2 and len(tb)>=2 and ta[-1]==tb[-1] and (ta[0]==tb[0] or ta[0] in tb or tb[0] in ta):
        return True,0.90,'same_surname_given_name_variant'
    if len(ta)==1 and len(tb)>=2 and ta[0] in tb:
        return True,0.84,'surname_or_given_name_variant'
    if len(tb)==1 and len(ta)>=2 and tb[0] in ta:
        return True,0.84,'surname_or_given_name_variant'
    return False,0,''

def build(db: str|Path, document_id:int)->dict[str,int]:
    with sqlite3.connect(db) as con:
        con.row_factory=sqlite3.Row; con.execute('PRAGMA foreign_keys=ON'); con.executescript(SCHEMA)
        con.execute('DELETE FROM character_identity_members WHERE document_id=?',(document_id,)); con.execute('DELETE FROM character_identity_groups WHERE document_id=?',(document_id,))
        rows=con.execute('''SELECT e.id,e.canonical_name,g.decision,g.score,e.entity_type,e.profile_text FROM entities e JOIN character_candidate_gate g ON g.entity_id=e.id AND g.document_id=e.document_id WHERE e.document_id=? AND g.decision IN ("validated","probable") AND e.entity_type="character" ORDER BY e.id''',(document_id,)).fetchall()
        groups=[]
        for e in rows:
            placed=False
            for group in groups:
                ok,conf,method=compatible(e['canonical_name'],group['name'])
                if ok:
                    group['members'].append((e,conf,method)); placed=True; break
            if not placed: groups.append({'name':e['canonical_name'],'root':e,'members':[(e,1.0,'canonical')]})
        created=0; members=0
        for g in groups:
            member_rows=g['members']; root=g['root']; confidence=min(x[1] for x in member_rows)
            if len(member_rows)==1 and confidence==1.0: method='single_candidate'
            else: method='conservative_name_variant'
            cur=con.execute('INSERT INTO character_identity_groups(document_id,canonical_entity_id,canonical_name,member_entity_ids_json,confidence,method) VALUES(?,?,?,?,?,?)',(document_id,root['id'],norm(root['canonical_name']),json.dumps([x[0]['id'] for x in member_rows]),confidence,method))
            gid=cur.lastrowid; created+=1
            for e,conf,match in member_rows:
                con.execute('INSERT INTO character_identity_members(document_id,group_id,entity_id,variant_name,match_method,confidence) VALUES(?,?,?,?,?,?)',(document_id,gid,e['id'],norm(e['canonical_name']),match,conf)); members+=1
        con.commit(); return {'groups':created,'members':members}

def main():
    p=argparse.ArgumentParser(); p.add_argument('database'); p.add_argument('document_id',type=int); a=p.parse_args(); r=build(a.database,a.document_id); print('=== CHARACTER IDENTITY NORMALIZATION ==='); print('groups:',r['groups']); print('members:',r['members'])
if __name__=='__main__': main()
