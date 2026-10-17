import hashlib
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, localcontext

from app.schemas.financial_analysis import (
    FinancialMetric,
    LineItemCode,
    MetricStatus,
    PeriodKind,
    ReportedFinancialFact,
    StatementBasis,
    ValidationCheck,
    ValidationCheckStatus,
    ValidationFinding,
    ValidationSeverity,
)

FORMULA_SET_VERSION = "1.0.0"
REPORT_SCHEMA_VERSION = "1.0.0"
FORMULA_VERSION = "1.0.0"
CROSS_STATEMENT_TOLERANCE = Decimal("1")
DECIMAL_PRECISION = 160

METRIC_DEFINITIONS = {
    "revenue_growth_yoy": (
        "Revenue growth (YoY)",
        "(current revenue - prior comparable revenue) / prior revenue * 100",
        "%",
    ),
    "pat_growth_yoy": (
        "PAT growth (YoY)",
        "percentage change for positive prior PAT; otherwise absolute change "
        "with an explicit loss/zero-baseline status",
        "%",
    ),
    "gross_profit": (
        "Gross profit",
        "revenue from operations - cost of sales",
        "currency",
    ),
    "gross_margin": (
        "Gross margin",
        "(revenue from operations - cost of sales) / revenue * 100",
        "%",
    ),
    "operating_margin": (
        "Operating margin",
        "operating profit / revenue from operations * 100",
        "%",
    ),
    "pbt_margin": (
        "PBT margin",
        "profit before tax / revenue from operations * 100",
        "%",
    ),
    "pat_margin": (
        "PAT margin",
        "profit after tax / revenue from operations * 100",
        "%",
    ),
    "total_borrowings": (
        "Total borrowings",
        "current borrowings + non-current borrowings",
        "currency",
    ),
    "net_debt": (
        "Net debt",
        "total borrowings - cash and cash equivalents",
        "currency",
    ),
    "debt_to_equity": (
        "Debt-to-equity",
        "total borrowings / total equity",
        "x",
    ),
    "debt_to_assets": (
        "Debt-to-assets",
        "total borrowings / total assets",
        "x",
    ),
    "interest_coverage": (
        "Interest coverage",
        "operating profit / finance costs",
        "x",
    ),
    "current_ratio": (
        "Current ratio",
        "current assets / current liabilities",
        "x",
    ),
    "quick_ratio": (
        "Quick ratio",
        "(cash and equivalents + trade receivables) / current liabilities",
        "x",
    ),
    "working_capital": (
        "Working capital",
        "current assets - current liabilities",
        "currency",
    ),
    "cfo_margin": (
        "CFO margin",
        "cash from operating activities / revenue from operations * 100",
        "%",
    ),
    "free_cash_flow": (
        "Free cash flow",
        "cash from operating activities - capital expenditure",
        "currency",
    ),
    "net_cash_movement": (
        "Net cash movement",
        "cash from operating activities + cash from investing activities "
        "+ cash from financing activities",
        "currency",
    ),
    "return_on_assets": (
        "Return on assets",
        "profit after tax / average of opening and closing total assets * 100",
        "%",
    ),
    "return_on_equity": (
        "Return on equity",
        "profit after tax / average of opening and closing total equity * 100",
        "%",
    ),
    "basic_eps": (
        "Basic EPS",
        "reported basic earnings per share; not reconstructed",
        "INR/share",
    ),
    "diluted_eps": (
        "Diluted EPS",
        "reported diluted earnings per share; not reconstructed",
        "INR/share",
    ),
}

_SCALE_FACTORS = {
    "rupees": Decimal(1),
    "thousand_rupees": Decimal(1_000),
    "lakh_rupees": Decimal(100_000),
    "crore_rupees": Decimal(10_000_000),
    "rupees_per_share": Decimal(1),
}


def normalize_value(value: Decimal, unit: str) -> Decimal:
    """Convert an explicitly declared INR scale to rupees without rounding."""
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        return value * _SCALE_FACTORS[unit]


def _blocking_input_reason(reason: str | None) -> bool:
    return reason in {
        "AMBIGUOUS_INPUT",
        "INVALID_NUMERIC_VALUE",
        "NUMERIC_VALUE_TOO_LARGE",
        "NEGATIVE_BASELINE",
    }


def calculate_analysis(
    facts: list[ReportedFinancialFact],
    reconciliation_tolerance: Decimal = CROSS_STATEMENT_TOLERANCE,
) -> tuple[list[FinancialMetric], list[ValidationFinding], list[ValidationCheck]]:
    """Calculate deterministic metrics from normalized source facts."""
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        ordered_facts = sorted(facts, key=lambda item: item.fact_id)
        return _calculate_analysis(ordered_facts, reconciliation_tolerance)


