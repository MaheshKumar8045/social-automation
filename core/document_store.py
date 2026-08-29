from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from core.models import DocumentStructure, PageRecord
from core.layout_section_validator import ValidatedSection
from core.story_segmenter import StorySegmenter
from core.scene_segmenter import SceneSegmenter
from core.entity_extractor import EntityExtractor
from core.entity_resolver import EntityResolver


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
    raw_text TEXT NOT NULL DEFAULT '',
    quality_score REAL NOT NULL DEFAULT 0,
    normalization_method TEXT NOT NULL DEFAULT '',
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

CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    story_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    text TEXT NOT NULL,
    segmentation_method TEXT NOT NULL,
    confidence REAL NOT NULL,
    UNIQUE(document_id, story_order)
);

CREATE INDEX IF NOT EXISTS idx_stories_document_section
    ON stories(document_id, section_id);

CREATE INDEX IF NOT EXISTS idx_stories_document_order
    ON stories(document_id, story_order);

CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    scene_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    text TEXT NOT NULL,
    segmentation_method TEXT NOT NULL,
    confidence REAL NOT NULL,
    UNIQUE(document_id, story_id, scene_order)
);

CREATE INDEX IF NOT EXISTS idx_scenes_document_story
    ON scenes(document_id, story_id, scene_order);

CREATE INDEX IF NOT EXISTS idx_scenes_document_page
    ON scenes(document_id, page_start);

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    profile_text TEXT NOT NULL,
    confidence REAL NOT NULL,
    discovery_method TEXT NOT NULL,
    UNIQUE(document_id, entity_type, canonical_name)
);

CREATE TABLE IF NOT EXISTS entity_mentions (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    mention_text TEXT NOT NULL,
    context TEXT NOT NULL,
    confidence REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entities_document_type
    ON entities(document_id, entity_type);

CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity
    ON entity_mentions(entity_id);

CREATE INDEX IF NOT EXISTS idx_entity_mentions_scene
    ON entity_mentions(scene_id);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    resolution_method TEXT NOT NULL,
    confidence REAL NOT NULL,
    UNIQUE(document_id, entity_id, alias)
);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_document_alias
    ON entity_aliases(document_id, alias);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_entity
    ON entity_aliases(entity_id);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    event_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    text TEXT NOT NULL,
    discovery_method TEXT NOT NULL,
    confidence REAL NOT NULL,
    UNIQUE(document_id, scene_id, event_order)
);

CREATE INDEX IF NOT EXISTS idx_events_document_scene
    ON events(document_id, scene_id, event_order);


