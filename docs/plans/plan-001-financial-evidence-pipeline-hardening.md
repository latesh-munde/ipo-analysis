# PLAN-001: Financial Evidence Pipeline Hardening

- Status: In progress
- Created: 2026-10-17
- Related plans: [Phase 3 ingestion](./phase-3-document-ingestion-extraction-plan.md),
  [Phase 4 analysis](./phase-4-financial-analysis-engine-plan.md),
  [OCR number trust](./ocr-financial-number-trust-plan.md),
  [Large-document recovery](./plan-002-large-document-recovery.md)
- Related features: [Document ingestion](../features/document-ingestion.md),
  [Financial analysis](../features/financial-analysis.md)

## Problem and motivation

The application can extract and review some OCR-derived cells, but geometric
table reconstruction is heuristic and misses some scanned pages. Review actions
have no authenticated reviewer identity. Phase 3 emits raw extracted cells
rather than canonical, validated financial facts. Documents also have no
trusted issuer/IPO association, so the system cannot safely combine DRHP, RHP,
restated statements, or other filings.

These gaps affect the trust chain from a PDF page to a financial metric. Work
must proceed in small modules with measurable acceptance criteria. A passing
OCR confidence score or a plausible-looking table is never sufficient evidence
that a financial value is correct.

## Outstanding limitation map and execution order

The following blockers remain independent acceptance gates; completing one
does not establish that the full financial-analysis pipeline is complete.

1. **Scanned-table qualification:** heuristic geometry, wrapped/merged layouts,
   and accuracy on scanned financial statements remain unqualified. Complete
   the open Module 1 synthetic coverage and manually annotated scanned-page
   benchmark before claiming broad OCR-table use. The supplied Jio RHP probes
   are not a substitute for that benchmark.
2. **Phase 3 fact production:** users still map source cells through analysis.
   Implement a separate candidate-production workflow and automatic
   classification only with deterministic rules, explicit uncertainty, and
   source-bound evidence; do not infer missing values or silently approve
   candidates. This extends Module 3.
3. **Verified review identity:** remains deferred under the chosen trusted-local,
   single-user deployment. Do not expose the app as a shared or network service
   or label timestamps as verified reviewer identity. Revisit Module 2 only
   after an identity and authorization model is selected.
4. **Issuer/IPO association and cross-document analysis:** implement explicit,
   auditable association first (Module 4), then company-scoped analysis
   (Module 5); do not join documents by filename or extracted name.
5. **Large-document recovery:** add bounded extraction time, OCR concurrency
   limits, and retry/resume attempt history. This is Module 6 and can be
   implemented incrementally without waiting for Modules 1–5. The current
   update selects its first slice: a cooperative whole-extraction deadline
   with remaining-time limits on OCR.

The detailed operational plan is tracked in
[Large-document recovery](./plan-002-large-document-recovery.md). Its first
slice preserves successfully extracted pages, explicitly marks pages not
started after the deadline, and does not claim a hard deadline for synchronous
PyMuPDF calls. OCR concurrency control and retry/resume history remain open.

## Deployment decision

- The user chose trusted local single-user use. The application has no
  authentication, and review records must not claim a verified person as the
  reviewer. Run on loopback (`127.0.0.1`) only; shared/network deployment and
  attributable review approval remain out of scope until an identity provider
  is selected.

## Goals

- Make extraction limitations observable and prevent ambiguous OCR layouts
  from appearing more authoritative than they are.
- Preserve the chain of evidence from original PDF page, through reviewed
  financial facts, to calculated metrics.
- Record review identity only after an explicit authentication model exists.
- Persist validated financial facts with exact period, statement, scale, and
  evidence provenance.
- Associate documents with a company/IPO using an explicit, auditable
  relationship rather than names or extracted text alone.
- Enable cross-document analysis only when company, reporting scope, and
  evidence requirements are satisfied.

## Non-goals

