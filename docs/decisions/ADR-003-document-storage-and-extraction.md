# ADR-003: Local document storage and PDF extraction

- Status: Accepted
- Date: 2026-10-17

## Context

Phase 2 has no persistence or file-storage layer. Phase 3 requires durable
document metadata, extracted page text and tables, exact duplicate detection,
and local handling of private IPO PDFs without transmitting content externally.

## Decision

- Store generated-UUID PDF files and a SQLite database in a configurable local
  document-storage directory.
- Use Python's standard-library SQLite support for document, page, and table
  records; keep uploaded PDFs outside the publicly mounted frontend directory.
- Use PyMuPDF for PDF validation, page text, rendering, and line-based table
  extraction.
- Use Tesseract only as an optional local OCR executable. OCR is disabled by
  default and can be enabled/configured through application settings.
- Detect exact duplicates by SHA-256 and return the existing document rather
  than storing or extracting the bytes again.
- Recover stale `processing` records as failed with an explicit warning during
  application startup.

## Alternatives considered

- Add a server database and migration framework: deferred because it would add
  infrastructure and dependencies not otherwise present in the project.
- Keep metadata in memory: rejected because documents and extraction results
  must survive process restarts.
- Use a hosted OCR service: rejected because it would transmit uploaded
  prospectuses externally and may incur cost.
- Use filename equality for deduplication: rejected because names are
  user-controlled and do not establish byte equality.

## Consequences

- Development and single-instance deployments need only a protected writable
  local directory; the configured storage path and backups must be secured.
- SQLite is suitable for this initial local feature, not a claim that it is the
  final multi-worker or distributed persistence strategy.
- Tesseract must be separately installed with language data to enable OCR.
- PDF table reconstruction and OCR remain imperfect; warnings and source-page
  provenance must be retained, and extracted financial values must not be
  treated as verified calculations.
- PyMuPDF is dual-licensed under AGPL-3.0 or an Artifex commercial license;
  deployment and distribution must comply with the applicable license.
- The application currently has no authentication or authorization; deployments
  with private documents must restrict access until access controls exist.

## Follow-up

Reassess persistence and access control before multi-user or multi-instance
deployment. Consider a managed database or object store only with a documented
deployment need and an explicit migration plan.

## References

- [Phase 3 document-ingestion plan](../plans/phase-3-document-ingestion-extraction-plan.md)
- [Document-ingestion feature](../features/document-ingestion.md)
