from __future__ import annotations
import argparse, json, re, sqlite3
from pathlib import Path

SCHEMA='''
CREATE TABLE IF NOT EXISTS visual_fact_reconciliation (
 id INTEGER PRIMARY KEY,
 document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 canonical_character_id INTEGER NOT NULL REFERENCES canonical_characters(id) ON DELETE CASCADE,
 category TEXT NOT NULL,
 attribute TEXT NOT NULL,
 value TEXT NOT NULL,
 state_type TEXT NOT NULL,
 status TEXT NOT NULL,
 confidence REAL NOT NULL,
 scene_ids_json TEXT NOT NULL DEFAULT '[]',
 fact_ids_json TEXT NOT NULL DEFAULT '[]',
 evidence_json TEXT NOT NULL DEFAULT '[]',
 UNIQUE(document_id, canonical_character_id, category, attribute, value, state_type)
);
CREATE INDEX IF NOT EXISTS idx_visual_fact_recon_lookup ON visual_fact_reconciliation(document_id,canonical_character_id,scene_ids_json);
'''

STATEFUL={'clothing','expression','mannerism','equipment','injury','dirt','wetness','pose'}
STABLE={'age','height','build','hair','facial_hair','eyes','complexion','face','distinctive_mark'}
CONTEXTUAL={'weather','terrain','light','atmosphere','material'}

def scene_set(con, fact_ids):
    if not fact_ids:return set()
    q=','.join('?' for _ in fact_ids)
    return {int(r[0]) for r in con.execute(f'SELECT DISTINCT scene_id FROM visual_facts WHERE id IN ({q}) AND scene_id IS NOT NULL',tuple(fact_ids)).fetchall()}

def reconcile(db,doc):
 with sqlite3.connect(db) as con:
  con.row_factory=sqlite3.Row; con.execute('PRAGMA foreign_keys=ON'); con.executescript(SCHEMA)
  con.execute('DELETE FROM visual_fact_reconciliation WHERE document_id=?',(doc,))
  chars=con.execute('SELECT id,canonical_name,status,confidence FROM canonical_characters WHERE document_id=?',(doc,)).fetchall()
  out={'stable':0,'stateful':0,'contextual':0,'conflict':0,'unsupported':0}
  for ch in chars:
   facts=con.execute('''SELECT vf.* FROM visual_facts vf
      JOIN canonical_character_aliases ca ON ca.entity_id=(SELECT entity_id FROM visual_profiles WHERE id=vf.profile_id)
      WHERE ca.canonical_character_id=? ORDER BY vf.scene_id,vf.id''',(ch['id'],)).fetchall()
   groups={}
   for f in facts:
    key=(f['category'],f['attribute'],f['value'])
    groups.setdefault(key,[]).append(f)
   attrs={}
   for (cat,attr,val),fs in groups.items(): attrs.setdefault((cat,attr),[]).append((val,fs))
   for (cat,attr),vals in attrs.items():
    if attr in STATEFUL: st='stateful'
    elif attr in STABLE: st='stable'
    elif attr in CONTEXTUAL: st='contextual'
    else: st='contextual'
    distinct=len(vals)
    for val,fs in vals:
     ids=[int(f['id']) for f in fs]; scenes=sorted(scene_set(con,ids)); conf=min(float(f['confidence']) for f in fs)
     status='supported'
     if st=='stable' and distinct>1:
      status='conflict'; out['conflict']+=1
     elif not fs:
      status='unsupported'; out['unsupported']+=1
     out[st]+=1
     evidence=[{'fact_id':int(f['id']),'scene_id':f['scene_id'],'page_start':f['page_start'],'page_end':f['page_end'],'evidence':f['evidence']} for f in fs]
     con.execute('''INSERT INTO visual_fact_reconciliation(document_id,canonical_character_id,category,attribute,value,state_type,status,confidence,scene_ids_json,fact_ids_json,evidence_json)
       VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(doc,ch['id'],cat,attr,val,st,status,conf,json.dumps(scenes),json.dumps(ids),json.dumps(evidence,ensure_ascii=False)))
  con.commit(); return out

def main():
 p=argparse.ArgumentParser(description='Reconcile visual facts by stability and scene scope'); p.add_argument('database'); p.add_argument('document_id',type=int); a=p.parse_args(); r=reconcile(a.database,a.document_id); print('=== VISUAL FACT RECONCILIATION ==='); print('stable:',r['stable']); print('stateful:',r['stateful']); print('contextual:',r['contextual']); print('conflicts:',r['conflict']); print('unsupported:',r['unsupported'])
if __name__=='__main__':main()
