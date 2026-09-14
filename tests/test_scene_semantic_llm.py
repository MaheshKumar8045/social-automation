from core.llm_schemas import SceneSemanticAnalysis
from core.scene_semantic_llm import _validate_analysis, build_scene_prompt


class _FakeClient:
    def __init__(self, model="qwen3:30b"):
        self.settings = type("Settings", (), {"model": model})()


def _analysis(**overrides):
    data = {
        "summary": "A character reflects on a capture while observing a ruined city.",
        "primary_visual_moment": {
            "text": "Lord Shiva watched the dying embers of the city.",
            "evidence": "Lord Shiva watched the dying embers of the city.",
            "priority": "primary",
        },
        "characters": [
            {
                "name": "Lord Shiva",
                "scene_role": "visible",
                "physical_presence": True,
                "evidence": "Lord Shiva watched the dying embers of the city.",
                "reason": "direct physical action",
            }
        ],
        "dialogue": [],
        "environment": [],
        "objects": [],
        "source_facts": [],
        "inferences": [],
    }
    data.update(overrides)
    return SceneSemanticAnalysis.model_validate(data)


def test_valid_source_evidence_is_accepted():
    source = "Lord Shiva watched the dying embers of the city."
    result = _validate_analysis(
        _analysis(),
        source_text=source,
        known_character_names={"Lord Shiva"},
        model="qwen3:30b",
    )
    assert result.status == "ready"
    assert result.source_validated is True
    assert result.llm_used is True


def test_hallucinated_primary_moment_is_rejected():
    analysis = _analysis(
        primary_visual_moment={
            "text": "Lord Shiva raised a sword.",
            "evidence": "Lord Shiva raised a sword.",
            "priority": "primary",
        }
    )
    result = _validate_analysis(
        analysis,
        source_text="Lord Shiva watched the dying embers of the city.",
        known_character_names={"Lord Shiva"},
        model="qwen3:30b",
    )
    assert result.status == "rejected"
    assert "primary_visual_moment_evidence_not_in_source" in result.rejected_reasons


def test_hallucinated_dialogue_is_rejected():
    analysis = _analysis(
        dialogue=[
            {
                "speaker": "Lord Shiva",
                "text": "I will destroy the city.",
                "evidence": "I will destroy the city.",
            }
        ]
    )
    result = _validate_analysis(
        analysis,
        source_text="Lord Shiva watched the dying embers of the city.",
        known_character_names={"Lord Shiva"},
        model="qwen3:30b",
    )
    assert result.status == "rejected"
    assert "dialogue_not_verbatim_source" in result.rejected_reasons


def test_prompt_requires_exact_source_evidence():
    prompt = build_scene_prompt(
        source_text="Kumbha was captured by my son.",
        characters=[{"canonical_name": "Kumbha"}],
        events=[{"text": "Kumbha was captured by my son."}],
        world_profile={"dimensions": {}},
    )
    assert "Evidence fields must be exact substrings of SOURCE SCENE" in prompt
    assert "Kumbha was captured by my son." in prompt
