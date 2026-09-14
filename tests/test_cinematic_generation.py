

def test_audio_dialogue_source_matches_rendered_voice_text():
    result = enhance_generation_package(media=_media(), **_context('Ravana said, "We must fight."'))
    audio = result["short_video"]["audio"]
    rendered = [c["dialogue"] for c in result["short_video"]["clips"] if c["dialogue"]]
    assert audio["dialogue_source"] == rendered
    assert audio["dialogue_mode"] == "spoken dialogue; use exact source wording and only source-established speaker identity"


def test_generation_intent_is_exported_as_shared_source_of_truth():
    result = enhance_generation_package(media=_media(), **_context("The warriors crossed the ruined gate."))
    intent = result["generation_intent"]
    assert intent["schema_version"] == 2
    assert result["image"]["source_visual_moments"] == intent["visual_moment_candidates"]
    assert result["short_video"]["source_visual_moments"] == intent["visual_moment_candidates"]
    assert result["long_video"]["source_visual_moments"] == intent["visual_moment_candidates"]


def test_video_prompts_receive_scene_specific_cinematic_direction():
    result = enhance_generation_package(media=_media(), **_context("The warriors crossed the ruined gate."))
    assert all("CINEMATIC DIRECTION" in c["prompt"] for c in result["short_video"]["clips"])
    assert all("CINEMATIC DIRECTION" in s["prompt"] for s in result["long_video"]["shots"])
