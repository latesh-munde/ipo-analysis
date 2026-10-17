# ADR-004: Source-bound financial analysis input

- Status: Accepted
- Date: 2026-10-17

## Context

Phase 3 persists `ExtractedTable` rows as raw strings with document, page, and
table references. It does not define a canonical financial-fact model or retain
period, currency, unit, statement-basis, audit, or restatement metadata. Letting
clients submit numeric values directly would break evidence integrity and could
silently detach calculations from extracted source material.

## Decision

- Financial-analysis requests identify stored source table cells and declare
  their semantic metadata; the backend resolves the numeric text from the
  selected document table. Client-submitted authoritative numeric values are
  not accepted.
- Preserve the original label/value/header cell text and exact document/page/
  table/row/column references in each ephemeral fact and each derived metric.
- Require explicit period, basis, audit/restatement status, INR currency or
  unknown currency, and rupees/thousand/lakh/crore scale. Do not infer or convert.
- Separate calculation scopes by period, currency, statement basis, audit
  status, and restatement status.
- Generate reports on demand without adding durable analysis persistence or a
  company/document identity model.
- Use a configurable INR reconciliation tolerance. Keep formulas deterministic
  and independent of HTTP handlers, persistence, frontend, and AI.

## Consequences

- The implementation is safe against client-invented amounts and makes manual
  mapping visible, but it does not replace a structured Phase 3 financial-fact
  extraction contract.
- Reports are reproducible from recorded formula/input metadata, but are not
  retained by the application.
- Cross-document company attribution and DRHP/RHP reconciliation remain
  blocked until the application has a trusted company/IPO document association.
- Manual mapping and source OCR both require human review; the calculations are
  not an audit opinion or investment recommendation.

## Alternatives considered

- Accept raw financial numbers in an API payload: rejected because the API
  could not prove that they came from the uploaded document.
- Guess line items and periods from raw OCR/table text: rejected because Phase 3
  table extraction does not preserve a reliable semantic structure.
- Add a financial database, company registry, or automatic parser now:
  deferred because no upstream schema or relationship contract exists.
