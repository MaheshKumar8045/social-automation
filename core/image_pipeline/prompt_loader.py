from __future__ import annotations
import json,re
from pathlib import Path
from typing import Any
from .models import SceneJob
class PromptPackageError(ValueError): pass
def _mapping(v:Any)->dict[str,Any]: return v if isinstance(v,dict) else {}
def _txt(path:Path)->SceneJob:
    text=path.read_text(encoding="utf-8")
    header,sep,rest=text.partition("=== IMAGE GENERATION PROMPT ===")
    if not sep: raise PromptPackageError(f"missing IMAGE GENERATION PROMPT section: {path}")
    prompt,sep,rest=rest.partition("=== IMAGE LAYOUT ===")
    if not sep: raise PromptPackageError(f"missing IMAGE LAYOUT section: {path}")
    layout,sep,over=rest.partition("=== DIALOGUE / NARRATIVE OVERLAYS ===")
    if not sep: raise PromptPackageError(f"missing DIALOGUE / NARRATIVE OVERLAYS section: {path}")
    def hv(n):
        m=re.search(rf"(?m)^{re.escape(n)}:\s*(.+?)\s*$",header); return m.group(1).strip() if m else ""
    try: sid=int(hv("SCENE ID")); order=int(hv("SCENE ORDER"))
    except ValueError as e: raise PromptPackageError(f"invalid scene id/order: {path}") from e
    title=hv("TITLE"); p=prompt.strip()
    if not p: raise PromptPackageError(f"empty image prompt: {path}")
    try: overlays=json.loads(over.strip() or "[]"); layout_obj=json.loads(layout.strip() or "{}")
    except json.JSONDecodeError as e: raise PromptPackageError(f"invalid scene JSON: {path}: {e}") from e
    if not isinstance(overlays,list): overlays=[]
    record={"scene_id":sid,"scene_order":order,"title":title,"source_prompt_file":str(path),"source_prompt_format":"image_scene_txt","plan":{"image_prompt":p,"media_prompt_package":{"image":{"prompt":p,"dialogue_overlays":overlays,"layout":layout_obj}}}}
    return SceneJob(sid,order,title,p,[x for x in overlays if isinstance(x,dict)],record)
def load_jobs(path:str|Path)->list[SceneJob]:
    src=Path(path)
    if not src.exists(): raise PromptPackageError(f"prompt package does not exist: {src}")
    if src.is_dir() or src.suffix.lower()==".txt":
        paths=[src] if src.is_file() else sorted(src.glob("scene_*.txt"))
        if not paths: raise PromptPackageError(f"no scene_*.txt image prompts found in: {src}")
        jobs=[_txt(p) for p in paths]
    else:
        try: package=json.loads(src.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e: raise PromptPackageError(f"invalid prompt package JSON: {src}: {e}") from e
        scenes=package.get("scenes")
        if not isinstance(scenes,list): raise PromptPackageError("prompt package has no scenes list")
        jobs=[]
        for rec in scenes:
            if not isinstance(rec,dict): continue
            try: sid=int(rec["scene_id"]); order=int(rec["scene_order"])
            except (KeyError,TypeError,ValueError) as e: raise PromptPackageError(f"invalid scene record: {rec!r}") from e
            plan=_mapping(rec.get("plan")); media=_mapping(plan.get("media_prompt_package")); image=_mapping(media.get("image"))
            prompt=str(plan.get("image_prompt") or image.get("prompt") or "").strip()
            if not prompt: raise PromptPackageError(f"scene {sid} has no image prompt")
            ovs=image.get("dialogue_overlays",plan.get("image_dialogue_overlays",[])); ovs=ovs if isinstance(ovs,list) else []
            jobs.append(SceneJob(sid,order,str(rec.get("title") or ""),prompt,[x for x in ovs if isinstance(x,dict)],rec))
    seen=set()
    for j in jobs:
        if j.scene_id in seen: raise PromptPackageError(f"duplicate scene_id: {j.scene_id}")
        seen.add(j.scene_id)
    return sorted(jobs,key=lambda j:(j.scene_order,j.scene_id))
