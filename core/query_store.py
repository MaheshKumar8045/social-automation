from __future__ import annotations

import argparse
import json

from core.document_store import DocumentStore


def main():
    parser = argparse.ArgumentParser(
        description="Run read-only SQL queries against a document store."
    )
    parser.add_argument("database")
    parser.add_argument("sql")
    args = parser.parse_args()

    store = DocumentStore(args.database)
    rows = store.query(args.sql)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
