from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_PROFILE_PATH = Path("config/social_export_profiles.json")
DEFAULT_OUTPUT_DIR = Path("data/exports")


def load_profiles(path: str | Path = DEFAULT_PROFILE_PATH) -> dict[str, dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        profiles = json.load(handle)
    if not isinstance(profiles, dict):
        raise ValueError("social export profiles must be a JSON object")
    return profiles


def _center_crop(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    source_ratio = image.width / image.height
    target_ratio = target_width / target_height

    if source_ratio > target_ratio:
        crop_width = round(image.height * target_ratio)
        left = (image.width - crop_width) // 2
        box = (left, 0, left + crop_width, image.height)
    else:
        crop_height = round(image.width / target_ratio)
        top = (image.height - crop_height) // 2
        box = (0, top, image.width, top + crop_height)

    return image.crop(box)


def export_image(
    input_path: str | Path,
    profile: str,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    profiles_path: str | Path = DEFAULT_PROFILE_PATH,
    filename: str | None = None,
) -> str:
    profiles = load_profiles(profiles_path)
    if profile not in profiles:
        available = ", ".join(sorted(profiles))
        raise ValueError(f"unknown social export profile '{profile}'. Available: {available}")

    config = profiles[profile]
    width = int(config["width"])
    height = int(config["height"])
    mode = config.get("mode", "resize")
    output_format = str(config.get("format", "JPEG")).upper()
    quality = int(config.get("quality", 95))

    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"input image not found: {input_path}")

    with Image.open(input_path) as source:
        image = source.convert("RGB")
        if mode == "center_crop":
            image = _center_crop(image, width, height)
        elif mode != "resize":
            raise ValueError(f"unsupported social export mode: {mode}")
        image = image.resize((width, height), Image.Resampling.LANCZOS)

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        if filename is None:
            filename = f"{input_path.stem}_{profile}_{width}x{height}.jpg"
        output_path = output_dir / filename

        save_kwargs: dict[str, Any] = {"format": output_format, "quality": quality, "optimize": True}
        if output_format == "JPEG":
            save_kwargs["progressive"] = True
        image.save(output_path, **save_kwargs)

    return str(output_path)
