# OCR and Financial-Number Trust Plan

- Status: In progress; OCR layout and review gate implemented, reliability and
  real-page qualification still outstanding
- Created: 2026-10-17
- Priority: Financial-number extraction and evidence integrity
- Related plans: [Phase 3 ingestion](./phase-3-document-ingestion-extraction-plan.md), [Phase 4 analysis](./phase-4-financial-analysis-engine-plan.md)

## Objective

Enable scanned and mixed-content prospectuses to support financial analysis
without treating OCR as ground truth. Preserve the source image and extraction
alternatives, expose uncertainty, and require review of OCR-derived financial
figures before they can be used as reported inputs. Never silently repair,
round, infer, or substitute a number.

“Trustworthy” means auditable, explicit about uncertainty, reproducible, and
review-gated; OCR cannot be guaranteed error-free.

## Current assessment

- Phase 3 persists per-page selected text and raw tables with document/page
  references. Stage 1 now also persists native and OCR alternatives separately;
  the compatibility `text` field retains its prior selected-text behavior.
- OCR runs behind a local Tesseract adapter and is enabled by configuration.
  Tesseract 5.5.3 with English data is installed locally and was exercised on
  the provided RHP; the test exposed numeric errors even at high reported
  confidence, so OCR is not qualified for automatic financial-number use.
- Table extraction uses PyMuPDF's line-based extraction. OCR text is not
  converted into table cells, so scanned financial tables do not yet feed the
  Phase 4 source-cell workflow.
- Phase 4 accepts user-selected cells from stored tables and reports OCR
  provenance/warnings where available. It does not yet have an explicit
  server-enforced human verification contract for OCR-derived financial facts.
- The user-provided local test filing is
  `C:\Users\lates\Downloads\Red Herring Prospectus jio.pdf`. It must remain
  local and must not be committed or sent to external services.

## Staged implementation

### Stage 1 — Preserve native and OCR readings (verified)

- Keep the existing `text` field and selection behavior for compatibility.
- Persist native text and OCR text separately; `null` OCR text means OCR was
  not run, while an empty string means OCR ran but found no text.
- Display the chosen text and both extraction readings in the UI when
  available.
- Add an explicit warning that OCR text, especially numbers, has not been
  verified against the source.
- Add tests for native-only, OCR-used, OCR-not-selected, and persistence paths.

**Acceptance:** OCR can no longer erase the native reading, API round-trips both
alternatives, and users see the unverified status. Targeted regression tests
and the full backend regression suite pass.

### Stage 2 — Live OCR qualification on financial pages (tested; automatic use not qualified)

- Install/configure local Tesseract and language data only in the development
  environment; do not add a cloud OCR dependency or transmit documents.
- Verify Tesseract version/language availability and run OCR against scanned
  and mixed pages from the local RHP.
- Build a manually checked test ledger of financial figures from selected
  pages; compare OCR output exactly, including signs, parentheses, separators,
  decimal places, percentages, and units.
- Record failure modes and restrict supported page types or OCR settings when
  exact number accuracy is not adequate. Confidence is a warning signal, not a
  correctness guarantee.

**Acceptance:** actual scanned pages are processed locally and results,
limitations, and measured numeric discrepancies are recorded. This test stage
is complete, but its result is a failure to qualify OCR as an automatic source
of financial numbers. The human-review gate remains mandatory.

**Observed on the supplied local RHP:** Tesseract 5.5.3 (`eng`) processed
scanned PDF page 307 through the application extractor: native text was 42
characters, OCR returned 751 characters at mean word confidence about 0.816,
and the page was marked `completed_with_warnings` with a financial-number
review warning. Forced OCR of financial narrative pages 439–453 produced mean
confidence between 0.915 and 0.961. Comparison of digit-like token sets against
native PDF text found number differences on several pages. On page 446,
eight unique native number strings were absent from OCR and eight OCR strings
were extra; visual inspection confirmed leading-digit corruption on financial
amounts despite OCR confidence about 0.939. These token-set checks are a
diagnostic, not a general accuracy score. OCR must not be treated as a trusted
financial value.

