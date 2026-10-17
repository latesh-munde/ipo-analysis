from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


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
    extraction_method: str
    status: str
    character_count: int
    warnings: list[ExtractionWarning]
    ocr_confidence: float | None = None


class ExtractedTable(BaseModel):
    document_id: str
    page_number: int
    table_index: int
    extraction_method: str
    rows: list[list[str]]
    warnings: list[ExtractionWarning]


class DocumentResult(BaseModel):
    document: DocumentMetadata
    pages: list[PageExtraction]
    tables: list[ExtractedTable]
