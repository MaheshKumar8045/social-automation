import csv
import sys
from pathlib import Path


def clean_title(title: str) -> str:
    replacements = {
        "â€”": "—",
        "â€“": "–",
        "â€˜": "‘",
        "â€™": "’",
        "â€œ": "“",
        "â€\x9d": "”",
        "â€¦": "…",
    }

    for bad, good in replacements.items():
        title = title.replace(bad, good)

    return title.strip()


def clean_chapter_index(input_path: str | Path, output_path: str | Path):
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Chapter index not found: {input_path}")

    rows = []

    with input_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            chapter = row["chapter_number"].strip()
            title = clean_title(row["title"])
            page = int(row["page_number"])

            rows.append(
                {
                    "chapter_number": chapter,
                    "title": title,
                    "page_number": page,
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        fieldnames = [
            "chapter_number",
            "title",
            "page_number",
        ]

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"Created: {output_path}")
    print(f"Sections: {len(rows)}")

    return rows


def main():
    if len(sys.argv) != 3:
        print(
            "Usage:\n"
            "  python -m core.clean_chapter_index "
            "data\\mybook_chapter_index.csv "
            "data\\mybook_sections.csv"
        )
        raise SystemExit(1)

    clean_chapter_index(
        sys.argv[1],
        sys.argv[2],
    )


if __name__ == "__main__":
    main()