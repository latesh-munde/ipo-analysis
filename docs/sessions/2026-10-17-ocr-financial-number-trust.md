# Session: OCR Financial-Number Trust

- Date: 2026-10-17
- Status: In progress; OCR layout candidates and the persisted review gate are implemented
- Related plan: [OCR and financial-number trust plan](../plans/ocr-financial-number-trust-plan.md)
- Related feature: [PDF ingestion](../features/document-ingestion.md), [financial analysis](../features/financial-analysis.md)

## Objective

Prioritize local OCR for financial figures in scanned/mixed prospectuses while
preserving the original source evidence and preventing unverified OCR output
from being treated as checked financial data.

## Follow-up roadmap and Module 1 progress

- Access-model decision: keep this application trusted-local and single-user.
  No authentication or fabricated reviewer principal was added; review actions
  remain unverified. The README launch commands now bind explicitly to
  `127.0.0.1`, and feature docs warn against shared/network exposure. Verified
  identity attribution remains deferred until a shared deployment is chosen.
- Started Module 3. The analysis service now persists validated source facts as
  idempotent immutable revisions and calculates from the persisted records. A
  new paginated API returns current facts or history; evidence carries
  document/table/cell hashes. OCR reviews now bind to the exact source-cell
  hash, so a changed table or bounding box invalidates the approval. Existing
  legacy reviews without that hash are treated as stale and need re-review.
- Fact identity now follows the source value-cell locator rather than mutable
  canonical mapping fields. Remapping that source cell creates a new immutable
  revision, while a single request mapping that cell more than once is rejected.
  The persisted schema restricts fact statuses and currency values.
- Targeted tests after Module 3 changes: 59 passed, one existing
  Starlette/httpx deprecation warning.
- 2026-10-18 increment: candidate cells now retain each OCR word's raw
  confidence score. A warning is emitted for scores below 60/100 or missing
  scores; this is an uncertainty cue, not a correctness guarantee. Numeric
  rows are aligned only when recurring source x-positions establish stable
  columns; otherwise irregular rows remain unchanged and are warned. Synthetic
  tests cover both safeguards.
- Follow-up against the supplied RHP found digitally encoded statements on
  pages 329–335. Added numeric-column alignment using repeated right-edge
  anchors; absent note cells remain empty instead of shifting following
  amounts. Synthetic tests cover that regression. Forced OCR on statement
  pages 329, 330, and 334 found 615/618 numeric tokens exactly matching the
  PDF text layer and failed to recover 10/628 native numeric tokens in the
  sampled table regions. A punctuation mismatch that changes numeric scale
  was observed. These are digitally encoded pages, not scanned-table
  qualification; candidate warnings remain visible.
- Re-probed the supplied RHP locally after the stricter classifier change.
  Source pages 307 and 446 produced zero OCR table candidates; page 307 is an
  organization chart, not a financial statement. The historical page-446 false
  positives are no longer emitted, but this does not qualify table recall; an
  annotated scanned financial-table set is still needed.
- Full backend suite after this increment: 60 passed, one existing
  Starlette/httpx deprecation warning.
- Created a separate dependency-ordered hardening plan covering OCR layout,
  authenticated review, persisted canonical financial facts, explicit
  issuer/IPO-document association, company-scoped cross-document analysis, and
  operational/release validation:
  [Financial Evidence Pipeline Hardening](../plans/plan-001-financial-evidence-pipeline-hardening.md).
- Started Module 1. Candidate cells now retain the raw OCR word strings that
  formed each cell. A narrow geometric rule joins one nearby, x-aligned wrapped
  label fragment to its numeric row and expands the cell bounding box across
  both lines. Financial-looking values are recognized for candidate gating
  without changing their raw strings.
- Added synthetic coverage for two amount columns, wrapped labels, exact token
  preservation, box union, parentheses, currency prefixes, percentages, dashes,
  and rejection of isolated split text.
- Rechecked the supplied RHP locally. Page 307 still yields no candidate. The
  old loose rule's four page-446 “rows” were prose fragments; the stricter
  candidate gate now rejects them. No annotated scanned financial table was
  found in the sampled pages, so real-page recall/precision remains unknown.
- Full backend suite after the Module 1 increment: 58 passed with one existing
  Starlette/httpx deprecation warning. Ruff lint and formatting checks,
  `pip check`, frontend JavaScript syntax check, and `git diff --check` passed.

