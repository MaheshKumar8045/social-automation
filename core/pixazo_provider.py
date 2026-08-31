from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from .provider_config import require_api_key


class PixazoProvider:
    """Pixazo adapter with environment-configurable endpoints/models."""

    name = "pixazo"
    default_base_url = "https://gateway.pixazo.ai"
    default_endpoints = {
        "image": "/flux/text-to-image",
        "video": "/ltx/text-to-video",
        "audio": "/tracks/generate-music",
    }

    def __init__(self) -> None:
        config = require_api_key(self.name)
        self.api_key = config.api_key
        self.base_url = (config.base_url or self.default_base_url).rstrip("/")
        self.timeout = float(os.getenv("PIXAZO_HTTP_TIMEOUT", "60"))
        self.poll_seconds = float(os.getenv("PIXAZO_POLL_SECONDS", "5"))
        self.max_poll_seconds = float(os.getenv("PIXAZO_MAX_POLL_SECONDS", "900"))

    def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": self.api_key or "",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Pixazo HTTP {exc.code}: {detail[:1000]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Pixazo connection error: {exc.reason}") from exc

    @staticmethod
    def _extract_url(data: dict[str, Any]) -> str | None:
        for key in ("output_url", "media_url", "url", "image_url", "video_url", "audio_url"):
            value = data.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        output = data.get("output")
        if isinstance(output, dict):
            return PixazoProvider._extract_url(output)
        if isinstance(output, list):
            for item in output:
                if isinstance(item, dict):
                    found = PixazoProvider._extract_url(item)
                    if found:
                        return found
                elif isinstance(item, str) and item.startswith(("http://", "https://")):
                    return item
        return None

    def submit(self, job: dict[str, Any]) -> dict[str, Any]:
        media_type = job["job_type"]
        endpoint = os.getenv(
            f"PIXAZO_{media_type.upper()}_ENDPOINT",
            self.default_endpoints[media_type],
        )
        plan = job.get("plan", {})
        prompt_key = job.get("prompt_key")
        prompt = plan.get(prompt_key) or plan.get("prompt")
        if not prompt:
            raise ValueError(f"generation plan has no {prompt_key} for Pixazo")

        payload: dict[str, Any] = {"prompt": prompt}
        model = os.getenv(f"PIXAZO_{media_type.upper()}_MODEL")
        if model:
            payload["model"] = model
        response = self._request("POST", self.base_url + endpoint, payload)
        request_id = response.get("request_id") or response.get("job_id")
        asset_uri = self._extract_url(response)
        if asset_uri:
            return {"provider": self.name, "provider_job_id": request_id or asset_uri, "status": "completed", "asset_uri": asset_uri, "raw": response}
        if request_id:
            return {"provider": self.name, "provider_job_id": request_id, "status": "submitted", "asset_uri": None, "raw": response}
        raise RuntimeError(f"Pixazo response contained neither media URL nor request id: {response}")

    def status(self, provider_job_id: str) -> dict[str, Any]:
        template = os.getenv("PIXAZO_STATUS_ENDPOINT", "/v2/requests/status/{request_id}")
        url = self.base_url + template.format(request_id=provider_job_id)
        started = time.monotonic()
        while True:
            response = self._request("GET", url)
            status = str(response.get("status", "")).upper()
            asset_uri = self._extract_url(response)
            if status in {"COMPLETED", "SUCCEEDED", "SUCCESS", "DONE"} or asset_uri:
                return {"provider": self.name, "provider_job_id": provider_job_id, "status": "completed", "asset_uri": asset_uri, "raw": response}
            if status in {"FAILED", "ERROR", "CANCELLED", "CANCELED"}:
                raise RuntimeError(f"Pixazo generation failed: {response}")
            if time.monotonic() - started >= self.max_poll_seconds:
                return {"provider": self.name, "provider_job_id": provider_job_id, "status": "submitted", "asset_uri": None, "raw": response}
            time.sleep(self.poll_seconds)
