from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PageRecord:
    """Persisted representation of a processed PDF page."""

    page_number: int
    page_type: str
    source: str
    text: str
    ocr_used: bool


@dataclass(frozen=True)
class DocumentStructure:
    """Complete structural result for one PDF scan.

    ``total_pages`` is the actual PDF page count. ``pages`` contains
    only pages processed by the current scan, which may be a bounded
    regression scan.
    """

    pdf_path: Path
    total_pages: int
    sections: list[Any]
    pages: list[PageRecord]
    document_type: str = "unknown"

    @property
    def scanned_page_count(self) -> int:
        return len(self.pages)

    @property
    def scanned_page_end(self) -> int:
        if not self.pages:
            return 0
        return max(page.page_number for page in self.pages)