## Work completed

- Assessed Phase 3 plan and source implementation. Before this session's
  change, it stored only selected page text; longer OCR output replaced the
  native alternative.
- Confirmed OCR-derived page text is not currently reconstructed into tables,
  so scanned financial tables cannot yet be mapped through the existing
  Phase 4 source-cell workflow.
- Created a staged plan separating reading preservation, real OCR qualification,
  layout-aware number extraction, human verification, and reliability/retry.
- Established baseline backend tests: 51 passed, with one pre-existing
  Starlette/httpx deprecation warning.
- Implemented Stage 1 changes to preserve native and OCR readings separately,
  show both in the UI, and warn that recognized financial figures require
  source review.
- After user approval, installed Tesseract OCR 5.5.3 locally with English
  language data. The supplied RHP was used locally; it was not uploaded or
  sent to an external service.
- Ran the actual application page-extraction path on RHP PDF page 307.
  Tesseract returned 751 characters from a page with 42 raw native characters
  and mean confidence approximately 0.816. The result had the OCR review
  warning and document status `completed_with_warnings`.
- Uploaded a one-page copy of RHP PDF page 307 to a temporary local
  `DocumentService` store with Tesseract configured by absolute path, then
  retrieved the persisted result. Both native and OCR readings survived the
  SQLite round-trip; the temporary database and extracted PDF were removed.
- Forced local OCR on financial narrative pages 439–453 for comparison with
  the PDF's native text. Confidence ranged from 0.915 to 0.961, but numeric
  token mismatches appeared on multiple pages. On page 446, OCR included
  leading-digit corruption in financial amounts despite confidence around
  0.939; this was visually checked against the rendered PDF page.
- Added Tesseract TSV word boxes, confidence, and engine-version detection while
  keeping the legacy `(text, confidence)` adapter intact.
- Added heuristic OCR table candidates with per-cell page-coordinate boxes and
  page/OCR metadata. Candidate tables remain distinct from native tables and
  carry explicit layout-review warnings.
- Added local source-page PNG rendering and a UI review workflow that highlights
  OCR cells, accepts a user-confirmed transcription, and requires a source-check
  acknowledgment.
- Added SQLite persistence for review records without changing the original
  extracted OCR cell. Analysis checks that the reviewed raw string still
  matches the stored table cell.
- Enforced the gate in the analysis service: unreviewed OCR values have no
  reported numeric value, are identified as `unverified`, and block dependent
  metrics with `OCR_VALUE_UNVERIFIED`. Reviewed corrections are parsed as
  Decimal input while both the original and confirmed strings remain in
  evidence.
- Added synthetic OCR-layout, persistence, page-image, review API, and
  analysis-bypass/correction tests.
- Exercised the layout pass locally against the supplied RHP without storing or
  exporting pages: scanned page 307 yielded 101 OCR words and no table
  candidate; forced OCR on digitally encoded financial page 446 yielded four
  heuristic rows/eight cells. This confirms layout extraction still misses
  some scanned table layouts and does not qualify its output as correct.

## Files changed

- `docs/plans/ocr-financial-number-trust-plan.md`
- `docs/sessions/2026-10-17-ocr-financial-number-trust.md`
- `backend/app/schemas/documents.py`
- `backend/app/schemas/financial_analysis.py`
- `backend/app/services/pdf_ocr.py`
- `backend/app/services/pdf_extraction.py`
- `backend/app/services/document_repository.py`
- `backend/app/services/documents.py`
- `backend/app/services/financial_analysis.py`
- `backend/app/financial/calculations.py`
- `backend/app/financial/evidence.py`
- `backend/app/api/v1/router.py`
- `backend/tests/unit/test_documents.py`
- `backend/tests/unit/test_pdf_ocr.py`
- `backend/tests/test_documents_api.py`
- `backend/tests/test_financial_analysis_api.py`
- `backend/tests/unit/test_financial_fact_persistence.py`
- `docs/plans/plan-001-financial-evidence-pipeline-hardening.md`
- `frontend/js/app.js`
- `frontend/pages/index.html`
- `frontend/css/base.css`
- `docs/features/document-ingestion.md`
- `docs/features/financial-analysis.md`
- `docs/features/document-ingestion.md`
- `docs/architecture/ARCHITECTURE.md`
- `README.md`

