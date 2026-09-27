from __future__ import annotations
import re
from functools import lru_cache
from pathlib import Path
from PIL import Image

def _norm(s): return re.sub(r"[^a-z0-9]+"," ",s.casefold()).strip()
@lru_cache(maxsize=1)
def _ocr():
    from paddleocr import PaddleOCR
    return PaddleOCR(lang="en",use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False)
def _ocr_text(path):
    try:
        out=_ocr().predict(str(path)); parts=[]
        for item in out or []:
            if isinstance(item,dict):
                for k in ("rec_texts","texts"):
                    if isinstance(item.get(k),list): parts += [str(x) for x in item[k] if str(x).strip()]
        return " ".join(parts).strip(),None
    except Exception as e:return None,str(e)
def validate_image(path,*,prompt,overlays,title,visible_characters,story_context=None,previous_visual_state=None,vision_enabled=True,vision_model="qwen2.5vl:7b"):
    p=Path(path); result={"status":"pass","issues":[],"checks":{}}
    try:
        with Image.open(p) as im: im.verify()
        with Image.open(p) as im: result["checks"]["dimensions"]=list(im.size); result["checks"]["file_size_bytes"]=p.stat().st_size
    except Exception as e:return {"status":"fail","issues":[f"image unreadable: {e}"],"checks":{}}
    if result["checks"]["dimensions"][0]<512 or result["checks"]["dimensions"][1]<512: result["issues"].append("image resolution is unexpectedly small")
    if result["checks"]["file_size_bytes"]<20000: result["issues"].append("image file is unexpectedly small")
    text,err=_ocr_text(p); result["checks"]["ocr_available"]=text is not None
    required=[str(x.get("text")).strip() for x in overlays if isinstance(x,dict) and x.get("required") is not False and str(x.get("text") or "").strip()]
    if text and not required and len(_norm(text).split())>=2: result["issues"].append("unexpected generated text detected in clean artwork; retrying image generation")
    if required and text: result["checks"]["dialogue"]=[{"expected":x,"found":_norm(x) in _norm(text)} for x in required]
    technical=any(x.startswith("image unreadable") or x in {"image resolution is unexpectedly small","image file is unexpectedly small","unexpected generated text detected in clean artwork; retrying image generation"} for x in result["issues"])
    if required and text and not all(x["found"] for x in result["checks"]["dialogue"]): technical=True; result["issues"].append("required dialogue/narrative text was not confirmed by OCR")
    result["status"]="fail" if technical else "pass"; return result
