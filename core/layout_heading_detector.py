from dataclasses import dataclass
import re
from statistics import median

from core.text_fragment import TextFragment


@dataclass
class LayoutHeadingCandidate:
    """A possible structural heading detected from page layout."""

    page_number: int
    text: str
    fragments: list[TextFragment]
    score: float
    reason: str


class LayoutHeadingDetector:
    """
    Generic, layout-aware heading candidate detector.

    The detector adapts to the current page instead of assuming
    fixed font sizes or fixed page dimensions.

    It supports both:
        - PDF text fragments
        - OCR fragments
    """

    STRUCTURAL_KEYWORDS = {
        "chapter",
        "section",
        "part",
        "appendix",
        "prologue",
        "epilogue",
    }

    ROMAN_RE = re.compile(
        r"^[IVXLCDM]+[.,:;]?$",
        re.IGNORECASE,
    )

    NUMBER_RE = re.compile(
        r"^\d+[.,:;]?$",
    )

    def find_candidates(
        self,
        page_number: int,
        fragments: list[TextFragment],
    ) -> list[LayoutHeadingCandidate]:

        if not fragments:
            return []

        body_size = self._estimate_body_size(fragments)

        candidates = []

        for index, fragment in enumerate(fragments):
            if not self._is_structural_keyword(
                fragment.text
            ):
                continue

            candidate = self._build_candidate(
                page_number,
                fragments,
                index,
                body_size,
            )

            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def _build_candidate(
        self,
        page_number: int,
        fragments: list[TextFragment],
        keyword_index: int,
        body_size: float,
    ) -> LayoutHeadingCandidate | None:

        keyword = fragments[keyword_index]

        block = [keyword]
        score = 3.0
        reasons = ["heading-keyword"]

        # A structural keyword that is substantially larger
        # than ordinary page text is a stronger heading signal.
        if self._is_larger_than_body(
            keyword,
            body_size,
        ):
            score += 2.0
            reasons.append("larger-than-body")

        number_index = self._find_nearby_number(
            fragments,
            keyword_index,
            body_size,
        )

        if number_index is not None:
            block.append(
                fragments[number_index]
            )
            score += 3.0
            reasons.append("nearby-number")

        title_fragments = self._find_title_fragments(
            fragments,
            keyword_index,
            number_index,
            body_size,
        )

        if title_fragments:
            block.extend(title_fragments)
            score += 2.0
            reasons.append("nearby-title")

        block = self._unique_fragments(block)

        text = " ".join(
            fragment.text.strip()
            for fragment in block
            if fragment.text.strip()
        )

        if not text:
            return None

        return LayoutHeadingCandidate(
            page_number=page_number,
            text=text,
            fragments=block,
            score=score,
            reason=",".join(reasons),
        )

    def _find_nearby_number(
        self,
        fragments: list[TextFragment],
        keyword_index: int,
        body_size: float,
    ) -> int | None:

        keyword = fragments[keyword_index]

        for index in range(
            keyword_index + 1,
            min(keyword_index + 8, len(fragments)),
        ):
            fragment = fragments[index]

            if not self._looks_like_number(
                fragment.text
            ):
                continue

            if self._is_near(
                keyword,
                fragment,
                body_size,
            ):
                return index

        return None

    def _find_title_fragments(
        self,
        fragments: list[TextFragment],
        keyword_index: int,
        number_index: int | None,
        body_size: float,
    ) -> list[TextFragment]:

        anchor_index = (
            number_index
            if number_index is not None
            else keyword_index
        )

        anchor = fragments[anchor_index]

        if anchor.y is None:
            return []

        next_row = self._find_next_visual_row(
            fragments,
            anchor_index,
            body_size,
        )

        if next_row is None:
            return []

        title_fragments = []

        # Estimate a page-relative horizontal range.
        page_width = self._estimate_page_width(
            fragments
        )

        for index in range(
            anchor_index + 1,
            len(fragments),
        ):
            fragment = fragments[index]

            if fragment.y is None:
                continue

            if abs(fragment.y - next_row) > self._row_tolerance(
                body_size
            ):
                continue

            if self._is_structural_keyword(
                fragment.text
            ):
                continue

            if self._looks_like_number(
                fragment.text
            ):
                continue

            if self._looks_like_page_marker(
                fragment.text
            ):
                continue

            # Reject fragments that are clearly in a distant
            # column rather than part of the heading.
            if self._is_distant_column(
                anchor,
                fragment,
                page_width,
            ):
                continue

            title_fragments.append(fragment)

        title_fragments.sort(
            key=lambda fragment: (
                fragment.x
                if fragment.x is not None
                else 0.0
            )
        )

        return title_fragments

    def _find_next_visual_row(
        self,
        fragments: list[TextFragment],
        anchor_index: int,
        body_size: float,
    ) -> float | None:

        anchor = fragments[anchor_index]

        if anchor.y is None:
            return None

        anchor_y = anchor.y

        distances = []

        for fragment in fragments[anchor_index + 1:]:
            if fragment.y is None:
                continue

            distance = abs(
                fragment.y - anchor_y
            )

            minimum_gap = max(
                body_size * 0.25,
                4.0,
            )

            maximum_gap = max(
                body_size * 5.0,
                80.0,
            )

            if (
                distance >= minimum_gap
                and distance <= maximum_gap
            ):
                distances.append(distance)

        if not distances:
            return None

        return anchor_y + min(
            distances,
            key=lambda distance: distance,
        ) * self._direction(
            fragments,
            anchor_index,
        )

    @staticmethod
    def _direction(
        fragments: list[TextFragment],
        anchor_index: int,
    ) -> float:

        """
        Estimate the page's vertical reading direction.

        PDF text commonly moves toward smaller Y values.
        OCR commonly moves toward larger Y values.
        """

        anchor = fragments[anchor_index]

        if anchor.y is None:
            return -1.0

        following = []

        for fragment in fragments[
            anchor_index + 1:
        ]:
            if fragment.y is None:
                continue

            if abs(fragment.y - anchor.y) < 5:
                continue

            following.append(fragment.y)

            if len(following) >= 5:
                break

        if not following:
            return -1.0

        above = sum(
            value < anchor.y
            for value in following
        )

        below = sum(
            value > anchor.y
            for value in following
        )

        return -1.0 if above >= below else 1.0

    @staticmethod
    def _estimate_body_size(
        fragments: list[TextFragment],
    ) -> float:

        sizes = []

        for fragment in fragments:
            size = (
                fragment.font_size
                or fragment.height
            )

            if size is None:
                continue

            if size <= 0:
                continue

            sizes.append(float(size))

        if not sizes:
            return 20.0

        # Median is more robust than an arbitrary fixed value.
        return median(sizes)

    @staticmethod
    def _estimate_page_width(
        fragments: list[TextFragment],
    ) -> float:

        right_edges = []

        for fragment in fragments:
            if fragment.x is None:
                continue

            width = fragment.width or 0.0

            right_edges.append(
                fragment.x + width
            )

        if not right_edges:
            return 1000.0

        return max(right_edges)

    @staticmethod
    def _is_larger_than_body(
        fragment: TextFragment,
        body_size: float,
    ) -> bool:

        size = (
            fragment.font_size
            or fragment.height
        )

        if size is None:
            return False

        return size >= body_size * 1.15

    @staticmethod
    def _row_tolerance(
        body_size: float,
    ) -> float:

        return max(
            body_size * 0.75,
            10.0,
        )

    @staticmethod
    def _is_distant_column(
        anchor: TextFragment,
        fragment: TextFragment,
        page_width: float,
    ) -> bool:

        if (
            anchor.x is None
            or fragment.x is None
        ):
            return False

        distance = abs(
            fragment.x - anchor.x
        )

        # Use page width rather than a fixed pixel threshold.
        return distance > page_width * 0.55

    @staticmethod
    def _is_near(
        first: TextFragment,
        second: TextFragment,
        body_size: float,
    ) -> bool:

        if (
            first.x is None
            or second.x is None
            or first.y is None
            or second.y is None
        ):
            return True

        horizontal = abs(
            second.x - first.x
        )

        vertical = abs(
            second.y - first.y
        )

        allowed_horizontal = max(
            body_size * 12,
            100.0,
        )

        allowed_vertical = max(
            body_size * 3,
            40.0,
        )

        return (
            horizontal <= allowed_horizontal
            and vertical <= allowed_vertical
        )

    @classmethod
    def _looks_like_number(
        cls,
        text: str,
    ) -> bool:

        cleaned = text.strip()

        if cls.NUMBER_RE.fullmatch(cleaned):
            return True

        return bool(
            cls.ROMAN_RE.fullmatch(cleaned)
        )

    @classmethod
    def _is_structural_keyword(
        cls,
        text: str,
    ) -> bool:

        cleaned = (
            text.strip()
            .strip(".,:;")
            .lower()
        )

        return cleaned in cls.STRUCTURAL_KEYWORDS

    @staticmethod
    def _looks_like_page_marker(
        text: str,
    ) -> bool:

        cleaned = text.strip().upper()

        return cleaned in {
            "PAGE",
            "@PAGE",
            "AGE",
        }

    @staticmethod
    def _unique_fragments(
        fragments: list[TextFragment],
    ) -> list[TextFragment]:

        result = []
        seen = set()

        for fragment in fragments:
            identity = id(fragment)

            if identity in seen:
                continue

            seen.add(identity)
            result.append(fragment)

        return result