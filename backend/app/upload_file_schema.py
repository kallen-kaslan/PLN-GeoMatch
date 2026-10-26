"""Add file history without changing legacy upload batches."""

from typing import cast

from sqlalchemy import Table
from sqlalchemy.engine import Connection

from app.models.upload_file import UploadFileArchive, UploadSheetImport


def upgrade_upload_files(connection: Connection) -> None:
    for model in (UploadFileArchive, UploadSheetImport):
        cast(Table, model.__table__).create(connection, checkfirst=True)