- Guarantee error-free OCR or automatically repair uncertain digits.
- Infer an issuer match solely from a filename, OCR text, or a model.
- Automatically approve OCR values or financial facts.
- Add external OCR, an LLM extraction dependency, or cloud document storage.
- Add investment recommendations as a substitute for evidence-backed metrics.

## Current behavior

- Tesseract TSV retains word confidence and pixel boxes. Current row/cell
  reconstruction groups words from OCR line IDs and splits wide gaps; it is
  intentionally heuristic.
- Candidate cells retain source document hash, page geometry, engine/version,
  language, DPI, and cell boxes. Candidate extraction does not by itself certify
  a complete table or correctly interpreted row/period.
- Module 1 now also retains each contributing OCR token's confidence score.
  Candidate tables warn when any token confidence is below 60/100 or
  unavailable; this is an uncertainty indicator, not an accuracy guarantee.
- Rows with differing cell counts receive an explicit irregular-layout
  warning. When repeated numeric anchors establish a stable grid, values are
  aligned by their source positions and missing cells remain empty; otherwise
  the original row layout is retained.
- Where at least three repeated numeric right-edge anchors support a stable
  grid, numeric cells are aligned by their source-page x-position. A missing
  cell becomes an empty cell at that position; later values are not shifted.
  Rows without sufficient evidence retain their original layout and warning.
- Module 1 now retains the OCR word strings contributing to each candidate
  cell, applies a conservative numeric-column gate, and can join one wrapped
  label line to a following aligned numeric row when horizontal/vertical
  geometry supports that interpretation. Candidate boxes cover both label
  lines. This remains a heuristic, not a table recognition guarantee.
- A local review action persists the raw OCR string, confirmed transcription,
  source coordinates, and timestamp. There is no login or authenticated
  reviewer identity. New reviews also bind to a SHA-256 of the exact source
  cell, including the table fingerprint and bounding box; older unbound reviews
  are stale and require re-review.
- The analysis API blocks OCR values unless a persisted review matches the
  current cell text. The report still relies on user-supplied line-item and
  period mappings.
- The analysis request still requires an explicit line-item/period/unit/basis
  mapping and contains no numeric input. After source validation, the service
  persists canonical facts as immutable, idempotent revisions with document,
  table, and cell hashes. The report returns revisioned facts; a paginated
  endpoint exposes current facts or their history.
- Fact identity is anchored to the source value-cell locator, not mutable
  mapping metadata. Correcting a line-item/period mapping therefore creates a
  new revision of that fact instead of leaving two current mappings for one
  source cell. A request that maps one source cell more than once is rejected.
- The persisted-fact schema constrains status and currency to supported values.
- Analysis is scoped to one document. No issuer, IPO, or trusted
  document-to-company registry exists.
- Local RHP probe: scanned page 307 and digitally encoded page 446 produce no
  candidate under the current gate. The earlier loose split-plus-digit rule
  had treated page 446 prose fragments as four rows/eight cells; the current
  gate no longer does so. Page 307 OCR reads as an organization chart. Forced
  OCR of digitally encoded statement pages 329, 330, and 334 produces
  candidates; see the exploratory numeric comparison below. These pages do not
  establish scanned-table recall. The supplied filing has no confirmed,
  annotated scanned financial-table page.

## Module sequence and acceptance criteria

Modules are implemented and reviewed separately. Do not start a dependent
module until its prerequisites' acceptance checks pass. Modules marked
“decision required” need a product/security choice before implementation.

### Module 1 — OCR layout evaluation and conservative table candidates

**Status:** In progress; geometry/token provenance and wrapped-label handling
have an initial implementation and synthetic tests. Confidence provenance and
an irregular-row warning are also implemented. Real-page qualification is
blocked pending a representative scanned financial-table sample.

**Completed within this module**

- Retain each cell's contributing raw word strings with its geometric box.
- Merge a single nearby, x-aligned wrapped label fragment into the following
  numeric row under a narrow geometry rule.
