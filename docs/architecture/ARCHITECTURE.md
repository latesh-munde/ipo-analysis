# System Architecture

## Status and scope

This describes the current application foundation, Phase 3 document ingestion,
and the in-progress Phase 4 source-bound financial-analysis feature. It does not
claim that RAG, MCP, or AI analysis is implemented unless confirmed in source.

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
       +--> Financial-analysis service -> table-cell evidence resolution
       |                               -> Decimal normalization/validation
       |                               -> deterministic metrics/report
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
The financial-analysis API, formula policies, source contract, and limitations
are described in `../features/financial-analysis.md`.

### Financial analysis

`POST /api/v1/documents/{document_id}/financial-analysis` accepts explicit
financial-fact metadata and source table coordinates. The analysis service
resolves the value, line label, period-header cell, and extraction warnings from
the existing document-table repository; it does not trust client numeric input.
Pure calculations live in `app/financial/calculations.py`; the service
coordinates document lookup and report assembly. Formula results use Decimal
arithmetic and carry formula versions, fact IDs, and exact source references.
The web page displays those same backend results and performs no financial
calculations.

Phase 3 currently stores raw strings rather than structured financial facts.
Until that upstream contract exists, period, line item, unit, currency, basis,
audit, and restatement metadata are explicitly mapped by the user. Reports are
on-demand and not persisted. The one-document scope avoids attributing facts to
an unverified company; cross-document DRHP/RHP analysis remains outstanding.

### Future analysis components

- AI integration: qualitative interpretation and evidence-grounded explanation only where useful.

## Financial evidence principles

Preserve source document/version/page/period/currency/units where available. Distinguish source-reported facts, calculated metrics, and model-generated interpretations. Never invent evidence or allow an LLM to silently overwrite verified calculations.

## Architecture evolution

Update this document when component boundaries, data flow, runtime lifecycle, security, or major dependencies change. Record durable decisions in ADRs.