def _calculate_analysis(
    facts: list[ReportedFinancialFact],
    reconciliation_tolerance: Decimal,
) -> tuple[list[FinancialMetric], list[ValidationFinding], list[ValidationCheck]]:
    findings: dict[str, ValidationFinding] = {}
    checks: list[ValidationCheck] = []
    contexts: dict[tuple, list[ReportedFinancialFact]] = defaultdict(list)
    for fact in sorted(facts, key=lambda item: item.fact_id):
        contexts[_scope_key(fact)].append(fact)
        if fact.statement_basis == StatementBasis.UNKNOWN:
            _add_finding(
                findings,
                "UNKNOWN_STATEMENT_BASIS",
                ValidationSeverity.WARNING,
                "Statement basis is unknown; no standalone/consolidated "
                "combination was performed.",
                [fact.fact_id],
            )
        if fact.audit_status.value == "unknown":
            _add_finding(
                findings,
                "UNKNOWN_AUDIT_STATUS",
                ValidationSeverity.WARNING,
                "Audit status is unknown; no assurance level is implied.",
                [fact.fact_id],
            )
        if fact.restatement_status.value == "unknown":
            _add_finding(
                findings,
                "UNKNOWN_RESTATEMENT_STATUS",
                ValidationSeverity.WARNING,
                "Restatement status is unknown; no restatement was inferred.",
                [fact.fact_id],
            )
        if fact.currency == "UNKNOWN":
            _add_finding(
                findings,
                "UNKNOWN_CURRENCY",
                ValidationSeverity.WARNING,
                "Currency is not identified; results are not currency-comparable.",
                [fact.fact_id],
            )
        if fact.status == "rejected":
            _add_finding(
                findings,
                fact.reason_code or "INVALID_REPORTED_VALUE",
                ValidationSeverity.ERROR,
                "The selected source cell could not be used as a financial value.",
                [fact.fact_id],
            )
        elif fact.status == "unavailable":
            _add_finding(
                findings,
                fact.reason_code or "SOURCE_VALUE_UNAVAILABLE",
                ValidationSeverity.INFO,
                "The selected source cell is blank or explicitly not disclosed.",
                [fact.fact_id],
            )

    for group in contexts.values():
        period_labels = {fact.period_label for fact in group}
        if len(period_labels) > 1:
            _add_finding(
                findings,
                "PERIOD_LABEL_CONFLICT",
                ValidationSeverity.WARNING,
                "Facts with identical dates use different period labels; dates "
                "remain the calculation scope.",
                [fact.fact_id for fact in group],
            )
    _detect_conflicts(contexts, findings)
    _run_reconciliations(
        facts,
        contexts,
        findings,
        checks,
        reconciliation_tolerance,
    )

    metrics: list[FinancialMetric] = []
    for context_key, context_facts in sorted(
        contexts.items(),
        key=lambda item: tuple(str(part) for part in item[0]),
    ):
        metrics.extend(_period_metrics(context_facts, context_key, findings))

    _append_revenue_growth(contexts, metrics, findings)
    _append_profit_growth(contexts, metrics, findings)
    _append_return_metrics(contexts, metrics, findings)
    validation_findings = sorted(
        findings.values(),
        key=lambda item: (item.code, item.fact_ids, item.finding_id),
    )
    attach_validation_findings(metrics, validation_findings)
    return metrics, validation_findings, checks


def attach_validation_findings(
    metrics: list[FinancialMetric],
    findings: list[ValidationFinding],
) -> None:
    for metric in metrics:
        input_ids = set(metric.input_fact_ids)
        related = [
            finding
            for finding in findings
            if input_ids.intersection(finding.fact_ids)
            or (not finding.fact_ids and finding.code in metric.finding_codes)
        ]
        metric.finding_ids = [finding.finding_id for finding in related]
        metric.finding_codes = list(
            dict.fromkeys(metric.finding_codes + [finding.code for finding in related])
        )


def _scope_key(fact: ReportedFinancialFact) -> tuple:
    return (
        fact.period_kind.value,
        fact.period_start,
        fact.period_end,
        fact.as_of_date,
        fact.statement_basis.value,
        fact.currency,
        fact.audit_status.value,
        fact.restatement_status.value,
    )


def _detect_conflicts(
    contexts: dict[tuple, list[ReportedFinancialFact]],
    findings: dict[str, ValidationFinding],
) -> None:
    for group in contexts.values():
        by_code: dict[LineItemCode, list[ReportedFinancialFact]] = defaultdict(list)
        for fact in group:
            by_code[fact.line_item_code].append(fact)
        for same_item in by_code.values():
            usable = [
                fact
                for fact in same_item
                if fact.status == "reported" and fact.normalized_value is not None
            ]
            values = {fact.normalized_value for fact in usable}
            if len(values) > 1:
                _add_finding(
                    findings,
                    "CONFLICTING_FACTS",
                    ValidationSeverity.ERROR,
                    "Conflicting reported values exist for the same line item "
                    "and period; affected metrics are blocked.",
                    [fact.fact_id for fact in usable],
                    "Review the source cells and explicitly resolve the conflicting "
                    "disclosure before relying on affected metrics.",
                )


def _period_metrics(
    facts: list[ReportedFinancialFact],
    context_key: tuple,
    findings: dict[str, ValidationFinding],
) -> list[FinancialMetric]:
    basis = StatementBasis(context_key[4])
    currency = context_key[5]
    reference = facts[0]
    flow = reference.period_kind != PeriodKind.POINT_IN_TIME
    if not flow and not any(
        fact.statement_type.value == "balance_sheet" for fact in facts
    ):
        return []
    metric_codes = (
        [
            "gross_profit",
            "gross_margin",
            "operating_margin",
            "pbt_margin",
            "pat_margin",
            "interest_coverage",
            "cfo_margin",
            "free_cash_flow",
            "net_cash_movement",
            "basic_eps",
            "diluted_eps",
        ]
        if flow
        else [
            "total_borrowings",
            "net_debt",
            "debt_to_equity",
            "debt_to_assets",
            "current_ratio",
            "quick_ratio",
            "working_capital",
        ]
    )
    metrics: list[FinancialMetric] = []
    for code in metric_codes:
        metric = _calculate_metric(code, facts, reference, basis, currency, findings)
        metrics.append(metric)
    return metrics


