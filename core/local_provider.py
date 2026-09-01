from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import torch
from diffusers import StableDiffusionPipeline


class LocalProvider:
    """Local Stable Diffusion image provider for the project's generation jobs."""

    name = "local"
    model_id = "runwayml/stable-diffusion-v1-5"

    # Instagram-friendly portrait composition. The final delivery layer can
    # upscale this 4:5 master to 1080x1350 without changing the composition.
    default_width = 512
    default_height = 640

    default_negative_prompt = (
        "illustration, painting, watercolor, drawing, sketch, engraving, "
        "cartoon, anime, comic, poster, low detail, distorted anatomy, "
        "extra limbs, duplicate people, deformed hands, text, watermark"
    )

    def __init__(self, model_id: str | None = None):
        if not torch.cuda.is_available():
            raise RuntimeError("Local image generation requires a CUDA-capable GPU")

        self.model_id = model_id or self.model_id
        self.pipe = StableDiffusionPipeline.from_pretrained(
            self.model_id,
            torch_dtype=torch.float32,
            safety_checker=None,
        )
        self.pipe.enable_attention_slicing()
        self.pipe.enable_model_cpu_offload()

    @staticmethod
    def _prompt_from_plan(job: dict[str, Any]) -> str:
        plan = job.get("plan") or {}
        prompt_key = job.get("prompt_key") or "image_prompt"
        prompt = plan.get(prompt_key)
        if not prompt:
            prompt = job.get("prompt")
        if not prompt:
            raise ValueError("Local image generation requires a generation-plan image prompt")
        return str(prompt)

    def submit(self, job: dict[str, Any]) -> dict[str, Any]:
        prompt = self._prompt_from_plan(job)
        negative_prompt = str(job.get("negative_prompt") or self.default_negative_prompt)

        output_dir = Path(job.get("output_dir") or "data/generated")
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = job.get("output_filename") or f"local-{uuid.uuid4().hex}.png"
        output_path = output_dir / filename

        width = int(job.get("width", self.default_width))
        height = int(job.get("height", self.default_height))

        generator = None
        seed = job.get("seed")
        if seed is not None:
            generator = torch.Generator(device="cpu").manual_seed(int(seed))

        result = self.pipe(
            prompt,
            negative_prompt=negative_prompt,
            height=height,
            width=width,
            num_inference_steps=int(job.get("num_inference_steps", 20)),
            guidance_scale=float(job.get("guidance_scale", 7.0)),
            generator=generator,
        )
        image = result.images[0]

        # Refuse to publish clearly invalid output such as an all-black/all-zero frame.
        extrema = image.convert("L").getextrema()
        if extrema[0] == 0 and extrema[1] == 0:
            raise RuntimeError("Local image generation produced a fully black image")
        if extrema[0] == 255 and extrema[1] == 255:
            raise RuntimeError("Local image generation produced a fully white image")

        image.save(output_path)

        return {
            "provider": self.name,
            "provider_job_id": f"local-{uuid.uuid4().hex}",
            "status": "completed",
            "asset_uri": str(output_path),
            "generation": {
                "model": self.model_id,
                "width": width,
                "height": height,
                "aspect_ratio": f"{width}:{height}",
                "steps": int(job.get("num_inference_steps", 20)),
                "guidance_scale": float(job.get("guidance_scale", 7.0)),
                "seed": seed,
            },
        }

    def status(self, provider_job_id: str) -> dict[str, Any]:
        return {
            "provider": self.name,
            "provider_job_id": provider_job_id,
            "status": "completed",
        }
