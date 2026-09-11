import sqlite3

from core.world_context import analyze_text, build_world_profile


def test_mythology_classification_is_source_driven():
    result = analyze_text(
        "Rama and Sita pray at the temple. Shiva is invoked and the king returns to Lanka."
    )
    assert result["llm_used"] is False
    assert result["dimensions"]["narrative_type"]["top"]["label"] == "mythology"
    assert result["dimensions"]["religious_context"]["top"]["label"] == "hindu"
    assert result["dimensions"]["culture"]["top"]["label"] == "indic"


def test_historical_patriotic_classification_can_differ_from_mythology():
    result = analyze_text(
        "The freedom fighter addressed the nation during the independence movement. "
        "The colonial police surrounded the city, and the patriot was later honored as a martyr."
    )
    assert result["dimensions"]["narrative_type"]["top"]["label"] in {"patriotic", "historical"}
    assert result["dimensions"]["narrative_type"]["top"]["label"] != "mythology"


def test_unknown_world_does_not_force_culture_or_religion():
    result = analyze_text(
        "A traveler entered a remote settlement and spoke with a stranger about the coming storm."
    )
    assert result["dimensions"]["culture"]["top"] is None
    assert result["dimensions"]["religious_context"]["top"] is None


def test_document_profile_reads_structured_source_data(tmp_path):
    db = tmp_path / "source.db"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE pages (document_id INTEGER, page_number INTEGER, text TEXT)")
        con.execute("CREATE TABLE sections (document_id INTEGER, page_number INTEGER, title TEXT)")
        con.execute("CREATE TABLE entities (document_id INTEGER, id INTEGER, canonical_name TEXT)")
        con.execute(
            "INSERT INTO pages VALUES (1, 1, ?)",
            ("Shiva is worshipped in the temple at Varanasi during the ancient story.",),
        )
        con.execute("INSERT INTO sections VALUES (1, 1, 'Ancient Kingdom')")
        con.execute("INSERT INTO entities VALUES (1, 1, 'Shiva')")
        con.commit()

    profile = build_world_profile(db, 1)
    assert profile["source"]["evidence_scope"] == "document-wide"
    assert profile["method"] == "deterministic_source_signal_analysis"
    assert profile["llm_used"] is False
    assert profile["dimensions"]["religious_context"]["top"]["label"] == "hindu"
