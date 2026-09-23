from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


BACKGROUND = (17, 19, 24, 220)  # #111318
TEXT = (243, 238, 227, 255)  # #F3EEE3
FONT_CANDIDATES = (
    r"C:\Windows\Fonts\georgia.ttf",
    r"C:\Windows\Fonts\Georgia.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Georgia.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/georgia.ttf",
)
FALLBACK_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
)


class OverlayRenderError(RuntimeError):
    pass


def _font_path() -> str | None:
    configured = os.getenv("SOCIAL_AUTOMATION_GEORGIA_FONT")
    candidates = ((configured,) if configured else ()) + FONT_CANDIDATES + FALLBACK_FONT_CANDIDATES
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _font_path()
    if path:
        return ImageFont.truetype(path, max(10, size))
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = " ".join(str(text or "").split()).split(" ")
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_height: int,
    start_size: int,
    min_size: int = 14,
) -> tuple[ImageFont.ImageFont, list[str], int]:
    for size in range(max(start_size, min_size), min_size - 1, -1):
        font = _load_font(size)
        lines = _wrap_text(draw, text, font, max_width)
        if not lines:
            continue
        spacing = max(2, int(size * 0.28))
        bbox = font.getbbox("Ag")
        line_height = max(1, bbox[3] - bbox[1])
        text_height = len(lines) * line_height + max(0, len(lines) - 1) * spacing
        if text_height <= max_height:
            return font, lines, spacing
    font = _load_font(min_size)
    lines = _wrap_text(draw, text, font, max_width)
    return font, lines, max(2, int(min_size * 0.28))


def _band_detail(image: Image.Image, top: int, bottom: int) -> float:
    if bottom <= top:
        return float("inf")
    gray = ImageOps.grayscale(image.crop((0, top, image.width, bottom)))
    sample_width = 128
    sample_height = max(16, round(gray.height * sample_width / max(1, gray.width)))
    gray = gray.resize((sample_width, sample_height))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    stat = ImageOps.autocontrast(edges).resize((1, 1))
    return float(stat.getpixel((0, 0)))


def _choose_band(image: Image.Image, total_height: int, safe_margin: float) -> tuple[int, int, str]:
    height = image.height
    margin = round(height * safe_margin)
    candidates = [
        (margin, min(height - margin, margin + total_height), "top"),
        (max(margin, height - margin - total_height), height - margin, "bottom"),
    ]
    scored = [(_band_detail(image, top, bottom), top, bottom, name) for top, bottom, name in candidates]
    _, top, bottom, name = min(scored, key=lambda item: (item[0], 0 if item[3] == "bottom" else 1))
    return top, bottom, name


def render_overlays(
    source_path: str | Path,
    destination_path: str | Path,
    overlays: list[dict[str, Any]],
    *,
    safe_margin_percent: float = 7.0,
    default_max_width_percent: float = 68.0,
    default_max_height_percent: float = 15.0,
) -> dict[str, Any]:
    source = Path(source_path)
    destination = Path(destination_path)
    if not source.exists():
        raise OverlayRenderError(f"source image does not exist: {source}")

    normalized = []
    for item in overlays:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text") or "").split()).strip()
        if text:
            normalized.append({
                "box_number": int(item.get("box_number") or len(normalized) + 1),
                "box_type": str(item.get("box_type") or "narrative_box"),
                "text": text,
                "required": item.get("required") is not False,
                "max_width_percent": float(item.get("max_width_percent") or default_max_width_percent),
                "max_height_percent": float(item.get("max_height_percent") or default_max_height_percent),
            })

    destination.parent.mkdir(parents=True, exist_ok=True)
    if not normalized:
        shutil.copy2(source, destination)
        return {"rendered": False, "boxes": [], "font": None, "placement": None}

    try:
        image = Image.open(source).convert("RGBA")
    except Exception as exc:
        raise OverlayRenderError(f"could not open generated image: {exc}") from exc

    draw = ImageDraw.Draw(image, "RGBA")
    gap = max(8, round(image.height * 0.012))
    max_box_height = round(image.height * (default_max_height_percent / 100.0))
    total_height = len(normalized) * max_box_height + max(0, len(normalized) - 1) * gap
    safe_margin = safe_margin_percent / 100.0
    band_top, band_bottom, band_name = _choose_band(image, total_height, safe_margin)

    max_width_percent = min(
        68.0,
        max(float(item["max_width_percent"]) for item in normalized),
    )
    box_width = min(image.width - 2 * round(image.width * safe_margin), round(image.width * max_width_percent / 100.0))
    left = (image.width - box_width) // 2
    box_height = max_box_height
    boxes: list[dict[str, Any]] = []

    for index, item in enumerate(normalized):
        top = band_top + index * (box_height + gap)
        bottom = min(band_bottom, top + box_height)
        horizontal_pad = max(12, round(box_width * 0.03))
        vertical_pad = max(10, round(box_height * 0.10))
        available_width = max(40, box_width - 2 * horizontal_pad)
        available_height = max(30, (bottom - top) - 2 * vertical_pad)
        start_size = max(16, round(min(image.width, image.height) * 0.034))
        font, lines, spacing = _fit_text(
            draw,
            item["text"],
            available_width,
            available_height,
            start_size,
        )

        draw.rounded_rectangle(
            (left, top, left + box_width, bottom),
            radius=max(8, round(min(image.width, image.height) * 0.012)),
            fill=BACKGROUND,
        )
        text_y = top + vertical_pad
        bbox = font.getbbox("Ag")
        line_height = max(1, bbox[3] - bbox[1])
        for line in lines:
            draw.text(
                (left + horizontal_pad, text_y),
                line,
                font=font,
                fill=TEXT,
            )
            text_y += line_height + spacing

        boxes.append({
            "box_number": item["box_number"],
            "box_type": item["box_type"],
            "text": item["text"],
            "required": item["required"],
            "x": left,
            "y": top,
            "width": box_width,
            "height": bottom - top,
            "font_size": getattr(font, "size", None),
            "line_count": len(lines),
        })

    image.convert("RGB").save(destination, format="PNG")
    return {
        "rendered": True,
        "boxes": boxes,
        "font": _font_path() or "Pillow default",
        "placement": band_name,
        "style": {
            "background": "#111318",
            "background_alpha": 220,
            "text": "#F3EEE3",
            "font_family": "Georgia",
            "font_weight": "regular",
            "max_width_percent": max_width_percent,
            "max_height_percent": default_max_height_percent,
        },
    }
