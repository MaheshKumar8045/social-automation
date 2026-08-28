from dataclasses import dataclass
from typing import Any


@dataclass
class HeadingCandidate:
    """A possible document heading."""

    page_number: int
    text: str
    line_index: int
    score: float
    reason: str


class HeadingDetector:
    """
    Finds structurally plausible heading candidates.

    This detector intentionally does not decide whether something
    is a chapter. It identifies lines with meaningful heading signals.
    """

    HEADING_KEYWORDS = {
        "chapter",
        "section",
        "part",
        "appendix",
        "prologue",
        "epilogue",
        "introduction",
        "conclusion",
    }

    def find_candidates(
        self,
        page_number: int,
        lines: list[str],
        scores: list[float] | None = None,
        boxes: Any = None,
    ) -> list[HeadingCandidate]:

        candidates = []

        for index, line in enumerate(lines):
            text = line.strip()

            if not text:
                continue

            score = 0.0
            reasons = []

            words = text.split()
            lower = text.lower()

            # Explicit heading keywords are the strongest text signal.
            if any(
                keyword in words_lower
                for keyword in self.HEADING_KEYWORDS
                for words_lower in [lower.split()]
            ):
                score += 4.0
                reasons.append("heading-keyword")

            # A standalone number can indicate a numbered heading.
            if self._looks_like_numbered_heading(text):
                score += 2.0
                reasons.append("numbered-heading")

            # A standalone Roman numeral can indicate a heading number.
            if self._looks_like_roman_numeral(text):
                score += 2.0
                reasons.append("roman-number")

            # A short line containing several words can be a title,
            # but this is only a weak signal by itself.
            if 2 <= len(words) <= 12 and len(text) <= 100:
                score += 0.5
                reasons.append("short-title")

            # OCR confidence is useful, but only as supporting evidence.
            if scores is not None and index < len(scores):
                if scores[index] >= 0.90:
                    score += 0.5
                    reasons.append("high-ocr-confidence")

            # Do not emit candidates based only on weak signals.
            if score < 2.0:
                continue

            candidates.append(
                HeadingCandidate(
                    page_number=page_number,
                    text=text,
                    line_index=index,
                    score=score,
                    reason=", ".join(reasons),
                )
            )

        return candidates

    @staticmethod
    def _looks_like_numbered_heading(text: str) -> bool:
        cleaned = text.strip().rstrip(".,:;")

        if not cleaned:
            return False

        if cleaned.isdigit():
            return True

        # Examples:
        # 1 Introduction
        # 2. Background
        parts = cleaned.split(maxsplit=1)

        if len(parts) == 2:
            number, remainder = parts

            if number.isdigit() and len(remainder) <= 100:
                return True

        return False

    @staticmethod
    def _looks_like_roman_numeral(text: str) -> bool:
        roman = set("IVXLCDM")

        cleaned = text.strip().rstrip(".,:;").upper()

        if not cleaned:
            return False

        return (
            len(cleaned) <= 12
            and all(char in roman for char in cleaned)
        )