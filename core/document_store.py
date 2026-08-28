from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from core.models import DocumentStructure, PageRecord
from core.layout_section_validator import ValidatedSection


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    page_count INTEGER NOT NULL,
    scanned_page_count INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    page_type TEXT NOT NULL,
    source TEXT NOT NULL,
    ocr_used INTEGER NOT NULL DEFAULT 0,
    text TEXT NOT NULL DEFAULT '',
    UNIQUE(document_id, page_number)
);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_order INTEGER NOT NULL,
    section_number TEXT,
    title TEXT NOT NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    confidence REAL NOT NULL,
    detection_method TEXT NOT NULL,
    UNIQUE(document_id, section_order)
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
    page_number INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    token_count INTEGER,
    UNIQUE(document_id, section_id, page_number, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_pages_document_page
    ON pages(document_id, page_number);

CREATE INDEX IF NOT EXISTS idx_sections_document_page
    ON sections(document_id, page_start);

CREATE INDEX IF NOT EXISTS idx_sections_document_number
    ON sections(document_id, section_number);

CREATE INDEX IF NOT EXISTS idx_chunks_document_section
    ON chunks(document_id, section_id);

CREATE INDEX IF NOT EXISTS idx_chunks_document_page
    ON chunks(document_id, page_number);
"""


class DocumentStore:
    """
    SQLite-backed, queryable document store.

    The database is intentionally independent of any vector database.
    It stores source text and structural metadata so downstream RAG,
    analytics, JSON export, and embedding pipelines can use one stable
    source of truth.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def save_structure(
        self,
        structure: DocumentStructure,
        *,
        chunk_size: int = 2000,
        chunk_overlap: int = 200,
    ) -> int:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be >= 0 and less than chunk_size"
            )

        pages = sorted(
            structure.pages,
            key=lambda page: page.page_number,
        )
        sections = sorted(
            (
                section
                for section in structure.sections
                if section.page_number >= 1
            ),
            key=lambda section: (
                section.page_number,
                -section.confidence,
            ),
        )

        # A bounded scan (e.g. max_pages=40) must never assign section
        # content beyond the pages that were actually persisted.
        scanned_page_end = (
            max((page.page_number for page in pages), default=0)
        )

        sections = [
            section
            for section in sections
            if section.page_number <= scanned_page_end
        ]

        with self._connect() as connection:
            connection.execute(
                "DELETE FROM documents WHERE path = ?",
                (str(structure.pdf_path.resolve()),),
            )

            cursor = connection.execute(
                """
                INSERT INTO documents
                    (filename, path, page_count,
                     scanned_page_count, document_type)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    structure.pdf_path.name,
                    str(structure.pdf_path.resolve()),
                    structure.total_pages,
                    len(pages),
                    structure.document_type or self._document_type(pages),
                ),
            )
            document_id = int(cursor.lastrowid)

            for page in pages:
                connection.execute(
                    """
                    INSERT INTO pages
                        (document_id, page_number, page_type,
                         source, ocr_used, text)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        page.page_number,
                        page.page_type,
                        page.source,
                        int(page.ocr_used),
                        page.text,
                    ),
                )

            section_rows = []
            for index, section in enumerate(sections, start=1):
                next_page = (
                    sections[index].page_number
                    if index < len(sections)
                    else scanned_page_end + 1
                )
                page_end = min(
                    scanned_page_end,
                    max(
                        section.page_number,
                        next_page - 1,
                    ),
                )
                section_rows.append(
                    (
                        document_id,
                        index,
                        section.section_number,
                        section.title,
                        section.page_number,
                        page_end,
                        section.confidence,
                        section.detection_method,
                    )
                )

            connection.executemany(
                """
                INSERT INTO sections
                    (document_id, section_order, section_number,
                     title, page_start, page_end, confidence,
                     detection_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                section_rows,
            )

            section_db_rows = connection.execute(
                """
                SELECT id, section_order, page_start, page_end
                FROM sections
                WHERE document_id = ?
                ORDER BY section_order
                """,
                (document_id,),
            ).fetchall()

            for row in section_db_rows:
                section_id = int(row["id"])
                start = int(row["page_start"])
                end = int(row["page_end"])

                page_rows = connection.execute(
                    """
                    SELECT page_number, text
                    FROM pages
                    WHERE document_id = ?
                      AND page_number BETWEEN ? AND ?
                    ORDER BY page_number
                    """,
                    (document_id, start, end),
                ).fetchall()

                for page_row in page_rows:
                    self._insert_chunks(
                        connection,
                        document_id,
                        section_id,
                        int(page_row["page_number"]),
                        str(page_row["text"] or ""),
                        chunk_size,
                        chunk_overlap,
                    )

            # Preserve text from pages outside any detected section
            # as queryable chunks too.
            assigned_pages = set()
            for row in section_db_rows:
                assigned_pages.update(
                    range(
                        int(row["page_start"]),
                        int(row["page_end"]) + 1,
                    )
                )

            unassigned = connection.execute(
                """
                SELECT page_number, text
                FROM pages
                WHERE document_id = ?
                ORDER BY page_number
                """,
                (document_id,),
            ).fetchall()

            for page_row in unassigned:
                page_number = int(page_row["page_number"])
                if page_number in assigned_pages:
                    continue

                self._insert_chunks(
                    connection,
                    document_id,
                    None,
                    page_number,
                    str(page_row["text"] or ""),
                    chunk_size,
                    chunk_overlap,
                )

            return document_id

    def close(self) -> None:
        """Compatibility no-op.

        DocumentStore opens short-lived SQLite connections per operation,
        so there is no persistent connection to close.
        """
        return None

    def __enter__(self) -> "DocumentStore":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @staticmethod
    def _insert_chunks(
        connection: sqlite3.Connection,
        document_id: int,
        section_id: int | None,
        page_number: int,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:
        normalized = " ".join(text.split())

        if not normalized:
            return

        start = 0
        chunk_index = 0
        step = chunk_size - chunk_overlap

        while start < len(normalized):
            end = min(
                len(normalized),
                start + chunk_size,
            )
            chunk = normalized[start:end].strip()

            if chunk:
                connection.execute(
                    """
                    INSERT INTO chunks
                        (document_id, section_id, page_number,
                         chunk_index, text, char_count, token_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        section_id,
                        page_number,
                        chunk_index,
                        chunk,
                        len(chunk),
                        len(chunk.split()),
                    ),
                )

            if end >= len(normalized):
                break

            start += step
            chunk_index += 1

    @staticmethod
    def _document_type(pages: list[PageRecord]) -> str:
        if not pages:
            return "unknown"

        sources = {page.source for page in pages}

        if sources == {"pdf_text"}:
            return "text"

        if sources == {"ocr"}:
            return "scanned"

        return "mixed"

    def query(
        self,
        sql: str,
        parameters: Iterable[Any] = (),
    ) -> list[dict[str, Any]]:
        """Run a read-only SQL query and return dictionaries."""
        normalized = sql.lstrip().upper()

        if not (
            normalized.startswith("SELECT")
            or normalized.startswith("WITH")
            or normalized.startswith("PRAGMA")
        ):
            raise ValueError(
                "query() only permits read-only SQL statements"
            )

        with self._connect() as connection:
            rows = connection.execute(
                sql,
                tuple(parameters),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_document(self, document_id: int) -> dict[str, Any] | None:
        rows = self.query(
            "SELECT * FROM documents WHERE id = ?",
            (document_id,),
        )
        return rows[0] if rows else None

    def get_sections(self, document_id: int) -> list[dict[str, Any]]:
        return self.query(
            """
            SELECT *
            FROM sections
            WHERE document_id = ?
            ORDER BY section_order
            """,
            (document_id,),
        )

    def get_pages(
        self,
        document_id: int,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["document_id = ?"]
        parameters: list[Any] = [document_id]

        if start_page is not None:
            clauses.append("page_number >= ?")
            parameters.append(start_page)

        if end_page is not None:
            clauses.append("page_number <= ?")
            parameters.append(end_page)

        return self.query(
            f"""
            SELECT *
            FROM pages
            WHERE {' AND '.join(clauses)}
            ORDER BY page_number
            """,
            parameters,
        )

    def get_chunks(
        self,
        document_id: int,
        section_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if section_id is None:
            return self.query(
                """
                SELECT *
                FROM chunks
                WHERE document_id = ?
                ORDER BY page_number, chunk_index
                """,
                (document_id,),
            )

        return self.query(
            """
            SELECT *
            FROM chunks
            WHERE document_id = ?
              AND section_id = ?
            ORDER BY page_number, chunk_index
            """,
            (document_id, section_id),
        )

    def export_json(
        self,
        document_id: int,
        output_path: str | Path,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        document = self.get_document(document_id)
        if document is None:
            raise ValueError(
                f"Unknown document id: {document_id}"
            )

        payload = {
            "document": document,
            "sections": self.get_sections(document_id),
            "pages": self.get_pages(document_id),
            "chunks": self.get_chunks(document_id),
        }

        output_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return output_path
