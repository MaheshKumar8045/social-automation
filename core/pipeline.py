from __future__ import annotations

import csv
import sys
from pathlib import Path

from core.document_store import DocumentStore
from core.structure_scanner import StructureScanner


def _write_chapter_index(
    structure,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "chapter_number",
                "title",
                "page_number",
            ]
        )

        for section in structure.sections:
            writer.writerow(
                [
                    section.section_number or "",
                    section.title,
                    section.page_number,
                ]
            )


def _write_sections_csv(
    structure,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sections = sorted(
        structure.sections,
        key=lambda section: (
            section.page_number,
            -section.confidence,
        ),
    )

    scanned_page_end = max(
        (page.page_number for page in structure.pages),
        default=0,
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        writer = csv.writer(handle)

        writer.writerow(
            [
                "section_order",
                "section_number",
                "title",
                "page_start",
                "page_end",
                "confidence",
                "detection_method",
            ]
        )

        for index, section in enumerate(
            sections,
            start=1,
        ):
            if index < len(sections):
                page_end = max(
                    section.page_number,
                    sections[index].page_number - 1,
                )
            else:
                page_end = scanned_page_end

            writer.writerow(
                [
                    index,
                    section.section_number or "",
                    section.title,
                    section.page_number,
                    page_end,
                    round(section.confidence, 3),
                    section.detection_method,
                ]
            )


def run(
    pdf_path: str | Path,
    *,
    max_pages: int | None = None,
    chunk_size: int = 2000,
    chunk_overlap: int = 200,
):
    """
    Run the complete document-processing pipeline.

    Outputs are generated beside the source PDF:

        <name>_chapter_index.csv
        <name>_sections.csv
        <name>_structure.db
        <name>_structure.json

    SQLite is the canonical queryable store for downstream RAG,
    analytics, filtering, and JSON generation.
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    output_dir = pdf_path.parent
    book_name = pdf_path.stem

    chapter_index_path = (
        output_dir / f"{book_name}_chapter_index.csv"
    )
    sections_path = (
        output_dir / f"{book_name}_sections.csv"
    )
    database_path = (
        output_dir / f"{book_name}_structure.db"
    )
    json_path = (
        output_dir / f"{book_name}_structure.json"
    )

    print("=" * 60)
    print("BOOK PROCESSING PIPELINE")
    print("=" * 60)
    print(f"Input PDF: {pdf_path}")
    print()

    scanner = StructureScanner()
    structure = scanner.scan(
        pdf_path,
        max_pages=max_pages,
    )

    _write_chapter_index(
        structure,
        chapter_index_path,
    )

    _write_sections_csv(
        structure,
        sections_path,
    )

    with DocumentStore(database_path) as store:
        document_id = store.save_structure(
            structure,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        store.export_json(
            document_id,
            json_path,
        )

    print()
    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Chapter index: {chapter_index_path}")
    print(f"Sections CSV:  {sections_path}")
    print(f"SQLite store:  {database_path}")
    print(f"JSON export:   {json_path}")
    print(f"Document ID:   {document_id}")
    print(f"Sections:      {len(structure.sections)}")
    print(f"Pages stored:  {len(structure.pages)}")

    return structure, document_id


def main():
    if len(sys.argv) not in {2, 3}:
        print(
            "Usage:\n"
            '  python -m core.pipeline "data\\mybook.pdf"\n'
            '  python -m core.pipeline "data\\mybook.pdf" 40'
        )
        raise SystemExit(1)

    max_pages = (
        int(sys.argv[2])
        if len(sys.argv) == 3
        else None
    )

    run(
        sys.argv[1],
        max_pages=max_pages,
    )


if __name__ == "__main__":
    main()
