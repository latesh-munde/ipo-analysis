import { apiRequest } from "./api/api-client.js";

const form = document.querySelector("#upload-form");
const fileInput = document.querySelector("#document-file");
const fileTitle = document.querySelector("#file-picker-title");
const fileDetail = document.querySelector("#file-picker-detail");
const uploadButton = document.querySelector("#upload-button");
const uploadStatus = document.querySelector("#upload-status");
const apiStatus = document.querySelector("#api-status");
const resultsSection = document.querySelector("#results-section");
const resultStatus = document.querySelector("#result-status");
const summary = document.querySelector("#document-summary");
const warningList = document.querySelector("#warning-list");
const pagesPanel = document.querySelector("#pages-panel");
const tablesPanel = document.querySelector("#tables-panel");
const pagesTab = document.querySelector("#pages-tab");
const tablesTab = document.querySelector("#tables-tab");
const pagesCount = document.querySelector("#pages-count");
const tablesCount = document.querySelector("#tables-count");
const factForm = document.querySelector("#fact-form");
const lineItemSelect = document.querySelector("#line-item");
const periodKindSelect = document.querySelector("#period-kind");
const periodStart = document.querySelector("#period-start");
const periodEnd = document.querySelector("#period-end");
const asOfDate = document.querySelector("#as-of-date");
const flowDates = document.querySelector("#flow-dates");
const asOfField = document.querySelector("#as-of-field");
const sourceTableSelect = document.querySelector("#source-table");
const periodHeaderRow = document.querySelector("#period-header-row");
const sourceRow = document.querySelector("#source-row");
const labelColumn = document.querySelector("#label-column");
const valueColumn = document.querySelector("#value-column");
const factList = document.querySelector("#fact-list");
const analyzeButton = document.querySelector("#analyze-button");
const analysisStatus = document.querySelector("#analysis-status");
const analysisReport = document.querySelector("#analysis-report");
const sourceReview = document.querySelector("#source-review");
const sourcePageImage = document.querySelector("#source-page-image");
const sourcePageHighlight = document.querySelector("#source-page-highlight");
const sourceReviewForm = document.querySelector("#source-review-form");
const sourceReviewValue = document.querySelector("#source-review-value");
const sourceReviewCheckbox = document.querySelector("#source-review-confirm-checkbox");
const sourceReviewSubmit = document.querySelector("#source-review-submit");
const sourceReviewStatus = document.querySelector("#source-review-status");
const PAGE_SIZE = 500;
const POINT_IN_TIME_ITEMS = new Set([
    "current_assets",
    "non_current_assets",
    "inventories",
    "trade_receivables",
    "other_bank_balances",
    "cash_and_equivalents",
    "total_assets",
    "share_capital",
    "reserves",
    "total_equity",
    "total_liabilities",
    "current_liabilities",
    "non_current_liabilities",
    "trade_payables",
    "current_borrowings",
    "non_current_borrowings",
    "lease_liabilities",
    "total_equity_and_liabilities",
    "opening_cash",
    "closing_cash",
]);
const LINE_ITEM_STATEMENTS = {
    revenue_from_operations: "profit_and_loss",
    other_income: "profit_and_loss",
    total_income: "profit_and_loss",
    cost_of_sales: "profit_and_loss",
    operating_profit: "profit_and_loss",
    finance_costs: "profit_and_loss",
    depreciation_amortization: "profit_and_loss",
    profit_before_tax: "profit_and_loss",
    tax_expense: "profit_and_loss",
    profit_after_tax: "profit_and_loss",
    basic_eps: "profit_and_loss",
    diluted_eps: "profit_and_loss",
    current_assets: "balance_sheet",
    non_current_assets: "balance_sheet",
    inventories: "balance_sheet",
    trade_receivables: "balance_sheet",
    other_bank_balances: "balance_sheet",
    cash_and_equivalents: "balance_sheet",
    total_assets: "balance_sheet",
    share_capital: "balance_sheet",
    reserves: "balance_sheet",
    total_equity: "balance_sheet",
    total_liabilities: "balance_sheet",
    current_liabilities: "balance_sheet",
    non_current_liabilities: "balance_sheet",
    trade_payables: "balance_sheet",
    current_borrowings: "balance_sheet",
    non_current_borrowings: "balance_sheet",
    lease_liabilities: "balance_sheet",
    total_equity_and_liabilities: "balance_sheet",
    cash_from_operating_activities: "cash_flow",
    cash_from_investing_activities: "cash_flow",
    cash_from_financing_activities: "cash_flow",
    capital_expenditure: "cash_flow",
    net_cash_movement: "cash_flow",
    opening_cash: "cash_flow",
    closing_cash: "cash_flow",
};
let selectedDocumentId = null;
let extractedTables = [];
let selectedFacts = [];
let reviewedCellKeys = new Set();
let activeReviewTarget = null;
let activeReviewButton = null;

fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (!file) {
        fileTitle.textContent = "Choose a PDF to analyze";
        fileDetail.textContent =
            "PDF format · Maximum size is set by the local server";
        return;
    }

    fileTitle.textContent = file.name;
    fileDetail.textContent = `${formatBytes(file.size)} · PDF document`;
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearUploadStatus();

    const file = fileInput.files?.[0];
    if (!file) {
        showUploadStatus("Choose a PDF file to continue.", "error");
        fileInput.focus();
        return;
    }

    if (!file.name.toLowerCase().endsWith(".pdf")) {
        showUploadStatus("Select a file with a .pdf extension.", "error");
        fileInput.focus();
        return;
    }

    const formData = new FormData(form);
    uploadButton.disabled = true;
    uploadButton.querySelector("span").textContent = "Extracting…";
    showUploadStatus(
        "Uploading and extracting this PDF locally. Larger documents may take a little longer.",
    );

    try {
        const upload = await apiRequest("/documents", {
            method: "POST",
            body: formData,
        });
        const document = upload.document;
        const [pages, tables] = await Promise.all([
            fetchAllResults(`/documents/${encodeURIComponent(document.document_id)}/pages`),
            fetchAllResults(`/documents/${encodeURIComponent(document.document_id)}/tables`),
        ]);
        const reviews = await apiRequest(
            `/documents/${encodeURIComponent(document.document_id)}/financial-cell-reviews`,
        );

        renderResults(document, pages, tables, reviews);
        const duplicateMessage = document.duplicate
            ? " This exact PDF was already uploaded, so the saved results are shown."
            : "";
        showUploadStatus(
            `Extraction finished: ${pages.length} page(s), ${tables.length} table(s).${duplicateMessage}`,
            "success",
        );
        resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        showUploadStatus(error.message, "error");
    } finally {
        uploadButton.disabled = false;
        uploadButton.querySelector("span").textContent = "Extract document";
    }
});

pagesTab.addEventListener("click", () => selectResultTab("pages"));
tablesTab.addEventListener("click", () => selectResultTab("tables"));

lineItemSelect.addEventListener("change", updatePeriodFields);
factForm.addEventListener("submit", addSelectedFact);
analyzeButton.addEventListener("click", calculateFinancialAnalysis);
document.querySelector("#close-source-review").addEventListener("click", () => {
    sourceReview.hidden = true;
});
sourceReviewForm.addEventListener("submit", submitFinancialCellReview);
sourcePageImage.addEventListener("error", () => {
    showSourceReviewStatus(
        "The source page could not be rendered. The OCR cell has not been verified.",
        "error",
    );
});

for (const tab of [pagesTab, tablesTab]) {
    tab.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
            return;
        }
        event.preventDefault();
        const nextTab = tab === pagesTab ? tablesTab : pagesTab;
        nextTab.focus();
        nextTab.click();
    });
}

async function checkBackendHealth() {
    try {
        const health = await apiRequest("/health");
        apiStatus.textContent = `Local backend connected · ${health.status}`;
        apiStatus.classList.add("is-online");
        apiStatus.classList.remove("is-offline");
    } catch {
        apiStatus.textContent =
            "Local backend unavailable · Start the server using the README steps";
        apiStatus.classList.add("is-offline");
        apiStatus.classList.remove("is-online");
    }
}

