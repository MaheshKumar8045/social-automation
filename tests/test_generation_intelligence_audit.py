import json
import sqlite3

from core.character_candidate_gate import gate
from core.character_canonicalizer import build as build_canonical_characters
from core.prompt_quality_audit import audit_package


def test_candidate_gate_rejects_interrogative_as_character():
    decision, score, reasons = gate("Who", "character", [])
    assert decision == "non_character"
    assert score == 1.0
    assert "common_word_or_demographic_term" in reasons


def test_candidate_gate_rejects_name_also_classified_as_location():
    decision, score, reasons = gate(
        "Mithila",
        "character",
        [],
        conflicting_entity_types={"location"},
    )
    assert decision == "non_character"
    assert score == 1.0
    assert reasons == ["ambiguous_name_without_person_evidence"]


def test_canonicalizer_does_not_promote_non_character_singleton(tmp_path):
    db = tmp_path / "source.db"
    with sqlite3.connect(db) as con:
        con.executescript(
            """
            CREATE TABLE documents (id INTEGER PRIMARY KEY);
            CREATE TABLE character_identity_groups (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                canonical_entity_id INTEGER,
                canonical_name TEXT,
                confidence REAL
            );
            CREATE TABLE mention_identity_resolution (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                group_id INTEGER,
                relationship TEXT,
                confidence REAL
            );
            CREATE TABLE character_identity_members (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                group_id INTEGER,
                entity_id INTEGER,
                variant_name TEXT,
                confidence REAL
            );
            CREATE TABLE character_candidate_gate (
                document_id INTEGER,
                entity_id INTEGER,
                decision TEXT,
                score REAL
            );
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY
            );
            """
        )
        con.execute("INSERT INTO documents VALUES (1)")
        con.execute(
            "INSERT INTO character_identity_groups VALUES (1,1,10,'Who',0.5)"
        )
        con.execute(
            "INSERT INTO character_identity_members VALUES (1,1,1,10,'Who',1.0)"
        )
        con.execute(
            "INSERT INTO character_candidate_gate VALUES (1,10,'non_character',1.0)"
        )
        con.commit()

    result = build_canonical_characters(db, 1)
    assert result["singleton"] == 0
    assert result["excluded"] == 1


def test_audit_does_not_flag_character_free_scene_as_unusual(tmp_path):
    package = {
        "qa_passed": True,
        "qa_failures": [],
        "scenes": [
            {
                "scene_id": 1,
                "scene_order": 1,
                "title": "A quiet chamber",
                "page_start": 1,
                "page_end": 1,
                "qa_status": "pass",
                "plan": {
                    "world_profile": {
                        "dimensions": {
                            "narrative_type": {"top": {"label": "mythology", "confidence": 0.9}},
                            "culture": {"top": {"label": "indic", "confidence": 0.9}},
                            "religious_context": {"top": {"label": "hindu", "confidence": 0.9}},
                        }
                    },
                    "image_prompt": (
                        "Source-grounded mythology media depiction. DETECTED STORY WORLD. "
                        "PRIMARY SOURCE VISUAL MOMENT: a quiet chamber."
                    ),
                    "characters": [],
                    "visual_inference": {"enabled": True, "genre": "mythology"},
                    "media_prompt_package": {"visual_inference": {"enabled": True, "genre": "mythology"}},
                },
            }
        ],
    }
    path = tmp_path / "all_prompts.json"
    path.write_text(json.dumps(package), encoding="utf-8")
    result = audit_package(path, sample_count=1)
    assert result["audit_failed_scenes"] == 0
    assert "visual_inference_structure_unusual" not in result["observations"]


def test_audit_flags_obvious_non_character_name(tmp_path):
    package = {
        "qa_passed": True,
        "qa_failures": [],
        "scenes": [
            {
                "scene_id": 1,
                "scene_order": 1,
                "title": "Scene",
                "page_start": 1,
                "page_end": 1,
                "qa_status": "pass",
                "plan": {
                    "world_profile": {
                        "dimensions": {
                            "narrative_type": {"top": {"label": "mythology"}},
                            "culture": {"top": {"label": "indic"}},
                            "religious_context": {"top": {"label": "hindu"}},
                        }
                    },
                    "image_prompt": "Source-grounded mythology. DETECTED STORY WORLD. PRIMARY SOURCE VISUAL MOMENT: action.",
                    "characters": [
                        {
                            "canonical_name": "Who",
                            "visual_profile": {
                                "identity_anchor": "vib-test",
                                "source_facts": [],
                                "inferred_facts": [],
                            },
                        }
                    ],
                    "visual_inference": {"enabled": True, "genre": "mythology"},
                    "media_prompt_package": {"visual_inference": {"enabled": True}},
                },
            }
        ],
    }
    path = tmp_path / "all_prompts.json"
    path.write_text(json.dumps(package), encoding="utf-8")
    result = audit_package(path, sample_count=1)
    assert result["audit_failed_scenes"] == 1
    assert "obvious_non_character_name:Who" in result["audit_failure_details"][0]["issues"]
