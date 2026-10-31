import { api } from "@/lib/api";

export type MasterKind = "prabayar" | "pascabayar" | "dil";
export type CorrectionKind = "idpel_tidak_ketemu" | "idpel_kosong";
export type SourceKind = MasterKind | "pdpj" | CorrectionKind;
export type MasterStatus = "all" | "valid" | "invalid" | "incomplete";

export const MASTER_TYPES: { key: MasterKind; label: string; description: string }[] = [
  { key: "prabayar", label: "Prabayar", description: "Data pelanggan dan transaksi LPB." },
  { key: "pascabayar", label: "Pascabayar", description: "Data pencatatan pelanggan ACMT / RBM." },
  { key: "dil", label: "DIL", description: "Referensi pelanggan, gardu, meter, dan atribut DIL sesuai berkas sumber." },
];

export interface MasterBatch {
  id: number;
  filename: string;
  dataset_type: SourceKind;
  status: string;
  period: string | null;
  source_sheet: string | null;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  created_at: string;
}

export interface MasterBatchPreview extends MasterBatch {
  headers: string[];
  preview: Record<string, unknown>[];
  row_numbers?: (number | null)[];
  column_mapping: Record<string, string>;
}

export interface MasterSummary {
  total_rows: number | null;
  valid_rows: number | null;
  invalid_rows: number | null;
  incomplete_coordinates: number | null;
  unique_idpels: number | null;
  duplicate_observations: number | null;
  ready_files: number;
  pending_files: number;
  statistics_ready: boolean;
  source_signature: string;
}

export interface MasterRecord {
  id: number;
  batch_id: number;
  filename: string;
  source_sheet: string | null;
  row_number: number | null;
  period: string | null;
  fields: Record<string, string | number | null>;
  is_valid: boolean;
  coordinates_complete: boolean;
  validation_errors: { field: string; code: string }[];
}

export interface MasterRecordDetail extends MasterRecord {
  raw_data: Record<string, unknown>;
  column_mapping: Record<string, string>;
  batch_status: string;
}

export interface ImportResult {
  batch_id: number;
  rows: number;
  valid_rows: number;
  error_rows: number;
}

export interface MappingField { key: string; label: string; aliases: string[]; required?: boolean }

export const MASTER_FIELDS: MappingField[] = [
  { key: "idpel", label: "IDPEL", aliases: ["idpel", "idpelanggan", "nopelanggan", "customerid"], required: true },
  { key: "nama", label: "Nama pelanggan", aliases: ["nama", "namapelanggan", "customername"] },
  { key: "lat", label: "Latitude (lintang)", aliases: ["lat", "latitude", "latitudey", "koordinaty", "lintang", "y"] },
  { key: "lon", label: "Longitude (bujur)", aliases: ["lon", "longitude", "longitudex", "koordinatx", "bujur", "x"] },
  { key: "tglbaca", label: "Tanggal baca / periode", aliases: ["vbulanrekap", "tglbaca", "tanggalbaca", "periode", "bulan", "blth", "tglrekap"] },
  { key: "tarif", label: "Tarif", aliases: ["tarif"] },
  { key: "daya", label: "Daya", aliases: ["daya"] },
  { key: "kode_dil", label: "Kode DIL", aliases: ["kodedil", "dilcode"] },
  { key: "kode_gardu", label: "Kode gardu", aliases: ["nomorgardu", "kodegardu", "gardu", "trafo", "idgardu"] },
  { key: "kode_rbm", label: "Kode RBM", aliases: ["koderbm", "rbm"] },
  { key: "unitup", label: "Unit / ULP", aliases: ["unitup", "ulp", "kodeunit"] },
  { key: "alamat", label: "Alamat", aliases: ["alamat", "alamatpelanggan", "address"] },
  { key: "nomor_meter", label: "Nomor meter / referensi", aliases: ["nomormeter", "notmeter", "idtitik", "noagenda", "ref"] },
  { key: "jenis_pel", label: "Jenis layanan (jika tercantum)", aliases: ["jenispel", "jenispelanggan", "jenislayanan", "layanan", "produk"] },
];

const DIL_FIELDS: MappingField[] = [
  { key: "kode_dlpd", label: "KODEDLPD", aliases: ["kodedlpd"] },
  { key: "kddk", label: "KDDK", aliases: ["kddk"] },
  { key: "status_dil", label: "STATUS_DIL", aliases: ["statusdil"] },
  { key: "nomor_meter_kwh", label: "NOMOR_METER_KWH", aliases: ["nomormeterkwh"] },
  { key: "nomor_meter_prepaid", label: "NOMOR_METER_PREPAID", aliases: ["nomormeterprepaid"] },
  { key: "nama_gardu", label: "NAMA_GARDU", aliases: ["namagardu"] },
  { key: "nama_penyulang", label: "NAMA_PENYULANG", aliases: ["namapenyulang"] },
  { key: "unit_upi", label: "UNITUPI", aliases: ["unitupi"] },
  { key: "unit_ap", label: "UNITAP", aliases: ["unitap"] },
  { key: "nama_pnj", label: "NAMAPNJ", aliases: ["namapnj"] },
  { key: "no_bang", label: "NOBANG", aliases: ["nobang"] },
  { key: "ket_no_bang", label: "KETNOBANG", aliases: ["ketnobang"] },
  { key: "rt", label: "RT", aliases: ["rt"] },
  { key: "rw", label: "RW", aliases: ["rw"] },
];

