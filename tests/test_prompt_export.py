from core.prompt_export import validate_plan


def _valid_plan():
    image_prompt = (
        "Source-grounded cinematic image of Lord Shiva in the established scene, "
        "mobile-first vertical 9:16 composition, preserving only supplied visual facts and continuity, "
        "with realistic composition, physically plausible lighting, clear subject separation, and no invented "
        "appearance or story details. Include one required dialogue-or-narrative box in protected negative space "
        "away from faces, hands, important objects, and primary action."
    )
    image_layout = {
        "aspect_ratio": "9:16",
        "orientation": "vertical",
        "mobile_first": True,
        "safe_margin_percent": 7,
        "critical_subject_safe_area_percent": 86,
        "background_visible_percent": [35, 55],
        "main_subject_height_percent": [45, 65],
        "dialogue_box_max_width_percent": 68,
        "dialogue_box_max_height_percent": 15,
        "dialogue_box_min_count": 1,
    }
    image_overlays = [{
        "text": "Source-grounded scene title",
        "purpose": "required narrative box when no source dialogue is available",
        "placement": "largest protected negative-space region opposite the primary subject, away from faces, hands, important objects, and primary action",
        "readability": "high contrast, short lines, mobile-readable typography",
    }]
    visual_inference = {
        "policy": "controlled missing-detail inference",
        "provenance_separate": True,
        "locked_for_continuity": True,
    }
    return {
        "plan_status": "ready",
        "source_grounded": True,
        "unknowns_must_remain_unknown": True,
        "image_prompt": image_prompt,
        "image_layout": image_layout,
        "image_dialogue_overlays": image_overlays,
        "visual_inference": visual_inference,
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
            "visual_inference": visual_inference,
            "image": {
                "prompt": image_prompt,
                "layout": image_layout,
                "dialogue_overlays": image_overlays,
                "visual_inference": visual_inference,
            },
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
