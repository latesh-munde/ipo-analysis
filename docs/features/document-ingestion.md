# Feature: PDF Document Ingestion and Extraction

- Status: In progress; implementation and verification underway
- Related plan: [Phase 3 plan](../plans/phase-3-document-ingestion-extraction-plan.md)

## Purpose

Accept IPO prospectus and financial-statement PDFs, extract traceable page text
and supported tables, and preserve warnings rather than guessing missing content.
This feature does not perform financial analysis or recommendations.
Financial analysis is a separate, in-progress feature documented in
[`financial-analysis.md`](./financial-analysis.md). It uses explicit references
to the stored raw table cells; PDF extraction itself does not identify or
validate financial facts.

## User workflow

Open the same-origin web page at `http://127.0.0.1:8000/`, choose a document
type if known, select a PDF, and choose **Extract document**. The page shows
upload progress/errors, document status and metadata, warnings, expandable page
text, and supported tables. The API can also be called directly. The service
validates the file, assigns an internal UUID, hashes the bytes, extracts the
document, and returns its status. Exact duplicate bytes return the original
document and extraction results. Metadata, page results, and tables can be
fetched separately.

## API

All successful responses use the Phase 2 `success/data/error/meta` envelope.

### Upload

`POST /api/v1/documents` accepts `multipart/form-data`:

- `file`: PDF bytes; the filename must end in `.pdf` and the declared media type
  must be `application/pdf`.
- `document_type`: optional descriptive label, such as `DRHP`, `RHP`, or
  `financial_statement`.

New records return HTTP 201. An exact duplicate returns HTTP 200 with the
existing document and `document.duplicate: true`.

```json
{
  "success": true,
  "data": {
    "document": {
      "document_id": "generated-uuid",
      "original_filename": "prospectus.pdf",
      "file_size": 12345,
      "detected_type": "application/pdf",
      "sha256": "sha256-hex-digest",
      "uploaded_at": "2026-10-17T00:00:00Z",
      "document_type": "DRHP",
      "status": "completed",
      "page_count": 1,
      "warnings": [],
      "duplicate": false
    },
    "page_count": 1,
    "table_count": 0
  },
  "error": null,
  "meta": {}
}
```

### Retrieve metadata and results

- `GET /api/v1/documents/{document_id}` returns metadata and document-level
  warnings.
- `GET /api/v1/documents/{document_id}/pages?offset=0&limit=100` returns
  ordered page results, including raw text, extraction method, page status,
  character count, and page warnings.
- `GET /api/v1/documents/{document_id}/tables?offset=0&limit=100` returns
  extracted rows, cell/page bounds when available, the extraction method, and
  document/page/table references.
- `GET /api/v1/documents/{document_id}/pages/{page_number}/image` renders the
  stored PDF page as a PNG for source verification.
- `GET /api/v1/documents/{document_id}/financial-cell-reviews` returns current
  persisted OCR-cell review records.
- `POST /api/v1/documents/{document_id}/pages/{page_number}/tables/{table_index}/cells/{row_index}/{column_index}/review`
  accepts `confirmed_value` and `source_checked: true` after the user compares
  the highlighted source region.
- Pagination `limit` is from 1 to 500. Missing document IDs return the standard
  404 envelope.

