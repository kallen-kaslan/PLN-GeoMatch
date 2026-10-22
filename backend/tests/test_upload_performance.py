import os
import sys
import json

# Tambahkan path backend ke sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database import SessionLocal
from app.models.upload import UploadBatch, SourceRecord, DatasetType, BatchStatus
from app.modules.spatial.master_builder import build_combined_master
from app.modules.spatial.engine import run_spatial_matching_job

def test_mapping_persistence_and_extraction():
    """
    Memastikan mapping kolom custom di UploadBatch benar-benar digunakan
    oleh downstream logic (master builder) tanpa menulis ulang SourceRecord.
    """
    print("=== TEST: Mapping Persistence & Extraction ===")
    db = SessionLocal()
    try:
        # 1. Buat batch dengan nama kolom "aneh" (custom)
        batch = UploadBatch(
            filename="custom_cols.csv",
            dataset_type=DatasetType.PASCABAYAR,
            status=BatchStatus.COMPLETED,
            column_mapping={
                "idpel": "NOMOR_PELANGGAN_CUSTOM",
                "nama": "NAMA_USER_CUSTOM",
                "latitude": "KOORD_Y",
                "longitude": "KOORD_X",
                "tarif": "TARIF_PEL",
                "daya": "DAYA_PEL"
            }
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)

        # 2. Tambahkan data mentah sesuai kolom custom
        raw_data = {
            "NOMOR_PELANGGAN_CUSTOM": "530000000001",
            "NAMA_USER_CUSTOM": "BUDI CUSTOM",
            "KOORD_Y": -6.2,
            "KOORD_X": 106.8,
            "TARIF_PEL": "R1",
            "DAYA_PEL": 900,
            "TGL_BACA": "2023-10-01"
        }
        rec = SourceRecord(batch_id=batch.id, data=raw_data)
        db.add(rec)
        db.commit()

        print(f"✓ Created batch #{batch.id} with custom mapping")

        # 3. Jalankan Master Builder
        # Logic builder harus bisa mengekstrak data dari raw_data menggunakan mapping di batch
        res = build_combined_master(db, pascabayar_batch_ids=[batch.id], prabayar_batch_ids=[])

        assert res["total_master_clean"] >= 1, "Master builder gagal memproses baris dengan mapping custom"
        print(f"✓ Master builder sukses mengekstrak kolom custom: {res}")

        # Cleanup
        db.query(SourceRecord).filter(SourceRecord.batch_id == batch.id).delete()
        db.query(UploadBatch).filter(UploadBatch.id == batch.id).delete()
        db.commit()
        print("✓ Cleanup sukses")

    finally:
        db.close()

if __name__ == "__main__":
    test_mapping_persistence_and_extraction()
