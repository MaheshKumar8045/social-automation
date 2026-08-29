from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS character_candidate_gate (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    score REAL NOT NULL,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(document_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_character_candidate_gate_doc_decision ON character_candidate_gate(document_id, decision);
"""
STOPWORDS=set('a an and are as at be been before but by can could did do does for from had has have he her here him his how i if in is it its just like many more most my never no not now of on one or only or perhaps quite rather said see she so some such than that the their them then there these they this those through to too two under up us very was we were what when where which while why will with without would you your after above about again almost already also always another any anyone anything around because behind below between both during each either enough every everywhere except few first following further get got great half however indeed instead itself last less little long maybe more most much neither never next none nothing often once other otherwise over perhaps rather same several since some someone something soon still such than though three together toward towards until upon very well whatever whenever whether while within without yet'.split())
NON_PERSON=set('african english englishman european french icelandic icelanders russians danish makololos makololo bochjesmen queen earth orange reykjawik sneffels'.split())
TITLE_ONLY=re.compile(r'^(?:mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame)\.?$',re.I)
PERSON_TITLE=re.compile(r'^(?:mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame)\.?\s+',re.I)
NAME_WORD=re.compile(r"^[A-Z][A-Za-z'’-]+$")
SPEECH_CUE=re.compile(r'\b(?:said|replied|asked|cried|shouted|exclaimed|answered|whispered|remarked|observed|rejoined|continued|added|called)\b',re.I)
ACTION_CUE=re.compile(r'\b(?:he|she|his|her)\s+(?:said|replied|asked|cried|shouted|looked|turned|stood|sat|walked|ran|came|went|took|gave|held|put|made)\b',re.I)
DIRECT_PERSON_CUE=re.compile(r'(?:\b(?:said|replied|asked|cried|shouted|exclaimed|answered|whispered|remarked|observed|rejoined|called)\s+{name}\b|\b{name}\s+(?:said|replied|asked|cried|shouted|exclaimed|answered|whispered|remarked|observed|rejoined|called)\b|\b(?:Mr\.?|Mrs\.?|Ms\.?|Miss|Dr\.?|Professor|Prof\.?|Captain|Capt\.?|Sir|Colonel|Major|Lieutenant)\s+{name}\b)',re.I)
ROLE_TOKENS={'river','rivers','mount','mountain','mountains','lake','ocean','sea','island','islands','colony','republic','government','commission','observatory','institution','post','world','africa','hope','zambesi','cape','port','town','city','village','forest','valley','country','countrymen','empire','kingdom','company','society','school','university','museum','academy','station','road','roads','falls','fall','gulfs','gulf','desert','coast','shore','bay','peninsula','expedition','party','tribe','people'}

def norm(name:str)->str:
 s=re.sub(r'\s+',' ',name.replace('‐','-').replace('‑','-').replace('‒','-').replace('–','-').replace('—','-')).strip(' ,.;:\"\'')
 s=re.sub(r'\s+([,.;:])',r'\1',s)
 return s[:-1] if s.endswith('-') and len(s)>3 else s

def gate(name:str,entity_type:str,mentions:list[sqlite3.Row])->tuple[str,float,list[str]]:
 n=norm(name); low=n.lower(); reasons=[]
 if entity_type!='character': return 'non_character',1.0,['upstream_type_not_character']
 if TITLE_ONLY.match(n): return 'non_character',1.0,['title_only']
 if low in STOPWORDS or low in NON_PERSON: return 'non_character',1.0,['common_word_or_demographic_term']
 if len(n)<3 or len(n)>45: return 'review',0.9,['name_length_anomaly']
 raw=name.strip()
 if raw.endswith(('-', '‐','‑','‒','–','—')): return 'review',0.4,['line_break_fragment']
 words=n.replace('-',' ').split(); title=bool(PERSON_TITLE.match(n))
 bare=[w.strip('.') for w in words if w.lower() not in {'mr','mrs','ms','miss','dr','prof','professor','capt','captain','sir','lady','lord','rev','reverend','colonel','major','lieutenant','herr','monsieur','madame'}]
 if not all(NAME_WORD.match(w) for w in bare if w): return 'review',0.65,['non_name_token']
 role_words={w.lower().rstrip('.') for w in bare}
 if not title and role_words & ROLE_TOKENS: return 'non_character',0.95,['generic_non_person_name_pattern']
 contexts=[str(m['context'] or '') for m in mentions]
 exact=sum(1 for x in contexts if n.lower() in x.lower())
 scenes=len({m['scene_id'] for m in mentions if m['scene_id'] is not None})
 speech=sum(1 for x in contexts if SPEECH_CUE.search(x)); action=sum(1 for x in contexts if ACTION_CUE.search(x))
 direct_pat=re.compile(DIRECT_PERSON_CUE.pattern.format(name=re.escape(n)),re.I); direct=sum(1 for x in contexts if direct_pat.search(x))
 score=.25
 if title: score+=.25; reasons.append('personal_title')
 if len(bare)>=2: score+=.15; reasons.append('multiword_person_name')
 if exact>=2: score+=.15; reasons.append('name_repeated_in_context')
 if len(mentions)>=3: score+=.10; reasons.append('recurring_mentions')
 if scenes>=2: score+=.10; reasons.append('multi_scene_presence')
 if direct: score+=.15; reasons.append('direct_person_reference')
 if speech: score+=.05; reasons.append('speech_context')
 if action: score+=.05; reasons.append('character_action_context')
 if any(w.lower() in STOPWORDS for w in bare): score-=.45; reasons.append('stopword_name_component')
 # An un-titled single token needs direct evidence; a multi-token un-titled
 # name needs either direct evidence or repeated person-like use. This avoids
 # validating place/publication names that happen to occur in dialogue chunks.
 if len(bare)==1 and not title and direct==0: score=min(score,.44); reasons.append('single_word_without_direct_person_reference')
 if len(bare)>=2 and not title and direct==0 and exact < 3: score=min(score,.47); reasons.append('untitled_name_without_repeated_direct_evidence')
 score=max(0,min(1,score)); decision='validated' if score>=.75 else 'probable' if score>=.48 else 'review'
 return decision,score,reasons

def build(db:str|Path,document_id:int)->dict[str,int]:
 with sqlite3.connect(db) as con:
  con.row_factory=sqlite3.Row; con.execute('PRAGMA foreign_keys=ON'); con.executescript(SCHEMA); con.execute('DELETE FROM character_candidate_gate WHERE document_id=?',(document_id,))
  entities=con.execute('SELECT id,entity_type,canonical_name FROM entities WHERE document_id=? ORDER BY id',(document_id,)).fetchall()
  for e in entities:
   mentions=con.execute('SELECT scene_id,context FROM entity_mentions WHERE document_id=? AND entity_id=? ORDER BY page_start,id',(document_id,e['id'])).fetchall(); decision,score,reasons=gate(e['canonical_name'],e['entity_type'],mentions)
   con.execute('INSERT INTO character_candidate_gate(document_id,entity_id,decision,normalized_name,score,reasons_json) VALUES(?,?,?,?,?,?)',(document_id,e['id'],decision,norm(e['canonical_name']),score,json.dumps(reasons)))
  con.commit(); return {r['decision']:int(r['n']) for r in con.execute('SELECT decision,COUNT(*) n FROM character_candidate_gate WHERE document_id=? GROUP BY decision',(document_id,)).fetchall()}

def main()->None:
 p=argparse.ArgumentParser(description='Conservative character candidate gate'); p.add_argument('database'); p.add_argument('document_id',type=int); a=p.parse_args(); counts=build(a.database,a.document_id); print('=== CHARACTER CANDIDATE GATE ==='); [print(f'{k}: {counts.get(k,0)}') for k in ('validated','probable','review','non_character')]
if __name__=='__main__': main()
