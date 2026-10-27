"""Shared mapping-aware extraction without changing original source data."""

import math
from functools import lru_cache
from typing import Any

from app.models.upload import DatasetType

NORMALIZATION_VERSION = 3

ALIASES: dict[str, tuple[str, ...]] = {
    "idpel": ("idpel", "idpelanggan", "nopelanggan", "customerid"),
    "lat": ("lat", "latitudey", "latitude", "lintang", "koordinaty", "y"),
    "lon": ("lon", "longitudex", "longitude", "long", "bujur", "koordinatx", "x"),
    "tglbaca": (
        "vbulanrekap",
        "tglbaca",
        "tanggalbaca",
        "periode",
        "tgl",
        "bulan",
        "blth",
        "tglrekap",
    ),
    "jenis_pel": ("jenispel", "jenispelanggan", "jenislayanan", "layanan", "produk"),
    "nama": ("nama", "namapelanggan", "customername"),
    "kode_gardu": ("nomorgardu", "kodegardu", "gardu", "trafo", "idgardu"),
    "kode_dil": ("kodedil", "dilcode"),
    "kode_rbm": ("koderbm", "rbm"),
    "unitup": ("unitup", "ulp", "kodeunit"),
    "alamat": ("alamat", "alamatpelanggan", "address"),
    "kode_dlpd": ("kodedlpd",),
    "kddk": ("kddk",),
    "status_dil": ("statusdil",),
    "nomor_meter_kwh": ("nomormeterkwh",),
    "nomor_meter_prepaid": ("nomormeterprepaid",),
    "nama_gardu": ("namagardu",),
    "nama_penyulang": ("namapenyulang",),
    "nama_pnj": ("namapnj",),
    "no_bang": ("nobang",),
    "ket_no_bang": ("ketnobang",),
    "rt": ("rt",),
    "rw": ("rw",),
    "unit_upi": ("unitupi",),
    "unit_ap": ("unitap",),
    "tarif": ("tarif",),
    "daya": ("daya",),
    "verif": ("verif", "statusverif", "status", "statusbayar"),
    "target_ref": ("targetref", "nomormeter", "notmeter", "idtitik", "noagenda", "ref"),
    "meter_ref": ("meterref", "nomormeter", "notmeter"),
    "agenda_ref": ("agendaref", "noagenda", "nomoragenda"),
    "survey_ref": ("surveyref", "idtitik", "referensisurvei", "ref"),
}


