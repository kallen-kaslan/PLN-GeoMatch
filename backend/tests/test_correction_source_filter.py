"""Source filters operate on category uploads, without modifying live data."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.upload import UploadBatch

MANUAL_HEADERS = "IDPEL,ID_TITIK,NOAGENDA,NOMOR_METER,LATITUDEY,LONGITUDEX,KETERANGAN"


def put(client, kind, filename, content, complete=True):
    response = client.post("/upload/", data={"dataset_type": kind}, files={"file": (filename, content.encode(), "text/csv")})
    assert response.status_code == 200, response.text
    batch = response.json()["id"]
    if complete:
        result = client.post("/upload/confirm-mapping", json={"batch_id": batch, "column_mapping": {}})
        assert result.status_code == 200, result.text
    return batch


@pytest.mark.parametrize("kind,other", [("idpel_kosong", "idpel_tidak_ketemu"), ("idpel_tidak_ketemu", "idpel_kosong")])
def test_category_documents_manual_search_and_pagination(client: TestClient, db_session: Session, kind, other):
    doc = put(client, kind, "dokumen.csv", "IDPEL,NAMA,LAT,LON\n777,Alpha,-6.2,106.8\n888,Beta,-6.2,106.8\n")
    second = put(client, kind, "manual-dokumen.csv", "IDPEL,NAMA,LAT,LON\n999,Dokumen biasa,-6.2,106.8\n")
    manual = put(client, kind, "manual-Survei.csv", MANUAL_HEADERS + "\n,T1,A1,,-6.2,106.8,Survei\n")
    foreign = put(client, other, "kategori-lain.csv", "IDPEL,NAMA,LAT,LON\n999,Lain,-6.2,106.8\n")
    put(client, "pdpj", "acuan.csv", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    put(client, kind, "belum-selesai.csv", "NAMA,LAT,LON\nDraft,-6.2,106.8\n", complete=False)
    base = f"/corrections/{kind}/overview"
    sources = client.get(base + "/sources").json()
    assert {row["id"] for row in sources} == {doc, second}
    assert client.get(base + "/summary").json()["total_rows"] == 4
    def rows(**params):
        result = client.get(base + "/records", params=params)
        assert result.status_code == 200, result.text
        return result.json()
    assert rows()["total"] == 4
    selected = rows(source="document", batch_id=doc, skip=1, limit=1)
    assert selected["total"] == 2 and selected["items"][0]["fields"]["nama"] == "Beta"
    assert rows(source="document", batch_id=doc, q="Alpha", status="not_processed")["total"] == 1
    assert rows(source="document", batch_id=doc, status="candidates_found")["total"] == 0
    assert rows(source="document")["total"] == 3
    assert rows(source="manual")["items"][0]["batch_id"] == manual
    assert rows(source="manual")["total"] == 1
    assert rows(batch_id=foreign)["total"] == 0
    assert rows(source="document", batch_id=manual)["total"] == 0
    assert client.get(base + "/records", params={"source": "invalid"}).status_code == 422
    assert db_session.get(UploadBatch, doc).filename == "dokumen.csv"
