import logging

import pymupdf as fitz

from app.core.config import Settings
from app.schemas.documents import (
    DocumentStatus,
    ExtractedTable,
    ExtractionWarning,
    PageExtraction,
)
from app.services.pdf_ocr import (
    OcrProcessingError,
    OcrUnavailableError,
    recognize_page,
)

log = logging.getLogger(__name__)


def extract_pdf(
    pdf: fitz.Document,
    document_id: str,
    settings: Settings,
) -> tuple[
    list[PageExtraction],
    list[ExtractedTable],
    list[ExtractionWarning],
    DocumentStatus,
]:
    pages: list[PageExtraction] = []
    tables: list[ExtractedTable] = []
    document_warnings: list[ExtractionWarning] = []

    for page_index in range(pdf.page_count):
        page_number = page_index + 1
        page_warnings: list[ExtractionWarning] = []
        try:
            page = pdf.load_page(page_index)
        except Exception:
            log.exception(
                "PDF page load failed document_id=%s page_number=%s",
                document_id,
                page_number,
            )
            warning = ExtractionWarning(
                code="PAGE_READ_FAILED",
                message="This page could not be read.",
                page_number=page_number,
            )
            pages.append(
                PageExtraction(
                    document_id=document_id,
                    page_number=page_number,
                    text="",
                    extraction_method="native_pdf",
                    status="failed",
                    character_count=0,
                    warnings=[warning],
                )
            )
            document_warnings.append(warning)
            continue

        native_text = ""
        native_failed = False
        try:
            native_text = page.get_text("text")
        except Exception:
            native_failed = True
            page_warnings.append(
                ExtractionWarning(
                    code="TEXT_EXTRACTION_FAILED",
                    message="Native text could not be extracted from this page.",
                    page_number=page_number,
                )
            )

        try:
            found_tables = page.find_tables(strategy="lines")
            for table_index, found_table in enumerate(found_tables.tables, start=1):
                rows = found_table.extract()
                tables.append(
                    ExtractedTable(
                        document_id=document_id,
                        page_number=page_number,
                        table_index=table_index,
                        extraction_method="pymupdf",
                        rows=[
                            ["" if cell is None else str(cell) for cell in row]
                            for row in rows
                        ],
                        warnings=[],
                    )
                )
        except Exception:
            log.exception(
                "PDF table extraction failed document_id=%s page_number=%s",
                document_id,
                page_number,
            )
            page_warnings.append(
                ExtractionWarning(
                    code="TABLE_EXTRACTION_FAILED",
                    message="Tables could not be extracted from this page.",
                    page_number=page_number,
                )
            )

        text = native_text
        method = "native_pdf"
        confidence: float | None = None
        is_blank = False
        try:
            is_blank = (
                not native_failed
                and not native_text.strip()
                and not page.get_images()
                and not page.get_drawings()
            )
        except Exception:
            page_warnings.append(
                ExtractionWarning(
                    code="PAGE_INSPECTION_FAILED",
                    message=(
                        "The page could not be fully inspected for scanned content."
                    ),
                    page_number=page_number,
                )
            )

        needs_ocr = not is_blank and (
            native_failed
            or len(native_text.strip()) < settings.document_low_text_char_threshold
        )
        if is_blank:
            page_warnings.append(
                ExtractionWarning(
                    code="BLANK_PAGE",
                    message="The PDF page appears to be blank.",
                    page_number=page_number,
                )
            )
        elif needs_ocr:
            if not settings.document_ocr_enabled:
                page_warnings.append(
                    ExtractionWarning(
                        code="OCR_DISABLED",
                        message="This page has little native text; OCR is disabled.",
                        page_number=page_number,
                    )
                )
            else:
                try:
                    ocr_text, confidence = recognize_page(
                        page,
                        executable=settings.document_ocr_tesseract_path,
                        language=settings.document_ocr_language,
                        timeout_seconds=settings.document_ocr_timeout_seconds,
                        dpi=settings.document_ocr_dpi,
                    )
                    if len(ocr_text.strip()) > len(native_text.strip()):
                        text = ocr_text
                        method = "tesseract_ocr"
                    elif not ocr_text.strip():
                        page_warnings.append(
                            ExtractionWarning(
                                code="OCR_NO_TEXT",
                                message="OCR did not recognize text on this page.",
                                page_number=page_number,
                            )
                        )
                    else:
                        page_warnings.append(
                            ExtractionWarning(
                                code="OCR_NOT_SELECTED",
                                message=(
                                    "Native text was retained because OCR produced "
                                    "less text."
                                ),
                                page_number=page_number,
                            )
                        )
                    if confidence is not None and confidence < 0.5:
                        page_warnings.append(
                            ExtractionWarning(
                                code="OCR_LOW_CONFIDENCE",
                                message=(
                                    "OCR confidence is low; verify extracted values "
                                    "against the source."
                                ),
                                page_number=page_number,
                            )
                        )
                except OcrUnavailableError:
                    page_warnings.append(
                        ExtractionWarning(
                            code="OCR_UNAVAILABLE",
                            message="The configured OCR executable is unavailable.",
                            page_number=page_number,
                        )
                    )
                except OcrProcessingError:
                    page_warnings.append(
                        ExtractionWarning(
                            code="OCR_FAILED",
                            message="OCR could not process this page.",
                            page_number=page_number,
                        )
                    )

        if native_failed and not text.strip():
            status = "failed"
        elif page_warnings:
            status = "completed_with_warnings"
        elif not text.strip():
            status = "empty"
        else:
            status = "completed"
        pages.append(
            PageExtraction(
                document_id=document_id,
                page_number=page_number,
                text=text,
                extraction_method=method,
                status=status,
                character_count=len(text),
                warnings=page_warnings,
                ocr_confidence=(
                    confidence if needs_ocr and settings.document_ocr_enabled else None
                ),
            )
        )
        document_warnings.extend(page_warnings)

    has_usable_content = any(page.text.strip() for page in pages) or bool(tables)
    has_failures = any(page.status == "failed" for page in pages)
    if not has_usable_content:
        status = DocumentStatus.FAILED
        if not document_warnings:
            document_warnings.append(
                ExtractionWarning(
                    code="NO_EXTRACTED_CONTENT",
                    message="No usable text or tables could be extracted.",
                )
            )
    elif document_warnings or has_failures:
        status = DocumentStatus.COMPLETED_WITH_WARNINGS
    else:
        status = DocumentStatus.COMPLETED

    return pages, tables, document_warnings, status
