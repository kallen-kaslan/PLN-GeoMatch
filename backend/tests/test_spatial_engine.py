"""
Test untuk logika status IDPEL dan kelayakan data di spatial matching engine

Aturan bisnis:
1. Status IDPEL (kolom candidate_idpel):
   - VALID = IDPEL ada
   - TIDAK_DITEMUKAN = IDPEL tidak ada

2. Kelayakan Data (validity_status) - kombinasi koordinat + IDPEL:
   - VALID = koordinat ada + IDPEL ada
   - PERLU_KONFIRMASI_IDPEL = koordinat ada + IDPEL tidak ada
   - DILUAR_RADIUS = koordinat tidak ada + IDPEL ada
   - IDPEL_KOSONG = IDPEL tidak ada (prioritas utama, koordinat ada/tidak)

3. Under-5m = klasifikasi independen, tidak mempengaruhi validity_status
"""
import pytest
from app.modules.spatial.engine import calculate_haversine_distance, run_spatial_matching_job
from app.models.upload import UploadBatch, SourceRecord, DatasetType, BatchStatus
from app.models.master_sisa import MasterSisaRecord
from app.models.matching import MatchCandidate


class TestCalculateDistance:
    """Test unit untuk fungsi kalkulasi jarak"""

    def test_haversine_same_point(self):
        """Jarak ke titik yang sama harus 0"""
        dist = calculate_haversine_distance(-6.2088, 106.8456, -6.2088, 106.8456)
        assert dist == 0.0

    def test_haversine_known_distance(self):
        """Jarak ~111km untuk 1 derajat latitude di ekuator"""
        dist = calculate_haversine_distance(0, 0, 1, 0)
        assert 110000 < dist < 112000

    def test_haversine_100m_distance(self):
        """Jarak 100m dengan koordinat Jakarta"""
        # ~0.0009 derajat latitude ≈ 100m
        dist = calculate_haversine_distance(-6.2088, 106.8456, -6.2079, 106.8456)
        assert 90 < dist < 110


class TestValidityStatusLogic:
    """Test untuk logika penentuan validity_status berdasarkan koordinat dan IDPEL"""

    def test_valid_when_coordinates_and_idpel_exist(self, db_session):
        """
        VALID = koordinat target ada + IDPEL kandidat ada + dalam radius
        """
        # Setup: Master sisa dengan IDPEL valid
        master = MasterSisaRecord(
            idpel="5312345678901",
            nama="Test User",
            latitude=-6.2088,
            longitude=106.8456,
            jenis_layanan="PASCABAYAR"
        )
        db_session.add(master)
        db_session.commit()

        # Setup: Target batch dengan koordinat
        batch = UploadBatch(
            filename="test_target.csv",
            dataset_type=DatasetType.KOORDINAT_KOSONG,
            status=BatchStatus.COMPLETED
        )
        db_session.add(batch)
        db_session.commit()

        # Target dekat dengan master (< 100m)
        target = SourceRecord(
            batch_id=batch.id,
            data={
                "nomormeter": "MTR-001",
                "latitudey": -6.2080,  # ~88m dari master
                "longitudex": 106.8456
            }
        )
        db_session.add(target)
        db_session.commit()

        # Execute matching
        result = run_spatial_matching_job(
            db=db_session,
            process_name="Test Valid Status",
            target_batch_id=batch.id,
            radius_meters=100.0
        )

        # Verify
        candidates = db_session.query(MatchCandidate).filter(
            MatchCandidate.process_id == result["process_id"]
        ).all()

        assert len(candidates) == 1
        assert candidates[0].validity_status == "VALID"
        assert candidates[0].candidate_idpel == "5312345678901"

    def test_perlu_konfirmasi_when_coordinates_exist_but_idpel_missing(self, db_session):
        """
        PERLU_KONFIRMASI_IDPEL = koordinat target ada + IDPEL kandidat tidak ada (UNASSIGNED)
        """
        # Setup: Master sisa TANPA IDPEL valid (UNASSIGNED)
        master = MasterSisaRecord(
            idpel="UNASSIGNED-1",
            nama="Tanpa IDPEL",
            latitude=-6.2088,
            longitude=106.8456,
            jenis_layanan="PASCABAYAR"
        )
        db_session.add(master)
        db_session.commit()

        # Setup: Target batch dengan koordinat
        batch = UploadBatch(
            filename="test_target.csv",
            dataset_type=DatasetType.KOORDINAT_KOSONG,
            status=BatchStatus.COMPLETED
        )
        db_session.add(batch)
        db_session.commit()

        target = SourceRecord(
            batch_id=batch.id,
            data={
                "nomormeter": "MTR-002",
                "latitudey": -6.2080,
                "longitudex": 106.8456
            }
        )
        db_session.add(target)
        db_session.commit()

        result = run_spatial_matching_job(
            db=db_session,
            process_name="Test Perlu Konfirmasi",
            target_batch_id=batch.id,
            radius_meters=100.0
        )

        candidates = db_session.query(MatchCandidate).filter(
            MatchCandidate.process_id == result["process_id"]
        ).all()

        assert len(candidates) == 1
        assert candidates[0].validity_status == "PERLU_KONFIRMASI_IDPEL"
        assert candidates[0].candidate_idpel.startswith("UNASSIGNED-")

    def test_diluar_radius_when_idpel_exists_but_no_nearby_coordinates(self, db_session):
        """
        DILUAR_RADIUS = IDPEL kandidat ada + tidak ada master dalam radius
        (Target koordinat ada, tapi tidak menemukan kandidat dalam radius)
        """
        # Setup: Master sisa dengan IDPEL valid tapi JAUH
        master = MasterSisaRecord(
            idpel="5312345678902",
            nama="Jauh dari Target",
            latitude=-6.3000,  # ~10km dari target
            longitude=106.8456,
            jenis_layanan="PASCABAYAR"
        )
        db_session.add(master)
        db_session.commit()

        # Setup: Target batch dengan koordinat
        batch = UploadBatch(
            filename="test_target.csv",
            dataset_type=DatasetType.KOORDINAT_KOSONG,
            status=BatchStatus.COMPLETED
        )
        db_session.add(batch)
        db_session.commit()

        target = SourceRecord(
            batch_id=batch.id,
            data={
                "nomormeter": "MTR-003",
                "latitudey": -6.2088,
                "longitudex": 106.8456
            }
        )
        db_session.add(target)
        db_session.commit()

        result = run_spatial_matching_job(
            db=db_session,
            process_name="Test Diluar Radius",
            target_batch_id=batch.id,
            radius_meters=100.0  # Radius kecil, master di luar
        )

        candidates = db_session.query(MatchCandidate).filter(
            MatchCandidate.process_id == result["process_id"]
        ).all()

        assert len(candidates) == 1
        assert candidates[0].validity_status == "DILUAR_RADIUS"
        # IDPEL menunjukkan jarak terdekat
        assert "DILUAR_RADIUS" in candidates[0].candidate_idpel

    def test_idpel_kosong_priority(self, db_session):
        """
        IDPEL_KOSONG = IDPEL tidak ada, prioritas utama
        Jika IDPEL kosong/tidak ada, status selalu IDPEL_KOSONG
        terlepas dari koordinat
        """
        # Setup: Master sisa tanpa IDPEL
        master = MasterSisaRecord(
            idpel="",
            nama="IDPEL Kosong",
            latitude=-6.2088,
            longitude=106.8456,
            jenis_layanan="PASCABAYAR"
        )
        db_session.add(master)
        db_session.commit()

        batch = UploadBatch(
            filename="test_target.csv",
            dataset_type=DatasetType.KOORDINAT_KOSONG,
            status=BatchStatus.COMPLETED
        )
        db_session.add(batch)
        db_session.commit()

        target = SourceRecord(
            batch_id=batch.id,
            data={
                "nomormeter": "MTR-004",
                "latitudey": -6.2080,
                "longitudex": 106.8456
            }
        )
        db_session.add(target)
        db_session.commit()

        result = run_spatial_matching_job(
            db=db_session,
            process_name="Test IDPEL Kosong",
            target_batch_id=batch.id,
            radius_meters=100.0
        )

        candidates = db_session.query(MatchCandidate).filter(
            MatchCandidate.process_id == result["process_id"]
        ).all()

        assert len(candidates) == 1
        # IDPEL kosong harus dapat status IDPEL_KOSONG
        assert candidates[0].validity_status == "IDPEL_KOSONG"