def _calculate_metric(
    code: str,
    facts: list[ReportedFinancialFact],
    period: ReportedFinancialFact,
    basis: StatementBasis,
    currency: str,
    findings: dict[str, ValidationFinding],
) -> FinancialMetric:
    input_codes: dict[str, tuple[LineItemCode, ...]] = {
        "gross_profit": (
            LineItemCode.REVENUE_FROM_OPERATIONS,
            LineItemCode.COST_OF_SALES,
        ),
        "gross_margin": (
            LineItemCode.REVENUE_FROM_OPERATIONS,
            LineItemCode.COST_OF_SALES,
        ),
        "operating_margin": (
            LineItemCode.OPERATING_PROFIT,
            LineItemCode.REVENUE_FROM_OPERATIONS,
        ),
        "pbt_margin": (
            LineItemCode.PROFIT_BEFORE_TAX,
            LineItemCode.REVENUE_FROM_OPERATIONS,
        ),
        "pat_margin": (
            LineItemCode.PROFIT_AFTER_TAX,
            LineItemCode.REVENUE_FROM_OPERATIONS,
        ),
        "total_borrowings": (
            LineItemCode.CURRENT_BORROWINGS,
            LineItemCode.NON_CURRENT_BORROWINGS,
        ),
        "net_debt": (
            LineItemCode.CURRENT_BORROWINGS,
            LineItemCode.NON_CURRENT_BORROWINGS,
            LineItemCode.CASH_AND_EQUIVALENTS,
        ),
        "debt_to_equity": (
            LineItemCode.CURRENT_BORROWINGS,
            LineItemCode.NON_CURRENT_BORROWINGS,
            LineItemCode.TOTAL_EQUITY,
        ),
        "debt_to_assets": (
            LineItemCode.CURRENT_BORROWINGS,
            LineItemCode.NON_CURRENT_BORROWINGS,
            LineItemCode.TOTAL_ASSETS,
        ),
        "interest_coverage": (
            LineItemCode.OPERATING_PROFIT,
            LineItemCode.FINANCE_COSTS,
        ),
        "current_ratio": (
            LineItemCode.CURRENT_ASSETS,
            LineItemCode.CURRENT_LIABILITIES,
        ),
        "quick_ratio": (
            LineItemCode.CASH_AND_EQUIVALENTS,
            LineItemCode.TRADE_RECEIVABLES,
            LineItemCode.CURRENT_LIABILITIES,
        ),
        "working_capital": (
            LineItemCode.CURRENT_ASSETS,
            LineItemCode.CURRENT_LIABILITIES,
        ),
        "cfo_margin": (
            LineItemCode.CASH_FROM_OPERATING_ACTIVITIES,
            LineItemCode.REVENUE_FROM_OPERATIONS,
        ),
        "free_cash_flow": (
            LineItemCode.CASH_FROM_OPERATING_ACTIVITIES,
            LineItemCode.CAPITAL_EXPENDITURE,
        ),
        "net_cash_movement": (
            LineItemCode.CASH_FROM_OPERATING_ACTIVITIES,
            LineItemCode.CASH_FROM_INVESTING_ACTIVITIES,
            LineItemCode.CASH_FROM_FINANCING_ACTIVITIES,
        ),
        "basic_eps": (LineItemCode.BASIC_EPS,),
        "diluted_eps": (LineItemCode.DILUTED_EPS,),
    }
    name, formula, unit = METRIC_DEFINITIONS[code]
    values, input_facts, reason = _get_inputs(facts, input_codes[code])
    status = MetricStatus.CALCULATED
    value: Decimal | None = None
    related_codes: list[str] = []

    if reason:
        status = (
            MetricStatus.BLOCKED
            if _blocking_input_reason(reason)
            else MetricStatus.UNAVAILABLE
        )
        related_codes.append(reason)
    else:
        assert values is not None
        if code == "gross_profit":
            revenue, cost = values
            if cost < 0:
                status, reason = MetricStatus.BLOCKED, "NEGATIVE_EXPENSE_SIGN"
            else:
                value = revenue - cost
        elif code == "gross_margin":
            revenue, cost = values
            if cost < 0:
                status, reason = MetricStatus.BLOCKED, "NEGATIVE_EXPENSE_SIGN"
            else:
                value, status, reason = _divide((revenue - cost) * 100, revenue)
        elif code in {"operating_margin", "pbt_margin", "pat_margin", "cfo_margin"}:
            numerator, denominator = values
            value, status, reason = _divide(numerator * 100, denominator)
        elif code == "total_borrowings":
            current, non_current = values
            if current < 0 or non_current < 0:
                status, reason = MetricStatus.BLOCKED, "NEGATIVE_BORROWINGS"
            else:
                value = current + non_current
        elif code == "net_debt":
            current, non_current, cash = values
            if current < 0 or non_current < 0 or cash < 0:
                status, reason = MetricStatus.BLOCKED, "INVALID_DEBT_OR_CASH_SIGN"
            else:
                value = current + non_current - cash
        elif code in {"debt_to_equity", "debt_to_assets"}:
            debt_parts = values[:-1]
            denominator = values[-1]
            if any(part < 0 for part in debt_parts):
                status, reason = MetricStatus.BLOCKED, "NEGATIVE_BORROWINGS"
            elif code == "debt_to_equity" and denominator <= 0:
                status, reason = MetricStatus.BLOCKED, "NON_POSITIVE_EQUITY"
            elif code == "debt_to_assets" and denominator <= 0:
                status, reason = MetricStatus.BLOCKED, "NON_POSITIVE_ASSETS"
            else:
                value = sum(debt_parts, Decimal(0)) / denominator
        elif code == "interest_coverage":
            operating_profit, finance_costs = values
            if finance_costs < 0:
                status, reason = MetricStatus.BLOCKED, "NEGATIVE_FINANCE_COST_SIGN"
            else:
                value, status, reason = _divide(operating_profit, finance_costs)
        elif code == "current_ratio":
            assets, liabilities = values
            if assets < 0:
                status, reason = MetricStatus.BLOCKED, "NEGATIVE_CURRENT_ASSETS"
            else:
                value, status, reason = _divide(assets, liabilities)
        elif code == "quick_ratio":
            cash, receivables, liabilities = values
            if cash < 0 or receivables < 0:
                status, reason = MetricStatus.BLOCKED, "NEGATIVE_QUICK_ASSETS"
            else:
                value, status, reason = _divide(cash + receivables, liabilities)
        elif code == "working_capital":
            assets, liabilities = values
            value = assets - liabilities
        elif code == "free_cash_flow":
            cfo, capex = values
            if capex < 0:
                status, reason = MetricStatus.BLOCKED, "NEGATIVE_CAPEX_SIGN"
            else:
                value = cfo - capex
        elif code == "net_cash_movement":
            value = sum(values, Decimal(0))
        elif code in {"basic_eps", "diluted_eps"}:
            value = values[0]

        if reason:
            related_codes.append(reason)
    if reason:
        _add_finding(
            findings,
            reason,
            ValidationSeverity.ERROR
            if status == MetricStatus.BLOCKED
            else ValidationSeverity.INFO,
            _reason_message(reason),
            [fact.fact_id for fact in input_facts],
        )
        related_codes.append(reason)

    return _metric(
        code,
        name,
        formula,
        unit,
        value,
        status,
        reason,
        period,
        basis,
        currency,
        input_facts,
        related_codes,
    )


