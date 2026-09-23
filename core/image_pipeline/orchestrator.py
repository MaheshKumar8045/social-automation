from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from .browser import BrowserBlockedError, BrowserAutomationError, GoogleAIModeBrowser
from .models import JobStatus, PipelineConfig, SceneJob
from .overlay_renderer import OverlayRenderError, render_overlays
from .prompt_loader import load_jobs
from .store import GenerationStore
from .validator import validate_image


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class ImageGenerationPipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.store = GenerationStore(self.config.output_dir / "generation.db")
        self.log = logging.getLogger("social_automation.image_pipeline")
        self.browser = GoogleAIModeBrowser(config)

    def close(self) -> None:
        try:
            self.store.close()
        finally:
            self.browser.close()

    def _story_context(self, job: SceneJob) -> dict[str, Any]:
        plan = _mapping(job.record.get("plan"))
        return {
            "characters": plan.get("characters") or [],
            "objects": plan.get("objects") or [],
            "events": plan.get("events") or [],
            "visual_constraints": plan.get("visual_constraints") or {},
            "visual_inference": plan.get("visual_inference") or {},
            "continuity": plan.get("continuity") or {},
            "source_evidence": plan.get("source_evidence") or [],
        }

    def _visible_characters(self, job: SceneJob) -> list[str]:
        result = []
        for item in _mapping(job.record.get("plan")).get("characters", []):
            if not isinstance(item, dict):
                continue
            if (item.get("source_presence") or {}).get("physical_presence") is True:
                name = str(item.get("canonical_name") or "").strip()
                if name and name.casefold() not in {x.casefold() for x in result}:
                    result.append(name)
        return result

    def _previous_visual_state(self, jobs: list[SceneJob], index: int) -> dict[str, Any]:
        if index <= 0:
            return {}
        previous = jobs[index - 1]
        row = self.store.get(previous.scene_id)
        if not row or row["status"] != JobStatus.COMPLETED or not row["final_path"]:
            return {}
        state: dict[str, Any] = {"image_path": row["final_path"]}
        if row["validation_path"] and Path(row["validation_path"]).exists():
            try:
                state["validation"] = json.loads(Path(row["validation_path"]).read_text(encoding="utf-8"))
            except Exception:
                pass
        return state

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _process_job(self, job: SceneJob, jobs: list[SceneJob], index: int) -> None:
        row = self.store.get(job.scene_id)
        if row and row["status"] == JobStatus.COMPLETED:
            return

        scene_dir = self.config.output_dir / f"scene_{job.scene_order:03d}_{job.scene_id:05d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        previous = self._previous_visual_state(jobs, index)
        visible_characters = self._visible_characters(job)
        current_attempt = int(row["attempt"] if row else 0)

        for attempt in range(current_attempt + 1, self.config.max_attempts + 1):
            attempt_dir = scene_dir / f"attempt_{attempt:02d}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            prompt_path = attempt_dir / f"prompt_attempt_{attempt:02d}.txt"
            prompt_path.write_text(job.prompt, encoding="utf-8")
            image_path = attempt_dir / "generated.png"
            validation_path = attempt_dir / "validation.json"

            self.store.begin_attempt(job.scene_id, attempt, prompt_path)
            self.store.set_status(
                job.scene_id, JobStatus.RUNNING, attempt=attempt,
                prompt_path=str(prompt_path),
                started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                last_error=None,
            )

            try:
                generation = self.browser.generate(
                    prompt=job.prompt,
                    destination=image_path,
                    previous_image=Path(previous["image_path"]) if previous.get("image_path") else None,
                )
                # Stage 1: validate the clean AI-generated artwork. Dialogue is intentionally
                # excluded here because text is a deterministic post-processing stage.
                generation_validation = validate_image(
                    image_path,
                    prompt=job.prompt,
                    overlays=[],
                    title=job.title,
                    visible_characters=visible_characters,
                    story_context=self._story_context(job),
                    previous_visual_state=previous,
                    vision_enabled=self.config.vision_validation,
                    vision_model=self.config.vision_model,
                )

                if generation_validation["status"] != "pass":
                    validation = {
                        "status": generation_validation["status"],
                        "issues": generation_validation.get("issues", []),
                        "checks": generation_validation.get("checks", {}),
                        "generation": generation,
                        "stage": "generation_validation",
                    }
                    self._write_json(validation_path, validation)
                    self.store.set_status(
                        job.scene_id, JobStatus.VALIDATED, validation_path=str(validation_path)
                    )
                    reason = "; ".join(str(x) for x in validation.get("issues", [])[:5]) or "generated image validation failed"
                    self.store.finish_attempt(
                        job.scene_id, attempt, status="validation_failed",
                        image_path=image_path, validation_path=validation_path,
                        failure_reason=reason,
                    )
                    if attempt < self.config.max_attempts:
                        self.store.set_status(job.scene_id, JobStatus.RETRY, last_error=reason)
                        self.browser.recover()
                        continue
                    self.store.set_status(job.scene_id, JobStatus.MANUAL_REVIEW, last_error=reason)
                    return

                # Stage 2: render the exact source dialogue/narrative text deterministically.
                rendered_path = attempt_dir / "rendered.png"
                try:
                    overlay_result = render_overlays(
                        image_path,
                        rendered_path,
                        job.overlays,
                    )
                except OverlayRenderError as exc:
                    raise BrowserAutomationError(f"deterministic overlay rendering failed: {exc}") from exc

                # Stage 3: validate the actual final artifact, including OCR of the
                # deterministic overlay when overlays are required.
                final_validation = validate_image(
                    rendered_path,
                    prompt=job.prompt,
                    overlays=job.overlays,
                    title=job.title,
                    visible_characters=visible_characters,
                    story_context=self._story_context(job),
                    previous_visual_state=previous,
                    vision_enabled=self.config.vision_validation,
                    vision_model=self.config.vision_model,
                )
                validation = {
                    "status": final_validation["status"],
                    "issues": final_validation.get("issues", []),
                    "checks": final_validation.get("checks", {}),
                    "generation": generation,
                    "generation_validation": generation_validation,
                    "overlay": overlay_result,
                    "final_validation": final_validation,
                    "stage": "final_validation",
                }
                self._write_json(validation_path, validation)
                self.store.set_status(
                    job.scene_id, JobStatus.VALIDATED, validation_path=str(validation_path)
                )

                if validation["status"] == "pass":
                    final_path = scene_dir / "final.png"
                    rendered_path.replace(final_path)
                    final_validation_path = scene_dir / "final_validation.json"
                    self._write_json(final_validation_path, validation)
                    self.store.finish_attempt(
                        job.scene_id, attempt, status="passed",
                        image_path=final_path, validation_path=final_validation_path
                    )
                    self.store.set_status(
                        job.scene_id, JobStatus.COMPLETED,
                        final_path=final_path,
                        validation_path=final_validation_path,
                        completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        last_error=None,
                    )
                    self.log.info("scene %s completed", job.scene_order)
                    return

                reason = "; ".join(str(x) for x in validation.get("issues", [])[:5]) or "validation requested retry"
                self.store.finish_attempt(
                    job.scene_id, attempt, status="validation_failed",
                    image_path=image_path, validation_path=validation_path,
                    failure_reason=reason,
                )
                if attempt < self.config.max_attempts:
                    self.store.set_status(job.scene_id, JobStatus.RETRY, last_error=reason)
                    self.browser.recover()
                    continue
                self.store.set_status(job.scene_id, JobStatus.MANUAL_REVIEW, last_error=reason)
                return

            except BrowserBlockedError as exc:
                self.store.finish_attempt(
                    job.scene_id, attempt, status="blocked", failure_reason=str(exc)
                )
                self.store.set_status(job.scene_id, JobStatus.BLOCKED, last_error=str(exc))
                raise
            except Exception as exc:
                self.log.exception("scene %s attempt %s failed", job.scene_order, attempt)
                self.store.finish_attempt(
                    job.scene_id, attempt, status="error", failure_reason=str(exc)
                )
                if attempt < self.config.max_attempts:
                    self.store.set_status(job.scene_id, JobStatus.RETRY, last_error=str(exc))
                    try:
                        self.browser.recover()
                    except Exception:
                        pass
                    continue
                self.store.set_status(job.scene_id, JobStatus.FAILED, last_error=str(exc))
                return

    def run(self) -> dict[str, Any]:
        jobs = load_jobs(self.config.package_path)
        hashes = {job.scene_id: _hash_prompt(job.prompt) for job in jobs}
        self.store.ensure_jobs(jobs, hashes)

        ids = set(self.store.pending_or_retry(self.config.limit, self.config.start_order))
        selected = [job for job in jobs if job.scene_id in ids]
        if not selected:
            return {"selected": 0, "summary": self.store.summary()}

        self.browser.start()
        try:
            index_by_id = {job.scene_id: index for index, job in enumerate(jobs)}
            for job in selected:
                self._process_job(job, jobs, index_by_id[job.scene_id])
        finally:
            self.browser.close()

        return {"selected": len(selected), "summary": self.store.summary()}
