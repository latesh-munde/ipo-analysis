# Phase 3 --- Document Ingestion and Extraction
**Project:** IPO Analysis System\
**Phase:** 3\
**Status:** In progress\
**Prerequisite:** Phase 2 is assumed complete.\
**Audience:** Coding agent and reviewer

## 1. Objective
Implement a reliable pipeline to accept IPO PDFs, extract text and
tables, use OCR for scanned pages when needed, validate extraction
results, and preserve source/page references.
This phase produces traceable document content. It does **not** decide
whether to apply for an IPO or perform investment analysis.

## 2. Scope

### In scope
-   Accept PDF documents such as DRHP, RHP, and financial statements.
-   Validate files before processing.
-   Extract text page by page.
-   Use OCR for scanned or low-text pages when configured.
-   Extract tables where supported.
-   Preserve document, page, and table references.
-   Report extraction status, warnings, and failures.
-   Detect exact duplicate files.
-   Handle invalid, incomplete, and partially readable PDFs.
-   Add tests and update relevant documentation.
### Out of scope
-   IPO scoring, valuation, or apply/avoid recommendations.
-   LLM-based interpretation of financial data.
-   Automatic web crawling or document downloading.
-   Broad architectural rewrites or new infrastructure without approval.
-   Silent correction or guessing of missing values.
-   Non-PDF support unless already required by the project.
## 3. Mandatory Agent Instructions
1.  Inspect the repository before coding: `README.md`, `AGENTS.md`,
    `CODING_STANDARDS.md`, architecture docs, Phase 2 code, dependency
    files, API patterns, persistence, and tests.
2.  Reuse existing architecture, naming, configuration, logging, error
    handling, and test conventions.
3.  Before implementation, provide a brief repository assessment,
    proposed file changes, dependency choices, and any blocking
    decisions.
4.  Do not assume paths or class names. Follow the repository's actual
    conventions.
5.  Keep PDF parsing, OCR, validation, and duplicate detection
    deterministic and testable.
6.  Preserve source document and page references for extracted text and
    tables.
7.  Never fabricate missing values or silently mark uncertain OCR output
    as verified.
8.  Preserve successful pages when another page fails. Report partial
    results and warnings explicitly.
9.  Avoid unrelated refactoring and unnecessary dependencies.
10. Do not transmit documents to external services or introduce paid
    services without approval.
11. Do not commit real IPO PDFs, credentials, `.env` files, virtual
    environments, temporary OCR output, or generated binaries.
12. Update documentation only to describe behavior that is actually
    implemented.
13. Run tests and report exact commands and results. Never claim unrun
    tests passed.
14. If multiple agents are used, agree on shared interfaces first and
    assign non-overlapping tasks.

## 4. Repository Assessment
Before coding, identify:
-   Backend entry point, framework, routes, and service organization.
-   Phase 2 data models and how IPOs or analysis requests are
    represented.
-   Existing file upload/storage and persistence mechanisms.
-   Configuration and dependency-management conventions.
-   Existing logging, exception handling, and test commands.
-   Existing PDF/OCR dependencies, if any.
-   Documentation locations for plans, architecture, APIs, and tests.
**Deliverable:** a concise assessment and implementation checklist. Do
not create duplicate abstractions if the project already has suitable
ones.

## 5. Proposed Pipeline
Adapt this logical flow to the current codebase:

``` text
Upload
  -> Validate file
  -> Register metadata and SHA-256 hash
  -> Inspect PDF and enumerate pages
  -> Extract native text per page
  -> OCR scanned/low-text pages when configured
  -> Extract tables where supported
  -> Validate results and record warnings
  -> Persist results and provenance
  -> Return status and extracted content
```

Keep responsibilities separated enough to test independently. Use the
existing synchronous/asynchronous model. Introduce background jobs only
if current request limits or processing time require them.

## 6. Upload Validation
Requirements:
-   Accept PDF files for the initial version.
-   Enforce a configurable maximum file size before expensive
    processing.
-   Check extension, declared content type, and PDF signature/structure;
    do not trust any one check alone.
-   Reject empty, malformed, unreadable, or unsupported files with
    controlled errors.
