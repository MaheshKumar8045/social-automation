from __future__ import annotations
import argparse,json,logging,os
from pathlib import Path
from .browser import GoogleAIModeDailyLimitError
from .models import PipelineConfig
from .orchestrator import ImageGenerationPipeline
def main():
 p=argparse.ArgumentParser(); p.add_argument("package"); p.add_argument("--output-dir"); p.add_argument("--limit",type=int); p.add_argument("--start-order",type=int); p.add_argument("--max-attempts",type=int,default=3); p.add_argument("--generation-timeout",type=float,default=300); p.add_argument("--vision-model",default=os.getenv("SOCIAL_AUTOMATION_VISION_MODEL","qwen2.5vl:7b")); p.add_argument("--no-vision",action="store_true"); p.add_argument("--verbose",action="store_true"); p.add_argument("--chrome-cdp-url",default=os.getenv("SOCIAL_AUTOMATION_CHROME_CDP_URL","http://127.0.0.1:9222")); p.add_argument("--no-chrome-auto-launch",action="store_true"); p.add_argument("--chrome-auto-user-data-dir",default=os.getenv("SOCIAL_AUTOMATION_CHROME_AUTO_USER_DATA_DIR",str(Path.home()/"social-automation-chrome"))); a=p.parse_args(); package=Path(a.package); out=Path(a.output_dir) if a.output_dir else package.parent/"generated_images"; logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,format="%(asctime)s | %(levelname)s | %(message)s"); cfg=PipelineConfig(package,out,a.limit,a.start_order,max(1,a.max_attempts),max(30,a.generation_timeout),vision_validation=not a.no_vision,vision_model=a.vision_model,chrome_cdp_url=a.chrome_cdp_url,chrome_auto_launch=not a.no_chrome_auto_launch,chrome_auto_user_data_dir=Path(a.chrome_auto_user_data_dir)); pipe=ImageGenerationPipeline(cfg)
 try: print(json.dumps(pipe.run(),ensure_ascii=False,indent=2)); return 0
 except GoogleAIModeDailyLimitError as e: print(str(e)); return 2
 finally: pipe.close()
if __name__=="__main__": raise SystemExit(main())
