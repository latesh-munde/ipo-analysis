from datetime import date, timedelta
from decimal import Decimal, localcontext

import pytest
from app.financial.calculations import calculate_analysis, normalize_value
from app.schemas.financial_analysis import (
    AuditStatus,
    EvidenceReference,
    FinancialMetric,
    FinancialUnit,
    LineItemCode,
    MetricStatus,
    PeriodKind,
    ReportedFinancialFact,
    RestatementStatus,
    StatementBasis,
    StatementType,
)
from app.services.financial_analysis import _parse_amount


def make_fact(
    fact_id: str,
    code: LineItemCode,
    value: str,
    start: date | None = date(2024, 4, 1),
    end: date | None = date(2025, 3, 31),
    as_of: date | None = None,
    unit: FinancialUnit = FinancialUnit.RUPEES,
    period_kind: PeriodKind = PeriodKind.ANNUAL,
    audit_status: AuditStatus = AuditStatus.AUDITED,
    restatement_status: RestatementStatus = RestatementStatus.AS_PUBLISHED,
) -> ReportedFinancialFact:
    statements = {
        LineItemCode.REVENUE_FROM_OPERATIONS: StatementType.PROFIT_AND_LOSS,
        LineItemCode.COST_OF_SALES: StatementType.PROFIT_AND_LOSS,
        LineItemCode.OPERATING_PROFIT: StatementType.PROFIT_AND_LOSS,
        LineItemCode.FINANCE_COSTS: StatementType.PROFIT_AND_LOSS,
        LineItemCode.PROFIT_BEFORE_TAX: StatementType.PROFIT_AND_LOSS,
        LineItemCode.PROFIT_AFTER_TAX: StatementType.PROFIT_AND_LOSS,
        LineItemCode.BASIC_EPS: StatementType.PROFIT_AND_LOSS,
        LineItemCode.DILUTED_EPS: StatementType.PROFIT_AND_LOSS,
        LineItemCode.CURRENT_ASSETS: StatementType.BALANCE_SHEET,
        LineItemCode.CASH_AND_EQUIVALENTS: StatementType.BALANCE_SHEET,
        LineItemCode.TRADE_RECEIVABLES: StatementType.BALANCE_SHEET,
        LineItemCode.CURRENT_LIABILITIES: StatementType.BALANCE_SHEET,
        LineItemCode.CURRENT_BORROWINGS: StatementType.BALANCE_SHEET,
        LineItemCode.NON_CURRENT_BORROWINGS: StatementType.BALANCE_SHEET,
        LineItemCode.TOTAL_EQUITY: StatementType.BALANCE_SHEET,
        LineItemCode.TOTAL_ASSETS: StatementType.BALANCE_SHEET,
        LineItemCode.TOTAL_LIABILITIES: StatementType.BALANCE_SHEET,
        LineItemCode.CASH_FROM_OPERATING_ACTIVITIES: StatementType.CASH_FLOW,
        LineItemCode.CASH_FROM_INVESTING_ACTIVITIES: StatementType.CASH_FLOW,
        LineItemCode.CASH_FROM_FINANCING_ACTIVITIES: StatementType.CASH_FLOW,
        LineItemCode.CAPITAL_EXPENDITURE: StatementType.CASH_FLOW,
        LineItemCode.OPENING_CASH: StatementType.CASH_FLOW,
        LineItemCode.CLOSING_CASH: StatementType.CASH_FLOW,
    }
    amount = Decimal(value)
    return ReportedFinancialFact(
        fact_id=fact_id,
        line_item_code=code,
        statement_type=statements[code],
        period_label=f"FY {end.year if end else as_of.year}",
        period_kind=period_kind,
        period_start=start,
        period_end=end,
        as_of_date=as_of,
        statement_basis=StatementBasis.CONSOLIDATED,
        audit_status=audit_status,
        restatement_status=restatement_status,
        currency="INR",
        reported_value=amount,
        normalized_value=normalize_value(amount, unit.value),
        reported_unit=unit,
        status="reported",
        reason_code=None,
        evidence=EvidenceReference(
            document_id="doc-1",
            source_document_sha256="a" * 64,
            source_table_sha256="b" * 64,
            source_cell_sha256="c" * 64,
            page_number=1,
            table_index=0,
            row_index=0,
            period_header_row_index=0,
            period_header_text="FY 2025",
            label_column_index=0,
            value_column_index=1,
            original_label=code.value,
            extracted_value=value,
            extraction_method="native_text",
            source_warnings=[],
        ),
    )