-   Explicitly handle encrypted/password-protected PDFs unless the
    project already supports them.
-   Use a generated internal ID; never use an untrusted filename as a
    storage path.
-   Store files using the existing storage abstraction and clean up
    temporary files.
-   Do not expose local paths or stack traces in API responses.
**Acceptance:** valid PDFs are accepted; invalid and oversized files
fail safely without unhandled exceptions.

## 7. Document Metadata and Status
Reuse the current data model where possible. Record at least:
-   Internal document ID and original filename.
-   File size, detected type, and SHA-256 hash.
-   Registration/upload timestamp.
-   Document type, if provided or reliably identified.
-   Processing status and page count, when available.
-   Extraction warnings/errors.
-   Extraction tool/configuration version where practical.
-   Source-file reference, if the application stores uploaded files.
Suggested statuses, adapted to existing conventions:
-   `uploaded`
-   `processing`
-   `completed`
-   `completed_with_warnings`
-   `failed`
-   `rejected`
-   `duplicate`
Define valid transitions. A failed run must not leave a document
permanently marked `processing`. Do not report `completed` if material
extraction failures occurred.

## 8. Native PDF Text Extraction
Requirements:
-   Extract text per page, not only as one flattened document string.
-   Use consistent one-based PDF page numbers in external results.
-   Preserve useful line breaks and financial formatting.
-   Record the extraction method and page-level status.
-   Detect empty or unusually low-text pages using explicit heuristics.
-   Distinguish blank pages from likely scanned pages where possible.
-   Preserve raw extracted text if normalized text is also stored.
-   Record a result or failure for every expected page.
Each page result should include:
-   Document ID.
-   One-based PDF page number.
-   Extracted text.
-   Extraction method.
-   Status and warnings/errors.
-   Basic quality indicators, such as character count.
Printed page labels such as `iv` or `A-3` must not be confused with PDF
page position. Store printed labels separately only if reliably
available.
**Acceptance:** text-based PDFs return ordered, traceable page results,
including explicit results for blank or failed pages.

## 9. OCR for Scanned Pages
Requirements:
-   OCR only pages that need it, based on documented heuristics or a
    controlled fallback.
-   Support mixed PDFs with both native-text and scanned pages.
-   Keep OCR behind a small adapter or equivalent boundary.
-   Make OCR engine, language, and required paths configurable.
-   Record OCR method, status, warnings, and confidence when available.
-   Handle missing dependencies, missing language data, timeouts, and
    page-rendering errors.
-   Do not replace good native text with worse OCR output without a
    tested rule.
-   Do not treat OCR text as guaranteed accurate, especially for
    decimals, negative values, percentages, dates, and tables.
If OCR is unavailable, report that clearly. Do not silently return empty
text as though OCR succeeded.
**Acceptance:** scanned pages can be processed when OCR is configured;
OCR failures remain visible and do not erase successful pages.

## 10. Table Extraction
Requirements:
-   Use a library compatible with the existing runtime and deployment
    environment.
-   Extract tables into rows and columns where supported.
-   Associate every table with document ID, PDF page number, table
    ID/index, and extraction method.
-   Preserve raw cell values; normalization must not overwrite them.
-   Represent empty cells consistently.
-   Record table-level warnings and allow page-text extraction to
    succeed if table extraction fails.
-   Do not promise perfect extraction for merged cells, complex layouts,
    multi-page tables, rotated pages, or scanned tables.
This is an example, not a required schema. Follow existing model and API
conventions.
Test raw values such as `1,234.56`, `(45.20)`, `-`, `0.00`, and `12.5%`
to ensure extraction does not silently change them.
**Acceptance:** supported tables retain their structure and page
references; table failures are reported without discarding usable text.

