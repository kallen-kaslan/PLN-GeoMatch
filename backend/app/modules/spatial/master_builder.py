"""
Modul Pembentukan Data Master (ACMT/RBM Pascabayar + LPB Prabayar)
Sesuai Action Plan PLN GeoMatch:
1. Cleaning data ACMT RBM multi-bulan agar tidak numpuk (ambil tglbaca mutakhir).
2. Cleaning data LPB multi-bulan agar tidak numpuk.
3. Gabungkan Paska + Pra menjadi Master (kolom: idpel, koordinat_x, koordinat_y, tglbaca, jenis_pel).
4. Auto-filter kolom sendiri (User-Oriented).
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.models.upload import UploadBatch, SourceRecord, BatchStatus, DatasetType
from app.models.master_sisa import CleanedMasterRecord, MasterSisaRecord

def normalize_column_name(col: str) -> str:
    """Membersihkan nama kolom: lowercase, hapus spasi/simbol untuk auto-filtering"""
    if not col:
        return ""
    return str(col).strip().lower().replace(" ", "").replace("_", "").replace("-", "")

def extract_standard_fields(row_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Auto-filter kolom user-oriented:
    Mengenali variasi nama kolom IDPEL, Koordinat X/Y (Lat/Long), Tgl Baca, Jenis Pel
    """
    normalized = {normalize_column_name(k): v for k, v in row_data.items() if v is not None}

    # 1. IDPEL
    idpel = None
    for alias in ["idpel", "idpelanggan", "nopelanggan", "customerid", "nometer"]:
        if alias in normalized and str(normalized[alias]).strip():
            idpel = str(normalized[alias]).strip()
            break

    # 2. Latitude (Y)
    lat = None
    for alias in ["latitudey", "latitude", "lat", "lintang", "koordinaty", "y"]:
        if alias in normalized:
            try:
                val = float(str(normalized[alias]).replace(",", "."))
                if val != 0:
                    lat = val
                    break
            except (ValueError, TypeError):
                continue

    # 3. Longitude (X)
    lon = None
    for alias in ["longitudex", "longitude", "long", "lon", "bujur", "koordinatx", "x"]:
        if alias in normalized:
            try:
                val = float(str(normalized[alias]).replace(",", "."))
                if val != 0:
                    lon = val
                    break
            except (ValueError, TypeError):
                continue

    # 4. Tanggal Baca / Periode
    tglbaca = None
    for alias in ["tglbaca", "tanggalbaca", "periode", "tgl", "bulan", "blth"]:
        if alias in normalized:
            tglbaca = str(normalized[alias]).strip()
            break

    # 5. Jenis Pelanggan (Paska / Pra)
    jenis_pel = None
    for alias in ["jenispelanggan", "jenispel", "layanan", "tarif", "produk"]:
        if alias in normalized:
            jenis_pel = str(normalized[alias]).strip()
            break

    # 6. Nama Pelanggan (opsional)
    nama = None
    for alias in ["namapelanggan", "nama", "customername"]:
        if alias in normalized:
            nama = str(normalized[alias]).strip()
            break

    # 7. Kode Gardu (untuk pencocokan gardu DIL)
    kode_gardu = None
    for alias in ["kodegardu", "gardu", "trafo", "idgardu"]:
        if alias in normalized:
            kode_gardu = str(normalized[alias]).strip()
            break

    return {
        "idpel": idpel,
        "lat": lat,
        "lon": lon,
        "tglbaca": tglbaca or "2026-01",
        "jenis_pel": jenis_pel or "PASCABAYAR",
        "nama": nama or "-",
        "kode_gardu": kode_gardu
    }

def build_combined_master(
    db: Session,
    pascabayar_batch_ids: List[int],
    prabayar_batch_ids: List[int]
) -> Dict[str, Any]:
    """
    Membersihkan data bertumpuk multi-bulan dari ACMT (pascabayar) dan LPB (prabayar),
    lalu menggabungkannya menjadi Master Terpadu.
    """
    # Dictionary deduplikasi: key = idpel, value = record terbaru
    dedup_master: Dict[str, Dict[str, Any]] = {}
    pascabayar_count = 0
    prabayar_count = 0

    # 1. Proses Data Pascabayar (ACMT / RBM)
    for batch_id in pascabayar_batch_ids:
        records = db.query(SourceRecord).filter(SourceRecord.batch_id == batch_id).all()
        for r in records:
            pascabayar_count += 1
            fields = extract_standard_fields(r.data or {})
            if not fields["idpel"] or fields["lat"] is None or fields["lon"] is None:
                continue

            idpel = fields["idpel"]
            fields["jenis_pel"] = "PASCABAYAR"

            # Jika sudah ada, bandingkan tglbaca/periode untuk ambil yang paling mutakhir
            if idpel in dedup_master:
                existing_tgl = str(dedup_master[idpel].get("tglbaca", ""))
                new_tgl = str(fields.get("tglbaca", ""))
                if new_tgl >= existing_tgl:
                    dedup_master[idpel] = fields
            else:
                dedup_master[idpel] = fields

    # 2. Proses Data Prabayar (LPB)
    for batch_id in prabayar_batch_ids:
        records = db.query(SourceRecord).filter(SourceRecord.batch_id == batch_id).all()
        for r in records:
            prabayar_count += 1
            fields = extract_standard_fields(r.data or {})
            if not fields["idpel"] or fields["lat"] is None or fields["lon"] is None:
                continue

            idpel = fields["idpel"]
            fields["jenis_pel"] = "PRABAYAR"

            # Deduplikasi
            if idpel in dedup_master:
                existing_tgl = str(dedup_master[idpel].get("tglbaca", ""))
                new_tgl = str(fields.get("tglbaca", ""))
                if new_tgl >= existing_tgl:
                    dedup_master[idpel] = fields
            else:
                dedup_master[idpel] = fields

    # Simpan hasil Master Bersih ke database
    # Buat Batch Master baru
    master_batch = UploadBatch(
        filename=f"Master_Gabungan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
        dataset_type=DatasetType.MASTER,
        status=BatchStatus.COMPLETED,
        total_rows=len(dedup_master)
    )
    db.add(master_batch)
    db.commit()
    db.refresh(master_batch)

    # Simpan source records hasil master
    new_records = []
    for idpel, data in dedup_master.items():
        rec = SourceRecord(
            batch_id=master_batch.id,
            idpel=idpel,
            data={
                "idpel": idpel,
                "koordinat_x": data["lon"],
                "koordinat_y": data["lat"],
                "latitude": data["lat"],
                "longitude": data["lon"],
                "tglbaca": data["tglbaca"],
                "jenis_pel": data["jenis_pel"],
                "nama": data["nama"],
                "kode_gardu": data.get("kode_gardu")
            }
        )
        new_records.append(rec)

    if new_records:
        db.bulk_save_objects(new_records)
    db.commit()

    return {
        "status": "success",
        "master_batch_id": master_batch.id,
        "total_pascabayar_raw": pascabayar_count,
        "total_prabayar_raw": prabayar_count,
        "total_master_clean": len(dedup_master),
        "removed_duplicates": (pascabayar_count + prabayar_count) - len(dedup_master)
    }
