from dataclasses import dataclass
from itertools import product
import re


@dataclass
class RomanNormalization:
    original: str
    normalized: str
    changed: bool
    confidence: float


class RomanNumeralNormalizer:
    """
    Normalize Roman numerals that may contain OCR errors.

    This component is document-agnostic.

    It does NOT assume:
        - a particular book
        - a particular chapter count
        - sequential chapters
        - particular page numbers

    It only considers constrained OCR substitutions and accepts
    a correction when the resulting token is a valid Roman numeral.
    """

    ROMAN_RE = re.compile(
        r"^[IVXLCDM]+$",
        re.IGNORECASE,
    )

    OCR_VARIANTS = {
        "0": ("O",),
        "1": ("I", "L"),
        "L": ("I",),
        "I": ("L", "1"),
        "V": ("Y",),
        "Y": ("V",),
        "X": ("K",),
        "K": ("X",),
        "C": ("G",),
        "G": ("C",),
        "D": ("O",),
        "O": ("D",),
    }

    def normalize(
        self,
        value: str,
    ) -> RomanNormalization:

        original = value.strip().upper()

        if not original:
            return RomanNormalization(
                original=value,
                normalized="",
                changed=False,
                confidence=0.0,
            )

        cleaned = self._clean_token(original)

        if self._is_valid_roman(cleaned):
            return RomanNormalization(
                original=value,
                normalized=cleaned,
                changed=(cleaned != original),
                confidence=1.0,
            )

        candidate = self._find_best_candidate(
            cleaned
        )

        if candidate is None:
            return RomanNormalization(
                original=value,
                normalized=cleaned,
                changed=False,
                confidence=0.0,
            )

        normalized, confidence = candidate

        return RomanNormalization(
            original=value,
            normalized=normalized,
            changed=(normalized != original),
            confidence=confidence,
        )

    def _find_best_candidate(
        self,
        token: str,
    ) -> tuple[str, float] | None:

        if len(token) > 12:
            return None

        variants = []

        for character in token:
            choices = [character]

            for replacement in self.OCR_VARIANTS.get(
                character,
                (),
            ):
                if replacement not in choices:
                    choices.append(replacement)

            variants.append(choices)

        best = None

        for candidate_tuple in product(*variants):
            candidate = "".join(candidate_tuple)

            if not self._is_valid_roman(candidate):
                continue

            substitutions = sum(
                original != replacement
                for original, replacement
                in zip(token, candidate)
            )

            if substitutions == 0:
                continue

            confidence = max(
                0.0,
                1.0 - (
                    substitutions
                    / max(len(token), 1)
                ) * 0.5,
            )

            if best is None or confidence > best[1]:
                best = (
                    candidate,
                    confidence,
                )

        return best

    @staticmethod
    def _clean_token(
        value: str,
    ) -> str:

        value = value.strip()

        value = value.rstrip(
            ".,:;!?)]}"
        )

        value = value.lstrip(
            "([{"
        )

        return value.upper()

    @classmethod
    def _is_valid_roman(
        cls,
        value: str,
    ) -> bool:

        if not value:
            return False

        if not cls.ROMAN_RE.fullmatch(value):
            return False

        # Convert the Roman numeral and then reconstruct the
        # canonical representation. This prevents invalid forms
        # such as IIX or VX from being accepted.
        number = cls._roman_to_int(value)

        if number <= 0 or number > 3999:
            return False

        canonical = cls._int_to_roman(number)

        return canonical == value

    @staticmethod
    def _roman_to_int(
        value: str,
    ) -> int:

        values = {
            "I": 1,
            "V": 5,
            "X": 10,
            "L": 50,
            "C": 100,
            "D": 500,
            "M": 1000,
        }

        total = 0
        previous = 0

        for character in reversed(value):
            current = values[character]

            if current < previous:
                total -= current
            else:
                total += current

            previous = current

        return total

    @staticmethod
    def _int_to_roman(
        number: int,
    ) -> str:

        values = (
            (1000, "M"),
            (900, "CM"),
            (500, "D"),
            (400, "CD"),
            (100, "C"),
            (90, "XC"),
            (50, "L"),
            (40, "XL"),
            (10, "X"),
            (9, "IX"),
            (5, "V"),
            (4, "IV"),
            (1, "I"),
        )

        result = []

        remaining = number

        for value, symbol in values:
            while remaining >= value:
                result.append(symbol)
                remaining -= value

        return "".join(result)