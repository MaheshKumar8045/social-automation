from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from core.provider_config import require_api_key


@dataclass(frozen=True)
class OpenAIImageResult:
    """Result returned by the OpenAI image generation adapter."""

    asset_uri: str
    provider_job_id: str | None = None
    raw: Any = None


class OpenAIProvider:
    """OpenAI image-generation adapter used by the generation job runner."""

    name = "openai"
    default_base_url = "https://api.openai.com/v1"

    def __init__(self, model: str | None = None, base_url: str | None = None):
        config = require_api_key(self.name)
        self.api_key = config.api_key
        self.base_url = (base_url or config.base_url or self.default_base_url).rstrip("/")
        self.model = model or config.model or "gpt-image-1"

    def submit(self, request: dict[str, Any]) -> OpenAIImageResult:
        """Generate an image and persist the returned base64 image locally."""
        prompt = request.get("prompt") or request.get("text")
        if not prompt:
            raise ValueError("OpenAI image generation requires a non-empty prompt")

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
        }
        for key in ("size", "quality", "background", "moderation"):
            if request.get(key) is not None:
                payload[key] = request[key]

        response = requests.post(
            f"{self.base_url}/images/generations",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()

        items = data.get("data") or []
        if not items:
            raise RuntimeError("OpenAI returned no generated image")

        item = items[0]
        image_b64 = item.get("b64_json")
        image_url = item.get("url")

        output_dir = Path(request.get("output_dir") or "data/generated")
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = request.get("output_filename") or "openai_image.png"
        output_path = output_dir / filename

        if image_b64:
            output_path.write_bytes(base64.b64decode(image_b64))
        elif image_url:
            image_response = requests.get(image_url, timeout=180)
            image_response.raise_for_status()
            output_path.write_bytes(image_response.content)
        else:
            raise RuntimeError("OpenAI response contained neither b64_json nor url")

        return OpenAIImageResult(
            asset_uri=str(output_path),
            provider_job_id=data.get("id"),
            raw=data,
        )

    def status(self, provider_job_id: str) -> dict[str, Any]:
        """Image generations are synchronous through this adapter."""
        return {"provider_job_id": provider_job_id, "status": "completed"}
