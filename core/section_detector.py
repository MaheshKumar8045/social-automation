import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Section:
    book_number: int
    section_number: str
    title: str
    page_number: int


class SectionDetector:
    """
    Detects chapter headings from OCR text.

    Supported pattern:

        CHAPTER XI.
        A MISSING COMPANION.

    The detector:
    - ignores ordinary running headers
    - detects Roman-numeral chapter headings
    - cleans common OCR punctuation errors
    - tracks book/part changes when chapter numbering restarts
    """

    CHAPTER_RE = re.compile(
        r"^\s*CHAPTER\s+([IVXLCDM0-9]+)\.?\s*$",
        re.IGNORECASE,
    )

    def __init__(self):
        self.book_number = 1
        self.last_chapter_value: Optional[int] = None

    @staticmethod
    def clean_title(title: str) -> str:
        """Clean common OCR/encoding artifacts from chapter titles."""

        replacements = {
            "â€”": "—",
            "â€“": "–",
            "â€˜": "‘",
            "â€™": "’",
            "â€œ": "“",
            "â€\x9d": "”",
            "â€¦": "…",
        }

        for bad, good in replacements.items():
            title = title.replace(bad, good)

        title = re.sub(r"\s+", " ", title)
        return title.strip()

    @staticmethod
    def roman_to_int(value: str) -> Optional[int]:
        """Convert a Roman numeral to an integer."""

        value = value.upper()

        roman = {
            "I": 1,
            "V": 5,
            "X": 10,
            "L": 50,
            "C": 100,
            "D": 500,
            "M": 1000,
        }

        if not value or any(char not in roman for char in value):
            return None

        total = 0
        previous = 0

        for char in reversed(value):
            current = roman[char]

            if current < previous:
                total -= current
            else:
                total += current

            previous = current

        return total

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
            chapter_value = self.roman_to_int(chapter_number)

            if chapter_value is None:
                continue

            # A restart from a later chapter back to I normally
            # indicates that a new book/part has started.
            if (
                self.last_chapter_value is not None
                and chapter_value == 1
                and self.last_chapter_value > 1
            ):
                self.book_number += 1

            self.last_chapter_value = chapter_value

            title = ""

            # The line immediately following "CHAPTER XI."
            # is normally the chapter title.
            if index + 1 < len(lines):
                title = self.clean_title(lines[index + 1])

            return Section(
                book_number=self.book_number,
                section_number=chapter_number,
                title=title,
                page_number=page_number,
            )

        return None