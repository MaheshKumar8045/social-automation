from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat


# Text-only overlay: no opaque/translucent panel is composited over the artwork.
TEXT = (247, 240, 220, 255)  # warm parchment / ivory
STROKE = (8, 11, 13, 245)  # dark cinematic outline
SHADOW = (0, 0, 0, 155)

# Prefer period / fantasy-book serif fonts when they are installed. The environment
# variable allows production machines to pin an exact font without changing code.
FONT_CANDIDATES = (
    r"C:\Windows\Fonts\CinzelDecorative-Regular.ttf",
    r"C:\Windows\Fonts\Cinzel-Regular.ttf",
    r"C:\Windows\Fonts\IMFellEnglish-Regular.ttf",
    r"C:\Windows\Fonts\CormorantGaramond-Regular.ttf",
    r"C:\Windows\Fonts\GARA.TTF",
    r"C:\Windows\Fonts\BKANT.TTF",
    r"C:\Windows\Fonts\georgia.ttf",
    r"C:\Windows\Fonts\Georgia.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/CinzelDecorative-Regular.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Cinzel-Regular.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/IMFellEnglish-Regular.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/CormorantGaramond-Regular.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/GARA.TTF",
    "/usr/share/fonts/truetype/msttcorefonts/BKANT.TTF",
    "/usr/share/fonts/truetype/msttcorefonts/Georgia.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/georgia.ttf",
)
FALLBACK_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
)


class OverlayRenderError(RuntimeError):
    pass


def _font_path() -> str | None:
    configured = (
        os.getenv("SOCIAL_AUTOMATION_OVERLAY_FONT")
        or os.getenv("SOCIAL_AUTOMATION_GEORGIA_FONT")
    )
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


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
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

        # Keep an unusually long source word visible instead of dropping it.
        if draw.textlength(word, font=font) <= max_width:
            current = word
        else:
            chunk = ""
            for char in word:
                candidate_chunk = chunk + char
                if draw.textlength(candidate_chunk, font=font) <= max_width:
                    chunk = candidate_chunk
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = char
            current = chunk

    if current:
        lines.append(current)
    return lines


def _text_metrics(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.ImageFont,
    spacing: int,
) -> tuple[int, int]:
    if not lines:
        return 0, 0
    widths = [round(draw.textlength(line, font=font)) for line in lines]
    bbox = font.getbbox("Ag")
    line_height = max(1, bbox[3] - bbox[1])
    height = len(lines) * line_height + max(0, len(lines) - 1) * spacing
    return max(widths, default=0), height


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_height: int,
    start_size: int,
    min_size: int = 22,
) -> tuple[ImageFont.ImageFont, list[str], int, int, int]:
    # Start noticeably larger than the previous 3.4% treatment.
    for size in range(max(start_size, min_size), min_size - 1, -1):
        font = _load_font(size)
        spacing = max(3, round(size * 0.20))
        lines = _wrap_text(draw, text, font, max_width)
        width, height = _text_metrics(draw, lines, font, spacing)
        if lines and width <= max_width and height <= max_height:
            return font, lines, spacing, width, height

    font = _load_font(min_size)
    spacing = max(3, round(min_size * 0.20))
    lines = _wrap_text(draw, text, font, max_width)
    width, height = _text_metrics(draw, lines, font, spacing)
    return font, lines, spacing, width, height


def _region_detail(image: Image.Image, box: tuple[int, int, int, int]) -> float:
    """Estimate visual complexity so text is placed over quiet scenery, not subjects."""
    left, top, right, bottom = box
    if right <= left or bottom <= top:
        return float("inf")

    crop = ImageOps.grayscale(image.crop(box))
    sample_width = 128
    sample_height = max(16, round(crop.height * sample_width / max(1, crop.width)))
    crop = crop.resize((sample_width, sample_height))

    edges = crop.filter(ImageFilter.FIND_EDGES)
    edge_mean = sum(edges.getdata()) / max(1, edges.width * edges.height)

    # Variance catches textured rock, foliage, clothing and other busy regions
    # that may not have strong single-pixel edges.
    stats = crop.resize((1, 1))
    mean = float(stats.getpixel((0, 0)))
    squares = crop.resize((32, 32))
    variance = sum((float(pixel) - mean) ** 2 for pixel in squares.getdata()) / max(
        1, squares.width * squares.height
    )

    return edge_mean * 0.78 + min(255.0, variance ** 0.5) * 0.22


