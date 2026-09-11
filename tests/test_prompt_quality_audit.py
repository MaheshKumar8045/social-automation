import json

from core.prompt_quality_audit import audit_package


def _plan():
    character = {
        "canonical_name": "Lord Shiva",
        "visual_profile": {
            "identity_anchor": "vib-7-shiva",
            "source_facts": [{"attribute": "build", "value": "slender"}],
            "inferred_facts": [{"attribute": "garment", "value": "source-compatible traditional attire"}],
        },
    }
    return {
        "world_profile": {
            "method": "weighted_deterministic_source_signal_analysis",
            "llm_used": False,
            "dimensions": {
                "narrative_type": {"top": {"label": "mythology", "score": 8}},
                "culture": {"top": {"label": "indic", "score": 7}},
                "religious_context": {"top": {"label": "hindu", "score": 8}},
            },
        },
        "visual_inference": {"enabled": True, "genre": "mythology", "characters": [character]},
        "characters": [character],
        "image_prompt": "Source-grounded mythology media depiction. DETECTED STORY WORLD: mythology; culture: indic. PRIMARY SOURCE VISUAL MOMENT: Lord Shiva walks toward the gate. 9:16.",
        "media_prompt_package": {"visual_inference": {"enabled": True, "characters": [character]}, "image": {"prompt": "x", "visual_inference": {"enabled": True}}},
    }


def test_audit_passes_world_context_and_provenance():
    package = {"qa_passed": True, "qa_failures": [], "scenes": [{"qa_status": "pass", "scene_id": 1, "scene_order": 1, "title": "The Gate", "page_start": 1, "page_end": 1, "plan": _plan()}]}
    path = __import__("pathlib").Path(__file__).with_name("_audit_package.json")
    path.write_text(json.dumps(package), encoding="utf-8")
    try:
        result = audit_package(path)
    finally:
        path.unlink()
    assert result["embedded_qa_passed"] is True
    assert result["audit_failed_scenes"] == 0
    assert result["sample_scenes"][0]["narrative_type"]["label"] == "mythology"


def test_audit_flags_missing_world_context_in_prompt(tmp_path):
    package = {"qa_passed": True, "qa_failures": [], "scenes": [{"qa_status": "pass", "scene_id": 1, "scene_order": 1, "title": "The Gate", "page_start": 1, "page_end": 1, "plan": {**_plan(), "image_prompt": "Source-grounded scene. PRIMARY SOURCE VISUAL MOMENT: Lord Shiva walks toward the gate. 9:16."}}]}
    path = tmp_path / "package.json"
    path.write_text(json.dumps(package), encoding="utf-8")
    result = audit_package(path)
    assert result["audit_failed_scenes"] == 1
    assert "missing_world_context_in_prompt" in result["audit_failure_details"][0]["issues"]
