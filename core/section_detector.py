import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Section:
    section_number: str
    title: str
    page_number: int


class SectionDetector:
    """
    Detects chapter headings from OCR text.

    Current supported pattern:

        CHAPTER XI.
        A MISSING COMPANION.

    Running headers and page numbers are intentionally ignored.
    """

    CHAPTER_RE = re.compile(
        r"^\s*CHAPTER\s+([IVXLCDM0-9]+)\.?\s*$",
        re.IGNORECASE,
    )

    def detect(
        self,
        page_number: int,
        lines: list[str],
    ) -> Optional[Section]:
        """
        Inspect OCR lines from one page.

        Returns a Section when a chapter heading is found.
        Otherwise returns None.
        """

        for index, line in enumerate(lines):
            cleaned = line.strip()

            match = self.CHAPTER_RE.match(cleaned)

            if not match:
                continue

            chapter_number = match.group(1).upper()

            title = ""

            # The line immediately following "CHAPTER XI."
            # is normally the chapter title.
            if index + 1 < len(lines):
                title = lines[index + 1].strip()

            return Section(
                section_number=chapter_number,
                title=title,
                page_number=page_number,
            )

        return None