from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA = '''CREATE TABLE IF NOT EXISTS visual_profiles (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE, entity_id INTEGER REFERENCES entities(id) ON DELETE SET NULL, profile_type TEXT NOT NULL, canonical_name TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '', metadata_json TEXT NOT NULL DEFAULT '{}', confidence REAL NOT NULL DEFAULT 0, UNIQUE(document_id, profile_type, canonical_name)); CREATE TABLE IF NOT EXISTS visual_facts (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES visual_profiles(id) ON DELETE CASCADE, category TEXT NOT NULL, attribute TEXT NOT NULL, value TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'supported', source_type TEXT NOT NULL, source_id INTEGER, scene_id INTEGER, page_start INTEGER, page_end INTEGER, evidence TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0, extraction_method TEXT NOT NULL, UNIQUE(profile_id, category, attribute, value, source_type, source_id, scene_id)); CREATE INDEX IF NOT EXISTS idx_visual_profiles_document ON visual_profiles(document_id, profile_type); CREATE INDEX IF NOT EXISTS idx_visual_facts_profile ON visual_facts(profile_id, category, attribute); CREATE INDEX IF NOT EXISTS idx_visual_facts_scene ON visual_facts(scene_id); CREATE TABLE IF NOT EXISTS scene_visual_context (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE, scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE, character_profile_ids TEXT NOT NULL DEFAULT '[]', environment_profile_ids TEXT NOT NULL DEFAULT '[]', object_mentions TEXT NOT NULL DEFAULT '[]', continuity_json TEXT NOT NULL DEFAULT '{}', evidence_json TEXT NOT NULL DEFAULT '[]', UNIQUE(document_id, scene_id)); CREATE TABLE IF NOT EXISTS visual_objects (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE, canonical_name TEXT NOT NULL, profile_text TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0, discovery_method TEXT NOT NULL, UNIQUE(document_id, canonical_name)); CREATE TABLE IF NOT EXISTS visual_object_mentions (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE, object_id INTEGER NOT NULL REFERENCES visual_objects(id) ON DELETE CASCADE, scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE, page_start INTEGER, page_end INTEGER, evidence TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0, UNIQUE(object_id, scene_id));'''


