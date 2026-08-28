from dataclasses import dataclass

from core.layout_section_validator import ValidatedSection
from core.roman_normalizer import RomanNumeralNormalizer


@dataclass
class ReconciledSections:
    """Final document-level structural sections."""

    sections: list[ValidatedSection]


class SectionReconciler:
    """
    Document-level cleanup of validated structural sections.

    This class is deliberately document-agnostic. It never assumes
    a known chapter list, page range, numbering scheme, or title set.
    """

    def __init__(self):
        self.roman_normalizer = RomanNumeralNormalizer()

    def reconcile(
        self,
        sections: list[ValidatedSection],
    ) -> ReconciledSections:
        if not sections:
            return ReconciledSections([])

        ordered = sorted(
            sections,
            key=lambda item: (
                item.page_number,
                -item.confidence,
            ),
        )

        normalized = [
            self._normalize_section(section)
            for section in ordered
        ]

        # First remove exact structural duplicates.
        unique = self._deduplicate(normalized)

        # Then remove only very strong false-positive patterns.
        cleaned = [
            section
            for section in unique
            if not self._is_obvious_false_positive(section)
        ]

        return ReconciledSections(cleaned)

    def _normalize_section(
        self,
        section: ValidatedSection,
    ) -> ValidatedSection:
        number = section.section_number

        if not number:
            return section

        result = self.roman_normalizer.normalize(number)

        if not result.normalized:
            return section

        confidence = section.confidence

        if result.changed:
            # Preserve the useful evidence while reflecting that
            # the number required an OCR correction.
            confidence *= 0.90 + result.confidence * 0.05

        return ValidatedSection(
            section_number=result.normalized,
            title=section.title,
            page_number=section.page_number,
            confidence=confidence,
            detection_method=section.detection_method,
        )

    def _is_obvious_false_positive(
        self,
        section: ValidatedSection,
    ) -> bool:
        title = " ".join(section.title.split()).strip()
        number = section.section_number.strip()

        if not title or not number:
            return True

        # Never accept an invalid Roman-like token such as DID.
        # Arabic numbers are allowed by the generic validator.
        if not number.isdigit():
            roman = self.roman_normalizer.normalize(number)
            if roman.confidence == 0.0:
                return True

        words = title.split()

        # Structural headings normally begin with an uppercase letter
        # (or a numeral/symbol). A lowercase-leading fragment is a
        # strong generic signal that OCR promoted ordinary body text
        # into a heading. Keep a high-confidence escape hatch for
        # unusual document styles.
        if (
            words
            and words[0][:1].islower()
            and section.confidence < 16.0
        ):
            return True

        # OCR can produce strange mixed-case words such as "LosT".
        # Treat these as suspicious only when the title is very short
        # and the confidence is not exceptionally strong.
        if (
            len(words) <= 2
            and any(self._has_internal_case_noise(word) for word in words)
            and section.confidence < 16.0
        ):
            return True

        return False

    @staticmethod
    def _has_internal_case_noise(word: str) -> bool:
        letters = [char for char in word if char.isalpha()]

        if len(letters) < 3:
            return False

        has_upper = any(char.isupper() for char in letters[1:])
        has_lower = any(char.islower() for char in letters)

        return has_upper and has_lower

    @staticmethod
    def _deduplicate(
        sections: list[ValidatedSection],
    ) -> list[ValidatedSection]:
        result = []
        seen = set()

        for section in sections:
            key = (
                section.page_number,
                section.section_number,
                section.title.strip().upper(),
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(section)

        return result
