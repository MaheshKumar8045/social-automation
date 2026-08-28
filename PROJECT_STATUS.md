# Mahabarath — Document Structure Engine

## Current Milestone

**Document Structure Engine + Queryable Data Layer**

The core document-processing architecture is now consolidated and has passed the
40-page functional regression and bounded SQLite/JSON integration test.

---

## Architecture

PDF
→ PDF inspection
→ PDF text / OCR fallback
→ page analysis
→ layout-aware fragment analysis
→ heading detection
→ section validation
→ Roman numeral normalization
→ reconciliation
→ targeted recovery
→ final document structure
→ SQLite / CSV / JSON

SQLite is the canonical structured downstream representation.

---

## Completed

### Document processing
- PDF inspection
- PDF text extraction
- Mixed PDF/text/OCR handling
- Layout-aware fragment processing
- PaddleOCR integration

### Structure detection
- Generic heading detection
- Layout-aware heading detection
- Page structure classification
- Section validation
- Roman numeral OCR normalization
- Section reconciliation
- Targeted section recovery
- False-positive suppression
- Contents-page protection
- StructureScanner integration

### OCR normalization

Examples validated:

- VIL → VII
- VIIL → VIII
- XXVIL → XXVII
- XXXVL → XXXVI
- XXXVIIL → XXXVIII
- DID → rejected

### Queryable data layer

SQLite tables:

- documents
- pages
- sections
- chunks

Supported outputs:

- SQLite database
- chapter index CSV
- sections CSV
- JSON

The SQLite representation is intended to serve as the canonical source for
downstream RAG, analytics, filtering, chunking, and JSON generation.

### Pipeline

The production pipeline now uses StructureScanner as the central structural
detection path rather than maintaining a separate legacy chapter-detection path.

---

## Validation Completed

### Python validation

All core Python modules compile successfully.

Core imports successfully.

### 40-page structural regression

Expected and observed:

| Page | Chapter | Title |
|---:|---|---|
| 19 | I | ON THE BANKS OF THE ORANGE RIVER. |
| 33 | II | OFFICIAL PRESENTATIONS, |

Result:

- Primary sections: 2
- Recovered sections: 0
- Final sections: 2

### 40-page database integration

Observed:

- documents: 1
- pages: 40
- sections: 2
- chunks: 41
- JSON: valid

Verified section boundaries:

- Chapter I: pages 19–32
- Chapter II: pages 33–40

A previous boundary bug where the final section incorrectly ended at the
full PDF page count (708) has been fixed for bounded scans.

---

## Pending

### Full production validation

The 708-page PDF has not yet been accepted as the final benchmark.

Next steps:

1. Run the full 708-page production pipeline.
2. Review all detected sections.
3. Measure missed sections and false positives.
4. Review targeted recovery results.
5. Validate section page ranges.
6. Validate SQLite records.
7. Validate JSON and CSV against SQLite.
8. Fix only genuine generic-detection problems.
9. Re-run validation after any fixes.

### Downstream RAG work

After structure extraction is stable:

- refine chunking strategy
- expose query APIs
- generate RAG-ready records
- optionally generate embeddings
- evaluate vector-store integration
- build downstream JSON schemas as required

---

## Design Constraint

The detector must remain generic.

Book-specific page numbers, chapter counts, titles, or manually inferred missing
chapters must not be hardcoded into the detection logic.

The current PDF is a benchmark/test document, not the source of document-specific
rules.

---

## Current Status

**READY FOR FULL 708-PAGE PRODUCTION VALIDATION**

The next major checkpoint is the complete production scan.
