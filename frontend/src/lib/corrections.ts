import { api } from "@/lib/api";
import type { CorrectionKind, MasterBatch, MasterBatchPreview } from "@/lib/master";
import type { Fields } from "@/lib/pdpj";

export const CORRECTION_TYPES: { key: CorrectionKind; slug: string; label: string }[] = [
  { key: "idpel_tidak_ketemu", slug: "idpel-tidak-ketemu", label: "IDPEL Tidak Ketemu" },
  { key: "idpel_kosong", slug: "idpel-kosong", label: "IDPEL Kosong" },
];
export type SearchStatus = "not_checked" | "pdpj_conflict" | "invalid_data" | "incomplete_coordinates" | "matched" | "no_candidates";
export type CorrectionFilter = SearchStatus | "all" | "identity_found" | "identity_not_found";
export const searchLabel: Record<SearchStatus, string> = {
  not_checked: "Belum diperiksa", pdpj_conflict: "Benturan dengan PDPJ", invalid_data: "Data perlu diperbaiki",
  incomplete_coordinates: "Koordinat belum lengkap", matched: "Kandidat ditemukan", no_candidates: "Tanpa kandidat dalam radius",
};
export const identityLabel: Record<string, string> = { not_checked: "Belum diperiksa", empty: "IDPEL kosong", invalid: "Format IDPEL bermasalah", found: "Ditemukan di master", not_found: "Tidak ditemukan di master" };
export const conflictLabel: Record<string, string> = { idpel_sama_pdpj: "IDPEL sama dengan PDPJ", meter_sama_pdpj: "Nomor meter sama dengan PDPJ", agenda_sama_pdpj: "Nomor agenda sama dengan PDPJ", survey_sama_pdpj: "Referensi survei sama dengan PDPJ" };
export interface ReadyPdpj { review_id: number; batch_id: number; filename: string; completed_by: string; completed_at: string; master_batch_ids: number[] }
export interface CorrectionRun { id: number; generation: number; status: "queued" | "running" | "completed" | "failed"; failure_code?: string | null; radius_meters: number; total_targets: number; matched_targets: number; created_at: string; completed_at: string | null }
export interface CorrectionCheck { process_id: number; batch_id: number; category: CorrectionKind; pdpj_review_id: number; status: CorrectionRun["status"]; current_generation: number; master_snapshot_id: number | null; latest_run: CorrectionRun; runs: CorrectionRun[]; requested_run_id?: number; execution_mode?: string }
export interface CorrectionScope { batch_id?: number; process_id?: number; generation?: number }
export interface CorrectionSummary { total_rows: number; not_checked: number; pdpj_conflicts: number; matched: number; no_candidates: number; invalid_data: number; incomplete_coordinates: number; identity_found: number; identity_not_found: number; eligible_searched: number; generation: number | null }
export interface CorrectionRow {
  id: number; batch_id: number; category: CorrectionKind; row_number: number; filename: string; source_sheet: string | null;
  fields: Fields; identity_status: string; search_status: SearchStatus; candidate_count: number;
  errors: { field: string; code: string }[];
  conflicts: { code: string; value: string; pdpj_row_id: number; row_number: number; fields: Fields }[];
  warnings: { code: string; pdpj_rows: number[] }[];
}
export interface CorrectionCandidate { id: number; rank: number; distance_meters: number; fields: Fields; is_accepted: number;
  observations: { batch_id: number; filename: string; dataset_type: string; row_number: number; source_sheet: string | null; fields: Fields }[] }
