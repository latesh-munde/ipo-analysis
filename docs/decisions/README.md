# Architecture Decision Records

Use ADRs for durable decisions that materially affect architecture, dependencies, security, data, testing, or deployment. Do not write an ADR for every small implementation detail.

Accepted decisions: [ADR-001](./ADR-001-technology-stack.md),
[ADR-002](./ADR-002-application-foundation.md), and
[ADR-003](./ADR-003-document-storage-and-extraction.md).

## Naming

`ADR-NNN-short-decision-title.md`

Use the next available identifier. Do not reuse IDs. Keep superseded ADRs and link to the replacing decision.

## Template

```markdown
# ADR-NNN: Decision title

- Status: Proposed | Accepted | Superseded | Rejected
- Date: YYYY-MM-DD

## Context
## Decision
## Alternatives considered
## Consequences
## Follow-up
## References
```

ADRs explain why a choice was made. `ARCHITECTURE.md` describes the current design.
