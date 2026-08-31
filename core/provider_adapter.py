from __future__ import annotations

from typing import Any, Protocol


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


def get_provider(name: str) -> GenerationProvider:
    if name == "mock":
        return MockProvider()
    raise ValueError(f"Unknown generation provider: {name}")
