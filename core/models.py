from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
@dataclass(frozen=True)
class PageRecord:
    page_number:int; page_type:str; source:str; text:str; ocr_used:bool
    raw_text:str=""; quality_score:float=0.0; normalization_method:str=""
@dataclass(frozen=True)
class DocumentStructure:
    pdf_path:Path; total_pages:int; sections:list[Any]; pages:list[PageRecord]; document_type:str="unknown"
    @property
    def scanned_page_count(self): return len(self.pages)
    @property
    def scanned_page_end(self): return max((p.page_number for p in self.pages),default=0)


@dataclass(frozen=True)
class StoryRecord:
    """A source-grounded narrative unit belonging to one detected section."""

    story_order: int
    title: str
    page_start: int
    page_end: int
    text: str
    section_order: int
    segmentation_method: str = "section_default"
    confidence: float = 1.0


@dataclass(frozen=True)
class SceneRecord:
    """A source-grounded scene unit belonging to one story."""

    scene_order: int
    title: str
    page_start: int
    page_end: int
    text: str
    segmentation_method: str = "paragraph_window"
    confidence: float = 1.0


@dataclass(frozen=True)
class EntityRecord:
    """A reusable source-grounded character, location, or environment entity."""
    entity_type: str
    canonical_name: str
    profile_text: str
    confidence: float = 0.5
    discovery_method: str = "heuristic"

@dataclass(frozen=True)
class EntityMentionRecord:
    """A source occurrence linking an entity back to a scene."""
    entity_type: str
    canonical_name: str
    scene_id: int
    story_id: int
    page_start: int
    page_end: int
    mention_text: str
    context: str
    confidence: float = 0.5

@dataclass(frozen=True)
class EventRecord:
    """A source-grounded event candidate associated with a scene."""
    event_order: int
    title: str
    page_start: int
    page_end: int
    text: str
    discovery_method: str = "scene_event"
    confidence: float = 0.4


@dataclass(frozen=True)
class EntityAliasRecord:
    """A source-grounded alias mapped to a canonical entity."""
    entity_id: int
    alias: str
    resolution_method: str
    confidence: float