async function fetchAllResults(path) {
    const items = [];
    let offset = 0;
    let total = 0;

    do {
        const page = await apiRequest(
            `${path}?offset=${offset}&limit=${PAGE_SIZE}`,
        );
        items.push(...page.items);
        total = page.total;
        offset += page.items.length;
        if (page.items.length === 0) {
            break;
        }
    } while (offset < total);

    return items;
}

function renderResults(documentInfo, pages, tables, reviews) {
    selectedDocumentId = documentInfo.document_id;
    extractedTables = tables;
    selectedFacts = [];
    activeReviewTarget = null;
    activeReviewButton = null;
    reviewedCellKeys = new Set(
        reviews.map((review) =>
            reviewCellKey(
                review.page_number,
                review.table_index,
                review.row_index,
                review.column_index,
            ),
        ),
    );
    sourceReview.hidden = true;
    analysisReport.replaceChildren();
    analysisReport.hidden = true;
    clearAnalysisStatus();
    populateSourceTables(tables);
    renderSelectedFacts();
    updatePeriodFields();
    resultsSection.hidden = false;
    resultStatus.textContent = statusLabel(documentInfo.status);
    resultStatus.className = "status-badge";
    if (documentInfo.status === "completed_with_warnings") {
        resultStatus.classList.add("is-warning");
    } else if (documentInfo.status === "failed") {
        resultStatus.classList.add("is-error");
    }
    renderSummary(documentInfo, pages.length, tables.length);
    renderWarnings(documentInfo.warnings ?? []);
    renderPages(pages);
    renderTables(tables);
    pagesCount.textContent = String(pages.length);
    tablesCount.textContent = String(tables.length);
    selectResultTab("pages");
}

function populateSourceTables(tables) {
    sourceTableSelect.replaceChildren();
    const placeholder = createElement("option", "", "Choose a source table");
    placeholder.value = "";
    sourceTableSelect.append(placeholder);
    for (const table of tables) {
        const option = createElement(
            "option",
            "",
            `PDF page ${table.page_number} · table ${table.table_index}`,
        );
        option.value = `${table.page_number}:${table.table_index}`;
        sourceTableSelect.append(option);
    }
    analyzeButton.disabled = tables.length === 0;
}

function updatePeriodFields() {
    const pointInTime = POINT_IN_TIME_ITEMS.has(lineItemSelect.value);
    periodKindSelect.value = pointInTime ? "point_in_time" : "annual";
    periodKindSelect.disabled = pointInTime;
    flowDates.hidden = pointInTime;
    periodStart.required = !pointInTime;
    periodEnd.required = !pointInTime;
    asOfField.hidden = !pointInTime;
    asOfDate.required = pointInTime;
}

function addSelectedFact(event) {
    event.preventDefault();
    const [pageValue, tableValue] = sourceTableSelect.value.split(":");
    const sourceTable = extractedTables.find(
        (table) =>
            table.page_number === Number(pageValue) &&
            table.table_index === Number(tableValue),
    );
    const rowIndex = Number(sourceRow.value);
    const periodHeaderRowIndex = Number(periodHeaderRow.value);
    const labelIndex = Number(labelColumn.value);
    const valueIndex = Number(valueColumn.value);
    if (
        !sourceTable ||
        !Number.isInteger(rowIndex) ||
        !Number.isInteger(periodHeaderRowIndex) ||
        !Number.isInteger(labelIndex) ||
        !Number.isInteger(valueIndex) ||
        rowIndex < 0 ||
        periodHeaderRowIndex < 0 ||
        rowIndex >= sourceTable.rows.length ||
        periodHeaderRowIndex >= sourceTable.rows.length ||
        labelIndex < 0 ||
        valueIndex < 0 ||
        labelIndex >= sourceTable.rows[rowIndex].length ||
        valueIndex >= sourceTable.rows[rowIndex].length ||
        labelIndex === valueIndex
    ) {
        showAnalysisStatus(
            "Choose an existing source row and separate label and value cells.",
            "error",
        );
        return;
    }

    const lineItem = lineItemSelect.value;
    const pointInTime = POINT_IN_TIME_ITEMS.has(lineItem);
    selectedFacts.push({
        line_item_code: lineItem,
        statement_type: LINE_ITEM_STATEMENTS[lineItem],
        period_label: document.querySelector("#period-label").value.trim(),
        period_kind: periodKindSelect.value,
        period_start: pointInTime ? null : periodStart.value,
        period_end: pointInTime ? null : periodEnd.value,
        as_of_date: pointInTime ? asOfDate.value : null,
        statement_basis: document.querySelector("#statement-basis").value,
        audit_status: document.querySelector("#audit-status").value,
        restatement_status: document.querySelector("#restatement-status").value,
        currency: document.querySelector("#currency").value,
        unit: document.querySelector("#financial-unit").value,
        page_number: sourceTable.page_number,
        table_index: sourceTable.table_index,
        row_index: rowIndex,
        period_header_row_index: periodHeaderRowIndex,
        label_column_index: labelIndex,
        value_column_index: valueIndex,
    });
    renderSelectedFacts();
    clearAnalysisStatus();
}