def metric_for(
    metrics: list[FinancialMetric],
    code: str,
    period_label: str = "FY 2025",
) -> FinancialMetric:
    return next(
        metric
        for metric in metrics
        if metric.metric_code == code and metric.period_label == period_label
    )


def test_calculates_growth_and_margins_with_exact_decimal_evidence() -> None:
    prior = [
        make_fact(
            "prior-revenue",
            LineItemCode.REVENUE_FROM_OPERATIONS,
            "100",
            date(2023, 4, 1),
            date(2024, 3, 31),
        )
    ]
    current = [
        make_fact("revenue", LineItemCode.REVENUE_FROM_OPERATIONS, "125"),
        make_fact("cost", LineItemCode.COST_OF_SALES, "75"),
        make_fact("operating", LineItemCode.OPERATING_PROFIT, "25"),
        make_fact("pbt", LineItemCode.PROFIT_BEFORE_TAX, "20"),
        make_fact("pat", LineItemCode.PROFIT_AFTER_TAX, "-5"),
    ]

    facts = prior + current
    metrics, findings, checks = calculate_analysis(facts)
    reversed_metrics, reversed_findings, reversed_checks = calculate_analysis(
        list(reversed(facts))
    )

    assert metrics == reversed_metrics
    assert findings == reversed_findings
    assert checks == reversed_checks
    assert metric_for(metrics, "revenue_growth_yoy").value == Decimal("25")
    assert metric_for(metrics, "gross_profit").value == Decimal("50")
    assert metric_for(metrics, "gross_margin").value == Decimal("40")
    assert metric_for(metrics, "operating_margin").value == Decimal("20")
    assert metric_for(metrics, "pbt_margin").value == Decimal("16")
    assert metric_for(metrics, "pat_margin").value == Decimal("-4")
    assert metric_for(metrics, "gross_margin").input_fact_ids == ["revenue", "cost"]
    assert metric_for(metrics, "gross_margin").evidence[0].document_id == "doc-1"


