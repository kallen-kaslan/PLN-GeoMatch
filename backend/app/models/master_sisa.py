from sqlalchemy import Column, String, Float, Boolean, DateTime, Integer, ForeignKey
from datetime import datetime
from app.database import Base

class CleanedMasterRecord(Base):
    __tablename__ = "cleaned_master_records"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("upload_batches.id"))
    idpel = Column(String, index=True, nullable=False)
    nama = Column(String, nullable=True)
    tarif = Column(String, nullable=True)
    daya = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    periode = Column(String, nullable=True)
    is_excluded_by_pdpj = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class MasterSisaRecord(Base):
    __tablename__ = "master_sisa_records"

    id = Column(Integer, primary_key=True, index=True)
    idpel = Column(String, index=True, nullable=False)
    nama = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    tarif = Column(String, nullable=True)
    daya = Column(Integer, nullable=True)
    jenis_layanan = Column(String, default="PASCABAYAR") # PRABAYAR / PASCABAYAR
    created_at = Column(DateTime, default=datetime.utcnow)
