from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.api.v1.router import get_document_service
from app.main import app
from app.schemas.documents import (
    DocumentMetadata,
    DocumentStatus,
    ExtractedTable,
    ExtractionWarning,
)
from fastapi.testclient import TestClient


def make_document_service(table: ExtractedTable) -> SimpleNamespace:
    metadata = DocumentMetadata(
        document_id="doc-1",
        original_filename="filing.pdf",
        file_size=10,
        detected_type="application/pdf",
        sha256="a" * 64,
        uploaded_at=datetime.now(UTC),
        document_type="RHP",
        status=DocumentStatus.COMPLETED,
        page_count=1,
        warnings=[],
    )
    return SimpleNamespace(
        get_metadata=lambda document_id: metadata if document_id == "doc-1" else None,
        get_tables=lambda document_id: [table] if document_id == "doc-1" else [],
    )


def revenue_fact(
    period_label: str,
    start: str,
    end: str,
    column: int,
) -> dict:
    return {
        "line_item_code": "revenue_from_operations",
        "statement_type": "profit_and_loss",
        "period_label": period_label,
        "period_kind": "annual",
        "period_start": start,
        "period_end": end,
        "statement_basis": "consolidated",
        "audit_status": "audited",
        "restatement_status": "as_published",
        "currency": "INR",
        "unit": "rupees",
        "page_number": 1,
        "table_index": 0,
        "row_index": 1,
        "period_header_row_index": 0,
        "label_column_index": 0,
        "value_column_index": column,
    }


def test_analysis_api_reads_values_from_exact_source_cells(monkeypatch) -> None:
    table = ExtractedTable(
        document_id="doc-1",
        page_number=1,
        table_index=0,
        extraction_method="tesseract_ocr",
        rows=[
            ["", "FY 2024", "FY 2025"],
            ["Revenue from operations", "100.00", "125.00"],
        ],
        warnings=[
            ExtractionWarning(
                code="OCR_LOW_CONFIDENCE",
                message="Review source digits.",
                page_number=1,
            )
        ],
    )
    service = make_document_service(table)
    monkeypatch.setitem(app.dependency_overrides, get_document_service, lambda: service)
    request = {
        "facts": [
            revenue_fact("FY 2024", "2023-04-01", "2024-03-31", 1),
            revenue_fact("FY 2025", "2024-04-01", "2025-03-31", 2),
        ]
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/documents/doc-1/financial-analysis",
            json=request,
        )

    assert response.status_code == 200
    report = response.json()["data"]
    growth = next(
        metric
        for metric in report["metrics"]
        if metric["metric_code"] == "revenue_growth_yoy"
        and metric["period_label"] == "FY 2025"
    )
    assert Decimal(growth["value"]) == Decimal("25")
    assert growth["formula_version"] == "1.0.0"
    assert growth["input_fact_ids"]
    assert [evidence["extracted_value"] for evidence in growth["evidence"]] == [
        "125.00",
        "100.00",
    ]
    assert [evidence["period_header_text"] for evidence in growth["evidence"]] == [
        "FY 2025",
        "FY 2024",
    ]
    assert "OCR_SOURCE_REQUIRES_VERIFICATION" in growth["finding_codes"]
    assert growth["finding_ids"]
    assert report["facts"][1]["evidence"]["original_label"] == "Revenue from operations"


def test_analysis_api_rejects_nonexistent_evidence_cells(monkeypatch) -> None:
    table = ExtractedTable(
        document_id="doc-1",
        page_number=1,
        table_index=0,
        extraction_method="native_text",
        rows=[["", "FY 2025"], ["Revenue", "100"]],
        warnings=[],
    )
    service = make_document_service(table)
    monkeypatch.setitem(app.dependency_overrides, get_document_service, lambda: service)
    fact = revenue_fact("FY 2025", "2024-04-01", "2025-03-31", 1)
    fact["page_number"] = 2

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/documents/doc-1/financial-analysis",
            json={"facts": [fact]},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOURCE_TABLE_NOT_FOUND"


def test_analysis_api_rejects_unknown_currencies(monkeypatch) -> None:
    table = ExtractedTable(
        document_id="doc-1",
        page_number=1,
        table_index=0,
        extraction_method="native_text",
        rows=[["", "FY 2025"], ["Revenue", "100"]],
        warnings=[],
    )
    service = make_document_service(table)
    monkeypatch.setitem(app.dependency_overrides, get_document_service, lambda: service)
    fact = revenue_fact("FY 2025", "2024-04-01", "2025-03-31", 1)
    fact["currency"] = "USD"

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/documents/doc-1/financial-analysis",
            json={"facts": [fact]},
        )

    assert response.status_code == 422
    assert response.json()["success"] is False
