from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path("config/generation_providers.json")


def load_provider_config(path: str | Path | None = None) -> dict[str, Any]:
    configured = path or os.getenv("GENERATION_PROVIDER_CONFIG") or DEFAULT_CONFIG
    p = Path(configured)
    if not p.exists():
        return {"providers": {}, "routing": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def choose_provider(media_type: str, config: dict[str, Any] | None = None) -> str:
    config = config or load_provider_config()
    routes = config.get("routing", {}).get(media_type, [])
    providers = config.get("providers", {})
    candidates = []
    for name in routes:
        spec = providers.get(name, {})
        if not spec.get("enabled", True):
            continue
        capabilities = spec.get("media_types", [])
        if media_type not in capabilities:
            continue
        candidates.append((float(spec.get("priority", 100)), name))
    if not candidates:
        raise RuntimeError(f"No enabled provider configured for media type '{media_type}'")
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][1]
