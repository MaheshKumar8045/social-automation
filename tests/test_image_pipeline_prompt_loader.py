from pathlib import Path

from core.image_pipeline.prompt_loader import load_jobs


def _write_prompt(path: Path, scene_id: int, scene_order: int, title: str, prompt: str, overlay_text: str):
    path.write_text(
        f"""SOURCE: test.db
SCENE ID: {scene_id}
SCENE ORDER: {scene_order}
TITLE: {title}
PAGES: 1–2

=== IMAGE GENERATION PROMPT ===
{prompt}

=== IMAGE LAYOUT ===
{{
  "aspect_ratio": "9:16",
  "orientation": "vertical"
}}

=== DIALOGUE / NARRATIVE OVERLAYS ===
[
  {{
    "box_number": 1,
    "box_type": "dialogue_box",
    "text": "{overlay_text}",
    "required": true
  }}
]
""",
        encoding="utf-8",
    )


def test_load_jobs_accepts_exported_image_prompt_txt_directory(tmp_path: Path):
    image_dir = tmp_path / "image"
    image_dir.mkdir()
    _write_prompt(
        image_dir / "scene_010.txt",
        scene_id=10,
        scene_order=2,
        title="Second Scene",
        prompt="AUTHORITATIVE EDITED PROMPT FOR SCENE 10",
        overlay_text="Come with me.",
    )
    _write_prompt(
        image_dir / "scene_002.txt",
        scene_id=2,
        scene_order=1,
        title="First Scene",
        prompt="AUTHORITATIVE EDITED PROMPT FOR SCENE 2",
        overlay_text="Wait here.",
    )

    jobs = load_jobs(image_dir)

    assert [job.scene_id for job in jobs] == [2, 10]
    assert jobs[0].prompt == "AUTHORITATIVE EDITED PROMPT FOR SCENE 2"
    assert jobs[1].prompt == "AUTHORITATIVE EDITED PROMPT FOR SCENE 10"
    assert jobs[0].overlays[0]["text"] == "Wait here."
    assert jobs[1].record["source_prompt_format"] == "image_scene_txt"


def test_load_jobs_accepts_single_image_prompt_txt(tmp_path: Path):
    path = tmp_path / "scene_001.txt"
    _write_prompt(
        path,
        scene_id=1,
        scene_order=1,
        title="Opening",
        prompt="EXACT TEXT PROMPT THAT MUST REACH THE IMAGE MODEL",
        overlay_text="Begin.",
    )

    jobs = load_jobs(path)

    assert len(jobs) == 1
    assert jobs[0].prompt == "EXACT TEXT PROMPT THAT MUST REACH THE IMAGE MODEL"
    assert jobs[0].overlays[0]["text"] == "Begin."
