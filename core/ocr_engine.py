from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image
from paddleocr import PaddleOCR


@dataclass
class OCRResult:
    """Structured OCR output for one page."""

    page_number: int
    text: str
    lines: list[str]
    scores: list[float]
    boxes: Any
    raw_result: Any


class OCREngine:
    """GPU-backed OCR engine using PaddleOCR."""

    def __init__(
        self,
        language: str = "en",
        device: str = "gpu:0",
    ):
        self.ocr = PaddleOCR(
            lang=language,
            device=device,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def process(
        self,
        image: Image.Image,
        page_number: int,
    ) -> OCRResult:
        """Run OCR on one page image."""

        image_array = np.asarray(image)
        results = list(self.ocr.predict(image_array))

        if not results:
            return OCRResult(
                page_number=page_number,
                text="",
                lines=[],
                scores=[],
                boxes=None,
                raw_result=None,
            )

        result = results[0]

        lines = list(result["rec_texts"])
        scores = [float(score) for score in result["rec_scores"]]
        boxes = result["rec_boxes"]

        text = "\n".join(lines)

        return OCRResult(
            page_number=page_number,
            text=text,
            lines=lines,
            scores=scores,
            boxes=boxes,
            raw_result=result,
        )