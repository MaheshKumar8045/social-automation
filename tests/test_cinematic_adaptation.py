import json

from core.cinematic_adaptation import build_adaptation, write_adaptation_outputs
from core.image_pipeline.prompt_loader import load_jobs


def _record(scene_id=1, order=1, story_id=1, text="Ravana walked through the ruined gate. The city burned."):
    return {
        "scene_id": scene_id,
        "scene_order": order,
        "story_id": story_id,
        "title": "The Ruined Gate",
        "page_start": 1,
        "page_end": 1,
        "source_database": "book.db",
        "plan": {
            "scene": {"text": text},
            "image_prompt": "Source-grounded image prompt.",
            "image_dialogue_overlays": [{"text": "The city burned."}],
            "characters": [{
                "canonical_name": "Ravana",
                "source_presence": {"physical_presence": True},
                "visual_profile": {"identity_anchor": "ravana-anchor"},
            }],
            "long_video_prompt_package": {
                "shots": [
                    {"shot_number": 1, "role": "establish", "purpose": "establish", "source_visual_focus": "Ravana walked through the ruined gate.", "prompt": "Source-grounded shot one."},
                    {"shot_number": 2, "role": "consequence", "purpose": "consequence", "source_visual_focus": "The city burned.", "prompt": "Source-grounded shot two."},
                ]
            },
            "audio_prompt": {
                "dialogue_source": ["The city burned."],
                "sound_design": "Use only source-compatible environmental sounds.",
                "music_direction": ["Restrained cinematic score."],
            },
            "media_prompt_package": {
                "generation_intent": {
                    "visual_moment_candidates": ["Ravana walked through the ruined gate.", "The city burned."],
                    "emotional_signal": "destruction",
                }
            },
            "continuity": {"location": "gate", "time": "night"},
        },
    }


def _package(tmp_path, records=None):
    source = tmp_path / "package.json"
    source.write_text(json.dumps({"scenes": records or [_record()]}), encoding="utf-8")
    return source


def test_adaptation_expands_scene_to_multiple_shots(tmp_path):
    package = build_adaptation(_package(tmp_path))
    assert package["scene_count"] == 1
    assert package["shot_count"] == 3
    assert [shot["shot_id"] for shot in package["shots"]] == [1, 2, 3]
    assert all(shot["source_grounded"] is True for shot in package["shots"])
    assert all(shot["duration_seconds"] >= 3.5 for shot in package["shots"])


def test_adaptation_preserves_source_focus_and_identity_lock(tmp_path):
    package = build_adaptation(_package(tmp_path))
    first = package["shots"][0]
    assert first["source_visual_focus"] == "Ravana walked through the ruined gate."
    assert first["continuity_before"]["identity_locks"][0]["canonical_name"] == "Ravana"
    assert first["continuity_before"]["identity_locks"][0]["identity_anchor"] == "ravana-anchor"


def test_outputs_are_consumable_by_existing_image_pipeline(tmp_path):
    source = _package(tmp_path)
    package = build_adaptation(source)
    records = json.loads(source.read_text(encoding="utf-8"))["scenes"]
    out = tmp_path / "adapted"
    write_adaptation_outputs(package, out, records)
    jobs = load_jobs(out / "shots" / "image")
    assert len(jobs) == package["shot_count"]
    assert all(job.prompt for job in jobs)
    assert jobs[0].scene_id == 1
    assert (out / "episode_001_narration.txt").exists()
    assert (out / "episode_001.srt").exists()


def test_story_change_starts_new_episode(tmp_path):
    first = _record(scene_id=1, order=1, story_id=1)
    second = _record(scene_id=2, order=2, story_id=2)
    package = build_adaptation(_package(tmp_path, [first, second]), minimum_shots=1, maximum_shots=1, scenes_per_episode=10)
    assert package["episode_count"] == 2
    assert [episode["story_ids"] for episode in package["episodes"]] == [[1], [2]]
