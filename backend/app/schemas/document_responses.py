from app.schemas.documents import DocumentMetadata
from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document: DocumentMetadata
    page_count: int
    table_count: int
