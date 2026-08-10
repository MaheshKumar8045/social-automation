import sys
from pathlib import Path

from core.chapter_indexer import build_chapter_index
from core.clean_chapter_index import clean_chapter_index


def run(pdf_path: str | Path):
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Keep generated files together using the PDF filename.
    output_dir = pdf_path.parent
    book_name = pdf_path.stem

    chapter_index_path = (
        output_dir / f"{book_name}_chapter_index.csv"
    )

    sections_path = (
        output_dir / f"{book_name}_sections.csv"
    )

    print("=" * 60)
    print("BOOK PROCESSING PIPELINE")
    print("=" * 60)
    print(f"Input PDF: {pdf_path}")
    print()

    # Step 1: OCR the PDF and detect chapters.
    build_chapter_index(
        pdf_path,
        chapter_index_path,
    )

    print()

    # Step 2: Clean the detected chapter index.
    clean_chapter_index(
        chapter_index_path,
        sections_path,
    )

    print()
    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Chapter index: {chapter_index_path}")
    print(f"Sections:       {sections_path}")


def main():
    if len(sys.argv) != 2:
        print(
            "Usage:\n"
            '  python -m core.pipeline "data\\mybook.pdf"'
        )
        raise SystemExit(1)

    run(sys.argv[1])


if __name__ == "__main__":
    main()