def test_calculates_debt_liquidity_and_cash_flow_metrics() -> None:
    point = date(2025, 3, 31)
    facts = [
        make_fact(
            "short-debt",
            LineItemCode.CURRENT_BORROWINGS,
            "10",
            None,
            None,
            point,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "long-debt",
            LineItemCode.NON_CURRENT_BORROWINGS,
            "20",
            None,
            None,
            point,
            unit=FinancialUnit.CRORE_RUPEES,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "cash",
            LineItemCode.CASH_AND_EQUIVALENTS,
            "40",
            None,
            None,
            point,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "equity",
            LineItemCode.TOTAL_EQUITY,
            "100",
            None,
            None,
            point,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "assets",
            LineItemCode.TOTAL_ASSETS,
            "150",
            None,
            None,
            point,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "liabilities",
            LineItemCode.TOTAL_LIABILITIES,
            "50",
            None,
            None,
            point,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "current-assets",
            LineItemCode.CURRENT_ASSETS,
            "80",
            None,
            None,
            point,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "current-liabilities",
            LineItemCode.CURRENT_LIABILITIES,
            "40",
            None,
            None,
            point,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "receivables",
            LineItemCode.TRADE_RECEIVABLES,
            "20",
            None,
            None,
            point,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact("revenue", LineItemCode.REVENUE_FROM_OPERATIONS, "100"),
        make_fact("operating", LineItemCode.OPERATING_PROFIT, "15"),
        make_fact("finance", LineItemCode.FINANCE_COSTS, "5"),
        make_fact("cfo", LineItemCode.CASH_FROM_OPERATING_ACTIVITIES, "30"),
        make_fact("cfi", LineItemCode.CASH_FROM_INVESTING_ACTIVITIES, "-10"),
        make_fact("cff", LineItemCode.CASH_FROM_FINANCING_ACTIVITIES, "-5"),
        make_fact("capex", LineItemCode.CAPITAL_EXPENDITURE, "8"),
    ]

    metrics, findings, checks = calculate_analysis(facts)

    assert metric_for(metrics, "total_borrowings").value == Decimal("200000010")
    assert metric_for(metrics, "net_debt").value == Decimal("199999970")
    assert metric_for(metrics, "debt_to_equity").value == Decimal("2000000.1")
    assert metric_for(metrics, "debt_to_assets").value == Decimal("200000010") / 150
    assert metric_for(metrics, "current_ratio").value == Decimal("2")
    assert metric_for(metrics, "quick_ratio").value == Decimal("1.5")
    assert metric_for(metrics, "working_capital").value == Decimal("40")
    assert metric_for(metrics, "interest_coverage").value == Decimal("3")
    assert metric_for(metrics, "cfo_margin").value == Decimal("30")
    assert metric_for(metrics, "free_cash_flow").value == Decimal("22")
    assert metric_for(metrics, "net_cash_movement").value == Decimal("15")
    assert not [item for item in findings if item.code == "BALANCE_SHEET_MISMATCH"]
    assert (
        next(
            item for item in checks if item.code == "BALANCE_SHEET_EQUATION"
        ).status.value
        == "pass"
    )


def test_missing_inputs_zero_baseline_and_conflicting_facts_are_explicit() -> None:
    prior = make_fact(
        "prior",
        LineItemCode.REVENUE_FROM_OPERATIONS,
        "0",
        date(2023, 4, 1),
        date(2024, 3, 31),
    )
    current = make_fact("current", LineItemCode.REVENUE_FROM_OPERATIONS, "10")
    conflict = make_fact("conflict", LineItemCode.REVENUE_FROM_OPERATIONS, "11")

    baseline_metrics, _, _ = calculate_analysis([prior, current])
    metrics, findings, _ = calculate_analysis([current, conflict])

    assert (
        metric_for(baseline_metrics, "revenue_growth_yoy").reason_code
        == "ZERO_BASELINE"
    )
    assert metric_for(metrics, "gross_margin").reason_code == "AMBIGUOUS_INPUT"
    assert metric_for(metrics, "gross_margin").status == MetricStatus.BLOCKED
    assert any(item.code == "CONFLICTING_FACTS" for item in findings)
    assert metric_for(metrics, "gross_margin").finding_ids
    assert "CONFLICTING_FACTS" in metric_for(metrics, "gross_margin").finding_codes


def test_zero_denominators_negative_equity_and_missing_capex_are_not_guessed() -> None:
    date_at = date(2025, 3, 31)
    facts = [
        make_fact("revenue", LineItemCode.REVENUE_FROM_OPERATIONS, "0"),
        make_fact("pat", LineItemCode.PROFIT_AFTER_TAX, "5"),
        make_fact("cfo", LineItemCode.CASH_FROM_OPERATING_ACTIVITIES, "-2"),
        make_fact(
            "equity",
            LineItemCode.TOTAL_EQUITY,
            "-1",
            None,
            None,
            date_at,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "current-debt",
            LineItemCode.CURRENT_BORROWINGS,
            "4",
            None,
            None,
            date_at,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "long-debt",
            LineItemCode.NON_CURRENT_BORROWINGS,
            "0",
            None,
            None,
            date_at,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
    ]

    metrics, _, _ = calculate_analysis(facts)

    assert metric_for(metrics, "pat_margin").reason_code == "ZERO_DENOMINATOR"
    assert metric_for(metrics, "free_cash_flow").reason_code == "MISSING_INPUT"
    assert metric_for(metrics, "debt_to_equity").reason_code == "NON_POSITIVE_EQUITY"
    assert metric_for(metrics, "net_debt").reason_code == "MISSING_INPUT"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1,23,456.75", Decimal("123456.75")),
        ("(₹ 1,000)", Decimal("-1000")),
        ("-", None),
        ("", None),
        ("1.2.3", None),
        ("1,2,34", None),
    ],
)
def test_source_amount_parser_preserves_missing_and_rejects_malformed_values(
    raw: str,
    expected: Decimal | None,
) -> None:
    value, reason = _parse_amount(raw)

    assert value == expected
    if expected is None and raw.strip() not in {"", "-"}:
        assert reason == "INVALID_NUMERIC_VALUE"


