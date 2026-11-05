"""Versioned target eligibility for coordinate-based correction workflows."""

from app.models.upload import DatasetType


COORDINATE_IDPEL_POLICY = "coordinates_idpel_v1"
TARGET_POLICY_KEY = "target_policy"


def target_errors(errors: list[dict], kind: DatasetType, *, coordinate_only: bool = False) -> list[dict]:
    if kind == DatasetType.IDPEL_KOSONG or (kind == DatasetType.IDPEL_TIDAK_KETEMU and coordinate_only):
        return [error for error in errors if error["field"] in {"lat", "lon", "idpel"}]
    return errors
