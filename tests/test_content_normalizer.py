import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest
from core.content_normalizer import ContentNormalizer
from core.text_fragment import TextFragment

class TestContentNormalizer(unittest.TestCase):
    def test_native_raw_word_lines_become_readable_text(self):
        raw = "The\nnext\nstep\nwas\nto\nadjust\nthe\nrods."
        result=ContentNormalizer().normalize(raw, [], source="pdf_text")
        self.assertEqual(result.text,"The next step was to adjust the rods.")

    def test_native_word_fragments_become_readable_lines(self):
        fs=[
            TextFragment("The",10,100,font_size=10),
            TextFragment("next",35,100,font_size=10),
            TextFragment("step",65,100,font_size=10),
            TextFragment("was",95,100,font_size=10),
        ]
        result=ContentNormalizer().normalize("",fs,source="pdf_text")
        self.assertEqual(result.text,"The next step was")

    def test_ocr_fragments_preserve_paragraph_break(self):
        fs=[
            TextFragment("First",10,10,width=20,height=10),
            TextFragment("paragraph.",35,10,width=40,height=10),
            TextFragment("Second",10,30,width=30,height=10),
            TextFragment("paragraph.",45,30,width=40,height=10),
        ]
        result=ContentNormalizer().normalize("",fs,source="ocr")
        self.assertEqual(result.text,"First paragraph.\n\nSecond paragraph.")

    def test_hyphenated_word_is_rejoined(self):
        fs=[
            TextFragment("cata-",10,100,font_size=10),
            TextFragment("logues",45,100,font_size=10),
        ]
        result=ContentNormalizer().normalize("",fs,source="pdf_text")
        self.assertEqual(result.text,"catalogues")

if __name__=="__main__":
    unittest.main()
