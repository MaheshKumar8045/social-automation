from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    GENERATED = "generated"
    VALIDATED = "validated"
    COMPLETED = "completed"
    RETRY = "retry"
    MANUAL_REVIEW = "manual_review"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class SceneJob:
    scene_id: int
    scene_order: int
    title: str
    prompt: str
    overlays: list[dict[str, Any]]
    record: dict[str, Any]


@dataclass(frozen=True)
class PipelineConfig:
    package_path: Path
    output_dir: Path
    limit: int | None = None
    start_order: int | None = None
    max_attempts: int = 3
    generation_timeout_s: float = 240.0
    page_timeout_ms: int = 45_000
    human_delay_min: float = 1.2
    human_delay_max: float = 2.8
    use_previous_reference: bool = True
    vision_validation: bool = True
    vision_model: str = "qwen2.5vl:7b"
    vision_timeout_s: float = 180.0
    keep_browser_open_on_error: bool = False
    chrome_user_data_dir: Path | None = None
    chrome_profile_directory: str | None = None
    chrome_cdp_url: str | None = None
    chrome_auto_launch: bool = True
    chrome_auto_user_data_dir: Path | None = None
