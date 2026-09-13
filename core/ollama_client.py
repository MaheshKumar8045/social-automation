from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .llm_schemas import SceneSemanticAnalysis


@dataclass(frozen=True)
class OllamaSettings:
    host: str = "http://localhost:11434"
    model: str = "qwen3:30b"
    timeout_seconds: float = 1800.0
    think: bool = False

    @classmethod
    def from_env(cls) -> "OllamaSettings":
        raw_timeout = os.getenv("SOCIAL_AUTOMATION_LLM_TIMEOUT", str(cls.timeout_seconds)).strip()
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise ValueError("SOCIAL_AUTOMATION_LLM_TIMEOUT must be a number of seconds") from exc
        if timeout <= 0:
            raise ValueError("SOCIAL_AUTOMATION_LLM_TIMEOUT must be greater than zero")
        raw_think = os.getenv("SOCIAL_AUTOMATION_LLM_THINK", "false").strip().lower()
        if raw_think not in {"0", "1", "false", "true", "no", "yes"}:
            raise ValueError("SOCIAL_AUTOMATION_LLM_THINK must be true or false")
        return cls(
            host=os.getenv("SOCIAL_AUTOMATION_LLM_HOST", cls.host).rstrip("/"),
            model=os.getenv("SOCIAL_AUTOMATION_LLM_MODEL", cls.model).strip() or cls.model,
            timeout_seconds=timeout,
            think=raw_think in {"1", "true", "yes"},
        )


class OllamaUnavailable(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, settings: OllamaSettings | None = None) -> None:
        self.settings = settings or OllamaSettings.from_env()
        try:
            from ollama import Client
        except ImportError as exc:
            raise OllamaUnavailable("Python package 'ollama' is not installed") from exc
        self._client = Client(host=self.settings.host, timeout=self.settings.timeout_seconds)

    def health(self) -> dict[str, Any]:
        try:
            return self._client.list()
        except Exception as exc:
            raise OllamaUnavailable(f"Ollama is unreachable at {self.settings.host}: {exc}") from exc

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
            raise OllamaUnavailable(f"Model '{requested}' is not installed. Available local models: {', '.join(names) or '(none)'}")

    def analyze_scene(self, *, system_prompt: str, user_prompt: str) -> SceneSemanticAnalysis:
        self.assert_model_available()
        try:
            response = self._client.chat(
                model=self.settings.model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                format=SceneSemanticAnalysis.model_json_schema(),
                options={"temperature": 0},
                think=self.settings.think,
                stream=False,
            )
        except Exception as exc:
            detail = str(exc)
            if "timed out" in detail.lower() or "timeout" in detail.lower():
                detail = f"timed out after {self.settings.timeout_seconds:g}s"
            raise OllamaUnavailable(f"Ollama inference failed: {detail}") from exc

        content = response.message.content if hasattr(response, "message") else response["message"]["content"]
        try:
            return SceneSemanticAnalysis.model_validate_json(content)
        except Exception as exc:
            raise OllamaUnavailable(f"Ollama returned invalid semantic JSON: {exc}") from exc
