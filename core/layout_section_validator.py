from dataclasses import dataclass
import re

from core.layout_heading_detector import LayoutHeadingCandidate
from core.text_fragment import TextFragment


@dataclass
class ValidatedSection:
    """A validated structural section."""

    section_number: str | None
    title: str
    page_number: int
    confidence: float
    detection_method: str = "primary"


class LayoutSectionValidator:
    """
    Validate layout-aware heading candidates.

    The validator is document-agnostic.

    It tries to distinguish:
        CHAPTER + NUMBER + TITLE

    from contents/index structures such as:
        CHAPTER + NUMBER + PAGE NUMBER
    """

    ROMAN_RE = re.compile(
        r"^[IVXLCDM]+$",
        re.IGNORECASE,
    )

    NUMBER_RE = re.compile(
        r"^\d+$",
    )

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
        candidates: list[LayoutHeadingCandidate],
    ) -> list[ValidatedSection]:

        if not candidates:
            return []

        strong_candidates = [
            candidate
            for candidate in candidates
            if self._has_number(candidate)
        ]

        # Several CHAPTER + NUMBER structures on the same page
        # are a strong contents/index signal.
        contents_like = len(strong_candidates) >= 2

        results = []

        for candidate in candidates:
            if not self._has_number(candidate):
                continue

            if self._looks_like_contents_entry(candidate):
                continue

            score = candidate.score

            score += 2.0

            if self._has_title(candidate):
                score += 2.0
            else:
                continue

            if self._title_is_spatially_coherent(candidate):
                score += 1.5

            if contents_like:
                score -= 5.0

            if self._contains_suspicious_material(candidate):
                score -= 4.0

            if score < 7.0:
                continue

            number = self._extract_number(candidate)
            title = self._extract_title(candidate)

            if not title:
                continue

            results.append(
                ValidatedSection(
                    section_number=number,
                    title=title,
                    page_number=candidate.page_number,
                    confidence=score,
                )
            )

        return results

    def _looks_like_contents_entry(
        self,
        candidate: LayoutHeadingCandidate,
    ) -> bool:

        fragments = candidate.fragments

        number_fragment = None

        for fragment in fragments:
            if self._looks_like_number(
                fragment.text
            ):
                number_fragment = fragment
                break

        if number_fragment is None:
            return False

        number_x = number_fragment.x

        if number_x is None:
            return False

        suspicious_right_side = []

        for fragment in fragments:
            if fragment is number_fragment:
                continue

            text = fragment.text.strip()

            if not text:
                continue

            if fragment.x is None:
                continue

            # Numeric/page-marker material appearing far to the
            # right of the chapter number is characteristic of
            # contents tables.
            if fragment.x > number_x + 250:
                suspicious_right_side.append(fragment)

        if not suspicious_right_side:
            return False

        numeric_or_marker_count = 0

        for fragment in suspicious_right_side:
            text = fragment.text.strip()

            if self._looks_like_number(text):
                numeric_or_marker_count += 1
                continue

            cleaned = text.upper()

            if cleaned in {
                "PAGE",
                "@PAGE",
                "AGE",
                "E",
                "E@",
                "»",
            }:
                numeric_or_marker_count += 1

        return numeric_or_marker_count >= 1

    def _has_number(
        self,
        candidate: LayoutHeadingCandidate,
    ) -> bool:

        return any(
            self._looks_like_number(
                fragment.text
            )
            for fragment in candidate.fragments
        )

    def _extract_number(
        self,
        candidate: LayoutHeadingCandidate,
    ) -> str | None:

        for fragment in candidate.fragments:
            text = fragment.text.strip()
            cleaned = text.rstrip(".,:;")

            if self._looks_like_number(cleaned):
                return cleaned.upper()

        return None

    def _extract_title(
        self,
        candidate: LayoutHeadingCandidate,
    ) -> str:

        fragments = candidate.fragments

        title_fragments = []

        number_seen = False

        number_fragment = None

        for fragment in fragments:
            text = fragment.text.strip()

            if not text:
                continue

            cleaned = text.rstrip(".,:;")

            if self._looks_like_number(cleaned):
                number_seen = True
                number_fragment = fragment
                continue

            if self._is_structural_keyword(text):
                continue

            if not number_seen:
                continue

            # Do not include material far to the right of the
            # chapter number. This prevents contents-page
            # page numbers from becoming the title.
            if (
                number_fragment is not None
                and fragment.x is not None
                and number_fragment.x is not None
            ):
                if fragment.x > number_fragment.x + 250:
                    continue

            # Ignore obvious page-number artifacts.
            if self._is_page_artifact(text):
                continue

            title_fragments.append(fragment)

        title_fragments.sort(
            key=lambda fragment: (
                fragment.x
                if fragment.x is not None
                else 0.0
            )
        )

        return " ".join(
            fragment.text.strip()
            for fragment in title_fragments
            if fragment.text.strip()
        ).strip()

    def _has_title(
        self,
        candidate: LayoutHeadingCandidate,
    ) -> bool:

        return bool(
            self._extract_title(candidate)
        )

    def _title_is_spatially_coherent(
        self,
        candidate: LayoutHeadingCandidate,
    ) -> bool:

        fragments = candidate.fragments

        number_seen = False
        number_fragment = None
        title_fragments = []

        for fragment in fragments:
            text = fragment.text.strip()

            if not text:
                continue

            cleaned = text.rstrip(".,:;")

            if self._looks_like_number(cleaned):
                number_seen = True
                number_fragment = fragment
                continue

            if self._is_structural_keyword(text):
                continue

            if not number_seen:
                continue

            if (
                number_fragment is not None
                and fragment.x is not None
                and number_fragment.x is not None
                and fragment.x > number_fragment.x + 250
            ):
                continue

            if self._is_page_artifact(text):
                continue

            if fragment.y is not None:
                title_fragments.append(fragment)

        if len(title_fragments) < 2:
            return False

        y_values = [
            fragment.y
            for fragment in title_fragments
            if fragment.y is not None
        ]

        if len(y_values) < 2:
            return False

        spread = max(y_values) - min(y_values)

        return spread <= 40.0

    def _contains_suspicious_material(
        self,
        candidate: LayoutHeadingCandidate,
    ) -> bool:

        for fragment in candidate.fragments:
            text = fragment.text.strip()

            if self._is_page_artifact(text):
                return True

        return False

    @staticmethod
    def _is_page_artifact(
        text: str,
    ) -> bool:

        cleaned = text.strip().upper()

        if cleaned in {
            "@PAGE",
            "PAGE",
            "AGE",
            "E@",
        }:
            return True

        return False

    @staticmethod
    def _is_structural_keyword(
        text: str,
    ) -> bool:

        return (
            text.strip()
            .strip(".,:;")
            .lower()
            in LayoutSectionValidator.STRUCTURAL_KEYWORDS
        )

    @classmethod
    def _looks_like_number(
        cls,
        text: str,
    ) -> bool:

        cleaned = text.strip().rstrip(".,:;")

        if not cleaned:
            return False

        if cls.NUMBER_RE.fullmatch(cleaned):
            return True

        return bool(
            cls.ROMAN_RE.fullmatch(cleaned)
        )