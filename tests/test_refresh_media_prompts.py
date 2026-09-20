from core.prompt_export import validate_plan
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
    assert result["generation_intent"]["narrative_focus_character"]["canonical_name"] == "Rama"
    assert "NARRATIVE FOCAL CHARACTER (CONTROLLED PRODUCTION INFERENCE): Rama" in result["image_prompt"]
    assert validate_plan(result) == []


def test_refresh_plan_recomputes_presence_and_emits_identity_lock():
    plan = _plan()
    plan["scene"]["text"] = "Professor Mayan stood at the gate."
    plan["characters"][0]["canonical_name"] = "Professor Mayan"
    plan["characters"][0]["scene_mentions"] = [{"context": "Professor Mayan stood at the gate."}]
    plan["characters"][0]["source_presence"] = {
        "physical_presence": False,
        "physical_presence_evidence_count": 0,
        "classification": "reference_only",
    }
    plan["characters"][0]["visual_profile"]["identity_anchor"] = "vib-mayan"
    plan["events"] = [{"text": "Professor Mayan stood at the gate.", "event_order": 1}]
    result = refresh_plan(plan)
    assert result["characters"][0]["source_presence"]["physical_presence"] is True
    assert "CANONICAL CHARACTER IDENTITY LOCK: Professor Mayan" in result["image_prompt"]
    assert validate_plan(result) == []


def test_refresh_plan_can_carry_first_person_narrative_focus():
    plan = _plan()
    plan["scene"]["text"] = "Sounds of joy float down to me from my city."
    plan["characters"] = [{
        "canonical_character_id": 1,
        "canonical_name": "Ravana",
        "scene_mentions": [],
        "visual_profile": {
            "identity_anchor": "vib-ravana",
            "source_facts": [],
            "inferred_facts": [],
        },
    }]
    result = refresh_plan(
        plan,
        narrative_focus_character={
            "canonical_name": "Ravana",
            "reason": "carried deterministic first-person narrative focus from the immediately preceding scene",
        },
    )
    assert "NARRATIVE FOCAL CHARACTER (CONTROLLED PRODUCTION INFERENCE): Ravana" in result["image_prompt"]
    assert result["image_dialogue_overlays"]
    assert result["image_dialogue_overlays"][0]["required"] is True
