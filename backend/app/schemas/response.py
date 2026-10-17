from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel):
    success: bool
    data: Any = None
    error: ErrorDetail | None = None
    meta: dict[str, Any] = {}
