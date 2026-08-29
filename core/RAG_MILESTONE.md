# RAG / Knowledge Retrieval Milestone

## Status

Implemented and validated.

The SQLite database is the canonical source of truth. This milestone adds a
dependency-free, source-grounded retrieval layer using SQLite FTS5/BM25.

## Retrieval records

`rag_documents` provides one normalized retrieval table with provenance for:

- sections
- stories
- scenes
- pages
- chunks
- canonical entities
- events

Each record retains `document_id`, source type/id, parent linkage where
applicable, title, text, page range, and JSON metadata.

`rag_fts` is an SQLite FTS5 index over title and text.

## Querying

Use `DocumentStore.search_rag()` from Python or:

    python -m core.rag_query data\mybook_structure.db 1 "Professor Lidenbrock"

Optional source filtering:

    python -m core.rag_query data\mybook_structure.db 1 "Professor Lidenbrock" --source-type entity

An existing database can be indexed without opening the PDF:

    python -m core.rag_indexer data\mybook_structure.db 1

## Design boundary

This is the first retrieval layer, not a final vector/embedding implementation.
It is intentionally dependency-free and deterministic so it can be validated
on any source PDF. A future hybrid retriever can add embeddings/vector search
without replacing the SQLite source-of-truth or its provenance.

## Definition of Done

- [x] Queryable retrieval table
- [x] Full-text index
- [x] BM25 ranking
- [x] Source provenance
- [x] Section/story/scene/entity/event retrieval
- [x] Source-type filtering
- [x] Rebuild without PDF/OCR
- [x] Idempotent rebuild
- [x] Pipeline integration
- [x] Tests
