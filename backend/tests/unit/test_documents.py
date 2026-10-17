from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pymupdf as fitz
import pytest
from app.core.config import Settings
from app.schemas.documents import (
    DocumentMetadata,
    DocumentStatus,
    PageExtraction,
)
from app.services.document_repository import DocumentRepository
from app.services.documents import DocumentInputError, DocumentService
from app.services.pdf_ocr import OcrPageResult, OcrWord


def make_pdf(
    text: str = "IPO document with enough source content to avoid low-text warnings.",
) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    if text:
        page.insert_text((72, 72), text)
    content = pdf.tobytes()
    pdf.close()
    return content


def test_legacy_page_result_defaults_new_ocr_reading_fields_to_none() -> None:
    page = PageExtraction.model_validate(
        {
            "document_id": "legacy-document",
            "page_number": 1,
            "text": "Previously persisted text",
            "extraction_method": "native_pdf",
            "status": "completed",
            "character_count": 25,
            "warnings": [],
        }
    )

    assert page.native_text is None
    assert page.ocr_text is None


def upload(
    service: DocumentService,
    content: bytes,
    *,
    filename: str = "prospectus.pdf",
    content_type: str = "application/pdf",
):
    return service.upload(
        BytesIO(content),
        filename,
        content_type,
        "DRHP",
    )


def test_upload_extracts_page_text_and_persists_provenance(tmp_path) -> None:
    service = DocumentService(Settings(document_storage_dir=tmp_path))

    result = upload(service, make_pdf())
    stored = service.get_result(result.document.document_id)

    assert result.document.status == DocumentStatus.COMPLETED
    assert result.document.page_count == 1
    assert stored is not None
    assert stored.pages[0].document_id == result.document.document_id
    assert stored.pages[0].page_number == 1
    assert "IPO document" in stored.pages[0].text
    assert stored.pages[0].extraction_method == "native_pdf"
    assert stored.pages[0].native_text == stored.pages[0].text
    assert stored.pages[0].ocr_text is None


def test_identical_upload_returns_existing_document_without_reprocessing(
    tmp_path,
) -> None:
    service = DocumentService(Settings(document_storage_dir=tmp_path))
    content = make_pdf()

    first = upload(service, content)
    second = upload(service, content, filename="same-bytes.pdf")

    assert second.document.document_id == first.document.document_id
    assert second.document.duplicate is True
    assert len(list(tmp_path.glob("*.pdf"))) == 1


@pytest.mark.parametrize(
    ("filename", "content_type", "content", "code"),
    [
        ("prospectus.txt", "application/pdf", make_pdf(), "UNSUPPORTED_FILE_TYPE"),
        ("prospectus.pdf", "text/plain", make_pdf(), "UNSUPPORTED_CONTENT_TYPE"),
        ("prospectus.pdf", "application/pdf", b"not a PDF", "INVALID_PDF"),
        ("prospectus.pdf", "application/pdf", b"", "EMPTY_FILE"),
        (
            "prospectus.pdf",
            "application/pdf",
            b"%PDF-1.7\ninvalid body",
            "UNREADABLE_PDF",
        ),
    ],
)
def test_invalid_uploads_return_controlled_errors(
    tmp_path,
    filename: str,
    content_type: str,
    content: bytes,
    code: str,
) -> None:
    service = DocumentService(Settings(document_storage_dir=tmp_path))

    with pytest.raises(DocumentInputError) as error:
        upload(service, content, filename=filename, content_type=content_type)

    assert error.value.code == code
    assert list(tmp_path.glob(".upload-*")) == []


def test_oversized_upload_is_rejected_before_pdf_processing(tmp_path) -> None:
    service = DocumentService(
        Settings(
            document_storage_dir=tmp_path,
            document_max_upload_bytes=100,
        )
    )

    with pytest.raises(DocumentInputError) as error:
        upload(service, make_pdf("x" * 500))

    assert error.value.status_code == 413
    assert error.value.code == "FILE_TOO_LARGE"
    assert list(tmp_path.glob(".upload-*")) == []


def test_encrypted_pdf_is_rejected(tmp_path) -> None:
    pdf = fitz.open()
    pdf.new_page()
    encrypted = pdf.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="private",
        owner_pw="owner",
    )
    pdf.close()
    service = DocumentService(Settings(document_storage_dir=tmp_path))

    with pytest.raises(DocumentInputError) as error:
        upload(service, encrypted)

    assert error.value.code == "ENCRYPTED_PDF"


