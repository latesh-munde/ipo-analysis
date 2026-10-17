from typing import Annotated

from app.core.config import Settings, get_settings
from app.schemas.documents import DocumentMetadata
from app.schemas.response import ApiResponse
from app.services.documents import DocumentInputError, DocumentService
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

router = APIRouter()


def get_document_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentService:
    return DocumentService(settings)


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


def _require_document(service: DocumentService, document_id: str) -> DocumentMetadata:
    metadata = service.get_metadata(document_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return metadata
