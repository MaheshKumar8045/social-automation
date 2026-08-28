from dataclasses import dataclass
from typing import Any

from core.pdf_analyzer import PageAnalysis
from core.pdf_reader import PDFReader
from core.ocr_engine import OCREngine
from core.text_fragment import TextFragment


@dataclass
class ProcessedPage:
    """Common page representation for downstream processing."""

    page_number: int
    text: str
    lines: list[str]
    source: str
    scores: list[float] | None = None
    boxes: Any = None
    fragments: list[TextFragment] | None = None


class PageProcessor:
    """
    Process PDF pages using either the existing PDF text layer
    or OCR when the page has no extractable text.

    OCR is initialized lazily only when a scanned page requires it.
    """

    def __init__(
        self,
        reader: PDFReader,
        ocr: OCREngine | None = None,
    ):
        self.reader = reader
        self.ocr = ocr

    def process(
        self,
        page: PageAnalysis,
    ) -> ProcessedPage:

        if page.has_text:
            text = self.reader.get_page_text(
                page.page_number - 1
            )

            fragments = self.reader.get_page_fragments(
                page.page_number - 1
            )

            return ProcessedPage(
                page_number=page.page_number,
                text=text,
                lines=text.splitlines(),
                source="pdf_text",
                fragments=fragments,
            )

        if self.ocr is None:
            self.ocr = OCREngine()

        image = self.reader.get_page_image(
            page.page_number - 1
        )

        result = self.ocr.process(
            image,
            page.page_number,
        )

        return ProcessedPage(
            page_number=page.page_number,
            text=result.text,
            lines=result.lines,
            source="ocr",
            scores=result.scores,
            boxes=result.boxes,
            fragments=self._ocr_fragments(result),
        )

    @staticmethod
    def _ocr_fragments(result) -> list[TextFragment]:
        """Convert OCR output into the common fragment representation."""

        fragments = []

        if result.boxes is None:
            return fragments

        for index, text in enumerate(result.lines):
            if not text.strip():
                continue

            confidence = None

            if index < len(result.scores):
                confidence = result.scores[index]

            box = result.boxes[index]

            x = None
            y = None
            width = None
            height = None

            try:
                x1, y1, x2, y2 = [
                    float(value)
                    for value in box
                ]

                x = x1
                y = y1
                width = x2 - x1
                height = y2 - y1

            except (TypeError, ValueError):
                pass

            fragments.append(
                TextFragment(
                    text=text.strip(),
                    x=x,
                    y=y,
                    confidence=confidence,
                    width=width,
                    height=height,
                )
            )

        return fragments