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
const PAGE_SIZE = 500;

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

        renderResults(document, pages, tables);
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

function renderResults(documentInfo, pages, tables) {
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
        const body = createElement("tbody");
        for (const row of table.rows) {
            const tableRow = createElement("tr");
            for (const cell of row) {
                const tableCell = createElement("td");
                tableCell.textContent = cell;
                tableRow.append(tableCell);
            }
            body.append(tableRow);
        }
        tableElement.append(body);
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
