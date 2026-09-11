from core.cinematic_generation import enhance_generation_package


def _media():
    return {
        "schema_version": 5,
        "source_grounded": True,
        "unknowns_must_remain_unknown": True,
        "visual_inference": {"enabled": True},
        "image": {
            "prompt": "old prompt",
            "dialogue_overlays": [],
            "layout": {"aspect_ratio": "9:16"},
        },
        "short_video": {
            "clip_count": 2,
            "clips": [
                {"clip_number": 1, "role": "establish the environment", "prompt": "old"},
                {"clip_number": 2, "role": "show the primary source action", "prompt": "old"},
            ],
        },
        "long_video": {
            "shots": [
                {"shot_number": 1, "purpose": "wide establishing shot", "prompt": "old"},
                {"shot_number": 2, "purpose": "action-focused shot", "prompt": "old"},
            ],
        },
    }


def _context(text: str):
    return {
        "scene": {"scene_order": 1, "title": "The End", "text": text},
        "characters": [{
            "canonical_character_id": 1,
            "canonical_name": "Lord Shiva",
            "visual_profile": {
                "identity_anchor": "vib-shiva",
                "source_facts": [],
                "inferred_facts": [],
            },
            "scene_mentions": [{
                "entity_id": 10,
                "context": "Lord Shiva watched the dying embers of the city.",
            }],
        }],
        "objects": [],
        "events": [{"text": "Lord Shiva watched the dying embers of the city.", "event_order": 1}],
        "continuity": {"available": True},
        "world_profile": {"dimensions": {"culture": {"top": {"label": "indic"}}}},
        "genre": "mythology",
    }


def test_destruction_scene_gets_environment_led_cinematic_direction():
    result = enhance_generation_package(media=_media(), **_context("I can still see the dying embers in what was once a fine city."))
    direction = result["image"]["cinematic_direction"]
    assert "wide establishing" in direction["framing"]
    assert result["image"]["source_visual_moments"]
    assert "CINEMATIC" in result["image"]["prompt"]
    assert "SOURCE-ANCHORED SCENE INTERPRETATION" in result["image"]["prompt"]


def test_first_person_source_sentence_can_be_used_without_inventing_quote():
    result = enhance_generation_package(media=_media(), **_context("I should have killed him when my son captured him."))
    overlays = result["image"]["dialogue_overlays"]
    assert overlays[0]["text"] == "I should have killed him when my son captured him."
    assert overlays[0]["text_source"] == "source_dialogue_or_first_person_source_sentence"


def test_character_blocking_stays_tied_to_character_mention():
    result = enhance_generation_package(media=_media(), **_context("Lord Shiva watched the dying embers of the city."))
    blocking = result["image"]["character_blocking"]
    assert blocking
    assert blocking[0].startswith("Lord Shiva:")


def test_video_prompts_receive_scene_specific_cinematic_direction():
    result = enhance_generation_package(media=_media(), **_context("The warriors crossed the ruined gate."))
    assert all("SOURCE-ANCHORED SCENE INTERPRETATION" in c["prompt"] for c in result["short_video"]["clips"])
    assert all("CINEMATIC DIRECTION" in s["prompt"] for s in result["long_video"]["shots"])
