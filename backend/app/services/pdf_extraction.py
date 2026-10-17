import logging
import re

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
    OcrWord,
    recognize_page_with_layout,
)

log = logging.getLogger(__name__)
OCR_LOW_CONFIDENCE_THRESHOLD = 60.0


def extract_pdf(
    pdf: fitz.Document,
    document_id: str,
    settings: Settings,
    *,
    document_sha256: str | None = None,
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
        page_tables: list[ExtractedTable] = []
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
                    native_text="",
                    extraction_method="native_pdf",
                    status="failed",
                    character_count=0,
                    warnings=[warning],
                )
            )
            document_warnings.append(warning)
            continue

        native_text = ""
        ocr_text: str | None = None
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
                page_tables.append(
                    ExtractedTable(
                        document_id=document_id,
                        source_document_sha256=document_sha256,
                        page_number=page_number,
                        table_index=table_index,
                        extraction_method="pymupdf",
                        rows=[
                            ["" if cell is None else str(cell) for cell in row]
                            for row in rows
                        ],
                        warnings=[],
                        page_width=getattr(page, "rect", None).width
                        if getattr(page, "rect", None) is not None
                        else None,
                        page_height=getattr(page, "rect", None).height
                        if getattr(page, "rect", None) is not None
                        else None,
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
                    ocr_result = recognize_page_with_layout(
                        page,
                        executable=settings.document_ocr_tesseract_path,
                        language=settings.document_ocr_language,
                        timeout_seconds=settings.document_ocr_timeout_seconds,
                        dpi=settings.document_ocr_dpi,
                    )
                    ocr_text, confidence = ocr_result.text, ocr_result.confidence
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
                    if ocr_text.strip():
                        (
                            candidate_rows,
                            candidate_boxes,
                            candidate_tokens,
                            candidate_confidences,
                        ) = _ocr_layout_rows(
                            ocr_result.words, scale=72 / settings.document_ocr_dpi
                        )
                        if candidate_rows:
                            page_tables.append(
                                ExtractedTable(
                                    document_id=document_id,
                                    source_document_sha256=document_sha256,
                                    page_number=page_number,
                                    table_index=len(page_tables) + 1,
                                    extraction_method="tesseract_ocr_layout",
                                    rows=candidate_rows,
                                    warnings=[
                                        ExtractionWarning(
                                            code="OCR_LAYOUT_CANDIDATE",
                                            message=(
                                                "Heuristic OCR rows/cells: verify "
                                                "labels, values, and periods against "
                                                "the PDF page."
                                            ),
                                            page_number=page_number,
                                        )
                                    ]
                                    + _irregular_row_warnings(
                                        candidate_rows,
                                        page_number,
                                    )
                                    + _low_confidence_warnings(
                                        candidate_confidences,
                                        page_number,
                                    ),
                                    cell_boxes=candidate_boxes,
                                    cell_tokens=candidate_tokens,
                                    cell_token_confidences=candidate_confidences,
                                    page_width=page.rect.width,
                                    page_height=page.rect.height,
                                    ocr_engine="tesseract",
                                    ocr_engine_version=ocr_result.engine_version,
                                    ocr_language=settings.document_ocr_language,
                                    ocr_render_dpi=settings.document_ocr_dpi,
                                )
                            )
                        else:
                            page_warnings.append(
                                ExtractionWarning(
                                    code="OCR_TABLE_NOT_RECONSTRUCTED",
                                    message=(
                                        "OCR text was found, but a table-like layout "
                                        "could not be reconstructed. No OCR table "
                                        "cells were created."
                                    ),
                                    page_number=page_number,
                                )
                            )
                        page_warnings.append(
                            ExtractionWarning(
                                code="OCR_TEXT_REQUIRES_REVIEW",
                                message=(
                                    "OCR may misread financial figures. Verify every "
                                    "number against the original PDF before using it "
                                    "in financial analysis."
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
                native_text=native_text,
                ocr_text=ocr_text,
                extraction_method=method,
                status=status,
                character_count=len(text),
                warnings=page_warnings,
                ocr_confidence=(
                    confidence if needs_ocr and settings.document_ocr_enabled else None
                ),
            )
        )
        tables.extend(page_tables)
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


def _ocr_layout_rows(
    words: list[OcrWord],
    *,
    scale: float,
) -> tuple[
    list[list[str]],
    list[list[list[float] | None]],
    list[list[list[str]]],
    list[list[list[float | None]]],
]:
    lines: dict[tuple[int, int, int], list[OcrWord]] = {}
    for word in words:
        lines.setdefault(word.line_id, []).append(word)

    rows: list[list[str]] = []
    boxes: list[list[list[float] | None]] = []
    cell_tokens: list[list[list[str]]] = []
    cell_token_confidences: list[list[list[float | None]]] = []
    for line in sorted(
        lines.values(),
        key=lambda line: (min(word.y0 for word in line), min(word.x0 for word in line)),
    ):
        line.sort(key=lambda word: word.x0)
        widths = [
            (word.x1 - word.x0) / max(1, len(word.text))
            for word in line
            if word.text.strip()
        ]
        if not widths:
            continue
        gap_threshold = max(14.0, sorted(widths)[len(widths) // 2] * 2.5)
        cell_groups: list[list[OcrWord]] = [[]]
        for word in line:
            if cell_groups[-1] and word.x0 - cell_groups[-1][-1].x1 > gap_threshold:
                cell_groups.append([])
            cell_groups[-1].append(word)

        row = [" ".join(word.text for word in group) for group in cell_groups]
        row_tokens = [[word.text for word in group] for group in cell_groups]
        row_confidences = [[word.confidence for word in group] for group in cell_groups]
        row_boxes = [
            [
                min(word.x0 for word in group) * scale,
                min(word.y0 for word in group) * scale,
                max(word.x1 for word in group) * scale,
                max(word.y1 for word in group) * scale,
            ]
            for group in cell_groups
        ]
        rows.append(row)
        boxes.append(row_boxes)
        cell_tokens.append(row_tokens)
        cell_token_confidences.append(row_confidences)

    rows, boxes, cell_tokens, cell_token_confidences = _merge_wrapped_labels(
        rows,
        boxes,
        cell_tokens,
        cell_token_confidences,
    )
    candidate_rows = [
        (row, row_boxes, row_tokens, row_confidences)
        for row, row_boxes, row_tokens, row_confidences in zip(
            rows,
            boxes,
            cell_tokens,
            cell_token_confidences,
            strict=True,
        )
        if len(row) > 1
    ]
    rows = [row for row, _, _, _ in candidate_rows]
    boxes = [row_boxes for _, row_boxes, _, _ in candidate_rows]
    cell_tokens = [row_tokens for _, _, row_tokens, _ in candidate_rows]
    cell_token_confidences = [
        row_confidences for _, _, _, row_confidences in candidate_rows
    ]
    if any(
        len(row) > 1
        and not _looks_like_financial_cell(row[0])
        and all(_looks_like_financial_cell(value) for value in row[1:])
        for row in rows
    ):
        rows, boxes, cell_tokens, cell_token_confidences = _align_numeric_columns(
            rows,
            boxes,
            cell_tokens,
            cell_token_confidences,
        )
    numeric_rows = sum(
        any(_looks_like_financial_cell(cell) for cell in row[1:]) for row in rows
    )
    if len(rows) < 3 or numeric_rows < 2:
        return [], [], [], []
    return rows, boxes, cell_tokens, cell_token_confidences


def _merge_wrapped_labels(
    rows: list[list[str]],
    boxes: list[list[list[float] | None]],
    cell_tokens: list[list[list[str]]],
    cell_token_confidences: list[list[list[float | None]]],
) -> tuple[
    list[list[str]],
    list[list[list[float] | None]],
    list[list[list[str]]],
    list[list[list[float | None]]],
]:
    merged_rows: list[list[str]] = []
    merged_boxes: list[list[list[float] | None]] = []
    merged_tokens: list[list[list[str]]] = []
    merged_confidences: list[list[list[float | None]]] = []
    for row, row_boxes, row_tokens, row_confidences in zip(
        rows,
        boxes,
        cell_tokens,
        cell_token_confidences,
        strict=True,
    ):
        if (
            merged_rows
            and len(merged_rows[-1]) == 1
            and len(row) > 1
            and len(merged_tokens[-1][0]) > 1
            and not _looks_like_financial_cell(merged_rows[-1][0])
            and any(_looks_like_financial_cell(cell) for cell in row[1:])
            and merged_boxes[-1][0] is not None
            and row_boxes[0] is not None
            and _is_wrapped_label(
                merged_rows[-1][0],
                merged_boxes[-1][0],
                row[0],
                row_boxes[0],
            )
        ):
            previous_box = merged_boxes.pop()[0]
            previous_label = merged_rows.pop()[0]
            previous_tokens = merged_tokens.pop()[0]
            previous_confidences = merged_confidences.pop()[0]
            row[0] = f"{previous_label} {row[0]}"
            row_boxes[0] = [
                min(previous_box[0], row_boxes[0][0]),
                min(previous_box[1], row_boxes[0][1]),
                max(previous_box[2], row_boxes[0][2]),
                max(previous_box[3], row_boxes[0][3]),
            ]
            row_tokens[0] = previous_tokens + row_tokens[0]
            row_confidences[0] = previous_confidences + row_confidences[0]
        merged_rows.append(row)
        merged_boxes.append(row_boxes)
        merged_tokens.append(row_tokens)
        merged_confidences.append(row_confidences)
    return merged_rows, merged_boxes, merged_tokens, merged_confidences


def _low_confidence_warnings(
    cell_token_confidences: list[list[list[float | None]]],
    page_number: int,
) -> list[ExtractionWarning]:
    low_confidence_count = sum(
        confidence is None or confidence < OCR_LOW_CONFIDENCE_THRESHOLD
        for row in cell_token_confidences
        for cell in row
        for confidence in cell
    )
    if not low_confidence_count:
        return []
    return [
        ExtractionWarning(
            code="OCR_LOW_CONFIDENCE_TOKENS",
            message=(
                f"{low_confidence_count} OCR token(s) in this candidate table have "
                "low or unavailable confidence; verify them against the PDF."
            ),
            page_number=page_number,
        )
    ]


def _align_numeric_columns(
    rows: list[list[str]],
    boxes: list[list[list[float] | None]],
    cell_tokens: list[list[list[str]]],
    cell_confidences: list[list[list[float | None]]],
) -> tuple[
    list[list[str]],
    list[list[list[float] | None]],
    list[list[list[str]]],
    list[list[list[float | None]]],
]:
    alignment_tolerance = 8.0
    numeric_data_rows = [
        index
        for index, row in enumerate(rows)
        if len(row) > 1
        and not _looks_like_financial_cell(row[0])
        and all(_looks_like_financial_cell(value) for value in row[1:])
    ]
    anchor_points = [
        (box[2], box[1])
        for index in numeric_data_rows
        for box, value in zip(boxes[index][1:], rows[index][1:], strict=True)
        if box is not None and value.strip()
    ]
    if not anchor_points:
        return rows, boxes, cell_tokens, cell_confidences

    clusters: list[list[tuple[float, float]]] = []
    for point in sorted(anchor_points):
        if (
            clusters
            and point[0]
            - sum(existing[0] for existing in clusters[-1]) / len(clusters[-1])
            <= alignment_tolerance
        ):
            clusters[-1].append(point)
        else:
            clusters.append([point])
    anchors = [
        sum(point[0] for point in cluster) / len(cluster)
        for cluster in clusters
        if len({round(point[1], 1) for point in cluster}) >= 3
    ]
    if len(anchors) < 3:
        return rows, boxes, cell_tokens, cell_confidences

    for index in numeric_data_rows:
        aligned_values = [""] * len(anchors)
        aligned_boxes: list[list[float] | None] = [None] * len(anchors)
        aligned_tokens: list[list[str]] = [[] for _ in anchors]
        aligned_confidences: list[list[float | None]] = [[] for _ in anchors]
        claimed_columns: set[int] = set()
        valid_alignment = True
        for value_index, value_box in enumerate(boxes[index][1:], start=1):
            if value_box is None:
                valid_alignment = False
                break
            column_index = min(
                range(len(anchors)),
                key=lambda anchor_index: abs(value_box[2] - anchors[anchor_index]),
            )
            if (
                abs(value_box[2] - anchors[column_index]) > alignment_tolerance
                or column_index in claimed_columns
            ):
                valid_alignment = False
                break
            claimed_columns.add(column_index)
            aligned_values[column_index] = rows[index][value_index]
            aligned_boxes[column_index] = value_box
            aligned_tokens[column_index] = cell_tokens[index][value_index]
            aligned_confidences[column_index] = cell_confidences[index][value_index]

        if valid_alignment:
            rows[index] = [rows[index][0], *aligned_values]
            boxes[index] = [boxes[index][0], *aligned_boxes]
            cell_tokens[index] = [cell_tokens[index][0], *aligned_tokens]
            cell_confidences[index] = [
                cell_confidences[index][0],
                *aligned_confidences,
            ]

    return rows, boxes, cell_tokens, cell_confidences


def _irregular_row_warnings(
    rows: list[list[str]],
    page_number: int,
) -> list[ExtractionWarning]:
    if len({len(row) for row in rows}) <= 1:
        return []
    return [
        ExtractionWarning(
            code="OCR_LAYOUT_IRREGULAR_ROWS",
            message=(
                "Candidate rows have different cell counts. Cell-to-column "
                "alignment may be ambiguous; verify each cell against the PDF."
            ),
            page_number=page_number,
        )
    ]


def _is_wrapped_label(
    previous_label: str,
    previous_box: list[float],
    current_label: str,
    current_box: list[float],
) -> bool:
    if not current_label.strip() or any(char.isdigit() for char in current_label):
        return False
    previous_height = previous_box[3] - previous_box[1]
    current_height = current_box[3] - current_box[1]
    vertical_gap = current_box[1] - previous_box[3]
    allowed_vertical_gap = max(previous_height, current_height) * 1.5
    horizontal_tolerance = max(8.0, min(previous_height, current_height))
    return (
        0 <= vertical_gap <= allowed_vertical_gap
        and abs(previous_box[0] - current_box[0]) <= horizontal_tolerance
        and len(previous_label.split()) > 1
    )


def _looks_like_financial_cell(value: str) -> bool:
    stripped = re.sub(r"^(?:INR|Rs\.?)\s*", "", value.strip(), flags=re.IGNORECASE)
    stripped = stripped.replace("₹", "").strip()
    allowed = set("0123456789,().%+-–—₹ ")
    return (
        bool(stripped)
        and all(char in allowed for char in stripped)
        and (any(char.isdigit() for char in stripped) or stripped in {"-", "–", "—"})
    )
