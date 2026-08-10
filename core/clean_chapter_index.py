import csv
from pathlib import Path


INPUT = Path("data/chapter_index.csv")
OUTPUT = Path("data/sections.csv")


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


def main():
    rows = []

    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        book_number = 1
        last_chapter = None

        for row in reader:
            chapter = row["chapter_number"].strip()
            title = clean_title(row["title"])
            page = int(row["page_number"])

            # Ignore obvious front-matter false positives.
            if page < 19:
                continue

            # A chapter-number restart from a later chapter to I
            # marks the second book in this document.
            if (
                last_chapter is not None
                and chapter == "I"
                and last_chapter != "I"
            ):
                book_number += 1

            rows.append({
                "book_number": book_number,
                "chapter_number": chapter,
                "title": title,
                "page_number": page,
            })

            last_chapter = chapter

    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "book_number",
            "chapter_number",
            "title",
            "page_number",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Created: {OUTPUT}")
    print(f"Sections: {len(rows)}")
    print(f"Books: {book_number}")


if __name__ == "__main__":
    main()