def test_source_amount_parser_rejects_values_beyond_supported_precision() -> None:
    value, reason = _parse_amount("9" * 129)

    assert value is None
    assert reason == "NUMERIC_VALUE_TOO_LARGE"


def test_scale_normalization_uses_decimal_multipliers() -> None:
    assert normalize_value(Decimal("1.25"), "crore_rupees") == Decimal("12500000")


def test_scale_normalization_preserves_high_precision_values() -> None:
    value = Decimal("9" * 128)

    assert normalize_value(value, "crore_rupees") == Decimal("9" * 128 + "0000000")


def test_revenue_growth_does_not_mix_restatement_statuses() -> None:
    prior = make_fact(
        "prior",
        LineItemCode.REVENUE_FROM_OPERATIONS,
        "100",
        date(2023, 4, 1),
        date(2024, 3, 31),
    )
    restated = make_fact(
        "restated-current",
        LineItemCode.REVENUE_FROM_OPERATIONS,
        "125",
        audit_status=AuditStatus.AUDITED,
        restatement_status=RestatementStatus.RESTATED,
    )

    metrics, _, _ = calculate_analysis([prior, restated])

    assert (
        metric_for(metrics, "revenue_growth_yoy", "FY 2025").reason_code
        == "NO_COMPARABLE_PERIOD"
    )


