from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str | None
    base_url: str | None
    model: str | None


def get_provider_config(name: str) -> ProviderConfig:
    prefix = name.upper().replace("-", "_")
    return ProviderConfig(
        name=name,
        api_key=os.getenv(f"{prefix}_API_KEY"),
        base_url=os.getenv(f"{prefix}_BASE_URL"),
        model=os.getenv(f"{prefix}_MODEL"),
    )


def require_api_key(name: str) -> ProviderConfig:
    config = get_provider_config(name)
    if not config.api_key:
        raise RuntimeError(f"Missing {name.upper().replace('-', '_')}_API_KEY environment variable")
    return config