def _get_inputs(
    facts: list[ReportedFinancialFact],
    codes: tuple[LineItemCode, ...],
) -> tuple[list[Decimal] | None, list[ReportedFinancialFact], str | None]:
    values: list[Decimal] = []
    used: list[ReportedFinancialFact] = []
    reason: str | None = None
    for code in codes:
        candidates = [fact for fact in facts if fact.line_item_code == code]
        usable = [
            fact
            for fact in candidates
            if fact.status == "reported" and fact.normalized_value is not None
        ]
        if not usable:
            used.extend(candidates)
            reason = reason or (
                (candidates[0].reason_code or "MISSING_VALUE")
                if candidates
                else "MISSING_INPUT"
            )
            continue
        unique_values = {fact.normalized_value for fact in usable}
        used.extend(usable)
        if len(unique_values) > 1:
            reason = reason or "AMBIGUOUS_INPUT"
            continue
        usable.sort(key=lambda fact: fact.fact_id)
        values.append(usable[0].normalized_value)
    if reason:
        return None, used, reason
    return values, used, None


def _divide(
    numerator: Decimal,
    denominator: Decimal,
) -> tuple[Decimal | None, MetricStatus, str | None]:
    if denominator == 0:
        return None, MetricStatus.UNAVAILABLE, "ZERO_DENOMINATOR"
    if denominator < 0:
        return None, MetricStatus.BLOCKED, "NEGATIVE_DENOMINATOR"
    return numerator / denominator, MetricStatus.CALCULATED, None


def _append_revenue_growth(
    contexts: dict[tuple, list[ReportedFinancialFact]],
    metrics: list[FinancialMetric],
    findings: dict[str, ValidationFinding],
) -> None:
    annual_contexts = [
        (key, facts)
        for key, facts in contexts.items()
        if key[0] != PeriodKind.POINT_IN_TIME.value
        and any(fact.statement_type.value == "profit_and_loss" for fact in facts)
    ]
    for current_key, current_facts in annual_contexts:
        current = current_facts[0]
        input_facts: list[ReportedFinancialFact] = []
        reason: str | None = None
        value: Decimal | None = None
        status = MetricStatus.UNAVAILABLE
        related_codes: list[str] = []
        current_value, current_inputs, current_reason = _get_inputs(
            current_facts,
            (LineItemCode.REVENUE_FROM_OPERATIONS,),
        )
        input_facts.extend(current_inputs)
        if current_reason:
            reason = current_reason
        elif current.period_kind not in {
            PeriodKind.ANNUAL,
            PeriodKind.INTERIM,
            PeriodKind.QUARTERLY,
        }:
            reason = "INCOMPATIBLE_PERIOD_KIND"
        else:
            _, prior_facts = _find_prior_period(current_key, annual_contexts)
            if prior_facts is None:
                reason = "NO_COMPARABLE_PERIOD"
            else:
                prior_value, prior_inputs, prior_reason = _get_inputs(
                    prior_facts,
                    (LineItemCode.REVENUE_FROM_OPERATIONS,),
                )
                input_facts.extend(prior_inputs)
                if prior_reason:
                    reason = prior_reason
                elif current_value is not None and prior_value is not None:
                    if prior_value[0] == 0:
                        reason = "ZERO_BASELINE"
                    elif prior_value[0] < 0:
                        reason = "NEGATIVE_BASELINE"
                    else:
                        value = (
                            (current_value[0] - prior_value[0]) / prior_value[0] * 100
                        )
                        status = MetricStatus.CALCULATED

        if reason:
            related_codes.append(reason)
            _add_finding(
                findings,
                reason,
                ValidationSeverity.INFO
                if reason in {"NO_COMPARABLE_PERIOD", "MISSING_INPUT", "ZERO_BASELINE"}
                else ValidationSeverity.ERROR,
                _reason_message(reason),
                [fact.fact_id for fact in input_facts],
            )
        if _blocking_input_reason(reason):
            status = MetricStatus.BLOCKED
        metrics.append(
            _metric(
                "revenue_growth_yoy",
                METRIC_DEFINITIONS["revenue_growth_yoy"][0],
                METRIC_DEFINITIONS["revenue_growth_yoy"][1],
                "%",
                value,
                status,
                reason,
                current,
                StatementBasis(current_key[4]),
                current_key[5],
                input_facts,
                related_codes,
            )
        )


