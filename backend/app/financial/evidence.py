import hashlib
import json

from app.schemas.documents import ExtractedTable


def financial_table_sha256(table: ExtractedTable) -> str:
    payload = json.dumps(
        table.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def financial_cell_sha256(
    table: ExtractedTable,
    row_index: int,
    column_index: int,
    source_document_sha256: str,
) -> str:
    cell_box = None
    if (
        table.cell_boxes is not None
        and row_index < len(table.cell_boxes)
        and column_index < len(table.cell_boxes[row_index])
    ):
        cell_box = table.cell_boxes[row_index][column_index]
    payload = {
        "source_document_sha256": source_document_sha256,
        "source_table_sha256": financial_table_sha256(table),
        "page_number": table.page_number,
        "table_index": table.table_index,
        "row_index": row_index,
        "column_index": column_index,
        "source_value": table.rows[row_index][column_index],
        "cell_box": cell_box,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