File validation errors use the standard envelope and a specific error code,
for example:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ENCRYPTED_PDF",
    "message": "Password-protected PDF files are not supported."
  },
  "meta": {}
}
```

Other validation codes include `FILENAME_REQUIRED`, `UNSUPPORTED_FILE_TYPE`,
`UNSUPPORTED_CONTENT_TYPE`, `FILE_TOO_LARGE`, `TOO_MANY_PAGES`, `EMPTY_FILE`,
`INVALID_PDF`, `EMPTY_PDF`, and `UNREADABLE_PDF`.

## Processing, status, and provenance

- Uploads are bounded by `DOCUMENT_MAX_UPLOAD_BYTES` and
  `DOCUMENT_MAX_PAGES`; the defaults are 50 MiB and 2,000 pages. Extraction
  also has a configurable 30-minute cooperative time budget.
- Files are written using a generated UUID, never the client filename.
- SQLite stores metadata, page results, table results, and warnings under the
  local storage directory. Stored PDFs are not served as static assets.
- Every expected PDF page receives a one-based result, including blank or
  unreadable pages.
- Page results retain the selected `text` for compatibility and separately
  preserve `native_text` and `ocr_text`. `ocr_text: null` means OCR was not run;
  an empty string means OCR ran but recognized no text. The UI exposes both
  readings when OCR ran.
- The selected `text` still prefers OCR only when it returns more
  non-whitespace characters; that length heuristic does not establish
  correctness. Tesseract confidence is recorded where available, and every
  non-empty OCR result warns that financial figures must be checked against
  the original PDF. OCR output is not verified financial data.
- Tesseract TSV word positions are grouped into heuristic OCR row/cell
  candidates. Candidate tables retain each cell's PDF-page bounding box,
  contributing raw OCR word strings and their confidence scores, page
  dimensions, source document SHA-256, detected engine version, language,
  render DPI, and explicit warnings. Tokens with confidence below 60/100 or
  unavailable confidence are flagged; confidence is not a correctness score.
  When repeated numeric-cell right edges establish at least three stable
  columns across three or more rows, numeric cells are aligned to those source
  positions; absent cells are represented by empty strings, never zero. Rows
  that cannot be aligned remain as extracted and receive an irregular-layout
  warning. A nearby, x-aligned wrapped label fragment may be joined to a
  following numeric row when its geometry meets a narrow rule; its box spans
  both lines. This is not semantic table detection: multi-line labels,
  headers, merged cells, region boundaries, and unrelated text can still be
  misgrouped.
- Review records persist the original OCR cell string, the confirmed
  transcription, source coordinates, cell hash, and timestamp without changing
  the extracted table. The review is stale if the source document, table,
  cell value, or cell bounds change. Legacy reviews without a cell hash require
  re-review. The UI shows the exact page and highlights the cell region.
  The analysis service only parses the confirmed transcription for OCR-derived
  values; an unreviewed value is reported as `unverified` and dependent metrics
  are `blocked`. The API enforces this even if the browser is bypassed.
- A document with no usable extracted text or tables is `failed`. Partial
  extraction or warnings produce `completed_with_warnings`; clean results are
  `completed`.
- When the cooperative extraction budget is reached, completed pages are
  preserved and pages not yet started are returned as `not_processed` with a
  `DOCUMENT_EXTRACTION_TIMEOUT` warning. The Tesseract recognition subprocess
  receives a timeout no greater than the remaining budget or its configured
  per-page timeout, whichever is shorter. This is not a hard wall-clock
  guarantee: an in-progress synchronous PyMuPDF operation cannot be interrupted
  and may finish after the configured budget.
- At application startup, stale `processing` records from an interrupted prior
  run are changed to `failed` with a `PROCESSING_INTERRUPTED` warning.
- Exact byte duplicates (SHA-256) return the original record without re-running
  extraction. Filenames do not determine duplicates.
- Table empty cells are represented as empty strings. Other cell text is not
  normalized or financially interpreted.
- No document content is sent to an external service.

## Configuration and dependencies

The Python dependencies are declared in `backend/pyproject.toml`. PyMuPDF
provides local PDF parsing, page rendering, and supported table extraction.
`python-multipart` enables FastAPI multipart uploads. SQLite is provided by
Python's standard library. PyMuPDF is dual-licensed under AGPL-3.0 or an
Artifex commercial license; confirm the applicable terms before distributing
or deploying this application.

Settings use `backend/.env` when running the app from `backend/`:

| Setting | Default | Purpose |
| --- | --- | --- |
| `DOCUMENT_STORAGE_DIR` | `data/documents` | Local PDF and SQLite storage directory |
| `DOCUMENT_MAX_UPLOAD_BYTES` | `52428800` | Maximum upload size |
| `DOCUMENT_MAX_PAGES` | `2000` | Maximum accepted PDF page count |
| `DOCUMENT_EXTRACTION_TIMEOUT_SECONDS` | `1800` | Cooperative extraction time budget |
| `DOCUMENT_OCR_ENABLED` | `false` | Enables local Tesseract OCR fallback |
| `DOCUMENT_OCR_LANGUAGE` | `eng` | Tesseract language code |
| `DOCUMENT_OCR_TESSERACT_PATH` | `tesseract` | Tesseract executable or PATH name |
| `DOCUMENT_OCR_TIMEOUT_SECONDS` | `30` | Per-page OCR process timeout |
| `DOCUMENT_OCR_DPI` | `200` | OCR rendering resolution (72–600 DPI) |
| `DOCUMENT_LOW_TEXT_CHAR_THRESHOLD` | `40` | Native-text threshold for OCR selection |

To enable OCR, install the Tesseract executable and the desired language data
locally, then set `DOCUMENT_OCR_ENABLED=true`. If disabled or unavailable, the
page remains available with an `OCR_DISABLED` or `OCR_UNAVAILABLE` warning.
OCR timeouts, rendering failures, and Tesseract errors remain visible as
page-level warnings.

## Limitations and security

- Line-based table detection depends on visible table rules and PyMuPDF support.
  Borderless, complex merged, rotated, multi-page, or scanned tables may not
  retain their intended structure.
- OCR and OCR-to-table reconstruction are heuristic, may flatten or misgroup
  layout, and can misread financial values. A review action only confirms the
  selected cell's transcription; users must also check the line-item and period
  mapping.
- A local spot check against the supplied RHP found financial-number
  discrepancies in OCR output even when reported word confidence was above
  0.9. Confidence must not be used as a substitute for checking the source
  page. A loose geometry rule also treated four prose fragments on a
  digitally encoded page as table rows; the current stricter candidate gate
  rejects that observed false positive, but scanned financial-table precision
  and recall remain unmeasured. Local review is not associated with an
  authenticated reviewer identity; this initial application has no
  authentication/authorization.
- Forced 200-DPI OCR of digitally encoded statement pages 329, 330, and 334
  was compared spatially with the PDF text layer in manually inspected table
  regions: 615 of 618 OCR numeric tokens matched exactly; 10 of 628 native
  numeric tokens were not recovered. The sample includes a punctuation error
  that changes numeric scale. These are not scanned-table qualification pages.
- Native PDF parsing has upload/page-count bounds and a cooperative
  whole-extraction budget, but no hard wall-clock interruption for a running
  PyMuPDF operation. OCR also has a per-page subprocess timeout capped by the
  time remaining in the extraction budget. Extraction remains synchronous;
  OCR concurrency policy and retry/resume attempt history are not implemented.
- The Phase 2 application has no authentication or authorization layer.
  This is a trusted local single-user tool only: launch it bound to
  `127.0.0.1` and do not expose it as a shared or network-accessible app.
  Review timestamps are not verified reviewer attribution.
- Local storage is not encrypted by this feature; protect the configured storage
  directory and backups.

## Tests and verification

Synthetic PDFs and mocked OCR exercise the upload, persistence, provenance,
duplicate, validation, and extraction paths. No real IPO documents or OCR
executable are needed for the test suite. A local browser smoke test also
uploaded a synthetic one-page PDF and verified the displayed metadata, page
text, and empty-table state. Record the exact commands and outcomes in the
Phase 3 plan when verification is complete.
