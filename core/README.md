# Core PDF Document Processing

This package is the document-ingestion foundation for the Mahabarath pipeline.
It is document-agnostic: the source PDF is the input, not a hard-coded book
schema.

## Current pipeline

```text
PDF
  -> PDF analysis
  -> native PDF text and/or OCR
  -> deterministic content normalization
  -> layout-aware structure detection
  -> section validation/reconciliation/recovery
  -> queryable SQLite
  -> CSV + JSON
```

The canonical content layer is `ContentNormalizer`. It reconstructs readable
lines and paragraphs from PDF/OCR fragments without using an LLM to rewrite
source material. Raw extraction is retained for provenance.

## Outputs

`core.pipeline` creates:

- `<name>_chapter_index.csv` — compact structural index
- `<name>_sections.csv` — section ranges and detection metadata
- `<name>_structure.db` — canonical queryable SQLite store
- `<name>_structure.json` — JSON representation of the stored document

SQLite tables:

- `documents` — source document metadata
- `pages` — canonical page text plus raw text/provenance
- `sections` — detected structural ranges
- `chunks` — retrieval-oriented text units
- `stories` — source-grounded story units derived from sections
- `scenes` — source-grounded scene units derived from stories
- `entities` — reusable source-grounded character/location/environment candidates
- `entity_mentions` — scene-level evidence linking entities back to source
- `events` — source-grounded event candidates, one per scene in the baseline

`pages` now records:

- `text` — canonical normalized text
- `raw_text` — original extracted/native/OCR text
- `source` — `pdf_text` or `ocr`
- `quality_score`
- `normalization_method`

This makes the database suitable as the source layer for downstream RAG,
analytics, filtering, entity extraction, story generation, and JSON export.

## Important design rules

- No hard-coded chapter numbers, titles, page numbers, or character names.
- `sample.pdf` is only a regression fixture.
- Native text and OCR are treated as source evidence, not generated content.
- The LLM is not used to silently "correct" source text.
- Structural numbering is document-local; repeated chapter numbers can occur
  when a PDF contains multiple works.
- Page numbers exposed by the processing API are one-based human PDF pages.
- SQLite is the stable source of truth; vector storage can be added later.
- Story and scene segmentation must preserve source text and page provenance.
- Deterministic segmentation is a baseline; semantic/LLM segmentation may be
  added later without changing the storage contract.

## CLI

Full scan:

```powershell
python -m core.pipeline "data\mybook.pdf"
```

Bounded regression scan:

```powershell
python -m core.pipeline "data\mybook.pdf" 40
```

Read-only SQL:

```powershell
python -m core.query_store "data\mybook_structure.db" "SELECT page_number, text FROM pages ORDER BY page_number"
```

Extraction benchmark for representative pages:

```powershell
python -m core.content_benchmark "data\mybook.pdf" 19 20 32 33 351 400
```

## Current milestone

Completed foundation:

- dynamic PDF analysis
- native text extraction
- OCR fallback
- layout-aware section detection
- Roman numeral normalization/reconciliation/recovery
- queryable SQLite persistence
- CSV/JSON exports
- deterministic canonical content normalization

Current milestone:

**Section -> Story -> Scene source-grounded segmentation is implemented.**
The baseline creates one story per detected section and splits each story at
paragraph boundaries into configurable scene-sized windows without rewriting
source text.

Current milestone:

**Scene -> Character/Environment/Event source-grounded discovery is implemented.**
The baseline discovers likely names and setting phrases from stored scene text,
stores evidence-bearing mentions, and creates scene-level event candidates.
It does not invent biographies, physical traits, or event summaries.

Next milestone:

**Semantic entity resolution/profile enrichment and RAG indexing.**


## RAG / Retrieval

The SQLite store now includes a source-grounded FTS5 retrieval layer. Use `python -m core.rag_query <db> <document_id> "query"` for retrieval, or `python -m core.rag_indexer <db> <document_id>` to rebuild it without reopening the PDF. See `RAG_MILESTONE.md`.
