from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pymupdf as fitz
import pytest
from app.core.config import Settings
from app.schemas.documents import DocumentMetadata, DocumentStatus
from app.services.document_repository import DocumentRepository
from app.services.documents import DocumentInputError, DocumentService


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
        return "Recognized prospectus text with sufficient detail.", 0.91

    monkeypatch.setattr(pdf_extraction, "recognize_page", fake_ocr)
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


def test_ocr_unavailable_is_reported_without_erasing_native_text(monkeypatch) -> None:
    from app.services import pdf_extraction
    from app.services.pdf_ocr import OcrUnavailableError

    def unavailable(*args, **kwargs):
        raise OcrUnavailableError("tesseract missing")

    monkeypatch.setattr(pdf_extraction, "recognize_page", unavailable)
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
