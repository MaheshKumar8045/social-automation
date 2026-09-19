from core.refresh_media_prompts import refresh_plan


def _plan():
    return {
        "plan_status": "ready",
        "source_grounded": True,
        "unknowns_must_remain_unknown": True,
        "scene": {"scene_id": 1, "scene_order": 1, "title": "The End", "text": "Rama Tomorrow is my funeral."},
        "characters": [{
            "canonical_character_id": 1,
            "canonical_name": "Rama",
            "scene_mentions": [{"context": "Rama"}],
            "visual_profile": {
                "identity_anchor": "vib-rama",
                "source_facts": [],
                "inferred_facts": [],
            },
        }],
        "objects": [],
        "events": [],
        "continuity": {"available": True},
        "world_profile": {"dimensions": {"culture": {"top": {"label": "indic"}}}},
        "visual_genre": "mythology",
        "generation_constraints": [],
        "source_evidence": [],
        "llm_scene_semantics": {
            "status": "rejected",
            "analysis": None,
            "rejected_reasons": ["visible_character_evidence_not_in_source:Rama"],
        },
    }


def test_refresh_plan_is_deterministic_and_zero_llm():
    result = refresh_plan(_plan())
    assert result["media_prompt_package"]["schema_version"] == 6
    assert result["image_prompt"]
    assert result["image_dialogue_overlays"]
    assert result["short_video_prompt_package"]["clips"]
    assert result["long_video_prompt_package"]["shots"]
    assert result["audio_prompt"]
    assert result["characters"][0]["source_presence"]["classification"] == "reference_only"
    assert "Rama" not in result["image_prompt"].lower()