The later layout pass was exercised locally on two pages from the same RHP:
the previously sampled scanned page 307 produced 101 word boxes but no
multi-row/multi-column table candidate; forced OCR on digitally encoded page
446 produced four heuristic rows/eight cells. This demonstrates that current
layout grouping does not reconstruct every scanned financial table and that a
nonempty candidate is not evidence of correct cell assignment. No OCR candidate
was promoted to trusted data by this check.

### Stage 3 — Layout-aware OCR financial cells

- Implemented: OCR output retains word text, confidence, Tesseract TSV
  bounding boxes, and engine version. Heuristic OCR rows/cells are persisted
  with page geometry, cell boxes, language, engine, and render DPI.
- OCR candidates are separate from native extracted tables and retain the
  original token strings; the candidate UI labels them as heuristic.
- Keep unreadable or ambiguous values unparsed; do not infer a value from
  surrounding rows or comparative periods.

**Acceptance status:** Basic synthetic multi-column extraction and geometry
round-trip tests are implemented. Full acceptance is outstanding: wrapped
labels, percentages, merged cells, low-confidence handling, real scanned RHP
financial tables, and systematic raw-token/cell mapping have not been
qualified. The RHP sample previously demonstrated OCR number errors.

### Stage 4 — Human verification gate and source viewer

- Implemented: an in-app source-page endpoint/view highlights the selected
  OCR cell; the user submits a confirmed transcription and `source_checked`
  acknowledgment.
- Implemented: SQLite persists source OCR text, confirmed text, source
  coordinates, and timestamp without mutating extraction output.
- Implemented: the API only calculates from a matching persisted review.
  Unreviewed or stale OCR values become `unverified`, and dependent metrics
  are blocked with `OCR_VALUE_UNVERIFIED`.

**Acceptance status:** backend API tests verify unreviewed bypass attempts are
blocked and reviewed corrections preserve/use the confirmed value. A browser
smoke test and authenticated reviewer identity are outstanding.

### Stage 5 — Reliability, retry, and end-to-end regression

- Add an overall document processing deadline and bounded rendering/OCR
  concurrency suitable for large prospectuses; keep successful page results
  when a page fails.
- Add an explicit retry/resume policy for failed/interrupted documents while
  preserving attempt history and idempotency.
- Test persisted partial success, failure recovery, retries, duplicate uploads,
  oversized/page-limited PDFs, OCR unavailable/timeout, and mixed native/scanned
  documents through service/API paths.
- Run the full backend suite, lint, formatting, dependency, frontend syntax,
  and browser smoke checks.

**Acceptance:** long documents have a documented resource policy, failures are
visible and recoverable, and existing extraction/analysis behavior remains
compatible.

## Boundaries and non-goals

- No external/cloud OCR, LLM number extraction, or silent value correction.
- No claim that OCR is “100% accurate” or “foolproof.”
- Review records are not tied to authenticated identities, and user-entered
  period, basis, and line-item mapping remains explicitly declared.
- This work does not by itself create issuer identity or cross-document
  association; that remains a separate Phase 4 integration dependency.
- The original PDF is the source of truth; extracted text is a derived,
  potentially erroneous representation.

## Verification record

- Baseline before Stage 1: `backend\.venv\Scripts\python.exe -m pytest` —
  51 passed, one existing Starlette/httpx deprecation warning.
- Stage 1 results and subsequent verification are recorded in the linked
  session note.
- Stage 1 full backend regression: 53 passed, one existing
  Starlette/httpx deprecation warning. Ruff lint, changed-file formatting,
  dependency check, JavaScript syntax, and `git diff --check` passed.
- Live OCR was exercised on the supplied local RHP, but automatic OCR-number
  use did not pass qualification. See the Stage 2 sample results above.
- This implementation increment: full backend suite — 56 passed, one existing
  Starlette/httpx deprecation warning; Ruff lint, changed-file format check,
  `pip check`, `node --check frontend\js\app.js`, and `git diff --check` passed.
- Local browser smoke loaded the application and health endpoint. Page-image,
  review persistence, bypass blocking, and corrected-value behavior are also
  covered by API tests; a browser upload-to-review click-through is outstanding.
