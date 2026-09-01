from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import torch
from diffusers import StableDiffusionPipeline


class LocalProvider:
    """Local Stable Diffusion image provider for generation jobs."""

    name = "local"
    model_id = "runwayml/stable-diffusion-v1-5"

    def __init__(self, model_id: str | None = None):
        if not torch.cuda.is_available():
            raise RuntimeError("Local image generation requires a CUDA-capable GPU")

        self.model_id = model_id or self.model_id
        self.pipe = StableDiffusionPipeline.from_pretrained(
            self.model_id,
            dtype=torch.float16,
            safety_checker=None,
        )
        self.pipe.enable_attention_slicing()
        self.pipe.enable_model_cpu_offload()

    @staticmethod
    def _prompt_from_job(job: dict[str, Any]) -> str | None:
        plan = job.get("plan") or {}
        prompt = job.get("prompt")
        if prompt:
            return str(prompt)

        prompt_key = job.get("prompt_key")
        if prompt_key and plan.get(prompt_key):
            return str(plan[prompt_key])

        prompts = plan.get("prompts") or {}
        if prompt_key and prompts.get(prompt_key):
            return str(prompts[prompt_key])

        return str(plan["image_prompt"]) if plan.get("image_prompt") else None

    def submit(self, job: dict[str, Any]) -> dict[str, Any]:
        prompt = self._prompt_from_job(job)
        if not prompt:
            raise ValueError("Local image generation requires a generation-plan prompt")

        output_dir = Path(job.get("output_dir") or "data/generated")
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = job.get("output_filename") or f"local-{uuid.uuid4().hex}.png"
        output_path = output_dir / filename

        result = self.pipe(
            prompt,
            height=int(job.get("height", 512)),
            width=int(job.get("width", 512)),
            num_inference_steps=int(job.get("num_inference_steps", 20)),
            guidance_scale=float(job.get("guidance_scale", 7.0)),
        )
        result.images[0].save(output_path)

        return {
            "provider": self.name,
            "provider_job_id": f"local-{uuid.uuid4().hex}",
            "status": "completed",
            "asset_uri": str(output_path),
        }

    def status(self, provider_job_id: str) -> dict[str, Any]:
        return {
            "provider": self.name,
            "provider_job_id": provider_job_id,
            "status": "completed",
        }
