from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _required_dialogue(overlays: list[dict[str, Any]]) -> list[str]:
    values = []
    for item in overlays:
        if item.get("required") is False:
            continue
        text = str(item.get("text") or "").strip()
        if text:
            values.append(text)
    return values


@lru_cache(maxsize=1)
def _ocr_engine():
    from paddleocr import PaddleOCR
    return PaddleOCR(
        lang=os.getenv("SOCIAL_AUTOMATION_OCR_LANG", "en"),
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def _ocr_text(path: Path) -> tuple[str | None, str | None]:
    try:
        ocr = _ocr_engine()
            lang=os.getenv("SOCIAL_AUTOMATION_OCR_LANG", "en"),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        result = ocr.predict(str(path))
        chunks: list[str] = []
        for item in result or []:
            if isinstance(item, dict):
                for key in ("rec_texts", "texts"):
                    values = item.get(key)
                    if isinstance(values, list):
                        chunks.extend(str(x) for x in values if str(x).strip())
            else:
                text = str(item)
                if text.strip():
                    chunks.append(text)
        return " ".join(chunks).strip(), None
    except Exception as exc:
        return None, f"PaddleOCR failed: {exc}"


def _vision_check(path: Path, context: dict[str, Any], model: str) -> dict[str, Any]:
    try:
        import ollama
    except Exception as exc:
        return {"status": "unavailable", "error": f"ollama package unavailable: {exc}"}
    try:
        request = {
            "task": "Tolerant validation of a generated cinematic story image. "
                    "Return REVIEW only for a clear contradiction or obvious mismatch.",
            "scene_title": context["title"],
            "image_prompt": context["prompt"],
            "required_dialogue": context["required_dialogue"],
            "canonical_visible_characters": context["visible_characters"],
            "story_context": context["story_context"],
            "previous_visual_state": (
                "A previous accepted image is supplied as the second image when available. "
                "Compare continuity only; do not require identical composition."
                if context["previous_visual_state"].get("image_path")
                else "No previous accepted image is available."
            ),
            "return_json": {
                "overall": "PASS or REVIEW",
                "visual_match": "0..1",
                "story_match": "0..1",
                "continuity_match": "0..1",
                "dialogue_visible": "true/false/unknown",
                "issues": ["only clear issues"]
            }
        }
        response = ollama.chat(
            model=model,
            messages=[{
                "role": "user",
                "content": (
                    "Analyze the attached image against this contract. "
                    "Be tolerant because the generation prompt is already refined. "
                    "Do not invent a failure for a plausible artistic interpretation. "
                    "Return JSON only.\n" + json.dumps(request, ensure_ascii=False)
                ),
                "images": [str(path)] + (
                    [str(context["previous_visual_state"]["image_path"])]
                    if context.get("previous_visual_state", {}).get("image_path")
                    and Path(context["previous_visual_state"]["image_path"]).exists()
                    else []
                ),
            }],
            options={"temperature": 0},
        )
        content = str(getattr(getattr(response, "message", None), "content", "") or "")
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            return {"status": "invalid_response", "raw": content[:4000]}
        parsed = json.loads(match.group(0))
        parsed["status"] = "ok"
        return parsed
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def validate_image(
    path: str | Path,
    *,
    prompt: str,
    overlays: list[dict[str, Any]],
    title: str,
    visible_characters: list[str],
    story_context: dict[str, Any] | None = None,
    previous_visual_state: dict[str, Any] | None = None,
    vision_enabled: bool = True,
    vision_model: str = "qwen2.5vl:7b",
) -> dict[str, Any]:
    image_path = Path(path)
    result: dict[str, Any] = {"status": "pass", "issues": [], "checks": {}}

    try:
        with Image.open(image_path) as image:
            image.verify()
        with Image.open(image_path) as image:
            width, height = image.size
            result["checks"]["image_readable"] = True
            result["checks"]["dimensions"] = [width, height]
            result["checks"]["aspect_ratio"] = round(width / height, 4) if height else 0
            result["checks"]["file_size_bytes"] = image_path.stat().st_size
            if width < 512 or height < 512:
                result["issues"].append("image resolution is unexpectedly small")
            if image_path.stat().st_size < 20_000:
                result["issues"].append("image file is unexpectedly small")
            stat = ImageStat.Stat(image.convert("RGB"))
            result["checks"]["mean_brightness"] = round(sum(stat.mean) / 3, 2)
    except Exception as exc:
        return {"status": "fail", "issues": [f"image unreadable: {exc}"], "checks": {}}

    required = _required_dialogue(overlays)
    # Clean AI-generated artwork must contain zero generated typography. Run OCR
    # on the clean stage as a hard guard; the deterministic overlay stage runs OCR
    # again to verify the exact source text.
    ocr_text: str | None = None
    ocr_error: str | None = None
    ocr_text, ocr_error = _ocr_text(image_path)
    result["checks"]["ocr_available"] = ocr_text is not None
    if ocr_error:
        result["checks"]["ocr_note"] = ocr_error

    if not required and ocr_text:
        normalized_ocr = _norm(ocr_text)
        tokens = [token for token in normalized_ocr.split() if token]
        if len(tokens) >= 2 or any(len(token) >= 12 for token in tokens):
            result["checks"]["unexpected_text"] = ocr_text[:500]
            result["issues"].append(
                "unexpected generated text detected in clean artwork; retrying image generation"
            )

    if required and ocr_text:
        normalized_ocr = _norm(ocr_text)
        dialogue_hits = []
        for expected in required:
            expected_norm = _norm(expected)
            dialogue_hits.append({
                "expected": expected,
                "found": expected_norm in normalized_ocr,
            })
        result["checks"]["dialogue"] = dialogue_hits
        if not all(x["found"] for x in dialogue_hits):
            result["issues"].append("required dialogue/narrative text was not confirmed by OCR")
    elif required:
        result["checks"]["dialogue"] = {"status": "not_verified", "required": required}

    if vision_enabled and vision_model:
        vision = _vision_check(
            image_path,
            {
                "title": title,
                "prompt": prompt,
                "required_dialogue": required,
                "visible_characters": visible_characters,
                "story_context": story_context or {},
                "previous_visual_state": previous_visual_state or {},
            },
            vision_model,
        )
        result["vision"] = vision
        if vision.get("status") == "ok":
            result["checks"]["vision_match"] = {
                "visual_match": vision.get("visual_match"),
                "story_match": vision.get("story_match"),
                "continuity_match": vision.get("continuity_match"),
            }
            if str(vision.get("overall", "")).upper() == "REVIEW":
                result["issues"].extend(str(x) for x in vision.get("issues", [])[:5])

    technical_failure = any(
        item.startswith("image unreadable")
        or item == "unexpected generated text detected in clean artwork; retrying image generation"
        or item in {"image resolution is unexpectedly small", "image file is unexpectedly small"}
        for item in result["issues"]
    )
    vision = result.get("vision", {})
    clear_semantic_failure = (
        isinstance(vision, dict)
        and vision.get("status") == "ok"
        and str(vision.get("overall", "")).upper() == "REVIEW"
        and (
            float(vision.get("visual_match") or 1) < 0.55
            or float(vision.get("story_match") or 1) < 0.55
        )
    )
    result["status"] = "fail" if technical_failure or clear_semantic_failure else "pass"
    return result
