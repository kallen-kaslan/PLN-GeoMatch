import os
import sys

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add backend directory to sys.path so `app` package can be imported.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Read database URL from app settings (.env) instead of hardcoding in alembic.ini.
from app.config import settings  # noqa: E402

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Import all model modules so Alembic autogenerate sees every table.
from app.models.user import User  # noqa: E402
from app.models.upload import UploadBatch, SourceRecord  # noqa: E402
from app.models.master_sisa import CleanedMasterRecord, MasterSisaRecord  # noqa: E402
from app.models.matching import ReconciliationProcess, MatchCandidate  # noqa: E402
from app.models.pdpj import PdpjReview, PdpjRow, PdpjRecommendation, PdpjChange  # noqa: E402, F401
from app.models.correction import CorrectionCheck, CorrectionAttempt, CorrectionTarget, CorrectionCandidateEvidence  # noqa: E402, F401
from app.models.correction_decision import CorrectionDecision  # noqa: E402, F401
from app.models.upload_file import UploadFileArchive, UploadSheetImport  # noqa: E402, F401
from app.models.coordinate_repair import CoordinateRepair  # noqa: E402, F401
from app.database import Base  # noqa: E402

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        context.configure(connection=supplied_connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
