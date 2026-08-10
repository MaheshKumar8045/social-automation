import csv
import sys
from pathlib import Path

from core.pdf_reader import PDFReader
from core.ocr_engine import OCREngine
from core.section_detector import SectionDetector


def build_chapter_index(
    pdf_path: str | Path,
    output_path: str | Path,
):
    pdf_path = Path(pdf_path)
    output_path = Path(output_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PDFReader(str(pdf_path))
    ocr = OCREngine()
    detector = SectionDetector()

    chapters = []

    print(f"PDF pages: {reader.page_count}")
    print("Scanning for chapters...")
    print()

    for page_number, image in reader.iter_pages(0, reader.page_count):
        result = ocr.process(image, page_number)

        section = detector.detect(
            page_number,
            result.lines,
        )

        if section is not None:
            # Ignore OCR false positives where the detected
            # chapter title is simply a page/header marker.
            if section.title.strip().upper() == "PAGE":
                continue

            chapters.append(section)

            print(
                f"FOUND: Chapter {section.section_number} "
                f"| {section.title} "
                f"| PDF page {section.page_number}"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.writer(f)

        writer.writerow(
            [
                "chapter_number",
                "title",
                "page_number",
            ]
        )

        for chapter in chapters:
            writer.writerow(
                [
                    chapter.section_number,
                    chapter.title,
                    chapter.page_number,
                ]
            )

    print()
    print(f"Chapters found: {len(chapters)}")
    print(f"Saved: {output_path}")

    return chapters


def main():
    if len(sys.argv) != 3:
        print(
            "Usage:\n"
            "  python -m core.chapter_indexer "
            "data\\mybook.pdf data\\mybook_chapter_index.csv"
        )
        raise SystemExit(1)

    build_chapter_index(
        sys.argv[1],
        sys.argv[2],
    )


if __name__ == "__main__":
    main()