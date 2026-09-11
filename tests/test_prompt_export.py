from core.prompt_export import validate_plan


def _valid_plan():
    return {
        "plan_status": "ready",
        "source_grounded": True,
        "unknowns_must_remain_unknown": True,
        "image_prompt": "Source-grounded cinematic image of Lord Shiva in the established scene, preserving only supplied visual facts and continuity, with realistic composition, physically plausible lighting, clear subject separation, and no invented appearance or story details.",
        "characters": [{
            "canonical_name": "Lord Shiva",
            "visual_profile": {
                "identity_anchor": "vib-test-shiva",
                "source_facts": [],
                "inferred_facts": [{
                    "attribute": "visual_style",
                    "value": "dignified cinematic presentation",
                    "basis": "genre_prior",
                }],
            },
        }],
        "short_video_prompt_package": {
            "clip_count": 1,
            "clips": [{
                "clip_number": 1,
                "prompt": "Source-grounded short-video clip showing the supplied action with restrained camera movement and no invented story events, while preserving character identity, environment, continuity, and unknown visual attributes.",
            }],
        },
        "long_video_prompt_package": {
            "shots": [{
                "shot_number": 1,
                "prompt": "Source-grounded long-video shot preserving the established subject, setting, action, continuity, and unknown appearance details, with coherent spatial progression and no unsupported narrative additions.",
            }],
        },
        "audio_prompt": {
            "music_direction": ["Use restrained cinematic instrumental music supporting the source-derived emotional tone."],
            "sound_design": "Use only source-compatible environmental and action sounds; do not invent events.",
        },
        "media_prompt_package": {
            "source_grounded": True,
            "unknowns_must_remain_unknown": True,
            "image": {},
            "short_video": {},
            "long_video": {},
        },
        "source_evidence": [],
    }


def test_validate_plan_accepts_complete_media_package():
    assert validate_plan(_valid_plan()) == []


def test_validate_plan_rejects_missing_nested_media_content():
    plan = _valid_plan()
    plan["short_video_prompt_package"]["clips"] = []
    plan["long_video_prompt_package"]["shots"] = []
    plan["audio_prompt"]["music_direction"] = []
    errors = validate_plan(plan)
    assert "short-video clips are missing" in errors
    assert "long-video shots are missing" in errors
    assert "audio/music direction is missing or too short" in errors


def test_validate_plan_rejects_character_loss_between_plan_and_image_prompt():
    plan = _valid_plan()
    plan["image_prompt"] = "Source-grounded cinematic image of the established scene with no invented visual facts or continuity changes."
    errors = validate_plan(plan)
    assert "image prompt does not contain any canonical character from the generation plan" in errors
