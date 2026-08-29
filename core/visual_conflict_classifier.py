from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path

SCHEMA='''
CREATE TABLE IF NOT EXISTS visual_conflict_classification (
 id INTEGER PRIMARY KEY,
 document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 canonical_character_id INTEGER NOT NULL REFERENCES canonical_characters(id) ON DELETE CASCADE,
 category TEXT NOT NULL,
 attribute TEXT NOT NULL,
 value TEXT NOT NULL,
 classification TEXT NOT NULL,
 confidence REAL NOT NULL,
 reason TEXT NOT NULL,
 scene_ids_json TEXT NOT NULL DEFAULT '[]',
 fact_ids_json TEXT NOT NULL DEFAULT '[]',
 UNIQUE(document_id,canonical_character_id,category,attribute,value)
);
'''

def classify(db: str|Path, doc:int)->dict[str,int]:
 with sqlite3.connect(db) as con:
  con.row_factory=sqlite3.Row; con.execute('PRAGMA foreign_keys=ON'); con.executescript(SCHEMA)
  con.execute('DELETE FROM visual_conflict_classification WHERE document_id=?',(doc,))
  rows=con.execute('''SELECT * FROM visual_fact_reconciliation WHERE document_id=? AND status='conflict' ORDER BY canonical_character_id,attribute,id''',(doc,)).fetchall()
  out={'low_evidence':0,'scene_scoped':0,'strong_conflict':0}
  for r in rows:
   conf=float(r['confidence']); scenes=json.loads(r['scene_ids_json'] or '[]'); facts=json.loads(r['fact_ids_json'] or '[]')
   if conf < 0.60:
    cls='low_evidence'; reason='weak visual extraction confidence; preserve source fact but do not treat as a character contradiction'
   else:
    # A stable attribute occurring in disjoint scenes can be a source/state
    # distinction; keep it visible for review rather than collapsing it.
    all_scene_ids=set()
    for rr in con.execute('''SELECT scene_ids_json FROM visual_fact_reconciliation WHERE document_id=? AND canonical_character_id=? AND attribute=? AND status='conflict' ''',(doc,r['canonical_character_id'],r['attribute'])).fetchall():
     all_scene_ids.update(json.loads(rr['scene_ids_json'] or '[]'))
    if len(scenes) and len(all_scene_ids)>len(scenes):
     cls='scene_scoped'; reason='higher-confidence alternatives are confined to different source scenes; retain as scoped evidence'
    else:
     cls='strong_conflict'; reason='higher-confidence incompatible stable attribute remains unresolved by available scene evidence'
   out[cls]+=1
   con.execute('''INSERT INTO visual_conflict_classification(document_id,canonical_character_id,category,attribute,value,classification,confidence,reason,scene_ids_json,fact_ids_json) VALUES(?,?,?,?,?,?,?,?,?,?)''',(doc,r['canonical_character_id'],r['category'],r['attribute'],r['value'],cls,conf,reason,r['scene_ids_json'],r['fact_ids_json']))
  con.commit(); return out

def main():
 p=argparse.ArgumentParser(description='Classify visual conflicts by evidence strength and scene scope'); p.add_argument('database'); p.add_argument('document_id',type=int); a=p.parse_args(); r=classify(a.database,a.document_id); print('=== VISUAL CONFLICT CLASSIFICATION ==='); [print(k+':',r[k]) for k in ('low_evidence','scene_scoped','strong_conflict')]
if __name__=='__main__': main()
