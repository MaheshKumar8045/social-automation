from __future__ import annotations

import re
from typing import Any

from .generation_intent import build_generation_intent

_QUOTE_RE = re.compile(r'["“](.*?)[“”"]', re.S)
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')
_SPEECH_RE = re.compile(r"\b(?:said|asked|replied|answered|exclaimed|cried|shouted|whispered|remarked|called|murmured|observed|added|told)\b", re.I)
_ACTION_RE = re.compile(r"\b(?:approach\w*|arriv\w*|attack\w*|battle\w*|capture\w*|climb\w*|come|cross\w*|cry\w*|die\w*|enter\w*|fall\w*|flee\w*|follow\w*|fight\w*|grab\w*|hold\w*|kill\w*|look\w*|move\w*|open\w*|reach\w*|return\w*|run\w*|save\w*|see\w*|sit\w*|stand\w*|take\w*|turn\w*|walk\w*|watch\w*|travel\w*|strike\w*|destroy\w*|burn\w*|collapse\w*|kneel\w*|rise\w*|speak\w*)\b", re.I)
_CHARACTER_PHYSICAL_RE = re.compile(r"\b(?:approach\w*|arriv\w*|attack\w*|capture\w*|climb\w*|come|cross\w*|cry\w*|die\w*|enter\w*|fall\w*|flee\w*|follow\w*|fight\w*|fought|grab\w*|hold\w*|kill\w*|look\w*|move\w*|open\w*|reach\w*|return\w*|run\w*|save\w*|sit\w*|stand\w*|take\w*|turn\w*|walk\w*|watch\w*|travel\w*|strike\w*|destroy\w*|burn\w*|collapse\w*|kneel\w*|rise\w*|speak\w*|was|were|is|are|stood|sat|lay|remained|waited|rested|entered|arrived|appeared|left|returned|looked|watched|faced|knelt|rose|walked|ran|fled|followed|held|carried|spoke|sang|wept|cried)\b", re.I)
_PRESENCE_RE = re.compile(r"\b(?:was|were|is|are|stood|sat|lay|remained|waited|rested|entered|arrived|appeared|left|returned|looked|watched|faced|knelt|rose|walked|ran|fled|followed|held|carried|spoke|sang|wept|cried)\b", re.I)
_DESTRUCTION_RE = re.compile(r"\b(?:ruin\w*|destroy\w*|destruction|ashes|embers|burnt|burned|fire|smoke|collapse\w*|wreck\w*|dead|dying|death)\b", re.I)
_COMBAT_RE = re.compile(r"\b(?:battle|fight\w*|fought|attack\w*|strike\w*|weapon|sword|kill\w*|capture\w*)\b", re.I)
_TRAVEL_RE = re.compile(r"\b(?:walk\w*|run\w*|travel\w*|arriv\w*|leave\w*|cross\w*|journey)\b", re.I)
_REACTION_RE = re.compile(r"\b(?:fear|afraid|frightened|angry|furious|grief|sad|wept|cried|shocked|astonished|surprised|regret\w*)\b", re.I)
_DIALOGUE_START_RE = re.compile(r"^(?:i|we|my|our|you|your|this|that|it|he|she|they|tomorrow|today|tonight|why|how|what|when|where|who|can|could|will|would|shall|should|must|let|perhaps|if|there|here)\b", re.I)
_HEADING_PREFIX_RE = re.compile(r"^\s*(?:(?:[IVXLCDM]{1,8}[.)]\s+)|(?:[IVXLCDM]{2,8}\s+(?=[A-Z]))|(?:\d{1,3}[.)]?\s+))")
_NAME_TOKEN_RE = re.compile(r"^[A-Z][A-Za-z'’-]*$")

