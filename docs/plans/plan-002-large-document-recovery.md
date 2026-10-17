# PLAN-002: Large-Document Recovery

- Status: In progress
- Created: 2026-10-18
- Related plans: [Financial evidence pipeline hardening](./plan-001-financial-evidence-pipeline-hardening.md),
  [Phase 3 ingestion](./phase-3-document-ingestion-extraction-plan.md)
- Related features: [Document ingestion](../features/document-ingestion.md)

## Problem and motivation

PDF extraction is synchronous and may process as many as 2,000 pages. OCR has
an individual subprocess timeout, but native page parsing has no overall time
budget. A long-running upload can consequently occupy the request worker for
an excessive period. A failure or interruption also has no persisted per-page
attempt history or resume workflow.

This plan covers the large-document recovery blocker from Module 6 of the
financial evidence pipeline. It is separate from the other release blockers:
scanned-table qualification, Phase 3 fact production, verified reviewer
identity, and issuer/IPO association remain tracked in
[PLAN-001](./plan-001-financial-evidence-pipeline-hardening.md).

## Goals

- Bound cooperative PDF extraction work with a configurable whole-extraction
  time budget.
- Preserve completed page results when the deadline is reached.
- Represent pages that were not started explicitly, rather than returning
  apparently complete results.
- Limit OCR subprocess time to the lesser of its per-page limit and the
  remaining extraction budget.
- Keep timeout outcomes visible through existing page/document warnings.
- Establish an incremental foundation for later process isolation,
  concurrency control, and retry/resume.

## Non-goals

- Claim a strict wall-clock bound for synchronous native PDF parsing or table
  extraction; a running PyMuPDF call cannot be preempted by this deadline.
- Add parallel OCR work or a configurable worker pool in this increment.
- Retry or resume failed work, or persist extraction attempt history.
- Change document upload APIs, financial-fact persistence, or OCR trust gates.
- Silently discard successful page results or present unprocessed pages as
  successfully extracted.

## Requirements and acceptance criteria

### Implemented slice: cooperative extraction deadline

- A positive `DOCUMENT_EXTRACTION_TIMEOUT_SECONDS` setting has a documented
  default.
- Extraction checks the deadline before starting each page. Once reached, it
  does not load further pages, but returns an ordered result for every expected
  page.
- Pages not started after the deadline have status `not_processed`, method
  `not_processed`, and a `DOCUMENT_EXTRACTION_TIMEOUT` warning.
- A page already in progress is retained. When its work completes after the
  deadline, it is retained with the timeout warning.
- The OCR subprocess timeout is capped by the remaining extraction time.
- A timed-out extraction with usable earlier results is
  `completed_with_warnings`; it remains `failed` if no usable content was
  produced.
- Tests verify partial-result preservation, ordered not-processed pages, no
  further page loads, the OCR remaining-time cap, and unchanged behavior when
  the deadline is not reached.

### Remaining recovery work

- **Hard deadline and resource isolation:** establish a killable boundary for
  potentially long PyMuPDF parsing/rendering work and define memory/render-size
  limits. The cooperative deadline is not sufficient to guarantee a hard
  request-duration limit.
- **OCR concurrency:** keep OCR concurrency bounded if parallel processing is
  introduced; document and test the cap. The current sequential flow uses at
  most one OCR operation at a time.
- **Retry/resume history:** persist attempt identifiers, page-level outcomes,
  timestamps, and retry reasons; resume only incomplete/failed pages under
  idempotent persistence without duplicating facts or reviews.
- **Release evidence:** exercise a large synthetic PDF and verify time,
  resource cleanup, recovery outcomes, and operational warnings.

## Current behavior

- Upload validation enforces a maximum byte size and page count.
- PDF page extraction runs sequentially in the API request path.
- Tesseract recognition has a configurable per-page timeout, now capped by the
  remaining cooperative extraction budget.
- Page extraction failures are represented individually. Deadline exhaustion
  preserves completed pages and adds explicit `not_processed` results for pages
  that were not started.
