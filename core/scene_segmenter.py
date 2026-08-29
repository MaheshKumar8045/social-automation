from __future__ import annotations

import re

from core.models import SceneRecord


class SceneSegmenter:
    """
    Deterministically split a story into source-grounded scene units.

    This baseline does not invent events or rewrite source text. It uses
    paragraph boundaries and a configurable target character window. A
    later semantic/LLM segmenter can replace this strategy while preserving
    the SceneRecord contract.
    """

    def __init__(
        self,
        *,
        target_chars: int = 3500,
        min_chars: int = 900,
        strategy: str = "paragraph_window",
    ):
        if target_chars <= 0:
            raise ValueError("target_chars must be greater than 0")
        if min_chars < 0 or min_chars > target_chars:
            raise ValueError("min_chars must be >= 0 and <= target_chars")
        if strategy != "paragraph_window":
            raise ValueError("Unsupported strategy. Use 'paragraph_window'.")
        self.target_chars = target_chars
        self.min_chars = min_chars
        self.strategy = strategy

    def segment(
        self,
        story: dict,
        *,
        page_text: dict[int, str] | None = None,
    ) -> list[SceneRecord]:
        text = str(story.get("text") or "").strip()
        if not text:
            return []

        paragraphs = self._paragraphs(text)
        if len(paragraphs) <= 1:
            return [self._make_scene(1, story, text, "story_default")]

        groups: list[str] = []
        current: list[str] = []
        current_len = 0

        for paragraph in paragraphs:
            addition = len(paragraph) + (2 if current else 0)
            if current and current_len >= self.min_chars and current_len + addition > self.target_chars:
                groups.append("\n\n".join(current))
                current = []
                current_len = 0
            current.append(paragraph)
            current_len += addition

        if current:
            if groups and current_len < self.min_chars:
                groups[-1] = groups[-1] + "\n\n" + "\n\n".join(current)
            else:
                groups.append("\n\n".join(current))

        scenes: list[SceneRecord] = []
        cursor = 0
        for order, group in enumerate(groups, start=1):
            start_offset = text.find(group, cursor)
            if start_offset < 0:
                start_offset = cursor
            end_offset = start_offset + len(group)
            cursor = end_offset

            page_start, page_end = self._page_range(
                story, text, start_offset, end_offset, page_text
            )
            scenes.append(
                self._make_scene(
                    order,
                    story,
                    group,
                    self.strategy,
                    page_start=page_start,
                    page_end=page_end,
                )
            )
        return scenes

    @staticmethod
    def _paragraphs(text: str) -> list[str]:
        parts = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
        return parts or [text.strip()]

    @staticmethod
    def _page_range(
        story: dict,
        full_text: str,
        start: int,
        end: int,
        page_text: dict[int, str] | None,
    ) -> tuple[int, int]:
        page_start = int(story["page_start"])
        page_end = int(story["page_end"])
        if not page_text or page_start >= page_end:
            return page_start, page_end

        # Best-effort provenance mapping for future callers that provide the
        # page texts used to construct the story.
        cursor = 0
        selected: list[int] = []
        for page, value in sorted(page_text.items()):
            value = str(value or "")
            if not value:
                continue
            pos = full_text.find(value, cursor)
            if pos < 0:
                continue
            page_a, page_b = pos, pos + len(value)
            if page_b > start and page_a < end:
                selected.append(page)
            cursor = page_b
        if selected:
            return min(selected), max(selected)
        return page_start, page_end

    @staticmethod
    def _make_scene(
        order: int,
        story: dict,
        text: str,
        method: str,
        *,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> SceneRecord:
        story_title = str(story.get("title") or f"Story {story.get('story_order', order)}")
        title = f"{story_title} — Scene {order}"
        return SceneRecord(
            scene_order=order,
            title=title,
            page_start=int(page_start if page_start is not None else story["page_start"]),
            page_end=int(page_end if page_end is not None else story["page_end"]),
            text=text.strip(),
            segmentation_method=method,
            confidence=1.0,
        )
