from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IPO Analysis System"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    document_storage_dir: Path = Path("data/documents")
    document_max_upload_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    document_max_pages: int = Field(default=2000, gt=0)
    document_ocr_enabled: bool = False
    document_ocr_language: str = "eng"
    document_ocr_tesseract_path: str = "tesseract"
    document_ocr_timeout_seconds: int = Field(default=30, gt=0)
    document_ocr_dpi: int = Field(default=200, ge=72, le=600)
    document_low_text_char_threshold: int = Field(default=40, ge=0)
    financial_reconciliation_tolerance_rupees: Decimal = Field(
        default=Decimal("1"),
        ge=0,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