class VisualKnowledgeBible:
    """Build an evidence-first visual continuity layer from source text.

    Character visual facts are accepted only when the matched visual phrase has
    a local syntactic/possessive relationship to the character mention. A
    nearby adjective alone is never sufficient. Unknown attributes remain
    unknown rather than being inferred from unrelated context.
    """

    CHARACTER_PATTERNS = {
        "age": [re.compile(r"\b(?:aged|age[d]?|about|nearly|approximately)\s+(\d{1,3})\s*(?:years?|yrs?)\b", re.I), re.compile(r"\b(\d{1,3})[- ]year[- ]old\b", re.I)],
        "height": [re.compile(r"\b(?:about|nearly|approximately|some)\s+([\d'\".,]+\s*(?:feet|foot|ft|inches|inch|in|metres|meters|m|cm))\b", re.I), re.compile(r"\b([\d]+\s*(?:feet|foot|ft|inches|inch|in|metres|meters|m|cm))\s+(?:high|tall)\b", re.I)],
        "build": [re.compile(r"\b((?:very|quite|rather|extremely|remarkably|slightly)?\s*(?:tall|short|large|small|slender|thin|lean|slight|stout|stocky|broad|muscular|powerful|robust|strong|weak|lanky|massive|heavy|delicate))\b", re.I)],
        "hair": [re.compile(r"\b((?:long|short|thick|thin|curly|straight|wavy|dark|black|brown|fair|blond|blonde|grey|gray|white|red|auburn)\s+(?:hair|locks|tresses))\b", re.I), re.compile(r"\b(?:hair|beard|moustache|mustache)\s+(?:was|were|is|of)\s+([^.;,]{2,50})", re.I)],
        "facial_hair": [re.compile(r"\b((?:long|short|full|thick|heavy|bushy|black|brown|grey|gray|white|red)?\s*(?:beard|moustache|mustache|whiskers))\b", re.I)],
        "eyes": [re.compile(r"\b((?:blue|green|grey|gray|brown|black|hazel|dark|bright|deep|large|small|piercing|keen|sharp)\s+eyes?)\b", re.I)],
        "complexion": [re.compile(r"\b((?:pale|fair|dark|ruddy|florid|sallow|swarthy|tanned|sunburnt|sunburned|weathered|fresh|healthy|worn|haggard)\s+(?:face|complexion|skin))\b", re.I)],
        "face": [re.compile(r"\b((?:round|oval|long|broad|thin|narrow|square|angular|handsome|ugly|rugged|stern|kind|intelligent|expressive)\s+(?:face|features|countenance))\b", re.I)],
        "distinctive_mark": [re.compile(r"\b(?:scar|scars|mark|marks|birthmark|tattoo|wound|injury)\b[^.;]{0,100}", re.I)],
        "clothing": [re.compile(r"\b(?:wearing|wore|dressed in|clad in|attired in)\s+([^.;]{3,140})", re.I), re.compile(r"\b((?:coat|cloak|jacket|shirt|trousers|pants|dress|skirt|boots|shoes|hat|cap|helmet|gloves|scarf|belt|uniform|suit|vest|waistcoat|tunic|gown|sleeves?))\b", re.I)],
        "expression": [re.compile(r"\b((?:smiling|smiled|laughing|laughed|angry|furious|frightened|afraid|terrified|calm|anxious|worried|sad|joyful|cheerful|stern|serious|grave|excited|astonished|surprised|pale with fear))\b", re.I)],
        "mannerism": [re.compile(r"\b((?:habitually|always|often|usually|constantly)\s+[^.;]{3,120})", re.I)],
    }
    ENV_PATTERNS = {
        "weather": re.compile(r"\b((?:cold|hot|warm|freezing|icy|snowy|stormy|windy|foggy|misty|rainy|raining|sunny|dark|cloudy|clear|humid|dry)\s+(?:weather|air|wind|sky|day|night))\b", re.I),
        "terrain": re.compile(r"\b((?:steep|rocky|rugged|rough|smooth|flat|narrow|wide|deep|vast|dark|icy|snow-covered|snowy|volcanic|sandy|muddy|forested|barren)\s+(?:mountain|mountains|valley|plain|plains|road|shore|bank|banks|cave|cavern|tunnel|gallery|shaft|coast|island|islands|ground|terrain))\b", re.I),
        "light": re.compile(r"\b((?:bright|dim|dark|faint|brilliant|dazzling|sunlit|moonlit|shadowy|gloomy|red|blue|golden)\s+(?:light|glow|illumination|daylight|sunlight|moonlight))\b", re.I),
        "atmosphere": re.compile(r"\b((?:silent|quiet|noisy|oppressive|eerie|mysterious|terrible|terrific|beautiful|magnificent|desolate|lonely|cheerful|pleasant|stifling|suffocating|humid|damp|dry)\s+(?:atmosphere|air|place|scene|silence|stillness))\b", re.I),
        "material": re.compile(r"\b((?:rock|stone|ice|snow|sand|water|lava|basalt|granite|clay|wooden|wood|metal|iron|steel|glass|leather|brick|marble)\s+(?:wall|walls|floor|floors|ceiling|rock|rocks|ground|surface|door|doors|bridge|structure|material))\b", re.I),
    }
    OBJECT_TERMS = {"map","compass","lantern","lamp","rope","pickaxe","axe","hammer","rifle","gun","pistol","knife","dagger","sword","bag","backpack","satchel","bottle","flask","book","journal","diary","letter","parchment","instrument","thermometer","barometer","telescope","microscope","boat","raft","carriage","wagon","vehicle","machine","key","door","bridge"}

    def __init__(self, database_path: str | Path): self.database_path = Path(database_path)

    def build(self, document_id: int) -> dict[str, int]:
        with sqlite3.connect(self.database_path) as con:
            con.row_factory = sqlite3.Row; con.execute('PRAGMA foreign_keys=ON'); con.executescript(SCHEMA); self._clear_document(con, document_id)
            entities = con.execute('SELECT id,entity_type,canonical_name,profile_text,confidence FROM entities WHERE document_id=? ORDER BY id',(document_id,)).fetchall()
            scenes = con.execute('SELECT id,story_id,title,page_start,page_end,text FROM scenes WHERE document_id=? ORDER BY story_id,scene_order',(document_id,)).fetchall()
            entity_profiles={}
            for e in entities:
                ptype=self._profile_type(e['entity_type'])
                if ptype is None: continue
                pid=self._profile(con,document_id,int(e['id']),ptype,e['canonical_name'],float(e['confidence'] or 0)); entity_profiles[int(e['id'])]=pid
                mentions=con.execute('''SELECT em.scene_id,em.page_start,em.page_end,em.context,em.confidence FROM entity_mentions em WHERE em.document_id=? AND em.entity_id=? ORDER BY em.page_start,em.id''',(document_id,int(e['id']))).fetchall()
                for m in mentions:
                    text=str(m['context'] or ''); self._extract_character_facts(con,pid,e['canonical_name'],int(m['scene_id']),int(m['page_start']),int(m['page_end']),text,float(m['confidence'] or .5))
                if e['profile_text']: self._add_fact(con,pid,'source_profile','profile_evidence',str(e['profile_text']),'entity',int(e['id']),None,None,None,str(e['profile_text']),float(e['confidence'] or .5),'existing_entity_evidence')
            object_ids=self._build_objects(con,document_id,scenes); self._build_scene_context(con,document_id,scenes,entity_profiles,object_ids); self._build_environment_facts(con,document_id,scenes,entity_profiles); con.commit()
            return {k:int(v) for k,v in {'profiles':con.execute('SELECT COUNT(*) FROM visual_profiles WHERE document_id=?',(document_id,)).fetchone()[0],'facts':con.execute('SELECT COUNT(*) FROM visual_facts vf JOIN visual_profiles vp ON vp.id=vf.profile_id WHERE vp.document_id=?',(document_id,)).fetchone()[0],'objects':con.execute('SELECT COUNT(*) FROM visual_objects WHERE document_id=?',(document_id,)).fetchone()[0],'object_mentions':con.execute('SELECT COUNT(*) FROM visual_object_mentions WHERE document_id=?',(document_id,)).fetchone()[0],'scene_context':con.execute('SELECT COUNT(*) FROM scene_visual_context WHERE document_id=?',(document_id,)).fetchone()[0]}.items()}

    @staticmethod
    def _clear_document(con,document_id):
        con.execute('DELETE FROM scene_visual_context WHERE document_id=?',(document_id,)); con.execute('DELETE FROM visual_object_mentions WHERE document_id=?',(document_id,)); con.execute('DELETE FROM visual_objects WHERE document_id=?',(document_id,)); con.execute('DELETE FROM visual_facts WHERE profile_id IN (SELECT id FROM visual_profiles WHERE document_id=?)',(document_id,)); con.execute('DELETE FROM visual_profiles WHERE document_id=?',(document_id,))
    @staticmethod
    def _profile_type(entity_type): return 'character' if entity_type=='character' else ('environment' if entity_type in {'location','environment'} else None)
    @staticmethod
    def _profile(con,document_id,entity_id,profile_type,name,confidence):
        con.execute('INSERT INTO visual_profiles(document_id,entity_id,profile_type,canonical_name,confidence) VALUES(?,?,?,?,?)',(document_id,entity_id,profile_type,name,confidence)); return int(con.execute('SELECT last_insert_rowid()').fetchone()[0])

    def _extract_character_facts(self,con,profile_id,name,scene_id,page_start,page_end,text,base_confidence):
        # Reject a candidate match unless the character mention occurs inside a
        # local descriptive clause tied to the visual phrase. This prevents
        # unrelated phrases such as "large scale map" or "serious difficulty"
        # from becoming character attributes merely because the name is nearby.
        name_re=re.escape(name.strip())
        local=re.compile(rf'(?is)(?:\b(?:the|a|an)\s+)?{name_re}[^.!?;:]{0,120}?(?:\b(?:was|were|is|had|has|looked|appeared|seemed|stood|wore|wearing|dressed|clad|possessed|possessed|with|of)\b)[^.!?;:]{0,100}|(?:\b(?:his|her|their)\b)[^.!?;:]{0,100}?{name_re}[^.!?;:]{0,80}')
        local_spans=[m.span() for m in local.finditer(text)]
        if not local_spans: return
        for attribute,patterns in self.CHARACTER_PATTERNS.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    if not any(a<=match.start()<=b or a<=match.end()<=b for a,b in local_spans): continue
                    value=self._clean_value(match.group(1) if match.lastindex else match.group(0))
                    if not value: continue
                    # Extra semantic guards for patterns whose words are highly
                    # polysemous in ordinary prose.
                    if attribute=='build' and not re.search(rf'(?is)(?:{name_re}|\b(?:his|her|their)\b)[^.!?;:]{0,80}\b(?:was|were|is|looked|appeared|stood|seemed|remained)\b[^.!?;:]{0,60}\b(?:tall|short|large|small|slender|thin|lean|slight|stout|stocky|broad|muscular|powerful|robust|strong|weak|lanky|massive|heavy|delicate)\b|\b(?:tall|short|large|small|slender|thin|lean|slight|stout|stocky|broad|muscular|powerful|robust|strong|weak|lanky|massive|heavy|delicate)\b[^.!?;:]{0,60}\b(?:man|woman|person|figure|fellow|hunter|astronomer|colonel|professor|doctor)\b',text): continue
                    if attribute=='expression' and not re.search(rf'(?is)(?:{name_re}|\b(?:his|her|their)\b)[^.!?;:]{0,70}\b(?:face|features|countenance|expression|look|air|manner)\b[^.!?;:]{0,50}\b(?:{re.escape(value)})\b|\b(?:{re.escape(value)})\b[^.!?;:]{0,60}\b(?:face|features|countenance|expression|look|air|manner)\b[^.!?;:]{0,60}(?:{name_re}|\b(?:his|her|their)\b)',text): continue
                    evidence=self._evidence(text,match.start(),match.end()); self._add_fact(con,profile_id,'appearance' if attribute not in {'clothing','expression','mannerism'} else attribute,attribute,value,'scene',None,scene_id,page_start,page_end,evidence,min(.98,max(.35,base_confidence)),'source_pattern_local')

    def _build_environment_facts(self,con,document_id,scenes,entity_profiles):
        env_ids=con.execute("SELECT id FROM entities WHERE document_id=? AND entity_type IN ('environment','location')",(document_id,)).fetchall(); env_set={int(r[0]) for r in env_ids}
        for scene in scenes:
            text=str(scene['text'] or ''); mentioned=con.execute('SELECT entity_id FROM entity_mentions WHERE document_id=? AND scene_id=?',(document_id,int(scene['id']))).fetchall()
            for row in mentioned:
                eid=int(row[0]);
                if eid not in env_set or eid not in entity_profiles: continue
                pid=entity_profiles[eid]
                for category,pattern in self.ENV_PATTERNS.items():
                    for match in pattern.finditer(text): self._add_fact(con,pid,category,category,self._clean_value(match.group(1)),'scene',None,int(scene['id']),int(scene['page_start']),int(scene['page_end']),self._evidence(text,match.start(),match.end()),.65,'source_pattern')

    def _build_objects(self,con,document_id,scenes):
        ids={}
        for scene in scenes:
            text=str(scene['text'] or ''); words=set(re.findall(r"\b[A-Za-z][A-Za-z'-]+\b",text.lower()))
            for term in sorted(words & self.OBJECT_TERMS):
                name=term.title(); row=con.execute('SELECT id FROM visual_objects WHERE document_id=? AND canonical_name=?',(document_id,name)).fetchone()
                if row: oid=int(row[0])
                else: con.execute('INSERT INTO visual_objects(document_id,canonical_name,confidence,discovery_method) VALUES(?,?,?,?)',(document_id,name,.55,'visual_prop_lexicon')); oid=int(con.execute('SELECT last_insert_rowid()').fetchone()[0])
                ids[name]=oid; evidence=self._term_evidence(text,term); con.execute('INSERT OR IGNORE INTO visual_object_mentions(document_id,object_id,scene_id,page_start,page_end,evidence,confidence) VALUES(?,?,?,?,?,?,?)',(document_id,oid,int(scene['id']),int(scene['page_start']),int(scene['page_end']),evidence,.55)); current=con.execute('SELECT profile_text FROM visual_objects WHERE id=?',(oid,)).fetchone()[0] or ''
                if evidence and evidence not in current: con.execute('UPDATE visual_objects SET profile_text=? WHERE id=?',((current+'\n\n'+evidence).strip()[:6000],oid))
        return ids

    def _build_scene_context(self,con,document_id,scenes,entity_profiles,object_ids):
        for scene in scenes:
            sid=int(scene['id']); mentions=con.execute('SELECT DISTINCT entity_id FROM entity_mentions WHERE document_id=? AND scene_id=? ORDER BY entity_id',(document_id,sid)).fetchall(); chars=[]; env=[]
            for row in mentions:
                pid=entity_profiles.get(int(row[0]));
                if pid is None: continue
                typ=con.execute('SELECT profile_type FROM visual_profiles WHERE id=?',(pid,)).fetchone()[0]; (chars if typ=='character' else env).append(pid)
            text=str(scene['text'] or ''); words=set(re.findall(r"\b[A-Za-z][A-Za-z'-]+\b",text.lower())); obj=[object_ids[w.title()] for w in sorted(words & self.OBJECT_TERMS) if w.title() in object_ids]; ev=[{'object':t,'evidence':self._term_evidence(text,t)} for t in sorted(words & self.OBJECT_TERMS) if self._term_evidence(text,t)]
            continuity={'persistent_character_profiles':chars,'environment_profiles':env,'object_profile_ids':obj,'source_grounded':True,'unknowns_must_remain_unknown':True}
            con.execute('INSERT INTO scene_visual_context(document_id,scene_id,character_profile_ids,environment_profile_ids,object_mentions,continuity_json,evidence_json) VALUES(?,?,?,?,?,?,?)',(document_id,sid,json.dumps(chars),json.dumps(env),json.dumps(obj),json.dumps(continuity,sort_keys=True),json.dumps(ev,ensure_ascii=False)))

    @staticmethod
    def _add_fact(con,profile_id,category,attribute,value,source_type,source_id,scene_id,page_start,page_end,evidence,confidence,method):
        con.execute('INSERT OR IGNORE INTO visual_facts(profile_id,category,attribute,value,status,source_type,source_id,scene_id,page_start,page_end,evidence,confidence,extraction_method) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(profile_id,category,attribute,value,'supported',source_type,source_id,scene_id,page_start,page_end,evidence,confidence,method))
    @staticmethod
    def _clean_value(value): return re.sub(r'\s+',' ',value.strip(" \t\r\n,.;:!?\"'()[]"))[:300]
    @staticmethod
    def _evidence(text,start,end,radius=180): return text[max(0,start-radius):min(len(text),end+radius)].strip()
    @staticmethod
    def _term_evidence(text,term,radius=180):
        m=re.search(r'\b'+re.escape(term)+r'\b',text,re.I); return VisualKnowledgeBible._evidence(text,m.start(),m.end(),radius) if m else ''

def build_visual_knowledge_bible(database_path,document_id): return VisualKnowledgeBible(database_path).build(document_id)
def main():
    p=argparse.ArgumentParser(description='Build the source-grounded visual knowledge bible'); p.add_argument('database'); p.add_argument('document_id',type=int); a=p.parse_args(); counts=build_visual_knowledge_bible(a.database,a.document_id); print('=== VISUAL KNOWLEDGE BIBLE ==='); [print(f'{k}: {v}') for k,v in counts.items()]
if __name__=='__main__':
    import argparse
    main()
