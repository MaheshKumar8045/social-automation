from pathlib import Path

from PIL import Image, ImageChops

from core.image_pipeline.overlay_renderer import render_overlays


def test_render_overlays_creates_deterministic_final_artifact(tmp_path: Path):
    source = tmp_path / "generated.png"
    destination = tmp_path / "final.png"
    Image.new("RGB", (720, 1280), (90, 90, 90)).save(source)

    result = render_overlays(
        source,
        destination,
        [{
            "box_number": 1,
            "box_type": "narrative_box",
            "text": "The end Ravana Tomorrow is my funeral.",
            "required": True,
            "max_width_percent": 68,
            "max_height_percent": 15,
        }],
    )

    assert destination.exists()
    assert result["rendered"] is True
    assert result["boxes"][0]["text"].startswith("The end Ravana")
    assert result["boxes"][0]["width"] <= round(720 * 0.60)
    assert result["boxes"][0]["height"] <= round(1280 * 0.18)
    assert result["boxes"][0]["background"] == "transparent"
    assert result["boxes"][0]["outline_color"] == "#080B0D"
    assert result["boxes"][0]["font_size"] >= 22

    with Image.open(source).convert("RGB") as before, Image.open(destination).convert("RGB") as after:
        assert ImageChops.difference(before, after).getbbox() is not None


def test_render_overlays_preserves_clean_art_when_no_overlay(tmp_path: Path):
    source = tmp_path / "generated.png"
    destination = tmp_path / "final.png"
    Image.new("RGB", (720, 1280), (90, 90, 90)).save(source)

    result = render_overlays(source, destination, [])

    assert result["rendered"] is False
    assert destination.read_bytes() == source.read_bytes()


def test_render_overlays_places_multiple_boxes_in_separate_regions(tmp_path: Path):
    source = tmp_path / "generated.png"
    destination = tmp_path / "final.png"
    Image.new("RGB", (720, 1280), (90, 90, 90)).save(source)

    result = render_overlays(
        source,
        destination,
        [
            {"box_number": 1, "text": "First source line.", "required": True},
            {"box_number": 2, "text": "Second source line.", "required": True},
        ],
    )

    assert len(result["boxes"]) == 2
    first = result["boxes"][0]
    second = result["boxes"][1]
    assert first["background"] == "transparent"
    assert second["background"] == "transparent"
    first_right = first["x"] + first["width"]
    first_bottom = first["y"] + first["height"]
    second_right = second["x"] + second["width"]
    second_bottom = second["y"] + second["height"]
    assert (
        first_right <= second["x"]
        or second_right <= first["x"]
        or first_bottom <= second["y"]
        or second_bottom <= first["y"]
    )


def test_generation_store_serializes_windows_paths(tmp_path: Path):
    from core.image_pipeline.models import JobStatus, SceneJob
    from core.image_pipeline.store import GenerationStore

    db = tmp_path / "generation.db"
    store = GenerationStore(db)
    job = SceneJob(
        scene_id=1,
        scene_order=1,
        title="Test",
        prompt="test",
        overlays=[],
        record={},
    )
    store.ensure_jobs([job], {1: "hash"})
    validation = tmp_path / "validation.json"
    store.set_status(1, JobStatus.VALIDATED, validation_path=validation)
    row = store.get(1)
    store.close()

    assert row["validation_path"] == str(validation)


def test_render_overlays_never_clips_long_text_at_image_edges(tmp_path: Path):
    for width, height in ((896, 1200), (768, 1376)):
        source = tmp_path / f"source_{width}.png"
        destination = tmp_path / f"final_{width}.png"
        Image.new("RGB", (width, height), (70, 80, 90)).save(source)

        result = render_overlays(
            source,
            destination,
            [{
                "box_number": 1,
                "box_type": "dialogue_box",
                "text": (
                    "I do not know if they will remember me like a mangy dog "
                    "or whether I will get a funeral fit for an Emperor."
                ),
                "required": True,
                "max_width_percent": 60,
                "max_height_percent": 18,
            }],
        )

        box = result["boxes"][0]
        safe_margin = round(width * 0.07)
        assert box["x"] >= safe_margin
        assert box["y"] >= safe_margin
        assert box["x"] + box["width"] <= width - safe_margin
        assert box["y"] + box["height"] <= height - safe_margin
        assert box["font_size"] >= 56
        assert box["background"] == "transparent"
