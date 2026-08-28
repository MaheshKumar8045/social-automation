from dataclasses import dataclass


@dataclass
class TextFragment:
    """
    One piece of text together with its visual/layout information.

    Coordinates use the PDF page coordinate system when the
    fragment comes from a PDF text layer. OCR fragments can
    use the bounding-box coordinates supplied by the OCR engine.
    """

    text: str
    x: float | None = None
    y: float | None = None
    font_size: float | None = None
    confidence: float | None = None
    width: float | None = None
    height: float | None = None