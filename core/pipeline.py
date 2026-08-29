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



def _write_scenes_csv(
    database_path: Path,
    document_id: int,
    output_path: Path,
) -> None:
    """Write deterministic source-grounded scene units."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with DocumentStore(database_path) as store:
        scenes = store.get_scenes(document_id)

    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "scene_id",
            "story_id",
            "scene_order",
            "title",
            "page_start",
            "page_end",
            "confidence",
            "segmentation_method",
            "text",
        ])
        for scene in scenes:
            writer.writerow([
                scene["id"],
                scene["story_id"],
                scene["scene_order"],
                scene["title"],
                scene["page_start"],
                scene["page_end"],
                round(scene["confidence"], 3),
                scene["segmentation_method"],
                scene["text"],
            ])


def _write_stories_csv(
    database_path: Path,
    document_id: int,
    output_path: Path,
) -> None:
    """Write the source-grounded story units produced by the pipeline."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with DocumentStore(database_path) as store:
        stories = store.get_stories(document_id)

    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "story_order",
            "section_id",
            "title",
            "page_start",
            "page_end",
            "confidence",
            "segmentation_method",
            "text",
        ])
        for story in stories:
            writer.writerow([
                story["story_order"],
                story["section_id"],
                story["title"],
                story["page_start"],
                story["page_end"],
                round(story["confidence"], 3),
                story["segmentation_method"],
                story["text"],
            ])


def _write_entities_csv(
    database_path: Path,
    document_id: int,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with DocumentStore(database_path) as store:
        entities = store.get_entities(document_id)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "entity_id", "entity_type", "canonical_name",
            "profile_text", "confidence", "discovery_method",
        ])
        for entity in entities:
            writer.writerow([
                entity["id"], entity["entity_type"], entity["canonical_name"],
                entity["profile_text"], round(entity["confidence"], 3),
                entity["discovery_method"],
            ])


def _write_entity_mentions_csv(
    database_path: Path,
    document_id: int,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with DocumentStore(database_path) as store:
        mentions = store.get_entity_mentions(document_id)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "mention_id", "entity_id", "scene_id", "story_id",
            "page_start", "page_end", "mention_text", "context",
            "confidence",
        ])
        for row in mentions:
            writer.writerow([
                row["id"], row["entity_id"], row["scene_id"], row["story_id"],
                row["page_start"], row["page_end"], row["mention_text"],
                row["context"], round(row["confidence"], 3),
            ])


def _write_entity_aliases_csv(database_path: Path, document_id: int, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with DocumentStore(database_path) as store:
        aliases = store.get_entity_aliases(document_id)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer=csv.writer(handle)
        writer.writerow(["alias_id","entity_id","alias","resolution_method","confidence"])
        for row in aliases:
            writer.writerow([row["id"],row["entity_id"],row["alias"],row["resolution_method"],round(row["confidence"],3)])

def _write_events_csv(
    database_path: Path,
    document_id: int,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with DocumentStore(database_path) as store:
        events = store.get_events(document_id)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "event_id", "scene_id", "event_order", "title",
            "page_start", "page_end", "confidence",
            "discovery_method", "text",
        ])
        for row in events:
            writer.writerow([
                row["id"], row["scene_id"], row["event_order"], row["title"],
                row["page_start"], row["page_end"], round(row["confidence"], 3),
                row["discovery_method"], row["text"],
            ])


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
        <name>_stories.csv
        <name>_scenes.csv

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
    stories_path = (
        output_dir / f"{book_name}_stories.csv"
    )
    scenes_path = (
        output_dir / f"{book_name}_scenes.csv"
    )
    entities_path = (
        output_dir / f"{book_name}_entities.csv"
    )
    mentions_path = (
        output_dir / f"{book_name}_entity_mentions.csv"
    )
    events_path = (
        output_dir / f"{book_name}_events.csv"
    )
    aliases_path = (
        output_dir / f"{book_name}_entity_aliases.csv"
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

    _write_stories_csv(
        database_path,
        document_id,
        stories_path,
    )

    _write_scenes_csv(
        database_path,
        document_id,
        scenes_path,
    )

    _write_entities_csv(
        database_path,
        document_id,
        entities_path,
    )

    _write_entity_mentions_csv(
        database_path,
        document_id,
        mentions_path,
    )

    _write_events_csv(
        database_path,
        document_id,
        events_path,
    )
    _write_entity_aliases_csv(
        database_path,
        document_id,
        aliases_path,
    )

    print()
    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Chapter index: {chapter_index_path}")
    print(f"Sections CSV:  {sections_path}")
    print(f"SQLite store:  {database_path}")
    print(f"JSON export:   {json_path}")
    print(f"Stories CSV:   {stories_path}")
    print(f"Scenes CSV:    {scenes_path}")
    print(f"Entities CSV:  {entities_path}")
    print(f"Mentions CSV:  {mentions_path}")
    print(f"Events CSV:    {events_path}")
    print(f"Aliases CSV:   {aliases_path}")
    print(f"Document ID:   {document_id}")
    print(f"Sections:      {len(structure.sections)}")
    with DocumentStore(database_path) as store:
        print(f"Stories:       {len(store.get_stories(document_id))}")
        print(f"Scenes:        {len(store.get_scenes(document_id))}")
        print(f"Entities:      {len(store.get_entities(document_id))}")
        print(f"Mentions:      {len(store.get_entity_mentions(document_id))}")
        print(f"Aliases:       {len(store.get_entity_aliases(document_id))}")
        print(f"Events:        {len(store.get_events(document_id))}")
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