- Require at least three candidate rows and two numeric-like non-label rows;
  currency prefixes, signed/parenthesized values, percentages, and dashes are
  classified without rewriting the original strings.
- Add deterministic synthetic tests for two amount columns, a wrapped label,
  parentheses, dashes, percentages, currency prefixes, source token strings,
  bounding-box union, and rejection of an isolated split line.
- Preserve per-token confidence and flag low/unavailable confidence without
  treating the score as proof of correctness.
- Preserve ragged rows without fabricating empty cells and warn when row cell
  counts differ.
- Align repeated numeric columns only when at least three source rows establish
  the x-position anchors; retain the original value strings and evidence boxes.

**Still open:** general grid/region detection, multi-line wrapped labels and
headers, robust merged-cell handling, broader ambiguity detection, and
qualification on scanned financial tables. Numeric-anchor alignment is
conservative and does not certify labels, periods, or a complete table.

**Scope**

- Establish synthetic layout fixtures and an annotation/evaluation procedure
  for real pages kept outside Git.
- Reconstruct candidate rows from geometric alignment with explicit handling
  for horizontal columns, vertically wrapped labels, line continuation, and
  visual gaps/merged cells where the source geometry supports those judgments.
- Keep raw OCR tokens immutable and preserve a link from each candidate cell
  to its contributing tokens and source-page box.
- Reject or downgrade ambiguous regions rather than filling missing cells,
  guessing row spans, or treating a page's unrelated text as a financial table.
- Surface when no reliable candidate is available and retain the page OCR
  output for manual inspection.

**Acceptance**

- Synthetic fixtures cover two or more amount columns; commas, decimals,
  parentheses, signs, dashes, and percentages; wrapped labels; irregular
  spacing; merged/missing cells; unrelated page text; and ambiguous alignment.
- Confidence scores remain associated with source tokens; low or absent scores
  produce a warning, and a ragged row is not padded or shifted to appear
  complete.
- When repeated numeric anchors are reliable, a row missing an intermediate
  cell retains an empty value at that column and subsequent amounts remain
  aligned.
- Repeated runs on identical OCR words produce identical rows, cell boxes,
  source-token references, and warnings.
- No geometry or OCR confidence rule silently fills a missing value or turns
  an ambiguous cell into a usable financial value.
- A locally annotated set of scanned financial pages reports candidate
  precision/recall and cell-level exact transcription accuracy. Each expected
  value is checked against its rendered PDF; OCR confidence is not the oracle.
- If the provided RHP lacks suitable scanned financial tables, record that as
  an evaluation gap and use a user-approved representative local sample or
  synthetic fixtures; do not claim real-page qualification from page 307 or
  forced OCR of digitally encoded page 446.

**Local exploratory results:** Forced 200-DPI OCR of digitally encoded
financial-statement pages 329, 330, and 334 produced candidate rows with
irregular-layout and low-confidence warnings. A spatial comparison of numeric
tokens in manually inspected table regions against the PDF text layer found
615 exact OCR transcriptions out of 618 OCR numeric tokens; 10 of 628 native
numeric tokens were not recovered. The mismatches include a punctuation
distortion that changes numeric scale. This is a small exploratory check, not
an annotated benchmark, and does not qualify scanned-table recall.

**Deliverable:** layout implementation, reproducible synthetic tests, and
documented local evaluation results without committing prospectus content.

### Module 2 — Authentication and attributable reviews (deferred)

**Prerequisite:** Module 1 candidate-cell locators and review-state contract.

**Decision:** trusted local single-user use, with no authentication. Do not
create a synthetic user ID or label an action/time record as verified identity.
The module's authenticated-attribution acceptance criteria are intentionally
deferred; revisit them before any shared or network-accessible deployment.

**Scope**

- Protect private document/page/review/analysis routes.
- Record immutable reviewer identity, action, time, source hash/cell revision,
  and review outcome.
