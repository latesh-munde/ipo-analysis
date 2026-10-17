# Feature: Deterministic Financial Analysis

- Status: In progress; source-cell analysis is implemented, pending a structured
  financial-fact contract from Phase 3
- Last verified: 2026-10-17
- Related plan: [Phase 4 plan](../plans/phase-4-financial-analysis-engine-plan.md)
- Related ADR: [ADR-004](../decisions/ADR-004-financial-analysis-contract.md)

## Purpose

Calculate reproducible financial metrics from explicitly selected, stored
Phase 3 table cells. The backend parses the chosen source value and performs
all financial arithmetic with `Decimal`. It does not infer line items, periods,
units, currencies, or investment conclusions.

## User workflow

1. Upload a DRHP, RHP, or financial-statement PDF and review its extracted
   tables and warnings.
2. In **Financial analysis**, select a canonical line item and explicitly
   declare its statement period, basis, audit/restatement status, currency, and
   reported scale.
3. Select the source table, the zero-based financial row and label column, the
   value column, and the zero-based period-header row.
4. Add all relevant facts and choose **Calculate financial metrics**.
5. Review backend-calculated values, formulas, statuses, source cells, findings,
   cross-statement checks, and limitations.

The UI submits source coordinates and declared metadata, never numeric fact
values. The service verifies every coordinate against the selected document's
stored table rows and reads the reported amount from that cell.

## Phase 3 source contract

Phase 3 currently exposes `ExtractedTable` with `document_id`, one-based
`page_number`, `table_index`, `extraction_method`, raw `rows: list[list[str]]`,
and table warnings. Row and column coordinates in analysis requests are
zero-based. It does not produce canonical financial facts, fiscal periods,
statement basis, currency/scale, audit/restatement metadata, or stable cell
IDs. Page text and table text are raw extraction results and may contain OCR
errors.

The Phase 4 route therefore resolves each submitted locator back to the saved
table and creates an ephemeral fact with deterministic ID and evidence for:
document ID, PDF page, table, financial row/label cell, numeric value cell,
period-header cell, and extraction method/warnings. Numeric input supplied
outside that source table is not accepted.

## API

`POST /api/v1/documents/{document_id}/financial-analysis`

The JSON body contains 1–500 facts. Each fact supplies:

- Canonical `line_item_code` and matching `statement_type`.
- A period label and either ordered flow dates or a point-in-time date.
- `period_header_row_index`, `page_number`, `table_index`, `row_index`,
  `label_column_index`, and `value_column_index`.
- Explicit `statement_basis`, `audit_status`, `restatement_status`, `currency`,
  and `unit`.

Example (value is resolved from page 4/table 0/row 3/column 2; the caller does
not send `125000`):

```json
{
  "facts": [
    {
      "line_item_code": "revenue_from_operations",
      "statement_type": "profit_and_loss",
      "period_label": "FY 2025",
      "period_kind": "annual",
      "period_start": "2024-04-01",
      "period_end": "2025-03-31",
      "as_of_date": null,
      "statement_basis": "consolidated",
      "audit_status": "audited",
      "restatement_status": "as_published",
      "currency": "INR",
      "unit": "crore_rupees",
      "page_number": 4,
      "table_index": 0,
      "row_index": 3,
      "period_header_row_index": 0,
      "label_column_index": 0,
      "value_column_index": 2
    }
  ]
}
```

The existing `success/data/error/meta` response envelope contains source facts,
metrics, validation findings/checks, formula versions, input fact IDs, evidence
references, and limitations. Missing documents return 404, unready extractions
return 409, and invalid/nonexistent evidence locators return a sanitized 422
error.

## Metrics and formula policies

All formulas are defined once in
[`calculations.py`](../../backend/app/financial/calculations.py) and identified
by formula-set and formula version `1.0.0`.

