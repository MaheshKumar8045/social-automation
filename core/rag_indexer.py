from __future__ import annotations

import argparse
from pathlib import Path
from core.document_store import DocumentStore


def build_rag_index(database_path: str | Path, document_id: int) -> int:
    """Build/rebuild the queryable FTS5 retrieval layer without opening the PDF."""
    with DocumentStore(database_path) as store:
        count = store.build_rag_index(document_id)
    print(f"RAG records: {count}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the SQLite FTS5 RAG index from an existing document store.")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    args = parser.parse_args()
    build_rag_index(args.database, args.document_id)

if __name__ == "__main__":
    main()
