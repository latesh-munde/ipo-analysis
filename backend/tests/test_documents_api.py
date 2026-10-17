from io import BytesIO

import pymupdf as fitz
from app.api.v1.router import get_document_service
from app.core.config import Settings
from app.main import app
from app.services.documents import DocumentService
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
