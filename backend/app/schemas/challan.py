import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ChallanGenerateRequest(BaseModel):
    scan_id: uuid.UUID

class ChallanResponse(BaseModel):
    challan_id: uuid.UUID
    scan_id: uuid.UUID
    lmo_id: uuid.UUID | None = None
    pdf_url: str | None = None
    pdf_hash: str | None = None
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ChallanListResponse(BaseModel):
    items: list[ChallanResponse]
    total: int
    page: int
    page_size: int
