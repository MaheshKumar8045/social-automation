from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.layout_heading_detector import LayoutHeadingCandidate, LayoutHeadingDetector
from core.layout_section_validator import LayoutSectionValidator, ValidatedSection
from core.models import DocumentStructure, PageRecord
from core.section_reconciler import SectionReconciler
from core.section_recovery import RecoveryCandidate, SectionRecovery
from core.page_structure_classifier import PageStructureClassifier
from core.text_fragment import TextFragment


class DoclingStructureScanner:
    """Build the project's structural input from Docling's document model."""

    NUMBERED_HEADING_RE = re.compile(
        r"^\s*(?P<number>[IVXLCDM]+|\d{1,4})[.)\-:]?\s+(?P<title>.+?)\s*$",
        re.IGNORECASE,
    )

    def __init__(self):
        self.heading_detector = LayoutHeadingDetector()
        self.page_classifier = PageStructureClassifier()
        self.validator = LayoutSectionValidator()
        self.reconciler = SectionReconciler()
        self.recovery = SectionRecovery(
            validator=self.validator,
            classifier=self.page_classifier,
        )

    def scan(self, pdf_path: str | Path, max_pages: int | None = None) -> DocumentStructure:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise RuntimeError(
                "Docling is required for the default document scanner. "
                "Install dependencies with: python -m pip install -r requirements.txt"
            ) from exc

        print("=" * 60)
        print("DOCLING DOCUMENT SCAN")
        print("=" * 60)
        print(f"PDF: {pdf_path}")
        print("Converting PDF with Docling...")

        result = DocumentConverter().convert(pdf_path)
        document = result.document
        available_pages = self._page_count(document)
        total_pages = min(available_pages, max_pages) if max_pages is not None else available_pages

        page_fragments: dict[int, list[TextFragment]] = {page: [] for page in range(1, total_pages + 1)}
        page_text: dict[int, list[str]] = {page: [] for page in range(1, total_pages + 1)}
        page_heading_candidates: dict[int, list[LayoutHeadingCandidate]] = {
            page: [] for page in range(1, total_pages + 1)
        }

        for item, _level in document.iterate_items():
            text = str(getattr(item, "text", "") or "").strip()
            if not text:
                continue
            label = str(getattr(item, "label", "") or "").lower()
            if label in {"page_header", "page_footer"}:
                continue

            prov = getattr(item, "prov", None) or []
            if not prov:
                continue
            provenance = prov[0]
            page_number = int(getattr(provenance, "page_no", 0) or 0)
            if page_number < 1 or page_number > total_pages:
                continue

            bbox = getattr(provenance, "bbox", None)
            l = self._number(getattr(bbox, "l", None))
            t = self._number(getattr(bbox, "t", None))
            r = self._number(getattr(bbox, "r", None))
            b = self._number(getattr(bbox, "b", None))
            width = (r - l) if l is not None and r is not None else None
            height = (b - t) if b is not None and t is not None else None

            fragment = TextFragment(
                text=text,
                x=l,
                y=t,
                font_size=height,
                width=width,
                height=height,
                confidence=1.0,
            )
            page_fragments[page_number].append(fragment)
            page_text[page_number].append(text)

            if label == "section_header":
                candidate = self._docling_heading_candidate(page_number, fragment)
                if candidate is not None:
                    page_heading_candidates[page_number].append(candidate)

        pages: list[PageRecord] = []
        raw_sections: list[ValidatedSection] = []
        recovery_candidates: list[RecoveryCandidate] = []

        for page_number in range(1, total_pages + 1):
            fragments = page_fragments[page_number]
            text = "\n".join(page_text[page_number]).strip()
            docling_candidates = self._deduplicate_candidates(page_heading_candidates[page_number])

            # A single Docling section_header is stronger structural evidence
            # than generic layout candidates generated from the same page.
            # Without this precedence rule, a legitimate chapter opener can
            # be misclassified as CONTENTS simply because the generic detector
            # independently recognizes the same numbered text or nearby prose.
            if len(docling_candidates) == 1:
                candidates = docling_candidates
            else:
                candidates = self.heading_detector.find_candidates(page_number, fragments) if fragments else []
                candidates.extend(docling_candidates)
                candidates = self._deduplicate_candidates(candidates)

            if candidates:
                structure = self.page_classifier.classify(page_number, candidates)
                validated = [
                    section
                    for section in self.validator.validate(structure.candidates)
                    if self._is_plausible_section(section)
                ]
                page_type = structure.page_type
            else:
                structure = None
                validated = []
                page_type = PageStructureClassifier.NORMAL

            pages.append(PageRecord(
                page_number=page_number,
                page_type=page_type,
                source="docling",
                text=text,
                ocr_used=False,
                raw_text=text,
                quality_score=1.0 if text else 0.0,
                normalization_method="docling_layout",
            ))

            if structure is not None and structure.page_type == PageStructureClassifier.SECTION_START and validated:
                raw_sections.extend(validated)
                continue

            if candidates:
                recovery_candidate = self.recovery.collect_candidate(page_number, candidates, page_type)
                if recovery_candidate is not None:
                    recovery_candidates.append(recovery_candidate)

        print(f"Docling pages available: {available_pages}")
        print(f"Pages represented in project structure: {total_pages}")
        print(f"Raw validated candidates: {len(raw_sections)}")

        primary_sections = self.reconciler.reconcile(raw_sections).sections
        recovered = [
            section for section in self.recovery.recover(recovery_candidates, primary_sections)
            if self._is_plausible_section(section)
        ]
        for section in recovered:
            section.detection_method = "recovery"

        final_sections = (
            self.reconciler.reconcile(primary_sections + recovered).sections
            if recovered else primary_sections
        )
        final_sections = [section for section in final_sections if self._is_plausible_section(section)]

        print(f"Primary reconciled sections: {len(primary_sections)}")
        print(f"Recovered sections: {len(recovered)}")
        print(f"Final reconciled sections: {len(final_sections)}")
        self._print_diagnostics(final_sections, recovered)

        return DocumentStructure(
            pdf_path=pdf_path,
            total_pages=available_pages,
            sections=final_sections,
            pages=pages,
            document_type="pdf_docling",
        )

    @classmethod
    def _docling_heading_candidate(
        cls,
        page_number: int,
        fragment: TextFragment,
    ) -> LayoutHeadingCandidate | None:
        match = cls.NUMBERED_HEADING_RE.match(fragment.text)
        if not match:
            return None

        number = match.group("number").upper()
        title = match.group("title").strip()
        if not cls._is_plausible_heading_title(title):
            return None

        number_fragment = TextFragment(
            text=number,
            x=fragment.x,
            y=fragment.y,
            font_size=fragment.font_size,
            confidence=fragment.confidence,
            width=fragment.width,
            height=fragment.height,
        )
        title_fragment = TextFragment(
            text=title,
            x=fragment.x,
            y=fragment.y,
            font_size=fragment.font_size,
            confidence=fragment.confidence,
            width=fragment.width,
            height=fragment.height,
        )
        return LayoutHeadingCandidate(
            page_number=page_number,
            text=f"{number} {title}",
            fragments=[number_fragment, title_fragment],
            score=10.0,
            reason="docling-section-header",
        )

    @staticmethod
    def _deduplicate_candidates(candidates: list[LayoutHeadingCandidate]) -> list[LayoutHeadingCandidate]:
        result: list[LayoutHeadingCandidate] = []
        seen: set[tuple[int, str]] = set()
        for candidate in sorted(candidates, key=lambda item: (-item.score, item.page_number, item.text)):
            key = (candidate.page_number, candidate.text.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)
        return result

    @staticmethod
    def _is_plausible_heading_title(title: str) -> bool:
        normalized = re.sub(r"\s+", " ", title.strip())
        if not normalized or not re.search(r"[A-Za-z]", normalized):
            return False
        if len(normalized) > 140:
            return False
        upper = normalized.upper()
        if any(token in upper for token in {"ISBN", "WWW.", "HTTP://", "HTTPS://"}):
            return False
        return True

    @classmethod
    def _is_plausible_section(cls, section: ValidatedSection) -> bool:
        title = re.sub(r"\s+", " ", section.title.strip())
        if not cls._is_plausible_heading_title(title):
            return False
        if re.fullmatch(r"[\$€£₹]?\s*\d+(?:[.,]\d+)?", title):
            return False
        return True

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _page_count(document: Any) -> int:
        pages = getattr(document, "pages", None)
        if isinstance(pages, dict):
            return len(pages)
        if pages is not None:
            try:
                return len(pages)
            except TypeError:
                pass
        max_page = 0
        for item, _level in document.iterate_items():
            for prov in getattr(item, "prov", None) or []:
                max_page = max(max_page, int(getattr(prov, "page_no", 0) or 0))
        return max_page

    @staticmethod
    def _print_diagnostics(sections: list[ValidatedSection], recovered: list[ValidatedSection]) -> None:
        print()
        print("=" * 60)
        print("DOCLING DIAGNOSTICS")
        print("=" * 60)
        print()
        print(f"{'PAGE':>6}  {'NUMBER':<10}  {'CONF':>6}  METHOD       TITLE")
        print("-" * 100)
        recovered_ids = {(s.page_number, s.section_number, s.title) for s in recovered}
        for section in sections:
            key = (section.page_number, section.section_number, section.title)
            method = "recovery" if key in recovered_ids else section.detection_method
            print(f"{section.page_number:>6}  {(section.section_number or '?'):<10}  {section.confidence:>6.1f}  {method:<11} {section.title}")
        print()
        print("=" * 60)
