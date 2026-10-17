from io import BytesIO

import pymupdf as fitz
from app.api.v1.router import get_document_service
from app.core.config import Settings
from app.main import app
from app.schemas.documents import DocumentStatus
from app.services.documents import DocumentService
from app.services.pdf_ocr import OcrPageResult, OcrWord
from fastapi.testclient import TestClient


def pdf_bytes() -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text(
        (72, 72),
        "Annual revenue was 1,234.56 units according to the filing.",
    )
    content = pdf.tobytes()
    pdf.close()
    return content


def test_document_upload_and_retrieval_routes(tmp_path, monkeypatch) -> None:
    service = DocumentService(Settings(document_storage_dir=tmp_path))
    monkeypatch.setitem(app.dependency_overrides, get_document_service, lambda: service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/documents",
            files={"file": ("rhp.pdf", BytesIO(pdf_bytes()), "application/pdf")},
            data={"document_type": "RHP"},
        )
        assert response.status_code == 201
        document_id = response.json()["data"]["document"]["document_id"]

        metadata = client.get(f"/api/v1/documents/{document_id}")
        pages = client.get(f"/api/v1/documents/{document_id}/pages")
        tables = client.get(f"/api/v1/documents/{document_id}/tables")

    assert metadata.status_code == 200
    assert metadata.json()["data"]["document_type"] == "RHP"
    assert pages.status_code == 200
    assert pages.json()["data"]["total"] == 1
    assert pages.json()["data"]["items"][0]["page_number"] == 1
    assert tables.status_code == 200
    assert tables.json()["data"]["total"] >= 0


def test_duplicate_upload_returns_existing_record(tmp_path, monkeypatch) -> None:
    service = DocumentService(Settings(document_storage_dir=tmp_path))
    monkeypatch.setitem(app.dependency_overrides, get_document_service, lambda: service)
    content = pdf_bytes()

    with TestClient(app) as client:
        files = {"file": ("drhp.pdf", BytesIO(content), "application/pdf")}
        first = client.post("/api/v1/documents", files=files)
        second = client.post(
            "/api/v1/documents",
            files={"file": ("renamed.pdf", BytesIO(content), "application/pdf")},
        )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["data"]["document"]["duplicate"] is True
    assert (
        second.json()["data"]["document"]["document_id"]
        == first.json()["data"]["document"]["document_id"]
    )


def test_invalid_upload_returns_standard_safe_error(tmp_path, monkeypatch) -> None:
    service = DocumentService(Settings(document_storage_dir=tmp_path))
    monkeypatch.setitem(app.dependency_overrides, get_document_service, lambda: service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/documents",
            files={"file": ("not.pdf", BytesIO(b"not a pdf"), "application/pdf")},
        )

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "INVALID_PDF"
    assert "stack" not in response.text.lower()


def test_missing_document_returns_standard_not_found(tmp_path, monkeypatch) -> None:
    service = DocumentService(Settings(document_storage_dir=tmp_path))
    monkeypatch.setitem(app.dependency_overrides, get_document_service, lambda: service)

    with TestClient(app) as client:
        response = client.get("/api/v1/documents/not-present")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_source_page_and_ocr_cell_review_routes(tmp_path, monkeypatch) -> None:
    from app.services import pdf_extraction

    words = []
    for line_number, (label, amount) in enumerate(
        [("FY 2024", "100"), ("Revenue", "100"), ("Revenue", "125")],
        start=1,
    ):
        for word_index, token in enumerate(label.split()):
            x0 = 100 + word_index * 35
            words.append(
                OcrWord(
                    text=token,
                    confidence=91,
                    x0=x0,
                    y0=line_number * 30,
                    x1=x0 + len(token) * 8,
                    y1=line_number * 30 + 12,
                    line_id=(1, 1, line_number),
                )
            )
        words.append(
            OcrWord(
                text=amount,
                confidence=91,
                x0=230,
                y0=line_number * 30,
                x1=260,
                y1=line_number * 30 + 12,
                line_id=(1, 1, line_number),
            )
        )

    monkeypatch.setattr(
        pdf_extraction,
        "recognize_page_with_layout",
        lambda *args, **kwargs: OcrPageResult(
            "FY 2024 100 Revenue 100 Revenue 125", 0.91, words
        ),
    )
    service = DocumentService(
        Settings(document_storage_dir=tmp_path, document_ocr_enabled=True)
    )
    monkeypatch.setitem(app.dependency_overrides, get_document_service, lambda: service)
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "scan")
    page.draw_rect((70, 60, 150, 90))
    content = pdf.tobytes()
    pdf.close()

    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/documents",
            files={"file": ("scanned.pdf", BytesIO(content), "application/pdf")},
        )
        document_id = upload.json()["data"]["document"]["document_id"]
        image = client.get(f"/api/v1/documents/{document_id}/pages/1/image")
        review = client.post(
            f"/api/v1/documents/{document_id}/pages/1/tables/1/cells/1/1/review",
            json={"confirmed_value": "1,000", "source_checked": True},
        )
        unchecked_review = client.post(
            f"/api/v1/documents/{document_id}/pages/1/tables/1/cells/1/2/review",
            json={"confirmed_value": "125", "source_checked": False},
        )
        reviews = client.get(f"/api/v1/documents/{document_id}/financial-cell-reviews")
        source_table = service.get_tables(document_id)[0]
        changed_boxes = [list(row) for row in source_table.cell_boxes]
        changed_boxes[1][1] = [11, 21, 21, 31]
        changed_table = source_table.model_copy(update={"cell_boxes": changed_boxes})
        service.repository.complete(
            document_id,
            DocumentStatus.COMPLETED,
            1,
            [],
            service.get_pages(document_id),
            [changed_table],
        )
        stale_reviews = client.get(
            f"/api/v1/documents/{document_id}/financial-cell-reviews"
        )
        invalid_page = client.get(f"/api/v1/documents/{document_id}/pages/2/image")

    assert upload.status_code == 201
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.content.startswith(b"\x89PNG")
    assert review.status_code == 200
    assert review.json()["data"]["source_value"] == "100"
    assert review.json()["data"]["confirmed_value"] == "1,000"
    assert len(review.json()["data"]["source_cell_sha256"]) == 64
    assert unchecked_review.status_code == 422
    assert unchecked_review.json()["success"] is False
    assert len(reviews.json()["data"]) == 1
    assert stale_reviews.json()["data"] == []
    assert invalid_page.status_code == 404