class TestUnder5mIndependent:
    """Test bahwa klasifikasi under-5m independen dari validity_status"""

    def test_under_5m_still_valid_status(self, db_session):
        """
        Jarak < 5m dengan IDPEL valid -> validity_status = VALID,
        is_under_5m = 1 (independen)
        """
        master = MasterSisaRecord(
            idpel="5312345678903",
            nama="Under 5m",
            latitude=-6.2088,
            longitude=106.8456,
            jenis_layanan="PASCABAYAR"
        )
        db_session.add(master)
        db_session.commit()

        batch = UploadBatch(
            filename="test_target.csv",
            dataset_type=DatasetType.KOORDINAT_KOSONG,
            status=BatchStatus.COMPLETED
        )
        db_session.add(batch)
        db_session.commit()

        # Target sangat dekat (~3m)
        target = SourceRecord(
            batch_id=batch.id,
            data={
                "nomormeter": "MTR-005",
                "latitudey": -6.20877,  # ~3m dari master
                "longitudex": 106.8456
            }
        )
        db_session.add(target)
        db_session.commit()

        result = run_spatial_matching_job(
            db=db_session,
            process_name="Test Under 5m",
            target_batch_id=batch.id,
            radius_meters=100.0
        )

        candidates = db_session.query(MatchCandidate).filter(
            MatchCandidate.process_id == result["process_id"]
        ).all()

        assert len(candidates) == 1
        assert candidates[0].validity_status == "VALID"
        assert candidates[0].is_under_5m == 1
        assert candidates[0].distance_meters < 5.0

    def test_under_5m_perlu_konfirmasi_status(self, db_session):
        """
        Jarak < 5m tanpa IDPEL -> validity_status = PERLU_KONFIRMASI_IDPEL,
        is_under_5m = 1 (independen)
        """
        master = MasterSisaRecord(
            idpel="UNASSIGNED-2",
            nama="Under 5m No IDPEL",
            latitude=-6.2088,
            longitude=106.8456,
            jenis_layanan="PASCABAYAR"
        )
        db_session.add(master)
        db_session.commit()

        batch = UploadBatch(
            filename="test_target.csv",
            dataset_type=DatasetType.KOORDINAT_KOSONG,
            status=BatchStatus.COMPLETED
        )
        db_session.add(batch)
        db_session.commit()

        target = SourceRecord(
            batch_id=batch.id,
            data={
                "nomormeter": "MTR-006",
                "latitudey": -6.20877,
                "longitudex": 106.8456
            }
        )
        db_session.add(target)
        db_session.commit()

        result = run_spatial_matching_job(
            db=db_session,
            process_name="Test Under 5m No IDPEL",
            target_batch_id=batch.id,
            radius_meters=100.0
        )

        candidates = db_session.query(MatchCandidate).filter(
            MatchCandidate.process_id == result["process_id"]
        ).all()

        assert len(candidates) == 1
        assert candidates[0].validity_status == "PERLU_KONFIRMASI_IDPEL"
        assert candidates[0].is_under_5m == 1