const REFERENCE_FIELDS: MappingField[] = [
  { key: "meter_ref", label: "Nomor meter", aliases: ["meterref", "nomormeter", "notmeter"] },
  { key: "agenda_ref", label: "Nomor agenda", aliases: ["agendaref", "noagenda", "nomoragenda"] },
  { key: "survey_ref", label: "Referensi survei / ID titik", aliases: ["surveyref", "idtitik", "referensisurvei", "ref"] },
];

export const masterFields = (kind: SourceKind): MappingField[] => {
  if (kind === "idpel_tidak_ketemu" || kind === "idpel_kosong") {
    return [...MASTER_FIELDS.filter((field) => ["idpel", "nama", "lat", "lon", "alamat"].includes(field.key)).map((field) => ({ ...field, required: field.key === "idpel" && kind === "idpel_tidak_ketemu" })), ...REFERENCE_FIELDS];
  }
  return [...MASTER_FIELDS, ...REFERENCE_FIELDS, ...(kind === "dil" ? DIL_FIELDS : [])];
};

function cleanSourceHeader(value: unknown): string {
  const text = String(value ?? "").trim();
  return ["", "none", "null", "nan", "-"].includes(text.toLowerCase()) ? "" : text;
}

export function hasSourceHeaders(values: unknown[]): boolean {
  return values.some((value) => cleanSourceHeader(value));
}

export function normalizeSourceHeaders(values: unknown[]): string[] {
  if (!hasSourceHeaders(values)) throw new Error("Baris header harus memuat nama kolom.");
  const used = new Set<string>();
  return values.map((value, index) => {
    const base = cleanSourceHeader(value) || `Kolom_${index + 1}`;
    let header = base;
    let suffix = 2;
    while (used.has(header)) header = `${base}__${suffix++}`;
    used.add(header);
    return header;
  });
}

export function guessMasterMapping(headers: string[], kind: SourceKind, rows: Record<string, unknown>[] = []): Record<string, string> {
  const normalized = (value: string) => value.toLowerCase().replace(/[\s_-]/g, "");
  const mapping = Object.fromEntries(masterFields(kind).map((field) => [
    field.key, field.aliases.map((alias) => headers.find((header) => normalized(header) === alias)).find(Boolean) ?? "",
  ]));
  const first = normalized(mapping.lat ?? ""), second = normalized(mapping.lon ?? "");
  const x = ["x", "koordinatx"], y = ["y", "koordinaty"];
  if ((x.includes(first) && y.includes(second)) || (y.includes(first) && x.includes(second))) {
    let forward = 0, reversed = 0;
    for (const row of rows) {
      const text = (value: unknown) => String(value ?? "").trim().replace(",", ".");
      const lat = text(row[mapping.lat]), lon = text(row[mapping.lon]);
      if (!lat || !lon) continue;
      const a = Number(lat), b = Number(lon);
      if (!Number.isFinite(a) || !Number.isFinite(b)) continue;
      if (Math.abs(a) <= 90 && Math.abs(b) > 90 && Math.abs(b) <= 180) forward++;
      if (Math.abs(a) > 90 && Math.abs(a) <= 180 && Math.abs(b) <= 90) reversed++;
    }
    if (reversed > 0 && forward === 0) [mapping.lat, mapping.lon] = [mapping.lon, mapping.lat];
  }
  return mapping;
}

export const masterApi = {
  batches: async (kind: MasterKind) => (await api.get<MasterBatch[]>(`/master/${kind}/batches`)).data,
  batch: async (kind: MasterKind, id: number) => (await api.get<MasterBatchPreview>(`/master/${kind}/batches/${id}`)).data,
  summary: async (kind: MasterKind, batchId?: number, signal?: AbortSignal, details = true) => (await api.get<MasterSummary>(`/master/${kind}/summary`, { params: { batch_id: batchId, details }, signal })).data,
  records: async (kind: MasterKind, params: { batch_id?: number; q: string; status: MasterStatus; skip: number; limit: number }, signal?: AbortSignal) =>
    (await api.get<{ total: number; items: MasterRecord[] }>(`/master/${kind}/records`, { params, signal })).data,
  detail: async (kind: MasterKind, id: number) => (await api.get<MasterRecordDetail>(`/master/${kind}/records/${id}`)).data,
};

export const masterFieldLabel = (field: string) => masterFields("dil").find((item) => item.key === (field === "target_ref" ? "nomor_meter" : field))?.label ?? field;
export const validationMessage = (code: string) => ({
  koordinat_tidak_valid: "Koordinat harus berupa angka dalam rentang yang benar.",
  idpel_wajib_diisi: "IDPEL belum terisi.",
  format_idpel_tidak_valid: "IDPEL harus berupa digit, tanpa mengubah nol di depan.",
  daya_tidak_valid: "Daya harus berupa bilangan bulat positif atau nol.",
  koordinat_wajib_diisi: "Koordinat belum terisi.",
  idpel_tidak_ditemukan: "IDPEL belum ditemukan pada sumber master pemeriksaan ini.",
  idpel_berulang_pdpj: "IDPEL berulang diperbolehkan, termasuk dengan jenis pelanggan atau koordinat berbeda. Validasi tetap dapat dilanjutkan.",
  kategori_idpel_harus_kosong: "IDPEL terisi pada kategori IDPEL Kosong. Periksa kategori berkas asal.",
}[code] ?? code);

export const displayValue = (value: unknown): string => value === null || value === undefined || value === "" ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
