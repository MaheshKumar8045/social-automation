from pathlib import Path

from core.image_pipeline.models import JobStatus
from core.image_pipeline.prompt_loader import load_jobs
from core.image_pipeline.store import GenerationStore


def _package(path: Path):
    path.write_text(
        """{
          "scene_count": 2,
          "scenes": [
            {
              "scene_id": 2, "scene_order": 2, "title": "Second",
              "plan": {"image_prompt": "Create image two", "media_prompt_package": {"image": {"dialogue_overlays": []}}}
            },
            {
              "scene_id": 1, "scene_order": 1, "title": "First",
              "plan": {"image_prompt": "Create image one", "media_prompt_package": {"image": {"dialogue_overlays": [{"text": "Hello", "required": true}]}}}
            }
          ]
        }""",
        encoding="utf-8",
    )


def test_load_jobs_sorts_by_scene_order(tmp_path: Path):
    path = tmp_path / "all_prompts.json"
    _package(path)
    jobs = load_jobs(path)
    assert [x.scene_order for x in jobs] == [1, 2]
    assert jobs[0].overlays[0]["text"] == "Hello"


def test_generation_store_resumes_pending_and_completed(tmp_path: Path):
    path = tmp_path / "all_prompts.json"
    _package(path)
    jobs = load_jobs(path)
    store = GenerationStore(tmp_path / "generation.db")
    try:
        store.ensure_jobs(jobs, {job.scene_id: str(job.scene_id) for job in jobs})
        assert store.pending_or_retry() == [1, 2]
        store.set_status(1, JobStatus.COMPLETED)
        assert store.pending_or_retry() == [2]
        store.set_status(2, JobStatus.RETRY)
        assert store.pending_or_retry() == [2]
    finally:
        store.close()
