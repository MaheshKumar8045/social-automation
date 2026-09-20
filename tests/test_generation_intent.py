from core.generation_intent import build_generation_intent


def _intent(text, *, events=None, characters=None, dialogue=None):
    return build_generation_intent(
        scene={"scene_order": 2, "title": "The End", "text": text},
        characters=characters or [],
        objects=[],
        events=events or [],
        continuity={"available": True},
        dialogue=dialogue or [],
        genre="mythology",
    )


def test_event_fragment_is_completed_to_source_sentence():
    text = "The city burned. The enemy celebrated his victory when the gates fell."
    result = _intent(text, events=[{"text": "The enemy celebrated his victory when"}])
    assert result["primary_visual_moment"] == "The enemy celebrated his victory when the gates fell."
    assert all(moment in text for moment in result["visual_moment_candidates"])
    assert all(not moment.lower().endswith(" when") for moment in result["visual_moment_candidates"])


def test_no_source_sentence_falls_back_to_complete_sentence_not_truncated_fragment():
    text = "The temples were looted. Smoke covered the streets."
    result = _intent(text)
    assert result["visual_moment_candidates"] == ["The temples were looted.", "Smoke covered the streets."]


def test_referenced_character_is_not_visible():
    chars = [{"canonical_name": "Rama", "scene_mentions": [{"context": "I remembered Rama after the battle."}]}]
    result = _intent("I remembered Rama after the battle.", characters=chars)
    assert result["visible_characters"] == []
    assert result["referenced_characters"] == ["Rama"]


def test_physical_character_event_is_visible():
    chars = [{"canonical_name": "Kumbha", "scene_mentions": [{"context": "Kumbha fought at the gate."}]}]
    events = [{"text": "Kumbha fought at the gate."}]
    result = _intent("Kumbha fought at the gate.", characters=chars, events=events)
    assert result["visible_characters"] == [{"name": "Kumbha", "evidence": "Kumbha fought at the gate."}]


def test_source_established_anonymous_participants_are_separate_from_canonical_characters():
    text = "The enemy is celebrating his victory. The monkey-men will be busy plundering Trikota."
    result = _intent(text)
    assert result["visible_characters"] == []
    assert [item["label"] for item in result["source_participants"]] == ["The enemy", "The monkey-men"]
    assert all(item["evidence"] in text for item in result["source_participants"])


def test_named_character_is_not_reclassified_as_anonymous_participant():
    text = "Rama stood over me after I had fallen."
    chars = [{"canonical_name": "Rama", "scene_mentions": [{"context": text}]}]
    result = _intent(text, characters=chars)
    assert result["visible_characters"] == [{"name": "Rama", "evidence": text}]
    assert result["source_participants"] == []


def test_cinematic_arc_matches_destruction():
    result = _intent("The city burned and the temples were destroyed.")
    assert result["emotional_signal"] == "destruction"
    assert result["cinematic_arc"] == ["establish", "consequence", "detail"]


def test_cinematic_arc_matches_travel():
    result = _intent("The warriors crossed the river and reached the city.")
    assert result["emotional_signal"] == "travel"
    assert result["cinematic_arc"] == ["establish", "movement", "destination"]


def test_first_person_dialogue_is_marked_as_narration():
    result = _intent("I watched the ruined city from afar.", dialogue=["I watched the ruined city from afar."])
    assert result["dialogue_kind"] == "first_person_narration"


def test_source_presence_is_authoritative_for_visible_character_intent():
    character = {
        "canonical_name": "Professor Mayan",
        "source_presence": {
            "physical_presence": True,
            "physical_presence_evidence_count": 1,
            "classification": "physical",
        },
        "scene_mentions": [
            {
                "context": "Professor Mayan was there with twenty of his best technicians."
            }
        ],
    }
    result = _intent(
        "One by one, the delegates arrived. Professor Mayan was there with twenty of his best technicians.",
        characters=[character],
        events=[],
    )
    assert result["visible_characters"]
    assert result["visible_characters"][0]["name"] == "Professor Mayan"


def test_reference_only_presence_does_not_become_visible():
    character = {
        "canonical_name": "Professor Mayan",
        "source_presence": {
            "physical_presence": False,
            "physical_presence_evidence_count": 0,
            "classification": "reference_only",
        },
        "scene_mentions": [
            {
                "context": "Maricha had brought Professor Mayan with twenty technicians."
            }
        ],
    }
    result = _intent(
        "Maricha had brought Professor Mayan with twenty technicians.",
        characters=[character],
        events=[],
    )
    assert result["visible_characters"] == []
    assert result["referenced_characters"] == ["Professor Mayan"]


def test_authoritative_reference_only_overrides_legacy_visibility_heuristic():
    character = {
        "canonical_name": "Rama",
        "source_presence": {
            "physical_presence": False,
            "physical_presence_evidence_count": 0,
            "classification": "reference_only",
        },
        "scene_mentions": [{"context": "Rama stood at the gate."}],
    }
    result = _intent(
        "Rama stood at the gate.",
        characters=[character],
        events=[{"text": "Rama stood at the gate.", "event_order": 1}],
    )
    assert result["visible_characters"] == []
    assert result["referenced_characters"] == ["Rama"]


def test_authoritative_physical_presence_survives_source_whitespace_normalization():
    character = {
        "canonical_name": "Professor Mayan",
        "source_presence": {
            "physical_presence": True,
            "physical_presence_evidence_count": 1,
            "classification": "physical",
        },
        "scene_mentions": [{"context": "Professor Mayan was\tthere with technicians."}],
    }
    result = _intent(
        "One by one, the delegates arrived. Professor Mayan was there with technicians.",
        characters=[character],
        events=[],
    )
    assert result["visible_characters"]
    assert result["visible_characters"][0]["name"] == "Professor Mayan"


def test_first_person_scene_with_one_named_canonical_character_resolves_narrative_focus():
    chars = [{
        "canonical_name": "Ravana",
        "source_presence": {
            "physical_presence": False,
            "physical_presence_evidence_count": 0,
            "classification": "reference_only",
        },
        "scene_mentions": [{"context": "Ravana Tomorrow is my funeral."}],
    }]
    result = _intent(
        "Ravana Tomorrow is my funeral.",
        characters=chars,
        dialogue=["Tomorrow is my funeral."],
    )
    assert result["visible_characters"] == []
    assert result["narrative_focus_character"]["canonical_name"] == "Ravana"


def test_ambiguous_first_person_scene_does_not_invent_narrative_focus():
    chars = [
        {"canonical_name": "Ravana", "scene_mentions": [{"context": "Ravana spoke to Hanuman."}]},
        {"canonical_name": "Hanuman", "scene_mentions": [{"context": "Ravana spoke to Hanuman."}]},
    ]
    result = _intent(
        "Ravana spoke to Hanuman. I remembered the city.",
        characters=chars,
        dialogue=["I remembered the city."],
    )
    assert result["narrative_focus_character"] is None


def test_visual_moments_preserve_source_order_over_later_high_salience_events():
    from core.generation_intent import _candidate_moments

    scene = {
        "scene_order": 1,
        "text": (
            "Tomorrow is my funeral. I can hear the jackals eating my friends and family. "
            "My beloved Lanka is being destroyed. My capital, Trikota, was the greatest city in the world."
        ),
    }
    events = [
        {"text": "My beloved Lanka is being destroyed."},
        {"text": "Tomorrow is my funeral."},
    ]
    moments = _candidate_moments(scene, events, [])
    assert moments[0] == "Tomorrow is my funeral."
    assert moments[1].startswith("I can hear the jackals")
    assert moments[2] == "My beloved Lanka is being destroyed."
