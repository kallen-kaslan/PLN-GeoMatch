# ruff: noqa: F401
# Model imports register every table before schema initialization.

from .config import settings
from .database import Base, engine, ensure_schema_compatibility
from .database_errors import register_database_error_handlers

# Import model
from .models.auth import AuthAudit, AuthGuard, AuthSession, AuthThrottle
from .models.coordinate_repair import CoordinateRepair
from .models.correction import (
    CorrectionAttempt,
    CorrectionCandidateEvidence,
    CorrectionCheck,
    CorrectionTarget,
)
from .models.correction_decision import CorrectionDecision
from .models.master_sisa import CleanedMasterRecord, MasterSisaRecord
from .models.master_summary import MasterSummaryCache
from .models.matching import MatchCandidate, ReconciliationProcess
from .models.pdpj import PdpjChange, PdpjRecommendation, PdpjReview, PdpjRow
from .models.schema_state import SchemaState
from .models.upload import SourceRecord, UploadBatch
from .models.upload_file import UploadFileArchive, UploadSheetImport
from .models.user import User

# Buat tabel otomatis jika belum ada
Base.metadata.create_all(bind=engine)

# Migrasi kolom lama (jika database sudah ada sebelum skema diperbarui)
ensure_schema_compatibility()


from .application import create_application

app = create_application()
