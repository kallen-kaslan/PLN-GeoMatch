from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any
from ..models.upload import BatchStatus, DatasetType

class UploadBatchBase(BaseModel):
    filename: str
    dataset_type: DatasetType

class UploadBatchResponse(UploadBatchBase):
    id: int
    status: BatchStatus
    total_rows: int
    created_at: datetime

    class Config:
        from_attributes = True

class MappingRequest(BaseModel):
    batch_id: int
    column_mapping: Dict[str, str]