- Define roles for reviewing OCR cells and managing issuer/document links.
- Handle revocation, review-history retention, and stale review invalidation.

**Acceptance**

- Unauthenticated callers cannot fetch private pages, write reviews, or
  calculate from protected documents.
- Every review is attributable to a stable authenticated principal and binds
  to the exact source document hash and current cell content.
- Re-review preserves the prior audit record; changed extraction invalidates
  the active approval without deleting history.
- Authorization, session/token handling, CSRF as applicable, and deployment
  configuration are documented and tested.

### Module 3 — Canonical financial-fact schema and Phase 3 producer

**Status:** Initial implementation verified for the local, single-document,
explicit-mapping workflow. Facts are persisted when the analysis path validates
them; deterministic automatic candidate classification and a separate
Phase 3-owned fact-production workflow remain open. Scanned-table qualification
and full acceptance review remain in progress.

**Prerequisites:** Module 1 locators and review/evidence contract; Module 2
identity policy if facts include reviewer attribution. Scanned-page OCR
qualification remains an independent release blocker; it does not relax the
per-cell review gate or permit unverified OCR facts into calculations.

**Scope**

- Define versioned persisted facts for line item, raw/confirmed value,
  normalized Decimal value, currency, unit, period kind/range/as-of date,
  statement type/basis, audit/restatement state, extraction/review status,
  and one or more stable evidence references.
- Distinguish reported facts from calculated facts and model interpretations.
- Produce candidate facts from extracted tables using deterministic rules and
  explicit human mapping/review where automatic classification is uncertain.
- Validate facts before persistence and invalidate/recompute when source
  extraction, reviewer transcription, or mapping changes.
- Preserve missing/blank values as unavailable, never zero.

**Acceptance**

- Schema validation rejects incompatible dates, statement/item mappings,
  malformed amount/unit combinations, unsupported currencies, stale evidence,
  and invalid review state.
- Every persisted fact resolves to the exact document hash, page, table/cell or
  bounded text span, extraction method, and review history.
- Reprocessing is idempotent and versioned; old facts remain auditable rather
  than being silently overwritten.
- API and repository tests prove missing or invalid facts cannot enter
  calculations as zero or client-supplied authoritative numbers.

### Module 4 — Trusted issuer, IPO, and document association

**Prerequisites:** Module 3 document and fact identifiers. Issuer/document
management remains restricted to the same trusted local single-user boundary;
it must not be exposed as a shared service without Module 2 authentication.

**Scope**

- Add company/issuer and IPO entities with stable IDs and controlled lifecycle.
- Associate documents through an explicit authorized action, recording who
  linked them, when, and on what basis.
- Store document role/version (for example DRHP, RHP, addendum, audited
  statement), issue identifiers, reporting periods, and supersession links.
- Treat extracted issuer names as suggestions requiring confirmation; do not
  equate similar names or tickers automatically.

**Acceptance**

- A document has no analysis-company scope until explicitly associated.
- Association history is auditable, authorized, reversible with history, and
  guarded against accidental cross-issuer linkage.
- Duplicate names and ambiguous issuer candidates require manual resolution.
- Tests prove facts cannot be queried across issuer boundaries by guessing or
  submitting another document/company identifier.

### Module 5 — Company-scoped cross-document analysis

**Prerequisites:** Modules 2–4.

**Scope**

- Change analysis inputs from arbitrary document IDs to an authorized issuer/
  IPO scope with an explicit set of approved facts/document versions.
- Resolve restatements, comparative statements, statement basis, periods,
  currencies, and units under documented precedence rules.
- Preserve all contributing document and cell evidence and report conflicts,
  superseded values, incompatible bases, and missing data.
- Keep the deterministic Decimal calculation engine independent of UI and
  interpretation models.

**Acceptance**

