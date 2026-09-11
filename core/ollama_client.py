from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .llm_schemas import SceneSemanticAnalysis


@dataclass(frozen=True)
class OllamaSettings:
    host: str = "http://localhost:11434"
    model: str = "qwen3:30b"
    timeout_seconds: float = 300.0

    @classmethod
    def from_env(cls) -> "OllamaSettings":
        return cls(
            host=os.getenv("SOCIAL_AUTOMATION_LLM_HOST", cls.host).rstrip("/"),
            model=os.getenv("SOCIAL_AUTOMATION_LLM_MODEL", cls.model),
            timeout_seconds=float(os.getenv("SOCIAL_AUTOMATION_LLM_TIMEOUT", cls.timeout_seconds)),
        )


class OllamaUnavailable(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, settings: OllamaSettings | None = None) -> None:
        self.settings = settings or OllamaSettings.from_env()
        try:
            from ollama import Client
        except ImportError as exc:  # pragma: no cover - exercised only without optional dependency
            raise OllamaUnavailable("Python package 'ollama' is not installed") from exc
        self._client = Client(host=self.settings.host, timeout=self.settings.timeout_seconds)

    def health(self) -> dict[str, Any]:
        try:
            return self._client.list()
        except Exception as exc:  # pragma: no cover - depends on local service
            raise OllamaUnavailable(
                f"Ollama is unreachable at {self.settings.host}: {exc}"
            ) from exc

    def models(self) -> list[str]:
        response = self.health()
        models = response.get("models", []) if isinstance(response, dict) else getattr(response, "models", [])
        result: list[str] = []
        for model in models:
            name = model.get("name") if isinstance(model, dict) else getattr(model, "model", None)
            if name:
                result.append(str(name))
        return result

    def assert_model_available(self) -> None:
        names = self.models()
        requested = self.settings.model
        if requested not in names:
            raise OllamaUnavailable(
                f"Model '{requested}' is not installed. Available local models: {', '.join(names) or '(none)'}"
            )

    def analyze_scene(self, *, system_prompt: str, user_prompt: str) -> SceneSemanticAnalysis:
        self.assert_model_available()
        try:
            response = self._client.chat(
                model=self.settings.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                format=SceneSemanticAnalysis.model_json_schema(),
                options={"temperature": 0},
                stream=False,
            )
        except Exception as exc:  # pragma: no cover - depends on local service/model
            raise OllamaUnavailable(f"Ollama inference failed: {exc}") from exc

        content = response.message.content if hasattr(response, "message") else response["message"]["content"]
        try:
            return SceneSemanticAnalysis.model_validate_json(content)
        except Exception as exc:
            raise OllamaUnavailable(f"Ollama returned invalid semantic JSON: {exc}") from exc
