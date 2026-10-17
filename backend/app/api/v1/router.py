from app.schemas.response import ApiResponse
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", response_model=ApiResponse)
def health_check() -> ApiResponse:
    return ApiResponse(
        success=True,
        data={"status": "ok"},
    )