def test_recoverable_incomplete_pdf_is_accepted_with_warning(tmp_path) -> None:
    content = make_pdf()
    truncated_content = content[:-20]
    service = DocumentService(Settings(document_storage_dir=tmp_path))

    result = upload(service, truncated_content)

    assert result.document.status == DocumentStatus.COMPLETED_WITH_WARNINGS
    assert any(warning.code == "PDF_REPAIRED" for warning in result.document.warnings)


def test_page_table_extraction_preserves_raw_cell_strings(tmp_path) -> None:
    pdf = fitz.open()
    page = pdf.new_page()
    x_coordinates = [72, 180, 300]
    y_coordinates = [72, 100, 128]
    for x in x_coordinates:
        page.draw_line((x, y_coordinates[0]), (x, y_coordinates[-1]))
    for y in y_coordinates:
        page.draw_line((x_coordinates[0], y), (x_coordinates[-1], y))
    values = [["Metric", "Amount"], ["Revenue", "1,234.56"]]
    for row_index, row in enumerate(values):
        for column_index, value in enumerate(row):
            page.insert_text(
                (x_coordinates[column_index] + 4, y_coordinates[row_index] + 18),
                value,
            )
    content = pdf.tobytes()
    pdf.close()
    service = DocumentService(Settings(document_storage_dir=tmp_path))

    result = upload(service, content)
    tables = service.get_tables(result.document.document_id)

    assert tables
    assert tables[0].document_id == result.document.document_id
    assert tables[0].page_number == 1
    assert tables[0].rows[1][1] == "1,234.56"


def test_scanned_page_uses_ocr_only_when_configured(tmp_path, monkeypatch) -> None:
    from app.services import pdf_extraction

    calls = []

    def fake_ocr(*args, **kwargs):
        calls.append(True)
        return OcrPageResult(
            "Recognized prospectus text with sufficient detail.",
            0.91,
            [],
        )

    monkeypatch.setattr(pdf_extraction, "recognize_page_with_layout", fake_ocr)
    settings = Settings(
        document_storage_dir=tmp_path,
        document_ocr_enabled=True,
    )
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "scan")
    page.draw_rect((70, 60, 150, 90))
    content = pdf.tobytes()
    pdf.close()

    result = upload(DocumentService(settings), content)
    extracted = DocumentService(settings).get_pages(result.document.document_id)

    assert calls
    assert extracted[0].extraction_method == "tesseract_ocr"
    assert extracted[0].ocr_confidence == pytest.approx(0.91)
    assert extracted[0].native_text.strip() == "scan"
    assert extracted[0].ocr_text == "Recognized prospectus text with sufficient detail."
    assert extracted[0].text == extracted[0].ocr_text
    assert any(
        warning.code == "OCR_TEXT_REQUIRES_REVIEW" for warning in extracted[0].warnings
    )


def test_shorter_ocr_is_preserved_without_replacing_native_text(tmp_path, monkeypatch):
    from app.services import pdf_extraction

    monkeypatch.setattr(
        pdf_extraction,
        "recognize_page_with_layout",
        lambda *args, **kwargs: OcrPageResult("OCR 1,280.50", 0.99, []),
    )
    settings = Settings(
        document_storage_dir=tmp_path,
        document_ocr_enabled=True,
        document_low_text_char_threshold=100,
    )
    pdf = fitz.open()
    page = pdf.new_page()
    native = "Native selectable financial statement text for source review."
    page.insert_text((72, 72), native)
    page.draw_line((70, 60), (150, 60))
    content = pdf.tobytes()
    pdf.close()

    service = DocumentService(settings)
    result = upload(service, content)
    extracted = service.get_pages(result.document.document_id)[0]

    assert extracted.extraction_method == "native_pdf"
    assert native in extracted.native_text
    assert extracted.ocr_text == "OCR 1,280.50"
    assert extracted.text == extracted.native_text
    assert any(
        warning.code == "OCR_TEXT_REQUIRES_REVIEW" for warning in extracted.warnings
    )


def test_pages_are_retained_when_another_page_fails() -> None:
    from app.services.pdf_extraction import extract_pdf

    class ReadablePage:
        def get_text(self, _kind):
            return "Text from the readable page."

        def find_tables(self):
            return SimpleNamespace(tables=[])

        def get_images(self):
            return []

        def get_drawings(self):
            return []

    class PartiallyReadablePdf:
        page_count = 2

        def load_page(self, page_index):
            if page_index == 0:
                raise RuntimeError("synthetic page read failure")
            return ReadablePage()

    pages, _, warnings, status = extract_pdf(
        PartiallyReadablePdf(),
        "document-id",
        Settings(document_ocr_enabled=False),
    )

    assert [page.page_number for page in pages] == [1, 2]
    assert pages[0].status == "failed"
    assert "readable page" in pages[1].text
    assert warnings[0].code == "PAGE_READ_FAILED"
    assert status == DocumentStatus.COMPLETED_WITH_WARNINGS