def _region_subject_occupancy(image: Image.Image, box: tuple[int, int, int, int]) -> float:
    """Estimate localized foreground/subject occupancy inside a candidate region.

    Mean detail alone can hide a person's legs or another foreground object when
    most of the candidate is quiet ground/background. We therefore inspect small
    tiles and use the strongest local detail as a subject-risk signal.
    """
    left, top, right, bottom = box
    if right <= left or bottom <= top:
        return 1.0

    crop = ImageOps.grayscale(image.crop(box))
    crop = crop.resize((48, 48))
    edges = crop.filter(ImageFilter.FIND_EDGES)

    tile_scores: list[float] = []
    rows, cols = 4, 3
    for row in range(rows):
        for col in range(cols):
            x1 = col * edges.width // cols
            x2 = (col + 1) * edges.width // cols
            y1 = row * edges.height // rows
            y2 = (row + 1) * edges.height // rows
            tile = edges.crop((x1, y1, x2, y2))
            stats = ImageStat.Stat(tile)
            mean = float(stats.mean[0]) / 255.0
            spread = min(1.0, float(stats.stddev[0]) / 96.0)
            tile_scores.append(min(1.0, mean + 0.50 * spread))

    if not tile_scores:
        return 1.0

    ordered = sorted(tile_scores, reverse=True)
    top_quartile = ordered[:max(1, len(ordered) // 4)]
    return 0.65 * sum(top_quartile) / len(top_quartile) + 0.35 * sum(tile_scores) / len(tile_scores)


def _overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[2], b[2])
    bottom = min(a[3], b[3])
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    area = max(1, (a[2] - a[0]) * (a[3] - a[1]))
    return intersection / area


def _candidate_positions(
    image: Image.Image,
    width: int,
    height: int,
    safe_margin: int,
) -> list[tuple[int, int, int, int]]:
    max_left = max(safe_margin, image.width - safe_margin - width)
    max_top = max(safe_margin, image.height - safe_margin - height)

    # Every candidate is clamped before creating the rectangle. This is critical:
    # never shrink the selected box after text was fitted to it, otherwise the last
    # characters can be clipped at the image edge.
    raw_x_values = (
        safe_margin,
        (image.width - width) // 2,
        max_left,
        round(image.width * 0.18) - width // 2,
        round(image.width * 0.82) - width // 2,
    )
    raw_y_values = (
        safe_margin,
        round(image.height * 0.25) - height // 2,
        (image.height - height) // 2,
        round(image.height * 0.75) - height // 2,
        max_top,
    )
    x_values = sorted({min(max(safe_margin, x), max_left) for x in raw_x_values})
    y_values = sorted({min(max(safe_margin, y), max_top) for y in raw_y_values})

    return [
        (x, y, x + width, y + height)
        for y in y_values
        for x in x_values
    ]


def _choose_text_position(
    image: Image.Image,
    width: int,
    height: int,
    safe_margin: int,
    occupied: list[tuple[int, int, int, int]],
) -> tuple[int, int, int, int, str]:
    candidates = _candidate_positions(image, width, height, safe_margin)
    scored: list[tuple[float, tuple[int, int, int, int], str]] = []

    for box in candidates:
        overlap = max((_overlap_ratio(box, other) for other in occupied), default=0.0)
        if overlap > 0.02:
            continue

        detail = _region_detail(image, box)
        subject_occupancy = _region_subject_occupancy(image, box)

        # Mean detail can miss a localized foreground subject: a candidate may
        # contain mostly quiet ground while a person's legs, body, weapon, or
        # another important object occupies only one or two tiles. Strong local
        # occupancy therefore carries a separate penalty.
        subject_penalty = subject_occupancy * 42.0

        # Prefer the upper/lower thirds over the visual center when detail is
        # comparable; the center is where primary action/characters commonly sit.
        center_y = (box[1] + box[3]) / 2 / max(1, image.height)
        center_penalty = max(0.0, 1.0 - abs(center_y - 0.5) / 0.5) * 7.0

        score = detail + subject_penalty + center_penalty
        scored.append((score, box, "low-detail subject-safe text region"))

    if not scored:
        box = (
            safe_margin,
            safe_margin,
            min(image.width - safe_margin, safe_margin + width),
            min(image.height - safe_margin, safe_margin + height),
        )
        return (*box, "fallback text region")

    _, box, label = min(scored, key=lambda item: item[0])
    return (*box, label)


def render_overlays(
    source_path: str | Path,
    destination_path: str | Path,
    overlays: list[dict[str, Any]],
    *,
    safe_margin_percent: float = 7.0,
    default_max_width_percent: float = 80.0,
    default_max_height_percent: float = 30.0,
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

    # Work on a transparent layer so the artwork is never covered by a box.
    overlay_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_layer, "RGBA")

    safe_margin = round(image.width * safe_margin_percent / 100.0)
    occupied: list[tuple[int, int, int, int]] = []
    boxes: list[dict[str, Any]] = []
    selected_font = _font_path()

    for item in normalized:
        max_width = min(
            round(image.width * min(82.0, float(item["max_width_percent"])) / 100.0),
            image.width - 2 * safe_margin,
        )
        max_height = min(
            round(image.height * min(34.0, float(item["max_height_percent"])) / 100.0),
            image.height - 2 * safe_margin,
        )
        text_padding = max(4, round(image.width * 0.012))
        available_width = max(80, max_width - 2 * text_padding)

        # Use a stable production baseline instead of scaling from the shorter
        # image dimension. This keeps 768px-wide and 896px-wide mobile renders
        # visually consistent while preserving the larger, cinematic type treatment.
        preferred_font_size = max(56, round(image.width * 0.060))
        start_size = preferred_font_size
        font, lines, spacing, text_width, text_height = _fit_text(
            draw,
            item["text"],
            available_width,
            max(60, max_height - 2 * text_padding),
            start_size,
            min_size=22,
        )

        stroke_width = max(2, round(getattr(font, "size", 28) * 0.055))
        shadow_offset = max(2, round(getattr(font, "size", 28) * 0.045))

        box_width = min(
            max_width,
            max(120, text_width + 2 * text_padding + 2 * stroke_width),
        )
        box_height = min(
            max_height,
            max(50, text_height + 2 * text_padding + 2 * stroke_width),
        )

        left, top, right, bottom, placement = _choose_text_position(
            image,
            box_width,
            box_height,
            safe_margin,
            occupied,
        )
        actual_width = right - left
        actual_height = bottom - top

        if actual_width < text_width + 2 * stroke_width:
            raise OverlayRenderError(
                f"overlay box became narrower than fitted text: "
                f"{actual_width} < {text_width + 2 * stroke_width}"
            )
        if actual_height < text_height + 2 * stroke_width:
            raise OverlayRenderError(
                f"overlay box became shorter than fitted text: "
                f"{actual_height} < {text_height + 2 * stroke_width}"
            )

        # Defensive invariant: the final rectangle must remain fully inside the
        # safe area and must be at least as wide/high as the fitted text.
        if actual_width < text_width + 2 * stroke_width:
            raise OverlayRenderError(
                f"overlay box became narrower than fitted text: "
                f"{actual_width} < {text_width + 2 * stroke_width}"
            )
        if actual_height < text_height + 2 * stroke_width:
            raise OverlayRenderError(
                f"overlay box became shorter than fitted text: "
                f"{actual_height} < {text_height + 2 * stroke_width}"
            )
        occupied.append((left, top, right, bottom))

        # Center the text inside the selected transparent region. The region
        # itself has no fill; only glyphs, outline and a restrained shadow exist.
        text_x = left + max(0, (actual_width - text_width) // 2)
        text_y = top + max(0, (actual_height - text_height) // 2)

        bbox = font.getbbox("Ag")
        line_height = max(1, bbox[3] - bbox[1])

        for line in lines:
            # Very subtle shadow gives readability over bright clouds/water
            # without turning the overlay into a UI card.
            draw.text(
                (text_x + shadow_offset, text_y + shadow_offset),
                line,
                font=font,
                fill=SHADOW,
                stroke_width=stroke_width + 1,
                stroke_fill=SHADOW,
            )
            draw.text(
                (text_x, text_y),
                line,
                font=font,
                fill=TEXT,
                stroke_width=stroke_width,
                stroke_fill=STROKE,
            )
            text_y += line_height + spacing

        boxes.append({
            "box_number": item["box_number"],
            "box_type": item["box_type"],
            "text": item["text"],
            "required": item["required"],
            "x": left,
            "y": top,
            "width": actual_width,
            "height": actual_height,
            "font_size": getattr(font, "size", None),
            "line_count": len(lines),
            "placement": placement,
            "background": "transparent",
            "text_color": "#F7F0DC",
            "outline_color": "#080B0D",
            "outline_width": stroke_width,
        })

    result_image = Image.alpha_composite(image, overlay_layer).convert("RGB")
    result_image.save(destination, format="PNG")

    return {
        "rendered": True,
        "boxes": boxes,
        "font": selected_font or "Pillow default",
        "placement": "independent low-detail regions",
        "style": {
            "background": "transparent",
            "text": "#F7F0DC",
            "outline": "#080B0D",
            "shadow": "#000000",
            "font_family": Path(selected_font).stem if selected_font else "Pillow default",
            "font_style": "ancient serif / period book",
            "max_width_percent": default_max_width_percent,
            "max_height_percent": default_max_height_percent,
            "placement_algorithm": "grid search over low-detail subject-safe regions with localized foreground occupancy penalty, overlap avoidance, and center-action penalty",
        },
    }