function renderSelectedFacts() {
    factList.replaceChildren();
    if (selectedFacts.length === 0) {
        factList.append(
            createElement(
                "p",
                "empty-state",
                "No source facts mapped yet. Values are read from selected extracted table cells.",
            ),
        );
        analyzeButton.textContent = "Calculate financial metrics";
        analyzeButton.disabled = extractedTables.length === 0;
        return;
    }
    const heading = createElement("h3", "", `Mapped source facts (${selectedFacts.length})`);
    factList.append(heading);
    selectedFacts.forEach((fact, index) => {
        const source = extractedTables.find(
            (table) =>
                table.page_number === fact.page_number &&
                table.table_index === fact.table_index,
        );
        const row = source.rows[fact.row_index];
        const item = createElement("div", "fact-item");
        const periodCell =
            source.rows[fact.period_header_row_index][fact.value_column_index];
        const requiresReview =
            source.extraction_method.startsWith("tesseract_ocr") &&
            !reviewedCellKeys.has(
                reviewCellKey(
                    fact.page_number,
                    fact.table_index,
                    fact.row_index,
                    fact.value_column_index,
                ),
            );
        const reviewNote = requiresReview ? " · OCR value needs source review" : "";
        const summaryText = `${lineItemLabel(fact.line_item_code)} · ${fact.period_label} (“${periodCell}”) · ${row[fact.label_column_index]}: ${row[fact.value_column_index]} · page ${fact.page_number}, table ${fact.table_index}, row ${fact.row_index}${reviewNote}`;
        const remove = createElement("button", "remove-fact", "Remove");
        remove.type = "button";
        remove.addEventListener("click", () => {
            selectedFacts.splice(index, 1);
            renderSelectedFacts();
        });
        item.append(createElement("span", "", summaryText), remove);
        factList.append(item);
    });
    analyzeButton.textContent = `Calculate ${selectedFacts.length} mapped fact(s)`;
    analyzeButton.disabled = selectedFacts.some((fact) => {
        const source = extractedTables.find(
            (table) =>
                table.page_number === fact.page_number &&
                table.table_index === fact.table_index,
        );
        return (
            source?.extraction_method.startsWith("tesseract_ocr") &&
            !reviewedCellKeys.has(
                reviewCellKey(
                    fact.page_number,
                    fact.table_index,
                    fact.row_index,
                    fact.value_column_index,
                ),
            )
        );
    });
    if (analyzeButton.disabled) {
        showAnalysisStatus(
            "Review each selected OCR value against its highlighted PDF cell before calculating.",
            "error",
        );
    }
}

function reviewCellKey(pageNumber, tableIndex, rowIndex, columnIndex) {
    return `${pageNumber}:${tableIndex}:${rowIndex}:${columnIndex}`;
}

