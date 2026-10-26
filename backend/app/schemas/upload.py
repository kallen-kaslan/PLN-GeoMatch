from datetime import datetime

from pydantic import BaseModel, Field

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
    column_mapping: dict[str, str]


class BatchProcessRequest(BaseModel):
    pdpj_review_id: int | None = Field(None, gt=0)
    dil_batch_id: int | None = None
    pascabayar_batch_id: int | None = None
    prabayar_batch_id: int | None = None
    pdpj_batch_id: int | None = None
    target_batch_id: int | None = None
    radius_meters: float = Field(100.0, gt=0, allow_inf_nan=False)
