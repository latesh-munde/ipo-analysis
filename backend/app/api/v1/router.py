from typing import Annotated

from app.core.config import Settings, get_settings
from app.schemas.documents import DocumentMetadata, FinancialCellReviewRequest
from app.schemas.financial_analysis import (
    FinancialAnalysisReport,
    FinancialAnalysisRequest,
)
from app.schemas.response import ApiResponse
from app.services.documents import DocumentInputError, DocumentService
from app.services.financial_analysis import (
    FinancialAnalysisInputError,
    FinancialAnalysisService,
)
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi import Path as ApiPath

router = APIRouter()


def get_document_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentService:
    return DocumentService(settings)


def get_financial_analysis_service(
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FinancialAnalysisService:
    return FinancialAnalysisService(
        document_service,
        settings.financial_reconciliation_tolerance_rupees,
    )


@router.get("/health", response_model=ApiResponse)
def health_check() -> ApiResponse:
    return ApiResponse(
        success=True,
        data={"status": "ok"},
    )


@router.post("/documents", response_model=ApiResponse, status_code=201)
def upload_document(
    response: Response,
    file: Annotated[UploadFile, File()],
    service: Annotated[DocumentService, Depends(get_document_service)],
    document_type: Annotated[str | None, Form()] = None,
) -> ApiResponse:
    try:
        result = service.upload(
            file.file,
            file.filename,
            file.content_type,
            document_type,
        )
    except DocumentInputError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    finally:
        file.file.close()

    response.status_code = 200 if result.document.duplicate else 201
    return ApiResponse(
        success=True,
        data=result.model_dump(mode="json"),
    )


@router.get("/documents/{document_id}", response_model=ApiResponse)
def get_document(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> ApiResponse:
    metadata = service.get_metadata(document_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return ApiResponse(
        success=True,
        data=metadata.model_dump(mode="json"),
    )


@router.get("/documents/{document_id}/pages", response_model=ApiResponse)
def get_document_pages(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ApiResponse:
    _require_document(service, document_id)
    pages = service.get_pages(document_id)
    return ApiResponse(
        success=True,
        data={
            "items": [
                page.model_dump(mode="json") for page in pages[offset : offset + limit]
            ],
            "offset": offset,
            "limit": limit,
            "total": len(pages),
        },
    )


@router.get("/documents/{document_id}/tables", response_model=ApiResponse)
def get_document_tables(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ApiResponse:
    _require_document(service, document_id)
    tables = service.get_tables(document_id)
    return ApiResponse(
        success=True,
        data={
            "items": [
                table.model_dump(mode="json")
                for table in tables[offset : offset + limit]
            ],
            "offset": offset,
            "limit": limit,
            "total": len(tables),
        },
    )


@router.get("/documents/{document_id}/pages/{page_number}/image")
def get_document_page_image(
    document_id: str,
    page_number: Annotated[int, ApiPath(ge=1)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> Response:
    try:
        image = service.render_page(document_id, page_number)
    except DocumentInputError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.get(
    "/documents/{document_id}/financial-cell-reviews",
    response_model=ApiResponse,
)
def get_financial_cell_reviews(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> ApiResponse:
    _require_document(service, document_id)
    return ApiResponse(
        success=True,
        data=[
            review.model_dump(mode="json")
            for review in service.get_financial_cell_reviews(document_id)
        ],
    )


@router.get(
    "/documents/{document_id}/financial-facts",
    response_model=ApiResponse,
)
def get_financial_facts(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
    include_history: Annotated[bool, Query()] = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ApiResponse:
    _require_document(service, document_id)
    facts = service.get_financial_facts(
        document_id,
        include_history=include_history,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        success=True,
        data={
            "items": [fact.model_dump(mode="json") for fact in facts],
            "offset": offset,
            "limit": limit,
            "include_history": include_history,
        },
    )


@router.post(
    "/documents/{document_id}/pages/{page_number}/tables/{table_index}"
    "/cells/{row_index}/{column_index}/review",
    response_model=ApiResponse,
)
def review_financial_cell(
    document_id: str,
    page_number: Annotated[int, ApiPath(ge=1)],
    table_index: Annotated[int, ApiPath(ge=0)],
    row_index: Annotated[int, ApiPath(ge=0)],
    column_index: Annotated[int, ApiPath(ge=0)],
    request: FinancialCellReviewRequest,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> ApiResponse:
    try:
        review = service.review_financial_cell(
            document_id,
            page_number,
            table_index,
            row_index,
            column_index,
            request.confirmed_value,
        )
    except DocumentInputError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return ApiResponse(success=True, data=review.model_dump(mode="json"))


@router.post(
    "/documents/{document_id}/financial-analysis",
    response_model=ApiResponse,
)
def analyze_document_financials(
    document_id: str,
    request: FinancialAnalysisRequest,
    service: Annotated[
        FinancialAnalysisService,
        Depends(get_financial_analysis_service),
    ],
) -> ApiResponse:
    try:
        report: FinancialAnalysisReport = service.analyze(document_id, request)
    except FinancialAnalysisInputError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return ApiResponse(success=True, data=report.model_dump(mode="json"))


def _require_document(service: DocumentService, document_id: str) -> DocumentMetadata:
    metadata = service.get_metadata(document_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return metadata
