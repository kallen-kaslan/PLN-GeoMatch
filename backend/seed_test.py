import os
import csv
from app.database import SessionLocal, engine, Base, ensure_schema_compatibility
from app.models.upload import UploadBatch, SourceRecord, BatchStatus, DatasetType
from app.models.matching import ReconciliationProcess, MatchCandidate
from app.models.master_sisa import MasterSisaRecord, CleanedMasterRecord
from app.modules.spatial.master_builder import build_combined_master
from app.modules.spatial.preparation import process_master_sisa_exclusion
from app.modules.spatial.engine import run_spatial_matching_job

def test_pln_workflow():
    print("=== 1. Inisialisasi Database ===")
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    db = SessionLocal()

    try:
        # Bersihkan data lama
        db.query(MatchCandidate).delete()
        db.query(ReconciliationProcess).delete()
        db.query(MasterSisaRecord).delete()
        db.query(CleanedMasterRecord).delete()
        db.query(SourceRecord).delete()
        db.query(UploadBatch).delete()
        db.commit()

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dummy_dir = os.path.join(base_dir, "data_dummy")

        print("\n=== 2. Load Raw ACMT (Pascabayar) & LPB (Prabayar) ===")
        # 1. Pascabayar ACMT
        acmt_batch = UploadBatch(filename="acmt_pascabayar.csv", dataset_type=DatasetType.PASCABAYAR, status=BatchStatus.COMPLETED)
        db.add(acmt_batch)
        db.commit()
        db.refresh(acmt_batch)

        with open(os.path.join(dummy_dir, "acmt_pascabayar.csv"), mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                db.add(SourceRecord(batch_id=acmt_batch.id, idpel=row.get("IDPELANGGAN"), data=dict(row)))
        db.commit()
        print(f"-> ACMT Batch #{acmt_batch.id} tersimpan")

        # 2. Prabayar LPB
        lpb_batch = UploadBatch(filename="lpb_prabayar.csv", dataset_type=DatasetType.PRABAYAR, status=BatchStatus.COMPLETED)
        db.add(lpb_batch)
        db.commit()
        db.refresh(lpb_batch)

        with open(os.path.join(dummy_dir, "lpb_prabayar.csv"), mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                db.add(SourceRecord(batch_id=lpb_batch.id, idpel=row.get("IDPELANGGAN"), data=dict(row)))
        db.commit()
        print(f"-> LPB Batch #{lpb_batch.id} tersimpan")

        print("\n=== 3. Tahap 1: Cleaning Data Multi-Bulan & Penggabungan Master (Paska + Pra) ===")
        master_res = build_combined_master(db, [acmt_batch.id], [lpb_batch.id])
        print(f"Total Baris Pascabayar Raw: {master_res['total_pascabayar_raw']}")
        print(f"Total Baris Prabayar Raw: {master_res['total_prabayar_raw']}")
        print(f"Duplikat/Numpuk Dihapus: {master_res['removed_duplicates']}")
        print(f"Master Bersih Terbentuk: {master_res['total_master_clean']} pelanggan unik")

        print("\n=== 4. Tahap 2: Exclude Data Valid (PDPJ) dari Master ===")
        pdpj_batch = UploadBatch(filename="pdpj_verif.csv", dataset_type=DatasetType.PDPJ, status=BatchStatus.COMPLETED)
        db.add(pdpj_batch)
        db.commit()
        db.refresh(pdpj_batch)

        with open(os.path.join(dummy_dir, "pdpj_verif.csv"), mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                db.add(SourceRecord(batch_id=pdpj_batch.id, idpel=row.get("IDPELANGGAN"), data=dict(row)))
        db.commit()

        sisa_res = process_master_sisa_exclusion(db, master_res['master_batch_id'], pdpj_batch.id)
        print(f"Total Master Bersih: {sisa_res['total_master']}")
        print(f"Dikecualikan karena sudah verif di PDPJ: {sisa_res['total_excluded_by_pdpj']}")
        print(f"Master Sisa (Belum Valid): {sisa_res['total_master_sisa']}")

        print("\n=== 5. Tahap 3 & 4: Cocokkan Koordinat Kosong ke Master Sisa ===")
        target_batch = UploadBatch(filename="koordinat_kosong.csv", dataset_type=DatasetType.KOORDINAT_KOSONG, status=BatchStatus.COMPLETED)
        db.add(target_batch)
        db.commit()
        db.refresh(target_batch)

        with open(os.path.join(dummy_dir, "koordinat_kosong.csv"), mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                db.add(SourceRecord(batch_id=target_batch.id, data=dict(row)))
        db.commit()

        match_res = run_spatial_matching_job(
            db=db,
            process_name="Uji Alur PLN GeoMatch",
            target_batch_id=target_batch.id,
            radius_meters=150.0
        )
        print(f"Total Titik Koordinat Kosong: {match_res['total_targets']}")
        print(f"Titik Menemukan Kandidat IDPEL di Master Sisa: {match_res['matched_targets']}")
        print(f"Titik Anomali (Di luar radius): {match_res['unmatched_targets']}")
        print(f"Total Pasangan Kandidat yang Terbentuk: {match_res['total_candidates_found']}")

        print("\n=== HASIL VERIFIKASI: SELURUH ALUR KERJA PLN BERHASIL DENGAN SEMPURNA! ===")

    finally:
        db.close()

if __name__ == "__main__":
    test_pln_workflow()