def normalize_column_name(col: str) -> str:
    """Normalize a header, never an identifier value."""
    return (
        str(col or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def normalize_source_headers(values: list[Any]) -> list[str]:
    """Keep blank separator columns addressable and duplicate headers distinct."""
    headers: list[str] = []
    used: set[str] = set()
    if not any(clean_text(value) for value in values):
        raise ValueError("Baris pertama berkas harus memuat nama kolom")
    for index, value in enumerate(values):
        base = clean_text(value) or f"Kolom_{index + 1}"
        header, suffix = base, 2
        while header in used:
            header = f"{base}__{suffix}"
            suffix += 1
        used.add(header)
        headers.append(header)
    return headers


def canonical_mapping(mapping: dict[str, str] | None) -> dict[str, str]:
    """Resolve frontend and legacy mapping keys to the same standard fields."""
    return dict(_canonical_items(tuple((mapping or {}).items())))


@lru_cache(maxsize=128)
def _canonical_items(items: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
    result: dict[str, str] = {}
    for key, column in items:
        if not column:
            continue
        field = next(
            (
                name
                for name, aliases in ALIASES.items()
                if normalize_column_name(key) in aliases
            ),
            None,
        )
        if field is None:
            raise ValueError(f"Field mapping tidak dikenal: {key}")
        if field in result and result[field] != column:
            raise ValueError(f"Mapping ganda untuk field {field}")
        result[field] = column
    return tuple(result.items())


def clean_text(value: Any) -> str | None:
    """Treat empty values consistently while preserving leading zeroes."""
    if value is None:
        return None
    value = str(value).strip()
    return None if value.lower() in {"", "none", "null", "nan", "-"} else value


@lru_cache(maxsize=128)
def _column_plan(
    headers: tuple[str, ...], mapping: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, bool, tuple[str, ...]], ...]:
    """Cache column addresses only; values and blank-alias fallback remain per row."""
    normalized = {normalize_column_name(key): key for key in headers}
    selected = dict(_canonical_items(mapping))
    return tuple(
        (
            name,
            name in selected,
            (selected[name],)
            if name in selected
            else tuple(normalized[alias] for alias in aliases if alias in normalized),
        )
        for name, aliases in ALIASES.items()
    )


def raw_fields(
    data: dict[str, Any], mapping: dict[str, str] | None = None
) -> dict[str, Any]:
    """Explicit mapping takes precedence, even when the selected cell is empty."""
    return {
        name: (
            data.get(columns[0])
            if explicit
            else next(
                (data[key] for key in columns if clean_text(data.get(key))),
                None,
            )
        )
        for name, explicit, columns in _column_plan(
            tuple(data), tuple((mapping or {}).items())
        )
    }


def coordinate_source_columns(
    data: dict[str, Any], mapping: dict[str, str] | None = None
) -> tuple[str | None, str | None]:
    """Identify the exact two columns used, respecting explicit empty selections."""
    selected = canonical_mapping(mapping)
    if "lat" in selected and "lon" in selected:
        return selected["lat"], selected["lon"]
    names = {normalize_column_name(key): key for key in data}

    def column(field: str) -> str | None:
        if field in selected:
            return selected[field]
        return next(
            (
                names[key]
                for key in ALIASES[field]
                if key in names and clean_text(data[names[key]])
            ),
            None,
        )

    return column("lat"), column("lon")


def is_xy_pair(columns: tuple[str | None, str | None]) -> bool:
    """Only ambiguous X/Y headers may be reoriented; LAT/LON remain authoritative."""
    first, second = (normalize_column_name(column or "") for column in columns)
    x, y = {"x", "koordinatx"}, {"y", "koordinaty"}
    return (first in x and second in y) or (first in y and second in x)


def extract_standard_fields(
    row_data: dict[str, Any], column_mapping: dict[str, str] | None = None
) -> dict[str, Any]:
    """Parse canonical fields and retain field-level validation errors."""
    result: dict[str, Any] = {
        key: clean_text(value)
        for key, value in raw_fields(row_data, column_mapping).items()
    }
    if is_xy_pair(coordinate_source_columns(row_data, column_mapping)):
        try:
            latitude = float((result["lat"] or "").replace(",", "."))
            longitude = float((result["lon"] or "").replace(",", "."))
            if (
                math.isfinite(latitude)
                and math.isfinite(longitude)
                and 90 < abs(latitude) <= 180
                and abs(longitude) <= 90
            ):
                # Some PLN exports name latitude X and longitude Y. Swap only
                # when the default latitude is impossible and the reverse is valid.
                result["lat"], result["lon"] = result["lon"], result["lat"]
                result["_coordinate_axes_swapped"] = True
        except (ValueError, TypeError):
            pass
    errors: list[dict[str, str]] = []
    for field, maximum in (("lat", 90), ("lon", 180)):
        value = result[field]
        result[field] = None
        if value is not None:
            try:
                number = float(value.replace(",", "."))
                if not math.isfinite(number) or not -maximum <= number <= maximum:
                    raise ValueError
                result[field] = number
            except (ValueError, TypeError):
                errors.append({"field": field, "code": "koordinat_tidak_valid"})
    if result["lat"] == 0 and result["lon"] == 0:
        result["lat"] = result["lon"] = None
    if result["idpel"] == "0":
        result["idpel"] = None
    elif result["idpel"] and (
        not result["idpel"].isascii() or not result["idpel"].isdigit()
    ):
        errors.append({"field": "idpel", "code": "format_idpel_tidak_valid"})
    daya = result["daya"]
    result["daya"] = None
    if daya is not None:
        try:
            number = float(daya.replace(",", "."))
            if not math.isfinite(number) or number < 0 or not number.is_integer():
                raise ValueError
            result["daya"] = int(number)
        except (ValueError, TypeError):
            errors.append({"field": "daya", "code": "daya_tidak_valid"})
    result["nama"] = result["nama"] or "-"
    if not result["target_ref"] and "target_ref" not in canonical_mapping(
        column_mapping
    ):
        result["target_ref"] = (
            result["nomor_meter_kwh"]
            or result["nomor_meter_prepaid"]
            or result["meter_ref"]
            or result["agenda_ref"]
            or result["survey_ref"]
        )
    result["_normalization_version"] = NORMALIZATION_VERSION
    result["validation_errors"] = errors
    return result


def with_reference_fields(
    current: dict[str, Any], raw: dict[str, Any], mapping: dict[str, str] | None
) -> dict[str, Any]:
    """Derive typed references for older PDPJ versions without reviving replaced values."""
    if all(key in current for key in ("meter_ref", "agenda_ref", "survey_ref")):
        return dict(current)
    original = extract_standard_fields(raw, mapping)
    result = dict(current)
    for key in ("meter_ref", "agenda_ref", "survey_ref"):
        if key not in result:
            value = original[key]
            if (
                value is not None
                and value == original["target_ref"]
                and original["target_ref"] != current.get("target_ref")
            ):
                value = current.get("target_ref")
            result[key] = value
    return result


def validate_fields(
    fields: dict[str, Any], dataset_type: DatasetType
) -> list[dict[str, str]]:
    """Missing coordinates do not invalidate master or PDPJ identity records."""
    errors = list(fields["validation_errors"])
    if (
        dataset_type
        in {
            DatasetType.PASCABAYAR,
            DatasetType.PRABAYAR,
            DatasetType.MASTER,
            DatasetType.DIL,
            DatasetType.PDPJ,
            DatasetType.IDPEL_TIDAK_KETEMU,
        }
        and not fields["idpel"]
    ):
        errors.append({"field": "idpel", "code": "idpel_wajib_diisi"})
    if dataset_type == DatasetType.IDPEL_KOSONG and fields["idpel"]:
        errors.append({"field": "idpel", "code": "kategori_idpel_harus_kosong"})
    if dataset_type in {DatasetType.KOORDINAT_KOSONG, DatasetType.TARGET}:
        for field in ("lat", "lon"):
            if fields[field] is None and not any(
                error["field"] == field for error in errors
            ):
                errors.append({"field": field, "code": "koordinat_wajib_diisi"})
    return errors


def validate_mapping(
    mapping: dict[str, str], headers: set[str], dataset_type: DatasetType
) -> None:
    """Reject unknown source columns and missing required field mappings."""
    selected = canonical_mapping(mapping)
    if any(column not in headers for column in selected.values()):
        raise ValueError("Kolom sumber pada mapping tidak ditemukan dalam berkas")
    normalized_headers = {normalize_column_name(header) for header in headers}
    required = (
        ()
        if dataset_type == DatasetType.IDPEL_KOSONG
        else ("lat", "lon")
        if dataset_type in {DatasetType.KOORDINAT_KOSONG, DatasetType.TARGET}
        else ("idpel",)
    )
    for field in required:
        if field not in selected and not normalized_headers.intersection(
            ALIASES[field]
        ):
            raise ValueError(f"Mapping field {field} wajib dipilih")
