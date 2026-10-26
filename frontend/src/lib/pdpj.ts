import { api } from "@/lib/api";
import { masterFields, type MasterBatch, type MasterBatchPreview } from "@/lib/master";

export type Fields = Record<string, string | number | null>;
export type PdpjStatus = "all" | "found" | "not_found" | "empty" | "invalid" | "incomplete" | "unresolved" | "exception" | "ready";
export interface PdpjReview {
  id: number; batch_id: number; master_batch_ids: number[]; status: "in_progress" | "completed";
  revision: number; created_at: string; completed_at: string | null; completed_by: string;
}
export interface PdpjSummary extends PdpjReview {
  summary: { total_rows: number; found: number; not_found: number; empty: number; invalid: number; incomplete_coordinates: number; exceptions: number; unresolved: number; ready: number };
  masters: MasterBatch[];
}
export interface PdpjRow {
  id: number; source_record_id: number; row_number: number; fields: Fields;
  existence: "found" | "not_found" | "empty" | "invalid"; coordinates_complete: boolean;
  issues: { field: string; code: string }[]; recommendation_count: number;
  reviewed: boolean; exception: boolean; exception_reason: string;
}
export interface Recommendation {
  id: number; fields: Fields; current: boolean;
  provenance: { batch_id: number; filename: string; dataset_type: string; row_number: number; source_sheet: string | null; period: string | null };
  validation_errors: { field: string; code: string }[];
}
export interface PdpjDetail extends PdpjRow {
  original_fields: Fields; raw_data: Record<string, unknown>; filename: string;
  source_sheet: string | null; column_mapping: Record<string, string>;
  recommendations_total: number; recommendations: Recommendation[];
  history: { id: number; action: string; actor: string; reason: string; created_at: string;
    before: { fields: Fields }; after: { fields: Fields }; sources: Record<string, unknown> }[];
}

export const PDPJ_FIELDS = masterFields("dil").map((field) => ({ ...field, key: field.key === "nomor_meter" ? "target_ref" : field.key }));
export const existenceLabel = { found: "IDPEL ditemukan", not_found: "IDPEL tidak ditemukan", empty: "IDPEL kosong", invalid: "Format IDPEL bermasalah" };
export const reviewLabel = (status: string) => status === "completed" ? "Selesai divalidasi" : "Dalam pemeriksaan";
export const pdpjApi = {
  batches: async () => (await api.get<MasterBatch[]>("/pdpj/batches")).data,
  batch: async (id: number) => (await api.get<MasterBatchPreview>(`/pdpj/batches/${id}`)).data,
  reviews: async (id: number) => (await api.get<PdpjReview[]>(`/pdpj/batches/${id}/reviews`)).data,
  start: async (batchId: number, masterIds?: number[]) => (await api.post<PdpjReview>("/pdpj/reviews", { batch_id: batchId, master_batch_ids: masterIds })).data,
  summary: async (id: number) => (await api.get<PdpjSummary>(`/pdpj/reviews/${id}`)).data,
  rows: async (id: number, params: { q: string; status: PdpjStatus; skip: number; limit: number }) => (await api.get<{ total: number; items: PdpjRow[] }>(`/pdpj/reviews/${id}/rows`, { params })).data,
  detail: async (id: number, rowId: number, skip: number) => (await api.get<PdpjDetail>(`/pdpj/reviews/${id}/rows/${rowId}`, { params: { skip, limit: 10 } })).data,
  edit: async (id: number, rowId: number, body: { revision: number; actor: string; reason: string; fields: Fields }) => (await api.patch(`/pdpj/reviews/${id}/rows/${rowId}`, body)).data,
  apply: async (id: number, rowId: number, body: { revision: number; actor: string; reason: string; recommendation_id: number; fields: string[]; overwrite: boolean }) => (await api.post(`/pdpj/reviews/${id}/rows/${rowId}/apply`, body)).data,
  decide: async (id: number, rowId: number, body: { revision: number; actor: string; reason: string; action: "reviewed" | "exception" | "reopen" }) => (await api.post(`/pdpj/reviews/${id}/rows/${rowId}/decision`, body)).data,
  complete: async (id: number, revision: number, actor: string) => (await api.post<PdpjReview>(`/pdpj/reviews/${id}/complete`, { revision, actor })).data,
  completeWithExceptions: async (id: number, body: { revision: number; actor: string; reason: string; expected_unresolved: number; confirmed: true }) =>
    (await api.post<PdpjReview>(`/pdpj/reviews/${id}/complete-with-exceptions`, body)).data,
};