def _append_profit_growth(
    contexts: dict[tuple, list[ReportedFinancialFact]],
    metrics: list[FinancialMetric],
    findings: dict[str, ValidationFinding],
) -> None:
    flow_contexts = [
        (key, facts)
        for key, facts in contexts.items()
        if key[0] != PeriodKind.POINT_IN_TIME.value
        and any(fact.statement_type.value == "profit_and_loss" for fact in facts)
    ]
    for current_key, current_facts in flow_contexts:
        current = current_facts[0]
        current_values, current_inputs, reason = _get_inputs(
            current_facts,
            (LineItemCode.PROFIT_AFTER_TAX,),
        )
        input_facts = list(current_inputs)
        previous_values: list[Decimal] | None = None
        if reason is None:
            _, previous_facts = _find_prior_period(current_key, flow_contexts)
            if previous_facts is None:
                reason = "NO_COMPARABLE_PERIOD"
            else:
                previous_values, previous_inputs, reason = _get_inputs(
                    previous_facts,
                    (LineItemCode.PROFIT_AFTER_TAX,),
                )
                input_facts.extend(previous_inputs)

        value: Decimal | None = None
        status = MetricStatus.UNAVAILABLE
        unit = "%"
        if (
            reason is None
            and current_values is not None
            and previous_values is not None
        ):
            current_profit = current_values[0]
            previous_profit = previous_values[0]
            if previous_profit <= 0 or current_profit < 0:
                value = current_profit - previous_profit
                unit = current.currency
                status = MetricStatus.CALCULATED
                if previous_profit < 0 < current_profit:
                    reason = "LOSS_TO_PROFIT"
                elif previous_profit < 0 and current_profit == 0:
                    reason = "LOSS_TO_BREAK_EVEN"
                elif previous_profit < 0:
                    reason = "LOSS_CONTINUES"
                elif current_profit < 0:
                    reason = "PROFIT_TO_LOSS"
                else:
                    reason = "ZERO_BASELINE_ABSOLUTE_CHANGE"
            else:
                value = (current_profit - previous_profit) / previous_profit * 100
                status = MetricStatus.CALCULATED

        related_codes: list[str] = []
        if reason:
            related_codes.append(reason)
            _add_finding(
                findings,
                reason,
                ValidationSeverity.WARNING
                if status == MetricStatus.CALCULATED
                else ValidationSeverity.INFO,
                _reason_message(reason),
                [fact.fact_id for fact in input_facts],
            )
        if _blocking_input_reason(reason):
            status = MetricStatus.BLOCKED
        metrics.append(
            _metric(
                "pat_growth_yoy",
                METRIC_DEFINITIONS["pat_growth_yoy"][0],
                METRIC_DEFINITIONS["pat_growth_yoy"][1],
                unit,
                value,
                status,
                reason,
                current,
                StatementBasis(current_key[4]),
                current_key[5],
                input_facts,
                related_codes,
            )
        )


def _append_return_metrics(
    contexts: dict[tuple, list[ReportedFinancialFact]],
    metrics: list[FinancialMetric],
    findings: dict[str, ValidationFinding],
) -> None:
    flow_contexts = [
        (key, facts)
        for key, facts in contexts.items()
        if key[0] != PeriodKind.POINT_IN_TIME.value
        and any(fact.statement_type.value == "profit_and_loss" for fact in facts)
    ]
    for period_key, period_facts in flow_contexts:
        period = period_facts[0]
        for code, balance_code, invalid_reason in (
            (
                "return_on_assets",
                LineItemCode.TOTAL_ASSETS,
                "NON_POSITIVE_ASSETS",
            ),
            (
                "return_on_equity",
                LineItemCode.TOTAL_EQUITY,
                "NON_POSITIVE_EQUITY",
            ),
        ):
            input_facts: list[ReportedFinancialFact] = []
            profit, profit_facts, reason = _get_inputs(
                period_facts,
                (LineItemCode.PROFIT_AFTER_TAX,),
            )
            input_facts.extend(profit_facts)
            opening: list[Decimal] | None = None
            closing: list[Decimal] | None = None
            if period.period_start is None or period.period_end is None:
                reason = reason or "MISSING_INPUT"
            else:
                opening, opening_facts, opening_reason = _point_in_time_input(
                    contexts,
                    period_key,
                    balance_code,
                    period.period_start - timedelta(days=1),
                )
                closing, closing_facts, closing_reason = _point_in_time_input(
                    contexts,
                    period_key,
                    balance_code,
                    period.period_end,
                )
                input_facts.extend(opening_facts + closing_facts)
                reason = reason or opening_reason or closing_reason

            value: Decimal | None = None
            status = MetricStatus.UNAVAILABLE
            if (
                reason is None
                and profit is not None
                and opening is not None
                and closing is not None
            ):
                if opening[0] <= 0 or closing[0] <= 0:
                    status, reason = MetricStatus.BLOCKED, invalid_reason
                else:
                    average_balance = (opening[0] + closing[0]) / 2
                    value, status, reason = _divide(
                        profit[0] * 100,
                        average_balance,
                    )
            if _blocking_input_reason(reason):
                status = MetricStatus.BLOCKED

            related_codes: list[str] = []
            if reason:
                related_codes.append(reason)
                _add_finding(
                    findings,
                    reason,
                    ValidationSeverity.ERROR
                    if status == MetricStatus.BLOCKED
                    else ValidationSeverity.INFO,
                    _reason_message(reason),
                    [fact.fact_id for fact in input_facts],
                )
            metrics.append(
                _metric(
                    code,
                    METRIC_DEFINITIONS[code][0],
                    METRIC_DEFINITIONS[code][1],
                    "%",
                    value,
                    status,
                    reason,
                    period,
                    StatementBasis(period_key[4]),
                    period_key[5],
                    input_facts,
                    related_codes,
                )
            )


