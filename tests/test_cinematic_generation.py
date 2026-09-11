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


def test_ocr_heading_and_speaker_name_are_removed_from_first_person_dialogue():
    context = _context("1 The end Ravana Tomorrow is my funeral.")
    result = enhance_generation_package(media=_media(), **context)
    overlay_texts = [item["text"] for item in result["image"]["dialogue_overlays"]]
    assert overlay_texts[0] == "Tomorrow is my funeral."
    assert "Ravana" not in overlay_texts[0]
    assert "The end" not in overlay_texts[0]


def test_referenced_character_is_not_rendered_without_physical_presence_evidence():
    context = _context("Kumbha was captured by my son. Lord Shiva watched the dying embers.")
    context["characters"] = [{
        "canonical_character_id": 2,
        "canonical_name": "Kumbha",
        "visual_profile": {"identity_anchor": "vib-kumbha", "source_facts": [], "inferred_facts": []},
        "scene_mentions": [{"entity_id": 11, "context": "my son captured Kumbha."}],
    }]
    context["events"] = [{"text": "Kumbha was captured by my son.", "event_order": 1}]
    result = enhance_generation_package(media=_media(), **context)
    assert result["image"]["character_blocking"] == ["Kumbha: Kumbha was captured by my son."]


def test_name_only_reference_is_not_treated_as_visible_character():
    context = _context("I remembered Kumbha after the city was destroyed.")
    context["characters"] = [{
        "canonical_character_id": 2,
        "canonical_name": "Kumbha",
        "visual_profile": {"identity_anchor": "vib-kumbha", "source_facts": [], "inferred_facts": []},
        "scene_mentions": [{"entity_id": 11, "context": "Kumbha"}],
    }]
    context["events"] = []
    result = enhance_generation_package(media=_media(), **context)
    assert result["image"]["character_blocking"] == []
    assert result["image"]["referenced_characters"] == ["Kumbha"]
    assert "no visible canonical characters are source-confirmed" in result["image"]["prompt"]


def test_character_name_from_speaker_prefix_does_not_become_visible_without_physical_evidence():
    context = _context("Ravana Tomorrow is my funeral.")
    context["characters"] = [{
        "canonical_character_id": 3,
        "canonical_name": "Ravana",
        "visual_profile": {"identity_anchor": "vib-ravana", "source_facts": [], "inferred_facts": []},
        "scene_mentions": [{"entity_id": 12, "context": "Ravana"}],
    }]
    result = enhance_generation_package(media=_media(), **context)
    assert result["image"]["character_blocking"] == []
    assert result["image"]["referenced_characters"] == ["Ravana"]


def test_character_blocking_stays_tied_to_character_mention():
    result = enhance_generation_package(media=_media(), **_context("Lord Shiva watched the dying embers of the city."))
    blocking = result["image"]["character_blocking"]
    assert blocking
    assert blocking[0].startswith("Lord Shiva:")


def test_video_prompts_receive_scene_specific_cinematic_direction():
    result = enhance_generation_package(media=_media(), **_context("The warriors crossed the ruined gate."))
    assert all("SOURCE-ANCHORED SCENE INTERPRETATION" in c["prompt"] for c in result["short_video"]["clips"])
    assert all("CINEMATIC DIRECTION" in s["prompt"] for s in result["long_video"]["shots"])
