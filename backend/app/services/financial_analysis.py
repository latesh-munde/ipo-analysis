import hashlib
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from app.financial.calculations import (
    FORMULA_SET_VERSION,
    REPORT_SCHEMA_VERSION,
    attach_validation_findings,
    calculate_analysis,
    normalize_value,
)
from app.schemas.documents import DocumentMetadata, DocumentStatus, ExtractedTable
from app.schemas.financial_analysis import (
    EvidenceReference,
    FinancialAnalysisReport,
    FinancialAnalysisRequest,
    FinancialFactInput,
    ReportedFinancialFact,
    ValidationFinding,
    ValidationSeverity,
)
from app.services.documents import DocumentService

_AMOUNT = re.compile(
    r"^(?:(?:\d{1,3}(?:,\d{3})+)|(?:\d{1,2}(?:,\d{2})*,\d{3})|\d+)(?:\.\d+)?$"
)
_MISSING_VALUES = {"", "-", "--", "—", "–", "n/a", "na", "not disclosed"}


class FinancialAnalysisInputError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class FinancialAnalysisService:
    def __init__(
        self,
        document_service: DocumentService,
        reconciliation_tolerance: Decimal,
    ) -> None:
        self.document_service = document_service
        self.reconciliation_tolerance = reconciliation_tolerance

    def analyze(
        self,
        document_id: str,
        request: FinancialAnalysisRequest,
    ) -> FinancialAnalysisReport:
        document = self.document_service.get_metadata(document_id)
        if document is None:
            raise FinancialAnalysisInputError(
                404, "DOCUMENT_NOT_FOUND", "The source document was not found."
            )
        if document.status in {DocumentStatus.PROCESSING, DocumentStatus.FAILED}:
            raise FinancialAnalysisInputError(
                409,
                "DOCUMENT_NOT_READY",
                "The source document has no usable completed extraction results.",
            )

        tables = {
            (table.page_number, table.table_index): table
            for table in self.document_service.get_tables(document_id)
        }
        facts = [
            self._fact_from_source(document, source, tables) for source in request.facts
        ]
        metrics, findings, checks = calculate_analysis(
            facts,
            self.reconciliation_tolerance,
        )
        findings.extend(self._source_quality_findings(facts))
        attach_validation_findings(metrics, findings)
        return FinancialAnalysisReport(
            report_schema_version=REPORT_SCHEMA_VERSION,
            formula_set_version=FORMULA_SET_VERSION,
            generated_at=datetime.now(UTC),
            document_id=document.document_id,
            document_name=document.original_filename,
            document_type=document.document_type,
            document_sha256=document.sha256,
            facts=facts,
            metrics=metrics,
            validation_findings=findings,
            validation_checks=checks,
            limitations=[
                "Phase 3 extracts raw table cells only. Line items and periods "
                "must be mapped explicitly; no automatic statement interpretation "
                "or OCR verification is performed.",
                "Only INR amounts with rupees, thousand, lakh, or crore scales "
                "are supported. Currency conversion is not performed.",
                "Lease liabilities are excluded from borrowings unless they are "
                "explicitly mapped as borrowings; EBITDA and investment "
                "recommendations are not calculated.",
                "The report is generated on demand and is not persisted.",
                "Audit and restatement status are user-declared because Phase 3 "
                "does not extract those structured attributes.",
            ],
        )

    def _fact_from_source(
        self,
        document: DocumentMetadata,
        source: FinancialFactInput,
        tables: dict[tuple[int, int], ExtractedTable],
    ) -> ReportedFinancialFact:
        table = tables.get((source.page_number, source.table_index))
        if table is None:
            raise FinancialAnalysisInputError(
                422,
                "SOURCE_TABLE_NOT_FOUND",
                "A selected page and table reference is not present in the document.",
            )
        if source.row_index >= len(table.rows):
            raise FinancialAnalysisInputError(
                422,
                "SOURCE_ROW_NOT_FOUND",
                "A selected row reference is not present in the source table.",
            )
        if source.period_header_row_index >= len(table.rows):
            raise FinancialAnalysisInputError(
                422,
                "SOURCE_PERIOD_HEADER_NOT_FOUND",
                "A selected period-header row is not present in the source table.",
            )
        row = table.rows[source.row_index]
        period_header_row = table.rows[source.period_header_row_index]
        if (
            source.label_column_index >= len(row)
            or source.value_column_index >= len(row)
            or source.value_column_index >= len(period_header_row)
        ):
            raise FinancialAnalysisInputError(
                422,
                "SOURCE_CELL_NOT_FOUND",
                "A selected label or value cell is not present in the source row.",
            )
        if source.label_column_index == source.value_column_index:
            raise FinancialAnalysisInputError(
                422,
                "INVALID_SOURCE_CELLS",
                "The source label and numeric value must use different cells.",
            )

        original_label = row[source.label_column_index]
        extracted_value = row[source.value_column_index]
        fact_id = _fact_id(document.document_id, source)
        evidence = EvidenceReference(
            document_id=document.document_id,
            page_number=table.page_number,
            table_index=table.table_index,
            row_index=source.row_index,
            period_header_row_index=source.period_header_row_index,
            period_header_text=period_header_row[source.value_column_index],
            label_column_index=source.label_column_index,
            value_column_index=source.value_column_index,
            original_label=original_label,
            extracted_value=extracted_value,
            extraction_method=table.extraction_method,
            source_warnings=[
                f"{warning.code}: {warning.message}" for warning in table.warnings
            ],
        )
        reported_value, reason_code = _parse_amount(extracted_value)
        status = "reported" if reported_value is not None else "unavailable"
        if reason_code in {"INVALID_NUMERIC_VALUE", "NUMERIC_VALUE_TOO_LARGE"}:
            status = "rejected"
        normalized_value = (
            normalize_value(reported_value, source.unit.value)
            if reported_value is not None
            else None
        )
        return ReportedFinancialFact(
            fact_id=fact_id,
            line_item_code=source.line_item_code,
            statement_type=source.statement_type,
            period_label=source.period_label.strip(),
            period_kind=source.period_kind,
            period_start=source.period_start,
            period_end=source.period_end,
            as_of_date=source.as_of_date,
            statement_basis=source.statement_basis,
            audit_status=source.audit_status,
            restatement_status=source.restatement_status,
            currency=source.currency,
            reported_value=reported_value,
            normalized_value=normalized_value,
            reported_unit=source.unit,
            status=status,
            reason_code=reason_code,
            evidence=evidence,
        )

    @staticmethod
    def _source_quality_findings(
        facts: list[ReportedFinancialFact],
    ) -> list[ValidationFinding]:
        findings: dict[str, ValidationFinding] = {}
        for fact in facts:
            if fact.evidence.extraction_method == "tesseract_ocr":
                _source_finding(
                    findings,
                    "OCR_SOURCE_REQUIRES_VERIFICATION",
                    "This financial value came from OCR and must be checked against "
                    "the original document.",
                    fact.fact_id,
                )
            if fact.evidence.source_warnings:
                _source_finding(
                    findings,
                    "SOURCE_EXTRACTION_WARNING",
                    "The selected table has extraction warnings: "
                    + ", ".join(fact.evidence.source_warnings),
                    fact.fact_id,
                )
            if not fact.evidence.original_label.strip():
                _source_finding(
                    findings,
                    "SOURCE_LABEL_EMPTY",
                    "The selected financial row has no extracted label text.",
                    fact.fact_id,
                )
            if not fact.evidence.period_header_text.strip():
                _source_finding(
                    findings,
                    "PERIOD_HEADER_EMPTY",
                    "The selected period-header cell is empty; verify the period "
                    "metadata against the source document.",
                    fact.fact_id,
                )
        return list(findings.values())


