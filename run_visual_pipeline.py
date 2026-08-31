from __future__ import annotations
import argparse,json,sqlite3,subprocess,sys
from pathlib import Path
STEPS=[('Visual Knowledge Bible','core.visual_knowledge_bible'),('Canonical Visual Bible','core.canonical_visual_bible'),('Visual Fact Reconciliation','core.visual_fact_reconciler'),('Visual Conflict Classification','core.visual_conflict_classifier'),('Continuity State','core.continuity_state')]
def run_module(module,db,doc):
 print(f'\n=== RUNNING: {module} ==='); r=subprocess.run([sys.executable,'-m',module,db,str(doc)],text=True,encoding='utf-8',errors='replace');
 if r.stdout: print(r.stdout,end='')
 if r.stderr: print(r.stderr,file=sys.stderr,end='')
 if r.returncode: raise SystemExit(r.returncode)
def scene_smoke(db,doc,sid):
 r=subprocess.run([sys.executable,'-m','core.scene_visual_state',db,str(doc),str(sid)],text=True,encoding='utf-8',errors='replace',capture_output=True)
 if r.returncode: raise SystemExit(f'FAIL: scene visual state failed for scene {sid}: {r.stderr.strip()}')
 try: s=json.loads(r.stdout)
 except json.JSONDecodeError as e: raise SystemExit(f'FAIL: scene {sid} returned invalid JSON: {e}')
 if s.get('unknowns_must_remain_unknown') is not True: raise SystemExit(f'FAIL: scene {sid} does not preserve unknowns')
 return s
def gen_smoke(db,doc,sid):
 r=subprocess.run([sys.executable,'-m','core.generation_context',db,str(doc),str(sid),'--summary'],text=True,encoding='utf-8',errors='replace',capture_output=True)
 if r.returncode: raise SystemExit(f'FAIL: generation context failed for scene {sid}: {r.stderr.strip()}')
 p=json.loads(r.stdout)
 if p.get('continuity_available') is not True: raise SystemExit(f'FAIL: generation context scene {sid} has no continuity state')
 return p
def planner_smoke(db,doc,sid):
 r=subprocess.run([sys.executable,'-m','core.generation_planner',db,str(doc),str(sid),'--summary'],text=True,encoding='utf-8',errors='replace',capture_output=True)
 if r.returncode: raise SystemExit(f'FAIL: generation planner failed for scene {sid}: {r.stderr.strip()}')
 p=json.loads(r.stdout)
 if p.get('plan_status')!='ready': raise SystemExit(f'FAIL: planner scene {sid} is not ready')
 return p
def prompt_smoke(db,doc,sid,mode):
 r=subprocess.run([sys.executable,'-m','core.prompt_builder',db,str(doc),str(sid),'--mode',mode,'--summary'],text=True,encoding='utf-8',errors='replace',capture_output=True)
 if r.returncode: raise SystemExit(f'FAIL: prompt builder {mode} failed for scene {sid}: {r.stderr.strip()}')
 p=json.loads(r.stdout)
 if p.get('status')!='ready': raise SystemExit(f'FAIL: prompt builder {mode} scene {sid} is not ready')
 if p.get('unknowns_must_remain_unknown') is not True: raise SystemExit(f'FAIL: prompt builder {mode} scene {sid} does not preserve unknowns')
 if p.get('prompt_chars',0)<=0: raise SystemExit(f'FAIL: prompt builder {mode} scene {sid} produced empty prompt')
 return p
def validate(db,doc):
 with sqlite3.connect(db) as c:
  q=lambda s,*a:c.execute(s,a).fetchone()[0]
  checks={'canonical_profiles':q('SELECT COUNT(*) FROM canonical_visual_profiles WHERE document_id=?',doc),'canonical_facts':q('SELECT COUNT(*) FROM canonical_visual_facts cvf JOIN canonical_visual_profiles cvp ON cvp.id=cvf.canonical_visual_profile_id WHERE cvp.document_id=?',doc),'strong_conflicts':q("SELECT COUNT(*) FROM visual_conflict_classification WHERE document_id=? AND classification='strong_conflict'",doc),'unsupported':q("SELECT COUNT(*) FROM visual_fact_reconciliation WHERE document_id=? AND status='unsupported'",doc),'known_bad_phrase_facts':q("""SELECT COUNT(*) FROM visual_facts WHERE profile_id IN (SELECT id FROM visual_profiles WHERE document_id=? AND profile_type='character') AND (LOWER(evidence) LIKE '%small tongue of platinum%' OR LOWER(evidence) LIKE '%large scale map%' OR LOWER(evidence) LIKE '%serious difficulty%' OR LOWER(value) LIKE '%200 feet%')""",doc),'canonical_characters':q("SELECT COUNT(*) FROM canonical_characters WHERE document_id=? AND status IN ('confirmed','likely','singleton')",doc),'canonical_without_source_profile':q("SELECT COUNT(*) FROM canonical_characters cc LEFT JOIN canonical_visual_profiles cvp ON cvp.canonical_character_id=cc.id AND cvp.document_id=cc.document_id WHERE cc.document_id=? AND cc.status IN ('confirmed','likely','singleton') AND cvp.id IS NULL",doc),'scene_context_rows':q('SELECT COUNT(*) FROM scene_visual_context WHERE document_id=?',doc),'object_mentions':q('SELECT COUNT(*) FROM visual_object_mentions WHERE document_id=?',doc),'continuity_rows':q('SELECT COUNT(*) FROM visual_scene_continuity WHERE document_id=?',doc),'continuity_state_rows':q('SELECT COUNT(*) FROM visual_entity_state WHERE document_id=?',doc)}
 print('\n=== VISUAL + CONTINUITY + GENERATION VALIDATION ==='); [print(f'{k}: {v}') for k,v in checks.items()]
 if checks['canonical_profiles']!=checks['canonical_characters'] or checks['canonical_facts']==0 or checks['known_bad_phrase_facts'] or checks['strong_conflicts'] or checks['unsupported'] or checks['canonical_without_source_profile'] or checks['scene_context_rows']==0 or checks['object_mentions']==0 or checks['continuity_rows']==0 or checks['continuity_state_rows']==0: raise SystemExit('FAIL: base pipeline validation failed')
 for sid in (1,8,21,78,200,291):
  s=scene_smoke(db,doc,sid); print(f'scene_{sid}: characters={len(s.get("characters",[]))}')
  g=gen_smoke(db,doc,sid); print(f'generation_{sid}: characters={g["characters"]} visual_facts={g["visual_fact_count"]} objects={g["objects"]} events={g["events"]}')
  p=planner_smoke(db,doc,sid); print(f'planner_{sid}: characters={p["characters"]} visual_facts={p["visual_fact_count"]} objects={p["objects"]} events={p["events"]} evidence={p["evidence_items"]}')
  for mode in ('image','video'):
   b=prompt_smoke(db,doc,sid,mode); print(f'prompt_{mode}_{sid}: chars={b["prompt_chars"]} negative={b["negative_constraints"]} continuity={b["continuity_constraints"]}')
 print('RESULT: PASS')
def main():
 p=argparse.ArgumentParser(description='Run visual, continuity, planning, and prompt regression checks'); p.add_argument('database'); p.add_argument('document_id',type=int); a=p.parse_args();
 if not Path(a.database).exists(): raise SystemExit(f'Database not found: {a.database}')
 for _,m in STEPS: run_module(m,a.database,a.document_id)
 validate(a.database,a.document_id)
if __name__=='__main__': main()