function openFinancialCellReview(table, rowIndex, columnIndex, button) {
    activeReviewTarget = { table, rowIndex, columnIndex };
    activeReviewButton = button;
    sourceReview.hidden = false;
    sourceReviewStatus.textContent = "";
    sourceReviewStatus.className = "upload-status";
    sourceReviewCheckbox.checked = false;
    sourceReviewValue.value = table.rows[rowIndex][columnIndex];
    sourceReviewSubmit.disabled = false;

    const imagePath =
        `/documents/${encodeURIComponent(selectedDocumentId)}` +
        `/pages/${table.page_number}/image`;
    sourcePageImage.src = `/api/v1${imagePath}`;
    sourcePageHighlight.hidden = true;
    const box = table.cell_boxes?.[rowIndex]?.[columnIndex];
    if (box && table.page_width && table.page_height) {
        const [x0, y0, x1, y1] = box;
        sourcePageHighlight.style.left = `${(x0 / table.page_width) * 100}%`;
        sourcePageHighlight.style.top = `${(y0 / table.page_height) * 100}%`;
        sourcePageHighlight.style.width = `${((x1 - x0) / table.page_width) * 100}%`;
        sourcePageHighlight.style.height = `${((y1 - y0) / table.page_height) * 100}%`;
        sourcePageHighlight.hidden = false;
    }
    selectResultTab("tables");
    sourceReview.scrollIntoView({ behavior: "smooth", block: "start" });
    sourceReviewValue.focus();
}

async function submitFinancialCellReview(event) {
    event.preventDefault();
    if (!selectedDocumentId || !activeReviewTarget) {
        showSourceReviewStatus("Choose an OCR cell to review first.", "error");
        return;
    }
    const { table, rowIndex, columnIndex } = activeReviewTarget;
    sourceReviewSubmit.disabled = true;
    showSourceReviewStatus("Saving the source verification…");
    try {
        await apiRequest(
            `/documents/${encodeURIComponent(selectedDocumentId)}` +
                `/pages/${table.page_number}/tables/${table.table_index}` +
                `/cells/${rowIndex}/${columnIndex}/review`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    confirmed_value: sourceReviewValue.value.trim(),
                    source_checked: sourceReviewCheckbox.checked,
                }),
            },
        );
        reviewedCellKeys.add(
            reviewCellKey(table.page_number, table.table_index, rowIndex, columnIndex),
        );
        if (activeReviewButton) {
            activeReviewButton.textContent = "Reviewed";
            activeReviewButton.classList.add("is-reviewed");
        }
        showSourceReviewStatus(
            "Review saved. The calculation API will use this confirmed value and retain the original OCR reading.",
            "success",
        );
        renderSelectedFacts();
    } catch (error) {
        showSourceReviewStatus(error.message, "error");
    } finally {
        sourceReviewSubmit.disabled = false;
    }
}

function showSourceReviewStatus(message, state = "") {
    sourceReviewStatus.textContent = message;
    sourceReviewStatus.className = `upload-status${state ? ` is-${state}` : ""}`;
}

async function calculateFinancialAnalysis() {
    if (!selectedDocumentId || selectedFacts.length === 0) {
        showAnalysisStatus("Map at least one source fact before calculating.", "error");
        return;
    }
    analyzeButton.disabled = true;
    showAnalysisStatus("Calculating metrics from the selected source cells…");
    try {
        const report = await apiRequest(
            `/documents/${encodeURIComponent(selectedDocumentId)}/financial-analysis`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ facts: selectedFacts }),
            },
        );
        renderFinancialReport(report);
        showAnalysisStatus(
            "Analysis generated and canonical facts saved. Review unavailable values, findings, and source references.",
            "success",
        );
    } catch (error) {
        showAnalysisStatus(error.message, "error");
    } finally {
        analyzeButton.disabled = selectedFacts.length === 0;
    }
}

