from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
SHOT_ROLES = ("establish", "develop", "action", "reaction", "consequence", "detail", "close", "transition")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean(value: Any, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip() if len(text) > limit else text


def _positive_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON package: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"package root must be an object: {path}")
    return value


def _parse_txt(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    header, marker, rest = text.partition("=== IMAGE GENERATION PROMPT ===")
    if not marker:
        raise ValueError(f"missing image prompt section: {path}")
    prompt, marker, rest = rest.partition("=== IMAGE LAYOUT ===")
    if not marker:
        raise ValueError(f"missing image layout section: {path}")
    layout, marker, overlays = rest.partition("=== DIALOGUE / NARRATIVE OVERLAYS ===")
    if not marker:
        raise ValueError(f"missing overlay section: {path}")

    def header_value(name: str) -> str:
        match = re.search(rf"(?m)^{re.escape(name)}:\s*(.+?)\s*$", header)
        return match.group(1).strip() if match else ""

    try:
        scene_id = int(header_value("SCENE ID"))
        scene_order = int(header_value("SCENE ORDER"))
    except ValueError as exc:
        raise ValueError(f"invalid scene id/order: {path}") from exc

    try:
        layout_obj = json.loads(layout.strip() or "{}")
        overlay_obj = json.loads(overlays.strip() or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid TXT JSON section: {path}: {exc}") from exc

    return {
        "scene_id": scene_id,
        "scene_order": scene_order,
        "story_id": 0,
        "title": header_value("TITLE"),
        "page_start": _positive_int(header_value("PAGES").split("–", 1)[0], 0),
        "page_end": _positive_int(header_value("PAGES").split("–", 1)[-1], 0),
        "source_text": _clean(prompt, 12000),
        "plan": {
            "image_prompt": prompt.strip(),
            "image_dialogue_overlays": overlay_obj if isinstance(overlay_obj, list) else [],
            "image_layout": layout_obj if isinstance(layout_obj, dict) else {},
            "long_video_prompt_package": {"shots": []},
            "short_video_prompt_package": {},
            "audio_prompt": {},
            "media_prompt_package": {},
        },
        "characters": [],
        "objects": [],
        "events": [],
        "continuity": {},
        "source_database": "",
    }


def load_scene_records(source: str | Path) -> list[dict[str, Any]]:
    path = Path(source)
    if not path.exists():
        raise ValueError(f"source does not exist: {path}")

    if path.is_file() and path.suffix.lower() == ".json":
        package = _load_json(path)
        records = package.get("scenes")
        if not isinstance(records, list):
            raise ValueError("JSON package has no scenes list")
        result = [dict(item) for item in records if isinstance(item, dict)]
    elif path.is_file() and path.suffix.lower() == ".txt":
        result = [_parse_txt(path)]
    elif path.is_dir():
        txts = sorted(path.glob("scene_*.txt"))
        if not txts:
            raise ValueError(f"no scene_*.txt files found: {path}")
        result = [_parse_txt(item) for item in txts]
    else:
        raise ValueError(f"expected all_prompts.json, a scene TXT, or an image-prompt directory: {path}")

    result.sort(key=lambda item: (_positive_int(item.get("scene_order")), _positive_int(item.get("scene_id"))))
    return result


def _plan(record: dict[str, Any]) -> dict[str, Any]:
    return _mapping(record.get("plan"))


def _intent(record: dict[str, Any]) -> dict[str, Any]:
    media = _mapping(_plan(record).get("media_prompt_package"))
    return _mapping(media.get("generation_intent"))


def _source_text(record: dict[str, Any]) -> str:
    scene = _mapping(_plan(record).get("scene"))
    if scene.get("text"):
        return _clean(scene["text"], 12000)
    if record.get("source_text"):
        return _clean(record["source_text"], 12000)
    return _clean(_plan(record).get("image_prompt"), 12000)


def _moments(record: dict[str, Any]) -> list[str]:
    intent = _intent(record)
    candidates = intent.get("visual_moment_candidates")
    if isinstance(candidates, list):
        values = [_clean(x, 500) for x in candidates if _clean(x, 500)]
        if values:
            return list(dict.fromkeys(values))[:8]
    media = _mapping(_plan(record).get("media_prompt_package"))
    image = _mapping(media.get("image"))
    values = image.get("source_visual_moments")
    if isinstance(values, list):
        return list(dict.fromkeys(_clean(x, 500) for x in values if _clean(x, 500)))[:8]
    return []


def _characters(record: dict[str, Any]) -> list[dict[str, Any]]:
    value = record.get("characters")
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    value = _plan(record).get("characters")
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _events(record: dict[str, Any]) -> list[dict[str, Any]]:
    value = record.get("events")
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    value = _plan(record).get("events")
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _complexity(record: dict[str, Any]) -> int:
    text = _source_text(record)
    words = len(text.split())
    intent = _intent(record)
    signal = str(intent.get("emotional_signal") or "").lower()
    events = _events(record)
    characters = _characters(record)
    score = 1
    if words > 120:
        score += 1
    if words > 260:
        score += 1
    if words > 450:
        score += 1
    if len(events) >= 3:
        score += 1
    if len(characters) >= 2:
        score += 1
    if signal in {"combat", "destruction"}:
        score += 1
    return min(8, score)


def _role_sequence(record: dict[str, Any], count: int) -> list[str]:
    intent = _intent(record)
    signal = str(intent.get("emotional_signal") or "").lower()
    if signal == "combat":
        base = ["establish", "action", "reaction", "detail", "close", "consequence", "transition"]
    elif signal == "destruction":
        base = ["establish", "consequence", "detail", "reaction", "close", "transition"]
    elif signal == "travel":
        base = ["establish", "develop", "transition", "reaction", "destination", "close"]
    elif signal == "reaction":
        base = ["establish", "reaction", "detail", "close", "transition"]
    else:
        base = ["establish", "develop", "reaction", "detail", "close", "transition"]
    roles = []
    for role in base:
        if role not in roles:
            roles.append(role)
        if len(roles) >= count:
            break
    while len(roles) < count:
        roles.append("develop" if len(roles) % 2 else "detail")
    return roles


def _existing_shots(record: dict[str, Any]) -> list[dict[str, Any]]:
    package = _mapping(_plan(record).get("long_video_prompt_package"))
    shots = package.get("shots")
    return [dict(x) for x in shots if isinstance(x, dict)] if isinstance(shots, list) else []


def _shot_count(record: dict[str, Any], minimum: int, maximum: int) -> int:
    existing = len(_existing_shots(record))
    desired = max(existing, _complexity(record))
    return max(minimum, min(maximum, desired))


def _continuity_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    continuity = record.get("continuity")
    if not isinstance(continuity, dict):
        continuity = _mapping(_plan(record).get("continuity"))
    result: dict[str, Any] = {}
    for key in ("location", "time", "weather", "lighting", "physical_state", "active_characters", "objects", "relationships"):
        if key in continuity:
            result[key] = continuity[key]
    characters = _characters(record)
    if characters:
        locks = []
        for item in characters:
            if not isinstance(item, dict):
                continue
            name = _clean(item.get("canonical_name"), 120)
            profile = _mapping(item.get("visual_profile"))
            anchor = _clean(profile.get("identity_anchor"), 120)
            presence = _mapping(item.get("source_presence"))
            if name and anchor and presence.get("physical_presence") is True:
                locks.append({"canonical_name": name, "identity_anchor": anchor})
        if locks:
            result["identity_locks"] = locks
    return result


def _carry_continuity(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    merged = dict(previous)
    merged.update(current)
    if previous.get("identity_locks") and current.get("identity_locks"):
        by_name = {x["canonical_name"].casefold(): x for x in previous["identity_locks"]}
        for item in current["identity_locks"]:
            by_name[item["canonical_name"].casefold()] = item
        merged["identity_locks"] = list(by_name.values())
    return merged


def _continuity_issues(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    issues = []
    for key in ("location", "time"):
        if previous.get(key) and current.get(key) and previous[key] != current[key]:
            issues.append(f"explicit_{key}_change")
    old_locks = {x["canonical_name"].casefold(): x.get("identity_anchor") for x in previous.get("identity_locks", []) if isinstance(x, dict)}
    new_locks = {x["canonical_name"].casefold(): x.get("identity_anchor") for x in current.get("identity_locks", []) if isinstance(x, dict)}
    for name in sorted(set(old_locks) & set(new_locks)):
        if old_locks[name] and new_locks[name] and old_locks[name] != new_locks[name]:
            issues.append(f"identity_anchor_changed:{name}")
    return issues


def _overlay_texts(record: dict[str, Any]) -> list[str]:
    plan = _plan(record)
    overlays = plan.get("image_dialogue_overlays")
    if not isinstance(overlays, list):
        media = _mapping(plan.get("media_prompt_package"))
        overlays = _mapping(media.get("image")).get("dialogue_overlays")
    return [_clean(x.get("text"), 300) for x in overlays if isinstance(x, dict) and _clean(x.get("text"), 300)] if isinstance(overlays, list) else []


def _audio_package(record: dict[str, Any]) -> dict[str, Any]:
    audio = _plan(record).get("audio_prompt")
    if isinstance(audio, dict):
        return dict(audio)
    return {}


def _build_shots(
    record: dict[str, Any],
    *,
    global_start: int,
    minimum: int,
    maximum: int,
    inherited_continuity: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    count = _shot_count(record, minimum, maximum)
    existing = _existing_shots(record)
    moments = _moments(record) or [_clean(_source_text(record), 500)]
    roles = _role_sequence(record, count)
    current_continuity = _continuity_snapshot(record)
    continuity = _carry_continuity(inherited_continuity, current_continuity)
    overlays = _overlay_texts(record)
    audio = _audio_package(record)
    shots: list[dict[str, Any]] = []

    for index in range(count):
        source_shot = existing[index] if index < len(existing) else {}
        role = _clean(source_shot.get("role") or roles[index], 80)
        focus = _clean(source_shot.get("source_visual_focus") or moments[index % len(moments)], 700)
        prompt = _clean(source_shot.get("prompt"), 10000)
        if not prompt:
            prompt = _clean(_plan(record).get("image_prompt"), 10000)
        if not prompt:
            prompt = f"Source-grounded cinematic shot. Preserve only the documented source moment: {focus}."
        shot_id = global_start + index
        shot_overlay = overlays[index] if index < len(overlays) else ""
        dialogue = ""
        dialogue_source = audio.get("dialogue_source")
        if isinstance(dialogue_source, list) and index < len(dialogue_source):
            dialogue = _clean(dialogue_source[index], 500)

        base_duration = 4.0 if role in {"establish", "consequence", "transition"} else 3.5
        voice_words = len(dialogue.split())
        overlay_words = len(shot_overlay.split())
        duration = max(base_duration, voice_words / 2.5 + 0.6, overlay_words / 3.0 + 0.5)
        shots.append({
            "shot_id": shot_id,
            "shot_order": index + 1,
            "scene_id": _positive_int(record.get("scene_id")),
            "scene_order": _positive_int(record.get("scene_order")),
            "role": role or "develop",
            "purpose": _clean(source_shot.get("purpose") or role, 200),
            "source_visual_focus": focus,
            "prompt": prompt,
            "image_prompt": prompt,
            "duration_seconds": round(duration, 2),
            "overlay_text": shot_overlay,
            "voiceover_text": dialogue,
            "audio_direction": audio,
            "continuity_before": dict(continuity),
            "source_grounded": True,
        })
    return shots, current_continuity


def build_adaptation(
    source: str | Path,
    *,
    minimum_shots: int = 3,
    maximum_shots: int = 8,
    scenes_per_episode: int = 10,
    start_scene: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    if minimum_shots < 1 or maximum_shots < minimum_shots:
        raise ValueError("shot bounds are invalid")
    records = load_scene_records(source)
    if start_scene is not None:
        records = [x for x in records if _positive_int(x.get("scene_order")) >= start_scene]
    if limit is not None:
        records = records[:max(0, limit)]
    if not records:
        raise ValueError("no scenes selected")

    episodes: list[dict[str, Any]] = []
    all_shots: list[dict[str, Any]] = []
    continuity: dict[str, Any] = {}
    global_shot_id = 1
    episode_index = 0
    current_episode: dict[str, Any] | None = None

    previous_story_id = None
    for record in records:
        story_id = _positive_int(record.get("story_id"))
        boundary = (
            current_episode is None
            or len(current_episode["scenes"]) >= scenes_per_episode
            or (previous_story_id not in (None, 0) and story_id not in (0, previous_story_id))
        )
        if boundary:
            episode_index += 1
            current_episode = {
                "episode_id": episode_index,
                "episode_title": f"Episode {episode_index:03d}",
                "story_ids": [],
                "scenes": [],
                "shots": [],
                "audio": [],
                "continuity_issues": [],
            }
            episodes.append(current_episode)

        if story_id and story_id not in current_episode["story_ids"]:
            current_episode["story_ids"].append(story_id)

        scene_continuity = _continuity_snapshot(record)
        issues = _continuity_issues(continuity, scene_continuity)
        current_episode["continuity_issues"].extend(
            {"scene_id": _positive_int(record.get("scene_id")), "issues": issues}
            for _ in [0]
            if issues
        )

        shots, continuity = _build_shots(
            record,
            global_start=global_shot_id,
            minimum=minimum_shots,
            maximum=maximum_shots,
            inherited_continuity=continuity,
        )
        global_shot_id += len(shots)
        current_episode["scenes"].append({
            "scene_id": _positive_int(record.get("scene_id")),
            "scene_order": _positive_int(record.get("scene_order")),
            "story_id": story_id,
            "title": _clean(record.get("title"), 240),
            "page_start": _positive_int(record.get("page_start")),
            "page_end": _positive_int(record.get("page_end")),
            "source_grounded": True,
            "complexity": _complexity(record),
            "shot_count": len(shots),
            "continuity": scene_continuity,
        })
        current_episode["shots"].extend(shots)
        audio = _audio_package(record)
        if audio:
            current_episode["audio"].append({
                "scene_id": _positive_int(record.get("scene_id")),
                "direction": audio,
            })
        all_shots.extend(shots)
        previous_story_id = story_id

    for episode in episodes:
        episode["shot_count"] = len(episode["shots"])
        episode["scene_count"] = len(episode["scenes"])

    return {
        "schema_version": SCHEMA_VERSION,
        "source": str(source),
        "scene_count": len(records),
        "episode_count": len(episodes),
        "shot_count": len(all_shots),
        "shot_policy": {
            "minimum": minimum_shots,
            "maximum": maximum_shots,
            "basis": "source scene complexity, existing source-grounded long-video plan, event density, character count, and source emotional signal",
        },
        "source_grounded": True,
        "unknowns_must_remain_unknown": True,
        "episodes": episodes,
        "shots": all_shots,
    }


def validate_adaptation(adaptation: dict[str, Any], source_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scene_text = {
        _positive_int(record.get("scene_id")): _source_text(record)
        for record in source_records
    }
    errors: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for shot in adaptation.get("shots", []):
        shot_id = _positive_int(shot.get("shot_id"))
        scene_id = _positive_int(shot.get("scene_id"))
        focus = _clean(shot.get("source_visual_focus"), 1000)
        if shot_id in seen_ids:
            errors.append({"shot_id": shot_id, "error": "duplicate_shot_id"})
        seen_ids.add(shot_id)
        source = scene_text.get(scene_id, "")
        if not source:
            errors.append({"shot_id": shot_id, "error": "missing_source_scene"})
        elif focus and focus.casefold() not in source.casefold():
            errors.append({"shot_id": shot_id, "error": "source_visual_focus_not_found_in_source"})
        if shot.get("source_grounded") is not True:
            errors.append({"shot_id": shot_id, "error": "shot_not_marked_source_grounded"})
        if not str(shot.get("image_prompt") or "").strip():
            errors.append({"shot_id": shot_id, "error": "missing_image_prompt"})
    return errors


def _write_shot_txt(path: Path, shot: dict[str, Any], scene: dict[str, Any]) -> None:
    overlay = shot.get("overlay_text") or ""
    payload = [{
        "box_number": 1,
        "box_type": "narrative_box",
        "text": overlay,
        "text_source": "source_adaptation_overlay",
        "required": True,
        "placement": "largest protected negative-space region opposite subject/action",
        "max_width_percent": 68,
        "max_height_percent": 15,
        "avoid": ["faces", "hands", "important_objects", "primary_action"],
    }] if overlay else []
    header = (
        f"SOURCE: {scene.get('source_database') or ''}\n"
        f"SCENE ID: {shot['shot_id']}\n"
        f"SCENE ORDER: {shot['shot_id']}\n"
        f"TITLE: {scene.get('title') or ''} | SHOT {shot['shot_order']} | {shot['role']}\n"
        f"PAGES: {scene.get('page_start')}–{scene.get('page_end')}\n\n"
    )
    text = (
        header
        + "=== IMAGE GENERATION PROMPT ===\n"
        + str(shot["image_prompt"]).strip()
        + "\n\n=== IMAGE LAYOUT ===\n"
        + json.dumps({"aspect_ratio": "9:16", "text_rendering": "deterministic overlay", "shot_id": shot["shot_id"]}, ensure_ascii=False, indent=2)
        + "\n\n=== DIALOGUE / NARRATIVE OVERLAYS ===\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n"
    )
    path.write_text(text, encoding="utf-8")


def _write_episode_text_artifacts(out: Path, episode: dict[str, Any]) -> None:
    episode_id = int(episode["episode_id"])
    narration = []
    srt = []
    elapsed = 0.0
    subtitle_index = 1

    def srt_time(seconds: float) -> str:
        total_ms = max(0, round(seconds * 1000))
        hours, rem = divmod(total_ms, 3600000)
        minutes, rem = divmod(rem, 60000)
        secs, millis = divmod(rem, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    for shot in episode.get("shots", []):
        duration = float(shot.get("duration_seconds") or 0.0)
        voice = _clean(shot.get("voiceover_text"), 1000)
        overlay = _clean(shot.get("overlay_text"), 1000)
        if voice:
            narration.append(f"[{int(shot['shot_id']):06d}] {voice}")
        if overlay:
            srt.extend([
                str(subtitle_index),
                f"{srt_time(elapsed)} --> {srt_time(elapsed + duration)}",
                overlay,
                "",
            ])
            subtitle_index += 1
        elapsed += duration

    (out / f"episode_{episode_id:03d}_narration.txt").write_text(
        "\n".join(narration) + ("\n" if narration else ""), encoding="utf-8"
    )
    (out / f"episode_{episode_id:03d}.srt").write_text(
        "\n".join(srt), encoding="utf-8"
    )


def write_adaptation_outputs(
    adaptation: dict[str, Any],
    output_dir: str | Path,
    source_records: list[dict[str, Any]],
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    image_dir = out / "shots" / "image"
    video_dir = out / "shots" / "video"
    audio_dir = out / "audio"
    subtitle_dir = out / "subtitles"
    for directory in (image_dir, video_dir, audio_dir, subtitle_dir):
        directory.mkdir(parents=True, exist_ok=True)

    scene_by_id = {_positive_int(x.get("scene_id")): x for x in source_records}
    for shot in adaptation["shots"]:
        scene = scene_by_id.get(_positive_int(shot["scene_id"]), {})
        _write_shot_txt(image_dir / f"scene_{shot['shot_id']:06d}_shot_{shot['shot_order']:02d}.txt", shot, scene)
        (video_dir / f"shot_{shot['shot_id']:06d}.json").write_text(json.dumps(shot, ensure_ascii=False, indent=2), encoding="utf-8")
        (audio_dir / f"shot_{shot['shot_id']:06d}.json").write_text(json.dumps({
            "shot_id": shot["shot_id"],
            "scene_id": shot["scene_id"],
            "voiceover_text": shot["voiceover_text"],
            "audio_direction": shot["audio_direction"],
            "duration_seconds": shot["duration_seconds"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        (subtitle_dir / f"shot_{shot['shot_id']:06d}.json").write_text(json.dumps({
            "shot_id": shot["shot_id"],
            "scene_id": shot["scene_id"],
            "text": shot["overlay_text"],
            "start_seconds": 0.0,
            "duration_seconds": shot["duration_seconds"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    for episode in adaptation["episodes"]:
        (out / f"episode_{episode['episode_id']:03d}.json").write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_episode_text_artifacts(out, episode)

    qa_errors = validate_adaptation(adaptation, source_records)
    adaptation["qa_passed"] = not qa_errors
    adaptation["qa_errors"] = qa_errors
    package_path = out / "cinematic_adaptation.json"
    package_path.write_text(json.dumps(adaptation, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "qa_report.json").write_text(json.dumps({
        "qa_passed": not qa_errors,
        "error_count": len(qa_errors),
        "errors": qa_errors,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "README.txt").write_text(
        "Cinematic adaptation package.\n"
        "The source-grounded image pipeline remains unchanged.\n"
        "shots/image contains scene_*.txt files directly consumable by core.image_pipeline.\n"
        "shots/video contains per-shot video-generation manifests.\n"
        "audio contains voice/music/sound-design manifests.\n"
        "subtitles contains deterministic overlay timing manifests.\n",
        encoding="utf-8",
    )
    return package_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a source-grounded cinematic shot adaptation from an exported generation package.")
    parser.add_argument("source")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--min-shots", type=int, default=3)
    parser.add_argument("--max-shots", type=int, default=8)
    parser.add_argument("--scenes-per-episode", type=int, default=10)
    parser.add_argument("--start-scene", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    records = load_scene_records(args.source)
    package = build_adaptation(
        args.source,
        minimum_shots=max(1, args.min_shots),
        maximum_shots=max(1, args.max_shots),
        scenes_per_episode=max(1, args.scenes_per_episode),
        start_scene=args.start_scene,
        limit=args.limit,
    )
    path = write_adaptation_outputs(package, args.output_dir, records)
    print(json.dumps({
        "output": str(path),
        "scene_count": package["scene_count"],
        "episode_count": package["episode_count"],
        "shot_count": package["shot_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
