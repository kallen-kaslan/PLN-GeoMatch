"""Admin-only file and sheet deletion: safe cascade, FK guard, 404 paths."""

from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.upload import SourceRecord, UploadBatch
from app.models.upload_file import UploadFileArchive, UploadSheetImport
from app.modules.auth.security import Principal, UserRole, current_user
from app.modules.upload.router import router as upload_router


ADMIN = Principal("admin-id", "admin", UserRole.ADMIN, "hash")


@pytest.fixture
def admin_client(db_session):
    """HTTP client with admin principal injected, no real session/CSRF needed."""
    from app.modules.auth.security import current_actor

    app = FastAPI()
    app.include_router(upload_router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_user] = lambda: ADMIN
    # current_actor depends on current_user; override for mutation endpoints too
    app.dependency_overrides[current_actor] = lambda: "admin"
    with TestClient(app) as c:
        yield c


def workbook_bytes() -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = "Data"
    sheet.append(["IDPEL", "NAMA"])
    sheet.append(["001", "A"])
    out = BytesIO()
    book.save(out)
    return out.getvalue()


def upload(client: TestClient) -> dict:
    r = client.post(
        "/upload/files",
        files={"file": ("test.xlsx", workbook_bytes())},
    )
    assert r.status_code == 200, r.text
    return r.json()


def import_sheet(client: TestClient, file_id: int, sheet: str | None, **kwargs) -> dict:
    r = client.post(
        f"/upload/files/{file_id}/import-sheet",
        json={"dataset_type": "dil", "sheet_name": sheet, **kwargs},
    )
    assert r.status_code == 200, r.text
    return r.json()


def confirm(client: TestClient, batch_id: int) -> None:
    r = client.post(
        "/upload/confirm-mapping",
        json={"batch_id": batch_id, "column_mapping": {"idpel": "IDPEL"}},
    )
    assert r.status_code == 200, r.text


def test_delete_file_removes_archive_batches_and_records(
    admin_client: TestClient, db_session: Session
) -> None:
    stored = upload(admin_client)
    batch = import_sheet(admin_client, stored["id"], "Data")
    confirm(admin_client, batch["id"])
    assert db_session.query(UploadBatch).count() == 1
    assert db_session.query(SourceRecord).count() == 1

    r = admin_client.delete(f"/upload/files/{stored['id']}")
    assert r.status_code == 200, r.text

    assert db_session.query(UploadFileArchive).count() == 0
    assert db_session.query(UploadSheetImport).count() == 0
    assert db_session.query(UploadBatch).count() == 0
    assert db_session.query(SourceRecord).count() == 0
    assert admin_client.get("/upload/files").json() == []


def test_delete_file_without_imports(admin_client: TestClient, db_session: Session) -> None:
    stored = upload(admin_client)
    r = admin_client.delete(f"/upload/files/{stored['id']}")
    assert r.status_code == 200, r.text
    assert db_session.query(UploadFileArchive).count() == 0


def test_delete_file_404(admin_client: TestClient) -> None:
    assert admin_client.delete("/upload/files/9999").status_code == 404


def test_delete_sheet_removes_batch_and_records(
    admin_client: TestClient, db_session: Session
) -> None:
    stored = upload(admin_client)
    batch = import_sheet(admin_client, stored["id"], "Data")
    confirm(admin_client, batch["id"])
    assert db_session.query(UploadBatch).count() == 1

    r = admin_client.delete(
        f"/upload/files/{stored['id']}/sheet/Data",
        params={"dataset_type": "dil", "period": ""},
    )
    assert r.status_code == 200, r.text
    assert db_session.query(UploadSheetImport).count() == 0
    assert db_session.query(UploadBatch).count() == 0
    assert db_session.query(SourceRecord).count() == 0
    # archive is kept
    assert db_session.query(UploadFileArchive).count() == 1


def test_delete_sheet_404_wrong_dataset_type(admin_client: TestClient) -> None:
    stored = upload(admin_client)
    import_sheet(admin_client, stored["id"], "Data")
    r = admin_client.delete(
        f"/upload/files/{stored['id']}/sheet/Data",
        params={"dataset_type": "pdpj"},
    )
    assert r.status_code == 404


def test_delete_sheet_blocked_when_batch_used_in_pdpj(
    admin_client: TestClient, db_session: Session
) -> None:
    from app.models.pdpj import PdpjReview

    stored = upload(admin_client)
    batch = import_sheet(admin_client, stored["id"], "Data")
    confirm(admin_client, batch["id"])
    review = PdpjReview(batch_id=batch["id"], master_batch_ids=[], status="in_progress")
    db_session.add(review)
    db_session.commit()

    r = admin_client.delete(
        f"/upload/files/{stored['id']}/sheet/Data",
        params={"dataset_type": "dil"},
    )
    assert r.status_code == 409
    assert "PDPJ" in r.json()["detail"]


def test_delete_file_blocked_when_batch_used_in_pdpj(
    admin_client: TestClient, db_session: Session
) -> None:
    from app.models.pdpj import PdpjReview

    stored = upload(admin_client)
    batch = import_sheet(admin_client, stored["id"], "Data")
    confirm(admin_client, batch["id"])
    review = PdpjReview(batch_id=batch["id"], master_batch_ids=[], status="in_progress")
    db_session.add(review)
    db_session.commit()

    r = admin_client.delete(f"/upload/files/{stored['id']}")
    assert r.status_code == 409
    assert "PDPJ" in r.json()["detail"]
