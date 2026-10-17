# Testing Strategy

## Goals

Provide confidence in API behavior, financial correctness, error handling, and regression prevention.

## Baseline commands

Run from `backend/`:

```powershell
python --version
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Current development interpreter: Python 3.13.6.

## Test layers

- Unit: financial formulas and normalization, configuration, logging facade,
  helpers, and adapters.
- API/integration: routes, response contracts, validation, exception handlers, and frontend delivery.
- Document fixtures: known files with expected extraction results and source locations.
- AI evaluation: later, curated examples with explicit evidence-support and factuality criteria.

## Phase 2 test cases to maintain

- Health endpoint returns the documented response.
- Home page and static assets are served.
- Unknown routes return the expected error contract and HTTP status.
- Request validation errors are sanitized and standardized.
- Unexpected exceptions return a safe message and are logged server-side.
- `Logger()` returns the same instance.
- Named logger retrieval before configuration does not crash module imports.
- Invalid logging levels are rejected.
- Settings use the expected defaults and environment overrides.
- Document uploads reject invalid, unsupported, encrypted, and oversized PDFs
  with sanitized, structured errors.
- Document extraction preserves page/table provenance and raw table values.
- Exact duplicate bytes return the existing record without duplicate storage.
- OCR selection and fallback behavior are tested without requiring Tesseract.
- Document metadata and extraction results persist across service instances.
- Local browser workflow displays upload status, source-linked page text,
  extracted table results or the empty-table state, and document warnings.
- Financial-analysis tests resolve numeric values only from stored source-table
  cells; cover formula values, missing/zero/conflicting inputs, incompatible
  restatement scopes, reconciliation tolerances, evidence propagation, and
  sanitized API errors. No financial test requires a PDF or external service.

## Phase 4 targeted checks

Run from `backend/`:

```powershell
python -m pytest tests/unit/test_financial_analysis.py tests/test_financial_analysis_api.py
```

The browser workflow for manual source-cell mapping and report rendering should
also be smoke-tested after UI changes. Review all returned source cells against
the original filing; OCR results are not verified financial data.

## Rules

Test normal paths, invalid inputs, boundaries, and failure paths. Mock network services in unit tests. Keep financial calculations independent of HTTP and AI providers. Report only checks that were actually executed.

Set coverage thresholds after critical paths and the initial suite are established.
