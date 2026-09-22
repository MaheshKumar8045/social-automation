import sqlite3

from core.character_candidate_gate import gate


def _mentions(*contexts: str) -> list[sqlite3.Row]:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE mentions(scene_id INTEGER, context TEXT)")
    con.executemany("INSERT INTO mentions(scene_id, context) VALUES (?, ?)", list(enumerate(contexts, 1)))
    return con.execute("SELECT scene_id, context FROM mentions ORDER BY scene_id").fetchall()


def _mentions_with_names(*items: tuple[str, str]) -> list[sqlite3.Row]:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE mentions(scene_id INTEGER, context TEXT, mention_text TEXT)")
    con.executemany(
        "INSERT INTO mentions(scene_id, context, mention_text) VALUES (?, ?, ?)",
        [(index, context, mention_text) for index, (context, mention_text) in enumerate(items, 1)],
    )
    return con.execute("SELECT scene_id, context, mention_text FROM mentions ORDER BY scene_id").fetchall()


def test_location_collision_does_not_hide_direct_character():
    decision, score, reasons = gate(
        "Aruna",
        "character",
        _mentions("Aruna said, 'We must go.'"),
        conflicting_entity_types={"location"},
    )
    assert decision in {"validated", "probable"}
    assert score >= 0.48
    assert "direct_person_reference" in reasons
    assert "name_also_classified_as_location_or_environment" in reasons


def test_location_collision_without_person_evidence_is_rejected():
    decision, score, reasons = gate(
        "Mithila",
        "character",
        _mentions("The road to Mithila was long."),
        conflicting_entity_types={"location"},
    )
    assert decision == "non_character"
    assert score == 1.0
    assert reasons == ["ambiguous_name_without_person_evidence"]


def test_location_collision_ignores_unrelated_speech_or_action():
    decision, score, reasons = gate(
        "Mithila",
        "character",
        _mentions("Lord Shiva said, 'We must travel to Mithila.'"),
        conflicting_entity_types={"location"},
    )
    assert decision == "non_character"
    assert score == 1.0
    assert reasons == ["ambiguous_name_without_person_evidence"]



def test_titled_canonical_character_accepts_safe_source_alias():
    decision, score, reasons = gate(
        "King Ravana",
        "character",
        _mentions_with_names(
            ("I, Ravana, have come a long way.", "Ravana"),
            ("The mighty king Ravana stood before us.", "Ravana"),
            ("King Ravana spoke to the court.", "Ravana"),
        ),
    )
    assert decision == "validated"
    assert score >= 0.75
    assert "direct_person_reference" in reasons
    assert "source_physical_presence" in reasons


def test_malformed_source_entity_name_does_not_gain_alias_from_short_name():
    decision, score, reasons = gate(
        "Ravana Tomorrow",
        "character",
        _mentions_with_names(
            ("Ravana Tomorrow is my funeral.", "Ravana Tomorrow"),
            ("Ravana Tomorrow is not a person named in the source.", "Ravana Tomorrow"),
        ),
    )
    assert decision == "review"
    assert score < 0.48
    assert "untitled_name_without_repeated_direct_evidence" in reasons
