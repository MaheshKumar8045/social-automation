# Core PDF Document Processing

This package provides a document-agnostic pipeline for mixed, text, and
scanned PDFs.

## Main flow

`StructureScanner` is the single structural source of truth:

1. PDF analysis
2. PDF text extraction where available
3. OCR fallback for image-only pages
4. layout-aware heading candidate detection
5. page-structure classification
6. structural validation
7. constrained OCR Roman-numeral normalization
8. document-level reconciliation
9. targeted second-pass recovery

The system does not require a known chapter list or hard-coded page numbers.

## Queryable output

`core.pipeline` creates four outputs beside the input PDF:

- `<name>_chapter_index.csv` — compact legacy-friendly chapter index
- `<name>_sections.csv` — richer section table
- `<name>_structure.db` — canonical SQLite document store
- `<name>_structure.json` — JSON export of the stored document

For bounded scans, section ranges are clipped to the last page actually scanned; a full scan uses the PDF's true final page.

The SQLite database contains:

- `documents`
- `pages`
- `sections`
- `chunks`

This makes the processed PDF directly queryable for downstream RAG,
analytics, filtering, chunking, and JSON workflows.

Example:

```sql
SELECT section_number, title, page_start, page_end
FROM sections
ORDER BY section_order;
```

Example:

```sql
SELECT page_number, text
FROM pages
WHERE page_number BETWEEN 19 AND 33
ORDER BY page_number;
```

Example:

```sql
SELECT section_id, page_number, chunk_index, text
FROM chunks
WHERE document_id = 1
ORDER BY page_number, chunk_index;
```

## CLI

Run the complete pipeline:

```powershell
python -m core.pipeline "data\mybook.pdf"
```

Run a limited regression scan:

```powershell
python -m core.pipeline "data\mybook.pdf" 40
```

Run a read-only SQL query:

```powershell
python -m core.query_store "data\mybook_structure.db" "SELECT * FROM sections ORDER BY section_order"
```
