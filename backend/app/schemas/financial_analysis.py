from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StatementType(StrEnum):
    PROFIT_AND_LOSS = "profit_and_loss"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"


class PeriodKind(StrEnum):
    ANNUAL = "annual"
    INTERIM = "interim"
    QUARTERLY = "quarterly"
    POINT_IN_TIME = "point_in_time"


class StatementBasis(StrEnum):
    CONSOLIDATED = "consolidated"
    STANDALONE = "standalone"
    UNKNOWN = "unknown"


class AuditStatus(StrEnum):
    AUDITED = "audited"
    UNAUDITED = "unaudited"
    UNKNOWN = "unknown"


class RestatementStatus(StrEnum):
    AS_PUBLISHED = "as_published"
    RESTATED = "restated"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class FinancialUnit(StrEnum):
    RUPEES = "rupees"
    THOUSAND_RUPEES = "thousand_rupees"
    LAKH_RUPEES = "lakh_rupees"
    CRORE_RUPEES = "crore_rupees"
    RUPEES_PER_SHARE = "rupees_per_share"


class LineItemCode(StrEnum):
    REVENUE_FROM_OPERATIONS = "revenue_from_operations"
    OTHER_INCOME = "other_income"
    TOTAL_INCOME = "total_income"
    COST_OF_SALES = "cost_of_sales"
    OPERATING_PROFIT = "operating_profit"
    FINANCE_COSTS = "finance_costs"
    DEPRECIATION_AMORTIZATION = "depreciation_amortization"
    PROFIT_BEFORE_TAX = "profit_before_tax"
    TAX_EXPENSE = "tax_expense"
    PROFIT_AFTER_TAX = "profit_after_tax"
    BASIC_EPS = "basic_eps"
    DILUTED_EPS = "diluted_eps"
    CURRENT_ASSETS = "current_assets"
    NON_CURRENT_ASSETS = "non_current_assets"
    INVENTORIES = "inventories"
    TRADE_RECEIVABLES = "trade_receivables"
    OTHER_BANK_BALANCES = "other_bank_balances"
    CASH_AND_EQUIVALENTS = "cash_and_equivalents"
    TOTAL_ASSETS = "total_assets"
    SHARE_CAPITAL = "share_capital"
    RESERVES = "reserves"
    TOTAL_EQUITY = "total_equity"
    TOTAL_LIABILITIES = "total_liabilities"
    CURRENT_LIABILITIES = "current_liabilities"
    NON_CURRENT_LIABILITIES = "non_current_liabilities"
    TRADE_PAYABLES = "trade_payables"
    CURRENT_BORROWINGS = "current_borrowings"
    NON_CURRENT_BORROWINGS = "non_current_borrowings"
    LEASE_LIABILITIES = "lease_liabilities"
    TOTAL_EQUITY_AND_LIABILITIES = "total_equity_and_liabilities"
    CASH_FROM_OPERATING_ACTIVITIES = "cash_from_operating_activities"
    CASH_FROM_INVESTING_ACTIVITIES = "cash_from_investing_activities"
    CASH_FROM_FINANCING_ACTIVITIES = "cash_from_financing_activities"
    CAPITAL_EXPENDITURE = "capital_expenditure"
    NET_CASH_MOVEMENT = "net_cash_movement"
    OPENING_CASH = "opening_cash"
    CLOSING_CASH = "closing_cash"


POINT_IN_TIME_ITEMS = frozenset(
    {
        LineItemCode.CURRENT_ASSETS,
        LineItemCode.NON_CURRENT_ASSETS,
        LineItemCode.INVENTORIES,
        LineItemCode.TRADE_RECEIVABLES,
        LineItemCode.OTHER_BANK_BALANCES,
        LineItemCode.CASH_AND_EQUIVALENTS,
        LineItemCode.TOTAL_ASSETS,
        LineItemCode.SHARE_CAPITAL,
        LineItemCode.RESERVES,
        LineItemCode.TOTAL_EQUITY,
        LineItemCode.TOTAL_LIABILITIES,
        LineItemCode.CURRENT_LIABILITIES,
        LineItemCode.NON_CURRENT_LIABILITIES,
        LineItemCode.TRADE_PAYABLES,
        LineItemCode.CURRENT_BORROWINGS,
        LineItemCode.NON_CURRENT_BORROWINGS,
        LineItemCode.LEASE_LIABILITIES,
        LineItemCode.TOTAL_EQUITY_AND_LIABILITIES,
        LineItemCode.OPENING_CASH,
        LineItemCode.CLOSING_CASH,
    }
)

