from dataclasses import dataclass
from core.layout_heading_detector import LayoutHeadingCandidate
from core.layout_section_validator import (
    LayoutSectionValidator,
    ValidatedSection,
)
from core.page_structure_classifier import PageStructureClassifier


@dataclass
class RecoveryCandidate:
    """A weak structural candidate retained for second-pass review."""

    page_number: int
    candidates: list[LayoutHeadingCandidate]
    reason: str
    score: float


class SectionRecovery:
    """
    Second-pass recovery for pages that already showed structural
    heading evidence during the primary scan.

    Crucially, recovery does not rescan arbitrary page ranges and does
    not infer missing chapter numbers from sequence. It only revisits
    weak candidates that the primary pass already observed.
    """

    def __init__(
        self,
        validator: LayoutSectionValidator | None = None,
        classifier: PageStructureClassifier | None = None,
    ):
        self.validator = validator or LayoutSectionValidator()
        self.classifier = classifier or PageStructureClassifier()

    def collect_candidate(
        self,
        page_number: int,
        candidates: list[LayoutHeadingCandidate],
        page_type: str,
    ) -> RecoveryCandidate | None:
        if not candidates:
            return None

        # Never use contents/navigation pages for section recovery.
        if page_type == PageStructureClassifier.CONTENTS:
            return None

        strongest = max(
            candidates,
            key=lambda candidate: candidate.score,
        )

        # Retain only pages with meaningful structural evidence.
        if strongest.score < 5.0:
            return None

        return RecoveryCandidate(
            page_number=page_number,
            candidates=candidates,
            reason="weak-heading-evidence",
            score=strongest.score,
        )

    def recover(
        self,
        candidates: list[RecoveryCandidate],
        existing: list[ValidatedSection],
    ) -> list[ValidatedSection]:
        recovered = []

        for candidate in candidates:
            # Validate candidates individually on the second pass.
            # This avoids the primary page-level decision suppressing
            # a legitimate candidate when another weak candidate is
            # present on the same page.
            for heading in sorted(
                candidate.candidates,
                key=lambda item: item.score,
                reverse=True,
            ):
                validated = self.validator.validate([heading])

                for section in validated:
                    if self._is_duplicate(
                        section,
                        existing,
                        recovered,
                    ):
                        continue

                    recovered.append(section)

        return recovered

    @staticmethod
    def _is_duplicate(
        section: ValidatedSection,
        existing: list[ValidatedSection],
        recovered: list[ValidatedSection],
    ) -> bool:
        for other in existing + recovered:
            if (
                section.page_number == other.page_number
                and section.section_number == other.section_number
            ):
                return True

        return False
