from types import SimpleNamespace

from core.docling_structure_scanner import DoclingStructureScanner
from core.layout_section_validator import ValidatedSection
from core.structure_scanner import StructureScanner
from core.text_fragment import TextFragment


def test_structure_scanner_defaults_to_docling(monkeypatch):
    monkeypatch.delenv("SOCIAL_AUTOMATION_PDF_BACKEND", raising=False)
    scanner = StructureScanner()
    assert scanner.backend == "docling"


def test_structure_scanner_supports_explicit_legacy_backend():
    scanner = StructureScanner(backend="legacy")
    assert scanner.backend == "legacy"


def test_docling_page_count_from_page_map():
    document = SimpleNamespace(pages={1: object(), 2: object(), 3: object()})
    assert DoclingStructureScanner._page_count(document) == 3


def test_docling_page_count_from_provenance_fallback():
    item = SimpleNamespace(prov=[SimpleNamespace(page_no=7)])
    document = SimpleNamespace(
        pages=None,
        iterate_items=lambda: iter([(item, 0)]),
    )
    assert DoclingStructureScanner._page_count(document) == 7


def test_docling_section_header_accepts_roman_numbering():
    candidate = DoclingStructureScanner._docling_heading_candidate(
        11,
        TextFragment("I. The end", x=72, y=100, height=24),
    )
    assert candidate is not None
    assert candidate.text == "I The end"
    assert candidate.fragments[0].text == "I"
    assert candidate.fragments[1].text == "The end"


def test_docling_scanner_rejects_numeric_metadata_title():
    section = ValidatedSection(
        section_number="2250",
        title="$12",
        page_number=442,
        confidence=12.0,
    )
    assert not DoclingStructureScanner._is_plausible_section(section)


def test_docling_scanner_accepts_normal_numbered_title():
    section = ValidatedSection(
        section_number="3",
        title="Captives",
        page_number=21,
        confidence=12.0,
    )
    assert DoclingStructureScanner._is_plausible_section(section)