def test_table_cell_values_are_not_normalized() -> None:
    from app.services.pdf_extraction import extract_pdf

    raw_values = ["1,234.56", "(45.20)", "-", "0.00", "12.5%"]

    class TablePage:
        def get_text(self, _kind):
            return "Financial values"

        def find_tables(self, **_kwargs):
            return SimpleNamespace(
                tables=[SimpleNamespace(extract=lambda: [raw_values])]
            )

        def get_images(self):
            return []

        def get_drawings(self):
            return []

    class OnePagePdf:
        page_count = 1

        def load_page(self, _page_index):
            return TablePage()

    _, tables, _, _ = extract_pdf(OnePagePdf(), "document-id", Settings())

    assert tables[0].rows == [raw_values]
    assert tables[0].page_number == 1


def test_scanned_financial_table_is_persisted_with_cell_boxes_and_review(
    tmp_path,
    monkeypatch,
) -> None:
    from app.services import pdf_extraction

    words = []
    for line_number, (label, amount) in enumerate(
        [("FY 2024", "1,000"), ("Revenue", "(1,200.50)"), ("Revenue", "-")],
        start=1,
    ):
        label_x = 100
        for token in label.split():
            width = len(token) * 8
            words.append(
                OcrWord(
                    text=token,
                    confidence=45.0 if line_number == 3 else 90.0,
                    x0=label_x,
                    y0=line_number * 30,
                    x1=label_x + width,
                    y1=line_number * 30 + 12,
                    line_id=(1, 1, line_number),
                )
            )
            label_x += width + 4
        words.append(
            OcrWord(
                text=amount,
                confidence=45.0 if line_number == 3 else 90.0,
                x0=230,
                y0=line_number * 30,
                x1=230 + max(10, len(amount) * 8),
                y1=line_number * 30 + 12,
                line_id=(1, 1, line_number),
            )
        )

    monkeypatch.setattr(
        pdf_extraction,
        "recognize_page_with_layout",
        lambda *args, **kwargs: OcrPageResult(
            "FY 2024 1,000 Revenue (1,200.50) Revenue -",
            0.9,
            words,
        ),
    )
    settings = Settings(
        document_storage_dir=tmp_path,
        document_ocr_enabled=True,
    )
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "scan")
    page.draw_rect((70, 60, 150, 90))
    content = pdf.tobytes()
    pdf.close()

    service = DocumentService(settings)
    document_id = upload(service, content).document.document_id
    table = service.get_tables(document_id)[0]

    assert table.extraction_method == "tesseract_ocr_layout"
    assert table.source_document_sha256 == service.get_metadata(document_id).sha256
    assert table.rows == [
        ["FY 2024", "1,000"],
        ["Revenue", "(1,200.50)"],
        ["Revenue", "-"],
    ]
    assert table.cell_tokens[1][1] == ["(1,200.50)"]
    assert table.cell_token_confidences[2][1] == [45.0]
    assert any(
        warning.code == "OCR_LOW_CONFIDENCE_TOKENS" for warning in table.warnings
    )
    assert table.cell_boxes[1][1] == pytest.approx([82.8, 21.6, 111.6, 25.92])
    assert table.ocr_engine == "tesseract"
    assert table.ocr_render_dpi == settings.document_ocr_dpi

    review = service.review_financial_cell(
        document_id, 1, table.table_index, 1, 1, "-1,200.50"
    )
    reopened = DocumentService(settings).get_financial_cell_review(
        document_id, 1, table.table_index, 1, 1
    )

    assert review.source_value == "(1,200.50)"
    assert review.confirmed_value == "-1,200.50"
    assert reopened == review
    assert service.get_tables(document_id)[0].rows[1][1] == "(1,200.50)"


