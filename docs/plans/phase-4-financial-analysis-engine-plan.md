# Phase 4 — Financial Analysis Engine: Implementation Plan
**Project:** IPO Analysis System
**Phase:** 4
**Status:** Planned; implementation delegated to a coding agent
**Objective:** Convert validated financial facts from Phase 3 into deterministic metrics and a traceable financial report.
## 1. Purpose
Phase 4 consumes structured facts extracted from IPO documents and calculates financial performance, financial position, cash-flow indicators, and ratios. The output must distinguish reported facts, derived metrics, unavailable values, validation findings, and calculation failures.
The calculations must be deterministic and implemented in ordinary testable code. An AI model may explain results in a later phase, but must not invent or override authoritative financial values.
### In scope
- Canonical financial-data models and reporting periods. • Normalization of labels, units, currencies, signs, and period metadata. • Structural, semantic, and cross-statement validation.
- Revenue growth, profitability, margins, debt, liquidity, cash flow, and selected ratios. • Multi-period comparisons with period compatibility checks. • Formula versioning, input references, and calculation statuses.
- Basic report generation with source evidence. • Unit tests, integration tests, fixtures, and documentation.
### Out of scope
- Document upload, PDF extraction, tables, or OCR; these belong to Phase 3. • Final “apply/avoid” recommendations or investment scoring. • Future financial forecasting or IPO valuation.
- Market price, grey-market premium, subscription, or listing-performance analysis. • Automatic correction of source values without explicit evidence. • LLM-generated numerical calculations as the source of truth.
- Legal, tax, audit, or regulatory certification.
## 2. Instructions for the coding agent
1. Inspect the repository before editing. Do not assume file names, classes, routes, database technology, or framework versions.
2. Read `AGENTS.md`, `CODING_STANDARDS.md`, `README.md`, architecture docs, existing phase plans, and relevant tests.
3. Treat Phase 2 foundation as implemented, but verify the actual repository state.
4. Treat Phase 3 as the upstream document ingestion and extraction phase; inspect its actual data contract before implementing adapters.
5. Save this plan under `docs/plans/`, following the repository naming convention. Suggested path: `docs/plans/phase-4-financial-analysis-engine.md`.
6. Do not refactor unrelated modules or break existing APIs without documenting why.
7. Implement in small, reviewable stages and test each stage.
8. Never silently fill missing values, assume units, mix periods, or replace extracted data with guesses.
9. If an upstream field is absent, document the dependency and provide an explicit unavailable-data path.
10. Record significant unresolved architecture choices in a decision note before implementation.
11. Keep the design tool-independent; do not require a specific agent, model, or proprietary skill.
12. Do not mark work complete unless code, tests, and documentation support that claim.
13. Finish with changed files, test commands and results, known limitations, and remaining work.
## 3. Repository discovery and baseline
- Identify backend package layout, app entry point, configuration, and dependency management. • Identify existing company, IPO, document, extracted-fact, financial-data, and report models. • Inspect Phase 3 fact structure and evidence-reference format.
- Identify persistence boundaries; do not add a database merely by assumption. • Identify API route conventions, schemas, and error response format. • Identify test framework, fixtures, linting, formatting, and type-check commands.
- Run existing tests before changes and record the baseline. • Preserve existing API contracts wherever practical. • Confirm the supported Python version from project configuration; do not change it casually.
- Map the proposed modules to existing architecture and avoid duplicate domain models.
## 4. Proposed architecture
Use existing repository conventions. The following are logical responsibilities, not mandatory filenames.
- **Domain models:** financial facts, periods, evidence references, metrics, and findings. • **Normalization:** canonical labels, period parsing, units, and sign conventions. • **Validation:** structural, semantic, cross-statement, and calculation-readiness checks.
- **Calculation engine:** pure deterministic functions with explicit inputs and outputs. • **Metric registry:** stable metric codes, formulas, required inputs, versions, and display metadata. • **Report builder:** assembles results, source references, warnings, and limitations.
- **Application service:** orchestrates retrieval, validation, calculation, and reporting. • **API layer:** follows existing FastAPI conventions. • **Frontend:** renders backend-calculated values and evidence.
- **Tests and fixtures:** synthetic statements, missing-data cases, and expected results.
### Dependency direction
- Domain models must not depend on HTTP handlers or frontend code. • Formula functions must not perform I/O, network calls, database access, or UI operations. • Validation returns structured findings; it must not silently mutate facts.
- Report generation consumes calculated results and evidence; it does not extract documents. • API handlers orchestrate services and translate errors into standard responses. • Treat extracted data as untrusted input.
## 5. Canonical data model
Adapt existing types where possible. Each financial fact should represent one value for one metric and period.
### Financial fact fields
- Stable fact ID. • Company or IPO identifier. • Statement type: profit and loss, balance sheet, cash flow, or other.
- Canonical line-item code and original extracted label. • Decimal-safe numeric value. • Currency and scale/unit, such as INR, thousand INR, lakh INR, or crore INR.
- Period start and end dates, or an as-of date for point-in-time balances. • Period kind: annual, interim, quarterly, trailing period, or point-in-time. • Source document ID and document type, such as DRHP or RHP.
- Page number and optional table, row, cell, or extraction reference. • Extraction confidence/quality metadata if supplied by Phase 3. • Status such as reported, normalized, unavailable, rejected, or superseded.
- Statement basis such as consolidated or standalone, if available. • Audit/restatement status, if available.
### Reporting periods
- Store actual dates; do not rely only on labels such as FY24. • Preserve the source fiscal-year convention and period end date. • Distinguish annual periods from shorter interim periods.
- Distinguish income-statement flow periods from balance-sheet as-of dates. • Do not compare periods with materially different durations as equivalent. • Support fiscal years ending in months other than March.
- Flag unresolved period labels for review.
### Numeric precision
- Use `Decimal` or the project's equivalent for authoritative financial arithmetic. • Avoid binary floating point for currency values and rounding-sensitive formulas. • Preserve original value and unit when creating normalized values.
- Define display rounding separately from internal calculation precision. • Do not round intermediate values unless the formula requires it. • Handle zero, negative, and large values safely.
### Evidence reference
- Point to the smallest available source location that can be inspected. • Include document ID and page number when available. • Include table/row/cell or extraction-fact ID when available.
- Preserve original label and extracted text when supported. • Never fabricate a page number or source locator. • If provenance is missing, expose that limitation in the report.
## 6. Normalization
- Map known label aliases to canonical line-item codes through an explicit registry. • Preserve original labels and record the mapping used. • Keep mappings centralized rather than scattering them across formulas.
- Leave ambiguous labels unresolved instead of forcing a match. • Normalize scale only when the source unit is known. • Keep currency conversion out of scope unless a reliable dated rate source is explicitly approved.
- Never combine currencies without a documented conversion policy and rate evidence. • Normalize signs only according to a documented statement convention. • Preserve whether expenses and cash outflows were reported as positive or negative.
- Keep missing, zero, not applicable, and not disclosed as distinct states. • Do not treat a dash or blank as zero without a source-specific rule. • Do not derive facts from narrative text unless Phase 3 supplies a structured fact with provenance.
## 7. Required line-item concepts
### Profit and loss
- Revenue from operations. • Other income and total income, if reported. • Cost of materials, cost of goods sold, purchases, and inventory changes, when applicable.
- Employee benefit expense. • Finance costs. • Depreciation and amortization.
- Other expenses. • Profit before exceptional items and tax. • Exceptional items.
- Profit before tax (PBT). • Tax expense. • Profit after tax (PAT) / profit for the period.
- Basic and diluted EPS, when reported.
### Balance sheet
- Current and non-current assets. • Inventories, trade receivables, cash equivalents, and other bank balances where disclosed. • Total assets.
- Share capital, reserves, and total equity. • Current and non-current borrowings. • Lease liabilities, where disclosed.
- Trade payables and other current/non-current liabilities. • Total equity and liabilities. • Contingent liabilities as separate disclosures, not automatically funded debt.
### Cash flow
- Cash flow from operating activities (CFO). • Cash flow from investing activities (CFI). • Cash flow from financing activities (CFF).
- Net increase/decrease in cash and cash equivalents. • Opening and closing cash and cash equivalents. • Capital expenditure only if explicitly available or derived under a documented rule.
### Optional supplementary inputs
- Weighted average shares, if relevant to EPS validation. • Related-party disclosures, auditor qualifications, restatements, or segment data may be surfaced only when supported by upstream extraction. • Optional inputs must not be required for the entire engine to run.
## 8. Validation framework
Every finding must have a stable code, severity, message, affected fact IDs, and a recommended resolution where appropriate.
### Structural checks
- Required identifiers and statement type are present. • Numeric values parse and are finite. • Period dates are valid and correctly ordered.
- Currency and unit are known or explicitly unknown. • Evidence references conform to the upstream schema. • Duplicate facts are detected using company, metric, period, statement, unit, and source identity.
- Conflicting duplicates are flagged rather than arbitrarily selected.
### Semantic checks
- Income-statement flows use compatible period ranges. • Balance-sheet facts use an as-of date. • Cash-flow values are not treated as point-in-time balances.
- Ratios use compatible units and periods. • Percentages are not treated as currency. • EPS is not treated as total profit.
- Debt definitions explicitly state which borrowing categories are included. • Suspicious scale differences are flagged rather than automatically rescaled. • Consolidated and standalone facts are not mixed silently.
- Audited, restated, and interim periods remain distinguishable.
### Cross-statement checks
- Compare total assets with equity plus liabilities when all components are available. • Compare opening cash plus net movement with closing cash when available. • Compare subtotals with component sums only when definitions are compatible.
- Use documented, configurable tolerances for rounding differences. • Do not fail the whole analysis because one component is missing. • Never claim a check passed if required inputs are unavailable.
### Severity model
- **ERROR:** invalid or contradictory input blocks a particular calculation. • **WARNING:** potential issue affects interpretation but does not block all analysis. • **INFO:** limitation, unavailable disclosure, or non-blocking observation.
- Do not reduce all validation results to one boolean. • Each metric carries its own status and relevant validation references.
## 9. Deterministic calculation contract
- Inputs are canonical facts for a company and a defined set of periods. • Outputs include metric code, period, value or unavailable status, formula version, input fact IDs, and findings. • Same inputs and formula version must yield the same result.
- Formula code must not call external services or AI models. • Missing required inputs produce explicit unavailable results with reason codes. • Zero denominators never cause unhandled exceptions or misleading values.
- Negative denominators follow a documented metric-specific policy. • Calculation errors are isolated so unrelated metrics can still be returned. • Formula definitions are documented and tested with hand-calculated examples.
- No calculation may silently alter its source facts.
## 10. Metric definitions
### Revenue and growth
- Revenue growth (YoY) = (current revenue − prior comparable revenue) / prior comparable revenue × 100. • Require comparable duration, compatible revenue definitions, currency, and normalized units. • If prior revenue is zero, return unavailable with `ZERO_BASELINE`.
- If prior revenue is negative or growth is not meaningful, apply a documented policy. • Do not substitute total income for revenue from operations without explicit labelling. • Multi-year CAGR is optional and requires reliable endpoints and elapsed duration.
### Profitability
- Gross profit/margin require revenue and a compatible cost-of-sales definition. • Operating profit/margin require a reported operating-profit value or documented derivation. • EBITDA can be derived only from a compatible profit measure and explicit finance costs, tax, depreciation, and amortization.
- Do not assume all issuers define EBITDA identically. • PBT margin = PBT / revenue × 100, with compatible periods and non-zero revenue. • PAT margin = PAT / revenue × 100, with compatible periods and non-zero revenue.
- Profit growth must handle sign transitions explicitly. • When profit changes from loss to profit, show absolute change and a sign-transition note rather than a misleading simple percentage.
### Debt and leverage
- Total borrowings includes only explicitly selected borrowing line items. • State whether lease liabilities are included. • Net debt = total borrowings − cash and cash equivalents.
- Debt-to-equity = defined debt / defined equity; zero or negative equity requires warning/unavailable policy. • Debt-to-assets = defined debt / total assets when total assets are positive. • Interest coverage = documented EBIT/operating-profit measure / finance costs.
- Never silently substitute EBITDA for EBIT. • Do not automatically classify contingent liabilities as funded debt.
### Liquidity and working capital
- Current ratio = current assets / current liabilities. • Quick ratio = defined quick assets / current liabilities; document excluded asset categories. • Working capital = current assets − current liabilities.
- Zero current liabilities makes ratios unavailable, not infinite. • Do not infer classifications when labels are ambiguous.
### Cash flow
- CFO margin = CFO / revenue × 100 for compatible periods and non-zero revenue. • Free cash flow = CFO − capex only when capex is explicit or derived by a documented rule. • Net cash movement = CFO + CFI + CFF when all components and sign conventions are compatible.
- Reconcile opening cash, net movement, and closing cash when available. • Negative CFO is a fact to report, not automatic proof of distress. • Depreciation is not a substitute for capital expenditure.
### Returns and per-share metrics
- ROA/ROE should use average assets/equity when the metric claims an average balance. • If only closing balances exist, omit the metric or label the alternative denominator explicitly. • Prefer reported EPS unless compliant derivation inputs are available.
- Derived EPS must document profit attribution, share-count basis, and period compatibility. • Preserve the distinction between basic and diluted EPS.
### Display conventions
- Store numeric values and units separately from formatted display strings. • Use `%`, `x`, or currency-per-share as appropriate. • Do not imply precision unsupported by source data.
- Expose formulas and periods in the report or metric detail. • Do not create an overall financial score without a separately approved methodology.
## 11. Period comparison and source selection
- Sort periods by dates, not display labels. • Match annual periods to annual periods and interim periods to comparable durations. • Do not compare half-year revenue with full-year revenue as YoY growth.
- If a prior comparable period is missing, mark growth unavailable. • Preserve audited, restated, and unaudited status when available. • Preserve multiple source versions and record which facts were selected.
- If DRHP and RHP values conflict, expose the conflict instead of silently choosing one. • Apply source-selection policy explicitly and document it. • Restated values supersede earlier values only when the source or policy supports that decision.
- Record selected fact IDs so an analysis can be reproduced.
## 12. Evidence traceability
- A reported fact shows extracted value, normalized value, original label, unit, period, document, and page when available. • A derived metric shows formula, formula version, input values, fact IDs, and evidence references. • A validation finding identifies affected facts and why it was raised.
- An unavailable metric lists missing inputs or the precise blocking reason. • Preserve table/cell evidence if Phase 3 provides it. • Do not cite a document generally when the specific input facts can be identified.
- Do not use the word “verified” unless the check and its scope are explicit.
## 13. Report contract
Suggested report sections:
- Company/IPO identity, if available. • Documents and periods included. • Data-quality summary and limitations.
- Revenue and growth. • Profitability and margins. • Debt, leverage, and liquidity.
- Cash-flow analysis. • Ratio summary. • Validation findings and source conflicts.
- Evidence references. • Methodology, formula versions, and generation timestamp.
Each metric result should include:
- `metric_code` and display name. • Period ID or explicit dates. • Numeric value, unit, and optional formatted value.
- Status: calculated, unavailable, or blocked. • Reason code when unavailable. • Formula identifier/text and version.
- Input fact IDs and evidence references. • Warning and validation finding IDs. • Optional deterministic explanation derived from the calculation state.
Report quality requirements:
- Separate source facts from derived metrics. • Do not hide missing periods or failed calculations. • Never turn unavailable values into zero for charts.
- Use the same backend result for charts and tables. • Show warnings near affected metrics and in a consolidated section. • Support reports with only one or two periods.
- Avoid investment-advice language in this phase.
## 14. API and service integration
Follow the existing FastAPI route/schema patterns.
- Define request/response schemas only if equivalent contracts do not already exist. • Accept a stable company/IPO/document scope rather than arbitrary client-supplied authoritative numbers. • Resolve extracted facts through the existing service/repository boundary.
- Return structured findings and metric statuses. • Use established HTTP error formats and status codes. • Prevent cross-company or cross-document data mixing.
- Keep calculation logic out of route handlers. • Avoid duplicating existing document/report endpoints. • Test valid requests, missing data, invalid IDs, and partial results.
- Document example requests and responses without secrets or private data.
## 15. Frontend integration
- Inspect current frontend layout and style conventions before adding views. • Reuse existing navigation, design tokens, loading states, and error states. • Present a concise overview before detailed tables.
- Include period labels, units, calculation status, and evidence references. • Explain unavailable values rather than rendering unexplained blanks. • Show warnings without treating every warning as a fatal error.
- Ensure responsive layout and readable number formatting. • Do not independently calculate metrics in JavaScript. • Keep display formatting separate from computation.
- Add frontend tests if a test approach exists; otherwise document manual checks.
## 16. Persistence and reproducibility
- Reuse current persistence patterns if analyses/reports are already stored. • Do not introduce durable persistence without checking architecture requirements. • If persisted, store input fact references, formula-set version, timestamp, and output schema version.
- If generated on demand, return enough metadata for audit and reproduction. • Version formulas when changes can alter prior results. • Do not mutate source facts while calculating or formatting.
- Keep normalization decisions distinct from raw extraction records. • Support reruns when facts or formula versions change.
## 17. Security and robustness
- Treat uploaded documents and extracted text as untrusted data. • Never execute formulas or code found in documents. • Prevent path traversal and unsafe evidence-file access.
- Enforce existing authorization and ownership checks. • Avoid logging entire documents or sensitive payloads unnecessarily. • Never include secrets or tokens in reports/logs.
- Bound fact collection and report payload sizes using existing project limits. • Handle malformed dates, extreme values, duplicate records, and nulls. • Return actionable errors without exposing stack traces to API clients.
## 18. Testing strategy
Use the repository's existing test framework. Prefer isolated unit tests for normalization, validation, and formulas.
### Normalization tests
- Known label aliases map to the expected canonical code. • Unknown and ambiguous labels remain unresolved. • INR, thousand, lakh, and crore scales normalize correctly.
- Unknown unit/currency produces a finding. • Expense and cash-flow sign conventions are preserved. • Blank, dash, null, zero, and not-disclosed remain distinct.
- Non-March fiscal years are supported. • Invalid dates and malformed numeric strings are rejected safely.
### Validation tests
- Required fields are missing. • Conflicting duplicate facts are detected. • Repeated facts from multiple documents are handled explicitly.
- Incompatible periods and currencies are detected. • Balance-sheet equation passes within tolerance and warns/fails outside it. • Cash-flow reconciliation passes within tolerance and warns/fails outside it.
- Missing components result in not-checkable status, not a false pass. • Finding codes, severity, and fact references remain stable.
### Formula tests
- Revenue grows, remains flat, and declines. • Prior revenue is zero. • Prior period is missing.
- Profit changes from profit to loss and loss to profit. • Ratio denominator is zero. • Equity is negative or zero.
- Cash exceeds borrowings, producing negative net debt. • Quick-ratio inputs are incomplete. • CFO is negative.
- Capex is missing for free cash flow. • Decimal precision and rounding boundaries are exercised. • Different input scales yield the same normalized result.
### Integration tests
- End-to-end flow from Phase 3 facts to report. • Partial dataset returns valid metrics and unavailable statuses. • DRHP/RHP conflicts remain visible.
- API results include evidence and formula metadata. • Report generation does not mutate source facts. • Phase 2 and Phase 3 regression tests still pass.
### Fixture requirements
- Include small hand-calculated fixtures. • Include a synthetic multi-year company. • Include sparse/missing-statement data.
- Include a restatement or conflicting-source case. • Use synthetic or appropriately anonymized data. • Document units, periods, and expected calculations in each fixture.
## 19. Implementation stages
### Stage 0 — Baseline and design
- Inspect repository instructions and architecture. • Run existing tests and record baseline. • Confirm Phase 3 fact and evidence contracts.
- Record unresolved assumptions. • Exit: interfaces map to actual repository structures.
### Stage 1 — Domain contracts
- Define/adapt fact, period, evidence, metric result, and finding models. • Define stable statuses and reason codes. • Add schema tests.
- Document canonical line-item identifiers. • Exit: contracts are explicit and independently testable.
### Stage 2 — Normalization and validation
- Implement alias registry and unit/period normalization. • Implement structural and semantic validation. • Implement cross-statement checks with tolerances.
- Preserve raw values and provenance. • Exit: fixtures produce deterministic facts and findings.
### Stage 3 — Calculation core
- Implement formula helpers and metric registry. • Implement growth and profitability first. • Implement debt, liquidity, and cash-flow metrics next.
- Add missing-data and denominator policies. • Exit: formulas pass hand-checked tests.
### Stage 4 — Report assembly
- Assemble metrics, periods, findings, and evidence. • Include formula metadata and input references. • Standardize unavailable statuses.
- Exit: report schema is stable and traceable.
### Stage 5 — API and UI
- Add/adapt application service and endpoints. • Integrate frontend without duplicated calculations. • Add API/presentation tests or manual checks.
- Exit: users can run analysis and inspect evidence.
### Stage 6 — Regression and handoff
- Run relevant tests and quality checks. • Update architecture, API, metric, and testing documentation. • Verify Phase 2/3 behavior.
- Produce implementation report and known limitations. • Exit: acceptance criteria are demonstrably met.
## 20. Acceptance criteria
- [ ] Repository instructions and baseline test results were reviewed. • [ ] Phase 3 input contract is explicit and documented. • [ ] Raw facts and provenance remain intact.
- [ ] Decimal-safe arithmetic is used for financial calculations. • [ ] Period, currency, unit, and sign compatibility are validated. • [ ] Supported growth, margin, debt, liquidity, and cash-flow metrics are implemented.
- [ ] Missing inputs and zero denominators return explicit statuses. • [ ] Cross-statement checks distinguish pass, warning, failure, and not-checkable. • [ ] Each derived metric identifies formula and input facts.
- [ ] Reported facts link to available document/page/table evidence. • [ ] API and UI use the same backend-calculated values. • [ ] Unit and integration tests cover normal, boundary, and missing-data cases.
- [ ] Existing tests pass or regressions are resolved and explained. • [ ] Documentation explains formulas, assumptions, limitations, and test commands. • [ ] No unsupported investment recommendation or forecast is included.
## 21. Documentation deliverables
- Phase 4 plan under `docs/plans/`. • Metric catalogue with formula, required inputs, units, caveats, and version. • Phase 3 integration/data contract.
- Validation rules and severity definitions. • API examples and report schema if APIs change. • Test instructions and fixture descriptions.
- Architecture decision records for significant decisions. • README/architecture updates only where required by actual changes.
## 22. Completion report required from agent
- **Implemented:** completed capabilities. • **Files changed:** significant paths and purpose. • **Data contract:** Phase 3 input shape and assumptions.
- **Metrics:** formulas implemented and omitted. • **Validation:** checks and limitations. • **Evidence:** how a user traces metrics to source facts.
- **Tests:** exact commands and outcomes. • **Compatibility:** regression status for existing behavior. • **Known limitations:** missing source fields and unresolved assumptions.
- **Follow-up:** only genuinely out-of-scope work.
## 23. Design principles
1. Correctness before breadth.
2. Evidence before interpretation.
3. Missing is not zero.
4. Identical inputs and formula versions yield identical results.
5. Growth and ratios require comparable inputs.
6. Suspicious data raises a finding; it is not silently repaired.
7. Valid metrics should still be returned when unrelated metrics are unavailable.
8. Formula, input, and limitation details must be inspectable.
9. Reuse the existing architecture and avoid speculative dependencies.
10. Inspect, plan, implement, test, document, and report.
## 24. Critical cautions
- Not every IPO has three audited years or every statement type. • Companies may use different line-item names and accounting presentations. • Total income is not automatically revenue from operations.
- Annual, quarterly, and interim periods are not interchangeable. • EBITDA definitions may differ across issuers. • Never mix standalone and consolidated statements silently.
- Do not mix restated and originally reported figures without a documented policy. • Ratios with zero, negative, missing, or incompatible denominators need explicit treatment. • Validation is not an audit opinion.
- Keep financial calculations separate from later AI narrative or decision layers.
## 25. Definition of done
Phase 4 is complete when the system consumes validated extracted facts, normalizes and validates them, calculates supported metrics deterministically, and generates a readable report where every value has a clear status and traceable evidence. The implementation must be tested, documented, compatible with repository conventions, and handed off with limitations clearly stated.
## Appendix A — Metric implementation checklist
### Revenue growth (YoY)
- Required inputs: Current and prior comparable-period revenue. • Output unit: %. • Policy: Zero prior revenue returns ZERO_BASELINE; periods must be comparable.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Gross margin
- Required inputs: Revenue and compatible cost-of-sales definition. • Output unit: %. • Policy: Do not infer cost of sales from ambiguous expenses.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Operating margin
- Required inputs: Revenue and defined operating profit. • Output unit: %. • Policy: Use an explicit reported value or documented derivation.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### PBT margin
- Required inputs: PBT and revenue for the same period. • Output unit: %. • Policy: Unavailable if revenue is zero.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### PAT margin
- Required inputs: PAT and revenue for the same period. • Output unit: %. • Policy: Preserve negative values and loss/profit transitions.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Total borrowings
- Required inputs: Selected short- and long-term borrowings. • Output unit: currency. • Policy: Document treatment of lease liabilities.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Net debt
- Required inputs: Total borrowings and cash equivalents. • Output unit: currency. • Policy: Negative net debt may represent net cash; preserve sign.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Debt-to-equity
- Required inputs: Defined debt and compatible equity. • Output unit: x. • Policy: Zero or negative equity requires explicit status/policy.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Debt-to-assets
- Required inputs: Defined debt and total assets. • Output unit: x or %. • Policy: Require compatible and positive total assets.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Interest coverage
- Required inputs: Defined EBIT/operating profit and finance costs. • Output unit: x. • Policy: Never substitute EBITDA silently.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Current ratio
- Required inputs: Current assets and current liabilities. • Output unit: x. • Policy: Zero current liabilities makes the ratio unavailable.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Quick ratio
- Required inputs: Defined quick assets and current liabilities. • Output unit: x. • Policy: Document included and excluded current assets.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Working capital
- Required inputs: Current assets and current liabilities. • Output unit: currency. • Policy: Inputs must refer to a compatible balance-sheet date.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### CFO margin
- Required inputs: CFO and revenue for the same period. • Output unit: %. • Policy: Preserve cash-flow sign.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Free cash flow
- Required inputs: CFO and explicit capex. • Output unit: currency. • Policy: Do not use depreciation as a substitute for capex.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Net cash movement
- Required inputs: CFO, CFI, and CFF. • Output unit: currency. • Policy: Require compatible signs and periods.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Return on assets
- Required inputs: Profit measure and average assets. • Output unit: %. • Policy: Do not call closing-assets calculation average-based ROA.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### Return on equity
- Required inputs: Profit measure and average equity. • Output unit: %. • Policy: Document profit attribution and negative-equity policy.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
### EPS
- Required inputs: Reported EPS or valid profit/share-count inputs. • Output unit: currency/share. • Policy: Preserve basic/diluted distinction.
- Tests: normal case, missing input, boundary/zero denominator where applicable, unit normalization, and evidence propagation. • Report: value/status, period, formula version, input fact IDs, evidence, and warnings.
## Appendix B — Agent review checklist
- [ ] Each formula is defined once and referenced by a stable metric code. • [ ] Period type and statement basis are explicit. • [ ] Currency and scale are normalized before arithmetic.
- [ ] Raw extracted facts remain immutable. • [ ] Derived values can be recomputed from recorded inputs. • [ ] Zero, missing, not disclosed, and not applicable remain distinct.
- [ ] Negative values and sign transitions are covered by tests. • [ ] Rounding and tolerance rules are explicit. • [ ] Errors are isolated to affected metrics where possible.
- [ ] Reports expose unavailable values and limitations. • [ ] Source conflicts are visible rather than silently resolved. • [ ] Client-supplied calculations are not treated as authoritative.
- [ ] UI renders backend values without duplicating formulas. • [ ] Documented commands match this repository. • [ ] Unrelated changes are excluded from the pull request.
## Appendix C — Pull request checklist
- Summarize behavior changes rather than only listing files. • List supported and intentionally unsupported metrics. • Include API examples if the response contract changed.
- Include test commands and exact outcomes. • Link formula-policy decisions to decision records. • Confirm evidence references survive end-to-end.
- Confirm Phase 2 and Phase 3 regression tests were run. • Explain remaining dependencies on extraction quality or source disclosures. • Label synthetic reports as synthetic.
## Appendix D — Phase boundaries and downstream readiness
- Phase 3 owns ingestion, extraction, OCR, and source-location capture. • Phase 4 owns canonical financial facts, validation, deterministic metrics, and evidence-backed reporting. • Later phases may add qualitative risk analysis, peer comparisons, valuation, subscription context, and decision support.
- Later AI explanations must consume Phase 4 outputs and must not override deterministic values. • Reports must distinguish calculated, unavailable, and warning-bearing metrics. • Keep metric codes stable so downstream systems do not depend on display labels.
- Document breaking schema changes before introducing them.
## Appendix E — Minimal end-to-end acceptance scenario
Given synthetic company data for three annual periods containing revenue, PBT, PAT, borrowings, cash, equity, assets, current assets, current liabilities, CFO, CFI, and CFF:
- The engine normalizes facts and retains original evidence. • Growth is calculated only for comparable annual periods with valid baselines. • Margins and ratios are calculated only when inputs are present and compatible.
- An inconsistent balance-sheet equation creates a finding under the configured tolerance policy. • A zero-denominator ratio returns unavailable without an unhandled exception. • The report includes periods, values, formula versions, evidence, and warnings.
- Re-running identical facts with the same formula version yields identical outputs. • Automated tests prove the behavior without a live IPO document or LLM.
## Appendix F — Additional guardrails
- Keep formulas independent from report templates. • Prefer explicit result objects over magic numeric sentinels. • Use stable reason codes for frontend rendering and automated tests.
- Avoid a global tolerance for unrelated currency and ratio checks. • Keep metric metadata inspectable without executing calculations. • Separate source-selection policy from formula implementation.
- Preserve statement basis where available. • OCR confidence is source-quality metadata, not proof of financial correctness. • Define consistent Decimal serialization for API responses.
- Keep locale-specific formatting outside the calculation layer. • Make unsupported metrics distinct from metrics missing inputs. • Use deterministic ordering for periods, metrics, and findings.
- Add regression fixtures when calculation defects are fixed. • Record formula changes that alter previously generated results. • Keep report language factual; avoid unsupported conclusions about financial health.
- Expose raw and normalized values when normalization materially changes scale or sign. • Ensure evidence links cannot cross company or document boundaries. • Prefer explicit interfaces between ingestion and analysis.
- Keep new dependencies minimal and justify each one. • Follow project typing, formatting, and linting conventions. • If a test cannot run, explain the environmental reason and residual risk.
- Update this plan if an approved decision changes scope.
