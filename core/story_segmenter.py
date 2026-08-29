from __future__ import annotations

from core.models import DocumentStructure, StoryRecord


class StorySegmenter:
    """
    Create source-grounded narrative units from detected sections.

    The baseline strategy intentionally treats each section as one story unit.
    This is a safe structural segmentation: it never invents boundaries or
    rewrites source text. The class is designed as a seam for a later semantic
    segmenter (LLM or other model) that can split a section into multiple
    stories while retaining the same StoryRecord contract.
    """

    def __init__(self, strategy: str = "section"):
        if strategy != "section":
            raise ValueError(
                "Unsupported strategy. The deterministic baseline is 'section'."
            )
        self.strategy = strategy

    def segment(self, structure: DocumentStructure) -> list[StoryRecord]:
        pages = {p.page_number: p for p in structure.pages}
        sections = sorted(
            structure.sections,
            key=lambda s: (s.page_number, -s.confidence),
        )
        scanned_end = structure.scanned_page_end
        stories: list[StoryRecord] = []

        for order, section in enumerate(sections, start=1):
            start = max(1, int(section.page_number))
            if order < len(sections):
                end = max(start, int(sections[order].page_number) - 1)
            else:
                end = scanned_end
            end = min(end, scanned_end)

            text_parts = []
            for page_number in range(start, end + 1):
                page = pages.get(page_number)
                if page and page.text.strip():
                    text_parts.append(page.text.strip())

            text = "\n\n".join(text_parts).strip()
            if not text:
                continue

            number = (section.section_number or "").strip()
            title = section.title.strip() or f"Section {order}"
            if number:
                title = f"{number}. {title}"

            stories.append(
                StoryRecord(
                    story_order=len(stories) + 1,
                    title=title,
                    page_start=start,
                    page_end=end,
                    text=text,
                    section_order=order,
                    segmentation_method="section_default",
                    confidence=1.0,
                )
            )

        return stories
