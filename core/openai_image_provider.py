from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from .provider_config import require_api_key


class OpenAIImageProvider:
    """OpenAI Images API adapter using only the Python standard library."""

    name = "openai"

    def __init__(self) -> None:
        config = require_api_key(self.name)
        self.api_key = config.api_key
        self.base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = config.model or "gpt-image-2"

    @staticmethod
    def _prompt(job: dict[str, Any]) -> str:
        plan = job.get("plan") or {}
        scene = plan.get("scene") or {}
        characters = plan.get("characters") or []
        objects = plan.get("objects") or []
        events = plan.get("events") or []
        constraints = plan.get("visual_constraints") or []

        parts = [
            "Create a cinematic story-frame image grounded strictly in the supplied source plan.",
            f"Scene {plan.get('scene_id')}.",
            f"Scene context: {json.dumps(scene, ensure_ascii=False)}",
        ]
        if characters:
            parts.append("Characters: " + json.dumps(characters, ensure_ascii=False))
        if objects:
            parts.append("Objects: " + json.dumps(objects, ensure_ascii=False))
        if events:
            parts.append("Events: " + json.dumps(events, ensure_ascii=False))
        parts.append("Visual constraints: " + json.dumps(constraints, ensure_ascii=False))
        parts.append("Do not invent unspecified character appearance, clothing, age, facial features, setting details, or props.")
        return "\n\n".join(parts)

    def submit(self, job: dict[str, Any]) -> dict[str, Any]:
        if job.get("job_type") != "image":
            raise ValueError("OpenAIImageProvider only supports image jobs")
        prompt = self._prompt(job)
        body = {
            "model": self.model,
            "prompt": prompt,
            "size": os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
            "quality": os.getenv("OPENAI_IMAGE_QUALITY", "auto"),
            "output_format": os.getenv("OPENAI_IMAGE_OUTPUT_FORMAT", "png"),
        }
        request = urllib.request.Request(
            f"{self.base_url}/images/generations",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI image API returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI image API request failed: {exc.reason}") from exc

        data = payload.get("data") or []
        if not data:
            raise RuntimeError("OpenAI image API returned no image data")
        item = data[0]
        b64 = item.get("b64_json")
        if not b64:
            raise RuntimeError("OpenAI image API response did not contain b64_json")

        out_dir = Path(os.getenv("GENERATION_ASSET_DIR", "data/generated_assets"))
        out_dir.mkdir(parents=True, exist_ok=True)
        asset_name = f"scene_{job.get('scene_id')}_{uuid.uuid4().hex}.png"
        asset_path = out_dir / asset_name
        asset_path.write_bytes(base64.b64decode(b64))

        return {
            "provider": self.name,
            "provider_job_id": payload.get("id") or f"openai-{uuid.uuid4().hex}",
            "status": "completed",
            "asset_uri": str(asset_path),
            "model": self.model,
            "output_format": body["output_format"],
            "size": body["size"],
        }

    def status(self, provider_job_id: str) -> dict[str, Any]:
        # Images generation is returned as a completed response by this adapter.
        return {"provider": self.name, "provider_job_id": provider_job_id, "status": "completed"}
