# ADR-001: Initial technology stack

- Status: Accepted
- Date: 2026-10-17

## Context

The project needs a web interface and a Python backend for future document processing and financial analysis. The frontend must use plain HTML, CSS, and JavaScript without a frontend framework.

## Decision

- Use Python 3.13.6 as the current development interpreter.
- Use FastAPI for the backend.
- Use HTML, CSS, and vanilla JavaScript ES modules for the frontend.
- Use Pydantic Settings for configuration.
- Use Python standard logging behind a project Logger singleton facade.
- Use pytest/HTTPX for tests and Ruff for code quality.
- Add dependencies and design patterns only when requirements justify them.

## Alternatives considered

- React or another frontend framework: rejected for the current requirement.
- A different Python web framework: not selected for the initial foundation.
- A large up-front architecture: rejected in favor of incremental modular design.

## Consequences

- The frontend avoids framework-specific build complexity.
- Backend/frontend API contracts must remain explicit.
- Python and dependency compatibility must be checked locally and in CI.
- The logging facade must not create import-order dependencies; logger retrieval and logging configuration are separate concerns.
- This decision does not select a database, LLM provider, RAG design, vector store, or MCP integration.

## Follow-up

Revisit only when a concrete requirement justifies a material change.
