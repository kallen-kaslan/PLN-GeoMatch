from sqlalchemy import Column, String, JSON, DateTime, Enum, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base

class BatchStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    NEEDS_MAPPING = "needs_mapping"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DatasetType(str, enum.Enum):
    PASCABAYAR = "pascabayar"       # ACMT / RBM (Pascabayar)
    PRABAYAR = "prabayar"           # LPB (Prabayar)
    MASTER = "master"               # Gabungan Pascabayar + Prabayar
    PDPJ = "pdpj"                   # Data yang sudah verif
    KOORDINAT_KOSONG = "koordinat_kosong" # Target lapangan IDPEL kosong/tidak ditemukan
    TARGET = "target"               # Alias kompatibilitas target

class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    dataset_type = Column(Enum(DatasetType))
    status = Column(Enum(BatchStatus), default=BatchStatus.UPLOADED)
    column_mapping = Column(JSON, nullable=True)
    total_rows = Column(Integer, default=0)
    valid_rows = Column(Integer, default=0)
    error_rows = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    records = relationship("SourceRecord", back_populates="batch", cascade="all, delete-orphan")

class SourceRecord(Base):
    __tablename__ = "source_records"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("upload_batches.id"))
    data = Column(JSON)
    idpel = Column(String, index=True, nullable=True)

    batch = relationship("UploadBatch", back_populates="records")
