# System Architecture

## Status and scope

This describes the current application foundation and Phase 3 document-ingestion implementation. It does not claim that RAG, MCP, or AI analysis is implemented unless confirmed in source code.

## Current foundation

- Python 3.13.6 development environment
- FastAPI application
- Plain HTML/CSS/vanilla JavaScript frontend
- API routes grouped under `/api/v1`
- Pydantic Settings for configuration
- Python standard logging accessed through a project `Logger` singleton facade
- Centralized HTTP, request-validation, and unexpected-exception handlers
- Consistent API response envelope
- PDF upload and page-level text/table extraction through application services
- Local SQLite persistence for document metadata and extraction results
- Optional local Tesseract OCR for pages with little native text
- pytest/HTTPX tests and Ruff quality checks

Verify these modules and their exact behavior in the current branch before making changes.

## Request flow

```text
Browser (HTML/CSS/JS)
       |
       | HTTP / JSON
       v
FastAPI entry point and middleware/handlers
       |
       v
Versioned API router and input validation
       |
       v
Application services
       |
       +--> Document service -> local PDF storage and SQLite repository
       |                     -> PyMuPDF text/table extraction
       |                     -> optional local Tesseract OCR
       +--> Deterministic financial calculations (future feature)
       +--> Optional AI interpretation/retrieval (future feature)
       |
       v
Consistent JSON response
```

## Component responsibilities

### Entry point

Creates the FastAPI app, loads configuration, configures logging, registers exception handlers, mounts static frontend assets, and includes versioned routers.

### Configuration

Loads environment-specific settings and validates values. Secrets remain in local environment configuration or an appropriate secret manager, never source control.

### Logging

A project `Logger` singleton facade delegates to Python's standard logging infrastructure. Module-specific loggers use `__name__`. Configure logging once during application initialization. The singleton is process-local; it does not share memory across multiple worker processes.

### Exception handling

Translate HTTP exceptions, request-validation failures, and unexpected errors into a consistent response contract. Client responses must be sanitized; internal diagnostics belong in protected server logs. Avoid logging request bodies or sensitive document text.

### API and schemas

Routes define HTTP contracts and delegate complex work to services. Schemas validate inputs and represent response shapes.

### Frontend

The browser renders pages and calls same-origin `/api/v1` endpoints. A centralized API client handles JSON parsing and standardized errors. Keep UI logic separate from backend business rules.

### Document ingestion

`/api/v1/documents` validates multipart PDF uploads, assigns UUID storage names,
computes SHA-256, and returns the existing record for exact duplicates. PDF files
and a SQLite database are kept under the configured local document storage
directory, which is not mounted as static content. PyMuPDF extracts one result per
PDF page and supported tables; optional local Tesseract OCR is attempted only for
low-text pages. Page and table results retain document IDs and one-based PDF page
numbers. Detailed API behavior and limitations are documented in
`../features/document-ingestion.md`.

### Future analysis components

- Financial domain: deterministic, independently tested calculations.
- AI integration: qualitative interpretation and evidence-grounded explanation only where useful.

## Financial evidence principles

Preserve source document/version/page/period/currency/units where available. Distinguish source-reported facts, calculated metrics, and model-generated interpretations. Never invent evidence or allow an LLM to silently overwrite verified calculations.

## Architecture evolution

Update this document when component boundaries, data flow, runtime lifecycle, security, or major dependencies change. Record durable decisions in ADRs.
