import sqlite3

from core.generation_context import GenerationContext


def test_characters_fallback_normalizes_canonical_character_id():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row

    con.executescript(
        """
        CREATE TABLE scenes (
            id INTEGER,
            document_id INTEGER,
            text TEXT
        );
        CREATE TABLE events (
            document_id INTEGER,
            scene_id INTEGER,
            text TEXT
        );
        CREATE TABLE entities (
            id INTEGER,
            document_id INTEGER,
            canonical_name TEXT,
            entity_type TEXT
        );
        CREATE TABLE entity_mentions (
            document_id INTEGER,
            scene_id INTEGER,
            entity_id INTEGER,
            page_start INTEGER,
            page_end INTEGER,
            context TEXT,
            confidence REAL
        );
        CREATE TABLE canonical_characters (
            id INTEGER,
            document_id INTEGER,
            canonical_name TEXT,
            status TEXT,
            confidence REAL
        );
        CREATE TABLE canonical_character_aliases (
            id INTEGER,
            entity_id INTEGER,
            canonical_character_id INTEGER,
            alias TEXT,
            relationship TEXT,
            confidence REAL
        );
        CREATE TABLE canonical_visual_profiles (
            id INTEGER,
            document_id INTEGER,
            canonical_character_id INTEGER
        );
        CREATE TABLE canonical_visual_facts (
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
        """
    )

    con.execute(
        "INSERT INTO scenes(id, document_id, text) VALUES(1, 1, ?)",
        ("Ravana Tomorrow is my funeral.",),
    )
    con.execute(
        "INSERT INTO canonical_characters(id, document_id, canonical_name, status, confidence) "
        "VALUES(30, 1, 'King Ravana', 'confirmed', 1.0)"
    )
    con.execute(
        "INSERT INTO canonical_character_aliases("
        "id, entity_id, canonical_character_id, alias, relationship, confidence"
        ") VALUES(1, NULL, 30, 'Ravana', 'approved_alias', 1.0)"
    )
    con.commit()

    characters = GenerationContext(":memory:")._characters(con, 1, 1)

    assert [c["canonical_character_id"] for c in characters] == [30]
    assert characters[0]["canonical_name"] == "King Ravana"
    assert characters[0]["source_presence"]["physical_presence"] is False

    con.close()


def test_characters_fallback_resolves_bare_source_name_from_titled_canonical_name():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE scenes (id INTEGER, document_id INTEGER, text TEXT);
        CREATE TABLE events (document_id INTEGER, scene_id INTEGER, text TEXT);
        CREATE TABLE entities (id INTEGER, document_id INTEGER, canonical_name TEXT, entity_type TEXT);
        CREATE TABLE entity_mentions (
            document_id INTEGER, scene_id INTEGER, entity_id INTEGER,
            page_start INTEGER, page_end INTEGER, context TEXT, confidence REAL
        );
        CREATE TABLE canonical_characters (
            id INTEGER, document_id INTEGER, canonical_name TEXT, status TEXT, confidence REAL
        );
        CREATE TABLE canonical_character_aliases (
            id INTEGER, entity_id INTEGER, canonical_character_id INTEGER,
            alias TEXT, relationship TEXT, confidence REAL
        );
        CREATE TABLE canonical_visual_profiles (
            id INTEGER, document_id INTEGER, canonical_character_id INTEGER
        );
        CREATE TABLE canonical_visual_facts (
            canonical_visual_profile_id INTEGER, category TEXT, attribute TEXT,
            value TEXT, status TEXT, confidence REAL, scene_id INTEGER,
            page_start INTEGER, page_end INTEGER, evidence TEXT
        );
        """
    )
    con.execute(
        "INSERT INTO scenes(id, document_id, text) VALUES(1, 1, ?)",
        ("1 The end Ravana Tomorrow is my funeral.",),
    )
    con.execute(
        "INSERT INTO canonical_characters(id, document_id, canonical_name, status, confidence) "
        "VALUES(30, 1, 'King Ravana', 'confirmed', 1.0)"
    )
    con.commit()

    characters = GenerationContext(":memory:")._characters(con, 1, 1)

    assert [c["canonical_character_id"] for c in characters] == [30]
    assert characters[0]["canonical_name"] == "King Ravana"
    assert characters[0]["source_presence"]["physical_presence"] is False
    con.close()
