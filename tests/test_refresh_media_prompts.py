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


def test_refresh_plan_does_not_mark_burning_city_as_physical_character():
    plan = _plan()
    plan["scene"]["text"] = (
        "Ravana Tomorrow is my funeral. My capital, Trikota, was the greatest city in the world. "
        "Trikota burned for days. Hanuman did that to us."
    )
    plan["characters"] = [
        {
            "canonical_character_id": 10,
            "canonical_name": "Trikota",
            "scene_mentions": [{"context": "My capital, Trikota, was the greatest city in the world. Trikota burned for days."}],
            "visual_profile": {"identity_anchor": "vib-trikota", "source_facts": [], "inferred_facts": []},
        },
        {
            "canonical_character_id": 11,
            "canonical_name": "Hanuman",
            "scene_mentions": [{"context": "Hanuman did that to us."}],
            "visual_profile": {"identity_anchor": "vib-hanuman", "source_facts": [], "inferred_facts": []},
        },
    ]
    result = refresh_plan(plan)
    by_name = {c["canonical_name"]: c for c in result["characters"]}
    assert by_name["Trikota"]["source_presence"]["physical_presence"] is False
    assert by_name["Hanuman"]["source_presence"]["physical_presence"] is False


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


def test_refresh_package_resolves_first_person_focus_from_document_character_index(tmp_path):
    import json
    from core.refresh_media_prompts import refresh_package

    first = _plan()
    first["scene"]["scene_order"] = 1
    first["scene"]["text"] = "Ravana Tomorrow is my funeral. I can hear the jackals."
    first["characters"] = [{
        "canonical_character_id": 10,
        "canonical_name": "Trikota",
        "scene_mentions": [{"context": "My capital, Trikota, was the greatest city in the world. Trikota burned for days."}],
        "visual_profile": {"identity_anchor": "vib-trikota", "visual_role": "deity", "source_facts": [], "inferred_facts": []},
    }]

    second = _plan()
    second["scene"]["scene_order"] = 2
    second["scene"]["text"] = "Ravana walked through the ruins."
    second["characters"] = [{
        "canonical_character_id": 20,
        "canonical_name": "Ravana",
        "scene_mentions": [{"context": "Ravana walked through the ruins."}],
        "visual_profile": {"identity_anchor": "vib-ravana", "visual_role": "ruler", "source_facts": [], "inferred_facts": []},
    }]

    package = {
        "schema_version": 2,
        "document_id": 1,
        "scene_count": 2,
        "scenes": [
            {"scene_id": 1, "story_id": 1, "scene_order": 1, "title": "Scene 1", "plan": first},
            {"scene_id": 2, "story_id": 1, "scene_order": 2, "title": "Scene 2", "plan": second},
        ],
    }
    source = tmp_path / "all_prompts.json"
    source.write_text(json.dumps(package), encoding="utf-8")
    output = tmp_path / "refresh"
    summary = refresh_package(source, output)

    assert summary["qa_passed"] is True
    refreshed = json.loads((output / "all_prompts.json").read_text(encoding="utf-8"))["scenes"]
    first_plan = refreshed[0]["plan"]
    assert first_plan["narrative_focus_character"]["canonical_name"] == "Ravana"
    assert "NARRATIVE FOCAL CHARACTER (CONTROLLED PRODUCTION INFERENCE): Ravana" in first_plan["image_prompt"]
    assert "mandatory source-confirmed visible canonical characters: Trikota" not in first_plan["image_prompt"]
    assert "CANONICAL CHARACTER IDENTITY LOCK: Ravana" in first_plan["image_prompt"]


