import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.models.matching import ReconciliationProcess, ProcessStatus, ReviewStatus, MatchCandidate
from app.models.upload import UploadBatch, SourceRecord, DatasetType
from app.models.master_sisa import MasterSisaRecord
from app.modules.spatial.master_builder import build_combined_master
from app.modules.spatial.preparation import process_master_sisa_exclusion
from app.modules.spatial.engine import run_spatial_matching_job

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=2, default_retry_delay=5)
def execute_matching_task(
    self,
    process_id: int,
    process_name: str,
    target_batch_id: int,
    radius_meters: float = 100.0,
    max_candidates_per_target: int = 5
) -> Dict[str, Any]:
    """
    Background worker task untuk menjalankan pencocokan spasial Haversine.
    Menjaga process_id tunggal konsisten dari awal hingga selesai.
    """
    db = SessionLocal()
    try:
        process = db.query(ReconciliationProcess).filter(ReconciliationProcess.id == process_id).first()
        if not process:
            logger.error(f"[CELERY] Process #{process_id} tidak ditemukan.")
            return {"status": "failed", "detail": f"Process #{process_id} not found"}

        # Klaim proses dan ubah status ke RUNNING
        process.matching_status = ProcessStatus.RUNNING
        db.commit()

        # Jalankan pencocokan dengan process_id yang sama
        res = run_spatial_matching_job(
            db=db,
            process_name=process_name,
            target_batch_id=target_batch_id,
            radius_meters=radius_meters,
            max_candidates_per_target=max_candidates_per_target,
            process_id=process_id
        )

        logger.info(f"[CELERY] Task matching selesai untuk Process #{process_id}: {res}")
        return res

    except Exception as exc:
        db.rollback()
        logger.exception(f"[CELERY] Error pada matching task Process #{process_id}: {str(exc)}")
        try:
            p = db.query(ReconciliationProcess).filter(ReconciliationProcess.id == process_id).first()
            if p:
                p.matching_status = ProcessStatus.FAILED
                db.commit()
        except Exception:
            db.rollback()

        # Retry untuk error sementara
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"status": "failed", "error": "Internal processing error"}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=5)
def execute_batch_reconciliation_pipeline(
    self,
    process_id: int,
    pascabayar_batch_id: Optional[int],
    prabayar_batch_id: Optional[int],
    pdpj_batch_id: Optional[int],
    target_batch_id: Optional[int],
    radius_meters: float = 100.0
) -> Dict[str, Any]:
    """
    Background task untuk alur lengkap multi-dataset staged:
    1. Build Master Bersih
    2. Exclude PDPJ -> Master Sisa
    3. Spatial Matching -> Match Candidates
    Semua dijalankan di worker tanpa memblokir HTTP request.
    """
    db = SessionLocal()
    try:
        process = db.query(ReconciliationProcess).filter(ReconciliationProcess.id == process_id).first()
        if not process:
            logger.error(f"[CELERY] Pipeline Process #{process_id} tidak ditemukan.")
            return {"status": "failed", "detail": f"Process #{process_id} not found"}

        # Klaim status
        process.matching_status = ProcessStatus.RUNNING
        db.commit()

        paska_ids = [pascabayar_batch_id] if pascabayar_batch_id else []
        pra_ids = [prabayar_batch_id] if prabayar_batch_id else []

        if not paska_ids and not pra_ids:
            paska_ids = [b.id for b in db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PASCABAYAR).all()]
            pra_ids = [b.id for b in db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PRABAYAR).all()]

        # 1. Build Combined Master
        res_master = build_combined_master(db=db, pascabayar_batch_ids=paska_ids, prabayar_batch_ids=pra_ids)
        master_batch_id = res_master["master_batch_id"]

        # 2. Exclude PDPJ
        pdpj_id = pdpj_batch_id
        if not pdpj_id:
            pdpj_batch = db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PDPJ).first()
            if pdpj_batch:
                pdpj_id = pdpj_batch.id

        if pdpj_id:
            process_master_sisa_exclusion(db, master_batch_id, pdpj_id)
        else:
            m_records = db.query(SourceRecord).filter(SourceRecord.batch_id == master_batch_id).all()
            new_sisa = []
            for mr in m_records:
                mdata = mr.data or {}
                new_sisa.append(MasterSisaRecord(
                    idpel=mr.idpel or f"UNASSIGNED-{mr.id}",
                    nama=mdata.get("nama", "-"),
                    latitude=float(mdata.get("koordinat_y") or mdata.get("latitude") or 0),
                    longitude=float(mdata.get("koordinat_x") or mdata.get("longitude") or 0),
                    tarif=mdata.get("tarif", "-"),
                    daya=int(mdata.get("daya", 0)) if mdata.get("daya") else None,
                    jenis_layanan=mdata.get("jenis_pel", "PASCABAYAR")
                ))
            if new_sisa:
                db.bulk_save_objects(new_sisa)
                db.commit()

        # 3. Spatial Matching
        target_id = target_batch_id
        if not target_id:
            target_batch = db.query(UploadBatch).filter(
                UploadBatch.dataset_type.in_([DatasetType.KOORDINAT_KOSONG, DatasetType.TARGET])
            ).order_by(UploadBatch.id.desc()).first()
            if target_batch:
                target_id = target_batch.id

        if not target_id:
            process.matching_status = ProcessStatus.COMPLETED
            process.review_status = ReviewStatus.NOT_STARTED
            process.total_targets = 0
            process.matched_targets = 0
            process.unmatched_targets = 0
            process.completed_at = datetime.utcnow()
            db.commit()
            return {
                "process_id": process.id,
                "status": "completed",
                "message": "Master data selesai dibentuk. Tidak ada target koordinat kosong."
            }

        res = run_spatial_matching_job(
            db=db,
            process_name=process.process_name,
            target_batch_id=target_id,
            radius_meters=radius_meters,
            max_candidates_per_target=5,
            process_id=process.id
        )

        logger.info(f"[CELERY] Pipeline batch sukses untuk Process #{process_id}")
        return res

    except Exception as exc:
        db.rollback()
        logger.exception(f"[CELERY] Gagal pada pipeline batch Process #{process_id}: {str(exc)}")
        try:
            p = db.query(ReconciliationProcess).filter(ReconciliationProcess.id == process_id).first()
            if p:
                p.matching_status = ProcessStatus.FAILED
                db.commit()
        except Exception:
            db.rollback()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"status": "failed", "error": "Internal pipeline error"}
    finally:
        db.close()
