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
    assert result["boxes"][0]["width"] <= round(720 * 0.68)
    assert result["boxes"][0]["height"] <= round(1280 * 0.15)

    with Image.open(source).convert("RGB") as before, Image.open(destination).convert("RGB") as after:
        assert ImageChops.difference(before, after).getbbox() is not None


def test_render_overlays_preserves_clean_art_when_no_overlay(tmp_path: Path):
    source = tmp_path / "generated.png"
    destination = tmp_path / "final.png"
    Image.new("RGB", (720, 1280), (90, 90, 90)).save(source)

    result = render_overlays(source, destination, [])

    assert result["rendered"] is False
    assert destination.read_bytes() == source.read_bytes()


def test_render_overlays_stacks_multiple_required_boxes(tmp_path: Path):
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
    assert result["boxes"][0]["y"] < result["boxes"][1]["y"]
    assert result["boxes"][0]["x"] == result["boxes"][1]["x"]
