# AI and Document Intelligence

This is a design and planning area. It does not imply that AI, RAG, MCP, vector storage, or agent orchestration is implemented.

## Objective

Analyze IPO documents and provide traceable findings about fundamentals, financial performance, valuation, risks, and missing or contradictory information.

## Non-negotiable principles

- Keep deterministic calculations separate from LLM-generated interpretation.
- Preserve document/version/page/period/currency/unit provenance where available.
- Never invent missing values or source citations.
- Treat uploaded documents and extracted text as untrusted input.
- Surface uncertainty, contradictions, missing evidence, and limitations.
- Evaluate outputs against curated examples before relying on them.

## Technologies to evaluate when requirements are clear

- LLM: qualitative interpretation and explanation.
- RAG: retrieval over document passages when it improves grounding and evidence traceability.
- OCR: scanned or image-based PDFs that cannot be reliably parsed as text.
- MCP: standardized access to analysis tools/resources for compatible clients or agents.
- Vector store: only if semantic retrieval needs justify embedding storage and operational costs.
- Agentic orchestration: defer until a concrete multi-step workflow requires it.

RAG and MCP solve different problems and can coexist. Neither is automatically required.

## Questions before implementation

1. Which document formats and sizes must be supported?
2. Are files text-based, scanned, or mixed?
3. What citation granularity is required?
4. What extraction accuracy and fallback behavior are acceptable?
5. What data may be sent to external providers?
6. What are the cost, latency, retention, and privacy constraints?
7. How will factuality and evidence support be evaluated?
8. What should happen when a provider is unavailable?

For AI features, create a plan, update architecture and ADRs, define evaluation fixtures, document provider configuration, and specify failure behavior before calling the feature production-ready.
