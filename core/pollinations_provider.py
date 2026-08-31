from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .provider_config import require_api_key


class PollinationsProvider:
    """Pollinations adapter for authenticated image generation."""

    name = "pollinations"
    default_base_url = "https://gen.pollinations.ai"
    default_model = "flux"

    def __init__(self) -> None:
        config = require_api_key(self.name)
        self.api_key = config.api_key or ""
        self.base_url = (config.base_url or self.default_base_url).rstrip("/")
        self.model = config.model or os.getenv("POLLINATIONS_IMAGE_MODEL", self.default_model)
        self.timeout = float(os.getenv("POLLINATIONS_HTTP_TIMEOUT", "120"))

    def _request(self, url: str) -> tuple[bytes, str]:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "image/*,application/json",
                "User-Agent": "Mahabarath-Social-Automation/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read(), response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Pollinations HTTP {exc.code}: {detail[:1000]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Pollinations connection error: {exc.reason}") from exc

    def submit(self, job: dict[str, Any]) -> dict[str, Any]:
        if job.get("job_type") != "image":
            raise ValueError("PollinationsProvider currently supports image jobs only")
        plan = job.get("plan", {})
        prompt_key = job.get("prompt_key", "image_prompt")
        prompt = plan.get(prompt_key) or plan.get("prompt")
        if not prompt:
            raise ValueError(f"generation plan has no {prompt_key} for Pollinations")

        query = urllib.parse.urlencode({"model": self.model})
        url = f"{self.base_url}/image/{urllib.parse.quote(str(prompt), safe='')}?{query}"
        _, content_type = self._request(url)
        if not content_type.lower().startswith("image/"):
            raise RuntimeError(f"Pollinations returned unexpected content type: {content_type or 'unknown'}")
        return {
            "provider": self.name,
            "provider_job_id": f"pollinations-{abs(hash(url))}",
            "status": "completed",
            "asset_uri": url,
            "content_type": content_type,
        }

    def status(self, provider_job_id: str) -> dict[str, Any]:
        return {"provider": self.name, "provider_job_id": provider_job_id, "status": "completed"}
