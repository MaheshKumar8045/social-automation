from __future__ import annotations

import argparse
import json
from core.document_store import DocumentStore


def search(database_path: str, document_id: int, query: str, limit: int = 8, source_type: str | None = None):
    with DocumentStore(database_path) as store:
        return store.search_rag(document_id, query, limit=limit, source_type=source_type)


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the source-grounded SQLite RAG index.")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--source-type", choices=["page", "chunk", "section", "story", "scene", "entity", "event"], default=None)
    args = parser.parse_args()
    print(json.dumps(search(args.database, args.document_id, args.query, args.limit, args.source_type), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
