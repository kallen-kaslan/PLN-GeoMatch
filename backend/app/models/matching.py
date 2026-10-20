from sqlalchemy import Column, String, Float, DateTime, Integer, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base

class ProcessStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ReviewStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    FINALIZED = "finalized"

class ReconciliationProcess(Base):
    __tablename__ = "reconciliation_processes"

    id = Column(Integer, primary_key=True, index=True)
    process_name = Column(String, nullable=False)
    radius_meters = Column(Float, default=50.0)
    matching_status = Column(Enum(ProcessStatus), default=ProcessStatus.QUEUED)
    review_status = Column(Enum(ReviewStatus), default=ReviewStatus.NOT_STARTED)

    total_targets = Column(Integer, default=0)
    matched_targets = Column(Integer, default=0)
    unmatched_targets = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    candidates = relationship("MatchCandidate", back_populates="process", cascade="all, delete-orphan")

class MatchCandidate(Base):
    __tablename__ = "match_candidates"

    id = Column(Integer, primary_key=True, index=True)
    process_id = Column(Integer, ForeignKey("reconciliation_processes.id"))

    target_ref = Column(String, nullable=False)
    target_lat = Column(Float, nullable=False)
    target_lon = Column(Float, nullable=False)

    candidate_idpel = Column(String, nullable=False)
    candidate_nama = Column(String, nullable=True)
    candidate_lat = Column(Float, nullable=False)
    candidate_lon = Column(Float, nullable=False)

    distance_meters = Column(Float, nullable=False)
    rank = Column(Integer, default=1)

    # Status kelengkapan data & klasifikasi pelanggan
    jenis_layanan = Column(String, default="PASCABAYAR") # PRABAYAR / PASCABAYAR
    validity_status = Column(String, default="VALID") # VALID (ada IDPEL + Coord), PERLU_KONFIRMASI_IDPEL (tanpa IDPEL)
    is_under_5m = Column(Integer, default=0) # 1 jika jarak < 5 meter (indikasi rumah berdampingan/sama)

    is_accepted = Column(Integer, default=0)

    process = relationship("ReconciliationProcess", back_populates="candidates")
