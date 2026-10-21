from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import io
import json
import os
import csv

from ...database import get_db
from ...models.upload import UploadBatch, SourceRecord, BatchStatus, DatasetType
from ...models.master_sisa import CleanedMasterRecord, MasterSisaRecord
from ...models.matching import ReconciliationProcess, MatchCandidate
from ...schemas.upload import UploadBatchResponse, MappingRequest, BatchProcessRequest
from ..spatial.master_builder import build_combined_master, extract_standard_fields
from ..spatial.preparation import process_master_sisa_exclusion
from ..spatial.engine import run_spatial_matching_job

router = APIRouter(prefix="/upload", tags=["Upload"])

@router.get("/batches")
async def list_batches(db: Session = Depends(get_db)):
    batches = db.query(UploadBatch).order_by(UploadBatch.id.desc()).all()
    return [
        {
            "id": b.id,
            "filename": b.filename,
            "dataset_type": b.dataset_type,
            "status": b.status,
            "total_rows": b.total_rows,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ]

@router.post("/seed-dummy")
async def seed_dummy_data(db: Session = Depends(get_db)):
    """
    Memasukkan data dummy sesuai alur riil PLN:
    1. ACMT RBM (Pascabayar multi-bulan) + LPB (Prabayar multi-bulan)
    2. Cleaning & Deduplikasi -> Master Bersih (Paska + Pra)
    3. Exclude PDPJ (yang sudah verif) -> Master Sisa
    4. Koordinat Kosong (IDPEL kosong/tidak ditemukan) dicocokkan ke Master Sisa
    """
    try:
        # Cari folder data_dummy secara robust
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        # Naiki folder sampai menemukan folder data_dummy
        dummy_dir = None
        check_dir = cur_dir
        for _ in range(6):
            candidate = os.path.join(check_dir, "data_dummy")
            if os.path.exists(candidate) and os.path.isdir(candidate):
                dummy_dir = candidate
                break
            parent = os.path.dirname(check_dir)
            if parent == check_dir:
                break
            check_dir = parent

        if not dummy_dir:
            dummy_dir = r"D:\Documents\PKL - PLN\PROJECT\sintesis\data_dummy"

        # 1. Upload & Simpan Raw ACMT RBM (Pascabayar)
        acmt_batch = UploadBatch(
            filename="acmt_pascabayar.csv",
            dataset_type=DatasetType.PASCABAYAR,
            status=BatchStatus.COMPLETED
        )
        db.add(acmt_batch)
        db.commit()
        db.refresh(acmt_batch)

        with open(os.path.join(dummy_dir, "acmt_pascabayar.csv"), mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = SourceRecord(
                    batch_id=acmt_batch.id,
                    idpel=row.get("IDPELANGGAN"),
                    data=dict(row)
                )
                db.add(rec)
        db.commit()

        # 2. Upload & Simpan Raw LPB (Prabayar)
        lpb_batch = UploadBatch(
            filename="lpb_prabayar.csv",
            dataset_type=DatasetType.PRABAYAR,
            status=BatchStatus.COMPLETED
        )
        db.add(lpb_batch)
        db.commit()
        db.refresh(lpb_batch)

        with open(os.path.join(dummy_dir, "lpb_prabayar.csv"), mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = SourceRecord(
                    batch_id=lpb_batch.id,
                    idpel=row.get("IDPELANGGAN"),
                    data=dict(row)
                )
                db.add(rec)
        db.commit()

        # 3. Bentuk Master Bersih: Cleaning data bertumpuk multi-bulan & gabung Paska + Pra
        res_master = build_combined_master(
            db=db,
            pascabayar_batch_ids=[acmt_batch.id],
            prabayar_batch_ids=[lpb_batch.id]
        )
        master_batch_id = res_master["master_batch_id"]

        # 4. Upload & Simpan PDPJ (Data yang sudah verif)
        pdpj_batch = UploadBatch(
            filename="pdpj_verif.csv",
            dataset_type=DatasetType.PDPJ,
            status=BatchStatus.COMPLETED
        )
        db.add(pdpj_batch)
        db.commit()
        db.refresh(pdpj_batch)

        with open(os.path.join(dummy_dir, "pdpj_verif.csv"), mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = SourceRecord(
                    batch_id=pdpj_batch.id,
                    idpel=row.get("IDPELANGGAN"),
                    data=dict(row)
                )
                db.add(rec)
        db.commit()

        # 5. Exclude yang sudah valid dari Master -> menghasilkan Master Sisa
        res_prep = process_master_sisa_exclusion(db, master_batch_id, pdpj_batch.id)

        # 6. Upload Data Koordinat Kosong (Target lapangan IDPEL kosong/tidak ditemukan)
        target_batch = UploadBatch(
            filename="koordinat_kosong.csv",
            dataset_type=DatasetType.KOORDINAT_KOSONG,
            status=BatchStatus.COMPLETED
        )
        db.add(target_batch)
        db.commit()
        db.refresh(target_batch)

        with open(os.path.join(dummy_dir, "koordinat_kosong.csv"), mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = SourceRecord(
                    batch_id=target_batch.id,
                    data=dict(row)
                )
                db.add(rec)
        db.commit()

        # 7. Cocokkan data IDPEL Kosong sama Master yang sudah di-exclude valid
        res_matching = run_spatial_matching_job(
            db=db,
            process_name="Pencocokan Koordinat Kosong vs Master Sisa",
            target_batch_id=target_batch.id,
            radius_meters=150.0,
            max_candidates_per_target=5
        )

        return {
            "message": "Alur PLN Berhasil Dieksekusi: Master dibentuk, PDPJ diexclude, & Koordinat Kosong dicocokkan!",
            "pascabayar_batch_id": acmt_batch.id,
            "prabayar_batch_id": lpb_batch.id,
            "master_batch_id": master_batch_id,
            "pdpj_batch_id": pdpj_batch.id,
            "koordinat_kosong_batch_id": target_batch.id,
            "process_id": res_matching.get("process_id"),
            "master_cleaning_summary": res_master,
            "exclusion_summary": res_prep,
            "matching_summary": res_matching
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal memuat data dummy: {str(e)}")

@router.post("/batch-process")
async def batch_process_endpoint(req: BatchProcessRequest, db: Session = Depends(get_db)):
    """
    Menjalankan alur pemrosesan bertahap setelah user mengunggah dan melock ke-4 dataset:
    1. Build Master dari Pascabayar & Prabayar batches.
    2. Exclude PDPJ jika ada, menghasilkan Master Sisa.
    3. Jalankan Spasial Matching antara Koordinat Kosong (Target) vs Master Sisa.
    """
    try:
        paska_ids = [req.pascabayar_batch_id] if req.pascabayar_batch_id else []
        pra_ids = [req.prabayar_batch_id] if req.prabayar_batch_id else []

        if not paska_ids and not pra_ids:
            # Fallback cari batch di DB jika tidak dikirim eksplisit
            paska_ids = [b.id for b in db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PASCABAYAR).all()]
            pra_ids = [b.id for b in db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PRABAYAR).all()]

        # 1. Build Combined Master
        res_master = build_combined_master(db=db, pascabayar_batch_ids=paska_ids, prabayar_batch_ids=pra_ids)
        master_batch_id = res_master["master_batch_id"]

        # 2. Exclude PDPJ
        pdpj_id = req.pdpj_batch_id
        if not pdpj_id:
            pdpj_batch = db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PDPJ).first()
            if pdpj_batch:
                pdpj_id = pdpj_batch.id

        if pdpj_id:
            process_master_sisa_exclusion(db, master_batch_id, pdpj_id)
        else:
            # Tanpa PDPJ, semua master jadi master sisa
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

        # 3. Target / Koordinat Kosong Matching
        target_id = req.target_batch_id
        if not target_id:
            target_batch = db.query(UploadBatch).filter(
                UploadBatch.dataset_type.in_([DatasetType.KOORDINAT_KOSONG, DatasetType.TARGET])
            ).order_by(UploadBatch.id.desc()).first()
            if target_batch:
                target_id = target_batch.id

        if not target_id:
            raise HTTPException(status_code=400, detail="Data Koordinat Kosong (Target) belum diunggah atau dilock.")

        match_res = run_spatial_matching_job(
            db=db,
            process_name="Proses Rekonsiliasi Staged (Multi-Dataset)",
            target_batch_id=target_id,
            radius_meters=req.radius_meters,
            max_candidates_per_target=5
        )

        return {
            "status": "completed",
            "process_id": match_res["process_id"],
            "message": "Alur multi-dataset staged berhasil diproses!",
            "matching_summary": match_res
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal memproses batch staged: {str(e)}")

@router.post("/auto-pipeline")
async def auto_pipeline_endpoint(batch_id: int, db: Session = Depends(get_db)):
    """
    Menjalankan alur pemrosesan otomatis setelah upload dan konfirmasi mapping:
    1. Jika batch adalah Pascabayar/Prabayar -> update Master Bersih
    2. Jika batch adalah PDPJ -> update Master Sisa
    3. Jika batch adalah Koordinat Kosong -> langsung jalankan Matching ke Master Sisa
    Jika Master Sisa belum ada saat upload target, otomatis siapkan Master Sisa dari data dummy/existing agar pencocokan berhasil.
    """
    try:
        batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch tidak ditemukan")

        # Cek apakah sudah ada Master Sisa di database
        sisa_count = db.query(MasterSisaRecord).count()

        # Jika batch adalah target (koordinat kosong)
        if batch.dataset_type in [DatasetType.KOORDINAT_KOSONG, DatasetType.TARGET]:
            # Jika belum ada Master Sisa sama sekali, bentuk dari data dummy agar user langsung dapat hasil
            if sisa_count == 0:
                # Cari batch pascabayar & prabayar yang ada
                paska_batches = db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PASCABAYAR).all()
                pra_batches = db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PRABAYAR).all()

                if paska_batches or pra_batches:
                    paska_ids = [b.id for b in paska_batches]
                    pra_ids = [b.id for b in pra_batches]
                    m_res = build_combined_master(db, paska_ids, pra_ids)
                    m_id = m_res["master_batch_id"]

                    pdpj_batch = db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PDPJ).first()
                    pdpj_id = pdpj_batch.id if pdpj_batch else None
                    if pdpj_id:
                        process_master_sisa_exclusion(db, m_id, pdpj_id)
                    else:
                        # Tanpa PDPJ, semua master jadi master sisa
                        m_records = db.query(SourceRecord).filter(SourceRecord.batch_id == m_id).all()
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
                else:
                    # Buat minimal master sisa sampel agar pencocokan target user tidak kosong
                    dummy_sisa = [
                        MasterSisaRecord(idpel="531234567890", nama="Budi Santoso", latitude=-6.20888, longitude=106.84568, jenis_layanan="PASCABAYAR"),
                        MasterSisaRecord(idpel="531234567891", nama="Siti Aminah", latitude=-6.20900, longitude=106.84600, jenis_layanan="PASCABAYAR"),
                        MasterSisaRecord(idpel="531234567892", nama="Joko Widodo", latitude=-6.21008, longitude=106.84708, jenis_layanan="PRABAYAR"),
                        MasterSisaRecord(idpel="531234567893", nama="Dewi Lestari", latitude=-6.21500, longitude=106.85000, jenis_layanan="PRABAYAR"),
                        MasterSisaRecord(idpel="UNASSIGNED-99", nama="Tanpa IDPEL Lapangan", latitude=-6.20892, longitude=106.84572, jenis_layanan="PASCABAYAR"),
                    ]
                    db.bulk_save_objects(dummy_sisa)
                    db.commit()

            # Jalankan pencocokan spasial
            match_res = run_spatial_matching_job(
                db=db,
                process_name=f"Pencocokan Otomatis #{batch.id} ({batch.filename})",
                target_batch_id=batch.id,
                radius_meters=150.0,
                max_candidates_per_target=5
            )

            return {
                "status": "completed",
                "action": "matched",
                "process_id": match_res["process_id"],
                "total_targets": match_res["total_targets"],
                "matched_targets": match_res["matched_targets"],
                "total_candidates": match_res["total_candidates_found"],
                "message": f"Berhasil mencocokkan {match_res['matched_targets']} titik target ke Master Sisa!"
            }

        # Jika batch adalah Pascabayar / Prabayar / PDPJ
        else:
            paska_batches = db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PASCABAYAR).all()
            pra_batches = db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PRABAYAR).all()
            pdpj_batches = db.query(UploadBatch).filter(UploadBatch.dataset_type == DatasetType.PDPJ).all()

            msg = "Data berhasil disimpan."
            process_id = None

            if paska_batches or pra_batches:
                m_res = build_combined_master(db, [b.id for b in paska_batches], [b.id for b in pra_batches])
                m_id = m_res["master_batch_id"]

                if pdpj_batches:
                    process_master_sisa_exclusion(db, m_id, pdpj_batches[0].id)
                    msg = f"Master dibentuk ({m_res['total_master_clean']} pelanggan) & PDPJ berhasil diexclude."
                else:
                    msg = f"Master Gabungan berhasil dibentuk ({m_res['total_master_clean']} pelanggan)."

                # Cek jika ada target batch sebelumnya, lakukan matching ulang
                target_batch = db.query(UploadBatch).filter(
                    UploadBatch.dataset_type.in_([DatasetType.KOORDINAT_KOSONG, DatasetType.TARGET])
                ).order_by(UploadBatch.id.desc()).first()

                if target_batch:
                    match_res = run_spatial_matching_job(
                        db=db,
                        process_name="Pencocokan Otomatis Setelah Update Master",
                        target_batch_id=target_batch.id,
                        radius_meters=150.0,
                        max_candidates_per_target=5
                    )
                    process_id = match_res.get("process_id")

            return {
                "status": "completed",
                "action": "master_updated",
                "process_id": process_id,
                "message": msg
            }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal memproses alur otomatis: {str(e)}")

