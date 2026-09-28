from pathlib import Path

from core.cinematic_assembly import build_video_manifest, write_video_manifests


def test_video_manifest_detects_existing_and_missing_shots(tmp_path):
    image_root = tmp_path / "images"
    image_root.mkdir()
    (image_root / "scene_000001_00001_final.png").write_bytes(b"png")
    adaptation = {
        "source": "book.json",
        "episodes": [{
            "episode_id": 1,
            "shots": [
                {"shot_id": 1, "duration_seconds": 4.0, "overlay_text": "Hello", "voiceover_text": ""},
                {"shot_id": 2, "duration_seconds": 3.5, "overlay_text": "", "voiceover_text": "World"},
            ],
        }],
    }
    manifest = build_video_manifest(adaptation, image_root)
    assert manifest["ready"] is False
    assert manifest["missing_shot_ids"] == [2]
    assert manifest["episodes"][0]["shots"][0]["image"].endswith("scene_000001_00001_final.png")


def test_video_manifest_writes_concat_and_ffmpeg_plan(tmp_path):
    image_root = tmp_path / "images"
    image_root.mkdir()
    (image_root / "scene_000001_00001_final.png").write_bytes(b"png")
    adaptation = {
        "source": "book.json",
        "episodes": [{
            "episode_id": 1,
            "shots": [{"shot_id": 1, "duration_seconds": 4.0, "overlay_text": "", "voiceover_text": ""}],
        }],
    }
    manifest = build_video_manifest(adaptation, image_root)
    out = tmp_path / "out"
    write_video_manifests(manifest, out)
    concat = out / "video" / "episode_001.concat.txt"
    ffmpeg = out / "video" / "episode_001.ffmpeg.txt"
    assert concat.exists()
    assert "duration 4.00" in concat.read_text(encoding="utf-8")
    assert ffmpeg.exists()
    assert "ffmpeg" in ffmpeg.read_text(encoding="utf-8")