- Same facts and formula version produce reproducible results.
- No metric combines incompatible currencies, periods, standalone/consolidated
  bases, unauthenticated issuer associations, or superseded facts silently.
- Restatement precedence and conflict behavior are covered by hand-checked
  fixtures, including corrections and unresolved contradictions.
- API bypass tests prove callers cannot cross issuer/document authorization
  boundaries.

### Module 6 — Operational limits, recovery, and release evidence

**Prerequisites:** Modules 1–5 for full feature completion; relevant subset
checks may run earlier.

**Status:** In progress. A cooperative extraction deadline and remaining-time
cap for OCR are implemented; hard interruption of synchronous PyMuPDF work,
explicit OCR concurrency policy, and retry/resume attempt history remain open.
See [Large-document recovery](./plan-002-large-document-recovery.md).

**Scope**

- Bound whole-document time, memory/render size, OCR concurrency, and storage
  growth; make partial results and failed pages explicit.
- Define retry/resume semantics with attempt history and idempotent extraction.
- Add full-flow integration and browser tests for upload, OCR candidates,
  source viewing, review, fact production, issuer association, and analysis.

**Acceptance**

- Large documents respect documented resource bounds and release temporary
  resources after success/failure.
- Retries retain successful pages and do not duplicate facts/reviews.
- Full backend suite, Ruff, formatting, dependency checks, JavaScript syntax,
  browser flow, and migration/upgrade tests pass.
- Final evidence report lists real-page coverage, measured extraction metrics,
  false positives/negatives, limitations, and remaining blockers.

## Data integrity and security invariants

- The original PDF and its SHA-256 remain the source identity.
- OCR text, layout candidates, reviewed transcriptions, canonical facts, and
  calculated metrics are separate versioned states.
- Every candidate/fact/metric has resolvable evidence; review never mutates raw
  OCR output.
- An OCR confidence score never substitutes for verification.
- Missing, ambiguous, incompatible, stale, or unauthorized input blocks or
  yields an explicit unavailable state; it is never silently changed to zero.
- Uploaded PDF text is untrusted data and cannot direct application behavior.
- Private documents, page images, review history, and financial facts require
  authorization before non-local deployment.

## Testing and documentation strategy

- Keep synthetic OCR TSV/geometry fixtures deterministic and independent of an
  installed OCR executable.
- Keep representative prospectuses and annotations outside Git; document local
  file hashes and page references only when safe and approved.
- Use manually verified page-region annotations as the test oracle.
- Update the corresponding Phase 3/4 plans, feature guides, architecture, API
  contracts, security documentation, and session record as each module lands.
- Do not mark the Phase 3/4 plans complete until the dependent module
  acceptance criteria are met.

## Risks and open questions

- The current supplied RHP sample contains only one detected low-native-text,
  image-backed page in a simple page scan. It may not contain a representative
  scanned financial table. A suitable local evaluation document/page must be
  identified before real-scanned-table acceptance.
- Geometric heuristics can create plausible but false table structures.
  Conservative rejection lowers recall; accepting weak candidates risks
  presenting misleading cells. Module 1 must measure both outcomes.
- Authentication architecture depends on whether this remains a single-user
  local app or becomes a shared/deployed service. Resolve before Module 2.
- Structured-fact lifecycle and restatement conflict policy must be fixed
  before automatic cross-document analysis.
- Authentication, data migration, and association introduce compatibility and
  privacy work beyond OCR extraction alone.

## Completion notes

- Initial local RHP geometry probe completed. Module 1 is active; remaining
  modules have not started. No real scanned financial-table qualification is
  claimed.
- Module 1 first increment is implemented; focused and full regression results
  are recorded in the current session note. Its acceptance criteria remain
  open pending broader synthetic coverage and manually annotated scanned
  financial pages.
- Initial Module 1 increment verification: 58 backend tests passed (one existing
  deprecation warning); Ruff lint and changed-file formatting passed. These
  results do not satisfy the real-page qualification criterion.
