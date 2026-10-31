"""
Konfigurasi pytest untuk testing PLN GeoMatch
"""

import os
import sys

import pytest

# Tambahkan parent directory ke path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Never import the project's configured live database while running tests.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.master_sisa import MasterSnapshot
from app.models.master_summary import MasterSummaryCache  # noqa: F401
from app.models.matching import MatchCandidate, MatchingRun, ReconciliationProcess  # noqa: F401
from app.models.upload import SourceRecord, UploadBatch  # noqa: F401
from app.models.pdpj import PdpjReview, PdpjRow, PdpjRecommendation, PdpjChange  # noqa: F401
from app.models.correction import CorrectionCheck, CorrectionAttempt, CorrectionTarget, CorrectionCandidateEvidence  # noqa: F401
from app.models.correction_decision import CorrectionDecision  # noqa: F401
from app.models.upload_file import UploadFileArchive, UploadSheetImport  # noqa: F401
from app.models.coordinate_repair import CoordinateRepair  # noqa: F401


@pytest.fixture(autouse=True)
def isolated_file_archives(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "UPLOAD_STORAGE_DIR", str(tmp_path / "uploads"))


@pytest.fixture(scope="function")
def db_session():
    """Database session untuk testing dengan SQLite in-memory"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db_session):
    """HTTP integration tests use only the fixture's in-memory database."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.modules.history.router import router as history_router
    from app.modules.spatial.router import router as spatial_router
    from app.modules.upload.router import router as upload_router
    from app.modules.master.router import router as master_router
    from app.modules.pdpj.router import router as pdpj_router
    from app.modules.corrections.router import router as correction_router

    app = FastAPI()
    app.include_router(upload_router)
    app.include_router(spatial_router)
    app.include_router(history_router)
    app.include_router(master_router)
    app.include_router(pdpj_router)
    app.include_router(correction_router)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def master_snapshot_id(db_session):
    """Explicit source snapshot for existing spatial engine scenarios."""
    snapshot = MasterSnapshot()
    db_session.add(snapshot)
    db_session.commit()
    return snapshot.id
