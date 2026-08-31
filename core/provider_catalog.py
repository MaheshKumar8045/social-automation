from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path("config/generation_providers.json")


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path or os.getenv("GENERATION_PROVIDER_CONFIG", DEFAULT_CONFIG))
    if not config_path.exists():
        return {"providers": {}, "routing": {}}
    return json.loads(config_path.read_text(encoding="utf-8"))


def enabled_providers(media_type: str, path: str | Path | None = None) -> list[dict[str, Any]]:
    catalog = load_catalog(path)
    providers = catalog.get("providers", {})
    ordered = catalog.get("routing", {}).get(media_type, [])
    result: list[dict[str, Any]] = []
    for index, name in enumerate(ordered):
        item = providers.get(name, {})
        if not item.get("enabled", False) or media_type not in item.get("media_types", []):
            continue
        result.append({"name": name, "priority": item.get("priority", 100), "routing_index": index, **item})
    return sorted(result, key=lambda x: (x.get("priority", 100), x.get("routing_index", 0)))


def provider_env_name(provider: str) -> str:
    return "GENERATION_PROVIDER_" + "_".join(c if c.isalnum() else "_" for c in provider.upper())
