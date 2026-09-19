from pathlib import Path

from PIL import Image

from core.cinematic_generation import enhance_generation_package
from core.render_text_overlays import render_overlays
from core.visual_continuity import character_identity_block, fixed_style_block, subject_policy


def _media():
    return {
        "schema_version": 5,
        "source_grounded": True,
        "unknowns_must_remain_unknown": True,
        "visual_inference": {"enabled": True},
        "image": {"prompt": "old", "dialogue_overlays": [], "layout": {"aspect_ratio": "9:16"}},
        "short_video": {"clip_count": 2, "clips": []},
        "long_video": {"shots": []},
    }


def _context(text, characters=None, events=None):
    return {
        "scene": {"scene_order": 1, "title": "Test Scene", "text": text},
        "characters": characters or [],
        "objects": [],
        "events": events or [],
        "continuity": {"available": True},
        "world_profile": {"dimensions": {"culture": {"top": {"label": "indic"}}}},
        "genre": "mythology",
    }


def test_environment_scene_gets_hard_subject_exclusion_and_fixed_style():
    result = enhance_generation_package(
        media=_media(),
        **_context("The ruined city lies silent beneath smoke and ash."),
    )
    prompt = result["image"]["prompt"].lower()
    assert "keep the frame free of human or humanoid subjects" in prompt
    assert "global cinematic art direction (locked for every scene)" in prompt
    assert "text / overlay policy" in prompt
    assert "do not draw, spell, simulate, or invent dialogue/caption text" in prompt


def test_visible_character_gets_immutable_identity_block():
    character = {
        "canonical_character_id": 7,
        "canonical_name": "Rama",
        "source_presence": {
            "physical_presence": True,
            "physical_presence_evidence_count": 1,
            "classification": "physical",
        },
        "visual_profile": {
            "identity_anchor": "vib-rama-fixed",
            "visual_role": "warrior",
            "source_facts": [
                {"attribute": "costume", "value": "blue robe"},
            ],
            "inferred_facts": [],
        },
        "scene_mentions": [{"context": "Rama stood at the gate."}],
    }
    result = enhance_generation_package(
        media=_media(),
        **_context(
            "Rama stood at the gate.",
            characters=[character],
            events=[{"text": "Rama stood at the gate."}],
        ),
    )
    prompt = result["image"]["prompt"]
    assert "CANONICAL CHARACTER IDENTITY LOCK: Rama" in prompt
    assert "Identity anchor: vib-rama-fixed" in prompt
    assert "SOURCE costume=blue robe" in prompt


def test_reference_only_character_does_not_get_identity_block():
    character = {
        "canonical_character_id": 8,
        "canonical_name": "Rama",
        "source_presence": {
            "physical_presence": False,
            "physical_presence_evidence_count": 0,
            "classification": "reference_only",
        },
        "visual_profile": {
            "identity_anchor": "vib-rama-fixed",
            "source_facts": [{"attribute": "costume", "value": "blue robe"}],
            "inferred_facts": [],
        },
        "scene_mentions": [{"context": "I remembered Rama after the war."}],
    }
    result = enhance_generation_package(
        media=_media(),
        **_context("I remembered Rama after the war.", characters=[character]),
    )
    prompt = result["image"]["prompt"]
    assert "VISIBLE SOURCE-CONFIRMED CHARACTERS: none" in prompt
    assert "CANONICAL CHARACTER IDENTITY LOCK: Rama" not in prompt
    assert "blue robe" not in prompt


def test_fixed_style_block_is_identical_across_scenes():
    first = fixed_style_block({}, "mythology")
    second = fixed_style_block({}, "mythology")
    assert first == second
    assert "fixed project grade" in first


def test_deterministic_overlay_produces_consistent_panel_and_legible_text():
    image = Image.new("RGB", (900, 1600), (90, 90, 90))
    boxes = [{"text": "Tomorrow is my funeral.", "box_number": 1}]
    first = render_overlays(image, boxes)
    second = render_overlays(image, boxes)
    assert first.size == second.size == image.size
    assert first.tobytes() == second.tobytes()
    assert first.tobytes() != image.convert("RGBA").tobytes()
