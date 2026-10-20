import os
import csv
import random
from datetime import datetime, timedelta

from app.database import SessionLocal, engine, Base, ensure_schema_compatibility
from app.models.upload import UploadBatch, SourceRecord, BatchStatus, DatasetType
from app.models.matching import ReconciliationProcess, MatchCandidate
from app.models.master_sisa import MasterSisaRecord, CleanedMasterRecord
from app.modules.spatial.master_builder import build_combined_master
from app.modules.spatial.preparation import process_master_sisa_exclusion
from app.modules.spatial.engine import run_spatial_matching_job

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_dummy")

# Skala data dummy via environment variable (default kecil untuk uji cepat).
PASCA_COUNT = int(os.getenv("SEED_PASCA_COUNT", "30"))
PRA_COUNT = int(os.getenv("SEED_PRA_COUNT", "30"))
PDPJ_COUNT = int(os.getenv("SEED_PDPJ_COUNT", "12"))
TARGET_COUNT = int(os.getenv("SEED_TARGET_COUNT", "20"))

BASE_LAT = -6.20888
BASE_LON = 106.84568

NAMA_PASCA = [
    "Budi Santoso", "Siti Aminah", "Ahmad Dahlan", "Dewi Lestari", "Joko Widodo",
    "Rina Marlina", "Agus Setiawan", "Maya Sari", "Hadi Purnama", "Lestari Wulandari",
    "Dedi Kurniawan", "Putri Indah", "Bambang Wijaya", "Intan Permata", "Eko Prasetyo",
    "Nadia Aziz", "Fauzi Hasan", "Sari Dewi", "Rizal Ramadhan", "Citra Lestari",
]
NAMA_PRA = [
    "Andi Saputra", "Laila Fitri", "Tegar Prakoso", "Riska Maulida", "Dimas Arya",
    "Vera Oktavia", "Rifki Anwar", "Salma Aulia", "Yoga Pratama", "Febriani",
    "Irfan Maulana", "Tiara Ramadhani", "Zaki Falah", "Nabila", "Ardiansyah",
]
TARIF = ["R1", "R1T", "B1", "B2", "R3"]
DAYA = [450, 900, 1300, 2200]
STATUS_BAYAR = ["LUNAS", "BELUM", "PARSIAL"]
PERIODES = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03"]
KETERANGAN_TARGET = [
    "Tiang depan pagar - IDPEL pudar / belum tercatat",
    "Rumah baru baru direnovasi, IDPEL belum dicetak",
    "Dekat gardu trafo - koordinat lapangan hilang",
    "Pencatatan IDPEL di lapangan rusak",
    "Titik verifikasi anomaly luar jangkauan",
]

random.seed(42)


def offset_coord(base, spread=0.0025):
    return round(base + random.uniform(-spread, spread), 6)


def ensure_dir():
    os.makedirs(SEED_DIR, exist_ok=True)


