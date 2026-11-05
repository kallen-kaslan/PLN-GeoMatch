"""Only coordinates and category membership gate an empty-ID target search."""

from app.models.upload import DatasetType


def target_errors(errors: list[dict], kind: DatasetType) -> list[dict]:
    if kind == DatasetType.IDPEL_KOSONG:
        return [error for error in errors if error["field"] in {"lat", "lon", "idpel"}]
    return errors
