import csv
from pathlib import Path

from core.pdf_reader import PDFReader
from core.ocr_engine import OCREngine
from core.section_detector import SectionDetector


PDF_PATH = Path(r"data\sample.pdf")
OUTPUT_PATH = Path(r"data\chapter_index.csv")


def main():
    reader = PDFReader(str(PDF_PATH))
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
            chapters.append(section)

            print(
                f"FOUND: Chapter {section.section_number} "
                f"| {section.title} "
                f"| PDF page {section.page_number}"
            )

    with OUTPUT_PATH.open(
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
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()