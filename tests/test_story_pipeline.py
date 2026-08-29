import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.document_store import DocumentStore
from core.models import DocumentStructure, PageRecord
from core.story_segmenter import StorySegmenter


class StoryPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pdf = self.tmp / "book.pdf"
        self.pdf.write_bytes(b"test")

        self.structure = DocumentStructure(
            pdf_path=self.pdf,
            total_pages=4,
            document_type="text",
            sections=[
                SimpleNamespace(
                    page_number=2, section_number="I", title="First",
                    confidence=1.0, detection_method="primary"
                ),
                SimpleNamespace(
                    page_number=4, section_number="II", title="Second",
                    confidence=1.0, detection_method="primary"
                ),
            ],
            pages=[
                PageRecord(1, "normal", "pdf_text", "front", False),
                PageRecord(2, "section_start", "pdf_text", "A paragraph.", False),
                PageRecord(3, "normal", "pdf_text", "More.", False),
                PageRecord(4, "section_start", "pdf_text", "Second story.", False),
            ],
        )

    def test_segmenter_creates_one_story_per_section(self):
        stories = StorySegmenter().segment(self.structure)
        self.assertEqual(len(stories), 2)
        self.assertEqual(stories[0].page_start, 2)
        self.assertEqual(stories[0].page_end, 3)
        self.assertEqual(stories[1].page_start, 4)

    def test_store_and_json_include_stories(self):
        db = self.tmp / "book.db"
        output = self.tmp / "book.json"
        with DocumentStore(db) as store:
            document_id = store.save_structure(self.structure)
            stories = store.get_stories(document_id)
            self.assertEqual(len(stories), 2)
            store.export_json(document_id, output)

        self.assertTrue(output.exists())
        self.assertIn('"stories"', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