## Decisions made

- Local OCR only; no uploaded prospectus is sent to an external service.
- OCR is never considered ground truth. Any OCR-derived financial input must
  retain the raw OCR reading and have a matching persisted source-page review
  before calculations can use it.
- Preserve the existing `PageExtraction.text` behavior for compatibility while
  separately retaining native and OCR alternatives.
- Keep OCR layout reconstruction explicitly heuristic; do not pass unreviewed
  OCR rows into calculations as verified facts.

## Tests and checks

- Baseline: `Set-Location backend; .\.venv\Scripts\python.exe -m pytest` —
  51 passed, one deprecation warning.
- Stage 1: `Set-Location backend; .\.venv\Scripts\python.exe -m pytest` —
  53 passed, one existing deprecation warning.
- `ruff check .`, changed-file `ruff format --check`, `pip check`,
  `node --check frontend\js\app.js`, and `git diff --check` — passed.
- Live OCR sample: local Tesseract 5.5.3/English; scanned page 307 and
  financial pages 439–453 compared. High-confidence financial-number
  mismatches found, so OCR remains unqualified without a review gate.
- Full backend suite: 56 passed, one existing deprecation warning.
- Backend Ruff lint passed; changed-file Ruff format check passed; `pip check`,
  `node --check frontend\js\app.js`, and `git diff --check` passed.
- Latest full backend suite: 68 passed with one existing
  Starlette/httpx deprecation warning. `pip check`, frontend syntax validation,
  and `git diff --check` passed. After correcting a test import-order issue,
  Ruff lint and changed-file format checks passed.
- Browser smoke: local app and health endpoint loaded; browser showed upload UI
  and connected backend. No full upload/review click-through was performed in
  the browser; route and gate interactions are covered by API tests.

## Findings and limitations

- Phase 3's own written output contract is traceable document text/tables, not
  canonical financial facts. The missing financial-fact producer is a Phase 4
  integration dependency, not by itself a Phase 3 scope defect.
- The provided local RHP exists at
  `C:\Users\lates\Downloads\Red Herring Prospectus jio.pdf`.
- The supplied RHP is 11,630,670 bytes and has 591 pages. Selected pages were
  processed locally for OCR comparison; the entire 591-page upload workflow
  was not run.
- Tesseract is installed at
  `C:\Program Files\Tesseract-OCR\tesseract.exe`; `tesseract` is not currently
  resolvable on PATH, so configure `DOCUMENT_OCR_TESSERACT_PATH` to that
  executable in this environment.
- The existing OCR trigger selected page 307 for OCR. Financial pages
  439–453 contain native text, so forced OCR there was a diagnostic comparison,
  not a claim that OCR is needed for those digitally encoded pages.
- High Tesseract confidence did not prevent numeric reading errors. OCR is
  therefore not qualified as an automatic source of financial facts.
- The scanned RHP sample page did not reconstruct as a table, and a forced OCR
  pass on a different financial page generated heuristic cells only. Wider
  page-by-page table validation remains necessary.
- OCR cannot be guaranteed error-free; reliability must come from source
  comparison, explicit review, preserved provenance, and refusal to calculate
  from unverified OCR candidates.

## Open questions / blockers

- Validate heuristic layout reconstruction on actual scanned financial tables
  and cover wrapped labels, percentages, merged cells, and low-confidence
  tokens.
- Add a browser smoke test for source rendering, highlighting, correction, and
  UI calculation state.
- Add authentication/authorization before associating reviews with a trusted
  reviewer identity or exposing private source pages beyond local use.
- Set a safe overall processing-time and concurrency policy for very large PDFs.
- Decide whether the product remains a single-user local app or will use an
  organization identity provider before implementing authenticated reviewer
  identity and authorization in Module 2.
- The canonical-fact mapping is still explicit and user-driven through the
  analysis workflow; a distinct Phase 3 fact-candidate/production workflow
  remains to be implemented.

## Next steps

1. Verify actual scanned RHP financial tables locally; do not commit or copy the
   PDF and do not treat OCR confidence as qualification.
2. Add browser smoke coverage and refine layout handling based on verified
   samples.
3. Address total processing limits and explicit retry/recovery behavior.

## Documentation updated

- Added the staged OCR/financial-number trust plan and this session note.
