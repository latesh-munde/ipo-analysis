# Feature: PDF Document Ingestion and Extraction

- Status: In progress; implementation and verification underway
- Related plan: [Phase 3 plan](../plans/phase-3-document-ingestion-extraction-plan.md)

## Purpose

Accept IPO prospectus and financial-statement PDFs, extract traceable page text
and supported tables, and preserve warnings rather than guessing missing content.
This feature does not perform financial analysis or recommendations.

## User workflow

Upload one PDF to the versioned API. The service validates the file, assigns an
internal UUID, hashes the bytes, extracts the document, and returns its status.
Exact duplicate bytes return the original document and extraction results.
Metadata, page results, and tables can be fetched separately.

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
  extracted rows, the extraction method, and document/page/table references.
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
  `DOCUMENT_MAX_PAGES`; the defaults are 50 MiB and 2,000 pages.
- Files are written using a generated UUID, never the client filename.
- SQLite stores metadata, page results, table results, and warnings under the
  local storage directory. Stored PDFs are not served as static assets.
- Every expected PDF page receives a one-based result, including blank or
  unreadable pages.
- Native page text is kept as extracted. OCR replaces it only when OCR returns
  more non-whitespace characters. OCR output records its method and confidence
  where Tesseract reports one; confidence below 0.5 adds a verification warning.
  OCR output is not verified financial data.
- A document with no usable extracted text or tables is `failed`. Partial
  extraction or warnings produce `completed_with_warnings`; clean results are
  `completed`.
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
- OCR is heuristic, may flatten layout, and can misread financial values;
  extracted OCR values must be checked against the source.
- Native PDF parsing has upload/page-count bounds but no separate wall-clock
  timeout. OCR has a per-page subprocess timeout.
- The Phase 2 application has no authentication or authorization layer.
  Deployments handling private prospectuses must restrict network access until
  access controls are implemented.
- Local storage is not encrypted by this feature; protect the configured storage
  directory and backups.

## Tests and verification

Synthetic PDFs and mocked OCR exercise the upload, persistence, provenance,
duplicate, validation, and extraction paths. No real IPO documents or OCR
executable are needed for the test suite. Record the exact commands and outcomes
in the Phase 3 plan when verification is complete.
