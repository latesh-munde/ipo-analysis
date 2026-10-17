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
    PageExtraction,
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
                """
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
