from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageStat


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_SCENE_NUMBER_RE = re.compile(r"(?:scene[_-]?)?(\d+)", re.I)


def _scene_number(path: Path) -> int | None:
    matches = list(_SCENE_NUMBER_RE.finditer(path.stem))
    return int(matches[-1].group(1)) if matches else None


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\georgia.ttf"),
        Path(r"C:\Windows\Fonts\times.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                pass
    return ImageFont.load_default(size=max(12, size))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: Any, max_width: int) -> str:
    words = str(text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if current and width > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


def _activity_score(image: Image.Image, box: tuple[int, int, int, int]) -> float:
    crop = image.convert("L").crop(box)
    stat = ImageStat.Stat(crop)
    # Low variance is a useful deterministic proxy for negative space.
    return float(stat.var[0])


def _candidate_regions(width: int, height: int, box_w: int, box_h: int, margin: int) -> list[tuple[int, int, int, int]]:
    x = max(margin, (width - box_w) // 2)
    positions = [
        (x, margin),
        (x, height - margin - box_h),
        (margin, max(margin, (height - box_h) // 2)),
        (width - margin - box_w, max(margin, (height - box_h) // 2)),
    ]
    return [
        (max(0, left), max(0, top), min(width, left + box_w), min(height, top + box_h))
        for left, top in positions
    ]


def _find_safe_region(image: Image.Image, box_w: int, box_h: int, margin: int) -> tuple[int, int, int, int]:
    regions = _candidate_regions(image.width, image.height, box_w, box_h, margin)
    return min(regions, key=lambda box: _activity_score(image, box))


def _get_scene_plan(package: dict[str, Any], scene_number: int) -> dict[str, Any] | None:
    for item in package.get("scenes") or []:
        if not isinstance(item, dict):
            continue
        plan = item.get("plan") if isinstance(item.get("plan"), dict) else item
        if not isinstance(plan, dict):
            continue
        values = [
            plan.get("scene_id"),
            plan.get("scene_order"),
            (plan.get("scene") or {}).get("scene_id") if isinstance(plan.get("scene"), dict) else None,
            (plan.get("scene") or {}).get("scene_order") if isinstance(plan.get("scene"), dict) else None,
        ]
        if scene_number in {int(v) for v in values if isinstance(v, int) or str(v).isdigit()}:
            return plan
    return None


def render_overlays(image: Image.Image, boxes: list[dict[str, Any]]) -> Image.Image:
    output = image.convert("RGBA")
    if not boxes:
        return output
    width, height = output.size
    panel_w = int(width * 0.68)
    max_panel_h = int(height * 0.15)
    margin = max(8, int(width * 0.07))
    font_size = max(24, int(height * 0.034))
    overlay_layer = Image.new("RGBA", output.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_layer)

    occupied: list[tuple[int, int, int, int]] = []
    for box in boxes[:2]:
        text = str(box.get("text") or "").strip()
        if not text:
            continue
        current_size = font_size
        while current_size >= 20:
            font = _load_font(current_size)
            padding_x = int(width * 0.03)
            padding_y = int(height * 0.022)
            wrapped = _wrap(draw, text, font, panel_w - 2 * padding_x)
            bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=max(4, int(current_size * 0.35)))
            text_h = bbox[3] - bbox[1]
            panel_h = text_h + 2 * padding_y
            if panel_h <= max_panel_h:
                break
            current_size -= 2
        else:
            font = _load_font(20)
            wrapped = _wrap(draw, text, font, panel_w - 2 * padding_x)
            bbox = draw.multiline_textbbox((0, 0), wrapped, font=font)
            panel_h = min(max_panel_h, bbox[3] - bbox[1] + 2 * padding_y)

        region = _find_safe_region(output, panel_w, panel_h, margin)
        # Prefer a region that does not collide with an earlier box.
        candidates = _candidate_regions(width, height, panel_w, panel_h, margin)
        non_overlapping = [
            candidate
            for candidate in candidates
            if all(
                candidate[2] <= other[0] or candidate[0] >= other[2]
                or candidate[3] <= other[1] or candidate[1] >= other[3]
                for other in occupied
            )
        ]
        if non_overlapping:
            region = min(non_overlapping, key=lambda candidate: _activity_score(output, candidate))

        left, top, right, bottom = region
        radius = max(6, int(min(width, height) * 0.012))
        draw.rounded_rectangle(
            region,
            radius=radius,
            fill=(17, 19, 24, 220),
        )
        padding_x = int(width * 0.03)
        padding_y = int(height * 0.022)
        draw.multiline_text(
            (left + padding_x, top + padding_y),
            wrapped,
            font=font,
            fill=(243, 238, 227, 255),
            spacing=max(4, int(current_size * 0.35)),
            align="left",
        )
        occupied.append(region)

    return Image.alpha_composite(output, overlay_layer)


def process_directory(
    input_dir: Path,
    output_dir: Path,
    package_path: Path,
    *,
    expected_count: int | None = None,
    require_complete: bool = False,
) -> dict[str, Any]:
    if not package_path.is_file():
        return {"processed": 0, "skipped": 0, "failures": [f"package not found: {package_path}"]}
    if not input_dir.is_dir():
        return {
            "processed": 0,
            "skipped": 0,
            "failures": [
                f"input image directory not found: {input_dir}",
                "Generate the source images first, then run the overlay renderer.",
            ],
        }

    package = json.loads(package_path.read_text(encoding="utf-8"))
    image_paths = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_EXTS)
    if not image_paths:
        return {
            "processed": 0,
            "skipped": 0,
            "failures": [f"no supported images found in: {input_dir}"],
        }

    staging_dir = output_dir.with_name(output_dir.name + ".staging")
    shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    skipped = 0
    failures: list[str] = []

    for image_path in image_paths:
        scene_number = _scene_number(image_path)
        if scene_number is None:
            skipped += 1
            continue
        plan = _get_scene_plan(package, scene_number)
        if not plan:
            failures.append(f"{image_path.name}: scene {scene_number} not found in package")
            continue
        boxes = (
            plan.get("image_dialogue_overlays")
            or (plan.get("image") or {}).get("dialogue_overlays")
            or plan.get("dialogue_overlays")
            or []
        )
        required_boxes = [
            box
            for box in boxes
            if isinstance(box, dict)
            and box.get("required") is not False
            and str(box.get("text") or "").strip()
        ]
        if not required_boxes:
            failures.append(
                f"{image_path.name}: required source-derived dialogue/narrative overlay is missing"
            )
            continue
        try:
            with Image.open(image_path) as source:
                rendered = render_overlays(source, boxes)
                out = staging_dir / image_path.name
                rendered.convert("RGB").save(out, quality=95)
            processed += 1
        except Exception as exc:
            failures.append(f"{image_path.name}: {exc}")

    if expected_count is not None and processed != expected_count:
        failures.append(
            f"expected {expected_count} rendered images but processed {processed}"
        )
    if require_complete:
        scene_count = len(package.get("scenes") or [])
        if processed != scene_count:
            failures.append(
                f"complete render required: package contains {scene_count} scenes but only {processed} images were rendered"
            )

    if not failures:
        shutil.rmtree(output_dir, ignore_errors=True)
        staging_dir.replace(output_dir)
    else:
        # Preserve the staging directory for inspection; never publish a partial
        # final image set when completeness was requested.
        failures.append(f"partial output retained for inspection at: {staging_dir}")

    return {"processed": processed, "skipped": skipped, "failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply deterministic project-standard dialogue/narrative overlays to generated images.")
    parser.add_argument("--input-dir", required=True, help="Directory containing generated clean images.")
    parser.add_argument("--output-dir", required=True, help="Directory that receives the final composited images only after a complete successful run.")
    parser.add_argument("--package", required=True, help="Path to all_prompts.json")
    parser.add_argument("--expected-count", type=int, default=None, help="Require exactly this many rendered images.")
    parser.add_argument("--require-complete", action="store_true", help="Require one rendered image for every scene in the package.")
    args = parser.parse_args()
    result = process_directory(
        Path(args.input_dir),
        Path(args.output_dir),
        Path(args.package),
        expected_count=args.expected_count,
        require_complete=args.require_complete,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
