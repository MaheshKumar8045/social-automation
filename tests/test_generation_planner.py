from core.generation_planner import GenerationPlanner


def test_prompt_bundle_preserves_narrative_focus_through_cinematic_enhancement(monkeypatch):
    captured = {}

    media = {
        "schema_version": 5,
        "source_grounded": True,
        "unknowns_must_remain_unknown": True,
        "visual_inference": {},
        "image": {
            "prompt": "Source-grounded cinematic source-anchored scene interpretation; cinematic direction.",
            "dialogue_overlays": [{"box_number": 1, "required": True}],
            "layout": {"aspect_ratio": "9:16"},
        },
        "short_video": {
            "clips": [{"clip_number": 1, "prompt": "source-anchored scene interpretation"}],
            "audio": {},
        },
        "long_video": {
            "shots": [{"shot_number": 1, "prompt": "source-anchored scene interpretation"}],
        },
        "cinematic_scene_intelligence": {
            "intent": {"source_participants": []},
        },
    }

    monkeypatch.setattr(
        "core.generation_planner.compile_media_prompts",
        lambda context: media,
    )

    def fake_enhance(**kwargs):
        captured["narrative_focus_character"] = kwargs["narrative_focus_character"]
        return kwargs["media"]

    monkeypatch.setattr(
        "core.generation_planner.enhance_generation_package",
        fake_enhance,
    )

    focus = {
        "canonical_name": "King Ravana",
        "reason": "first-person narrative with source narrator heading",
    }

    result = GenerationPlanner._prompt_bundle(
        {
            "scene": {"scene_order": 1, "title": "The end", "text": "Ravana Tomorrow is my funeral."},
            "visual_genre": "mythology",
            "continuity": {},
            "world_profile": {},
        },
        [],
        [],
        [],
        [],
        narrative_focus_character=focus,
    )

    assert captured["narrative_focus_character"] == focus
    assert result["media_prompt_package"]["image"]["prompt"]
