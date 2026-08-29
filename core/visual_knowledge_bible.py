from __future__ import annotations
import argparse,json,re,sqlite3
from pathlib import Path

SCHEMA='''CREATE TABLE IF NOT EXISTS visual_profiles (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE, entity_id INTEGER REFERENCES entities(id) ON DELETE SET NULL, profile_type TEXT NOT NULL, canonical_name TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '', metadata_json TEXT NOT NULL DEFAULT '{}', confidence REAL NOT NULL DEFAULT 0, UNIQUE(document_id, profile_type, canonical_name)); CREATE TABLE IF NOT EXISTS visual_facts (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES visual_profiles(id) ON DELETE CASCADE, category TEXT NOT NULL, attribute TEXT NOT NULL, value TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'supported', source_type TEXT NOT NULL, source_id INTEGER, scene_id INTEGER, page_start INTEGER, page_end INTEGER, evidence TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0, extraction_method TEXT NOT NULL, UNIQUE(profile_id, category, attribute, value, source_type, source_id, scene_id)); CREATE INDEX IF NOT EXISTS idx_visual_profiles_document ON visual_profiles(document_id, profile_type); CREATE INDEX IF NOT EXISTS idx_visual_facts_profile ON visual_facts(profile_id, category, attribute); CREATE INDEX IF NOT EXISTS idx_visual_facts_scene ON visual_facts(scene_id); CREATE TABLE IF NOT EXISTS scene_visual_context (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE, scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE, character_profile_ids TEXT NOT NULL DEFAULT '[]', environment_profile_ids TEXT NOT NULL DEFAULT '[]', object_mentions TEXT NOT NULL DEFAULT '[]', continuity_json TEXT NOT NULL DEFAULT '{}', evidence_json TEXT NOT NULL DEFAULT '[]', UNIQUE(document_id, scene_id)); CREATE TABLE IF NOT EXISTS visual_objects (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE, canonical_name TEXT NOT NULL, profile_text TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0, discovery_method TEXT NOT NULL, UNIQUE(document_id, canonical_name)); CREATE TABLE IF NOT EXISTS visual_object_mentions (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE, object_id INTEGER NOT NULL REFERENCES visual_objects(id) ON DELETE CASCADE, scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE, page_start INTEGER, page_end INTEGER, evidence TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0, UNIQUE(object_id, scene_id));'''

BUILD_WORDS=r'(?:tall|short|large|small|slender|thin|lean|slight|stout|stocky|broad|muscular|powerful|robust|strong|weak|lanky|massive|heavy|delicate)'
EXPRESSION_WORDS=r'(?:smiling|smiled|laughing|laughed|angry|furious|frightened|afraid|terrified|calm|anxious|worried|sad|joyful|cheerful|stern|serious|grave|excited|astonished|surprised)'
HAIR_WORDS=r'(?:long|short|thick|thin|curly|straight|wavy|dark|black|brown|fair|blond|blonde|grey|gray|white|red|auburn)'

