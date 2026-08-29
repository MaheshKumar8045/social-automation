import sqlite3

from core.document_store import DocumentStore


def _seed(db):
    DocumentStore(db)
    con = sqlite3.connect(db)
    doc = con.execute(
        """INSERT INTO documents
           (filename,path,page_count,scanned_page_count,document_type)
           VALUES (?,?,?,?,?)""",
        ("book.pdf", "/book.pdf", 2, 2, "text"),
    ).lastrowid
    con.execute(
        """INSERT INTO pages
           (document_id,page_number,page_type,source,text)
           VALUES (?,?,?,?,?)""",
        (doc, 1, "normal", "pdf_text",
         "Axel met Professor Lidenbrock in Iceland."),
    )
    sec = con.execute(
        """INSERT INTO sections
           (document_id,section_order,section_number,title,page_start,page_end,confidence,detection_method)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc, 1, "I", "The Journey", 1, 2, 1.0, "test"),
    ).lastrowid
    story = con.execute(
        """INSERT INTO stories
           (document_id,section_id,story_order,title,page_start,page_end,text,segmentation_method,confidence)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (doc, sec, 1, "The Journey", 1, 2,
         "Axel met Professor Lidenbrock in Iceland.", "test", 1.0),
    ).lastrowid
    scene = con.execute(
        """INSERT INTO scenes
           (document_id,story_id,scene_order,title,page_start,page_end,text,segmentation_method,confidence)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (doc, story, 1, "Meeting", 1, 1,
         "Axel met Professor Lidenbrock in Iceland.", "test", 1.0),
    ).lastrowid
    entity = con.execute(
        """INSERT INTO entities
           (document_id,entity_type,canonical_name,profile_text,confidence,discovery_method)
           VALUES (?,?,?,?,?,?)""",
        (doc, "character", "Professor Lidenbrock",
         "Professor and scientist.", .9, "test"),
    ).lastrowid
    con.execute(
        """INSERT INTO entity_mentions
           (document_id,entity_id,scene_id,story_id,page_start,page_end,mention_text,context,confidence)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (doc, entity, scene, story, 1, 1,
         "Professor Lidenbrock", "Axel met Professor Lidenbrock.", .9),
    )
    con.execute(
        """INSERT INTO events
           (document_id,scene_id,event_order,title,page_start,page_end,text,discovery_method,confidence)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (doc, scene, 1, "Meeting", 1, 1,
         "Axel met Professor Lidenbrock.", "test", .8),
    )
    con.execute(
        """INSERT INTO chunks
           (document_id,section_id,page_number,chunk_index,text,char_count,token_count)
           VALUES (?,?,?,?,?,?,?)""",
        (doc, sec, 1, 0,
         "Axel met Professor Lidenbrock in Iceland.", 42, 6),
    )
    con.commit()
    con.close()
    return doc


def test_rag_build_and_search(tmp_path):
    db = tmp_path / "rag.db"
    doc = _seed(db)
    store = DocumentStore(db)

    count = store.build_rag_index(doc)
    assert count == 7

    results = store.search_rag(doc, "Professor Lidenbrock", limit=5)
    assert results
    assert any(r["source_type"] == "entity" for r in results)
    assert any(r["source_type"] == "scene" for r in results)

    entity_results = store.search_rag(
        doc, "Professor Lidenbrock", limit=5, source_type="entity"
    )
    assert len(entity_results) == 1
    assert entity_results[0]["title"] == "character: Professor Lidenbrock"


def test_rag_rebuild_is_idempotent(tmp_path):
    db = tmp_path / "rag.db"
    doc = _seed(db)
    store = DocumentStore(db)

    assert store.build_rag_index(doc) == 7
    assert store.build_rag_index(doc) == 7
    assert store.query(
        "SELECT COUNT(*) AS n FROM rag_documents WHERE document_id = ?",
        (doc,),
    )[0]["n"] == 7
