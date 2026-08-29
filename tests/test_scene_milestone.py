import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.models import DocumentStructure, PageRecord
from core.layout_section_validator import ValidatedSection
from core.document_store import DocumentStore
from core.scene_segmenter import SceneSegmenter


class SceneMilestoneTests(unittest.TestCase):
    def test_segmenter_preserves_source_and_splits(self):
        text = "A" * 1800 + "\n\n" + "B" * 1800 + "\n\n" + "C" * 1800
        story = {"story_order": 1, "title": "I. Test", "page_start": 1, "page_end": 3, "text": text}
        scenes = SceneSegmenter(target_chars=3500, min_chars=900).segment(story)
        self.assertGreaterEqual(len(scenes), 2)
        self.assertEqual("".join(s.text for s in scenes).replace("\n\n", ""), text.replace("\n\n", ""))

    def test_store_persists_stories_and_scenes(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "book.db"
            structure = DocumentStructure(
                Path(d) / "book.pdf",
                3,
                [
                    ValidatedSection("I", "First", 1, 10.0),
                    ValidatedSection("II", "Second", 3, 10.0),
                ],
                [
                    PageRecord(1, "normal", "pdf_text", "First.\n\n" + "A" * 1800, False),
                    PageRecord(2, "normal", "pdf_text", "B" * 1800, False),
                    PageRecord(3, "normal", "pdf_text", "Second.\n\n" + "C" * 1800, False),
                ],
                "text",
            )
            store = DocumentStore(db)
            doc_id = store.save_structure(structure, chunk_size=1000, chunk_overlap=100)
            self.assertEqual(2, len(store.get_stories(doc_id)))
            self.assertGreaterEqual(len(store.get_scenes(doc_id)), 2)
            tables = {r[0] for r in sqlite3.connect(db).execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            self.assertIn("stories", tables)
            self.assertIn("scenes", tables)


if __name__ == "__main__":
    unittest.main()