## 11. Validation and Provenance
Validate at three levels:
**File level** - File can be opened and has a valid page count. - File
meets configured limits. - Unsupported, encrypted, or corrupt cases have
explicit outcomes.
**Page/table level** - Page numbering and ordering are consistent. -
Every expected page has a result, even if extraction failed. - Empty
output and extraction errors are recorded. - Every table has a
document/page reference. - Raw values are preserved.
**Document level** - Overall status reflects page-level outcomes. - A
document with no usable text or tables is not reported as successfully
extracted. - Warnings and failures can be retrieved. - Retries do not
create duplicate page/table results.
Every extracted text or table result must be traceable to its source
document and PDF page. Preserve OCR/native extraction method. Do not
infer missing financial values or perform financial consistency analysis
in this phase.

## 12. Duplicate Detection

### Exact duplicates
-   Compute SHA-256 from uploaded file bytes.
-   Identical hashes should follow one documented policy: return the
    existing document or create an explicit duplicate relationship.
-   Avoid repeating expensive extraction for exact duplicates by
    default.
-   Ensure retries and repeated requests are safe.
### Possible logical duplicates
Different files may represent the same issuer/document period but differ
in bytes.
-   Use metadata only when available and reliable.
-   Flag possible duplicates for review rather than automatically
    merging them.
-   Do not treat filename equality as proof.
-   Do not assume DRHP and RHP files are duplicates; they may be
    different revisions.
**Acceptance:** identical files are detected reliably, while distinct
prospectus versions remain separate.

## 13. API and Persistence
Follow existing API and persistence patterns. Do not create a parallel
API or introduce a new database without approval.
If equivalent endpoints do not exist, implement the minimum needed to:
-   Upload/register a PDF.
-   Retrieve document metadata and processing status.
-   Retrieve page-level text and warnings.
-   Retrieve extracted tables.
Use stable IDs, structured errors, and appropriate status codes. Do not
expose stack traces, internal paths, or secrets. Apply existing
authentication/authorization rules.
Persist document metadata, page results, tables, and warnings using
existing models or small extensions. Add migrations if the project
already uses them. Make retries idempotent.
Example values are illustrative. Return real counts and warnings only.

## 14. Configuration, Dependencies, and Security
Use the project's existing configuration mechanism. Add only settings
actually needed, such as:
-   Maximum upload size.
-   Storage/temp directory.
-   OCR enabled/disabled.
-   OCR engine, language, and required paths.
-   OCR timeout and page-selection threshold.
-   Processing concurrency limits, if necessary.
Before adding libraries, check runtime compatibility, maintenance,
licensing, extraction capability, deployment requirements, and external
executable requirements. Document setup and pin/constrain dependencies
according to existing practice.
Treat PDFs as untrusted input:
-   Enforce size and processing-time limits.
-   Protect against path traversal and unsafe filenames.
-   Do not execute embedded scripts or attachments.
-   Limit OCR/rendering concurrency and clean up temporary files.
-   Avoid logging full document content.
-   Do not send documents to external OCR services without explicit
    approval.

## 15. Error Handling and Logging
-   Use existing logging and exception conventions.
-   Log document ID, page number, stage, duration, and error code where
    useful.
-   Do not log secrets or full document contents by default.
-   Separate validation errors from unexpected internal errors.
-   Preserve successful pages when another page fails.
-   Return user-safe messages and structured warning/error codes.
-   Clean up temporary resources after success or failure.
-   Ensure retries do not duplicate results.
## 16. Testing
Use the repository's existing testing framework. Keep unit tests
independent of real OCR executables, network access, and live services
where possible.

### Unit tests
-   File validation and size limits.
-   SHA-256 and duplicate policy.
-   PDF inspection and page numbering.
-   Native text extraction and empty pages.
-   OCR selection, missing dependencies, failures, and timeouts.
-   Table normalization and raw cell preservation.
-   Provenance, status transitions, and partial success.
-   Retry/idempotency and safe error responses.
### Integration tests
-   Upload and retrieve a text-based PDF.
-   Process a scanned PDF when OCR is available.
-   Process a mixed PDF.
-   Extract a known table with a page reference.
-   Handle corrupt, empty, encrypted, and oversized PDFs.
-   Upload identical bytes twice.
-   Simulate a page failure and verify successful pages remain
    available.