| Metric | Formula and policy |
| --- | --- |
| Revenue growth (YoY) | `(current revenue - prior comparable revenue) / prior revenue * 100`; requires matching period kind, one-year-aligned dates and duration, basis, currency, audit status, and restatement status. A zero baseline returns `ZERO_BASELINE`. |
| PAT growth (YoY) | Uses a percentage only for a positive prior PAT and non-negative current PAT. Loss/profit transitions, negative baselines, and zero baselines report the absolute change with an explicit reason code instead. |
| Gross profit | `revenue from operations - cost of sales`; cost of sales must be reported as a non-negative expense magnitude. |
| Gross margin | `gross profit / revenue from operations * 100`. |
| Operating margin | `explicit operating profit / revenue from operations * 100`; no operating profit is inferred. |
| PBT margin | `profit before tax / revenue from operations * 100`. |
| PAT margin | `profit after tax / revenue from operations * 100`; losses remain negative. |
| Basic/diluted EPS | Returns a separately reported basic/diluted EPS value in INR/share; does not infer EPS from profit or shares. |
| Total borrowings | `current borrowings + non-current borrowings`; both inputs are required. Lease liabilities are excluded. |
| Net debt | `total borrowings - cash and cash equivalents`; net cash (negative net debt) is preserved. |
| Debt-to-equity | `total borrowings / total equity`; zero or negative equity blocks the metric. |
| Debt-to-assets | `total borrowings / total assets`; assets must be positive. |
| Interest coverage | `explicit operating profit / finance costs`; EBITDA is not substituted. |
| Current ratio | `current assets / current liabilities`; zero liabilities make it unavailable. |
| Quick ratio | `(cash and cash equivalents + trade receivables) / current liabilities`; inventories and other bank balances are excluded. |
| Working capital | `current assets - current liabilities`. |
| CFO margin | `cash from operating activities / revenue from operations * 100`; cash-flow sign is preserved. |
| Free cash flow | `cash from operating activities - capital expenditure`; capex must be explicitly reported as a non-negative spend amount. |
| Net cash movement | `CFO + CFI + CFF`; source cash-flow signs are preserved. |
| Return on assets | `PAT / average opening and closing total assets * 100`; opening assets are the point-in-time value on the day before the flow period starts, and closing assets are as of period end. Both must be positive. |
| Return on equity | `PAT / average opening and closing total equity * 100`; uses the same exact opening/closing date policy and blocks non-positive equity. PAT is the selected profit measure; no owner-attribution adjustment is inferred. |

INR values are normalized to rupees using exact Decimal scale factors for
rupees, thousand rupees, lakh rupees, and crore rupees. Currency conversion and
display rounding are not performed. Only INR or explicitly unknown currency is
accepted; unknown currency/basis is surfaced as a warning and never combined
with a different value. Formula divisions use Python Decimal arithmetic; no
binary floating-point calculations are used. Source numeric values are limited
to 128 digits, and calculations run with 160 significant digits of Decimal
precision so normalization and intermediate arithmetic do not silently fall
back to the default low-precision context. Repeating division results are
therefore represented to the configured Decimal precision.

Missing or explicitly blank/dash/not-disclosed cells are unavailable, not
zero. Malformed amounts and values exceeding the supported numeric precision
are rejected. Parentheses and a leading minus sign
represent negative values; signs are otherwise preserved. A negative expense
or capex is blocked where the formula requires a positive magnitude.

## Validation and evidence

- Duplicate identical facts preserve all source references. Conflicting values
  for the same line item and scope are reported and affected calculations are
  blocked.
- Statement basis, period kind/dates, currency, audit status, restatement
  status, and normalized scale are part of the calculation scope. Incompatible
  inputs are not silently combined.
- Balance-sheet equation and cash-flow/cash-balance reconciliations return
  `pass`, `warning`, `failure`, or `not_checkable`; a missing component is not a
  pass. Reconciliation tolerance is configurable in rupees.
- OCR and table extraction warnings remain visible. OCR-sourced facts require
  manual verification against the original filing.
- Each metric contains formula text/version, input fact IDs, and the exact
  document/page/table/row/value/period-header evidence for every input.

## Configuration

`FINANCIAL_RECONCILIATION_TOLERANCE_RUPEES` sets the default balance and cash
reconciliation tolerance (default `1` rupee). A difference up to the tolerance
passes, up to five times the tolerance warns, and a larger difference fails.

## Tests and verification

Run from `backend/`:

```powershell
python -m pytest tests/unit/test_financial_analysis.py tests/test_financial_analysis_api.py
python -m ruff check .
python -m ruff format --check .
```

Financial analysis tests use synthetic source-cell values and hand-calculated
fixtures; they do not require an IPO PDF, OCR, network access, or an LLM.

## Limitations and follow-up

- The upstream Phase 3 service does not yet create or persist structured
  financial facts. Mapping is a user-reviewed, on-demand step; automatic
  statement/label extraction and cross-cell period interpretation remain
  outstanding. Resolve this by adding a validated, evidence-linked fact schema
  and repository at the Phase 3 extraction boundary, then adapt this service to
  consume those facts directly.
- Analysis is scoped to one document because the repository has no company/IPO
  identity or document-association model. DRHP/RHP/restatement conflicts across
  documents cannot yet be compared safely.
- Audit and restatement metadata is explicitly user-declared. It is not inferred
  from document wording. Unknown status remains visible and is not mixed with
  a known status.
- PAT growth, return on assets/equity, and reported basic/diluted EPS are
  supported as described above. EPS derivation, EBITDA, profit attribution
  beyond explicitly mapped PAT, forecasts, valuation, AI interpretation,
  investment advice, report persistence, export, and PDF generation are not
  implemented.
- No real prospectus was processed for verification; no PDF was needed for the
  financial calculation and source-cell tests.

## Related documentation

- [Phase 3 document ingestion](./document-ingestion.md)
- [Architecture](../architecture/ARCHITECTURE.md)
- [Testing strategy](../testing/README.md)