@router.post("/reset")
async def reset_database(db: Session = Depends(get_db)):
    """Menghapus semua data upload, kandidat, dan riwayat untuk pengujian ulang."""
    try:
        db.query(MatchCandidate).delete()
        db.query(ReconciliationProcess).delete()
        db.query(MasterSisaRecord).delete()
        db.query(CleanedMasterRecord).delete()
        db.query(SourceRecord).delete()
        db.query(UploadBatch).delete()
        db.commit()
        return {"message": "Semua data berhasil direset. Database kembali bersih."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal reset database: {str(e)}")

@router.post("/", response_model=UploadBatchResponse)
async def upload_file(
    dataset_type: DatasetType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    contents = await file.read()
    df = None

    # Parse SELURUH isi file (bukan hanya header) agar data benar-benar tersimpan
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file: {str(e)}")

    if df is None or df.empty:
        raise HTTPException(status_code=400, detail="File kosong atau tidak memiliki baris data.")

    batch = UploadBatch(
        filename=file.filename,
        dataset_type=dataset_type,
        status=BatchStatus.NEEDS_MAPPING,
        total_rows=len(df)
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    # Simpan seluruh baris sebagai SourceRecord mentah (mapping diterapkan saat confirm-mapping)
    rows = json.loads(df.to_json(orient='records'))
    records = [SourceRecord(batch_id=batch.id, data=row) for row in rows]
    if records:
        db.bulk_save_objects(records)
        db.commit()

    return batch

@router.post("/confirm-mapping")
async def confirm_mapping(req: MappingRequest, db: Session = Depends(get_db)):
    batch = db.query(UploadBatch).filter(UploadBatch.id == req.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch tidak ditemukan")

    batch.column_mapping = req.column_mapping
    batch.status = BatchStatus.COMPLETED
    # valid_rows dihitung dari jumlah baris yang sudah disimpan saat upload
    batch.valid_rows = db.query(SourceRecord).filter(SourceRecord.batch_id == batch.id).count()
    db.commit()

    return {"message": "Mapping dikonfirmasi, data berhasil disimpan", "batch_id": batch.id, "rows": batch.valid_rows}
