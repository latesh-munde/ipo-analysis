from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class DocumentStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class ExtractionWarning(BaseModel):
    code: str
    message: str
    page_number: int | None = None


class DocumentMetadata(BaseModel):
    document_id: str
    original_filename: str
    file_size: int
    detected_type: str
    sha256: str
    uploaded_at: datetime
    document_type: str | None
    status: DocumentStatus
    page_count: int | None
    warnings: list[ExtractionWarning]
    duplicate: bool = False


class PageExtraction(BaseModel):
    document_id: str
    page_number: int
    text: str
    native_text: str | None = None
    ocr_text: str | None = None
    extraction_method: str
    status: str
    character_count: int
    warnings: list[ExtractionWarning]
    ocr_confidence: float | None = None


class ExtractedTable(BaseModel):
    document_id: str
    source_document_sha256: str | None = None
    page_number: int
    table_index: int
    extraction_method: str
    rows: list[list[str]]
    warnings: list[ExtractionWarning]
    cell_boxes: list[list[list[float] | None]] | None = None
    cell_tokens: list[list[list[str]]] | None = None
    cell_token_confidences: list[list[list[float | None]]] | None = None
    page_width: float | None = None
    page_height: float | None = None
    ocr_engine: str | None = None
    ocr_engine_version: str | None = None
    ocr_language: str | None = None
    ocr_render_dpi: int | None = None


class FinancialCellReviewRequest(BaseModel):
    confirmed_value: str = Field(min_length=1, max_length=256)
    source_checked: bool

    @field_validator("confirmed_value")
    @classmethod
    def validate_confirmed_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A confirmed source value is required.")
        return value

    @field_validator("source_checked")
    @classmethod
    def require_source_confirmation(cls, value: bool) -> bool:
        if not value:
            raise ValueError("The reviewer must confirm checking the source page.")
        return value


class FinancialCellReview(BaseModel):
    document_id: str
    page_number: int
    table_index: int
    row_index: int
    column_index: int
    source_value: str
    confirmed_value: str
    reviewed_at: datetime
    source_cell_sha256: str | None = None
    status: str = "verified"


class DocumentResult(BaseModel):
    document: DocumentMetadata
    pages: list[PageExtraction]
    tables: list[ExtractedTable]