def test_cross_statement_mismatch_uses_configured_rupee_tolerance() -> None:
    as_of = date(2025, 3, 31)
    facts = [
        make_fact(
            "assets",
            LineItemCode.TOTAL_ASSETS,
            "112",
            None,
            None,
            as_of,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "equity",
            LineItemCode.TOTAL_EQUITY,
            "100",
            None,
            None,
            as_of,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "liabilities",
            LineItemCode.TOTAL_LIABILITIES,
            "10",
            None,
            None,
            as_of,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
    ]

    _, findings, default_checks = calculate_analysis(facts)
    _, _, tolerant_checks = calculate_analysis(facts, Decimal("2"))

    assert (
        next(
            check for check in default_checks if check.code == "BALANCE_SHEET_EQUATION"
        ).status.value
        == "warning"
    )
    assert (
        next(
            check for check in tolerant_checks if check.code == "BALANCE_SHEET_EQUATION"
        ).status.value
        == "pass"
    )
    assert any(finding.code == "BALANCE_SHEET_MISMATCH" for finding in findings)


def test_negative_net_debt_and_zero_current_liability_policy() -> None:
    as_of = date(2025, 3, 31)
    facts = [
        make_fact(
            "short-debt",
            LineItemCode.CURRENT_BORROWINGS,
            "1",
            None,
            None,
            as_of,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "long-debt",
            LineItemCode.NON_CURRENT_BORROWINGS,
            "0",
            None,
            None,
            as_of,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "cash",
            LineItemCode.CASH_AND_EQUIVALENTS,
            "2",
            None,
            None,
            as_of,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "current-assets",
            LineItemCode.CURRENT_ASSETS,
            "10",
            None,
            None,
            as_of,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "current-liabilities",
            LineItemCode.CURRENT_LIABILITIES,
            "0",
            None,
            None,
            as_of,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
    ]

    metrics, _, _ = calculate_analysis(facts)

    assert metric_for(metrics, "net_debt").value == Decimal("-1")
    assert metric_for(metrics, "current_ratio").reason_code == "ZERO_DENOMINATOR"


def test_cash_opening_and_closing_balance_reconciliation() -> None:
    start = date(2024, 4, 1)
    end = date(2025, 3, 31)
    facts = [
        make_fact("cfo", LineItemCode.CASH_FROM_OPERATING_ACTIVITIES, "30", start, end),
        make_fact(
            "cfi", LineItemCode.CASH_FROM_INVESTING_ACTIVITIES, "-10", start, end
        ),
        make_fact("cff", LineItemCode.CASH_FROM_FINANCING_ACTIVITIES, "-5", start, end),
        make_fact(
            "opening",
            LineItemCode.OPENING_CASH,
            "100",
            None,
            None,
            start,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "closing",
            LineItemCode.CLOSING_CASH,
            "115",
            None,
            None,
            end,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
    ]

    _, _, checks = calculate_analysis(facts)

    assert (
        next(
            check for check in checks if check.code == "CASH_BALANCE_RECONCILIATION"
        ).status.value
        == "pass"
    )


def test_returns_use_opening_and_closing_balances_and_eps_is_reported() -> None:
    start = date(2024, 4, 1)
    end = date(2025, 3, 31)
    facts = [
        make_fact("pat", LineItemCode.PROFIT_AFTER_TAX, "100", start, end),
        make_fact(
            "opening-assets",
            LineItemCode.TOTAL_ASSETS,
            "500",
            None,
            None,
            start - timedelta(days=1),
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "closing-assets",
            LineItemCode.TOTAL_ASSETS,
            "600",
            None,
            None,
            end,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "opening-equity",
            LineItemCode.TOTAL_EQUITY,
            "200",
            None,
            None,
            start - timedelta(days=1),
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "closing-equity",
            LineItemCode.TOTAL_EQUITY,
            "300",
            None,
            None,
            end,
            period_kind=PeriodKind.POINT_IN_TIME,
        ),
        make_fact(
            "basic-eps",
            LineItemCode.BASIC_EPS,
            "10.25",
            start,
            end,
            unit=FinancialUnit.RUPEES_PER_SHARE,
        ),
    ]

    metrics, _, _ = calculate_analysis(facts)

    with localcontext() as context:
        context.prec = 160
        expected_roa = Decimal("100") / Decimal("550") * 100
    assert metric_for(metrics, "return_on_assets").value == expected_roa
    assert metric_for(metrics, "return_on_equity").value == Decimal("40")
    assert metric_for(metrics, "basic_eps").value == Decimal("10.25")
    assert metric_for(metrics, "basic_eps").unit == "INR/share"
    assert metric_for(metrics, "diluted_eps").reason_code == "MISSING_INPUT"


def test_profit_loss_transition_reports_absolute_change_with_note() -> None:
    prior = make_fact(
        "prior-pat",
        LineItemCode.PROFIT_AFTER_TAX,
        "-10",
        date(2023, 4, 1),
        date(2024, 3, 31),
    )
    current = make_fact(
        "current-pat",
        LineItemCode.PROFIT_AFTER_TAX,
        "15",
    )

    metrics, findings, _ = calculate_analysis([prior, current])
    change = metric_for(metrics, "pat_growth_yoy")

    assert change.value == Decimal("25")
    assert change.unit == "INR"
    assert change.reason_code == "LOSS_TO_PROFIT"
    assert any(finding.code == "LOSS_TO_PROFIT" for finding in findings)
