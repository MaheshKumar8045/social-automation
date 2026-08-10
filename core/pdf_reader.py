from pathlib import Path
from io import BytesIO
from typing import Iterator

from PIL import Image
from pypdf import PdfReader


class PDFReader:
    """Read scanned PDF pages one at a time."""

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)

        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")

        self.reader = PdfReader(str(self.pdf_path))

    @property
    def page_count(self) -> int:
        """Return the total number of pages."""
        return len(self.reader.pages)

    def get_page_image(self, page_number: int) -> Image.Image:
        """
        Extract one embedded page image.

        page_number is zero-based.
        """
        if page_number < 0 or page_number >= self.page_count:
            raise IndexError(
                f"Page {page_number} is outside the PDF "
                f"(0-{self.page_count - 1})"
            )

        page = self.reader.pages[page_number]

        if not page.images:
            raise ValueError(
                f"Page {page_number + 1} does not contain an embedded image."
            )

        # Use the largest embedded image on the page.
        image_file = max(
            page.images,
            key=lambda image: len(image.data),
        )

        image = Image.open(BytesIO(image_file.data))

        # PaddleOCR works cleanly with RGB images.
        return image.convert("RGB")

    def iter_pages(
        self,
        start_page: int = 0,
        end_page: int | None = None,
    ) -> Iterator[tuple[int, Image.Image]]:
        """
        Yield (page_number, image) one page at a time.

        Page numbers returned here are one-based for human readability.
        """
        if end_page is None:
            end_page = self.page_count

        start_page = max(0, start_page)
        end_page = min(self.page_count, end_page)

        if start_page >= end_page:
            raise ValueError(
                f"Invalid page range: {start_page} to {end_page}"
            )

        for page_index in range(start_page, end_page):
            yield page_index + 1, self.get_page_image(page_index)