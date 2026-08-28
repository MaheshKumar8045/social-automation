from pathlib import Path

from core.document_store import DocumentStore


def export_database_json(
    database_path: str | Path,
    output_path: str | Path,
    document_id: int | None = None,
) -> Path:
    """
    Export a SQLite document store to JSON.

    If document_id is omitted, the database must contain exactly one
    document.
    """
    store = DocumentStore(database_path)

    if document_id is None:
        rows = store.query(
            "SELECT id FROM documents ORDER BY id"
        )

        if len(rows) != 1:
            raise ValueError(
                "document_id is required when the database does not "
                "contain exactly one document"
            )

        document_id = int(rows[0]["id"])

    return store.export_json(
        document_id,
        output_path,
    )


# Backwards-compatible descriptive alias.
export_structure_json = export_database_json
