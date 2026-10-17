import hashlib
import logging
import os
import sqlite3
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

import pymupdf as fitz

from app.core.config import Settings
from app.financial.evidence import financial_cell_sha256
from app.schemas.document_responses import DocumentUploadResponse
from app.schemas.documents import (
    DocumentMetadata,
    DocumentResult,
    DocumentStatus,
    ExtractedTable,
    ExtractionWarning,
    FinancialCellReview,
    PageExtraction,
)
from app.schemas.financial_analysis import PersistedFinancialFact, ReportedFinancialFact
from app.services.document_repository import DocumentRepository
from app.services.pdf_extraction import extract_pdf

log = logging.getLogger(__name__)
CHUNK_SIZE = 1024 * 1024
PDF_MIME_TYPE = "application/pdf"


class DocumentInputError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class DocumentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage_dir = settings.document_storage_dir.resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.repository = DocumentRepository(self.storage_dir / "documents.sqlite3")

    def upload(
        self,
        file: BinaryIO,
        filename: str | None,
        content_type: str | None,
        document_type: str | None,
    ) -> DocumentUploadResponse:
        safe_filename = self._validate_metadata(filename, content_type, document_type)
        staged_path, file_size, sha256 = self._stage_upload(file)
        final_path: Path | None = None
        document_id = str(uuid.uuid4())
        try:
            existing = self.repository.find_by_hash(sha256)
            if existing is not None:
                return self._duplicate_response(existing)

            page_count, initial_warnings = self._inspect_pdf(staged_path)
            final_path = self.storage_dir / f"{document_id}.pdf"
            os.replace(staged_path, final_path)
            metadata = DocumentMetadata(
                document_id=document_id,
                original_filename=safe_filename,
                file_size=file_size,
                detected_type=PDF_MIME_TYPE,
                sha256=sha256,
                uploaded_at=datetime.now(UTC),
                document_type=document_type.strip() if document_type else None,
                status=DocumentStatus.PROCESSING,
                page_count=page_count,
                warnings=initial_warnings,
            )
            try:
                self.repository.create(metadata, final_path)
            except sqlite3.IntegrityError:
                existing = self.repository.find_by_hash(sha256)
                if existing is None:
                    final_path.unlink(missing_ok=True)
                    raise
                final_path.unlink(missing_ok=True)
                return self._duplicate_response(existing)
            except Exception:
                final_path.unlink(missing_ok=True)
                raise

            warnings: list[ExtractionWarning] = []
            try:
                with fitz.open(filename=str(final_path)) as pdf:
                    pages, tables, warnings, status = extract_pdf(
                        pdf,
                        document_id,
                        self.settings,
                        document_sha256=sha256,
                    )
                warnings = initial_warnings + warnings
                if initial_warnings and status == DocumentStatus.COMPLETED:
                    status = DocumentStatus.COMPLETED_WITH_WARNINGS
                self.repository.complete(
                    document_id,
                    status,
                    page_count,
                    warnings,
                    pages,
                    tables,
                )
            except Exception:
                log.exception("Document processing failed document_id=%s", document_id)
                warnings = initial_warnings + [
                    ExtractionWarning(
                        code="PROCESSING_FAILED",
                        message="The document could not be fully processed.",
                    )
                ]
                self.repository.fail(document_id, warnings, page_count)

            stored_metadata = self.repository.get_metadata(document_id)
            if stored_metadata is None:
                raise RuntimeError("The processed document record is missing.")
            return DocumentUploadResponse(
                document=stored_metadata,
                page_count=page_count,
                table_count=len(self.repository.get_tables(document_id)),
            )
        finally:
            staged_path.unlink(missing_ok=True)

    def get_result(self, document_id: str) -> DocumentResult | None:
        metadata = self.repository.get_metadata(document_id)
        if metadata is None:
            return None
        return DocumentResult(
            document=metadata,
            pages=self.repository.get_pages(document_id),
            tables=self.repository.get_tables(document_id),
        )

    def get_metadata(self, document_id: str) -> DocumentMetadata | None:
        return self.repository.get_metadata(document_id)

    def get_pages(self, document_id: str) -> list[PageExtraction]:
        return self.repository.get_pages(document_id)

    def get_tables(self, document_id: str) -> list[ExtractedTable]:
        return self.repository.get_tables(document_id)

    def render_page(self, document_id: str, page_number: int) -> bytes:
        metadata = self.repository.get_metadata(document_id)
        if metadata is None:
            raise DocumentInputError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
        if metadata.page_count is None or not 1 <= page_number <= metadata.page_count:
            raise DocumentInputError(
                404,
                "PAGE_NOT_FOUND",
                "The requested PDF page was not found.",
            )

        stored_path = self.repository.get_source_path(document_id)
        if stored_path is None:
            raise DocumentInputError(
                500,
                "DOCUMENT_SOURCE_UNAVAILABLE",
                "The stored source PDF is unavailable.",
            )
        try:
            source_path = stored_path.resolve(strict=True)
            source_path.relative_to(self.storage_dir)
        except (OSError, ValueError) as exc:
            raise DocumentInputError(
                500,
                "DOCUMENT_SOURCE_UNAVAILABLE",
                "The stored source PDF is unavailable.",
            ) from exc

        try:
            with fitz.open(filename=str(source_path)) as pdf:
                page = pdf.load_page(page_number - 1)
                return page.get_pixmap(dpi=120, alpha=False).tobytes("png")
        except (fitz.FileDataError, RuntimeError, ValueError) as exc:
            raise DocumentInputError(
                500,
                "PAGE_RENDER_FAILED",
                "The requested source page could not be rendered.",
            ) from exc

    def review_financial_cell(
        self,
        document_id: str,
        page_number: int,
        table_index: int,
        row_index: int,
        column_index: int,
        confirmed_value: str,
    ) -> FinancialCellReview:
        metadata = self.repository.get_metadata(document_id)
        if metadata is None:
            raise DocumentInputError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
        table = next(
            (
                item
                for item in self.repository.get_tables(document_id)
                if item.page_number == page_number and item.table_index == table_index
            ),
            None,
        )
        if table is None:
            raise DocumentInputError(
                404,
                "SOURCE_TABLE_NOT_FOUND",
                "The source table was not found.",
            )
        if row_index < 0 or column_index < 0:
            raise DocumentInputError(
                422,
                "SOURCE_CELL_NOT_FOUND",
                "The selected OCR cell was not found.",
            )
        if not table.extraction_method.startswith("tesseract_ocr"):
            raise DocumentInputError(
                422,
                "CELL_NOT_OCR_DERIVED",
                "Only OCR-derived cells can use this review workflow.",
            )
        if (
            row_index >= len(table.rows)
            or column_index >= len(table.rows[row_index])
            or row_index >= len(table.cell_boxes or [])
            or column_index >= len(table.cell_boxes[row_index])
            or table.cell_boxes[row_index][column_index] is None
        ):
            raise DocumentInputError(
                422,
                "SOURCE_CELL_NOT_FOUND",
                "The selected OCR cell or its source region was not found.",
            )

        review = FinancialCellReview(
            document_id=document_id,
            page_number=page_number,
            table_index=table_index,
            row_index=row_index,
            column_index=column_index,
            source_value=table.rows[row_index][column_index],
            confirmed_value=confirmed_value,
            reviewed_at=datetime.now(UTC),
            source_cell_sha256=financial_cell_sha256(
                table,
                row_index,
                column_index,
                metadata.sha256,
            ),
        )
        self.repository.save_financial_cell_review(review)
        return review

    def get_financial_cell_review(
        self,
        document_id: str,
        page_number: int,
        table_index: int,
        row_index: int,
        column_index: int,
    ) -> FinancialCellReview | None:
        metadata = self.repository.get_metadata(document_id)
        if metadata is None:
            return None
        review = self.repository.get_financial_cell_review(
            document_id, page_number, table_index, row_index, column_index
        )
        if review is None:
            return None
        table = next(
            (
                item
                for item in self.repository.get_tables(document_id)
                if item.page_number == page_number and item.table_index == table_index
            ),
            None,
        )
        if (
            table is None
            or not table.extraction_method.startswith("tesseract_ocr")
            or row_index < 0
            or column_index < 0
            or row_index >= len(table.rows)
            or column_index >= len(table.rows[row_index])
            or table.rows[row_index][column_index] != review.source_value
            or review.source_cell_sha256
            != financial_cell_sha256(
                table,
                row_index,
                column_index,
                metadata.sha256,
            )
        ):
            return None
        return review

    def get_financial_cell_reviews(
        self,
        document_id: str,
    ) -> list[FinancialCellReview]:
        metadata = self.repository.get_metadata(document_id)
        if metadata is None:
            return []
        reviews = self.repository.get_financial_cell_reviews(document_id)
        tables = {
            (table.page_number, table.table_index): table
            for table in self.repository.get_tables(document_id)
        }
        current_reviews = []
        for review in reviews:
            table = tables.get((review.page_number, review.table_index))
            if (
                table is not None
                and table.extraction_method.startswith("tesseract_ocr")
                and review.row_index < len(table.rows)
                and review.column_index < len(table.rows[review.row_index])
                and table.rows[review.row_index][review.column_index]
                == review.source_value
                and review.source_cell_sha256
                == financial_cell_sha256(
                    table,
                    review.row_index,
                    review.column_index,
                    metadata.sha256,
                )
            ):
                current_reviews.append(review)
        return current_reviews

    def save_financial_facts(
        self,
        facts: list[ReportedFinancialFact],
    ) -> list[PersistedFinancialFact]:
        return self.repository.save_financial_facts(facts)

    def get_financial_facts(
        self,
        document_id: str,
        *,
        include_history: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PersistedFinancialFact]:
        return self.repository.get_financial_facts(
            document_id,
            include_history=include_history,
            limit=limit,
            offset=offset,
        )

    def _validate_metadata(
        self,
        filename: str | None,
        content_type: str | None,
        document_type: str | None,
    ) -> str:
        if not filename or not filename.strip():
            raise DocumentInputError(
                400,
                "FILENAME_REQUIRED",
                "A filename is required.",
            )
        safe_filename = Path(filename.replace("\\", "/")).name[:255]
        if Path(safe_filename).suffix.lower() != ".pdf":
            raise DocumentInputError(
                415,
                "UNSUPPORTED_FILE_TYPE",
                "Only PDF documents are supported.",
            )
        declared_type = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
        if declared_type != PDF_MIME_TYPE:
            raise DocumentInputError(
                415,
                "UNSUPPORTED_CONTENT_TYPE",
                "The uploaded file must declare application/pdf.",
            )
        if document_type is not None and len(document_type.strip()) > 80:
            raise DocumentInputError(
                422,
                "INVALID_DOCUMENT_TYPE",
                "Document type must be 80 characters or fewer.",
            )
        return safe_filename

    def _stage_upload(self, file: BinaryIO) -> tuple[Path, int, str]:
        digest = hashlib.sha256()
        size = 0
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".upload-",
                suffix=".pdf",
                dir=self.storage_dir,
                delete=False,
            ) as staged:
                temp_path = Path(staged.name)
                first_chunk = True
                while chunk := file.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > self.settings.document_max_upload_bytes:
                        raise DocumentInputError(
                            413,
                            "FILE_TOO_LARGE",
                            "The uploaded file exceeds the configured size limit.",
                        )
                    if first_chunk:
                        first_chunk = False
                        if not chunk.startswith(b"%PDF-"):
                            raise DocumentInputError(
                                422,
                                "INVALID_PDF",
                                "The file does not have a valid PDF signature.",
                            )
                    staged.write(chunk)
                    digest.update(chunk)
            if size == 0:
                raise DocumentInputError(
                    422,
                    "EMPTY_FILE",
                    "The uploaded file is empty.",
                )
            return temp_path, size, digest.hexdigest()
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    def _inspect_pdf(
        self,
        path: Path,
    ) -> tuple[int, list[ExtractionWarning]]:
        try:
            with fitz.open(stream=path.read_bytes(), filetype="pdf") as pdf:
                if pdf.needs_pass:
                    raise DocumentInputError(
                        422,
                        "ENCRYPTED_PDF",
                        "Password-protected PDF files are not supported.",
                    )
                page_count = pdf.page_count
                warnings = (
                    [
                        ExtractionWarning(
                            code="PDF_REPAIRED",
                            message=(
                                "The PDF structure was repaired while opening; "
                                "verify extracted content against the source."
                            ),
                        )
                    ]
                    if pdf.is_repaired
                    else []
                )
        except DocumentInputError:
            raise
        except Exception as exc:
            raise DocumentInputError(
                422,
                "UNREADABLE_PDF",
                "The PDF is malformed or cannot be read.",
            ) from exc

        if page_count < 1:
            raise DocumentInputError(
                422,
                "EMPTY_PDF",
                "The PDF does not contain any pages.",
            )
        if page_count > self.settings.document_max_pages:
            raise DocumentInputError(
                413,
                "TOO_MANY_PAGES",
                "The PDF exceeds the configured page limit.",
            )
        return page_count, warnings

    def _duplicate_response(self, metadata: DocumentMetadata) -> DocumentUploadResponse:
        result = metadata.model_copy(update={"duplicate": True})
        return DocumentUploadResponse(
            document=result,
            page_count=result.page_count or 0,
            table_count=len(self.repository.get_tables(result.document_id)),
        )