def _clean(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip() if len(text) > limit else text

def _normalize_for_match(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

def _strip_scene_heading(text: str, scene: dict[str, Any] | None = None) -> str:
    value = _clean(text, 3000); title = _clean((scene or {}).get("title"), 160)
    if title and _normalize_for_match(value).startswith(_normalize_for_match(title)):
        match = re.match(r"^\s*" + re.escape(title), value, re.I)
        if match: value = value[match.end():].lstrip(" -:;,.\t")
    return _HEADING_PREFIX_RE.sub("", value, count=1).strip()

def _sentences(text: str) -> list[str]:
    return [_clean(x) for x in _SENTENCE_RE.split(re.sub(r"\s+", " ", text or "").strip()) if len(x.split()) >= 4]

def _clean_dialogue_candidate(sentence: str, scene: dict[str, Any] | None = None) -> str:
    value = _clean(sentence, 220).strip(" '’“”")
    if not value: return ""
    value = _HEADING_PREFIX_RE.sub("", value, count=1); title = _clean((scene or {}).get("title"), 160)
    if title and _normalize_for_match(value).startswith(_normalize_for_match(title)):
        match = re.match(r"^\s*" + re.escape(title), value, re.I)
        if match: value = value[match.end():].lstrip(" -:;,.\t")
    words = value.split()
    for index, word in enumerate(words):
        token = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", word)
        if index <= 0 or not _DIALOGUE_START_RE.match(token): continue
        prefix = [re.sub(r"[^A-Za-z'’-]", "", item) for item in words[:index] if item]
        if prefix and prefix[0].lower() not in {"i", "we", "my", "our", "you", "your"} and all(_NAME_TOKEN_RE.match(item) for item in prefix): value = " ".join(words[index:])
        break
    return _clean(value, 220)

def _source_dialogue(scene_text: str, scene: dict[str, Any] | None = None) -> list[str]:
    quoted = [_clean_dialogue_candidate(m.group(1), scene) for m in _QUOTE_RE.finditer(scene_text or "")]
    quoted = [x for x in quoted if len(x.split()) >= 3]
    if quoted: return list(dict.fromkeys(quoted))[:3]
    candidates=[]
    for sentence in _sentences(_strip_scene_heading(scene_text, scene)):
        value=_clean_dialogue_candidate(sentence, scene)
        if _SPEECH_RE.search(value) or (re.search(r"\b(?:I|we|my|our)\b", value, re.I) and len(value.split()) <= 28): candidates.append(value)
    return list(dict.fromkeys(candidates))[:2]

def _visual_moments(scene_text: str, events: list[dict[str, Any]], characters: list[dict[str, Any]]) -> list[str]:
    source=_strip_scene_heading(scene_text); names=[str(c.get("canonical_name") or "").casefold() for c in characters]; candidates=[]; order=0
    for event in events:
        order+=1; text=_clean(event.get("text"))
        if not text or text not in scene_text: continue
        score=50+(35 if _ACTION_RE.search(text) else 0)+(15 if _DESTRUCTION_RE.search(text) else 0)+(10 if _COMBAT_RE.search(text) else 0)+sum(10 for name in names if name and name in text.casefold()); candidates.append((score,order,text))
    for sentence in _sentences(source):
        order+=1; score=10+(45 if _ACTION_RE.search(sentence) else 0)+(15 if _DESTRUCTION_RE.search(sentence) else 0)+(10 if _COMBAT_RE.search(sentence) else 0)+(7 if _REACTION_RE.search(sentence) else 0)+sum(10 for name in names if name and name in sentence.casefold()); candidates.append((score,order,sentence))
    result=[]; seen=set()
    for _,_,text in sorted(candidates,key=lambda x:(-x[0],x[1])):
        key=text.casefold()
        if key not in seen and text in scene_text: seen.add(key); result.append(text)
    return result[:6]

def _character_blocking(scene_text: str, characters: list[dict[str, Any]], events: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    visible=[]; referenced=[]; event_texts=[_clean(e.get("text"),360) for e in events if _clean(e.get("text"),360)]
    for character in characters:
        name=_clean(character.get("canonical_name"),100)
        if not name: continue
        matching=[e for e in event_texts if e in scene_text and re.search(rf"\b{re.escape(name)}\b",e,re.I)]
        physical=next((e for e in matching if _CHARACTER_PHYSICAL_RE.search(e)),None)
        source_contexts=[]
        for mention in character.get("scene_mentions") or []:
            context=_clean(mention.get("context"),320)
            if context and context in scene_text and re.search(rf"\b{re.escape(name)}\b",context,re.I): source_contexts.append(context)
        if physical is None: physical=next((c for c in source_contexts if _CHARACTER_PHYSICAL_RE.search(c)),None)
        if physical: visible.append(f"{name}: {physical}")
        elif matching or source_contexts or re.search(rf"\b{re.escape(name)}\b",scene_text,re.I): referenced.append(name)
    return visible[:8],list(dict.fromkeys(referenced))[:10]

def _camera_for(role: str, signal: str, has_visible: bool) -> dict[str,str]:
    profiles={"establish":("wide environmental establishing frame","slow lateral drift","24–28mm equivalent wide perspective"),"action":("medium-wide action frame with clear spatial separation","restrained tracking matched to the source action","28–35mm equivalent natural perspective"),"consequence":("wide environmental consequence frame emphasizing source-established aftermath","slow push-in toward the documented consequence","35mm equivalent natural perspective"),"detail":("purposeful environmental or source-object detail","slow micro-dolly or static hold","50–85mm equivalent detail perspective"),"reaction":(("medium reaction frame" if has_visible else "environmental reaction frame"),"subtle push-in or static hold","50mm equivalent natural perspective"),"movement":("tracking composition preserving travel geography","lateral or rear tracking move","28–35mm equivalent wide-natural perspective"),"destination":("forward-looking destination composition grounded in the source setting","measured reveal or gentle forward move","35mm equivalent natural perspective"),"develop":("balanced medium-wide development composition","slow arc or restrained dolly","35–50mm equivalent natural perspective"),"close":("balanced closing composition","slow pull-back or gentle rise","35–50mm equivalent natural perspective")}
    framing,movement,lens=profiles.get(role,profiles["develop"]); lighting="motivated naturalistic lighting with physically credible contrast and atmospheric depth"
    if signal=="destruction": lighting="low-key motivated light with smoke, dust, embers or fire only where source-compatible"
    elif signal=="combat": lighting="directional motivated light with grounded contrast and readable action separation"
    return {"framing":framing,"movement":movement,"lens":lens,"camera_height":"eye-level unless source evidence or shot purpose clearly supports a different height","lighting":lighting}

def _shot_plan(intent: dict[str, Any], count: int, long_form: bool=False) -> list[dict[str,str]]:
    signal=intent["emotional_signal"]; available=intent["visual_moment_candidates"]
    if long_form:
        base=["establish"]
        if signal=="travel": base.append("movement")
        if signal=="combat": base.append("action")
        if signal=="destruction": base.append("consequence")
        base += ["reaction","detail","close"]
        if count>len(base):
            optional=["develop","action" if signal=="combat" else "consequence","detail","reaction","close"]
            for role in optional:
                if len(base)>=count: break
                if role not in base or role=="detail": base.append(role)
        roles=base[:count]
    else: roles=intent["cinematic_arc"][:count]
    moments=[available[i%len(available)] for i in range(count)]
    return [{"role":role,"purpose":role,"source_visual_focus":moments[i],**{f"camera_{k}":v for k,v in _camera_for(role,signal,bool(intent["visible_characters"])).items()}} for i,role in enumerate(roles)]

def _audio_direction(intent: dict[str, Any]) -> dict[str, Any]:
    dialogue=intent["dialogue"]
    if intent["dialogue_kind"]=="spoken": mode="spoken dialogue; use exact source wording and only source-established speaker identity"
    elif intent["dialogue_kind"]=="first_person_narration": mode="first-person narration/voice-over; do not stage the narration as on-screen speech unless physical speech is source-established"
    else: mode="no source dialogue; use environmental sound and restrained music only"
    return {"music_direction":["Restrained cinematic score supporting the source-derived emotional arc; intensity may evolve with shot purpose."],"dialogue_source":dialogue,"dialogue_mode":mode,"sound_design":"Use only source-compatible environmental/action sounds; never imply an unsupported event.","mixing":"Prioritize source dialogue or narration when present; duck music beneath voice; preserve environmental depth without masking the source voice.","silence_points":"Allow deliberate quiet before or after major source-derived emotional beats when appropriate."}

def _prompt(scene: dict[str,Any], intent: dict[str,Any], world_profile: dict[str,Any], genre: str, focus: str, camera: dict[str,str], extra: str="") -> str:
    visible=", ".join(x["name"] for x in intent["visible_characters"]) or "none"; referenced=", ".join(intent["referenced_characters"]) or "none"; dims=(world_profile or {}).get("dimensions") or {}; world=[]
    for key in ("culture","religious_context","region","period"):
        top=(dims.get(key) or {}).get("top") or {}
        if top.get("label"): world.append(f"{key.replace('_',' ')}={top['label']}")
    return (f"Source-grounded {genre} cinematic generation for scene {scene.get('scene_order','')}: {_clean(scene.get('title'),140)}. SOURCE-ANCHORED SCENE INTERPRETATION: {focus} SOURCE VISUAL MOMENT: {focus} "
            f"VISIBLE SOURCE-CONFIRMED CHARACTERS: {visible}. REFERENCED-ONLY CHARACTERS: {referenced}; do not render referenced-only names. "
            f"DETECTED STORY WORLD (context only): {', '.join(world) if world else 'unknown'}. CINEMATIC DIRECTION: {camera['framing']}; {camera['movement']}; {camera['lens']}; {camera.get('camera_height',camera.get('height','eye-level unless source evidence or shot purpose clearly supports a different height'))}; {camera.get('lighting','motivated naturalistic lighting')}. "
            "Preserve canonical identity anchors, continuity state, source-supported objects and geography. Unknown attributes remain unknown. Do not invent costumes, anatomy, props, architecture, weather, supernatural effects, actions, or story events. Maintain clear foreground/midground/background hierarchy and readable subject separation. " + extra)

def _overlays(dialogue: list[str], intent: dict[str,Any], layout: dict[str,Any]) -> list[dict[str,Any]]:
    boxes=[]
    if dialogue:
        box_type="dialogue_box" if intent["dialogue_kind"]=="spoken" else "narrative_box"; source="source_dialogue" if box_type=="dialogue_box" else "source_first_person_narration"
        for i,text in enumerate(dialogue[:2],1): boxes.append({"box_number":i,"box_type":box_type,"text":text,"text_source":source,"required":True,"placement":"largest protected negative-space region opposite subject/action","max_width_percent":layout.get("dialogue_box_max_width_percent",68),"max_height_percent":layout.get("dialogue_box_max_height_percent",15),"avoid":["faces","hands","important_objects","primary_action"]})
    else: boxes.append({"box_number":1,"box_type":"narrative_box","text":intent["primary_visual_moment"],"text_source":"source_visual_moment","required":True,"placement":"largest protected negative-space region opposite subject/action","max_width_percent":layout.get("dialogue_box_max_width_percent",68),"max_height_percent":layout.get("dialogue_box_max_height_percent",15),"avoid":["faces","hands","important_objects","primary_action"]})
    return boxes

def enhance_generation_package(*, scene: dict[str,Any], characters: list[dict[str,Any]], objects: list[dict[str,Any]], events: list[dict[str,Any]], continuity: dict[str,Any], world_profile: dict[str,Any], genre: str, media: dict[str,Any]) -> dict[str,Any]:
    text=str(scene.get("text") or ""); dialogue=_source_dialogue(text,scene); intent=build_generation_intent(scene=scene,characters=characters,objects=objects,events=events,continuity=continuity,dialogue=dialogue,genre=genre)
    existing_layout=((media.get("image") or {}).get("layout") or {})
    layout={"aspect_ratio":existing_layout.get("aspect_ratio","9:16"),"safe_margin_percent":existing_layout.get("safe_margin_percent",7),"critical_subject_safe_area_percent":existing_layout.get("critical_subject_safe_area_percent",86),"background_visible_percent":existing_layout.get("background_visible_percent",[35,55]),"main_subject_height_percent":existing_layout.get("main_subject_height_percent",[45,65]),"secondary_subject_height_percent":existing_layout.get("secondary_subject_height_percent",[25,50]),"group_subject_height_percent":existing_layout.get("group_subject_height_percent",[30,55]),"dialogue_box_max_width_percent":existing_layout.get("dialogue_box_max_width_percent",68),"dialogue_box_max_height_percent":existing_layout.get("dialogue_box_max_height_percent",15)}
    image_role="action" if intent["emotional_signal"]=="combat" else "consequence" if intent["emotional_signal"]=="destruction" else "movement" if intent["emotional_signal"]=="travel" else "reaction" if intent["emotional_signal"]=="reaction" and intent["visible_characters"] else "establish"
    image_camera=_camera_for(image_role,intent["emotional_signal"],bool(intent["visible_characters"]))
    image_prompt=_prompt(scene,intent,world_profile,genre,intent["primary_visual_moment"],image_camera,"Compose one dominant source-derived visual moment for mobile-first 9:16. Reserve protected negative space for deterministic text. Do not force a character portrait when the source moment is environmental.")
    overlays=_overlays(dialogue,intent,layout); short_roles=intent["cinematic_arc"][:3]; clips=[]
    for i,role in enumerate(short_roles):
        focus=intent["visual_moment_candidates"][min(i,len(intent["visual_moment_candidates"])-1)]; camera=_camera_for(role,intent["emotional_signal"],bool(intent["visible_characters"]))
        prompt=_prompt(scene,intent,world_profile,genre,focus,camera,f"This is clip {i+1} of 3. Sequence purpose: {role}. Use one primary source-established visual beat and progress from the preceding clip without creating a new event. Preserve vertical mobile readability.")
        line=dialogue[i] if i<len(dialogue) else None
        if line: prompt+=f' Use exact source voice text: "{line}".'
        clips.append({"clip_number":i+1,"duration_seconds":5,"role":role,"prompt":prompt,"source_visual_focus":focus,"camera":camera,"transition_to_next":"hard cut" if i<2 else "clean hold/fade","dialogue":line})
    richness=len(intent["visual_moment_candidates"])+len(intent["visible_characters"])+len(intent["dialogue"]); long_count=max(4,min(8,richness+2)); shots=[]
    for i,spec in enumerate(_shot_plan(intent,long_count,True)):
        focus=spec["source_visual_focus"]; camera={k.replace("camera_",""):v for k,v in spec.items() if k.startswith("camera_")}; prompt=_prompt(scene,intent,world_profile,genre,focus,camera,f"Long-form shot {i+1} of {long_count}; purpose: {spec['purpose']}. Maintain 180-degree spatial logic and exact continuity from the previous shot. Do not fabricate unsupported progression.")
        line=dialogue[i] if i<len(dialogue) else None
        if line: prompt+=f' If this shot carries voice, use exact source text: "{line}".'
        shots.append({"shot_number":i+1,**spec,"prompt":prompt,"duration_seconds":4 if spec["purpose"] in {"detail","reaction"} else 5,"dialogue":line})
    audio=_audio_direction(intent); inference=dict(media.get("visual_inference") or {}); inference["cinematic_scene_intelligence"]={"enabled":True,"intent_schema_version":intent["schema_version"],"intent":intent,"rule":"Source evidence controls what exists; world context informs production consistency; cinematic choices control presentation only."}
    return {**media,"schema_version":6,"visual_inference":inference,"generation_intent":intent,"image":{**(media.get("image") or {}),"prompt":image_prompt,"dialogue_overlays":overlays,"layout":{**existing_layout,**layout,"dialogue_box_count_minimum":1,"text_rendering":"deterministic overlay","placement_algorithm":"largest protected negative-space region opposite subject/action; never overlap faces, hands, important objects, or primary action"},"cinematic_direction":image_camera,"source_visual_moments":intent["visual_moment_candidates"],"character_blocking":[f"{x['name']}: {x['evidence']}" for x in intent["visible_characters"]],"referenced_characters":intent["referenced_characters"]},"short_video":{"aspect_ratio":layout["aspect_ratio"],"orientation":"portrait","clip_count":3,"clips":clips,"audio":audio,"cinematic_direction":image_camera,"source_visual_moments":intent["visual_moment_candidates"]},"long_video":{"aspect_ratio":layout["aspect_ratio"],"orientation":"portrait","shots":shots,"audio":audio,"cinematic_direction":image_camera,"source_visual_moments":intent["visual_moment_candidates"]}}