CREATE TABLE IF NOT EXISTS rag_documents (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    parent_type TEXT,
    parent_id INTEGER,
    title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(document_id, source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_rag_documents_document
    ON rag_documents(document_id, source_type);

CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(
    title,
    text,
    content='rag_documents',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS rag_documents_ai AFTER INSERT ON rag_documents BEGIN
    INSERT INTO rag_fts(rowid, title, text)
    VALUES (new.id, new.title, new.text);
END;

CREATE TRIGGER IF NOT EXISTS rag_documents_ad AFTER DELETE ON rag_documents BEGIN
    INSERT INTO rag_fts(rag_fts, rowid, title, text)
    VALUES ('delete', old.id, old.title, old.text);
END;

CREATE TRIGGER IF NOT EXISTS rag_documents_au AFTER UPDATE ON rag_documents BEGIN
    INSERT INTO rag_fts(rag_fts, rowid, title, text)
    VALUES ('delete', old.id, old.title, old.text);
    INSERT INTO rag_fts(rowid, title, text)
    VALUES (new.id, new.title, new.text);
END;

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
            self._ensure_column(connection, "pages", "raw_text", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "pages", "quality_score", "REAL NOT NULL DEFAULT 0")
            self._ensure_column(connection, "pages", "normalization_method", "TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _ensure_column(connection, table: str, column: str, definition: str) -> None:
        names={row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in names:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

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
                         source, ocr_used, text, raw_text,
                         quality_score, normalization_method)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        page.page_number,
                        page.page_type,
                        page.source,
                        int(page.ocr_used),
                        page.text,
                        page.raw_text,
                        page.quality_score,
                        page.normalization_method,
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

            # Baseline story segmentation is source-grounded: one detected
            # section becomes one story unit. A semantic segmenter can later
            # replace this strategy without changing the storage contract.
            stories = StorySegmenter().segment(structure)
            section_ids_by_order = {
                int(row["section_order"]): int(row["id"])
                for row in section_db_rows
            }
            story_rows = []
            for story in stories:
                section_id = section_ids_by_order.get(story.section_order)
                if section_id is None:
                    continue
                story_rows.append(
                    (
                        document_id,
                        section_id,
                        story.story_order,
                        story.title,
                        story.page_start,
                        story.page_end,
                        story.text,
                        story.segmentation_method,
                        story.confidence,
                    )
                )

            connection.executemany(
                """
                INSERT INTO stories
                    (document_id, section_id, story_order, title,
                     page_start, page_end, text,
                     segmentation_method, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                story_rows,
            )

            story_db_rows = connection.execute(
                """
                SELECT id, story_order, title, page_start, page_end, text
                FROM stories
                WHERE document_id = ?
                ORDER BY story_order
                """,
                (document_id,),
            ).fetchall()

            scene_rows = []
            segmenter = SceneSegmenter()
            for story_row in story_db_rows:
                story_data = dict(story_row)
                page_rows_for_story = connection.execute(
                    """
                    SELECT page_number, text
                    FROM pages
                    WHERE document_id = ?
                      AND page_number BETWEEN ? AND ?
                    ORDER BY page_number
                    """,
                    (
                        document_id,
                        int(story_row["page_start"]),
                        int(story_row["page_end"]),
                    ),
                ).fetchall()
                page_text = {
                    int(row["page_number"]): str(row["text"] or "")
                    for row in page_rows_for_story
                }
                scenes = segmenter.segment(
                    story_data,
                    page_text=page_text,
                )
                for scene in scenes:
                    scene_rows.append(
                        (
                            document_id,
                            int(story_row["id"]),
                            scene.scene_order,
                            scene.title,
                            scene.page_start,
                            scene.page_end,
                            scene.text,
                            scene.segmentation_method,
                            scene.confidence,
                        )
                    )

            connection.executemany(
                """
                INSERT INTO scenes
                    (document_id, story_id, scene_order, title,
                     page_start, page_end, text,
                     segmentation_method, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                scene_rows,
            )

            self._build_entity_layer(connection, document_id)

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

            self._build_rag_index(connection, document_id)
            return document_id


    def _build_rag_index(
        self,
        connection: sqlite3.Connection,
        document_id: int,
    ) -> None:
        """Rebuild the source-grounded retrieval index for one document."""
        connection.execute(
            "DELETE FROM rag_documents WHERE document_id = ?",
            (document_id,),
        )

        rows = connection.execute(
            """
            SELECT id, title, page_start, page_end
            FROM sections
            WHERE document_id = ?
            ORDER BY section_order
            """,
            (document_id,),
        ).fetchall()
        for row in rows:
            page_text = connection.execute(
                """
                SELECT text
                FROM pages
                WHERE document_id = ?
                  AND page_number BETWEEN ? AND ?
                ORDER BY page_number
                """,
                (document_id, int(row["page_start"]), int(row["page_end"])),
            ).fetchall()
            section_text = "\n\n".join(
                str(r["text"] or "") for r in page_text if str(r["text"] or "").strip()
            )
            connection.execute(
                """
                INSERT INTO rag_documents
                    (document_id, source_type, source_id, parent_type,
                     parent_id, title, text, page_start, page_end, metadata_json)
                VALUES (?, 'section', ?, NULL, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    document_id, int(row["id"]), str(row["title"] or ""),
                    section_text,
                    int(row["page_start"]), int(row["page_end"]),
                    json.dumps({"section_id": int(row["id"])}, ensure_ascii=False),
                ),
            )

        rows = connection.execute(
            """
            SELECT id, section_id, title, text, page_start, page_end
            FROM stories
            WHERE document_id = ?
            ORDER BY story_order
            """,
            (document_id,),
        ).fetchall()
        for row in rows:
            connection.execute(
                """
                INSERT INTO rag_documents
                    (document_id, source_type, source_id, parent_type,
                     parent_id, title, text, page_start, page_end, metadata_json)
                VALUES (?, 'story', ?, 'section', ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id, int(row["id"]), int(row["section_id"]),
                    str(row["title"] or ""), str(row["text"] or ""),
                    int(row["page_start"]), int(row["page_end"]),
                    json.dumps({"story_id": int(row["id"]), "section_id": int(row["section_id"])}, ensure_ascii=False),
                ),
            )

        rows = connection.execute(
            """
            SELECT id, story_id, title, text, page_start, page_end
            FROM scenes
            WHERE document_id = ?
            ORDER BY story_id, scene_order
            """,
            (document_id,),
        ).fetchall()
        for row in rows:
            connection.execute(
                """
                INSERT INTO rag_documents
                    (document_id, source_type, source_id, parent_type,
                     parent_id, title, text, page_start, page_end, metadata_json)
                VALUES (?, 'scene', ?, 'story', ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id, int(row["id"]), int(row["story_id"]),
                    str(row["title"] or ""), str(row["text"] or ""),
                    int(row["page_start"]), int(row["page_end"]),
                    json.dumps({"scene_id": int(row["id"]), "story_id": int(row["story_id"])}, ensure_ascii=False),
                ),
            )

        rows = connection.execute(
            """
            SELECT id, page_number, text
            FROM pages
            WHERE document_id = ?
              AND length(trim(text)) > 0
            ORDER BY page_number
            """,
            (document_id,),
        ).fetchall()
        for row in rows:
            connection.execute(
                """
                INSERT INTO rag_documents
                    (document_id, source_type, source_id, title, text,
                     page_start, page_end, metadata_json)
                VALUES (?, 'page', ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id, int(row["id"]), f"Page {int(row['page_number'])}",
                    str(row["text"] or ""), int(row["page_number"]),
                    int(row["page_number"]),
                    json.dumps({"page_id": int(row["id"]), "page_number": int(row["page_number"])}, ensure_ascii=False),
                ),
            )

        rows = connection.execute(
            """
            SELECT id, page_number, section_id, text
            FROM chunks
            WHERE document_id = ?
              AND length(trim(text)) > 0
            ORDER BY page_number, id
            """,
            (document_id,),
        ).fetchall()
        for row in rows:
            connection.execute(
                """
                INSERT INTO rag_documents
                    (document_id, source_type, source_id, parent_type,
                     parent_id, title, text, page_start, page_end, metadata_json)
                VALUES (?, 'chunk', ?, 'section', ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id, int(row["id"]), 
                    int(row["section_id"]) if row["section_id"] is not None else None,
                    f"Page {int(row['page_number'])} chunk",
                    str(row["text"] or ""), int(row["page_number"]),
                    int(row["page_number"]),
                    json.dumps({"chunk_id": int(row["id"]), "page_number": int(row["page_number"]), "section_id": row["section_id"]}, ensure_ascii=False),
                ),
            )

        rows = connection.execute(
            """
            SELECT id, entity_type, canonical_name, profile_text
            FROM entities
            WHERE document_id = ?
            ORDER BY entity_type, canonical_name
            """,
            (document_id,),
        ).fetchall()
        for row in rows:
            text = str(row["profile_text"] or "")
            title = f"{row['entity_type']}: {row['canonical_name']}"
            connection.execute(
                """
                INSERT INTO rag_documents
                    (document_id, source_type, source_id, title, text, metadata_json)
                VALUES (?, 'entity', ?, ?, ?, ?)
                """,
                (
                    document_id, int(row["id"]), title, text,
                    json.dumps({"entity_id": int(row["id"]), "entity_type": row["entity_type"]}, ensure_ascii=False),
                ),
            )

        rows = connection.execute(
            """
            SELECT id, scene_id, title, text, page_start, page_end
            FROM events
            WHERE document_id = ?
            ORDER BY scene_id, event_order
            """,
            (document_id,),
        ).fetchall()
        for row in rows:
            connection.execute(
                """
                INSERT INTO rag_documents
                    (document_id, source_type, source_id, parent_type,
                     parent_id, title, text, page_start, page_end, metadata_json)
                VALUES (?, 'event', ?, 'scene', ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id, int(row["id"]), int(row["scene_id"]),
                    str(row["title"] or ""), str(row["text"] or ""),
                    int(row["page_start"]), int(row["page_end"]),
                    json.dumps({"event_id": int(row["id"]), "scene_id": int(row["scene_id"])}, ensure_ascii=False),
                ),
            )

    def build_rag_index(self, document_id: int) -> int:
        """Rebuild retrieval records for an already stored document."""
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            if exists is None:
                raise ValueError(f"Unknown document id: {document_id}")
            self._build_rag_index(connection, document_id)
            return int(connection.execute(
                "SELECT COUNT(*) FROM rag_documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()[0])

    def search_rag(
        self,
        document_id: int,
        query: str,
        *,
        limit: int = 8,
        source_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search source-grounded retrieval records using SQLite FTS5/BM25."""
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        tokens = [
            token.replace('"', " ").strip()
            for token in query.strip().split()
        ]
        tokens = [token for token in tokens if token]
        if not tokens:
            raise ValueError("query must contain searchable terms")
        # Quote each token so punctuation in names (e.g. initials or hyphens)
        # cannot accidentally become FTS5 operators.
        match = " ".join(f'"{token}"' for token in tokens)

        filters = ["r.document_id = ?"]
        params = [match, document_id]
        if source_type is not None:
            filters.append("r.source_type = ?")
            params.append(source_type)
        params.append(limit)

        sql = f"""
            SELECT
                r.id,
                r.source_type,
                r.source_id,
                r.parent_type,
                r.parent_id,
                r.title,
                r.text,
                r.page_start,
                r.page_end,
                r.metadata_json,
                bm25(rag_fts) AS score
            FROM rag_fts
            JOIN rag_documents r ON r.id = rag_fts.rowid
            WHERE rag_fts MATCH ?
              AND {' AND '.join(filters)}
            ORDER BY score
            LIMIT ?
        """
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

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

    def get_stories(
        self,
        document_id: int,
        section_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if section_id is None:
            return self.query(
                """
                SELECT *
                FROM stories
                WHERE document_id = ?
                ORDER BY story_order
                """,
                (document_id,),
            )

        return self.query(
            """
            SELECT *
            FROM stories
            WHERE document_id = ?
              AND section_id = ?
            ORDER BY story_order
            """,
            (document_id, section_id),
        )

    def get_scenes(
        self,
        document_id: int,
        story_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if story_id is None:
            return self.query(
                """
                SELECT *
                FROM scenes
                WHERE document_id = ?
                ORDER BY story_id, scene_order
                """,
                (document_id,),
            )

        return self.query(
            """
            SELECT *
            FROM scenes
            WHERE document_id = ?
              AND story_id = ?
            ORDER BY scene_order
            """,
            (document_id, story_id),
        )

    def _build_entity_layer(
        self,
        connection: sqlite3.Connection,
        document_id: int,
    ) -> None:
        """Populate the source-grounded entity/event layer for one document."""
        connection.execute(
            "DELETE FROM entity_mentions WHERE document_id = ?",
            (document_id,),
        )
        connection.execute(
            "DELETE FROM events WHERE document_id = ?",
            (document_id,),
        )
        connection.execute(
            "DELETE FROM entities WHERE document_id = ?",
            (document_id,),
        )

        rows = connection.execute(
            """
            SELECT id, story_id, scene_order, title,
                   page_start, page_end, text
            FROM scenes
            WHERE document_id = ?
            ORDER BY story_id, scene_order
            """,
            (document_id,),
        ).fetchall()

        scenes = [dict(row) for row in rows]
        entities, mentions, events = EntityExtractor().extract(scenes)

        entity_ids: dict[tuple[str, str], int] = {}
        for entity in entities:
            cursor = connection.execute(
                """
                INSERT INTO entities
                    (document_id, entity_type, canonical_name,
                     profile_text, confidence, discovery_method)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    entity.entity_type,
                    entity.canonical_name,
                    entity.profile_text,
                    entity.confidence,
                    entity.discovery_method,
                ),
            )
            entity_ids[(entity.entity_type, entity.canonical_name)] = int(
                cursor.lastrowid
            )

        for mention in mentions:
            entity_id = entity_ids.get(
                (mention.entity_type, mention.canonical_name)
            )
            if entity_id is None:
                continue
            connection.execute(
                """
                INSERT INTO entity_mentions
                    (document_id, entity_id, scene_id, story_id,
                     page_start, page_end, mention_text, context,
                     confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    entity_id,
                    mention.scene_id,
                    mention.story_id,
                    mention.page_start,
                    mention.page_end,
                    mention.mention_text,
                    mention.context,
                    mention.confidence,
                ),
            )

        for row in rows:
            connection.execute(
                """
                INSERT INTO events
                    (document_id, scene_id, event_order, title,
                     page_start, page_end, text,
                     discovery_method, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    int(row["id"]),
                    1,
                    str(row["title"] or f"Scene {row['scene_order']}"),
                    int(row["page_start"]),
                    int(row["page_end"]),
                    str(row["text"] or ""),
                    "scene_event",
                    0.4,
                ),
            )

        EntityResolver().resolve_connection(connection, document_id)

    def build_entity_layer(self, document_id: int) -> None:
        """Rebuild entities, mentions, and event candidates from stored scenes."""
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            if exists is None:
                raise ValueError(f"Unknown document id: {document_id}")
            self._build_entity_layer(connection, document_id)

    def get_entities(
        self,
        document_id: int,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if entity_type is None:
            return self.query(
                """
                SELECT *
                FROM entities
                WHERE document_id = ?
                ORDER BY entity_type, canonical_name
                """,
                (document_id,),
            )
        return self.query(
            """
            SELECT *
            FROM entities
            WHERE document_id = ?
              AND entity_type = ?
            ORDER BY canonical_name
            """,
            (document_id, entity_type),
        )

    def get_entity_mentions(
        self,
        document_id: int,
        entity_id: int | None = None,
        scene_id: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["document_id = ?"]
        parameters: list[Any] = [document_id]
        if entity_id is not None:
            clauses.append("entity_id = ?")
            parameters.append(entity_id)
        if scene_id is not None:
            clauses.append("scene_id = ?")
            parameters.append(scene_id)
        return self.query(
            f"""
            SELECT *
            FROM entity_mentions
            WHERE {' AND '.join(clauses)}
            ORDER BY page_start, scene_id, id
            """,
            parameters,
        )

    def get_entity_aliases(
        self,
        document_id: int,
        entity_id: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["document_id = ?"]
        parameters: list[Any] = [document_id]
        if entity_id is not None:
            clauses.append("entity_id = ?")
            parameters.append(entity_id)
        return self.query(
            f"""
            SELECT *
            FROM entity_aliases
            WHERE {' AND '.join(clauses)}
            ORDER BY entity_id, alias
            """,
            parameters,
        )

    def get_events(
        self,
        document_id: int,
        scene_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if scene_id is None:
            return self.query(
                """
                SELECT *
                FROM events
                WHERE document_id = ?
                ORDER BY scene_id, event_order
                """,
                (document_id,),
            )
        return self.query(
            """
            SELECT *
            FROM events
            WHERE document_id = ?
              AND scene_id = ?
            ORDER BY event_order
            """,
            (document_id, scene_id),
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
            "stories": self.get_stories(document_id),
            "scenes": self.get_scenes(document_id),
            "entities": self.get_entities(document_id),
            "entity_mentions": self.get_entity_mentions(document_id),
            "entity_aliases": self.get_entity_aliases(document_id),
            "events": self.get_events(document_id),
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
