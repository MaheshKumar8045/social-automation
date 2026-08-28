from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class PageAnalysis:
    page_number: int
    text_characters: int
    has_text: bool


@dataclass
class PDFAnalysis:
    pdf_path: str
    total_pages: int
    text_pages: int
    scanned_pages: int
    page_results: list[PageAnalysis]

    @property
    def document_type(self) -> str:
        if self.text_pages == self.total_pages:
            return "text"

        if self.scanned_pages == self.total_pages:
            return "scanned"

        return "mixed"


class PDFAnalyzer:
    """
    Determines whether PDF pages contain extractable text.
    """

    def analyze(self, pdf_path: str | Path) -> PDFAnalysis:
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(
                f"PDF not found: {pdf_path}"
            )

        reader = PdfReader(str(pdf_path))

        page_results = []
        text_pages = 0
        scanned_pages = 0

        for page_index, page in enumerate(reader.pages):
            page_number = page_index + 1

            text = page.extract_text() or ""
            text_characters = len(text.strip())

            has_text = text_characters > 0

            if has_text:
                text_pages += 1
            else:
                scanned_pages += 1

            page_results.append(
                PageAnalysis(
                    page_number=page_number,
                    text_characters=text_characters,
                    has_text=has_text,
                )
            )

        return PDFAnalysis(
            pdf_path=str(pdf_path),
            total_pages=len(reader.pages),
            text_pages=text_pages,
            scanned_pages=scanned_pages,
            page_results=page_results,
        )