def test_ocr_layout_merges_wrapped_label_and_tracks_multiple_value_cells() -> None:
    from app.services.pdf_extraction import (
        _looks_like_financial_cell,
        _ocr_layout_rows,
    )

    words = []

    def add_line(line_number: int, y: float, cells: list[tuple[float, list[str]]]):
        for start_x, tokens in cells:
            x = start_x
            for token in tokens:
                width = len(token) * 8
                words.append(
                    OcrWord(
                        text=token,
                        confidence=92.0,
                        x0=x,
                        y0=y,
                        x1=x + width,
                        y1=y + 10,
                        line_id=(1, 1, line_number),
                    )
                )
                x += width + 4

    add_line(1, 10, [(100, ["Particulars"]), (230, ["FY2024"]), (350, ["FY2025"])])
    add_line(2, 40, [(100, ["Revenue", "from"])])
    add_line(3, 55, [(100, ["operations"]), (230, ["1,000"]), (350, ["(1,250.50)"])])
    add_line(4, 85, [(100, ["Margin"]), (230, ["—"]), (350, ["12.5%"])])

    rows, boxes, cell_tokens, cell_confidences = _ocr_layout_rows(words, scale=0.5)

    assert _ocr_layout_rows(words, scale=0.5) == (
        rows,
        boxes,
        cell_tokens,
        cell_confidences,
    )
    assert rows == [
        ["Particulars", "FY2024", "FY2025"],
        ["Revenue from operations", "1,000", "(1,250.50)"],
        ["Margin", "—", "12.5%"],
    ]
    assert cell_tokens[1][0] == ["Revenue", "from", "operations"]
    assert cell_confidences[1][0] == [92.0, 92.0, 92.0]
    assert boxes[1][0] == pytest.approx([50, 20, 96, 32.5])

    assert _looks_like_financial_cell("Rs. 1,000")
    assert _looks_like_financial_cell("₹ 1,000")
    assert _looks_like_financial_cell("(1,250.50)")
    assert _looks_like_financial_cell("12.5%")
    assert _looks_like_financial_cell("—")
    assert not _looks_like_financial_cell("revenue 1,000")


def test_ocr_layout_rejects_isolated_split_line_as_a_table() -> None:
    from app.services.pdf_extraction import _ocr_layout_rows

    words = [
        OcrWord("Revenue", 90, 100, 20, 150, 30, (1, 1, 1)),
        OcrWord("1,000", 90, 250, 20, 290, 30, (1, 1, 1)),
    ]

    assert _ocr_layout_rows(words, scale=0.5) == ([], [], [], [])


def test_ocr_layout_preserves_missing_cells_and_warns_on_irregular_rows() -> None:
    from app.services.pdf_extraction import (
        _irregular_row_warnings,
        _ocr_layout_rows,
    )

    words = []
    for line_number, cells in enumerate(
        [
            [(100, "Particulars"), (230, "FY2024"), (350, "FY2025")],
            [(100, "Revenue"), (230, "1,000"), (350, "1,200")],
            [(100, "Expenses"), (350, "800")],
            [(100, "Profit"), (230, "200"), (350, "400")],
        ],
        start=1,
    ):
        for x, token in cells:
            words.append(
                OcrWord(
                    text=token,
                    confidence=90,
                    x0=x,
                    y0=line_number * 30,
                    x1=x + max(10, len(token) * 8),
                    y1=line_number * 30 + 12,
                    line_id=(1, 1, line_number),
                )
            )

    rows, _, _, _ = _ocr_layout_rows(words, scale=0.5)

    assert [len(row) for row in rows] == [3, 3, 2, 3]
    warnings = _irregular_row_warnings(rows, page_number=1)
    assert len(warnings) == 1
    assert warnings[0].code == "OCR_LAYOUT_IRREGULAR_ROWS"


def test_ocr_layout_warns_for_low_and_unavailable_token_confidence() -> None:
    from app.services.pdf_extraction import _low_confidence_warnings

    warnings = _low_confidence_warnings(
        [[[None, 59.9, 60.0]]],
        page_number=3,
    )

    assert len(warnings) == 1
    assert warnings[0].code == "OCR_LOW_CONFIDENCE_TOKENS"
    assert "2 OCR token(s)" in warnings[0].message


