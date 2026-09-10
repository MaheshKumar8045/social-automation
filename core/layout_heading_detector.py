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

    It supports both PDF text fragments and OCR fragments.
    """

    STRUCTURAL_KEYWORDS = {
        "chapter", "section", "part", "appendix", "prologue", "epilogue",
    }

    ROMAN_RE = re.compile(r"^[IVXLCDM]+[.,:;]?$", re.IGNORECASE)
    NUMBER_RE = re.compile(r"^\d+[.,:;]?$")

    def find_candidates(self, page_number: int, fragments: list[TextFragment]) -> list[LayoutHeadingCandidate]:
        if not fragments:
            return []

        body_size = self._estimate_body_size(fragments)
        candidates = []

        for index, fragment in enumerate(fragments):
            if self._is_structural_keyword(fragment.text):
                candidate = self._build_candidate(page_number, fragments, index, body_size)
                if candidate is not None:
                    candidates.append(candidate)

        for index, fragment in enumerate(fragments):
            if not self._looks_like_number(fragment.text):
                continue
            candidate = self._build_numbered_candidate(page_number, fragments, index, body_size)
            if candidate is not None:
                candidates.append(candidate)

        return self._deduplicate_candidates(candidates)

    def _build_candidate(self, page_number, fragments, keyword_index, body_size):
        keyword = fragments[keyword_index]
        block = [keyword]
        score = 3.0
        reasons = ["heading-keyword"]

        if self._is_larger_than_body(keyword, body_size):
            score += 2.0
            reasons.append("larger-than-body")

        number_index = self._find_nearby_number(fragments, keyword_index, body_size)
        if number_index is not None:
            block.append(fragments[number_index])
            score += 3.0
            reasons.append("nearby-number")

        title_fragments = self._find_title_fragments(fragments, keyword_index, number_index, body_size)
        if title_fragments:
            block.extend(title_fragments)
            score += 2.0
            reasons.append("nearby-title")

        block = self._unique_fragments(block)
        text = " ".join(f.text.strip() for f in block if f.text.strip())
        if not text:
            return None
        return LayoutHeadingCandidate(page_number, text, block, score, ",".join(reasons))

    def _build_numbered_candidate(self, page_number, fragments, number_index, body_size):
        number = fragments[number_index]
        is_arabic = self._is_arabic_number(number.text)

        # A lone Roman numeral is common inside prose (especially "I").
        # Do not promote it unless the page/layout gives strong heading evidence.
        if not is_arabic and not self._roman_has_heading_evidence(fragments, number_index, body_size):
            return None

        block = [number]
        score = 4.0
        reasons = ["heading-number"]

        if self._is_larger_than_body(number, body_size):
            score += 2.0
            reasons.append("larger-than-body")

        title_fragments = self._same_row_title_fragments(fragments, number_index, body_size)
        if title_fragments:
            title_fragments = self._trim_numbered_title(title_fragments)
            if title_fragments:
                block.extend(title_fragments)
                score += 3.0
                reasons.append("same-row-title")
        else:
            next_row = self._find_next_visual_row(fragments, number_index, body_size)
            if next_row is not None:
                title = []
                page_width = self._estimate_page_width(fragments)
                for index in range(number_index + 1, len(fragments)):
                    fragment = fragments[index]
                    if fragment.y is None or abs(fragment.y - next_row) > self._row_tolerance(body_size):
                        continue
                    if self._looks_like_number(fragment.text) or self._is_structural_keyword(fragment.text):
                        continue
                    if self._looks_like_page_marker(fragment.text):
                        continue
                    if self._is_distant_column(number, fragment, page_width):
                        continue
                    title.append(fragment)
                title.sort(key=lambda f: f.x if f.x is not None else 0.0)
                title = self._trim_numbered_title(title)
                if title:
                    block.extend(title)
                    score += 3.0
                    reasons.append("next-row-title")

        # PDF text extraction can preserve the chapter number and title on the
        # same logical line even when no useful coordinates survive.
        if len(block) == 1 and is_arabic:
            inline = self._inline_numbered_title(fragments, number_index)
            if inline:
                block.extend(inline)
                score += 3.0
                reasons.append("inline-title")

        block = self._unique_fragments(block)
        title_present = any(
            f is not number
            and not self._looks_like_number(f.text)
            and not self._is_structural_keyword(f.text)
            for f in block
        )
        if not title_present:
            return None

        title_fragments = [f for f in block if f is not number]
        if self._title_looks_like_prose(title_fragments):
            return None

        text = self._normalize_heading_text(" ".join(f.text.strip() for f in block if f.text.strip()))
        if not text:
            return None
        return LayoutHeadingCandidate(page_number, text, block, score, ",".join(reasons))

    def _inline_numbered_title(self, fragments, number_index):
        result = []
        for fragment in fragments[number_index + 1:number_index + 8]:
            text = fragment.text.strip()
            if not text:
                continue
            if self._looks_like_number(text) or self._is_structural_keyword(text):
                break
            if self._looks_like_page_marker(text):
                break
            result.append(fragment)
            if len(" ".join(f.text for f in result).split()) >= 6:
                break
        return self._trim_numbered_title(result)

    def _trim_numbered_title(self, fragments):
        result = []
        words = []
        for fragment in fragments:
            text = fragment.text.strip()
            if not text:
                continue
            if self._looks_like_page_marker(text):
                break
            words.extend(text.split())
            result.append(fragment)
            if len(words) >= 6:
                break
        if not words:
            return []
        return result

    @staticmethod
    def _title_looks_like_prose(fragments):
        text = " ".join(f.text.strip() for f in fragments if f.text.strip())
        words = text.split()
        if len(words) > 10:
            return True
        if re.search(r"[.!?]$", text):
            return True
        return False

    @classmethod
    def _normalize_heading_text(cls, text):
        text = re.sub(r"\s+", " ", text).strip()
        # Common OCR/PDF split in chapter headings: "T HE" -> "THE".
        text = re.sub(r"\bT\s+HE\b", "THE", text, flags=re.IGNORECASE)
        return text

    @classmethod
    def _is_arabic_number(cls, text):
        return bool(cls.NUMBER_RE.fullmatch(text.strip()))

    def _roman_has_heading_evidence(self, fragments, number_index, body_size):
        number = fragments[number_index]
        if number.text.strip().rstrip(".,:;").upper() == "I":
            # "I" is overwhelmingly likely to be a pronoun in body text.
            return self._is_larger_than_body(number, body_size) and self._has_short_adjacent_title(fragments, number_index, body_size)
        return self._is_larger_than_body(number, body_size) and self._has_short_adjacent_title(fragments, number_index, body_size)

    def _has_short_adjacent_title(self, fragments, number_index, body_size):
        same = self._same_row_title_fragments(fragments, number_index, body_size)
        if same and not self._title_looks_like_prose(self._trim_numbered_title(same)):
            return True
        next_row = self._find_next_visual_row(fragments, number_index, body_size)
        return next_row is not None

    def _same_row_title_fragments(self, fragments, number_index, body_size):
        number = fragments[number_index]
        if number.y is None:
            return []
        tolerance = self._row_tolerance(body_size)
        result = []
        for index, fragment in enumerate(fragments):
            if index == number_index or fragment.y is None:
                continue
            if abs(fragment.y - number.y) > tolerance:
                continue
            if fragment.x is not None and number.x is not None and fragment.x <= number.x:
                continue
            if self._looks_like_number(fragment.text) or self._is_structural_keyword(fragment.text):
                continue
            if self._looks_like_page_marker(fragment.text):
                continue
            if self._is_distant_column(number, fragment, self._estimate_page_width(fragments)):
                continue
            result.append(fragment)
        result.sort(key=lambda f: f.x if f.x is not None else 0.0)
        return result

    def _find_nearby_number(self, fragments, keyword_index, body_size):
        keyword = fragments[keyword_index]
        for index in range(keyword_index + 1, min(keyword_index + 8, len(fragments))):
            fragment = fragments[index]
            if self._looks_like_number(fragment.text) and self._is_near(keyword, fragment, body_size):
                return index
        return None

    def _find_title_fragments(self, fragments, keyword_index, number_index, body_size):
        anchor_index = number_index if number_index is not None else keyword_index
        anchor = fragments[anchor_index]
        if anchor.y is None:
            return []
        next_row = self._find_next_visual_row(fragments, anchor_index, body_size)
        if next_row is None:
            return []
        title_fragments = []
        page_width = self._estimate_page_width(fragments)
        for index in range(anchor_index + 1, len(fragments)):
            fragment = fragments[index]
            if fragment.y is None or abs(fragment.y - next_row) > self._row_tolerance(body_size):
                continue
            if self._is_structural_keyword(fragment.text) or self._looks_like_number(fragment.text) or self._looks_like_page_marker(fragment.text):
                continue
            if self._is_distant_column(anchor, fragment, page_width):
                continue
            title_fragments.append(fragment)
        title_fragments.sort(key=lambda f: f.x if f.x is not None else 0.0)
        return title_fragments

    def _find_next_visual_row(self, fragments, anchor_index, body_size):
        anchor = fragments[anchor_index]
        if anchor.y is None:
            return None
        distances = []
        for fragment in fragments[anchor_index + 1:]:
            if fragment.y is None:
                continue
            distance = abs(fragment.y - anchor.y)
            if max(body_size * 0.25, 4.0) <= distance <= max(body_size * 5.0, 80.0):
                distances.append(distance)
        if not distances:
            return None
        return anchor.y + min(distances) * self._direction(fragments, anchor_index)

    @staticmethod
    def _direction(fragments, anchor_index):
        anchor = fragments[anchor_index]
        if anchor.y is None:
            return -1.0
        following = []
        for fragment in fragments[anchor_index + 1:]:
            if fragment.y is None or abs(fragment.y - anchor.y) < 5:
                continue
            following.append(fragment.y)
            if len(following) >= 5:
                break
        if not following:
            return -1.0
        above = sum(value < anchor.y for value in following)
        below = sum(value > anchor.y for value in following)
        return -1.0 if above >= below else 1.0

    @staticmethod
    def _estimate_body_size(fragments):
        sizes = [float(fragment.font_size or fragment.height) for fragment in fragments if (fragment.font_size or fragment.height) and (fragment.font_size or fragment.height) > 0]
        return median(sizes) if sizes else 20.0

    @staticmethod
    def _estimate_page_width(fragments):
        right_edges = [(f.x + (f.width or 0.0)) for f in fragments if f.x is not None]
        return max(right_edges) if right_edges else 1000.0

    @staticmethod
    def _is_larger_than_body(fragment, body_size):
        size = fragment.font_size or fragment.height
        return size is not None and size >= body_size * 1.15

    @staticmethod
    def _row_tolerance(body_size):
        return max(body_size * 0.75, 10.0)

    @staticmethod
    def _is_distant_column(anchor, fragment, page_width):
        if anchor.x is None or fragment.x is None:
            return False
        return abs(fragment.x - anchor.x) > page_width * 0.55

    @classmethod
    def _looks_like_number(cls, text):
        cleaned = text.strip()
        return bool(cls.NUMBER_RE.fullmatch(cleaned) or cls.ROMAN_RE.fullmatch(cleaned))

    @classmethod
    def _is_structural_keyword(cls, text):
        return text.strip().strip(".,:;").lower() in cls.STRUCTURAL_KEYWORDS

    @staticmethod
    def _looks_like_page_marker(text):
        return text.strip().upper() in {"PAGE", "@PAGE", "AGE"}

    @staticmethod
    def _unique_fragments(fragments):
        result, seen = [], set()
        for fragment in fragments:
            identity = id(fragment)
            if identity not in seen:
                seen.add(identity)
                result.append(fragment)
        return result

    @staticmethod
    def _deduplicate_candidates(candidates):
        result = []
        seen = set()
        for candidate in sorted(candidates, key=lambda c: (-c.score, c.page_number, c.text)):
            key = (candidate.page_number, candidate.text.lower())
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)
        return result