function renderFinancialReport(report) {
    analysisReport.replaceChildren();
    analysisReport.hidden = false;
    const reportHeader = createElement("div", "report-heading");
    reportHeader.append(
        createElement("h3", "", "Calculated metrics"),
        createElement(
            "p",
            "",
            `${report.facts.length} persisted fact(s) · Formula set ${report.formula_set_version} · Generated ${formatDate(report.generated_at)}`,
        ),
    );
    analysisReport.append(reportHeader);

    const metricTable = createElement("table", "metric-table");
    const head = createElement("thead");
    const headerRow = createElement("tr");
    for (const title of ["Metric", "Period", "Result", "Status", "Formula and source facts"]) {
        headerRow.append(createElement("th", "", title));
    }
    head.append(headerRow);
    metricTable.append(head);
    const body = createElement("tbody");
    for (const metric of report.metrics) {
        const row = createElement("tr");
        row.append(
            createElement("th", "", metric.display_name),
            createElement("td", "", metric.period_label),
            createElement(
                "td",
                "metric-value",
                metric.status === "calculated"
                    ? `${metric.value} ${metric.unit}`
                    : metric.reason_code || "Unavailable",
            ),
            createElement("td", `metric-status is-${metric.status}`, statusLabel(metric.status)),
        );
        const detailCell = createElement("td");
        detailCell.append(createElement("code", "formula-text", metric.formula));
        if (metric.input_fact_ids.length) {
            const evidenceList = createElement("ul", "metric-evidence");
            for (const evidence of metric.evidence) {
                evidenceList.append(
                    createElement(
                        "li",
                        "",
                        `PDF page ${evidence.page_number}, table ${evidence.table_index}, row ${evidence.row_index}, value column ${evidence.value_column_index} · period header row ${evidence.period_header_row_index}: “${evidence.period_header_text}” · “${evidence.original_label}” = “${evidence.extracted_value}”`,
                    ),
                );
            }
            detailCell.append(evidenceList);
        }
        if (metric.finding_ids.length) {
            detailCell.append(
                createElement(
                    "p",
                    "metric-findings",
                    `Related finding(s): ${metric.finding_codes.join(", ")} · ${metric.finding_ids.join(", ")}`,
                ),
            );
        }
        row.append(detailCell);
        body.append(row);
    }
    metricTable.append(body);
    const tableScroll = createElement("div", "table-scroll");
    tableScroll.append(metricTable);
    analysisReport.append(tableScroll);

    const factHeading = createElement("h3", "", "Source facts");
    analysisReport.append(factHeading);
    const factTable = createElement("table", "metric-table");
    const factBody = createElement("tbody");
    for (const fact of report.facts) {
        const row = createElement("tr");
        row.append(
            createElement("th", "", lineItemLabel(fact.line_item_code)),
            createElement("td", "", fact.period_label),
            createElement(
                "td",
                "",
                fact.normalized_value === null
                    ? fact.reason_code || "Value unavailable"
                    : `${fact.normalized_value} ${fact.currency}`,
            ),
            createElement(
                "td",
                "",
                `${fact.status} · revision ${fact.revision} · ${fact.statement_basis} · ${fact.audit_status} · ${fact.restatement_status} · reported in ${fact.reported_unit}`,
            ),
            createElement(
                "td",
                "",
                `PDF page ${fact.evidence.page_number} · table ${fact.evidence.table_index} · row ${fact.evidence.row_index} · period header “${fact.evidence.period_header_text}” · ${fact.evidence.original_label}: ${fact.evidence.extracted_value}`,
            ),
        );
        factBody.append(row);
    }
    factTable.append(factBody);
    const factScroll = createElement("div", "table-scroll");
    factScroll.append(factTable);
    analysisReport.append(factScroll);

    appendReportList(analysisReport, "Validation findings", report.validation_findings, (finding) =>
        `${finding.severity.toUpperCase()} · ${finding.code}: ${finding.message}`,
    );
    appendReportList(analysisReport, "Cross-statement checks", report.validation_checks, (check) =>
        `${check.status} · ${check.code}: ${check.message}${check.difference === null ? "" : ` (difference ${check.difference}; tolerance ${check.tolerance})`}`,
    );
    appendReportList(analysisReport, "Limitations", report.limitations, (item) => item);
}

function appendReportList(container, title, items, label) {
    const section = createElement("section", "report-notes");
    section.append(createElement("h3", "", title));
    if (items.length === 0) {
        section.append(createElement("p", "", "None reported."));
    } else {
        const list = createElement("ul");
        for (const item of items) {
            list.append(createElement("li", "", label(item)));
        }
        section.append(list);
    }
    container.append(section);
}

function lineItemLabel(code) {
    const option = [...lineItemSelect.options].find((item) => item.value === code);
    return option?.textContent ?? code;
}

