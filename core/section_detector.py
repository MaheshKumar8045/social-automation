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
    Detects chapter headings from OCR text or PDF text.

    Supports formats such as:

        CHAPTER XI.
        A MISSING COMPANION.

    and PDF text extraction such as:

        CHAPTER
        XI.
        A
        MISSING
        COMPANION.
    """

    CHAPTER_RE = re.compile(
        r"^\s*CHAPTER(?:\s+([IVXLCDM0-9]+))?\.?\s*$",
        re.IGNORECASE,
    )

    NUMBER_RE = re.compile(
        r"^\s*([IVXLCDM0-9]+)\.?\s*$",
        re.IGNORECASE,
    )

    def detect(
        self,
        page_number: int,
        lines: list[str],
    ) -> Optional[Section]:

        for index, line in enumerate(lines):
            cleaned = line.strip()

            chapter_match = self.CHAPTER_RE.match(cleaned)

            if not chapter_match:
                continue

            chapter_number = chapter_match.group(1)

            # Format:
            # CHAPTER
            # XI.
            if chapter_number is None:
                if index + 1 >= len(lines):
                    continue

                number_match = self.NUMBER_RE.match(
                    lines[index + 1].strip()
                )

                if not number_match:
                    continue

                chapter_number = number_match.group(1).upper()
                title_start = index + 2

            else:
                chapter_number = chapter_number.upper()
                title_start = index + 1

            title_parts = []

            for title_line in lines[title_start:]:
                cleaned_title_line = title_line.strip()

                if not cleaned_title_line:
                    continue

                # Stop once the actual chapter text begins.
                if cleaned_title_line.upper().startswith("IN "):
                    break

                title_parts.append(cleaned_title_line)

                # Most chapter titles are short. Stop after
                # collecting a reasonable title.
                if cleaned_title_line.endswith((".", "!", "?")):
                    break

            title = " ".join(title_parts).strip()

            if not title:
                continue

            return Section(
                section_number=chapter_number,
                title=title,
                page_number=page_number,
            )

        return None