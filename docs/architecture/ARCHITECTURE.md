# System Architecture

## Status and scope

This describes the current application foundation and the intended direction for IPO analysis. It does not claim that database persistence, document ingestion, RAG, MCP, or AI analysis is implemented unless confirmed in source code.

## Current foundation

- Python 3.13.6 development environment
- FastAPI application
- Plain HTML/CSS/vanilla JavaScript frontend
- API routes grouped under `/api/v1`
- Pydantic Settings for configuration
- Python standard logging accessed through a project `Logger` singleton facade
- Centralized HTTP, request-validation, and unexpected-exception handlers
- Consistent API response envelope
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
Application services (to be expanded)
       |
       +--> Document extraction (future feature)
       +--> Deterministic financial calculations (future feature)
       +--> Optional AI interpretation/retrieval (future feature)
       +--> Persistence (decision pending)
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

### Future analysis components

- Document extraction: text/table extraction and OCR when needed.
- Financial domain: deterministic, independently tested calculations.
- AI integration: qualitative interpretation and evidence-grounded explanation only where useful.
- Persistence: choose database and migrations after requirements are established.

## Financial evidence principles

Preserve source document/version/page/period/currency/units where available. Distinguish source-reported facts, calculated metrics, and model-generated interpretations. Never invent evidence or allow an LLM to silently overwrite verified calculations.

## Architecture evolution

Update this document when component boundaries, data flow, runtime lifecycle, security, or major dependencies change. Record durable decisions in ADRs.