LINE_ITEM_STATEMENTS = {
    LineItemCode.REVENUE_FROM_OPERATIONS: StatementType.PROFIT_AND_LOSS,
    LineItemCode.OTHER_INCOME: StatementType.PROFIT_AND_LOSS,
    LineItemCode.TOTAL_INCOME: StatementType.PROFIT_AND_LOSS,
    LineItemCode.COST_OF_SALES: StatementType.PROFIT_AND_LOSS,
    LineItemCode.OPERATING_PROFIT: StatementType.PROFIT_AND_LOSS,
    LineItemCode.FINANCE_COSTS: StatementType.PROFIT_AND_LOSS,
    LineItemCode.DEPRECIATION_AMORTIZATION: StatementType.PROFIT_AND_LOSS,
    LineItemCode.PROFIT_BEFORE_TAX: StatementType.PROFIT_AND_LOSS,
    LineItemCode.TAX_EXPENSE: StatementType.PROFIT_AND_LOSS,
    LineItemCode.PROFIT_AFTER_TAX: StatementType.PROFIT_AND_LOSS,
    LineItemCode.BASIC_EPS: StatementType.PROFIT_AND_LOSS,
    LineItemCode.DILUTED_EPS: StatementType.PROFIT_AND_LOSS,
    LineItemCode.CURRENT_ASSETS: StatementType.BALANCE_SHEET,
    LineItemCode.NON_CURRENT_ASSETS: StatementType.BALANCE_SHEET,
    LineItemCode.INVENTORIES: StatementType.BALANCE_SHEET,
    LineItemCode.TRADE_RECEIVABLES: StatementType.BALANCE_SHEET,
    LineItemCode.OTHER_BANK_BALANCES: StatementType.BALANCE_SHEET,
    LineItemCode.CASH_AND_EQUIVALENTS: StatementType.BALANCE_SHEET,
    LineItemCode.TOTAL_ASSETS: StatementType.BALANCE_SHEET,
    LineItemCode.SHARE_CAPITAL: StatementType.BALANCE_SHEET,
    LineItemCode.RESERVES: StatementType.BALANCE_SHEET,
    LineItemCode.TOTAL_EQUITY: StatementType.BALANCE_SHEET,
    LineItemCode.TOTAL_LIABILITIES: StatementType.BALANCE_SHEET,
    LineItemCode.CURRENT_LIABILITIES: StatementType.BALANCE_SHEET,
    LineItemCode.NON_CURRENT_LIABILITIES: StatementType.BALANCE_SHEET,
    LineItemCode.TRADE_PAYABLES: StatementType.BALANCE_SHEET,
    LineItemCode.CURRENT_BORROWINGS: StatementType.BALANCE_SHEET,
    LineItemCode.NON_CURRENT_BORROWINGS: StatementType.BALANCE_SHEET,
    LineItemCode.LEASE_LIABILITIES: StatementType.BALANCE_SHEET,
    LineItemCode.TOTAL_EQUITY_AND_LIABILITIES: StatementType.BALANCE_SHEET,
    LineItemCode.CASH_FROM_OPERATING_ACTIVITIES: StatementType.CASH_FLOW,
    LineItemCode.CASH_FROM_INVESTING_ACTIVITIES: StatementType.CASH_FLOW,
    LineItemCode.CASH_FROM_FINANCING_ACTIVITIES: StatementType.CASH_FLOW,
    LineItemCode.CAPITAL_EXPENDITURE: StatementType.CASH_FLOW,
    LineItemCode.NET_CASH_MOVEMENT: StatementType.CASH_FLOW,
    LineItemCode.OPENING_CASH: StatementType.CASH_FLOW,
    LineItemCode.CLOSING_CASH: StatementType.CASH_FLOW,
}


class FinancialFactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_item_code: LineItemCode
    statement_type: StatementType
    period_label: Annotated[str, Field(min_length=1, max_length=80)]
    period_kind: PeriodKind
    period_start: date | None = None
    period_end: date | None = None
    as_of_date: date | None = None
    statement_basis: StatementBasis
    audit_status: AuditStatus
    restatement_status: RestatementStatus
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$|^UNKNOWN$")] = "UNKNOWN"
    unit: FinancialUnit
    page_number: Annotated[int, Field(ge=1)]
    table_index: Annotated[int, Field(ge=0)]
    row_index: Annotated[int, Field(ge=0)]
    period_header_row_index: Annotated[int, Field(ge=0)]
    label_column_index: Annotated[int, Field(ge=0)]
    value_column_index: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_period_and_statement(self) -> "FinancialFactInput":
        self.period_label = self.period_label.strip()
        if not self.period_label:
            raise ValueError("Period label must not be blank.")
        if self.currency not in {"INR", "UNKNOWN"}:
            raise ValueError(
                "Only INR or explicitly unknown currency is supported; "
                "currency conversion is not performed."
            )
        expected_statement = LINE_ITEM_STATEMENTS[self.line_item_code]
        if self.statement_type != expected_statement:
            raise ValueError(
                f"{self.line_item_code.value} must come from a "
                f"{expected_statement.value} statement."
            )
        eps_items = {LineItemCode.BASIC_EPS, LineItemCode.DILUTED_EPS}
        if self.line_item_code in eps_items:
            if self.unit != FinancialUnit.RUPEES_PER_SHARE:
                raise ValueError("Reported EPS must use rupees_per_share units.")
        elif self.unit == FinancialUnit.RUPEES_PER_SHARE:
            raise ValueError("Rupees-per-share units are only valid for EPS facts.")

        if self.period_kind == PeriodKind.POINT_IN_TIME:
            if self.line_item_code not in POINT_IN_TIME_ITEMS:
                raise ValueError(
                    "Only balance-sheet balances and opening/closing cash "
                    "can use point-in-time periods."
                )
            if self.as_of_date is None or self.period_start or self.period_end:
                raise ValueError(
                    "Point-in-time facts require as_of_date and no flow dates."
                )
        else:
            if self.line_item_code in POINT_IN_TIME_ITEMS:
                raise ValueError("Balance values require a point-in-time period.")
            if (
                self.period_start is None
                or self.period_end is None
                or self.period_start > self.period_end
                or self.as_of_date is not None
            ):
                raise ValueError(
                    "Flow facts require ordered start/end dates and no as_of_date."
                )
        if (
            self.statement_type == StatementType.BALANCE_SHEET
            and self.period_kind != PeriodKind.POINT_IN_TIME
        ):
            raise ValueError("Balance-sheet facts require a point-in-time period.")
        if (
            self.statement_type != StatementType.BALANCE_SHEET
            and self.line_item_code
            not in {LineItemCode.OPENING_CASH, LineItemCode.CLOSING_CASH}
            and self.period_kind == PeriodKind.POINT_IN_TIME
        ):
            raise ValueError("Statement flows require a reporting period.")
        return self


class FinancialAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: Annotated[list[FinancialFactInput], Field(min_length=1, max_length=500)]


class EvidenceReference(BaseModel):
    document_id: str
    page_number: int
    table_index: int
    row_index: int
    period_header_row_index: int
    period_header_text: str
    label_column_index: int
    value_column_index: int
    original_label: str
    extracted_value: str
    extraction_method: str
    source_warnings: list[str]


class ReportedFinancialFact(BaseModel):
    fact_id: str
    line_item_code: LineItemCode
    statement_type: StatementType
    period_label: str
    period_kind: PeriodKind
    period_start: date | None
    period_end: date | None
    as_of_date: date | None
    statement_basis: StatementBasis
    audit_status: AuditStatus
    restatement_status: RestatementStatus
    currency: str
    reported_value: Decimal | None
    normalized_value: Decimal | None
    reported_unit: FinancialUnit
    status: str
    reason_code: str | None
    evidence: EvidenceReference


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationCheckStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAILURE = "failure"
    NOT_CHECKABLE = "not_checkable"


class ValidationFinding(BaseModel):
    finding_id: str
    code: str
    severity: ValidationSeverity
    message: str
    fact_ids: list[str]
    recommended_resolution: str | None = None


class ValidationCheck(BaseModel):
    code: str
    status: ValidationCheckStatus
    message: str
    fact_ids: list[str]
    difference: Decimal | None = None
    tolerance: Decimal | None = None


class MetricStatus(StrEnum):
    CALCULATED = "calculated"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


class FinancialMetric(BaseModel):
    metric_code: str
    display_name: str
    period_label: str
    period_kind: PeriodKind
    period_start: date | None
    period_end: date | None
    as_of_date: date | None
    statement_basis: StatementBasis
    audit_status: AuditStatus
    restatement_status: RestatementStatus
    currency: str | None
    value: Decimal | None
    unit: str
    status: MetricStatus
    reason_code: str | None
    formula: str
    formula_version: str
    input_fact_ids: list[str]
    evidence: list[EvidenceReference]
    finding_codes: list[str]
    finding_ids: list[str]


class FinancialAnalysisReport(BaseModel):
    report_schema_version: str
    formula_set_version: str
    generated_at: datetime
    document_id: str
    document_name: str
    document_type: str | None
    document_sha256: str
    facts: list[ReportedFinancialFact]
    metrics: list[FinancialMetric]
    validation_findings: list[ValidationFinding]
    validation_checks: list[ValidationCheck]
    limitations: list[str]