function showAnalysisStatus(message, kind = "") {
    analysisStatus.textContent = message;
    analysisStatus.className = "upload-status";
    if (kind) {
        analysisStatus.classList.add(`is-${kind}`);
    }
}

function clearAnalysisStatus() {
    analysisStatus.textContent = "";
    analysisStatus.className = "upload-status";
}
function renderSummary(documentInfo, pageCount, tableCount) {
    summary.replaceChildren();
    const values = [
        ["Document", documentInfo.original_filename],
        ["Type", documentInfo.document_type || "Not specified"],
        ["PDF pages", String(documentInfo.page_count ?? pageCount)],
        ["Tables found", String(tableCount)],
        ["File size", formatBytes(documentInfo.file_size)],
        ["Uploaded", formatDate(documentInfo.uploaded_at)],
        ["Document ID", documentInfo.document_id],
        ["SHA-256", documentInfo.sha256],
    ];

    for (const [label, value] of values) {
        const item = createElement("div", "summary-item");
        item.append(
            createElement("span", "", label),
            createElement("strong", "", value),
        );
        summary.append(item);
    }
}

function renderWarnings(warnings) {
    warningList.replaceChildren();
    warningList.hidden = warnings.length === 0;
    if (!warnings.length) {
        return;
    }

    warningList.append(createElement("h3", "", "Review these extraction notes"));
    const list = createElement("ul");
    for (const warning of warnings) {
        const location = warning.page_number
            ? `Page ${warning.page_number}: `
            : "";
        list.append(createElement("li", "", `${location}${warning.message}`));
    }
    warningList.append(list);
}

function renderPages(pages) {
    pagesPanel.replaceChildren();
    if (pages.length === 0) {
        pagesPanel.append(
            createElement(
                "p",
                "empty-state",
                "No page results were saved for this document. Check the document status and warnings above.",
            ),
        );
        return;
    }

    for (const page of pages) {
        const details = createElement("details", "page-result");
        const heading = createElement("summary");
        const title = createElement("span", "page-title", `PDF page ${page.page_number}`);
        const meta = createElement("span", "page-meta");
        meta.append(
            createElement("span", "", `${page.character_count} characters`),
            createElement("span", "method-pill", methodLabel(page.extraction_method)),
            createElement("span", "", statusLabel(page.status)),
        );
        heading.append(title, meta);

        const content = createElement("pre", "page-text");
        content.textContent = page.text || "[No text extracted from this page.]";
        details.append(heading, content);

        if (page.ocr_text !== null && page.ocr_text !== undefined) {
            const comparison = createElement("details", "page-readings");
            comparison.append(
                createElement(
                    "summary",
                    "",
                    "Compare source readings (OCR is unverified)",
                ),
            );
            comparison.append(
                createElement("h4", "", "Native PDF text"),
                createElement(
                    "pre",
                    "page-text",
                    page.native_text || "[No native text extracted.]",
                ),
                createElement("h4", "", "OCR text — verify every financial number"),
                createElement(
                    "pre",
                    "page-text",
                    page.ocr_text || "[OCR ran but did not recognize text.]",
                ),
            );
            details.append(comparison);
        }

        if (page.warnings?.length) {
            const notes = createElement("ul", "page-warnings");
            for (const warning of page.warnings) {
                notes.append(createElement("li", "", warning.message));
            }
            details.append(notes);
        }
        pagesPanel.append(details);
    }
}

