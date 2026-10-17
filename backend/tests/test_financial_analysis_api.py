from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.api.v1.router import get_document_service
from app.financial.evidence import financial_cell_sha256, financial_table_sha256
from app.main import app
from app.schemas.documents import (
    DocumentMetadata,
    DocumentStatus,
    ExtractedTable,
    ExtractionWarning,
)
from app.schemas.financial_analysis import PersistedFinancialFact
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
    saved_facts = {}

    def save_financial_facts(facts):
        persisted = []
        for fact in facts:
            previous = saved_facts.get(fact.fact_id)
            record = PersistedFinancialFact(
                **fact.model_dump(),
                revision=previous.revision + 1 if previous else 1,
                created_at=datetime.now(UTC),
            )
            saved_facts[fact.fact_id] = record
            persisted.append(record)
        return persisted

    return SimpleNamespace(
        get_metadata=lambda document_id: metadata if document_id == "doc-1" else None,
        get_tables=lambda document_id: [table] if document_id == "doc-1" else [],
        get_financial_cell_reviews=lambda _document_id: [],
        save_financial_facts=save_financial_facts,
        get_financial_facts=lambda _document_id, **_kwargs: list(saved_facts.values()),
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
        extraction_method="pymupdf",
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
    assert report["report_schema_version"] == "1.1.0"
    assert report["facts"][0]["revision"] == 1
    assert report["facts"][0]["evidence"]["source_table_sha256"] == (
        financial_table_sha256(table)
    )
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
    assert growth["finding_ids"]
    assert report["facts"][1]["evidence"]["original_label"] == "Revenue from operations"


def test_analysis_persists_canonical_facts_and_exposes_them(monkeypatch) -> None:
    table = ExtractedTable(
        document_id="doc-1",
        page_number=1,
        table_index=0,
        extraction_method="native_pdf",
        rows=[["", "FY 2025"], ["Revenue", "100"]],
        warnings=[],
    )
    service = make_document_service(table)
    monkeypatch.setitem(app.dependency_overrides, get_document_service, lambda: service)

    with TestClient(app) as client:
        report = client.post(
            "/api/v1/documents/doc-1/financial-analysis",
            json={"facts": [revenue_fact("FY 2025", "2024-04-01", "2025-03-31", 1)]},
        )
        saved = client.get(
            "/api/v1/documents/doc-1/financial-facts?include_history=true"
        )

    assert report.status_code == 200
    assert saved.status_code == 200
    fact = saved.json()["data"]["items"][0]
    assert fact["fact_id"] == report.json()["data"]["facts"][0]["fact_id"]
    assert fact["revision"] == 1
    assert fact["evidence"]["source_document_sha256"] == "a" * 64
    assert fact["evidence"]["source_cell_sha256"] == financial_cell_sha256(
        table,
        1,
        1,
        "a" * 64,
    )


def test_analysis_rejects_client_supplied_numeric_fact_values(monkeypatch) -> None:
    table = ExtractedTable(
        document_id="doc-1",
        page_number=1,
        table_index=0,
        extraction_method="native_pdf",
        rows=[["", "FY 2025"], ["Revenue", "100"]],
        warnings=[],
    )
    service = make_document_service(table)
    monkeypatch.setitem(app.dependency_overrides, get_document_service, lambda: service)
    fact = revenue_fact("FY 2025", "2024-04-01", "2025-03-31", 1)
    fact["reported_value"] = "999999"

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/documents/doc-1/financial-analysis",
            json={"facts": [fact]},
        )

    assert response.status_code == 422
    assert response.json()["success"] is False


def test_analysis_rejects_duplicate_source_cell_mapping(monkeypatch) -> None:
    table = ExtractedTable(
        document_id="doc-1",
        page_number=1,
        table_index=0,
        extraction_method="native_pdf",
        rows=[["", "FY 2025"], ["Revenue", "100"]],
        warnings=[],
    )
    service = make_document_service(table)
    monkeypatch.setitem(app.dependency_overrides, get_document_service, lambda: service)
    fact = revenue_fact("FY 2025", "2024-04-01", "2025-03-31", 1)
    duplicate = {
        **fact,
        "line_item_code": "total_income",
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/documents/doc-1/financial-analysis",
            json={"facts": [fact, duplicate]},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "DUPLICATE_SOURCE_CELL_MAPPING"


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


def test_unreviewed_ocr_cells_block_analysis_and_reviewed_corrections_are_used(
    monkeypatch,
) -> None:
    table = ExtractedTable(
        document_id="doc-1",
        page_number=1,
        table_index=0,
        extraction_method="tesseract_ocr_layout",
        rows=[
            ["", "FY 2024", "FY 2025"],
            ["Revenue from operations", "100.00", "125.00"],
        ],
        warnings=[],
        cell_boxes=[
            [None, [10, 10, 20, 20], [20, 10, 30, 20]],
            [[0, 20, 10, 30], [10, 20, 20, 30], [20, 20, 30, 30]],
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
        unreviewed_response = client.post(
            "/api/v1/documents/doc-1/financial-analysis",
            json=request,
        )
        service.get_financial_cell_reviews = lambda _document: [
            SimpleNamespace(
                page_number=1,
                table_index=0,
                row_index=1,
                column_index=col,
                source_value="changed OCR content",
                confirmed_value="9,999",
                reviewed_at=datetime.now(UTC),
                source_cell_sha256=financial_cell_sha256(
                    table,
                    1,
                    col,
                    "a" * 64,
                ),
            )
            for col in (1, 2)
        ]
        stale_review_response = client.post(
            "/api/v1/documents/doc-1/financial-analysis",
            json=request,
        )
        service.get_financial_cell_reviews = lambda _document: [
            SimpleNamespace(
                page_number=1,
                table_index=0,
                row_index=1,
                column_index=col,
                source_value={"1": "100.00", "2": "125.00"}[str(col)],
                confirmed_value={"1": "1,000.00", "2": "1,500.00"}[str(col)],
                reviewed_at=datetime.now(UTC),
                source_cell_sha256=financial_cell_sha256(
                    table,
                    1,
                    col,
                    "a" * 64,
                ),
            )
            for col in (1, 2)
        ]
        reviewed_response = client.post(
            "/api/v1/documents/doc-1/financial-analysis",
            json=request,
        )

    assert unreviewed_response.status_code == 200
    unreviewed = unreviewed_response.json()["data"]
    assert all(fact["status"] == "unverified" for fact in unreviewed["facts"])
    assert all(fact["reported_value"] is None for fact in unreviewed["facts"])
    growth = next(
        metric
        for metric in unreviewed["metrics"]
        if metric["metric_code"] == "revenue_growth_yoy"
        and metric["period_label"] == "FY 2025"
    )
    assert growth["status"] == "blocked"
    assert growth["reason_code"] == "OCR_VALUE_UNVERIFIED"
    assert all(
        fact["status"] == "unverified"
        for fact in stale_review_response.json()["data"]["facts"]
    )

    assert reviewed_response.status_code == 200
    reviewed = reviewed_response.json()["data"]
    assert reviewed["facts"][1]["reported_value"] == "1500.00"
    assert reviewed["facts"][1]["evidence"]["extracted_value"] == "125.00"
    assert reviewed["facts"][1]["evidence"]["confirmed_value"] == "1,500.00"
    assert reviewed["facts"][1]["evidence"]["review_status"] == "verified"
    reviewed_growth = next(
        metric
        for metric in reviewed["metrics"]
        if metric["metric_code"] == "revenue_growth_yoy"
        and metric["period_label"] == "FY 2025"
    )
    assert reviewed_growth["value"] == "50.0"