def _point_in_time_input(
    contexts: dict[tuple, list[ReportedFinancialFact]],
    period_key: tuple,
    code: LineItemCode,
    as_of_date: date,
) -> tuple[list[Decimal] | None, list[ReportedFinancialFact], str | None]:
    matching_facts = [
        fact
        for key, facts in contexts.items()
        if key[0] == PeriodKind.POINT_IN_TIME.value
        and key[3] == as_of_date
        and key[4:] == period_key[4:]
        for fact in facts
        if fact.line_item_code == code
    ]
    return _get_inputs(matching_facts, (code,))


def _find_prior_period(
    current_key: tuple,
    contexts: list[tuple[tuple, list[ReportedFinancialFact]]],
) -> tuple[tuple | None, list[ReportedFinancialFact] | None]:
    _, start, end, _, basis, currency, audit_status, restatement_status = current_key
    if start is None or end is None:
        return None, None
    current_duration = (end - start).days
    for key, facts in contexts:
        (
            _,
            prior_start,
            prior_end,
            _,
            prior_basis,
            prior_currency,
            prior_audit_status,
            prior_restatement_status,
        ) = key
        if (
            prior_start is None
            or prior_end is None
            or key[0] != current_key[0]
            or prior_basis != basis
            or prior_currency != currency
            or prior_audit_status != audit_status
            or prior_restatement_status != restatement_status
        ):
            continue
        if (
            prior_start.month == start.month
            and prior_start.day == start.day
            and prior_start.year == start.year - 1
            and prior_end.month == end.month
            and prior_end.day == end.day
            and abs((prior_end - prior_start).days - current_duration) <= 1
        ):
            return key, facts
    return None, None


def _run_reconciliations(
    facts: list[ReportedFinancialFact],
    contexts: dict[tuple, list[ReportedFinancialFact]],
    findings: dict[str, ValidationFinding],
    checks: list[ValidationCheck],
    tolerance: Decimal,
) -> None:
    for group in contexts.values():
        if group[0].period_kind == PeriodKind.POINT_IN_TIME and any(
            fact.statement_type.value == "balance_sheet" for fact in group
        ):
            _balance_sheet_check(group, findings, checks, tolerance)
    _cash_flow_checks(facts, contexts, findings, checks, tolerance)


def _balance_sheet_check(
    facts: list[ReportedFinancialFact],
    findings: dict[str, ValidationFinding],
    checks: list[ValidationCheck],
    tolerance: Decimal,
) -> None:
    assets, asset_facts, _ = _get_inputs(facts, (LineItemCode.TOTAL_ASSETS,))
    equity, equity_facts, _ = _get_inputs(facts, (LineItemCode.TOTAL_EQUITY,))
    liabilities, liability_facts, _ = _get_inputs(
        facts, (LineItemCode.TOTAL_LIABILITIES,)
    )
    total_e_and_l, total_facts, _ = _get_inputs(
        facts, (LineItemCode.TOTAL_EQUITY_AND_LIABILITIES,)
    )
    available_inputs = asset_facts + equity_facts + liability_facts + total_facts
    if assets is None or (
        total_e_and_l is None and (equity is None or liabilities is None)
    ):
        checks.append(
            ValidationCheck(
                code="BALANCE_SHEET_EQUATION",
                status=ValidationCheckStatus.NOT_CHECKABLE,
                message=(
                    "Total assets and a compatible equity/liabilities total "
                    "are required."
                ),
                fact_ids=[fact.fact_id for fact in available_inputs],
            )
        )
        return
    lhs = assets[0]
    if equity is not None and liabilities is not None:
        rhs = equity[0] + liabilities[0]
        used = asset_facts + equity_facts + liability_facts
    else:
        rhs = total_e_and_l[0]
        used = asset_facts + total_facts
    difference = abs(lhs - rhs)
    status = _reconciliation_status(difference, tolerance)
    checks.append(
        ValidationCheck(
            code="BALANCE_SHEET_EQUATION",
            status=status,
            message="Total assets compared with total equity and liabilities.",
            fact_ids=[fact.fact_id for fact in used],
            difference=difference,
            tolerance=tolerance,
        )
    )
    if status != ValidationCheckStatus.PASS:
        code = "BALANCE_SHEET_MISMATCH"
        _add_finding(
            findings,
            code,
            ValidationSeverity.ERROR
            if status == ValidationCheckStatus.FAILURE
            else ValidationSeverity.WARNING,
            "Total assets do not reconcile to total equity and liabilities "
            "within the documented tolerance.",
            [fact.fact_id for fact in used],
            "Review the statement totals, units, periods, and extraction cells.",
        )


