from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base, ensure_schema_compatibility

# Import model
from .models.user import User
from .models.upload import UploadBatch, SourceRecord
from .models.master_sisa import CleanedMasterRecord, MasterSisaRecord
from .models.matching import ReconciliationProcess, MatchCandidate
from .models.pdpj import PdpjReview, PdpjRow, PdpjRecommendation, PdpjChange
from .models.correction import CorrectionCheck, CorrectionAttempt, CorrectionTarget, CorrectionCandidateEvidence
from .models.correction_decision import CorrectionDecision
from .models.upload_file import UploadFileArchive, UploadSheetImport
from .models.coordinate_repair import CoordinateRepair

# Buat tabel otomatis jika belum ada
Base.metadata.create_all(bind=engine)

# Migrasi kolom lama (jika database sudah ada sebelum skema diperbarui)
ensure_schema_compatibility()

# Import Routers
from .modules.auth.router import router as auth_router
from .modules.upload.router import router as upload_router
from .modules.spatial.router import router as spatial_router
from .modules.history.router import router as history_router
from .modules.master.router import router as master_router
from .modules.pdpj.router import router as pdpj_router
from .modules.corrections.router import router as correction_router

app = FastAPI(title="PLN GeoMatch API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(spatial_router)
app.include_router(history_router)
app.include_router(master_router)
app.include_router(pdpj_router)
app.include_router(correction_router)

@app.get("/")
async def root():
    return {"message": "Welcome to PLN GeoMatch API", "status": "online"}

@app.get("/health")
async def health_check():
    redis_connected = False
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1)
        redis_connected = r.ping()
    except Exception:
        redis_connected = False

    return {
        "status": "ok",
        "redis_broker": "connected" if redis_connected else "offline"
    }
