# IPO Analysis System

A web application foundation for analyzing IPO documents and presenting evidence-backed assessments of company fundamentals, financial performance, valuation, risks, and missing information.

## Current project baseline

Phase 1 (project setup and coding standards) and Phase 2 (application foundation) are treated as implemented for this documentation baseline. Verify the working tree and run the documented checks before representing any individual test or behavior as currently verified.

### Technology

- Python 3.13.6 development interpreter
- FastAPI backend
- HTML5, CSS3, and vanilla JavaScript ES modules
- Versioned REST endpoints under `/api/v1`
- Pydantic Settings for configuration
- Python standard `logging` behind a project `Logger` singleton facade
- PyMuPDF for local PDF text, page rendering, and supported table extraction
- SQLite via Python's standard library for document metadata and extraction results
- pytest and HTTPX for tests
- Ruff for linting and formatting

No React, Angular, Vue, or similar frontend framework is part of the current design.

## Repository layout

```text
ipo-analysis/
├── README.md
├── AGENTS.md
├── CODING_STANDARDS.md
├── .gitignore
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   ├── api/v1/
│   │   └── schemas/
│   ├── tests/
│   ├── .env.example
│   └── pyproject.toml
├── frontend/
│   ├── pages/
│   ├── css/
│   └── js/
└── docs/
    ├── architecture/
    ├── decisions/
    ├── plans/
    ├── sessions/
    ├── features/
    ├── testing/
    └── ai/
```

This is the intended structure for the current foundation. Keep documentation synchronized with the actual repository and do not create empty modules solely to match the diagram.

## Run locally and analyze a PDF

The FastAPI server serves both the website and API from the same local address.
You do not need a separate frontend server or Node.js.

### 1. Install and start the backend (Windows PowerShell)

Run these commands from the repository root:

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

If PowerShell reports that script execution is disabled, activate the
environment for this terminal with:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Keep the terminal running while using the site. On startup, the API is at
`http://127.0.0.1:8000`.

### 2. Open the site and upload a PDF

1. Open **http://127.0.0.1:8000/** in your browser.
2. Confirm the header says **Local backend connected**.
3. Optionally choose DRHP, RHP, financial statement, or another document type.
4. Select a `.pdf` file and choose **Extract document**.
5. Review the document status, metadata, and any warnings.
6. Open **Page text** to review extracted content by one-based PDF page number.
   Open **Tables** to review supported table rows and their source pages.
7. Compare extracted content with the original PDF, particularly OCR results
   and financial figures. OCR is not guaranteed to be accurate.
8. In **Financial analysis**, map relevant values to their exact extracted
   table cells, explicitly set the period and reporting metadata, then calculate
   metrics. Review findings and verify OCR/table values against the filing.
   Analysis reports are shown in the web application and are not persisted or
   exported.

The default upload limit is 50 MiB and the page limit is 2,000 pages. The server
validates the file and reports invalid, encrypted, oversized, or unreadable PDF
errors on the page. Re-uploading identical bytes shows the existing result
instead of repeating extraction.

The UI also displays the API reference at
`http://127.0.0.1:8000/docs`; the health endpoint is
`http://127.0.0.1:8000/api/v1/health`.

### Optional local OCR for scanned pages

Native-text PDFs work without OCR. OCR is disabled by default. To extract
scanned pages, install the local Tesseract OCR program and its language data,
copy `backend/.env.example` to `backend/.env`, then set:

```dotenv
DOCUMENT_OCR_ENABLED=true
DOCUMENT_OCR_LANGUAGE=eng
DOCUMENT_OCR_TESSERACT_PATH=tesseract
```

Set `DOCUMENT_OCR_TESSERACT_PATH` to the executable path if Tesseract is not on
`PATH`. Restart the backend after changing `.env`. If OCR is disabled or
unavailable, pages needing OCR remain in the results with a warning. No uploaded
PDF is sent to a cloud OCR service. PyMuPDF is dual-licensed under AGPL-3.0 or
an Artifex commercial license; confirm applicable terms before distributing or
deploying this application.

### Where local documents are stored

By default, original PDFs and the SQLite document/index data are stored under
`backend/data/documents/`. The folder is excluded from Git and is not served
through the website. Protect this folder and its backups; this initial local
feature does not encrypt files or implement user authentication. Do not use the
development server to expose private uploaded documents to an untrusted network.

To select another local folder, set `DOCUMENT_STORAGE_DIR` in `backend/.env`.
Other supported limits and OCR settings are listed in
[`backend/.env.example`](./backend/.env.example) and described in the
[document-ingestion guide](./docs/features/document-ingestion.md). The
financial-analysis guide documents the INR reconciliation tolerance and the
source-cell mapping workflow.

### Create the development environment (if needed)

If the `py` launcher is unavailable, install Python 3.13 and create the virtual
environment using that interpreter. Once the `.venv` exists, the quick start is:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

## Quality checks

Run from `backend/`:

```powershell
python --version
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Only report checks as passing if they were actually run and passed.

## Configuration and secrets

- Use `backend/.env` for local settings when supported by the configuration implementation.
- Keep real `.env` files, credentials, tokens, and secrets out of Git.
- Commit `backend/.env.example` only with placeholder/non-secret values.
- Validate configuration at startup.
- Do not commit private IPO documents or sensitive extracted data unintentionally.

## Documentation map

- `AGENTS.md`: tool-independent coding-agent instructions
- `CODING_STANDARDS.md`: coding and quality rules
- `docs/architecture/ARCHITECTURE.md`: current system architecture
- `docs/decisions/`: durable architecture decisions (ADRs)
- `docs/plans/`: feature plans
- `docs/sessions/`: development progress and investigation notes
- `docs/features/`: implemented feature behavior
- `docs/features/document-ingestion.md`: PDF upload and extraction behavior
- `docs/features/financial-analysis.md`: source-bound financial calculations,
  formulas, API, and known Phase 3 integration gap
- `docs/testing/`: testing strategy
- `docs/ai/`: AI, retrieval, evidence, and evaluation design

## Financial-analysis principles

- Distinguish reported facts, deterministic calculations, and AI-generated interpretation.
- Preserve document/page/period/currency/unit provenance where available.
- Financial-analysis inputs must be mapped to saved source cells; the backend
  reads the value from that cell rather than trusting a client-supplied amount.
- Never fabricate financial values, source pages, or citations.
- Keep financial calculations deterministic and independently testable.
- State uncertainty, missing information, and limitations clearly.
- Do not present analysis as a guaranteed investment outcome.

## Development workflow

1. Inspect current code, documentation, and Git status.
2. Clarify requirements and acceptance criteria.
3. Plan significant features before coding.
4. Implement a focused change with appropriate tests.
5. Run quality checks and review the diff.
6. Update documentation affected by the change.
7. Report changes, actual verification, limitations, and next steps.
