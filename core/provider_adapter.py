from __future__ import annotations

import importlib
import os
from typing import Any, Protocol

from .provider_config import ProviderConfig, get_provider_config


class GenerationProvider(Protocol):
    """Provider contract shared by image, video, audio, and other media jobs."""
    name: str
    def submit(self, job: dict[str, Any]) -> dict[str, Any]: ...
    def status(self, provider_job_id: str) -> dict[str, Any]: ...


class MockProvider:
    name = "mock"
    def submit(self, job: dict[str, Any]) -> dict[str, Any]:
        import uuid
        return {"provider": self.name, "provider_job_id": f"mock-{uuid.uuid4().hex}", "status": "completed", "asset_uri": None}
    def status(self, provider_job_id: str) -> dict[str, Any]:
        return {"provider": self.name, "provider_job_id": provider_job_id, "status": "completed", "asset_uri": None}


class ConfiguredProvider:
    """Load any concrete adapter using GENERATION_PROVIDER_<NAME>_ADAPTER=module:ClassName."""
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name
        self._adapter = self._load_adapter(config.name)

    @staticmethod
    def _load_adapter(name: str) -> GenerationProvider:
        prefix = name.upper().replace("-", "_")
        spec = os.getenv(f"GENERATION_PROVIDER_{prefix}_ADAPTER")
        if not spec or ":" not in spec:
            raise NotImplementedError(
                f"No concrete adapter registered for provider '{name}'. "
                f"Set GENERATION_PROVIDER_{prefix}_ADAPTER=module:ClassName"
            )
        module_name, class_name = spec.split(":", 1)
        module = importlib.import_module(module_name)
        adapter_class = getattr(module, class_name)
        adapter = adapter_class()
        if not hasattr(adapter, "submit") or not hasattr(adapter, "status"):
            raise TypeError(f"Adapter '{spec}' must implement submit() and status()")
        return adapter

    def submit(self, job: dict[str, Any]) -> dict[str, Any]:
        return self._adapter.submit(job)
    def status(self, provider_job_id: str) -> dict[str, Any]) -> dict[str, Any]:
        return self._adapter.status(provider_job_id)


def get_provider(name: str) -> GenerationProvider:
    if name == "mock":
        return MockProvider()
    return ConfiguredProvider(get_provider_config(name))
