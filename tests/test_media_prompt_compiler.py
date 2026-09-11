from core.media_prompt_compiler import compile_media_prompts
from core.visual_generation_policy import build_inferred_visual_profile, load_visual_policy


def _context(text="A powerful figure walks toward the gate."):
    return {
        "visual_genre": "mythological_epic",
        "scene": {"scene_order": 1, "title": "The Gate", "text": text},
        "characters": [{
            "canonical_character_id": 7,
            "canonical_name": "Lord Shiva",
            "status": "confirmed",
            "confidence": 1.0,
            "visual_facts": [],
            "scene_mentions": [{
                "entity_id": 17,
                "context": "Lord Shiva walks toward the gate.",
                "page_start": 1,
                "page_end": 1,
                "confidence": 1.0,
            }],
        }],
        "objects": [{"canonical_name": "gate"}],
        "events": [{"text": "Lord Shiva walks toward the gate.", "event_order": 1}],
        "continuity": {"available": True, "environment_state": {}},
        "generation_constraints": [],
    }


def test_unknown_visuals_receive_controlled_inference():
    result = build_inferred_visual_profile(
        _context()["characters"][0],
        policy=load_visual_policy(),
    )
    assert result["inferred_facts"]
    assert all(item["basis"] == "genre_prior" for item in result["inferred_facts"])
    assert result["identity_anchor"].startswith("vib-")


def test_source_facts_block_conflicting_inference_bucket():
    character = _context()["characters"][0].copy()
    character["visual_facts"] = [{
        "category": "appearance",
        "attribute": "build",
        "value": "slender",
        "status": "supported",
        "confidence": 1.0,
    }]
    result = build_inferred_visual_profile(character)
    assert not any(
        item["attribute"] == "physique"
        and item["value"] == "powerful healthy athletic physique"
        for item in result["inferred_facts"]
    )


def test_image_is_mobile_first_and_has_required_box():
    media = compile_media_prompts(_context())
    assert media["image"]["layout"]["aspect_ratio"] == "9:16"
    assert media["image"]["layout"]["dialogue_box_count_minimum"] >= 1
    assert media["image"]["dialogue_overlays"]
    assert "9:16" in media["image"]["prompt"]
    assert "identity anchor" in media["image"]["prompt"].lower()


def test_source_dialogue_is_preserved():
    context = _context('Lord Shiva said, "Come with me now."')
    media = compile_media_prompts(context)
    overlays = media["image"]["dialogue_overlays"]
    assert overlays
    assert overlays[0]["text"] == "Come with me now."
    assert overlays[0]["text_source"] == "source_dialogue"


def test_no_source_dialogue_still_reserves_a_box_without_faking_speech():
    media = compile_media_prompts(_context("The gate stands before the travelers."))
    overlay = media["image"]["dialogue_overlays"][0]
    assert overlay["required"] is True
    assert overlay["box_type"] == "narrative_box"
    assert overlay["text_source"] == "source_scene_title"


def test_visual_moment_selection_prefers_action_and_character_context():
    media = compile_media_prompts(_context(
        "The society was democratic. Lord Shiva walks toward the gate. "
        "The northern plains were broad and distant."
    ))
    assert "Lord Shiva walks toward the gate" in media["image"]["prompt"]


def test_deterministic_output():
    ctx = _context()
    assert compile_media_prompts(ctx) == compile_media_prompts(ctx)
