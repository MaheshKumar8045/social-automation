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


def test_enrichment_preserves_existing_identity_anchor():
    from core.visual_generation_policy import enrich_character
    character = {
        "canonical_character_id": 99,
        "canonical_name": "Test Character",
        "visual_profile": {
            "identity_anchor": "vib-approved-anchor",
            "source_facts": [{"attribute": "costume", "value": "approved robe"}],
            "inferred_facts": [],
            "visual_role": "ruler",
        },
    }
    result = enrich_character(character, genre="mythology", world_context={})
    assert result["visual_profile"]["identity_anchor"] == "vib-approved-anchor"
    assert result["visual_profile"]["source_facts"][0]["value"] == "approved robe"


def test_overlay_renderer_missing_input_directory_is_actionable(tmp_path):
    from core.render_text_overlays import process_directory
    package = tmp_path / "all_prompts.json"
    package.write_text('{"scenes": []}', encoding="utf-8")
    result = process_directory(
        tmp_path / "does-not-exist",
        tmp_path / "final",
        package,
    )
    assert result["processed"] == 0
    assert any("input image directory not found" in item for item in result["failures"])


def test_overlay_renderer_does_not_publish_partial_output(tmp_path):
    from core.render_text_overlays import process_directory
    import json
    from PIL import Image

    package = tmp_path / "all_prompts.json"
    package.write_text(json.dumps({"scenes": [{"scene_id": 1, "scene_order": 1, "plan": {"scene_id": 1, "scene_order": 1, "image_dialogue_overlays": [{"text": "Hello"}]}}]}), encoding="utf-8")
    images = tmp_path / "images"
    images.mkdir()
    Image.new("RGB", (100, 100), (90, 90, 90)).save(images / "scene_001.png")
    result = process_directory(
        images,
        tmp_path / "final",
        package,
        expected_count=2,
        require_complete=True,
    )
    assert result["processed"] == 1
    assert result["failures"]
    assert not (tmp_path / "final").exists()
    assert (tmp_path / "final.staging").exists()


def test_first_person_narrative_focus_is_mandatory_and_not_physical_presence():
    character = {
        "canonical_character_id": 101,
        "canonical_name": "Ravana",
        "source_presence": {
            "physical_presence": False,
            "physical_presence_evidence_count": 0,
            "classification": "reference_only",
        },
        "visual_profile": {
            "identity_anchor": "vib-ravana",
            "visual_role": "ruler",
            "source_facts": [],
            "inferred_facts": [],
        },
        "scene_mentions": [{"context": "Ravana Tomorrow is my funeral."}],
    }
    result = enhance_generation_package(
        scene={"scene_order": 1, "title": "The end", "text": "Ravana Tomorrow is my funeral."},
        characters=[character],
        objects=[],
        events=[],
        continuity={"available": True},
        world_profile={},
        genre="mythology",
        media=_media(),
        narrative_focus_character={
            "canonical_name": "Ravana",
            "reason": "first-person narrative with exactly one explicitly named canonical character in the scene source",
        },
    )
    prompt = result["image"]["prompt"]
    assert "NARRATIVE FOCAL CHARACTER (CONTROLLED PRODUCTION INFERENCE): Ravana" in prompt
    assert "do not substitute another person" in prompt.lower()
    assert "TEXT RENDERING IS DISABLED" in prompt
    assert "do not generate words, letters, captions" in prompt.lower()
    assert result["generation_intent"]["visible_characters"] == []
    assert result["generation_intent"]["narrative_focus_character"]["canonical_name"] == "Ravana"


def test_visible_canonical_character_is_explicitly_mandatory_subject():
    character = {
        "canonical_character_id": 102,
        "canonical_name": "Ravana",
        "source_presence": {
            "physical_presence": True,
            "physical_presence_evidence_count": 1,
            "classification": "physical",
        },
        "visual_profile": {
            "identity_anchor": "vib-ravana",
            "visual_role": "ruler",
            "source_facts": [],
            "inferred_facts": [],
        },
        "scene_mentions": [{"context": "Ravana sat on the throne."}],
    }
    result = enhance_generation_package(
        scene={"scene_order": 2, "title": "The throne", "text": "Ravana sat on the throne."},
        characters=[character],
        objects=[],
        events=[{"text": "Ravana sat on the throne."}],
        continuity={"available": True},
        world_profile={},
        genre="mythology",
        media=_media(),
    )
    prompt = result["image"]["prompt"]
    assert "mandatory source-confirmed visible canonical characters: Ravana" in prompt
    assert "do not replace, gender-swap, omit, or substitute" in prompt.lower()


def test_overlay_renderer_fails_closed_when_required_overlay_is_missing(tmp_path):
    import json
    from PIL import Image
    from core.render_text_overlays import process_directory

    package = tmp_path / "all_prompts.json"
    package.write_text(json.dumps({
        "scenes": [{
            "scene_id": 1,
            "scene_order": 1,
            "plan": {
                "scene_id": 1,
                "scene_order": 1,
                "image_dialogue_overlays": [],
            },
        }],
    }), encoding="utf-8")
    images = tmp_path / "images"
    images.mkdir()
    Image.new("RGB", (100, 100), (90, 90, 90)).save(images / "scene_001.png")
    result = process_directory(images, tmp_path / "final", package, expected_count=1, require_complete=True)
    assert result["processed"] == 0
    assert any("required source-derived dialogue/narrative overlay is missing" in item for item in result["failures"])
    assert not (tmp_path / "final").exists()


def test_narrative_focus_prompt_contains_character_identity_lock():
    from core.media_prompt_compiler import compile_media_prompts

    character = {
        "canonical_character_id": 999,
        "canonical_name": "Ravana",
        "source_presence": {
            "physical_presence": False,
            "physical_presence_evidence_count": 0,
            "classification": "reference_only",
        },
        "visual_profile": {
            "identity_anchor": "vib-ravana-test",
            "visual_role": "ruler",
            "source_facts": [
                {
                    "attribute": "gender",
                    "value": "male",
                    "locked_for_continuity": True,
                }
            ],
            "inferred_facts": [],
            "unknown_source_attributes": [],
        },
    }
    result = compile_media_prompts({
        "scene": {
            "scene_order": 1,
            "title": "The end",
            "text": "Ravana Tomorrow is my funeral.",
        },
        "characters": [character],
        "objects": [],
        "events": [],
        "continuity": {},
        "world_profile": {},
        "visual_genre": "general_narrative",
    })
    prompt = result["image"]["prompt"]
    assert "CANONICAL CHARACTER IDENTITY LOCK: Ravana." in prompt
    assert "SOURCE gender=male" in prompt
    assert "NARRATIVE FOCAL CHARACTER EXECUTION RULE" in prompt