def _cash_flow_checks(
    facts: list[ReportedFinancialFact],
    contexts: dict[tuple, list[ReportedFinancialFact]],
    findings: dict[str, ValidationFinding],
    checks: list[ValidationCheck],
    tolerance: Decimal,
) -> None:
    flow_contexts = [
        (key, group)
        for key, group in contexts.items()
        if key[0] != PeriodKind.POINT_IN_TIME.value
        and any(fact.statement_type.value == "cash_flow" for fact in group)
    ]
    for key, group in flow_contexts:
        movement, movement_inputs, _ = _get_inputs(
            group,
            (
                LineItemCode.CASH_FROM_OPERATING_ACTIVITIES,
                LineItemCode.CASH_FROM_INVESTING_ACTIVITIES,
                LineItemCode.CASH_FROM_FINANCING_ACTIVITIES,
            ),
        )
        if movement is None:
            calculated_movement = None
        else:
            calculated_movement = sum(movement, Decimal(0))
        reported_movement, reported_inputs, _ = _get_inputs(
            group, (LineItemCode.NET_CASH_MOVEMENT,)
        )
        if calculated_movement is None or reported_movement is None:
            checks.append(
                ValidationCheck(
                    code="CASH_FLOW_MOVEMENT",
                    status=ValidationCheckStatus.NOT_CHECKABLE,
                    message=(
                        "CFO, CFI, CFF, and reported net movement are required "
                        "to reconcile cash flows."
                    ),
                    fact_ids=[fact.fact_id for fact in movement_inputs],
                )
            )
        else:
            difference = abs(calculated_movement - reported_movement[0])
            status = _reconciliation_status(difference, tolerance)
            checks.append(
                ValidationCheck(
                    code="CASH_FLOW_MOVEMENT",
                    status=status,
                    message=(
                        "CFO, CFI, and CFF compared with reported net cash movement."
                    ),
                    fact_ids=[
                        fact.fact_id for fact in movement_inputs + reported_inputs
                    ],
                    difference=difference,
                    tolerance=tolerance,
                )
            )
            if status != ValidationCheckStatus.PASS:
                _add_finding(
                    findings,
                    "CASH_FLOW_MOVEMENT_MISMATCH",
                    ValidationSeverity.ERROR
                    if status == ValidationCheckStatus.FAILURE
                    else ValidationSeverity.WARNING,
                    "CFO, CFI, and CFF do not reconcile to reported net cash movement.",
                    [fact.fact_id for fact in movement_inputs + reported_inputs],
                    "Review the cash-flow cells, signs, units, and reporting period.",
                )

        start = key[1]
        end = key[2]
        if start is None or end is None:
            continue
        opening, opening_facts = _point_cash(
            facts, key, LineItemCode.OPENING_CASH, start
        )
        closing, closing_facts = _point_cash(facts, key, LineItemCode.CLOSING_CASH, end)
        net_movement = (
            calculated_movement
            if calculated_movement is not None
            else reported_movement[0]
            if reported_movement is not None
            else None
        )
        if opening is None or closing is None or net_movement is None:
            checks.append(
                ValidationCheck(
                    code="CASH_BALANCE_RECONCILIATION",
                    status=ValidationCheckStatus.NOT_CHECKABLE,
                    message=(
                        "Opening cash, closing cash, and net cash movement "
                        "are required."
                    ),
                    fact_ids=[fact.fact_id for fact in opening_facts + closing_facts],
                )
            )
            continue
        calculated_closing = opening.normalized_value + net_movement
        difference = abs(calculated_closing - closing.normalized_value)
        status = _reconciliation_status(difference, tolerance)
        movement_facts = (
            movement_inputs if calculated_movement is not None else reported_inputs
        )
        involved = movement_facts + opening_facts + closing_facts
        checks.append(
            ValidationCheck(
                code="CASH_BALANCE_RECONCILIATION",
                status=status,
                message=(
                    "Opening cash plus net cash movement compared with closing cash."
                ),
                fact_ids=[fact.fact_id for fact in involved],
                difference=difference,
                tolerance=tolerance,
            )
        )
        if status != ValidationCheckStatus.PASS:
            _add_finding(
                findings,
                "CASH_BALANCE_MISMATCH",
                ValidationSeverity.ERROR
                if status == ValidationCheckStatus.FAILURE
                else ValidationSeverity.WARNING,
                "Opening cash plus cash movement does not reconcile to closing cash.",
                [fact.fact_id for fact in involved],
                "Review the cash-flow cells, signs, units, and reporting dates.",
            )