export interface CorrectionDetail extends CorrectionRow { raw_data: Record<string, unknown>; column_mapping: Record<string, string>; generation: number | null; radius_meters: number | null; candidates_total: number; candidates: CorrectionCandidate[] }
export interface CheckRequest { batch_id: number; pdpj_review_id: number; radius_meters: number; actor: string; request_key: string }
export interface RetryRequest { latest_run_id: number; radius_meters: number; actor: string; request_key: string }
export interface CorrectionDecision { id: number; revision: number; generation: number; candidate_id: number | null; candidate: Partial<CorrectionCandidate>; target_fields: Fields; actor: string; reason: string; created_at: string }
export interface CorrectionChoice { revision: number; current: CorrectionDecision | null; history: CorrectionDecision[] }
export interface ChoiceRequest { generation: number; expected_revision: number; candidate_id: number | null; actor: string; reason: string; request_key: string }

export const correctionApi = {
  readyPdpj: async () => (await api.get<ReadyPdpj[]>("/corrections/ready-pdpj")).data,
  batches: async (kind: CorrectionKind) => (await api.get<MasterBatch[]>(`/corrections/${kind}/batches`)).data,
  batch: async (kind: CorrectionKind, id: number) => (await api.get<MasterBatchPreview>(`/corrections/${kind}/batches/${id}`)).data,
  checks: async (kind: CorrectionKind, id: number) => (await api.get<CorrectionCheck[]>(`/corrections/${kind}/checks`, { params: { batch_id: id } })).data,
  check: async (kind: CorrectionKind, id: number) => (await api.get<CorrectionCheck>(`/corrections/${kind}/checks/${id}`)).data,
  start: async (kind: CorrectionKind, body: CheckRequest) => (await api.post<CorrectionCheck>(`/corrections/${kind}/checks`, body)).data,
  retry: async (kind: CorrectionKind, id: number, body: RetryRequest) => (await api.post<CorrectionCheck>(`/corrections/${kind}/checks/${id}/retry`, body)).data,
  summary: async (kind: CorrectionKind, scope: CorrectionScope) => (await api.get<CorrectionSummary>(`/corrections/${kind}/summary`, { params: scope })).data,
  rows: async (kind: CorrectionKind, params: CorrectionScope & { q: string; status: CorrectionFilter; skip: number; limit: number }) => (await api.get<{ total: number; items: CorrectionRow[] }>(`/corrections/${kind}/records`, { params })).data,
  detail: async (kind: CorrectionKind, id: number, scope: CorrectionScope, skip: number, radius_meters?: number) => (await api.get<CorrectionDetail>(`/corrections/${kind}/records/${id}`, { params: { ...scope, skip, limit: 10, radius_meters } })).data,
  allRows: async (kind: CorrectionKind, scope: CorrectionScope, signal: AbortSignal) => {
    const items: CorrectionRow[] = [];
    let total = 0;
    do {
      const response = await api.get<{ total: number; items: CorrectionRow[] }>(`/corrections/${kind}/records`, { params: { ...scope, skip: items.length, limit: 100 }, signal });
      total = response.data.total;
      if (!response.data.items.length && items.length < total) throw new Error("Data peta belum lengkap. Muat ulang pemeriksaan.");
      items.push(...response.data.items);
    } while (items.length < total);
    return items;
  },
  mapCandidates: async (kind: CorrectionKind, record: number, scope: CorrectionScope, radius_meters: number, signal: AbortSignal) => {
    const items: CorrectionCandidate[] = [];
    let total = 0;
    do {
      const response = await api.get<CorrectionDetail>(`/corrections/${kind}/records/${record}`, { params: { ...scope, radius_meters, skip: items.length, limit: 100 }, signal });
      total = response.data.candidates_total;
      if (!response.data.candidates.length && items.length < total) throw new Error("Kandidat belum termuat lengkap. Coba lagi.");
      items.push(...response.data.candidates);
    } while (items.length < total);
    return items;
  },
  choice: async (kind: CorrectionKind, process: number, record: number) => (await api.get<CorrectionChoice>(`/corrections/${kind}/checks/${process}/records/${record}/choice`)).data,
  choose: async (kind: CorrectionKind, process: number, record: number, body: ChoiceRequest) => (await api.post<CorrectionChoice>(`/corrections/${kind}/checks/${process}/records/${record}/choice`, body)).data,
};
