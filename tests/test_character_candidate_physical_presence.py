import sqlite3

from core.character_candidate_gate import gate


def _mentions(*contexts: str) -> list[sqlite3.Row]:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE mentions(scene_id INTEGER, context TEXT)")
    con.executemany("INSERT INTO mentions(scene_id, context) VALUES (?, ?)", list(enumerate(contexts, 1)))
    return con.execute("SELECT scene_id, context FROM mentions ORDER BY scene_id").fetchall()


def test_single_word_character_with_explicit_physical_presence_is_probable():
    decision, score, reasons = gate(
        "Vidyutjihva",
        "character",
        _mentions("A shadow moved behind her, towards the lone burning oil lamp. It was none other than Vidyutjihva. The tall, fair Asura stood there with a contemptuous smile playing on his lips."),
    )
    assert decision in {"validated", "probable"}
    assert score >= 0.48
    assert "source_physical_presence" in reasons


def test_single_word_reference_without_physical_presence_stays_reference_candidate():
    decision, score, reasons = gate(
        "Shiva",
        "character",
        _mentions("I thanked Shiva for not letting me open my mouth."),
    )
    assert decision == "review"
    assert score < 0.48
    assert "source_physical_presence" not in reasons
