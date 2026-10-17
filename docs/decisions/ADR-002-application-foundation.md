# ADR-002: Application foundation and API conventions

- Status: Accepted
- Date: 2026-10-17

## Context

The application needs consistent configuration, logging, exception handling, frontend delivery, and API responses before domain features are added.

## Decision

- Centralize settings using Pydantic Settings.
- Serve the plain frontend through FastAPI for the initial same-origin development setup.
- Prefix application endpoints with `/api/v1`.
- Use a consistent JSON response envelope for successful and failed requests.
- Register centralized handlers for HTTP errors, request validation errors, and unexpected exceptions.
- Use Python standard logging behind a project `Logger` singleton facade.
- Configure logging once during application initialization; named loggers can be retrieved before configuration to avoid import-order failures.
- Prefer FastAPI lifespan management for startup/shutdown behavior.

## Alternatives considered

- Duplicated error handling in each endpoint: rejected due to inconsistency.
- Logger configuration in every module: rejected due to duplication and initialization-order risks.
- Separate frontend development server: deferred because same-origin serving is sufficient for the initial foundation.

## Consequences

- The frontend can handle responses consistently.
- Central handlers must preserve correct HTTP status codes and safe messages.
- The logger singleton is process-local; multi-worker deployments require per-process logging configuration and appropriate log aggregation.
- The response envelope must be applied consistently as new routes are added.
- This ADR describes the intended foundation; verify implementation details against the current branch.

## Follow-up

Add tests for API contracts, exception handling, logging initialization, and static frontend delivery. Update this ADR if the response contract or lifecycle strategy changes.