function renderTables(tables) {
    tablesPanel.replaceChildren();
    if (tables.length === 0) {
        tablesPanel.append(
            createElement(
                "p",
                "empty-state",
                "No supported tables were detected. Text extraction is shown in the Page text tab. Scanned and complex tables may need manual review.",
            ),
        );
        return;
    }

    for (const table of tables) {
        const details = createElement("details", "table-result");
        const heading = createElement("summary");
        heading.append(
            createElement(
                "span",
                "page-title",
                `Table ${table.table_index} · PDF page ${table.page_number}`,
            ),
            createElement("span", "method-pill", methodLabel(table.extraction_method)),
        );

        const scroll = createElement("div", "table-scroll");
        const tableElement = createElement("table", "extracted-table");
        const columns = table.rows.reduce(
            (maximum, row) => Math.max(maximum, row.length),
            0,
        );
        const tableHead = createElement("thead");
        const headerRow = createElement("tr");
        headerRow.append(createElement("th", "", "Row / column"));
        for (let columnIndex = 0; columnIndex < columns; columnIndex += 1) {
            headerRow.append(
                createElement("th", "", `Column ${columnIndex}`),
            );
        }
        tableHead.append(headerRow);
        const body = createElement("tbody");
        for (const [rowIndex, row] of table.rows.entries()) {
            const tableRow = createElement("tr");
            tableRow.append(createElement("th", "", `Row ${rowIndex}`));
            for (const [columnIndex, cell] of row.entries()) {
                const tableCell = createElement("td");
                tableCell.append(createElement("span", "", cell));
                if (table.extraction_method.startsWith("tesseract_ocr")) {
                    const reviewButton = createElement(
                        "button",
                        "cell-review-button",
                        reviewedCellKeys.has(
                            reviewCellKey(
                                table.page_number,
                                table.table_index,
                                rowIndex,
                                columnIndex,
                            ),
                        )
                            ? "Reviewed"
                            : "Review against PDF",
                    );
                    reviewButton.type = "button";
                    if (
                        reviewedCellKeys.has(
                            reviewCellKey(
                                table.page_number,
                                table.table_index,
                                rowIndex,
                                columnIndex,
                            ),
                        )
                    ) {
                        reviewButton.classList.add("is-reviewed");
                    }
                    reviewButton.addEventListener("click", () =>
                        openFinancialCellReview(
                            table,
                            rowIndex,
                            columnIndex,
                            reviewButton,
                        ),
                    );
                    tableCell.append(reviewButton);
                }
                tableRow.append(tableCell);
            }
            body.append(tableRow);
        }
        tableElement.append(tableHead, body);
        scroll.append(tableElement);
        details.append(heading, scroll);

        if (table.warnings?.length) {
            const notes = createElement("ul", "page-warnings");
            for (const warning of table.warnings) {
                notes.append(createElement("li", "", warning.message));
            }
            details.append(notes);
        }
        tablesPanel.append(details);
    }
}

function selectResultTab(selected) {
    const showPages = selected === "pages";
    pagesTab.classList.toggle("is-active", showPages);
    pagesTab.setAttribute("aria-selected", String(showPages));
    pagesTab.tabIndex = showPages ? 0 : -1;
    tablesTab.classList.toggle("is-active", !showPages);
    tablesTab.setAttribute("aria-selected", String(!showPages));
    tablesTab.tabIndex = showPages ? -1 : 0;
    pagesPanel.hidden = !showPages;
    tablesPanel.hidden = showPages;
}

function createElement(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) {
        element.className = className;
    }
    if (text) {
        element.textContent = text;
    }
    return element;
}

function statusLabel(status) {
    const labels = {
        completed: "Completed",
        completed_with_warnings: "Completed with warnings",
        failed: "Extraction failed",
        processing: "Processing",
        empty: "Empty page",
        calculated: "Calculated",
        unavailable: "Unavailable",
        blocked: "Blocked",
    };
    return labels[status] ?? status;
}

function methodLabel(method) {
    return method === "tesseract_ocr" ? "OCR · verify values" : "Native PDF";
}

function formatBytes(bytes) {
    if (bytes < 1024) {
        return `${bytes} B`;
    }
    const kilobytes = bytes / 1024;
    if (kilobytes < 1024) {
        return `${kilobytes.toFixed(0)} KB`;
    }
    return `${(kilobytes / 1024).toFixed(1)} MB`;
}

function formatDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Unknown" : date.toLocaleString();
}

function showUploadStatus(message, kind = "") {
    uploadStatus.textContent = message;
    uploadStatus.className = "upload-status";
    if (kind) {
        uploadStatus.classList.add(`is-${kind}`);
    }
}

function clearUploadStatus() {
    uploadStatus.textContent = "";
    uploadStatus.className = "upload-status";
}

checkBackendHealth();
