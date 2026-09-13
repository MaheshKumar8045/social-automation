import pytest

import core.generation_planner as planner_module
from core.generation_planner import _extend_truncated_source_fragment
from core.llm_schemas import SceneSemanticAnalysis, SceneSemanticResult
from core.ollama_client import OllamaSettings


def _ready_result():
    analysis = SceneSemanticAnalysis.model_validate({
        "summary": "A source-grounded moment.",
        "primary_visual_moment": {"text": "Ravana lay wounded.", "evidence": "Ravana lay wounded.", "priority": "primary"},
        "characters": [], "dialogue": [], "environment": [], "objects": [], "source_facts": [], "inferences": [],
    })
    return SceneSemanticResult(status="ready", model="qwen3:30b", llm_used=True, source_validated=True, analysis=analysis, rejected_reasons=[])


def test_shadow_mode_never_applies_llm_mutation(monkeypatch):
    monkeypatch.setattr(planner_module, "llm_mode", lambda: "shadow")
    original = {
        "image": {"prompt": "source-grounded prompt with dialogue", "dialogue_overlays": [], "layout": {}},
        "short_video": {"clips": []}, "long_video": {"shots": []}, "visual_inference": {},
    }
    assert "LLM-VALIDATED" not in original["image"]["prompt"]
    assert planner_module.llm_mode() == "shadow"


def test_truncated_source_fragment_extends_to_sentence_boundary():
    source = "The enemy celebrated. My temples will be looted; the granaries torched and schools burnt. The jackals came."
    fragment = "The enemy celebrated. My temples will be looted; the granaries torched and schools"
    repaired = _extend_truncated_source_fragment(fragment, source)
    assert repaired == "The enemy celebrated. My temples will be looted; the granaries torched and schools burnt."
    assert repaired.endswith(".")


def test_complete_visual_fragment_is_unchanged():
    source = "Ravana lay wounded. The jackals came."
    assert _extend_truncated_source_fragment("Ravana lay wounded.", source) == "Ravana lay wounded."


def test_default_ollama_timeout_is_thirty_minutes(monkeypatch):
    monkeypatch.delenv("SOCIAL_AUTOMATION_LLM_TIMEOUT", raising=False)
    assert OllamaSettings.from_env().timeout_seconds == 1800.0


def test_default_qwen_thinking_is_disabled_for_semantic_extraction(monkeypatch):
    monkeypatch.delenv("SOCIAL_AUTOMATION_LLM_THINK", raising=False)
    assert OllamaSettings.from_env().think is False


def test_ollama_timeout_can_be_overridden(monkeypatch):
    monkeypatch.setenv("SOCIAL_AUTOMATION_LLM_TIMEOUT", "2400")
    assert OllamaSettings.from_env().timeout_seconds == 2400.0


def test_ollama_thinking_can_be_enabled(monkeypatch):
    monkeypatch.setenv("SOCIAL_AUTOMATION_LLM_THINK", "true")
    assert OllamaSettings.from_env().think is True


def test_default_context_is_4096(monkeypatch):
    monkeypatch.delenv("SOCIAL_AUTOMATION_LLM_CONTEXT", raising=False)
    assert OllamaSettings.from_env().context_tokens == 4096


def test_ollama_context_can_be_overridden(monkeypatch):
    monkeypatch.setenv("SOCIAL_AUTOMATION_LLM_CONTEXT", "8192")
    assert OllamaSettings.from_env().context_tokens == 8192


def test_invalid_ollama_timeout_fails_fast(monkeypatch):
    monkeypatch.setenv("SOCIAL_AUTOMATION_LLM_TIMEOUT", "0")
    with pytest.raises(ValueError, match="greater than zero"):
        OllamaSettings.from_env()


def test_invalid_ollama_thinking_fails_fast(monkeypatch):
    monkeypatch.setenv("SOCIAL_AUTOMATION_LLM_THINK", "maybe")
    with pytest.raises(ValueError, match="boolean"):
        OllamaSettings.from_env()


def test_invalid_ollama_context_fails_fast(monkeypatch):
    monkeypatch.setenv("SOCIAL_AUTOMATION_LLM_CONTEXT", "512")
    with pytest.raises(ValueError, match="at least 1024"):
        OllamaSettings.from_env()
