from dataclasses import dataclass
import re

from core.heading_detector import HeadingCandidate


@dataclass
class ValidatedSection:
    """A validated document section."""

    section_number: str | None
    title: str
    page_number: int
    confidence: float


class SectionValidator:
    """
    Validates structural heading candidates.

    This is intentionally document-agnostic. It does not know
    anything about a particular book, page number, title, or
    expected number of chapters.
    """

    STRUCTURAL_KEYWORDS = {
        "chapter",
        "section",
        "part",
        "appendix",
        "prologue",
        "epilogue",
    }

    def validate(
        self,
        candidates: list[HeadingCandidate],
        lines: list[str],
    ) -> list[ValidatedSection]:

        if not candidates:
            return []

        keyword_candidates = [
            candidate
            for candidate in candidates
            if "heading-keyword" in candidate.reason
        ]

        # Several explicit chapter/section markers on the same page
        # are commonly found in contents pages.
        if len(keyword_candidates) > 1:
            return []

        results = []

        for candidate in keyword_candidates:
            section = self._build_section(candidate, lines)

            if section is not None:
                results.append(section)

        return results

    def _build_section(
        self,
        candidate: HeadingCandidate,
        lines: list[str],
    ) -> ValidatedSection | None:

        index = candidate.line_index

        if index >= len(lines):
            return None

        number = None

        # Handle:
        #
        # CHAPTER
        # XI,
        #
        if index + 1 < len(lines):
            possible_number = lines[index + 1].strip()

            if self._looks_like_number(possible_number):
                number = possible_number.rstrip(".,:;").upper()
                title_start = index + 2
            else:
                title_start = index + 1
        else:
            title_start = index + 1

        title_parts = []

        for line in lines[title_start:]:
            text = line.strip()

            if not text:
                if title_parts:
                    break
                continue

            # Another structural marker means the previous title ended.
            if self._is_structural_heading(text):
                break

            # If this is a normal multi-word prose line, the body
            # has probably started.
            if (
                len(title_parts) >= 1
                and self._looks_like_prose_line(text)
            ):
                break

            title_parts.append(text)

            # A title ending in punctuation is a strong boundary.
            if text.endswith((".", "!", "?")):
                break

            # Safety limit.
            if len(title_parts) >= 20:
                break

        if not title_parts:
            return None

        title = " ".join(title_parts).strip()

        if not any(char.isalpha() for char in title):
            return None

        confidence = candidate.score

        if number is not None:
            confidence += 2.0

        if title_parts[-1].endswith((".", "!", "?")):
            confidence += 1.0

        return ValidatedSection(
            section_number=number,
            title=title,
            page_number=candidate.page_number,
            confidence=confidence,
        )

    @staticmethod
    def _looks_like_number(text: str) -> bool:
        """Recognize common Arabic and Roman numbering."""

        cleaned = text.strip().rstrip(".,:;")

        if not cleaned:
            return False

        if cleaned.isdigit():
            return True

        return bool(
            re.fullmatch(
                r"[IVXLCDM]+",
                cleaned,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def _looks_like_prose_line(text: str) -> bool:
        """
        Detect a likely body-text line.

        A single word is deliberately never considered prose here,
        because PDF extraction may split a heading into one word
        per line.
        """

        words = text.split()

        # One-word lines are compatible with word-per-line extraction.
        if len(words) <= 1:
            return False

        letters = [
            char
            for char in text
            if char.isalpha()
        ]

        if not letters:
            return False

        lowercase = sum(
            char.islower()
            for char in letters
        )

        lowercase_ratio = lowercase / len(letters)

        return lowercase_ratio > 0.35

    def _is_structural_heading(
        self,
        text: str,
    ) -> bool:

        words = text.split()

        if not words:
            return False

        first_word = (
            words[0]
            .strip(".,:;")
            .lower()
        )

        return first_word in self.STRUCTURAL_KEYWORDS