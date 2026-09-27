from __future__ import annotations
import shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageOps,ImageStat
TEXT=(247,240,220,255); STROKE=(8,11,13,255); SHADOW=(0,0,0,120)
class OverlayRenderError(RuntimeError): pass
def _font(size):
    candidates=["C:/Windows/Fonts/Georgia.ttf","C:/Windows/Fonts/times.ttf","C:/Windows/Fonts/DejaVuSerif.ttf"]
    for p in candidates:
        if Path(p).exists(): return ImageFont.truetype(p,size=size)
    return ImageFont.load_default()
def _wrap(draw,text,font,width):
    lines=[]; cur=""
    for w in text.split():
        test=w if not cur else cur+" "+w
        if draw.textlength(test,font=font)<=width:cur=test
        else:
            if cur:lines.append(cur)
            cur=w
    if cur:lines.append(cur)
    return lines
def _score(im,box):
    crop=ImageOps.grayscale(im.crop(box)).resize((48,48)); edges=crop.filter(ImageFilter.FIND_EDGES); st=ImageStat.Stat(edges); return float(st.mean[0])+float(st.stddev[0])*.5
def _pick(im,w,h,margin,occupied):
    xs={margin,max(margin,(im.width-w)//2),max(margin,im.width-margin-w)}; ys={margin,max(margin,(im.height-h)//4),max(margin,(im.height-h)//2),max(margin,im.height-margin-h)}
    choices=[]
    for y in ys:
        for x in xs:
            b=(x,y,x+w,y+h)
            if any(max(0,min(b[2],o[2])-max(b[0],o[0]))*max(0,min(b[3],o[3])-max(b[1],o[1]))>0 for o in occupied): continue
            choices.append(( _score(im,b),b))
    return min(choices,key=lambda x:x[0])[1] if choices else (margin,margin,margin+w,margin+h)
def render_overlays(source_path,destination_path,overlays,*,safe_margin_percent=7.0,default_max_width_percent=80.0,default_max_height_percent=30.0):
    src=Path(source_path); dst=Path(destination_path)
    if not src.exists(): raise OverlayRenderError(f"source image does not exist: {src}")
    items=[x for x in overlays if isinstance(x,dict) and str(x.get("text") or "").strip()]
    dst.parent.mkdir(parents=True,exist_ok=True)
    if not items: shutil.copy2(src,dst); return {"rendered":False,"boxes":[]}
    im=Image.open(src).convert("RGBA"); layer=Image.new("RGBA",im.size,(0,0,0,0)); draw=ImageDraw.Draw(layer); margin=round(im.width*safe_margin_percent/100); occupied=[]; boxes=[]
    for i,item in enumerate(items,1):
        text=" ".join(str(item["text"]).split()); maxw=min(round(im.width*default_max_width_percent/100),im.width-2*margin); maxh=min(round(im.height*default_max_height_percent/100),im.height-2*margin); size=max(44,round(im.width*.06));
        while size>=22:
            f=_font(size); lines=_wrap(draw,text,f,maxw-30); lh=max(1,f.getbbox("Ag")[3]-f.getbbox("Ag")[1]); th=len(lines)*lh+max(0,len(lines)-1)*round(size*.2)
            if th<=maxh-20: break
            size-=2
        tw=max(round(draw.textlength(x,font=f)) for x in lines); bw=min(maxw,tw+30); bh=min(maxh,th+24); box=_pick(im,bw,bh,margin,occupied); occupied.append(box); x=box[0]+(box[2]-box[0]-tw)//2; y=box[1]+(box[3]-box[1]-th)//2
        for line in lines:
            draw.text((x+2,y+2),line,font=f,fill=SHADOW,stroke_width=max(2,size//18),stroke_fill=SHADOW); draw.text((x,y),line,font=f,fill=TEXT,stroke_width=max(2,size//22),stroke_fill=STROKE); y+=lh+round(size*.2)
        boxes.append({"box_number":int(item.get("box_number") or i),"text":text,"x":box[0],"y":box[1],"width":box[2]-box[0],"height":box[3]-box[1],"background":"transparent"})
    Image.alpha_composite(im,layer).convert("RGB").save(dst,"PNG"); return {"rendered":True,"boxes":boxes}
