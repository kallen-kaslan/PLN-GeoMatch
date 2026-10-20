from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.models.master_sisa import CleanedMasterRecord, MasterSisaRecord
from app.models.upload import UploadBatch, SourceRecord, DatasetType
from app.modules.spatial.master_builder import normalize_column_name

def process_master_sisa_exclusion(db: Session, master_batch_id: int, pdpj_batch_id: int) -> Dict[str, Any]:
    """
    Mengambil data PDPJ (yang sudah verif) dan mengecualikannya dari Master.
    PDPJ Kolom: noagenda, idpelanggan, verif, jenispelanggan, latitudey, longitudex
    """
    pdpj_records = db.query(SourceRecord).filter(SourceRecord.batch_id == pdpj_batch_id).all()
    excluded_idpels = set()

    for r in pdpj_records:
        data = r.data or {}
        normalized = {normalize_column_name(k): v for k, v in data.items() if v is not None}

        # Ambil IDPEL dari PDPJ
        idpel = None
        for alias in ["idpelanggan", "idpel", "nopelanggan"]:
            if alias in normalized and str(normalized[alias]).strip():
                idpel = str(normalized[alias]).strip()
                break
        if not idpel and r.idpel:
            idpel = str(r.idpel).strip()

        # Ambil status verifikasi (jika ada kolom verif)
        # Sesuai instruksi: PDPJ adalah data yang sudah verif.
        is_verified = True
        for alias in ["verif", "statusverif", "status", "statusbayar"]:
            if alias in normalized:
                val = str(normalized[alias]).strip().lower()
                # Jika eksplisit belum verif / 0 / false
                if val in ["0", "false", "belum", "unverified"]:
                    is_verified = False
                break

        if idpel and is_verified:
            excluded_idpels.add(idpel)

    # Ambil Master Pelanggan
    master_records = db.query(SourceRecord).filter(SourceRecord.batch_id == master_batch_id).all()

    total_master = len(master_records)
    total_excluded = 0
    sisa_records = []

    # Reset tabel Master Sisa sebelum diisi yang baru
    db.query(MasterSisaRecord).delete()

    for r in master_records:
        data = r.data or {}
        raw_idpel = str(r.idpel).strip() if r.idpel else str(data.get("idpel", "")).strip()

        # Cek apakah IDPEL valid atau kosong
        has_idpel = bool(raw_idpel and raw_idpel.lower() not in ["none", "null", "-", "", "0"])

        # Exclude jika ada di PDPJ yang sudah terverifikasi
        if has_idpel and raw_idpel in excluded_idpels:
            total_excluded += 1
            continue

        try:
            # Koordinat X/Y
            lat = float(data.get("koordinat_y") or data.get("latitude") or 0)
            lon = float(data.get("koordinat_x") or data.get("longitude") or 0)
            if lat == 0 and lon == 0:
                continue

            # Deteksi Prabayar vs Pascabayar
            jenis_pel = str(data.get("jenis_pel") or data.get("tarif") or "-").upper()
            jenis_layanan = "PRABAYAR" if ("PRA" in jenis_pel or "T" in jenis_pel) else "PASCABAYAR"

            sisa_record = MasterSisaRecord(
                idpel=raw_idpel if has_idpel else f"UNASSIGNED-{r.id}",
                nama=data.get("nama", "-"),
                latitude=lat,
                longitude=lon,
                tarif=data.get("tarif", "-"),
                daya=int(data.get("daya", 0)) if data.get("daya") else None,
                jenis_layanan=jenis_layanan
            )
            sisa_records.append(sisa_record)
        except (ValueError, TypeError):
            continue

    if sisa_records:
        db.bulk_save_objects(sisa_records)

    db.commit()

    return {
        "status": "success",
        "total_master": total_master,
        "total_excluded_by_pdpj": total_excluded,
        "total_master_sisa": len(sisa_records),
    }