def write_csv(filename, header, rows):
    path = os.path.join(SEED_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def generate_acmt(count):
    """Pascabayar multi-bulan: beberapa IDPEL muncul 2x dengan tanggal berbeda (uji dedup)."""
    header = ["IDPELANGGAN", "NAMA_PELANGGAN", "LATITUDE", "LONGITUDE",
              "STATUS_BAYAR", "TANGGAL_BAYAR", "TARIF", "DAYA"]
    rows = []
    for i in range(count):
        idpel = f"53123456{(900 + i):03d}"
        nama = NAMA_PASCA[i % len(NAMA_PASCA)]
        lat = offset_coord(BASE_LAT)
        lon = offset_coord(BASE_LON)
        status = random.choice(STATUS_BAYAR)
        tgl = (datetime(2026, 1, 1) + timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%d")
        rows.append([idpel, nama, lat, lon, status, tgl,
                     random.choice(TARIF), random.choice(DAYA)])
        # Duplikat sengaja untuk sebagian pelanggan (multi-bulan, koordinat bergeser sedikit)
        if i % 5 == 0 and i > 0:
            rows.append([
                idpel, nama + " (Update)", offset_coord(lat, 0.0003),
                offset_coord(lon, 0.0003), status,
                (datetime(2026, 2, 1) + timedelta(days=random.randint(0, 28))).strftime("%Y-%m-%d"),
                random.choice(TARIF), random.choice(DAYA)
            ])
    return header, rows


def generate_lpb(count):
    """Prabayar multi-bulan: koordinat dan tarif bervariasi per pelanggan."""
    header = ["IDPELANGGAN", "NAMA_PELANGGAN", "TARIF", "DAYA",
              "LATITUDE", "LONGITUDE", "PERIODE"]
    rows = []
    for i in range(count):
        idpel = f"53123457{(100 + i):03d}"
        nama = NAMA_PRA[i % len(NAMA_PRA)]
        rows.append([
            idpel, nama, random.choice(TARIF), random.choice(DAYA),
            offset_coord(BASE_LAT), offset_coord(BASE_LON), random.choice(PERIODES)
        ])
        if i % 6 == 0 and i > 0:
            rows.append([
                idpel, nama + " (Update Bulan)", random.choice(TARIF),
                random.choice(DAYA), offset_coord(BASE_LAT, 0.0005),
                offset_coord(BASE_LON, 0.0005), random.choice(PERIODES)
            ])
    return header, rows


def generate_pdpj_verif(count):
    """PDPJ: meter yang sudah terverifikasi (akan diexclude dari master sisa)."""
    header = ["NOAGENDA", "IDPELANGGAN", "VERIF", "JENISPELANGGAN",
              "LATITUDEY", "LONGITUDEX"]
    rows = []
    for i in range(count):
        idpel = f"53123456{(900 + (i * 3)):03d}"
        rows.append([
            f"AGD-2026-{i:03d}", idpel, "1", random.choice(["PASCABAYAR", "PRABAYAR"]),
            offset_coord(BASE_LAT), offset_coord(BASE_LON)
        ])
    return header, rows


def generate_koordinat_kosong(count):
    """Target lapangan: sebagian tanpa IDPEL, sebagian dengan IDPEL palsu/tidak terdaftar."""
    header = ["NOAGENDA", "IDPELANGGAN", "VERIF", "JENISPELANGGAN",
              "LATITUDEY", "LONGITUDEX", "KETERANGAN"]
    rows = []
    for i in range(count):
        idpel = "" if i % 3 != 0 else f"53123499{(i):03d}"
        rows.append([
            f"NK-2026-{i:03d}", idpel, "0", random.choice(["PASCABAYAR", "PRABAYAR"]),
            offset_coord(BASE_LAT), offset_coord(BASE_LON),
            random.choice(KETERANGAN_TARGET)
        ])
    return header, rows


def generate_target_lapangan(count):
    """Titik target koordinat kosong untuk pencocokan spasial ke master sisa."""
    header = ["NOMOR_METER", "LATITUDEY", "LONGITUDEX", "KETERANGAN"]
    rows = []
    for i in range(count):
        rows.append([
            f"MTR-KOSONG-{(i + 1):03d}",
            offset_coord(BASE_LAT),
            offset_coord(BASE_LON),
            random.choice(KETERANGAN_TARGET)
        ])
    return header, rows


def generate_all_dummy():
    ensure_dir()
    files = {
        "acmt_pascabayar.csv": generate_acmt(PASCA_COUNT),
        "lpb_prabayar.csv": generate_lpb(PRA_COUNT),
        "pdpj_verif.csv": generate_pdpj_verif(PDPJ_COUNT),
        "koordinat_kosong.csv": generate_koordinat_kosong(TARGET_COUNT),
        "target_lapangan.csv": generate_target_lapangan(TARGET_COUNT),
    }
    for filename, (header, rows) in files.items():
        write_csv(filename, header, rows)
        print(f"[SEED] Menulis {filename}: {len(rows)} baris")
    return files


def test_pln_workflow():
    print("=" * 60)
    print("PERINGATAN: seed_test.py akan MENGHAPUS semua data existing")
    print("pada tabel upload_batches, source_records, master_sisa_records,")
    print("cleaned_master_records, reconciliation_processes, dan match_candidates")
    print("sebelum memasukkan data dummy baru.")
    print("=" * 60)

    print("\n=== 0. Generate Data Dummy (Variatif & Skalabel) ===")
    generate_all_dummy()
    print(f"Skala: pascabayar={PASCA_COUNT}, prabayar={PRA_COUNT}, "
          f"pdpj={PDPJ_COUNT}, target={TARGET_COUNT}")
    print("Ubah jumlah via env, contoh: SEED_PASCA_COUNT=100 SEED_TARGET_COUNT=50 python seed_test.py")

    print("\n=== 1. Inisialisasi Database ===")
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
        acmt_batch = UploadBatch(filename="acmt_pascabayar.csv", dataset_type=DatasetType.PASCABAYAR, status=BatchStatus.COMPLETED)
        db.add(acmt_batch)
        db.commit()
        db.refresh(acmt_batch)

        with open(os.path.join(dummy_dir, "acmt_pascabayar.csv"), mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                db.add(SourceRecord(batch_id=acmt_batch.id, idpel=row.get("IDPELANGGAN"), data=dict(row)))
        db.commit()
        print(f"-> ACMT Batch #{acmt_batch.id} tersimpan")

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
        target_batch = UploadBatch(filename="target_lapangan.csv", dataset_type=DatasetType.KOORDINAT_KOSONG, status=BatchStatus.COMPLETED)
        db.add(target_batch)
        db.commit()
        db.refresh(target_batch)

        with open(os.path.join(dummy_dir, "target_lapangan.csv"), mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                db.add(SourceRecord(batch_id=target_batch.id, data=dict(row)))
        db.commit()

        match_res = run_spatial_matching_job(
            db=db,
            process_name="Uji Alur PLN GeoMatch (Dummy Variatif)",
            target_batch_id=target_batch.id,
            radius_meters=150.0
        )
        print(f"Total Titik Koordinat Kosong: {match_res['total_targets']}")
        print(f"Titik Menemukan Kandidat IDPEL di Master Sisa: {match_res['matched_targets']}")
        print(f"Titik Anomali (Di luar radius): {match_res['unmatched_targets']}")
        print(f"Total Pasangan Kandidat yang Terbentuk: {match_res['total_candidates_found']}")

        print("\n=== HASIL VERIFIKASI: SELURUH ALUR KERJA PLN BERHASIL ===")

    finally:
        db.close()


if __name__ == "__main__":
    test_pln_workflow()