def _parse_amount(raw_value: str) -> tuple[Decimal | None, str | None]:
    value = raw_value.strip()
    if value.casefold() in _MISSING_VALUES:
        return None, "MISSING_VALUE"

    negative_parentheses = value.startswith("(") and value.endswith(")")
    if negative_parentheses:
        value = value[1:-1].strip()
    value = re.sub(r"^(?:INR|Rs\.?)\s*", "", value, flags=re.IGNORECASE)
    value = value.replace("₹", "").strip()
    if value.endswith("-"):
        return None, "INVALID_NUMERIC_VALUE"
    if value.startswith(("+", "-")):
        sign = value[0]
        value = value[1:]
    else:
        sign = ""
    if sum(character.isdigit() for character in value) > 128:
        return None, "NUMERIC_VALUE_TOO_LARGE"
    if not _AMOUNT.fullmatch(value):
        return None, "INVALID_NUMERIC_VALUE"
    try:
        amount = Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None, "INVALID_NUMERIC_VALUE"
    if not amount.is_finite() or (negative_parentheses and sign):
        return None, "INVALID_NUMERIC_VALUE"
    if negative_parentheses or sign == "-":
        amount = -amount
    return amount, None


def _fact_id(document_id: str, source: FinancialFactInput) -> str:
    source_key = "|".join(
        (
            document_id,
            str(source.page_number),
            str(source.table_index),
            str(source.row_index),
            str(source.period_header_row_index),
            str(source.label_column_index),
            str(source.value_column_index),
            source.line_item_code.value,
            source.period_label,
            source.period_kind.value,
            source.period_start.isoformat() if source.period_start else "",
            source.period_end.isoformat() if source.period_end else "",
            source.as_of_date.isoformat() if source.as_of_date else "",
            source.statement_basis.value,
            source.audit_status.value,
            source.restatement_status.value,
            source.currency,
            source.unit.value,
        )
    )
    return hashlib.sha256(source_key.encode()).hexdigest()[:24]


def _source_finding(
    findings: dict[str, ValidationFinding],
    code: str,
    message: str,
    fact_id: str,
) -> None:
    finding_id = hashlib.sha256(f"{code}:{fact_id}".encode()).hexdigest()[:16]
    findings.setdefault(
        finding_id,
        ValidationFinding(
            finding_id=finding_id,
            code=code,
            severity=ValidationSeverity.WARNING,
            message=message,
            fact_ids=[fact_id],
            recommended_resolution="Compare this table cell with the original PDF.",
        ),
    )
