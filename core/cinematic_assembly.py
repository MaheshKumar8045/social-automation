from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def load_adaptation(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("episodes"), list):
        raise ValueError("invalid cinematic_adaptation.json")
    return value


def _image_candidates(image_root: Path, shot_id: int) -> list[Path]:
    return sorted(image_root.rglob(f"scene_*_{shot_id:05d}_final.png"))


def build_video_manifest(adaptation: dict[str, Any], image_root: str | Path) -> dict[str, Any]:
    root = Path(image_root)
    episodes = []
    missing = []
    for episode in adaptation.get("episodes", []):
        shots = []
        for shot in episode.get("shots", []):
            shot_id = int(shot["shot_id"])
            candidates = _image_candidates(root, shot_id)
            image = str(candidates[0]) if candidates else ""
            if not image:
                missing.append(shot_id)
            shots.append({
                "shot_id": shot_id,
                "duration_seconds": float(shot.get("duration_seconds") or 3.5),
                "image": image,
                "subtitle_text": str(shot.get("overlay_text") or ""),
                "voiceover_text": str(shot.get("voiceover_text") or ""),
            })
        episodes.append({
            "episode_id": int(episode["episode_id"]),
            "shots": shots,
            "missing_shot_ids": [item["shot_id"] for item in shots if not item["image"]],
        })
    return {
        "schema_version": 1,
        "source_adaptation": adaptation.get("source"),
        "image_root": str(root),
        "episode_count": len(episodes),
        "missing_shot_ids": missing,
        "ready": not missing,
        "episodes": episodes,
    }


def _quote_concat(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")


def write_video_manifests(manifest: dict[str, Any], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    video_dir = out / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    for episode in manifest["episodes"]:
        concat_lines = []
        for shot in episode["shots"]:
            if not shot["image"]:
                continue
            concat_lines.append(f"file '{_quote_concat(Path(shot['image']))}'")
            concat_lines.append(f"duration {float(shot['duration_seconds']):.2f}")
        if concat_lines:
            last_image = next(
                (shot["image"] for shot in reversed(episode["shots"]) if shot["image"]),
                None,
            )
            if last_image:
                concat_lines.append(f"file '{_quote_concat(Path(last_image))}'")
        (video_dir / f"episode_{episode['episode_id']:03d}.concat.txt").write_text(
            "\n".join(concat_lines) + ("\n" if concat_lines else ""),
            encoding="utf-8",
        )
        command = (
            f'ffmpeg -y -f concat -safe 0 -i "episode_{episode["episode_id"]:03d}.concat.txt" '
            '-vf "scale=720:1280:force_original_aspect_ratio=decrease,'
            'pad=720:1280:(ow-iw)/2:(oh-ih)/2,format=yuv420p" '
            '-r 30 -movflags +faststart '
            f'"episode_{episode["episode_id"]:03d}.mp4"'
        )
        (video_dir / f"episode_{episode['episode_id']:03d}.ffmpeg.txt").write_text(command + "\n", encoding="utf-8")

    manifest_path = out / "video_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def render_episodes(manifest: dict[str, Any], output_dir: str | Path) -> list[str]:
    video_dir = Path(output_dir) / "video"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg was not found in PATH")
    rendered = []
    for episode in manifest["episodes"]:
        if episode["missing_shot_ids"]:
            raise RuntimeError(
                f"episode {episode['episode_id']} is missing images: {episode['missing_shot_ids']}"
            )
        concat = video_dir / f"episode_{episode['episode_id']:03d}.concat.txt"
        output = video_dir / f"episode_{episode['episode_id']:03d}.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat),
                "-vf",
                "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                "-r",
                "30",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
        )
        rendered.append(str(output))
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble generated cinematic shot images into episode video manifests or MP4s.")
    parser.add_argument("adaptation")
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()

    adaptation = load_adaptation(args.adaptation)
    manifest = build_video_manifest(adaptation, args.image_root)
    path = write_video_manifests(manifest, args.output_dir)
    rendered = render_episodes(manifest, args.output_dir) if args.render else []
    print(json.dumps({
        "manifest": str(path),
        "episode_count": manifest["episode_count"],
        "missing_shots": len(manifest["missing_shot_ids"]),
        "ready": manifest["ready"],
        "rendered": rendered,
    }, ensure_ascii=False, indent=2))
    return 0 if manifest["ready"] or not args.render else 2


if __name__ == "__main__":
    raise SystemExit(main())
