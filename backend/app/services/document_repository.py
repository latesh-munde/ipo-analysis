import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.documents import (
    DocumentMetadata,
    DocumentStatus,
    ExtractedTable,
    ExtractionWarning,
    FinancialCellReview,
    PageExtraction,
)
from app.schemas.financial_analysis import (
    PersistedFinancialFact,
    ReportedFinancialFact,
)


class DocumentRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    detected_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL UNIQUE,
                    uploaded_at TEXT NOT NULL,
                    document_type TEXT,
                    status TEXT NOT NULL,
                    page_count INTEGER,
                    warnings TEXT NOT NULL,
                    source_path TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS document_pages (
                    document_id TEXT NOT NULL REFERENCES documents(document_id),
                    page_number INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    PRIMARY KEY (document_id, page_number)
                );
                CREATE TABLE IF NOT EXISTS document_tables (
                    document_id TEXT NOT NULL REFERENCES documents(document_id),
                    page_number INTEGER NOT NULL,
                    table_index INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    PRIMARY KEY (document_id, page_number, table_index)
                );
                CREATE TABLE IF NOT EXISTS financial_cell_reviews (
                    document_id TEXT NOT NULL REFERENCES documents(document_id),
                    page_number INTEGER NOT NULL,
                    table_index INTEGER NOT NULL,
                    row_index INTEGER NOT NULL,
                    column_index INTEGER NOT NULL,
                    source_value TEXT NOT NULL,
                    confirmed_value TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    source_cell_sha256 TEXT,
                    PRIMARY KEY (
                        document_id, page_number, table_index, row_index,
                        column_index
                    )
                );
                CREATE TABLE IF NOT EXISTS financial_fact_versions (
                    fact_id TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK (revision >= 1),
                    document_id TEXT NOT NULL REFERENCES documents(document_id),
                    source_document_sha256 TEXT NOT NULL,
                    source_table_sha256 TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    fact_json TEXT NOT NULL,
                    PRIMARY KEY (fact_id, revision)
                );
                CREATE INDEX IF NOT EXISTS financial_fact_versions_by_document
                    ON financial_fact_versions (document_id, fact_id, revision);
                """
            )
            review_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(financial_cell_reviews)"
                ).fetchall()
            }
            if "source_cell_sha256" not in review_columns:
                connection.execute(
                    "ALTER TABLE financial_cell_reviews "
                    "ADD COLUMN source_cell_sha256 TEXT"
                )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def find_by_hash(self, sha256: str) -> DocumentMetadata | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE sha256 = ?",
                (sha256,),
            ).fetchone()
        return self._metadata_from_row(row) if row else None

    def create(self, metadata: DocumentMetadata, source_path: Path) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents (
                    document_id, original_filename, file_size, detected_type,
                    sha256, uploaded_at, document_type, status, page_count,
                    warnings, source_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.document_id,
                    metadata.original_filename,
                    metadata.file_size,
                    metadata.detected_type,
                    metadata.sha256,
                    metadata.uploaded_at.isoformat(),
                    metadata.document_type,
                    metadata.status.value,
                    metadata.page_count,
                    self._dump(metadata.warnings),
                    str(source_path),
                ),
            )

    def complete(
        self,
        document_id: str,
        status: DocumentStatus,
        page_count: int,
        warnings: list[ExtractionWarning],
        pages: list[PageExtraction],
        tables: list[ExtractedTable],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE documents
                SET status = ?, page_count = ?, warnings = ?
                WHERE document_id = ?
                """,
                (status.value, page_count, self._dump(warnings), document_id),
            )
            connection.executemany(
                """
                INSERT OR REPLACE INTO document_pages
                (document_id, page_number, result) VALUES (?, ?, ?)
                """,
                [(document_id, page.page_number, self._dump(page)) for page in pages],
            )
            connection.executemany(
                """
                INSERT OR REPLACE INTO document_tables
                (document_id, page_number, table_index, result)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        document_id,
                        table.page_number,
                        table.table_index,
                        self._dump(table),
                    )
                    for table in tables
                ],
            )

    def fail(
        self,
        document_id: str,
        warnings: list[ExtractionWarning],
        page_count: int | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE documents
                SET status = ?, page_count = ?, warnings = ?
                WHERE document_id = ?
                """,
                (
                    DocumentStatus.FAILED.value,
                    page_count,
                    self._dump(warnings),
                    document_id,
                ),
            )

    def fail_interrupted(self) -> int:
        warning = ExtractionWarning(
            code="PROCESSING_INTERRUPTED",
            message="Processing was interrupted before results were saved.",
        )
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT document_id FROM documents WHERE status = ?",
                (DocumentStatus.PROCESSING.value,),
            ).fetchall()
            connection.executemany(
                """
                UPDATE documents
                SET status = ?, warnings = ?
                WHERE document_id = ?
                """,
                [
                    (
                        DocumentStatus.FAILED.value,
                        self._dump([warning]),
                        row["document_id"],
                    )
                    for row in rows
                ],
            )
        return len(rows)

    def get_metadata(self, document_id: str) -> DocumentMetadata | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return self._metadata_from_row(row) if row else None

    def get_pages(self, document_id: str) -> list[PageExtraction]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT result FROM document_pages
                WHERE document_id = ? ORDER BY page_number
                """,
                (document_id,),
            ).fetchall()
        return [PageExtraction.model_validate_json(row["result"]) for row in rows]

    def get_tables(self, document_id: str) -> list[ExtractedTable]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT result FROM document_tables
                WHERE document_id = ?
                ORDER BY page_number, table_index
                """,
                (document_id,),
            ).fetchall()
        return [ExtractedTable.model_validate_json(row["result"]) for row in rows]

    def get_source_path(self, document_id: str) -> Path | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT source_path FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return Path(row["source_path"]) if row else None

    def get_financial_cell_review(
        self,
        document_id: str,
        page_number: int,
        table_index: int,
        row_index: int,
        column_index: int,
    ) -> FinancialCellReview | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM financial_cell_reviews
                WHERE document_id = ? AND page_number = ? AND table_index = ?
                    AND row_index = ? AND column_index = ?
                """,
                (document_id, page_number, table_index, row_index, column_index),
            ).fetchone()
        return self._review_from_row(row) if row else None

    def get_financial_cell_reviews(
        self,
        document_id: str,
    ) -> list[FinancialCellReview]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM financial_cell_reviews
                WHERE document_id = ?
                ORDER BY page_number, table_index, row_index, column_index
                """,
                (document_id,),
            ).fetchall()
        return [self._review_from_row(row) for row in rows]

    def save_financial_cell_review(
        self,
        review: FinancialCellReview,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO financial_cell_reviews (
                    document_id, page_number, table_index, row_index, column_index,
                    source_value, confirmed_value, reviewed_at, source_cell_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    document_id, page_number, table_index, row_index, column_index
                ) DO UPDATE SET
                    source_value = excluded.source_value,
                    confirmed_value = excluded.confirmed_value,
                    reviewed_at = excluded.reviewed_at,
                    source_cell_sha256 = excluded.source_cell_sha256
                """,
                (
                    review.document_id,
                    review.page_number,
                    review.table_index,
                    review.row_index,
                    review.column_index,
                    review.source_value,
                    review.confirmed_value,
                    review.reviewed_at.isoformat(),
                    review.source_cell_sha256,
                ),
            )

    def save_financial_facts(
        self,
        facts: list[ReportedFinancialFact],
    ) -> list[PersistedFinancialFact]:
        persisted: list[PersistedFinancialFact] = []
        with self._connect() as connection:
            for fact in facts:
                content_sha256 = self._financial_fact_content_sha256(fact)
                latest = connection.execute(
                    """
                    SELECT revision, content_sha256, fact_json
                    FROM financial_fact_versions
                    WHERE fact_id = ?
                    ORDER BY revision DESC
                    LIMIT 1
                    """,
                    (fact.fact_id,),
                ).fetchone()
                if latest and latest["content_sha256"] == content_sha256:
                    persisted.append(
                        PersistedFinancialFact.model_validate_json(latest["fact_json"])
                    )
                    continue

                revision = latest["revision"] + 1 if latest else 1
                created_at = datetime.now(UTC)
                record = PersistedFinancialFact(
                    **fact.model_dump(),
                    revision=revision,
                    created_at=created_at,
                )
                connection.execute(
                    """
                    INSERT INTO financial_fact_versions (
                        fact_id, revision, document_id, source_document_sha256,
                        source_table_sha256, content_sha256, created_at, fact_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.fact_id,
                        record.revision,
                        record.evidence.document_id,
                        record.evidence.source_document_sha256,
                        record.evidence.source_table_sha256,
                        content_sha256,
                        record.created_at.isoformat(),
                        self._dump(record),
                    ),
                )
                persisted.append(record)
        return persisted

    def get_financial_facts(
        self,
        document_id: str,
        *,
        include_history: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PersistedFinancialFact]:
        if include_history:
            query = """
                SELECT fact_json FROM financial_fact_versions
                WHERE document_id = ?
                ORDER BY fact_id, revision
                LIMIT ? OFFSET ?
            """
        else:
            query = """
                SELECT fact_json FROM financial_fact_versions AS facts
                WHERE document_id = ? AND revision = (
                    SELECT MAX(revision) FROM financial_fact_versions
                    WHERE fact_id = facts.fact_id
                        AND document_id = facts.document_id
                )
                ORDER BY fact_id
                LIMIT ? OFFSET ?
            """
        with self._connect() as connection:
            rows = connection.execute(
                query,
                (document_id, limit, offset),
            ).fetchall()
        return [
            PersistedFinancialFact.model_validate_json(row["fact_json"]) for row in rows
        ]

    @staticmethod
    def _dump(value: Any) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=DocumentRepository._json_default,
        )

    @staticmethod
    def _json_default(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        raise TypeError(f"Cannot serialize {type(value).__name__} to JSON.")

    @staticmethod
    def _metadata_from_row(row: sqlite3.Row) -> DocumentMetadata:
        return DocumentMetadata(
            document_id=row["document_id"],
            original_filename=row["original_filename"],
            file_size=row["file_size"],
            detected_type=row["detected_type"],
            sha256=row["sha256"],
            uploaded_at=datetime.fromisoformat(row["uploaded_at"]).astimezone(UTC),
            document_type=row["document_type"],
            status=row["status"],
            page_count=row["page_count"],
            warnings=[
                ExtractionWarning.model_validate(item)
                for item in json.loads(row["warnings"])
            ],
        )

    @staticmethod
    def _review_from_row(row: sqlite3.Row) -> FinancialCellReview:
        return FinancialCellReview(
            document_id=row["document_id"],
            page_number=row["page_number"],
            table_index=row["table_index"],
            row_index=row["row_index"],
            column_index=row["column_index"],
            source_value=row["source_value"],
            confirmed_value=row["confirmed_value"],
            reviewed_at=datetime.fromisoformat(row["reviewed_at"]).astimezone(UTC),
            source_cell_sha256=row["source_cell_sha256"],
        )

    @staticmethod
    def _financial_fact_content_sha256(fact: ReportedFinancialFact) -> str:
        payload = json.dumps(
            fact.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