def test_ocr_layout_aligns_numeric_columns_without_shifting_missing_cells() -> None:
    from app.services.pdf_extraction import _align_numeric_columns

    rows = [
        ["Revenue", "26", "391,729", "350,323", "1,468,853", "1,282,184", "1,095,581"],
        ["Total Income", "401,979", "356,864", "1,497,591", "1,293,330", "1,101,754"],
        ["Expenses", "28", "88,733", "85,167", "344,924", "333,546", "303,377"],
        ["Other Income", "27", "10,250", "6,541", "28,738", "11,146", "6,173"],
    ]
    column_right_edges = [237.0, 311.0, 376.0, 425.0, 473.0, 521.0]
    boxes = []
    tokens = []
    confidences = []
    for row_index, row in enumerate(rows):
        row_boxes = [[50.0, row_index * 12.0, 100.0, row_index * 12.0 + 8.0]]
        row_tokens = [[row[0]]]
        row_confidences = [[95.0]]
        value_edges = column_right_edges[1:] if row_index == 1 else column_right_edges
        for column_index, value in enumerate(row[1:]):
            right_edge = value_edges[column_index]
            row_boxes.append(
                [
                    right_edge - len(value) * 3.0,
                    row_index * 12.0,
                    right_edge,
                    row_index * 12.0 + 8.0,
                ]
            )
            row_tokens.append([value])
            row_confidences.append([95.0])
        boxes.append(row_boxes)
        tokens.append(row_tokens)
        confidences.append(row_confidences)

    aligned = _align_numeric_columns(rows, boxes, tokens, confidences)

    assert [len(row) for row in aligned[0]] == [7, 7, 7, 7]
    assert aligned[0][1] == [
        "Total Income",
        "",
        "401,979",
        "356,864",
        "1,497,591",
        "1,293,330",
        "1,101,754",
    ]
    assert aligned[1][1][1] is None
    assert aligned[2][1][2] == ["401,979"]
    assert aligned[3][1][2] == [95.0]


def test_ocr_unavailable_is_reported_without_erasing_native_text(monkeypatch) -> None:
    from app.services import pdf_extraction
    from app.services.pdf_ocr import OcrUnavailableError

    def unavailable(*args, **kwargs):
        raise OcrUnavailableError("tesseract missing")

    monkeypatch.setattr(pdf_extraction, "recognize_page_with_layout", unavailable)
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "tiny")
    page.draw_line((70, 60), (150, 60))

    pages, _, warnings, status = pdf_extraction.extract_pdf(
        pdf,
        "document-id",
        Settings(document_ocr_enabled=True),
    )
    pdf.close()

    assert pages[0].text.strip() == "tiny"
    assert pages[0].extraction_method == "native_pdf"
    assert any(warning.code == "OCR_UNAVAILABLE" for warning in warnings)
    assert status == DocumentStatus.COMPLETED_WITH_WARNINGS


def test_blank_pdf_has_an_explicit_page_result(tmp_path) -> None:
    pdf = fitz.open()
    pdf.new_page()
    content = pdf.tobytes()
    pdf.close()
    service = DocumentService(Settings(document_storage_dir=tmp_path))

    result = upload(service, content)
    pages = service.get_pages(result.document.document_id)

    assert result.document.status == DocumentStatus.FAILED
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert any(warning.code == "BLANK_PAGE" for warning in pages[0].warnings)


def test_table_failure_does_not_discard_native_page_text() -> None:
    from app.services.pdf_extraction import extract_pdf

    class TextPage:
        def get_text(self, _kind):
            return "A sufficiently long readable native-text page."

        def find_tables(self):
            raise RuntimeError("synthetic table failure")

        def get_images(self):
            return []

        def get_drawings(self):
            return []

    class OnePagePdf:
        page_count = 1

        def load_page(self, _page_index):
            return TextPage()

    pages, tables, warnings, status = extract_pdf(
        OnePagePdf(),
        "document-id",
        Settings(),
    )

    assert pages[0].text == "A sufficiently long readable native-text page."
    assert pages[0].status == "completed_with_warnings"
    assert tables == []
    assert warnings[0].code == "TABLE_EXTRACTION_FAILED"
    assert status == DocumentStatus.COMPLETED_WITH_WARNINGS


def test_startup_recovery_marks_interrupted_documents_failed(tmp_path) -> None:
    repository = DocumentRepository(tmp_path / "documents.sqlite3")
    metadata = DocumentMetadata(
        document_id="interrupted",
        original_filename="prospectus.pdf",
        file_size=100,
        detected_type="application/pdf",
        sha256="a" * 64,
        uploaded_at=datetime.now(UTC),
        document_type="DRHP",
        status=DocumentStatus.PROCESSING,
        page_count=1,
        warnings=[],
    )
    repository.create(metadata, Path("unexposed-internal-path"))

    assert repository.fail_interrupted() == 1

    recovered = repository.get_metadata("interrupted")
    assert recovered is not None
    assert recovered.status == DocumentStatus.FAILED
    assert recovered.warnings[0].code == "PROCESSING_INTERRUPTED"