def _point_cash(
    facts: list[ReportedFinancialFact],
    flow_key: tuple,
    code: LineItemCode,
    as_of: date,
) -> tuple[ReportedFinancialFact | None, list[ReportedFinancialFact]]:
    candidates = [
        fact
        for fact in facts
        if fact.line_item_code == code
        and fact.as_of_date == as_of
        and fact.statement_basis.value == flow_key[4]
        and fact.currency == flow_key[5]
        and fact.audit_status.value == flow_key[6]
        and fact.restatement_status.value == flow_key[7]
    ]
    usable = [
        fact
        for fact in candidates
        if fact.status == "reported" and fact.normalized_value is not None
    ]
    usable.sort(key=lambda fact: fact.fact_id)
    if not usable or len({fact.normalized_value for fact in usable}) != 1:
        return None, candidates
    return usable[0], usable


def _reconciliation_status(
    difference: Decimal,
    tolerance: Decimal,
) -> ValidationCheckStatus:
    if difference <= tolerance:
        return ValidationCheckStatus.PASS
    if difference <= tolerance * 5:
        return ValidationCheckStatus.WARNING
    return ValidationCheckStatus.FAILURE


def _metric(
    code: str,
    name: str,
    formula: str,
    unit: str,
    value: Decimal | None,
    status: MetricStatus,
    reason: str | None,
    period: ReportedFinancialFact,
    basis: StatementBasis,
    currency: str,
    input_facts: list[ReportedFinancialFact],
    finding_codes: list[str],
) -> FinancialMetric:
    return FinancialMetric(
        metric_code=code,
        display_name=name,
        period_label=period.period_label,
        period_kind=period.period_kind,
        period_start=period.period_start,
        period_end=period.period_end,
        as_of_date=period.as_of_date,
        statement_basis=basis,
        audit_status=period.audit_status,
        restatement_status=period.restatement_status,
        currency=currency,
        value=value,
        unit=currency if unit == "currency" else unit,
        status=status,
        reason_code=reason,
        formula=formula,
        formula_version=FORMULA_VERSION,
        input_fact_ids=[fact.fact_id for fact in input_facts],
        evidence=[fact.evidence for fact in input_facts],
        finding_codes=list(dict.fromkeys(finding_codes)),
        finding_ids=[],
    )


def _add_finding(
    findings: dict[str, ValidationFinding],
    code: str,
    severity: ValidationSeverity,
    message: str,
    fact_ids: list[str],
    resolution: str | None = None,
) -> None:
    ids = sorted(set(fact_ids))
    key = f"{code}:{','.join(ids)}"
    finding_id = hashlib.sha256(key.encode()).hexdigest()[:16]
    findings.setdefault(
        finding_id,
        ValidationFinding(
            finding_id=finding_id,
            code=code,
            severity=severity,
            message=message,
            fact_ids=ids,
            recommended_resolution=resolution,
        ),
    )


def _reason_message(reason: str) -> str:
    messages = {
        "MISSING_INPUT": "One or more required line items were not supplied.",
        "MISSING_VALUE": (
            "The selected source cell does not contain a reported value."
        ),
        "NUMERIC_VALUE_TOO_LARGE": (
            "The source cell exceeds the supported 128-digit numeric precision limit."
        ),
        "INVALID_NUMERIC_VALUE": (
            "The selected source cell is not a supported numeric amount."
        ),
        "ZERO_DENOMINATOR": "The formula denominator is zero.",
        "NEGATIVE_DENOMINATOR": "The formula denominator is negative.",
        "ZERO_BASELINE": (
            "Revenue growth is unavailable because prior revenue is zero."
        ),
        "NEGATIVE_BASELINE": (
            "Revenue growth is not calculated from a negative baseline."
        ),
        "NO_COMPARABLE_PERIOD": "No compatible prior-year period was supplied.",
        "AMBIGUOUS_INPUT": "Conflicting values prevent an unambiguous calculation.",
        "NEGATIVE_EXPENSE_SIGN": (
            "Expense was reported with a negative sign; sign policy is unresolved."
        ),
        "NEGATIVE_BORROWINGS": "Borrowings must not be negative for this metric.",
        "INVALID_DEBT_OR_CASH_SIGN": (
            "Borrowings and cash must not be negative for net debt."
        ),
        "NON_POSITIVE_EQUITY": (
            "Debt-to-equity is not meaningful with zero or negative equity."
        ),
        "NON_POSITIVE_ASSETS": "Debt-to-assets requires positive total assets.",
        "NEGATIVE_FINANCE_COST_SIGN": (
            "Finance costs must be reported as a non-negative expense."
        ),
        "NEGATIVE_CURRENT_ASSETS": (
            "Current assets must not be negative for the current ratio."
        ),
        "NEGATIVE_QUICK_ASSETS": "Quick assets must not be negative.",
        "NEGATIVE_CAPEX_SIGN": (
            "Capital expenditure must be entered as a positive spend amount."
        ),
        "INCOMPATIBLE_PERIOD_KIND": (
            "Revenue growth requires annual, interim, or quarterly periods."
        ),
        "LOSS_TO_PROFIT": (
            "PAT changed from a loss to a profit; the absolute change is shown."
        ),
        "LOSS_TO_BREAK_EVEN": (
            "PAT changed from a loss to break-even; the absolute change is shown."
        ),
        "PROFIT_TO_LOSS": (
            "PAT changed from a profit to a loss; the absolute change is shown."
        ),
        "LOSS_CONTINUES": (
            "PAT remained negative; the absolute change is shown instead of a "
            "percentage growth rate."
        ),
        "ZERO_BASELINE_ABSOLUTE_CHANGE": (
            "Prior PAT is zero; the absolute change is shown instead of a "
            "percentage growth rate."
        ),
    }
    return messages.get(
        reason, "The metric could not be calculated from the supplied facts."
    )
