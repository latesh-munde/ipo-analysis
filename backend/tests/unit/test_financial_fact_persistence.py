import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal

from app.schemas.documents import DocumentMetadata, DocumentStatus
from app.schemas.financial_analysis import (
    AuditStatus,
    EvidenceReference,
    FinancialFactInput,
    FinancialFactStatus,
    FinancialUnit,
    LineItemCode,
    ReportedFinancialFact,
    RestatementStatus,
    StatementBasis,
    StatementType,
)
from app.services.document_repository import DocumentRepository
from app.services.financial_analysis import _fact_id


def make_fact() -> ReportedFinancialFact:
    return ReportedFinancialFact(
        fact_id="fact-1",
        line_item_code=LineItemCode.REVENUE_FROM_OPERATIONS,
        statement_type=StatementType.PROFIT_AND_LOSS,
        period_label="FY 2025",
        period_kind="annual",
        period_start=date(2024, 4, 1),
        period_end=date(2025, 3, 31),
        as_of_date=None,
        statement_basis=StatementBasis.CONSOLIDATED,
        audit_status=AuditStatus.AUDITED,
        restatement_status=RestatementStatus.AS_PUBLISHED,
        currency="INR",
        reported_value=Decimal("100"),
        normalized_value=Decimal("100"),
        reported_unit=FinancialUnit.RUPEES,
        status="reported",
        reason_code=None,
        evidence=EvidenceReference(
            document_id="doc-1",
            source_document_sha256="a" * 64,
            source_table_sha256="b" * 64,
            source_cell_sha256="c" * 64,
            page_number=1,
            table_index=1,
            row_index=1,
            period_header_row_index=0,
            period_header_text="FY 2025",
            label_column_index=0,
            value_column_index=1,
            original_label="Revenue",
            extracted_value="100",
            extraction_method="native_pdf",
            source_warnings=[],
        ),
    )


def make_repository(tmp_path) -> DocumentRepository:
    repository = DocumentRepository(tmp_path / "documents.sqlite3")
    repository.create(
        DocumentMetadata(
            document_id="doc-1",
            original_filename="filing.pdf",
            file_size=1,
            detected_type="application/pdf",
            sha256="a" * 64,
            uploaded_at=datetime.now(UTC),
            document_type="RHP",
            status=DocumentStatus.COMPLETED,
            page_count=1,
            warnings=[],
        ),
        tmp_path / "filing.pdf",
    )
    return repository


def test_financial_fact_versions_are_idempotent_and_history_is_immutable(
    tmp_path,
) -> None:
    repository = make_repository(tmp_path)
    original = make_fact()

    first = repository.save_financial_facts([original])[0]
    repeated = repository.save_financial_facts([original])[0]
    revised_fact = original.model_copy(
        update={
            "line_item_code": LineItemCode.OTHER_INCOME,
            "reported_value": Decimal("125"),
            "normalized_value": Decimal("125"),
            "evidence": original.evidence.model_copy(
                update={
                    "extracted_value": "125",
                    "source_cell_sha256": "d" * 64,
                }
            ),
        }
    )
    second = repository.save_financial_facts([revised_fact])[0]

    assert first.revision == repeated.revision == 1
    assert first.created_at == repeated.created_at
    assert second.revision == 2
    assert second.reported_value == Decimal("125")
    assert repository.get_financial_facts("doc-1") == [second]
    assert repository.get_financial_facts("doc-1", include_history=True) == [
        first,
        second,
    ]


def test_missing_fact_value_remains_unavailable_after_persistence(tmp_path) -> None:
    repository = make_repository(tmp_path)
    missing_fact = make_fact().model_copy(
        update={
            "reported_value": None,
            "normalized_value": None,
            "status": FinancialFactStatus.UNAVAILABLE,
            "reason_code": "MISSING_VALUE",
            "evidence": make_fact().evidence.model_copy(update={"extracted_value": ""}),
        }
    )

    persisted = repository.save_financial_facts([missing_fact])[0]

    assert persisted.reported_value is None
    assert persisted.normalized_value is None
    assert persisted.status == FinancialFactStatus.UNAVAILABLE
    assert persisted.reason_code == "MISSING_VALUE"


def test_repository_migrates_legacy_review_table_with_unbound_reviews(tmp_path) -> None:
    database_path = tmp_path / "documents.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE financial_cell_reviews (
                document_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                table_index INTEGER NOT NULL,
                row_index INTEGER NOT NULL,
                column_index INTEGER NOT NULL,
                source_value TEXT NOT NULL,
                confirmed_value TEXT NOT NULL,
                reviewed_at TEXT NOT NULL,
                PRIMARY KEY (
                    document_id, page_number, table_index, row_index,
                    column_index
                )
            )
            """
        )

    DocumentRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(financial_cell_reviews)")
        }
    assert "source_cell_sha256" in columns


def test_fact_identity_is_stable_when_mapping_metadata_changes() -> None:
    original = FinancialFactInput(
        line_item_code=LineItemCode.REVENUE_FROM_OPERATIONS,
        statement_type=StatementType.PROFIT_AND_LOSS,
        period_label="FY 2025",
        period_kind="annual",
        period_start=date(2024, 4, 1),
        period_end=date(2025, 3, 31),
        statement_basis=StatementBasis.CONSOLIDATED,
        audit_status=AuditStatus.AUDITED,
        restatement_status=RestatementStatus.AS_PUBLISHED,
        currency="INR",
        unit=FinancialUnit.RUPEES,
        page_number=1,
        table_index=1,
        row_index=1,
        period_header_row_index=0,
        label_column_index=0,
        value_column_index=2,
    )
    remapped = FinancialFactInput.model_validate(
        {
            **original.model_dump(mode="json"),
            "line_item_code": LineItemCode.OTHER_INCOME.value,
            "period_label": "FY 2026",
            "period_start": "2025-04-01",
            "period_end": "2026-03-31",
        }
    )

    assert _fact_id("doc-1", original) == _fact_id("doc-1", remapped)