-   Verify persisted document, page, table, and warning records.
Use small synthetic, non-sensitive fixtures covering text PDFs,
scanned/mixed pages, simple financial tables, blank pages, corrupt
files, and duplicate cases. Do not commit real IPO documents without an
explicit licensing/privacy basis.
**Quality gates:** - New tests pass. - Existing Phase 2 regression tests
pass. - Configured formatting, linting, and type checks pass. -
OCR-specific environment requirements are documented. - No
developer-specific paths or sensitive artifacts are committed.

## 17. Implementation Sequence
Complete the stages in order unless repository findings justify a
documented adjustment.
1.  **Inspect and design:** assess Phase 2, choose interfaces, document
    dependencies and unresolved decisions.
2.  **Upload and duplicates:** implement validation, metadata, hash,
    exact duplicate behavior, and tests.
3.  **Native text:** inspect pages, extract text, preserve page results,
    and test.
4.  **OCR:** add adapter/configuration, page-selection logic, failure
    handling, and tests.
5.  **Tables:** extract structured tables, preserve raw
    values/provenance, and test.
6.  **Persistence and API:** store results, expose status/content, and
    verify idempotency.
7.  **Hardening:** test invalid inputs, partial failures, cleanup, and
    Phase 2 regressions.
8.  **Documentation:** update setup, API, configuration, architecture
    decisions, tests, and plan status.
At each stage, run the relevant tests before continuing. Keep changes
focused.

## 18. Definition of Done
-   [x] Valid PDFs can be uploaded/registered.
-   [x] Invalid, unsupported, and oversized files fail safely.
-   [x] Text is extracted page by page.
-   [ ] OCR is used for scanned pages when configured and needed.
-   [x] OCR/table failures are visible and do not erase successful text.
-   [x] Tables retain structure and page references where supported.
-   [x] Document, page, and table results preserve provenance.
-   [x] Raw extracted values are not silently modified or fabricated.
-   [x] Exact duplicate detection follows a tested policy.
-   [x] Partial-success statuses and warnings are accurate.
-   [x] Retries do not create duplicate extraction records.
-   [x] Dependencies, configuration, setup, API behavior, and
    limitations are documented.
-   [x] New tests and existing Phase 2 regression tests pass.
-   [x] Relevant project documentation is updated.
-   [x] No credentials, real private documents, or temporary artifacts
    are committed.
-   [x] Final report lists verified behavior, test commands/results,
    limitations, and remaining work.

## Current implementation verification — 2026-10-17

- `python -m pytest`: 29 passed; one upstream Starlette/httpx deprecation warning.
- `python -m pip check`: passed.
- `python -m ruff check .`: passed.
- Formatting of changed Python files: passed.
- Repository-wide `python -m ruff format --check .` still reports the existing
  formatting difference in `backend/app/core/logging.py`; that unrelated file
  was not changed.
- OCR adapter/selection and failure handling are unit-tested with a mocked
  Tesseract executable. The environment has no installed Tesseract executable,
  so a live scanned-PDF OCR check remains outstanding. Phase status remains
  **In progress** until that criterion is verified.

## 19. Required Completion Report
The agent must report:
1.  Summary of implemented and remaining work.
2.  Final pipeline and significant design decisions.
3.  Files changed, grouped by code, tests, configuration, and
    documentation.
4.  Dependencies added and installation requirements.
5.  Actual API routes with request/response and error examples.
6.  File validation, OCR, table, duplicate, and status behavior.
7.  Exact test commands and results.
8.  Manual checks performed, if any.
9.  Known limitations and deferred work.
Do not report tests as passing unless they were run. Clearly distinguish
verified behavior from assumptions.

## 20. Escalation Rules
Do not stop for choices already settled by repository conventions. Ask
the project owner before decisions that materially affect security,
cost, external data transmission, or architecture---for example:
-   Introducing paid/cloud OCR or transmitting documents externally.
-   Replacing the database or storage architecture.
-   Adding major infrastructure or broadening supported file types.
-   Making irreversible duplicate-merging decisions.
Otherwise, choose the safest minimal approach compatible with the
current project and document the assumption.
------------------------------------------------------------------------
**Core principle:** every extracted result must be traceable, every
failure visible, and every uncertain value distinguishable from verified
source content.
