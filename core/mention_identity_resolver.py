from __future__ import annotations
import argparse, json, re, sqlite3
from pathlib import Path

SCHEMA='''
CREATE TABLE IF NOT EXISTS mention_identity_resolution (
 id INTEGER PRIMARY KEY,
 document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 group_id INTEGER NOT NULL REFERENCES character_identity_groups(id) ON DELETE CASCADE,
 relationship TEXT NOT NULL,
 confidence REAL NOT NULL,
 evidence_json TEXT NOT NULL DEFAULT '[]',
 UNIQUE(document_id, group_id)
);
'''
TITLE_RE=re.compile(r'^(?:mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame)\.?\s+',re.I)

def base(s): return re.sub(r'[^a-z0-9 ]+',' ',TITLE_RE.sub('',s or '').lower()).strip()
def tokens(s): return base(s).split()
def context_names(con, doc, entity_id):
 return [r for r in con.execute('SELECT scene_id,page_start,page_end,context FROM entity_mentions WHERE document_id=? AND entity_id=? ORDER BY page_start,id',(doc,entity_id)).fetchall()]
def resolve(db,doc):
 with sqlite3.connect(db) as con:
  con.row_factory=sqlite3.Row; con.execute('PRAGMA foreign_keys=ON'); con.executescript(SCHEMA)
  con.execute('DELETE FROM mention_identity_resolution WHERE document_id=?',(doc,))
  groups=con.execute('SELECT id,canonical_name FROM character_identity_groups WHERE document_id=? ORDER BY id',(doc,)).fetchall()
  out={'confirmed_alias':0,'likely_alias':0,'ocr_fragment':0,'unresolved':0}
  for g in groups:
   members=con.execute('SELECT entity_id,variant_name,match_method FROM character_identity_members WHERE document_id=? AND group_id=? ORDER BY id',(doc,g['id'])).fetchall()
   if len(members)<2: continue
   names=[m['variant_name'] for m in members]; evidence=[]
   # Reject obvious OCR-only variants as identity proof.
   if any(re.search(r'[-‐‑‒–—]$',n.strip()) for n in names):
    rel='ocr_fragment'; conf=.99; evidence=['hyphenated source form requires reconstruction: '+n for n in names if n.strip().endswith('-')]
   else:
    all_mentions=[]
    for m in members:
     for x in context_names(con,doc,m['entity_id']): all_mentions.append((m['entity_id'],m['variant_name'],x))
    same_scene=set()
    for _,n,x in all_mentions:
     if x['scene_id'] is not None: same_scene.add(int(x['scene_id']))
    # Strong alias evidence: normalized full forms differ only by title, or a
    # bare surname is used where the full surname occurs in the same scenes.
    bases=[base(n) for n in names]
    exact_base=len(set(bases))==1
    surname_variant=False
    if len(bases)==2:
     a,b=bases
     ta,tb=a.split(),b.split()
     surname_variant=(len(ta)==1 and len(tb)>=2 and ta[0]==tb[-1]) or (len(tb)==1 and len(ta)>=2 and tb[0]==ta[-1])
    if exact_base:
     rel='confirmed_alias'; conf=.99; evidence=['same normalized personal name: '+' | '.join(names)]
    elif surname_variant:
     # Require overlapping scene evidence; this avoids treating every surname
     # occurrence as the same person.
     scene_sets=[]
     for m in members:
      scene_sets.append({int(x['scene_id']) for x in context_names(con,doc,m['entity_id']) if x['scene_id'] is not None})
     overlap=set.intersection(*scene_sets) if scene_sets else set()
     if overlap:
      rel='likely_alias'; conf=.88; evidence=['same surname with overlapping scenes',f'overlap_scenes={len(overlap)}']
     else:
      rel='unresolved'; conf=0.0; evidence=['surname-only match without overlapping scene evidence']
    else:
     rel='unresolved'; conf=0.0; evidence=['different name components; source evidence required: '+' | '.join(names)]
   con.execute('INSERT INTO mention_identity_resolution(document_id,group_id,relationship,confidence,evidence_json) VALUES(?,?,?,?,?)',(doc,g['id'],rel,conf,json.dumps(evidence,ensure_ascii=False)))
   out[rel]+=1
  con.commit(); return out

def main():
 p=argparse.ArgumentParser(); p.add_argument('database'); p.add_argument('document_id',type=int); a=p.parse_args(); r=resolve(a.database,a.document_id); print('=== MENTION IDENTITY RESOLUTION ==='); [print(k+':',r[k]) for k in ('confirmed_alias','likely_alias','ocr_fragment','unresolved')]
if __name__=='__main__': main()
