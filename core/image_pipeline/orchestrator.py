from __future__ import annotations
import hashlib,json,logging,time
from pathlib import Path
from PIL import Image,ImageOps
from .browser import BrowserAutomationError,BrowserBlockedError,GoogleAIModeDailyLimitError,GoogleAIModeBrowser
from .models import JobStatus,PipelineConfig,SceneJob
from .overlay_renderer import render_overlays,OverlayRenderError
from .prompt_loader import load_jobs
from .store import GenerationStore
from .validator import validate_image
def _hash(p):return hashlib.sha256(p.encode()).hexdigest()
class ImageGenerationPipeline:
    def __init__(self,config): self.config=config; config.output_dir.mkdir(parents=True,exist_ok=True); self.store=GenerationStore(config.output_dir/"generation.db"); self.browser=GoogleAIModeBrowser(config); self.log=logging.getLogger("image_pipeline")
    def close(self):\n        try: self.browser.close()\n        finally:\n            try: self.store.close()\n            except Exception: pass
    def _normalize(self,path):
        with Image.open(path) as im:
            src=list(im.size)
            if tuple(src)!=(720,1280): ImageOps.fit(im.convert("RGB"),(720,1280),method=Image.Resampling.LANCZOS).save(path,"PNG")
            return {"source_dimensions":src,"final_dimensions":[720,1280]}
    def _visible(self,job):
        out=[]
        for x in (job.record.get("plan") or {}).get("characters",[]):
            if isinstance(x,dict) and (x.get("source_presence") or {}).get("physical_presence") is True and x.get("canonical_name"): out.append(str(x["canonical_name"]))
        return out
    def _process(self,job,all_jobs,index):
        row=self.store.get(job.scene_id)
        if row and row["status"]==JobStatus.COMPLETED:return
        seq=index+1; scene_dir=self.config.output_dir/f"scene_{seq:03d}_{job.scene_id:05d}"; scene_dir.mkdir(parents=True,exist_ok=True); attempt=int(row["attempt"] if row else 0)+1
        for n in range(attempt,self.config.max_attempts+1):
            ad=scene_dir/f"attempt_{n:02d}"; ad.mkdir(parents=True,exist_ok=True); prompt_path=ad/f"prompt.txt"; image=ad/"generated.png"; rendered=ad/"rendered.png"; validation=ad/"validation.json"; prompt_path.write_text(job.prompt,encoding="utf-8"); self.store.begin_attempt(job.scene_id,n,prompt_path); self.store.set_status(job.scene_id,JobStatus.RUNNING,attempt=n,prompt_path=prompt_path,last_error=None)
            try:
                gen=self.browser.generate(prompt=job.prompt,destination=image); norm=self._normalize(image); clean=validate_image(image,prompt=job.prompt,overlays=[],title=job.title,visible_characters=self._visible(job),vision_enabled=self.config.vision_validation,vision_model=self.config.vision_model)
                if clean["status"]!="pass": raise BrowserAutomationError("; ".join(clean["issues"]) or "clean image validation failed")
                overlay=render_overlays(image,rendered,job.overlays); final=validate_image(rendered,prompt=job.prompt,overlays=job.overlays,title=job.title,visible_characters=self._visible(job),vision_enabled=self.config.vision_validation,vision_model=self.config.vision_model)
                payload={"generation":gen,"normalization":norm,"overlay":overlay,"validation":final}; validation.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
                if final["status"]!="pass": raise BrowserAutomationError("; ".join(final["issues"]) or "final validation failed")
                final_path=scene_dir/f"scene_{seq:03d}_{job.scene_id:05d}_final.png"; rendered.replace(final_path); self.store.finish_attempt(job.scene_id,n,status="passed",image_path=final_path,validation_path=validation); self.store.set_status(job.scene_id,JobStatus.COMPLETED,final_path=final_path,validation_path=validation,last_error=None); return
            except GoogleAIModeDailyLimitError:
                self.store.finish_attempt(job.scene_id,n,status="daily_limit",failure_reason="Google AI daily limit"); self.store.set_status(job.scene_id,JobStatus.RETRY,last_error="Google AI daily limit"); raise
            except BrowserBlockedError as e:
                self.store.finish_attempt(job.scene_id,n,status="blocked",failure_reason=str(e)); self.store.set_status(job.scene_id,JobStatus.BLOCKED,last_error=str(e)); raise
            except Exception as e:
                self.store.finish_attempt(job.scene_id,n,status="error",failure_reason=str(e))
                if n<self.config.max_attempts:self.store.set_status(job.scene_id,JobStatus.RETRY,last_error=str(e)); self.browser.recover(); continue
                self.store.set_status(job.scene_id,JobStatus.FAILED,last_error=str(e)); return
    def run(self):
        jobs=load_jobs(self.config.package_path); self.store.ensure_jobs(jobs,{j.scene_id:_hash(j.prompt) for j in jobs}); ids=set(self.store.pending_or_retry(self.config.limit,self.config.start_order)); selected=[j for j in jobs if j.scene_id in ids]
        if not selected:return {"selected":0,"summary":self.store.summary()}
        self.browser.start()
        try:
            for i,j in enumerate(jobs):
                if j.scene_id in ids:self._process(j,jobs,i)
        finally:self.browser.close()
        return {"selected":len(selected),"summary":self.store.summary()}
