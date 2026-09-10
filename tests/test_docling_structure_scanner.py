from types import SimpleNamespace

from core.docling_structure_scanner import DoclingStructureScanner
from core.layout_section_validator import ValidatedSection
from core.structure_scanner import StructureScanner


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
    item = SimpleNamespace(
        prov=[SimpleNamespace(page_no=7)],
    )
    document = SimpleNamespace(
        pages=None,
        iterate_items=lambda: iter([(item, 0)]),
    )
    assert DoclingStructureScanner._page_count(document) == 7


def test_docling_scanner_rejects_numeric_metadata_title():
    # Back-cover material such as `2250 $12` must not become a chapter.
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
