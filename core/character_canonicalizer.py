from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path

SCHEMA='''
CREATE TABLE IF NOT EXISTS canonical_characters (
 id INTEGER PRIMARY KEY,
 document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 identity_group_id INTEGER NOT NULL REFERENCES character_identity_groups(id) ON DELETE CASCADE,
 canonical_name TEXT NOT NULL,
 confidence REAL NOT NULL,
 status TEXT NOT NULL,
 UNIQUE(document_id, identity_group_id)
);
CREATE TABLE IF NOT EXISTS canonical_character_aliases (
 id INTEGER PRIMARY KEY,
 canonical_character_id INTEGER NOT NULL REFERENCES canonical_characters(id) ON DELETE CASCADE,
 entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
 alias TEXT NOT NULL,
 relationship TEXT NOT NULL,
 confidence REAL NOT NULL,
 UNIQUE(canonical_character_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_canonical_characters_doc ON canonical_characters(document_id,status);
'''

def build(db: str|Path, doc:int)->dict[str,int]:
 with sqlite3.connect(db) as con:
  con.row_factory=sqlite3.Row; con.execute('PRAGMA foreign_keys=ON'); con.executescript(SCHEMA)
  con.execute('DELETE FROM canonical_character_aliases WHERE canonical_character_id IN (SELECT id FROM canonical_characters WHERE document_id=?)',(doc,))
  con.execute('DELETE FROM canonical_characters WHERE document_id=?',(doc,))
  groups=con.execute('''SELECT g.id,g.canonical_entity_id,g.canonical_name,g.confidence,
      COALESCE(r.relationship,'unresolved') relationship, COALESCE(r.confidence,0) rconf
      FROM character_identity_groups g
      LEFT JOIN mention_identity_resolution r ON r.group_id=g.id AND r.document_id=g.document_id
      WHERE g.document_id=? ORDER BY g.id''',(doc,)).fetchall()
  counts={'confirmed':0,'likely':0,'singleton':0,'excluded':0}
  for g in groups:
   members=con.execute('SELECT entity_id,variant_name,confidence FROM character_identity_members WHERE document_id=? AND group_id=?',(doc,g['id'])).fetchall()
   if g['relationship']=='confirmed_alias': status='confirmed'; counts['confirmed']+=1
   elif g['relationship']=='likely_alias': status='likely'; counts['likely']+=1
   elif len(members)==1: status='singleton'; counts['singleton']+=1
   else: counts['excluded']+=1; continue
   conf=min(float(g['confidence']), max(float(g['rconf']),0.5) if g['relationship']!='unresolved' else float(g['confidence']))
   cur=con.execute('INSERT INTO canonical_characters(document_id,identity_group_id,canonical_name,confidence,status) VALUES(?,?,?,?,?)',(doc,g['id'],g['canonical_name'],conf,status))
   cid=cur.lastrowid
   for m in members:
    rel='canonical' if m['entity_id']==g['canonical_entity_id'] else ('alias' if status in {'confirmed','likely'} else 'variant')
    con.execute('INSERT INTO canonical_character_aliases(canonical_character_id,entity_id,alias,relationship,confidence) VALUES(?,?,?,?,?)',(cid,m['entity_id'],m['variant_name'],rel,m['confidence']))
  con.commit(); return counts

def main():
 p=argparse.ArgumentParser(); p.add_argument('database'); p.add_argument('document_id',type=int); a=p.parse_args(); r=build(a.database,a.document_id); print('=== CANONICAL CHARACTER LAYER ==='); [print(k+':',r[k]) for k in ('confirmed','likely','singleton','excluded')]
if __name__=='__main__': main()
