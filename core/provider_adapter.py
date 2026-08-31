from __future__ import annotations

from typing import Any, Protocol

from .provider_config import ProviderConfig, get_provider_config


class GenerationProvider(Protocol):
    """Common contract for image/video generation providers."""
    name: str

    def submit(self, job: dict[str, Any]) -> dict[str, Any]: ...

    def status(self, provider_job_id: str) -> dict[str, Any]: ...


class MockProvider:
    """Deterministic local provider for integration tests; creates no asset."""

    name = "mock"

    def submit(self, job: dict[str, Any]) -> dict[str, Any]:
        import uuid
        return {
            "provider": self.name,
            "provider_job_id": f"mock-{uuid.uuid4().hex}",
            "status": "completed",
            "asset_uri": None,
        }

    def status(self, provider_job_id: str) -> dict[str, Any]:
        return {
            "provider": self.name,
            "provider_job_id": provider_job_id,
            "status": "completed",
            "asset_uri": None,
        }


class ConfiguredProvider:
    """Explicit placeholder for a future real provider adapter.

    It intentionally refuses execution until a concrete adapter is installed;
    this prevents accidentally treating an API configuration as a working
    provider.
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name

    def submit(self, job: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"No concrete adapter registered for provider '{self.name}'")

    def status(self, provider_job_id: str) -> dict[str, Any]:
        raise NotImplementedError(f"No concrete adapter registered for provider '{self.name}'")


def get_provider(name: str) -> GenerationProvider:
    if name == "mock":
        return MockProvider()
    return ConfiguredProvider(get_provider_config(name))
