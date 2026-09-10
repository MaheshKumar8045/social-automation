from __future__ import annotations

import os
from pathlib import Path

from core.models import DocumentStructure, PageRecord
from core.pdf_analyzer import PDFAnalyzer
from core.pdf_reader import PDFReader
from core.page_processor import PageProcessor
from core.layout_heading_detector import LayoutHeadingDetector
from core.layout_section_validator import LayoutSectionValidator, ValidatedSection
from core.page_structure_classifier import PageStructureClassifier
from core.section_reconciler import SectionReconciler
from core.section_recovery import SectionRecovery, RecoveryCandidate


class StructureScanner:
    """Document structure scanner with Docling as the default backend.

    Docling owns low-level PDF parsing, reading order, OCR/layout
    understanding, and provenance. The project's existing semantic heading,
    validation, reconciliation, and recovery layers remain downstream.

    Set SOCIAL_AUTOMATION_PDF_BACKEND=legacy to run the previous pypdf/
    PaddleOCR implementation for comparison or emergency compatibility.
    """

    def __init__(self, ocr=None, backend: str | None = None):
        self.backend = (
            backend or os.getenv("SOCIAL_AUTOMATION_PDF_BACKEND", "docling")
        ).strip().lower()
        if self.backend not in {"docling", "legacy"}:
            raise ValueError(
                "SOCIAL_AUTOMATION_PDF_BACKEND must be 'docling' or 'legacy'."
            )

        self.analyzer = PDFAnalyzer()
        self.heading_detector = LayoutHeadingDetector()
        self.page_classifier = PageStructureClassifier()
        self.validator = LayoutSectionValidator()
        self.reconciler = SectionReconciler()
        self.recovery = SectionRecovery(
            validator=self.validator,
            classifier=self.page_classifier,
        )
        self.ocr = ocr

    def scan(
        self,
        pdf_path: str | Path,
        max_pages: int | None = None,
    ) -> DocumentStructure:
        if self.backend == "docling":
            from core.docling_structure_scanner import DoclingStructureScanner

            return DoclingStructureScanner().scan(pdf_path, max_pages=max_pages)

        return self._scan_legacy(pdf_path, max_pages=max_pages)

    def _scan_legacy(
        self,
        pdf_path: str | Path,
        max_pages: int | None = None,
    ) -> DocumentStructure:
        """Original scanner retained as an explicit compatibility backend."""
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        analysis = self.analyzer.analyze(pdf_path)
        reader = PDFReader(pdf_path)
        processor = PageProcessor(reader, ocr=self.ocr)

        page_results = analysis.page_results
        if max_pages is not None:
            page_results = page_results[:max_pages]

        total_to_scan = len(page_results)
        raw_sections: list[ValidatedSection] = []
        recovery_candidates: list[RecoveryCandidate] = []
        pages: list[PageRecord] = []

        print("=" * 60)
        print("LEGACY DOCUMENT STRUCTURE SCAN")
        print("=" * 60)
        print(f"PDF: {pdf_path}")
        print(f"PDF pages: {analysis.total_pages}")
        print(f"Pages being scanned: {total_to_scan}")
        print(f"Document type: {analysis.document_type}")
        print()

        for scan_index, page_analysis in enumerate(page_results, start=1):
            if scan_index == 1 or scan_index % 25 == 0 or scan_index == total_to_scan:
                print(
                    f"Progress: {scan_index}/{total_to_scan} "
                    f"(PDF page {page_analysis.page_number})"
                )

            processed = processor.process(page_analysis)

            if not processed.fragments:
                pages.append(PageRecord(
                    page_number=processed.page_number,
                    page_type=PageStructureClassifier.NORMAL,
                    source=processed.source,
                    text=processed.text,
                    ocr_used=processed.source == "ocr",
                    raw_text=processed.raw_text,
                    quality_score=processed.quality_score,
                    normalization_method=processed.normalization_method,
                ))
                continue

            candidates = self.heading_detector.find_candidates(
                processed.page_number,
                processed.fragments,
            )

            if not candidates:
                pages.append(PageRecord(
                    page_number=processed.page_number,
                    page_type=PageStructureClassifier.NORMAL,
                    source=processed.source,
                    text=processed.text,
                    ocr_used=processed.source == "ocr",
                    raw_text=processed.raw_text,
                    quality_score=processed.quality_score,
                    normalization_method=processed.normalization_method,
                ))
                continue

            structure = self.page_classifier.classify(
                processed.page_number,
                candidates,
            )
            validated = self.validator.validate(structure.candidates)

            pages.append(PageRecord(
                page_number=processed.page_number,
                page_type=structure.page_type,
                source=processed.source,
                text=processed.text,
                ocr_used=processed.source == "ocr",
                raw_text=processed.raw_text,
                quality_score=processed.quality_score,
                normalization_method=processed.normalization_method,
            ))

            if structure.page_type == PageStructureClassifier.SECTION_START and validated:
                raw_sections.extend(validated)
                continue

            recovery_candidate = self.recovery.collect_candidate(
                processed.page_number,
                candidates,
                structure.page_type,
            )
            if recovery_candidate is not None:
                recovery_candidates.append(recovery_candidate)

        print()
        print(f"Raw validated candidates: {len(raw_sections)}")
        primary_sections = self.reconciler.reconcile(raw_sections).sections
        print(f"Primary reconciled sections: {len(primary_sections)}")

        recovered = self.recovery.recover(recovery_candidates, primary_sections)
        for section in recovered:
            section.detection_method = "recovery"

        final_sections = (
            self.reconciler.reconcile(primary_sections + recovered).sections
            if recovered else primary_sections
        )

        print(f"Recovered sections: {len(recovered)}")
        print(f"Final reconciled sections: {len(final_sections)}")
        self._print_diagnostics(final_sections, recovered)

        return DocumentStructure(
            pdf_path=pdf_path,
            total_pages=analysis.total_pages,
            sections=final_sections,
            pages=pages,
            document_type=analysis.document_type,
        )

    @staticmethod
    def _print_diagnostics(
        sections: list[ValidatedSection],
        recovered: list[ValidatedSection],
    ) -> None:
        print()
        print("=" * 60)
        print("DIAGNOSTICS")
        print("=" * 60)
        print()
        print(f"{'PAGE':>6}  {'NUMBER':<10}  {'CONF':>6}  METHOD       TITLE")
        print("-" * 100)

        recovered_ids = {(s.page_number, s.section_number, s.title) for s in recovered}
        for section in sections:
            key = (section.page_number, section.section_number, section.title)
            method = "recovery" if key in recovered_ids else section.detection_method
            print(
                f"{section.page_number:>6}  "
                f"{(section.section_number or '?'):<10}  "
                f"{section.confidence:>6.1f}  "
                f"{method:<11} {section.title}"
            )
        print()
        print("=" * 60)
