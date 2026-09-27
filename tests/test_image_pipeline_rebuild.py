import json
from pathlib import Path
from core.image_pipeline.prompt_loader import load_jobs
from core.image_pipeline.models import SceneJob

def test_txt_scene_is_authoritative(tmp_path):
    p=tmp_path/"scene_001.txt"
    p.write_text("""SCENE ID: 1\nSCENE ORDER: 1\nTITLE: Test Scene\n=== IMAGE GENERATION PROMPT ===\nA cinematic test image.\n=== IMAGE LAYOUT ===\n{\"aspect_ratio\": \"9:16\"}\n=== DIALOGUE / NARRATIVE OVERLAYS ===\n[{\"box_number\":1,\"text\":\"Hello\",\"required\":true}]\n""",encoding="utf-8")
    jobs=load_jobs(p)
    assert len(jobs)==1
    assert jobs[0].scene_id==1
    assert jobs[0].prompt=="A cinematic test image."
    assert jobs[0].overlays[0]["text"]=="Hello"

def test_txt_loader_does_not_try_json(tmp_path):
    p = tmp_path / "scene_002.txt"
    try:
        p.write_text("SCENE ID: 2\nSCENE ORDER: 2\nTITLE: X\n=== IMAGE GENERATION PROMPT ===\nPrompt\n=== IMAGE LAYOUT ===\n{}\n=== DIALOGUE / NARRATIVE OVERLAYS ===\n[]\n",encoding="utf-8")
        jobs=load_jobs(p)
        assert jobs[0].prompt=="Prompt"
    finally:
        p.unlink(missing_ok=True)
