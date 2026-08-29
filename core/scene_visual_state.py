from __future__ import annotations
import argparse, json, sqlite3, sys
from pathlib import Path

SCHEMA='''
CREATE TABLE IF NOT EXISTS scene_visual_state_cache (
 id INTEGER PRIMARY KEY,
 document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 scene_id INTEGER NOT NULL,
 canonical_character_id INTEGER NOT NULL REFERENCES canonical_characters(id) ON DELETE CASCADE,
 state_json TEXT NOT NULL,
 UNIQUE(document_id,scene_id,canonical_character_id)
);
'''

def build_scene(db: str|Path, doc:int, scene:int)->dict:
 with sqlite3.connect(db) as con:
  con.row_factory=sqlite3.Row; con.execute('PRAGMA foreign_keys=ON'); con.executescript(SCHEMA)
  rows=con.execute('''SELECT ccp.id profile_id,ccp.canonical_character_id,ccp.canonical_name,ccp.status,ccp.confidence,
      cvf.category,cvf.attribute,cvf.value,cvf.status fact_status,cvf.confidence fact_confidence,
      cvf.source_fact_id,cvf.source_profile_id,cvf.source_entity_id,cvf.scene_id,cvf.page_start,cvf.page_end,cvf.evidence
      FROM canonical_visual_profiles ccp
      JOIN canonical_visual_facts cvf ON cvf.canonical_visual_profile_id=ccp.id
      WHERE ccp.document_id=?
        AND (cvf.scene_id=? OR (cvf.scene_id IS NULL AND cvf.category != 'source_profile'))
        AND cvf.category != 'source_profile'
      ORDER BY ccp.id,cvf.category,cvf.attribute,cvf.id''',(doc,scene)).fetchall()
  chars={}
  for r in rows:
   ch=chars.setdefault(str(r['canonical_character_id']),{'canonical_character_id':r['canonical_character_id'],'canonical_name':r['canonical_name'],'status':r['status'],'confidence':r['confidence'],'facts':[]})
   ch['facts'].append({'category':r['category'],'attribute':r['attribute'],'value':r['value'],'status':r['fact_status'],'confidence':r['fact_confidence'],'scene_id':r['scene_id'],'page_start':r['page_start'],'page_end':r['page_end'],'source_fact_id':r['source_fact_id'],'source_profile_id':r['source_profile_id'],'source_entity_id':r['source_entity_id'],'evidence':r['evidence']})
  state={'document_id':doc,'scene_id':scene,'unknowns_must_remain_unknown':True,'characters':list(chars.values())}
  con.execute('DELETE FROM scene_visual_state_cache WHERE document_id=? AND scene_id=?',(doc,scene))
  for ch in state['characters']:
   con.execute('INSERT INTO scene_visual_state_cache(document_id,scene_id,canonical_character_id,state_json) VALUES(?,?,?,?)',(doc,scene,ch['canonical_character_id'],json.dumps(ch,ensure_ascii=False)))
  con.commit(); return state

def main():
 p=argparse.ArgumentParser(description='Return source-grounded scene-effective visual state'); p.add_argument('database'); p.add_argument('document_id',type=int); p.add_argument('scene_id',type=int); a=p.parse_args();
 if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
 print(json.dumps(build_scene(a.database,a.document_id,a.scene_id),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
