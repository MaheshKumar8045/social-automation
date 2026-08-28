import csv
from pathlib import Path

from core.structure_scanner import StructureScanner


def build_chapter_index(
    pdf_path: str | Path,
    output_path: str | Path,
):
    """
    Build a structural section index for any supported PDF.

    Detection is delegated to StructureScanner so the CLI and the
    structural pipeline use the same generic detection/recovery logic.
    """
    pdf_path = Path(pdf_path)
    output_path = Path(output_path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    structure = StructureScanner().scan(pdf_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
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

    print()
    print(f"Chapters found: {len(structure.sections)}")
    print(f"Saved: {output_path}")

    return structure.sections


def main():
    import sys

    if len(sys.argv) != 3:
        print(
            "Usage:\n"
            "  python -m core.chapter_indexer "
            "data\\mybook.pdf "
            "data\\mybook_chapter_index.csv"
        )
        raise SystemExit(1)

    build_chapter_index(
        sys.argv[1],
        sys.argv[2],
    )


if __name__ == "__main__":
    main()
