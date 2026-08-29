import sqlite3
from pathlib import Path

from core.document_store import DocumentStore
from core.entity_extractor import EntityExtractor
from core.models import DocumentStructure, PageRecord
from core.layout_section_validator import ValidatedSection


def test_entity_extractor_is_source_grounded():
    scenes = [{
        "id": 1,
        "story_id": 1,
        "scene_order": 1,
        "title": "Test",
        "page_start": 1,
        "page_end": 1,
        "text": "Captain Nemo spoke. John walked toward the River Thames. "
                "They entered the dark cave.",
    }]
    entities, mentions, events = EntityExtractor().extract(scenes)
    names = {(e.entity_type, e.canonical_name) for e in entities}
    assert ("character", "Captain Nemo") in names
    assert ("character", "John") in names
    assert any(e.entity_type == "location" for e in entities)
    assert any(e.entity_type == "environment" for e in entities)
    assert len(mentions) >= 3
    assert events[0].text == scenes[0]["text"]


def test_document_store_entity_layer(tmp_path):
    db = tmp_path / "entity.db"
    structure = DocumentStructure(
        pdf_path=Path("/tmp/entity-fixture.pdf"),
        total_pages=2,
        sections=[
            ValidatedSection(
                section_number="I",
                title="Test",
                page_number=1,
                confidence=1.0,
                detection_method="primary",
            )
        ],
        pages=[
            PageRecord(
                page_number=1,
                page_type="normal",
                source="pdf_text",
                text="Captain Nemo met John at the River Thames.\n\n"
                     "They entered the dark cave.",
                ocr_used=False,
            ),
            PageRecord(
                page_number=2,
                page_type="normal",
                source="pdf_text",
                text="Mary asked John what happened.",
                ocr_used=False,
            ),
        ],
        document_type="text",
    )

    store = DocumentStore(db)
    document_id = store.save_structure(
        structure,
        chunk_size=1000,
        chunk_overlap=0,
    )

    assert len(store.get_entities(document_id)) > 0
    assert len(store.get_entity_mentions(document_id)) > 0
    assert len(store.get_events(document_id)) > 0

    tables = {
        row["name"]
        for row in store.query(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {"entities", "entity_mentions", "events"} <= tables
