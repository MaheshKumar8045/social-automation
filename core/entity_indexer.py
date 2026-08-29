from __future__ import annotations

import argparse
import csv
from pathlib import Path

from core.document_store import DocumentStore


def _write_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def build_entity_index(
    database_path: str | Path,
    document_id: int,
    output_dir: str | Path | None = None,
) -> tuple[Path, Path, Path]:
    """
    Build/rebuild the entity layer from an existing SQLite document.

    This operates only on stored stories/scenes. It never opens or OCRs the
    source PDF, making it safe for already-processed documents.
    """
    database_path = Path(database_path)
    if output_dir is None:
        output_dir = database_path.parent
    output_dir = Path(output_dir)

    with DocumentStore(database_path) as store:
        if store.get_document(document_id) is None:
            raise ValueError(f"Unknown document id: {document_id}")
        store.build_entity_layer(document_id)
        entities = store.get_entities(document_id)
        mentions = store.get_entity_mentions(document_id)
        events = store.get_events(document_id)

    stem = database_path.stem.replace("_structure", "")
    entities_path = output_dir / f"{stem}_entities.csv"
    mentions_path = output_dir / f"{stem}_entity_mentions.csv"
    events_path = output_dir / f"{stem}_events.csv"

    _write_csv(
        entities_path,
        ["id", "document_id", "entity_type", "canonical_name",
         "profile_text", "confidence", "discovery_method"],
        entities,
    )
    _write_csv(
        mentions_path,
        ["id", "document_id", "entity_id", "scene_id", "story_id",
         "page_start", "page_end", "mention_text", "context", "confidence"],
        mentions,
    )
    _write_csv(
        events_path,
        ["id", "document_id", "scene_id", "event_order", "title",
         "page_start", "page_end", "text", "discovery_method", "confidence"],
        events,
    )

    print(f"Entities: {len(entities)}")
    print(f"Mentions: {len(mentions)}")
    print(f"Events: {len(events)}")
    print(f"Entities CSV: {entities_path}")
    print(f"Mentions CSV: {mentions_path}")
    print(f"Events CSV: {events_path}")

    return entities_path, mentions_path, events_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build source-grounded entity/event indexes from an existing SQLite document."
    )
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    build_entity_index(
        args.database,
        args.document_id,
        args.output_dir,
    )


if __name__ == "__main__":
    main()
