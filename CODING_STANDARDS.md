## 1. General Principles

- Follow clean code, SOLID principles where appropriate, separation of concerns, and single responsibility.
- Keep code modular, readable, reusable, testable, and maintainable.
- Avoid unnecessary abstractions, duplicated logic, magic numbers, and hardcoded configuration.
- Do not mix UI, API handling, business logic, database operations, document extraction, and AI interpretation.
- Prefer simple, explicit implementations over premature optimization.
- Do not introduce a new library or framework without a clear requirement.

## 2. Python Backend Standards

### Naming Conventions

- Variables and functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private implementation details: prefix with `_` where appropriate.
- Use meaningful names; avoid unclear abbreviations.

### Code Quality

- Follow PEP 8.
- Add type hints to function parameters and return values.
- Use Pydantic models for API request and response validation.
- Keep functions focused on one responsibility.
- Prefer explicit exceptions over silent failures.
- Avoid global mutable state and circular imports.
- Use dependency injection for database sessions and shared services where appropriate.
- Add docstrings to public modules, classes, and non-obvious functions.

### Architecture

- **Routers:** Handle HTTP requests and responses.
- **Services:** Implement application use cases and orchestration.
- **Domain:** Contain core financial rules, entities, and business logic.
- **Repositories:** Handle database access.
- **Schemas:** Define and validate API data contracts.
- **Infrastructure:** Handle external services, document extraction, storage, and AI integrations.

Routers must not contain financial calculations or complex business logic.

## 3. Frontend Standards

### HTML

- Use semantic HTML5 elements.
- Keep HTML, CSS, and JavaScript in separate files.
- Avoid inline JavaScript and inline CSS.
- Use accessible labels, appropriate input types, and meaningful page titles.

### CSS

- Use consistent naming conventions, such as BEM where appropriate.
- Define shared colors, spacing, typography, and layout values using CSS custom properties.
- Avoid unnecessary `!important`, duplicated styles, and excessive specificity.
- Design responsive layouts for desktop, tablet, and mobile.

### JavaScript

- Use vanilla JavaScript with native browser APIs; do not use React, Vue, Angular, or similar frameworks.
- Use ES modules with `import` and `export`.
- Prefer `const`; use `let` only when reassignment is needed.
- Avoid `var`, unnecessary global variables, and inline event handlers.
- Use `async/await` for asynchronous API requests.
- Centralize API request handling, error handling, and response parsing.
- Validate user input and handle loading, empty, success, and failure states.
- Avoid inserting untrusted document or API content through `innerHTML`; use safe DOM methods and `textContent`.

## 4. API Standards

- Use RESTful resource-oriented endpoints.
- Prefix application endpoints with `/api/v1`.
- Use appropriate HTTP methods and status codes.
- Return consistent JSON response formats.
- Validate inputs at the API boundary.
- Do not expose stack traces, internal paths, secrets, or database details to clients.
- Add pagination for potentially large collections.
- Keep API request and response schemas documented.
- Make error messages actionable without exposing sensitive implementation details.

## 5. IPO Analysis and Financial Data Standards

- Never invent financial values, document contents, or source citations.
- Distinguish reported values, calculated values, and AI-generated interpretations.
- Preserve source document name, version, page number, reporting period, currency, and units wherever applicable.
- Validate financial periods, units, denominators, and missing values before calculations.
- Keep financial calculations deterministic and independently testable.
- Do not allow an AI model to silently override verified financial calculations.
- Clearly identify missing, inconsistent, unavailable, or unverified information.
- Support every significant analytical claim with traceable documentary evidence.
- Present IPO apply/not-apply conclusions with supporting evidence, valuation assumptions, risks, and uncertainty—not unsupported certainty.
- Store document hashes and analysis versions to support reproducibility.

## 6. Database and Configuration

- Use SQLAlchemy for database interaction and Alembic for schema migrations.
- Keep database models separate from API schemas.
- Use transactions for multi-step database changes.
- Avoid raw SQL string concatenation; use parameterized queries.
- Keep secrets, credentials, API keys, and environment-specific values outside source code.
- Commit `.env.example`, never actual secret-bearing `.env` files.
- Validate required environment variables at application startup.

## 7. Logging and Error Handling

- Use Python's standard logging infrastructure or a consistent structured logging configuration.
- Record meaningful events, failures, and processing durations.
- Include request or job identifiers where useful.
- Never log passwords, API keys, access tokens, or sensitive document contents.
- Do not use `print()` for production diagnostics.
- Never suppress exceptions without a justified recovery strategy.
- Return sanitized errors to clients and retain useful diagnostic details in protected server logs.

## 8. Testing Standards

- Use pytest for Python tests.
- Use FastAPI's test client through HTTPX for API tests.
- Test financial formulas independently of the API and AI model.
- Test valid inputs, invalid inputs, boundary conditions, missing values, and failure paths.
- Mock external AI providers and other network-dependent services in unit tests.
- Test document extraction and source-page attribution against known sample documents.
- Test that missing evidence does not produce fabricated conclusions.
- Add regression tests for every confirmed bug.
- Keep tests deterministic and independent of execution order.

## 9. Security Standards

- Enforce file upload size and file-type restrictions.
- Treat uploaded documents and extracted text as untrusted input.
- Generate safe server-side storage names and prevent path traversal.
- Keep uploaded files outside publicly served static directories.
- Never execute uploaded files or treat document text as trusted instructions.
- Apply authentication and authorization before exposing private analyses.
- Configure CORS narrowly if cross-origin requests are required.
- Use HTTPS in deployed environments and protect database credentials.

## 10. Git and Pull Request Standards

- Use feature branches; do not commit directly to the protected main branch.
- Use descriptive, consistent commit messages.
- Keep pull requests focused on a single logical change.
- Include purpose, implementation summary, testing performed, and risks in each PR.
- Run formatting, linting, and tests before merging.
- Require review for changes to financial calculations, security, and data handling.
- Update documentation when architecture, configuration, APIs, or workflows change.
- Remove temporary debug code and unused dependencies before merging.

## 11. Definition of Done

A feature is complete only when:

- Coding standards are followed.
- Appropriate unit and integration tests pass.
- Input validation and error handling are implemented.
- Security implications are reviewed.
- Logs are meaningful and do not expose sensitive data.
- Relevant documentation is updated.
- The change passes code review and automated quality checks.