class VisualKnowledgeBible:
    OBJECT_TERMS={'map','compass','lantern','lamp','rope','pickaxe','axe','hammer','rifle','gun','pistol','knife','dagger','sword','bag','backpack','satchel','bottle','flask','book','journal','diary','letter','parchment','instrument','thermometer','barometer','telescope','microscope','boat','raft','carriage','wagon','vehicle','machine','key','door','bridge'}
    MANNERISM_VERBS=r'(?:walked|walks|spoke|speaks|looked|looks|kept|keeps|took|takes|carried|carries|held|holds|stood|stands|went|goes|sat|sits|smoked|smokes|laughed|laughs|smiled|smiles|watched|watches|hunted|hunts|travelled|traveled|travel|rode|rides|remained|remains|returned|returns|followed|follows|guarded|guards|observed|observes|examined|examines|congratulated|congratulates|yielded|yields|preferred|prefers|used|uses)'
    def __init__(self,database_path):self.database_path=Path(database_path)
    def build(self,document_id):
      with sqlite3.connect(self.database_path) as con:
       con.row_factory=sqlite3.Row;con.execute('PRAGMA foreign_keys=ON');con.executescript(SCHEMA);self._clear(con,document_id)
       scenes=con.execute('SELECT id,story_id,title,page_start,page_end,text FROM scenes WHERE document_id=? ORDER BY story_id,scene_order',(document_id,)).fetchall()
       canon=con.execute("SELECT cc.id,cc.identity_group_id,cc.canonical_name,cc.confidence,ig.canonical_entity_id FROM canonical_characters cc JOIN character_identity_groups ig ON ig.id=cc.identity_group_id WHERE cc.document_id=? AND cc.status IN ('confirmed','likely','singleton') ORDER BY cc.id",(document_id,)).fetchall()
       entity_profiles={}
       for cc in canon:
        eid=cc['canonical_entity_id'];pid=self._profile(con,document_id,eid,'character',cc['canonical_name'],float(cc['confidence'] or 0))
        if eid is not None:entity_profiles[int(eid)]=pid
        members=con.execute('SELECT entity_id,variant_name FROM character_identity_members WHERE document_id=? AND group_id=?',(document_id,cc['identity_group_id'])).fetchall()
        for m in members:
         eid2=int(m['entity_id']);entity_profiles[eid2]=pid
         mentions=con.execute('SELECT scene_id,page_start,page_end,context,confidence FROM entity_mentions WHERE document_id=? AND entity_id=? ORDER BY page_start,id',(document_id,eid2)).fetchall()
         for x in mentions:self._extract(con,pid,str(m['variant_name'] or cc['canonical_name']),int(x['scene_id']),int(x['page_start']),int(x['page_end']),str(x['context'] or ''),float(x['confidence'] or .5))
       objects=self._objects(con,document_id,scenes);self._scene_context(con,document_id,scenes,entity_profiles,objects);con.commit()
       return {'profiles':con.execute('SELECT COUNT(*) FROM visual_profiles WHERE document_id=?',(document_id,)).fetchone()[0],'facts':con.execute('SELECT COUNT(*) FROM visual_facts vf JOIN visual_profiles vp ON vp.id=vf.profile_id WHERE vp.document_id=?',(document_id,)).fetchone()[0],'objects':con.execute('SELECT COUNT(*) FROM visual_objects WHERE document_id=?',(document_id,)).fetchone()[0],'object_mentions':con.execute('SELECT COUNT(*) FROM visual_object_mentions WHERE document_id=?',(document_id,)).fetchone()[0],'scene_context':con.execute('SELECT COUNT(*) FROM scene_visual_context WHERE document_id=?',(document_id,)).fetchone()[0]}
    def _extract(self,con,pid,name,sid,ps,pe,text,bc):
      if not name or not text:return
      match=re.search(re.escape(name.strip()),text,re.I)
      if not match:return
      start=max(0,match.start()-220);end=min(len(text),match.end()+220);local=text[start:end]
      nr=re.escape(name.strip())
      # Only accept facts from the sentence/clause containing the source alias.
      # This is deliberately conservative: unrelated adjectives elsewhere in
      # the mention window must never become character attributes.
      clauses=[c.strip() for c in re.split(r'(?<=[.!?;])\s+|\n+',local) if c.strip()]
      for clause in clauses:
       if not re.search(r'\b'+nr+r'\b',clause,re.I):continue
       self._extract_direct(con,pid,name,sid,ps,pe,clause,bc,nr)
    def _extract_direct(self,con,pid,name,sid,ps,pe,clause,bc,nr):
      def add(cat,attr,val,method,conf=None):
       val=self._clean(val)
       if val:self._add(con,pid,cat,attr,val,'scene',None,sid,ps,pe,clause,min(.98,max(.35,bc if conf is None else conf)),method)
      # Build: explicit character copula/appearance relation OR adjective+noun
      # phrase whose noun is tied to the alias in the same clause.
      p1=re.search(rf'\b{nr}\b[^,;:!?]{{0,100}}\b(?:was|were|is|are|looked|appeared|seemed|stood)\s+(?:to be\s+)?((?:very|quite|rather|extremely|remarkably|slightly)?\s*{BUILD_WORDS})\b',clause,re.I)
      p2=re.search(rf'\b((?:very|quite|rather|extremely|remarkably|slightly)?\s*{BUILD_WORDS})\s+(?:man|woman|person|figure|fellow|hunter|astronomer|colonel|professor|doctor)\b[^,;:!?]{{0,100}}\b{nr}\b',clause,re.I)
      if p1:add('appearance','build',p1.group(1),'character_subject_build')
      elif p2:add('appearance','build',p2.group(1),'character_subject_build')
      # Numeric height: only when explicitly attached to a person/character.
      p=re.search(rf'\b{nr}\b[^,;:!?]{{0,100}}\b(?:was|were|stood|measured)\s+(?:about|nearly|approximately)?\s*([\d]+\s*(?:feet|foot|ft|inches|inch|in|metres|meters|m|cm))\b(?:\s+(?:high|tall))?',clause,re.I)
      if p:add('appearance','height',p.group(1),'character_subject_height')
      p=re.search(rf'\b([\d]+\s*(?:feet|foot|ft|inches|inch|in|metres|meters|m|cm))\s+(?:high|tall)\b[^,;:!?]{{0,100}}\b(?:man|woman|person|figure)\b[^,;:!?]{{0,100}}\b{nr}\b',clause,re.I)
      if p:add('appearance','height',p.group(1),'character_subject_height')
      # Hair / facial hair: require hair/beard terminology in the same clause.
      p=re.search(rf'\b{nr}\b[^.;!?]{{0,100}}\b({HAIR_WORDS}\s+(?:hair|locks|tresses))\b',clause,re.I)
      if p:add('appearance','hair',p.group(1),'character_subject_hair')
      p=re.search(rf'\b({HAIR_WORDS}\s+(?:hair|locks|tresses))\b[^.;!?]{{0,100}}\b{nr}\b',clause,re.I)
      if p:add('appearance','hair',p.group(1),'character_subject_hair')
      p=re.search(rf'\b{nr}\b[^.;!?]{{0,100}}\b((?:long|short|full|thick|heavy|bushy|black|brown|grey|gray|white|red)?\s*(?:beard|moustache|mustache|whiskers))\b',clause,re.I)
      if p:add('appearance','facial_hair',p.group(1),'character_subject_facial_hair')
      # Eyes / complexion / face descriptors require the anatomical noun.
      for attr,words,nouns in [('eyes',r'(?:blue|green|grey|gray|brown|black|hazel|dark|bright|deep|large|small|piercing|keen|sharp)',r'eyes?'),('complexion',r'(?:pale|fair|dark|ruddy|florid|sallow|swarthy|tanned|sunburnt|sunburned|weathered|fresh|healthy|worn|haggard)',r'(?:face|complexion|skin)'),('face',r'(?:round|oval|long|broad|thin|narrow|square|angular|handsome|ugly|rugged|stern|kind|intelligent|expressive)',r'(?:face|features|countenance)')]:
       p=re.search(rf'\b(({words})\s+{nouns})\b',clause,re.I)
       if p and re.search(r'\b'+nr+r'\b',clause[:p.start()+1]+' '+clause[p.end():],re.I):add('appearance',attr,p.group(1),f'character_subject_{attr}')
      # Clothing: capture only a bounded wearing/dressed construction.
      p=re.search(r'\b(?:wearing|wore|dressed in|clad in|attired in)\s+([^.;!?]{3,100})',clause,re.I)
      if p and re.search(r'\b'+nr+r'\b',clause,re.I):add('clothing','clothing',p.group(1),'character_subject_clothing')
      # Expression: adjective must be connected to an explicit facial/air/look term.
      p=re.search(rf'\b({EXPRESSION_WORDS})\b[^.;!?]{{0,45}}\b(?:face|features|countenance|expression|look|air|manner)\b|\b(?:face|features|countenance|expression|look|air|manner)\b[^.;!?]{{0,45}}\b({EXPRESSION_WORDS})\b',clause,re.I)
      if p and re.search(r'\b'+nr+r'\b',clause,re.I):add('expression','expression',p.group(1) or p.group(2),'character_subject_expression')
      # Mannerism: recurrence marker + real behavior verb, with the character
      # alias in the same clause. This prevents "always ready pitched" and
      # other noun/object phrases from becoming character behavior.
      p=re.search(rf'\b(?:always|often|usually|habitually|constantly)\b[^.;!?]{{0,100}}\b({self.MANNERISM_VERBS})\b[^.;!?]{{0,80}}',clause,re.I)
      if p and re.search(r'\b'+nr+r'\b',clause,re.I):
       marker=re.search(r'\b(?:always|often|usually|habitually|constantly)\b',clause,re.I)
       add('mannerism','mannerism',clause[marker.start():p.end()],'source_mannerism_local')
      # Distinctive marks: only scar/birthmark/tattoo, and require the alias
      # plus a possessive/body relation in the same clause.
      p=re.search(r'\b((?:scar|scars|birthmark|tattoo)(?:[^.;!?]{0,80}))',clause,re.I)
      if p and re.search(r'\b'+nr+r'\b',clause,re.I):add('appearance','distinctive_mark',p.group(1),'character_subject_mark')
    def _clear(self,con,d):
      con.execute('DELETE FROM scene_visual_context WHERE document_id=?',(d,));con.execute('DELETE FROM visual_object_mentions WHERE document_id=?',(d,));con.execute('DELETE FROM visual_objects WHERE document_id=?',(d,));con.execute('DELETE FROM visual_facts WHERE profile_id IN (SELECT id FROM visual_profiles WHERE document_id=?)',(d,));con.execute('DELETE FROM visual_profiles WHERE document_id=?',(d,))
    def _profile(self,con,d,e,t,n,c):con.execute('INSERT INTO visual_profiles(document_id,entity_id,profile_type,canonical_name,confidence) VALUES(?,?,?,?,?)',(d,e,t,n,c));return con.execute('SELECT last_insert_rowid()').fetchone()[0]
    def _objects(self,con,d,scenes):
      ids={}
      for s in scenes:
       text=str(s['text'] or '');words=set(re.findall(r"\b[A-Za-z][A-Za-z'-]+\b",text.lower()))
       for term in sorted(words & self.OBJECT_TERMS):
        row=con.execute('SELECT id FROM visual_objects WHERE document_id=? AND canonical_name=?',(d,term.title())).fetchone();oid=int(row[0]) if row else None
        if oid is None:con.execute('INSERT INTO visual_objects(document_id,canonical_name,confidence,discovery_method) VALUES(?,?,?,?)',(d,term.title(),.55,'visual_prop_lexicon'));oid=con.execute('SELECT last_insert_rowid()').fetchone()[0]
        ids[term.title()]=oid;ev=self._term_evidence(text,term);con.execute('INSERT OR IGNORE INTO visual_object_mentions(document_id,object_id,scene_id,page_start,page_end,evidence,confidence) VALUES(?,?,?,?,?,?,?)',(d,oid,int(s['id']),int(s['page_start']),int(s['page_end']),ev,.55))
      return ids
    def _scene_context(self,con,d,scenes,entity_profiles,objects):
      for s in scenes:
       sid=int(s['id']);chars=[]
       for r in con.execute('SELECT DISTINCT entity_id FROM entity_mentions WHERE document_id=? AND scene_id=?',(d,sid)).fetchall():
        pid=entity_profiles.get(int(r[0]));
        if pid is not None:chars.append(pid)
       con.execute('INSERT INTO scene_visual_context(document_id,scene_id,character_profile_ids,environment_profile_ids,object_mentions,continuity_json,evidence_json) VALUES(?,?,?,?,?,?,?)',(d,sid,json.dumps(sorted(set(chars))),json.dumps([]),json.dumps(list(objects.values())),json.dumps({'source_grounded':True,'unknowns_must_remain_unknown':True},sort_keys=True),'[]'))
    @staticmethod
    def _add(con,pid,cat,attr,val,st,src,sid,ps,pe,ev,conf,method):con.execute('INSERT OR IGNORE INTO visual_facts(profile_id,category,attribute,value,status,source_type,source_id,scene_id,page_start,page_end,evidence,confidence,extraction_method) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,cat,attr,val,'supported',st,src,sid,ps,pe,ev,conf,method))
    @staticmethod
    def _clean(v):return re.sub(r'\s+',' ',v.strip(" \t\r\n,.;:!?\"'()[]"))[:300]
    @staticmethod
    def _evidence(t,a,b,r=140):return t[max(0,a-r):min(len(t),b+r)].strip()
    @staticmethod
    def _term_evidence(t,term,r=180):
      m=re.search(r'\b'+re.escape(term)+r'\b',t,re.I);return VisualKnowledgeBible._evidence(t,m.start(),m.end(),r) if m else ''

def build_visual_knowledge_bible(database_path,document_id):return VisualKnowledgeBible(database_path).build(document_id)
def main():
 p=argparse.ArgumentParser();p.add_argument('database');p.add_argument('document_id',type=int);a=p.parse_args();r=build_visual_knowledge_bible(a.database,a.document_id);print('=== VISUAL KNOWLEDGE BIBLE ===');[print(f'{k}: {v}') for k,v in r.items()]
if __name__=='__main__':main()