def test_refresh_package_carries_first_person_focus_to_adjacent_scene(tmp_path):
    import json
    from core.refresh_media_prompts import refresh_package

    first = _plan()
    first["scene"]["scene_order"] = 1
    first["scene"]["text"] = "Ravana Tomorrow is my funeral."
    first["characters"][0]["canonical_name"] = "Ravana"
    first["characters"][0]["scene_mentions"] = [{"context": "Ravana Tomorrow is my funeral."}]
    first["characters"][0]["visual_profile"]["identity_anchor"] = "vib-ravana"

    second = _plan()
    second["scene"]["scene_order"] = 2
    second["scene"]["text"] = "Sounds of joy float down to me from my city."
    second["characters"] = []

    package = {
        "schema_version": 2,
        "document_id": 1,
        "scene_count": 2,
        "scenes": [
            {"scene_id": 1, "story_id": 1, "scene_order": 1, "title": "Scene 1", "plan": first},
            {"scene_id": 2, "story_id": 1, "scene_order": 2, "title": "Scene 2", "plan": second},
        ],
    }
    source = tmp_path / "all_prompts.json"
    source.write_text(json.dumps(package), encoding="utf-8")
    output = tmp_path / "refresh"
    summary = refresh_package(source, output)

    assert summary["qa_passed"] is True
    refreshed = json.loads((output / "all_prompts.json").read_text(encoding="utf-8"))["scenes"]
    second_plan = refreshed[1]["plan"]
    assert second_plan["narrative_focus_character"]["canonical_name"] == "Ravana"
    assert "NARRATIVE FOCAL CHARACTER (CONTROLLED PRODUCTION INFERENCE): Ravana" in second_plan["image_prompt"]


def test_refresh_package_resolves_flattened_narrator_from_document_canonical_alias(tmp_path):
    import json
    import sqlite3
    from core.refresh_media_prompts import refresh_package

    db = tmp_path / "source.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE canonical_characters (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            canonical_name TEXT,
            status TEXT,
            confidence REAL
        );
        CREATE TABLE canonical_character_aliases (
            id INTEGER PRIMARY KEY,
            canonical_character_id INTEGER,
            alias TEXT,
            relationship TEXT,
            confidence REAL
        );
        CREATE TABLE canonical_visual_profiles (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            canonical_character_id INTEGER
        );
        CREATE TABLE canonical_visual_facts (
            id INTEGER PRIMARY KEY,
            canonical_visual_profile_id INTEGER,
            category TEXT,
            attribute TEXT,
            value TEXT,
            status TEXT,
            confidence REAL,
            scene_id INTEGER,
            page_start INTEGER,
            page_end INTEGER,
            evidence TEXT
        );
    """)
    con.execute(
        "INSERT INTO canonical_characters VALUES (10, 1, 'King Ravana', 'confirmed', 1.0)"
    )
    con.execute(
        "INSERT INTO canonical_character_aliases VALUES (1, 10, 'Ravana', 'alias', 1.0)"
    )
    con.execute(
        "INSERT INTO canonical_visual_profiles VALUES (1, 1, 10)"
    )
    con.commit()
    con.close()

    plan = _plan()
    plan["scene"]["scene_order"] = 1
    plan["scene"]["text"] = "1 The end Ravana Tomorrow is my funeral. I can hear the jackals."
    plan["characters"] = [{
        "canonical_character_id": 30,
        "canonical_name": "Trikota",
        "scene_mentions": [{"context": "My capital, Trikota, was the greatest city in the world."}],
        "visual_profile": {"identity_anchor": "vib-trikota", "source_facts": [], "inferred_facts": []},
    }]

    package = {
        "schema_version": 2,
        "document_id": 1,
        "source_database": str(db),
        "scene_count": 1,
        "scenes": [
            {"scene_id": 1, "story_id": 1, "scene_order": 1, "title": "I. The end — Scene 1", "plan": plan},
        ],
    }
    source = tmp_path / "all_prompts.json"
    source.write_text(json.dumps(package), encoding="utf-8")
    output = tmp_path / "refresh"

    summary = refresh_package(source, output)
    assert summary["qa_passed"] is True

    refreshed = json.loads((output / "all_prompts.json").read_text(encoding="utf-8"))
    result = refreshed["scenes"][0]["plan"]

    assert result["generation_intent"]["primary_visual_moment"] == "Tomorrow is my funeral."
    assert result["generation_intent"]["narrative_focus_character"]["canonical_name"] == "King Ravana"
    assert result["generation_intent"]["visible_characters"] == []
    assert "CANONICAL CHARACTER IDENTITY LOCK: King Ravana" in result["image_prompt"]
    assert "NARRATIVE FOCAL CHARACTER (CONTROLLED PRODUCTION INFERENCE): King Ravana" in result["image_prompt"]
