from dataclasses import dataclass

from core.layout_heading_detector import LayoutHeadingCandidate


@dataclass
class PageStructure:
    """Classification of the structural role of one page."""

    page_number: int
    page_type: str
    candidates: list[LayoutHeadingCandidate]


class PageStructureClassifier:
    """
    Classify a page using the relationships between structural
    heading candidates.

    This is intentionally document-agnostic.

    Possible page types:

        SECTION_START
        CONTENTS
        NORMAL
        UNKNOWN

    The classifier does not depend on a particular book's page
    numbers, chapter count, font size, or layout dimensions.
    """

    SECTION_START = "SECTION_START"
    CONTENTS = "CONTENTS"
    NORMAL = "NORMAL"
    UNKNOWN = "UNKNOWN"

    def classify(
        self,
        page_number: int,
        candidates: list[LayoutHeadingCandidate],
    ) -> PageStructure:

        if not candidates:
            return PageStructure(
                page_number=page_number,
                page_type=self.NORMAL,
                candidates=[],
            )

        numbered = [
            candidate
            for candidate in candidates
            if self._has_number(candidate)
        ]

        # A page containing several structural numbered entries
        # is more likely to be a contents/index/navigation page
        # than a single section opening.
        if len(numbered) >= 2:
            return PageStructure(
                page_number=page_number,
                page_type=self.CONTENTS,
                candidates=candidates,
            )

        strongest = max(
            candidates,
            key=lambda candidate: candidate.score,
        )

        if self._looks_like_section_start(
            strongest
        ):
            return PageStructure(
                page_number=page_number,
                page_type=self.SECTION_START,
                candidates=[strongest],
            )

        return PageStructure(
            page_number=page_number,
            page_type=self.UNKNOWN,
            candidates=candidates,
        )

    def _looks_like_section_start(
        self,
        candidate: LayoutHeadingCandidate,
    ) -> bool:

        if not self._has_number(candidate):
            return False

        if candidate.score < 7.0:
            return False

        if not self._has_title(candidate):
            return False

        return True

    @staticmethod
    def _has_number(
        candidate: LayoutHeadingCandidate,
    ) -> bool:

        for fragment in candidate.fragments:
            text = fragment.text.strip()
            cleaned = text.rstrip(".,:;")

            if cleaned.isdigit():
                return True

            if (
                cleaned
                and all(
                    character.upper()
                    in "IVXLCDM"
                    for character in cleaned
                )
            ):
                return True

        return False

    @staticmethod
    def _has_title(
        candidate: LayoutHeadingCandidate,
    ) -> bool:

        fragments = candidate.fragments

        number_seen = False
        title_count = 0

        for fragment in fragments:
            text = fragment.text.strip()

            if not text:
                continue

            cleaned = text.rstrip(".,:;")

            if cleaned.isdigit():
                number_seen = True
                continue

            if (
                cleaned
                and all(
                    character.upper()
                    in "IVXLCDM"
                    for character in cleaned
                )
            ):
                number_seen = True
                continue

            if text.lower() in {
                "chapter",
                "section",
                "part",
                "appendix",
                "prologue",
                "epilogue",
            }:
                continue

            if number_seen:
                title_count += 1

        return title_count > 0