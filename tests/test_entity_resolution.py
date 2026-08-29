import sqlite3
from core.document_store import SCHEMA
from core.entity_resolver import EntityResolver

def test_conservative_titled_name_resolution():
    con=sqlite3.connect(":memory:")
    con.row_factory=sqlite3.Row
    con.executescript(SCHEMA)
    con.execute("INSERT INTO documents(filename,path,page_count,scanned_page_count,document_type) VALUES ('x','/x',1,1,'text')")
    doc=con.execute("SELECT id FROM documents").fetchone()[0]
    con.execute("INSERT INTO sections(document_id,section_order,title,page_start,page_end,confidence,detection_method) VALUES (?,?,?,?,?,?,?)",(doc,1,"S",1,1,1,"test"))
    section=con.execute("SELECT id FROM sections").fetchone()[0]
    con.execute("INSERT INTO stories(document_id,section_id,story_order,title,page_start,page_end,text,segmentation_method,confidence) VALUES (?,?,?,?,?,?,?,?,?)",(doc,section,1,"S",1,1,"x","test",1))
    story=con.execute("SELECT id FROM stories").fetchone()[0]
    con.execute("INSERT INTO scenes(document_id,story_id,scene_order,title,page_start,page_end,text,segmentation_method,confidence) VALUES (?,?,?,?,?,?,?,?,?)",(doc,story,1,"S",1,1,"x","test",1))
    scene=con.execute("SELECT id FROM scenes").fetchone()[0]
    for name,conf in [("Professor Lidenbrock",.8),("Lidenbrock",.75)]:
        con.execute("INSERT INTO entities(document_id,entity_type,canonical_name,profile_text,confidence,discovery_method) VALUES (?,?,?,?,?,?)",(doc,"character",name,"",conf,"test"))
        eid=con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO entity_mentions(document_id,entity_id,scene_id,story_id,page_start,page_end,mention_text,context,confidence) VALUES (?,?,?,?,?,?,?,?,?)",(doc,eid,scene,story,1,1,name,"evidence "+name,conf))
    EntityResolver().resolve_connection(con,doc)
    assert con.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM entity_mentions").fetchone()[0] == 2
    assert con.execute("SELECT entity_id FROM entity_mentions WHERE mention_text='Lidenbrock'").fetchone()[0] == 1
    assert con.execute("SELECT alias FROM entity_aliases WHERE resolution_method='titled_name_variant'").fetchone()[0] == "Lidenbrock"

def test_locations_are_not_fuzzy_merged():
    con=sqlite3.connect(":memory:"); con.row_factory=sqlite3.Row; con.executescript(SCHEMA)
    con.execute("INSERT INTO documents(filename,path,page_count,scanned_page_count,document_type) VALUES ('x','/x',1,1,'text')")
    doc=1
    for name in ("River Thames","River Tames"):
        con.execute("INSERT INTO entities(document_id,entity_type,canonical_name,profile_text,confidence,discovery_method) VALUES (?,?,?,?,?,?)",(doc,"location",name,"",.6,"test"))
    EntityResolver().resolve_connection(con,doc)
    assert con.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 2
