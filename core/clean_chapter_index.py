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

        for row in reader:
            chapter = row["chapter_number"].strip()
            title = clean_title(row["title"])
            page = int(row["page_number"])

            rows.append({
                "chapter_number": chapter,
                "title": title,
                "page_number": page,
            })

    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "chapter_number",
            "title",
            "page_number",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Created: {OUTPUT}")
    print(f"Sections: {len(rows)}")


if __name__ == "__main__":
    main()