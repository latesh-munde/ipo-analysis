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

## Local setup

Use Python 3.13.6 for current development. From the repository root:

```powershell
cd backend
python --version
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

The editable install includes the multipart upload parser and PyMuPDF. OCR is
optional and runs locally: install Tesseract OCR and its language data, then set
`DOCUMENT_OCR_ENABLED=true` and configure `DOCUMENT_OCR_TESSERACT_PATH` and
`DOCUMENT_OCR_LANGUAGE` in `backend/.env`. Without OCR, pages needing OCR are
retained with an explicit warning. No document content is sent to a remote service.

If creating the environment for the first time:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If `pyproject.toml` has not yet been configured for editable installation, install the dependencies listed in that file and resolve the packaging configuration before using `pip install -e`.

## Local URLs

- Home page: http://127.0.0.1:8000/
- Health endpoint: http://127.0.0.1:8000/api/v1/health
- Interactive API docs: http://127.0.0.1:8000/docs
- Static frontend assets: served under `/static/`

These URLs describe the intended local development endpoints; confirm them against the current application configuration.

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
- `docs/testing/`: testing strategy
- `docs/ai/`: AI, retrieval, evidence, and evaluation design

## Financial-analysis principles

- Distinguish reported facts, deterministic calculations, and AI-generated interpretation.
- Preserve document/page/period/currency/unit provenance where available.
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
