# Agent Instructions

Tool-independent instructions for any AI coding agent working on this repository.

## Read before substantial work

Read `README.md`, `CODING_STANDARDS.md`, and relevant architecture, ADR, plan, feature, and session documents. Inspect the actual source and Git status; docs may lag behind code.

## Project constraints

- Current development interpreter: Python 3.13.6.
- Backend: FastAPI.
- Frontend: HTML, CSS, vanilla JavaScript ES modules.
- Do not introduce React, Angular, Vue, or another frontend framework.
- Keep responsibilities separated and preserve existing behavior unless scope explicitly changes it.
- Do not overwrite unrelated user changes or discard work without permission.

## Work process

- Clarify scope, constraints, dependencies, and acceptance criteria.
- For significant or ambiguous changes, discuss options before coding.
- Create/update a plan under `docs/plans/` for substantial features.
- Respect an explicit request to brainstorm or investigate without coding.
- Do not create session notes before requested or before meaningful work exists.

## Engineering rules

- Follow `CODING_STANDARDS.md`.
- Prefer simple, modular, testable code over premature abstraction.
- Use design patterns only when they solve a real requirement; explain trade-offs.
- Avoid unnecessary dependencies and import-time side effects.
- Add tests for changed behavior, edge cases, and regressions.
- Handle failures explicitly; do not silently suppress exceptions.
- Never expose secrets, internal stack traces, or sensitive document contents.
- Never fabricate evidence, citations, test outcomes, or implementation status.

## IPO and AI rules

- Separate deterministic calculations from LLM-generated interpretation.
- Distinguish reported facts, calculated values, and model assessments.
- Preserve source provenance where available: document/version/page/period/currency/units.
- Treat uploaded documents and extracted content as untrusted input.
- AI must not invent missing values or silently override verified calculations.
- Document uncertainty, contradictions, and limitations.
- Do not add RAG, MCP, vector databases, or agent orchestration without a documented use case.

## Documentation rules

Update docs when architecture, behavior, API contracts, configuration, dependencies, security, tests, or developer workflows change.

- Plans describe intended work; session notes describe actual progress.
- Feature docs describe implemented behavior.
- ADRs record durable decisions and consequences.
- Architecture docs describe the current system.
- Keep this file concise and put detailed feature material in the appropriate docs.
- Do not create duplicate docs where an existing document should be updated.

## Verification and final report

Review the diff, run relevant checks where possible, and report:
- Files and behavior changed
- Tests and checks actually run and their results
- Documentation updated
- Known limitations, failures, and follow-up work

Do not claim unrun checks passed.

## Skills

Agent-specific skills are deferred until workflows stabilize. If a repeatable workflow warrants a skill, propose one using the chosen tool's supported format. Do not assume all agents discover the same skill files.