- A stale `processing` document is marked failed after an interrupted prior
  application run; no retry history or resume mechanism exists.

## Proposed design

Use `time.monotonic()` to set one deadline at the start of `extract_pdf`.
Monotonic time avoids wall-clock adjustments. Check it before loading each page,
and calculate the remaining budget immediately before OCR. Pass OCR the smaller
of its existing per-page timeout and that remaining budget.

On exhaustion, stop initiating page work, retain any page already completed,
and add explicit ordered placeholders for remaining PDF pages. Emit a
document-level timeout warning and page-level warnings. Existing document
status rules then report partial usable output as
`completed_with_warnings`; no usable output remains `failed`.

This is intentionally cooperative. It does not claim to interrupt a currently
running native PyMuPDF operation. A later hard-deadline design should isolate
untrusted parsing/rendering work behind a process boundary rather than assume
that cancelling a Python thread stops native work.

## Alternatives considered

- **Async task cancellation:** rejected for this increment because cancellation
  does not reliably stop synchronous PyMuPDF/native work.
- **Immediate process-pool rewrite:** deferred because it changes execution,
  persistence, cancellation, and deployment behavior substantially; first
  establish explicit partial-result semantics and measured limits.
- **Only lower the maximum page count:** rejected as the primary fix because
  equal page counts can have very different OCR and rendering costs.

## API and data flow

No endpoint or response envelope changes are required. The new configuration
setting is consumed by the extraction service. Existing page results expose
`status: "not_processed"` and the new warning code; document-level metadata
retains the warning and existing aggregate status.

## Dependencies and design patterns

Use the standard-library monotonic clock and existing Pydantic settings,
warning schemas, extraction service, and tests. Add no runtime dependencies,
background job system, or parallelism.

## Security, privacy, and failure cases

- Preserve the source PDF and successful extracted content; do not log document
  text or introduce external services.
- A timeout is an explicit partial result, never a success-shaped complete
  result.
- Native PDF operations may exceed the cooperative deadline while in progress;
  document this limitation and do not describe the setting as a hard timeout.
- Keep temporary OCR files managed by the existing temporary-directory context.

## Testing strategy

- Use deterministic fake pages and a controlled monotonic clock to test
  deadline handling without waiting for real time.
- Verify results cover every page in source order and only pages before the
  deadline are loaded.
- Verify OCR receives the remaining budget and successful in-budget extraction
  remains unchanged.
- Run focused document extraction tests, then the backend suite and Ruff checks.

## Documentation updates

- Document the setting, default, warning/status behavior, and cooperative
  limitation in the document-ingestion feature guide and environment example.
- Update PLAN-001's Module 6 progress without marking the overall module or
  pipeline complete.

## Implementation steps

1. Add the configurable extraction budget and cooperative page-boundary checks.
2. Cap each OCR subprocess timeout by the remaining budget.
3. Preserve completed pages and make pages not started after timeout explicit.
4. Add deterministic regression tests for partial results and OCR budgeting.
5. Update feature, configuration, architecture, and roadmap documentation.
6. Keep hard interruption, concurrency policy, and retry/resume as follow-up
   work requiring separate design and validation.

## Risks and open questions

- The 30-minute default is a conservative initial bound and may need adjustment
  based on representative local workload measurements.
- A large or pathological native page operation can exceed the configured
  budget before control returns to the page checkpoint.
- The application still processes uploads synchronously; the cooperative
  deadline does not guarantee API responsiveness under concurrent large
  uploads.
- Retry attempt retention and cleanup policy must be decided before implementing
  resume.

## Completion notes

- Implemented the configurable cooperative deadline, page-boundary stop,
  explicit `not_processed` results, and OCR timeout capping.
- Added deterministic tests for page preservation and remaining OCR budget.
- Hard process-level interruption, bounded worker concurrency, retry/resume
  history, and release-scale evidence remain outstanding.
