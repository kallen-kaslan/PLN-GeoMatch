import type { SearchPage } from "@/lib/search";
import type { SearchIndexState } from "@/lib/search";
import { api } from "@/lib/api";
import type { CorrectionKind, MasterBatch, MasterBatchPreview } from "@/lib/master";
import type { Fields, PdpjPublication } from "@/lib/pdpj";
import { newestCheckpoint } from "@/lib/progress";

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
export interface ReadyPdpj { review_id: number; batch_id: number; filename: string; completed_by: string; completed_at: string; master_batch_ids: number[]; source_review_id: number | null; publication: PdpjPublication | null }
export interface CorrectionProcessing {
  state: "running" | "paused" | "failed" | "ready"; stage: "preparing" | "matching" | "validating" | "publishing" | "done";
  revision: number; total_rows: number; processed_rows: number; validated_rows: number; matched_rows: number;
  last_source_id: number; last_row_number: number | null; last_validated_source_id: number;
  started_at: string; updated_at: string; elapsed_seconds: number; stage_elapsed_seconds?: number; stage_timed_rows?: number; error: string | null;
  preparation?: MasterPreparationProgress;
}
export interface MasterPreparationProgress {
  phase: "reading" | "reserving" | "materializing" | "observations" | "ready";
  reused: boolean; work_done: number; work_total: number;
  source_total?: number; source_rows?: number; unique_rows?: number; cached_rows?: number;
  file_index?: number; file_count?: number; current_file?: string | null;
  pdpj_total?: number; pdpj_rows?: number; materialized_rows?: number; eligible_rows?: number; excluded_rows?: number;
  observation_rows?: number; observation_source_rows?: number; observation_source_total?: number;
}
export interface CorrectionRun { candidate_policy?: number; activity?: import("./progress").ProcessActivity; id: number; generation: number; status: "queued" | "running" | "completed" | "failed"; failure_code?: string | null; radius_meters: number; total_targets: number; matched_targets: number; created_at: string; completed_at: string | null; processing?: CorrectionProcessing | null }
export interface PdpjUpdate { review_id: number; publication: PdpjPublication | null; conflicts: { record_id: number; codes: string[] }[]; conflicts_checked?: boolean; decision_revision?: number }
export interface CorrectionCheck { process_id: number; batch_id: number; category: CorrectionKind; pdpj_review_id: number; status: CorrectionRun["status"]; current_generation: number; master_snapshot_id: number | null; latest_run: CorrectionRun; runs: CorrectionRun[]; requested_run_id?: number; execution_mode?: string; pdpj_update?: PdpjUpdate | null }

export function mergeCheckProgress(previous: CorrectionCheck | undefined, next: CorrectionCheck): CorrectionCheck {
  if (!previous || previous.process_id !== next.process_id) return next;
  if (previous.latest_run.generation > next.latest_run.generation) return previous;
  if (previous.latest_run.id !== next.latest_run.id) return next;
  const latest = newestCheckpoint(previous.latest_run, next.latest_run, (run) => run.processing?.revision ?? 0);
  return { ...next, latest_run: latest, status: latest.status,
    current_generation: latest.status === "completed" ? latest.generation : Math.max(previous.current_generation, next.current_generation),
    runs: next.runs.map((run) => run.id === latest.id ? latest : run) };
}
export interface CorrectionScope { batch_id?: number; process_id?: number; generation?: number; radius_meters?: number }
export interface CorrectionSummary { total_rows: number; not_checked: number; pdpj_conflicts: number; matched: number; no_candidates: number; invalid_data: number; incomplete_coordinates: number; identity_found: number; identity_not_found: number; eligible_searched: number; generation: number | null }
export interface MapRadiusSummary {
  process_id: number; generation: number; revision: number; radius_meters: number; stored_radius_meters: number; partial: boolean;
  total_rows: number; saved_rows: number; not_checked: number; matched: number; no_candidates: number;
  pdpj_conflicts: number; invalid_data: number; incomplete_coordinates: number; candidate_total: number;
  candidate_counts: Record<string, number>; newly_matched: number;
  baseline: { generation: number; radius_meters: number; matched: number; no_candidates: number; saved_rows: number };
}
export interface CorrectionRow {
  id: number; batch_id: number; category: CorrectionKind; row_number: number; filename: string; source_sheet: string | null;
  fields: Fields; identity_status: string; search_status: SearchStatus; candidate_count: number;
  errors: { field: string; code: string }[];
  conflicts: { code: string; value: string; pdpj_row_id: number | null; row_number: number; fields: Fields; pending_validation?: boolean }[];
  warnings: { code: string; pdpj_rows: number[] }[];
}
export interface ChoiceOwner { record_id: number; row_number: number }
export interface CorrectionCandidate { id: number; rank: number; distance_meters: number; fields: Fields; is_accepted: number; used_by?: ChoiceOwner[];
  observations: { batch_id: number; filename: string; dataset_type: string; row_number: number; source_sheet: string | null; fields: Fields }[] }
export interface CorrectionDetail extends CorrectionRow { raw_data: Record<string, unknown>; column_mapping: Record<string, string>; generation: number | null; radius_meters: number | null; filter_radius_meters?: number | null; candidates_total: number; candidates: CorrectionCandidate[] }
export interface CheckRequest { batch_id: number; pdpj_review_id: number; radius_meters: number; actor: string; request_key: string; incremental?: boolean }
export interface RetryRequest { latest_run_id: number; radius_meters: number; actor: string; request_key: string; incremental?: boolean }
export interface CorrectionDecision { id: number; revision: number; generation: number; candidate_id: number | null; candidate: Partial<CorrectionCandidate>; target_fields: Fields; actor: string; reason: string; created_at: string }
export interface CorrectionChoice { revision: number; current: CorrectionDecision | null; history: CorrectionDecision[] }
export interface ChoiceRequest { generation: number; expected_revision: number; candidate_id: number | null; actor: string; reason: string; request_key: string }
export interface AutomaticPreview {
  generation: number; radius_meters: number; total_targets: number; protected_count: number;
  selected_count: number; fallback_count: number; review_count: number; review_reasons: Record<string, number>;
  review: { record_id: number; row_number: number; reason: string }[]; fingerprint: string;
  tie_strategy?: "review" | "suggest";
  suggestion_count?: number;
  suggestions?: { record_id: number; row_number: number; candidate_id: number; idpel: string; distance_meters: number; needs_verification: true }[];
  unpaired_count?: number; unpaired?: AutomaticPreview["review"]; unpaired_reasons?: Record<string, number>;
}
export interface AutomaticRequest { generation: number; radius_meters: number; tie_strategy?: "review" | "suggest" }
export interface AutomaticReviewGroup {
  id: string; target_count: number; candidate_count: number; reason_counts: Record<string, number>;
  targets: AutomaticPreview["review"];
  coordinates: { lat: number; lon: number }[];
  candidates: { idpel: string; lat: number; lon: number; used_by: ChoiceOwner[]; proposed_for: ChoiceOwner | null }[];
}
export interface AutomaticReviewGroups { fingerprint: string; group_count: number; target_count: number; groups: AutomaticReviewGroup[] }
export type AdvancedSearchField = "idpel" | "meter" | "nama" | "gardu";
export interface AdvancedCandidate {
  idpel: string; fields: Fields; distance_meters: number | null; reasons: string[]; target_meter_matches: boolean;
  matched_sources: CorrectionCandidate["observations"];
  coordinate_source: CorrectionCandidate["observations"][number] | null;
  candidate: CorrectionCandidate | null;
  action: "choose" | "missing_coordinates" | "expand_search" | "change_filter" | "rerun_search" | "fix_target";
  suggested_radius_meters: number | null;
}
export interface AdvancedSearchResults { items: AdvancedCandidate[]; has_more: boolean; skip: number; next_skip?: number | null; stored_radius_meters?: number; search_index?: SearchIndexState }
export interface UnpairedSearchResults {
  fingerprint: string; search_radius_meters: number; stored_radius_meters: number;
  searched_count: number; found_count: number; unpaired_count: number; reason_counts: Record<string, number>;
  items: { record_id: number; row_number: number; reason: string; available_count: number; candidate: {
    idpel: string; distance_meters: number; fields: Fields; needs_verification: true;
    source: { batch_id: number; filename: string; source_sheet: string | null; row_number: number; dataset_type: string; pinned_source: boolean };
    action: "expand_search" | "change_filter" | "rerun_search"; suggested_radius_meters: number | null;
  } | null }[];
}

export const correctionApi = {
  downloadUnpaired: async (kind: CorrectionKind, process: number, body: AutomaticRequest & { fingerprint: string; search_radius_meters: number }) => {
    const response = await api.post<Blob>(`/corrections/${kind}/checks/${process}/automatic/unpaired-search/export`, body, { responseType: "blob" });
    const filename = /filename="([^"\\/]+)"/.exec(String(response.headers["content-disposition"] ?? ""))?.[1] ?? `usulan_lanjutan_${process}.xlsx`;
    return { blob: response.data, filename };
  },
  searchUnpaired: async (kind: CorrectionKind, process: number, body: AutomaticRequest & { fingerprint: string; search_radius_meters: number }, signal?: AbortSignal) =>
    (await api.post<UnpairedSearchResults>(`/corrections/${kind}/checks/${process}/automatic/unpaired-search`, body, { signal })).data,
  downloadSuggestions: async (kind: CorrectionKind, process: number, body: AutomaticRequest & { fingerprint: string }) => {
    const response = await api.post<Blob>(`/corrections/${kind}/checks/${process}/automatic/suggestions/export`, body, { responseType: "blob" });
    const filename = /filename="([^"\\/]+)"/.exec(String(response.headers["content-disposition"] ?? ""))?.[1] ?? `usulan_jarak_sama_${process}.xlsx`;
    return { blob: response.data, filename };
  },
  advancedCandidates: async (kind: CorrectionKind, process: number, record: number, params: { generation: number; radius_meters: number; field: AdvancedSearchField; q: string; skip: number }, signal?: AbortSignal) =>
    (await api.get<AdvancedSearchResults>(`/corrections/${kind}/checks/${process}/records/${record}/advanced-candidates`, { params, signal })).data,
  reviewGroups: async (kind: CorrectionKind, process: number, body: AutomaticRequest & { fingerprint: string }, signal?: AbortSignal) =>
    (await api.post<AutomaticReviewGroups>(`/corrections/${kind}/checks/${process}/automatic/review-groups`, body, { signal })).data,
  reviewDetail: async (kind: CorrectionKind, process: number, record: number, generation: number, radius_meters: number, skip: number, signal?: AbortSignal) =>
    (await api.get<CorrectionDetail>(`/corrections/${kind}/records/${record}`, { params: { process_id: process, generation, radius_meters, skip, limit: 10, include_usage: true }, signal })).data,
  automaticPreview: async (kind: CorrectionKind, process: number, body: AutomaticRequest, signal?: AbortSignal) =>
    (await api.post<AutomaticPreview>(`/corrections/${kind}/checks/${process}/automatic/preview`, body, { signal })).data,
  automaticApply: async (kind: CorrectionKind, process: number, body: AutomaticRequest & { fingerprint: string; request_key: string }) =>
    (await api.post<{ selected_count: number; already_applied: boolean }>(`/corrections/${kind}/checks/${process}/automatic/apply`, body)).data,
  readyPdpj: async () => (await api.get<ReadyPdpj[]>("/corrections/ready-pdpj")).data,
  batches: async (kind: CorrectionKind) => (await api.get<MasterBatch[]>(`/corrections/${kind}/batches`)).data,
  batch: async (kind: CorrectionKind, id: number) => (await api.get<MasterBatchPreview>(`/corrections/${kind}/batches/${id}`)).data,
  checks: async (kind: CorrectionKind, id: number, signal?: AbortSignal) => (await api.get<CorrectionCheck[]>(`/corrections/${kind}/checks`, { params: { batch_id: id, include_update_conflicts: false }, signal })).data,
  check: async (kind: CorrectionKind, id: number, signal?: AbortSignal) => (await api.get<CorrectionCheck>(`/corrections/${kind}/checks/${id}`, { params: { include_update_conflicts: false }, signal })).data,
  pdpjUpdate: async (kind: CorrectionKind, id: number, signal?: AbortSignal) => (await api.get<PdpjUpdate | null>(`/corrections/${kind}/checks/${id}/pdpj-update`, { signal })).data,
  start: async (kind: CorrectionKind, body: CheckRequest) => (await api.post<CorrectionCheck>(`/corrections/${kind}/checks`, body)).data,
  retry: async (kind: CorrectionKind, id: number, body: RetryRequest) => (await api.post<CorrectionCheck>(`/corrections/${kind}/checks/${id}/retry`, body)).data,
  advance: async (kind: CorrectionKind, id: number, run: CorrectionRun) => (await api.post<CorrectionRun>(`/corrections/${kind}/checks/${id}/advance`, { run_id: run.id, revision: run.processing!.revision, chunk_size: 100 })).data,
  progress: async (kind: CorrectionKind, id: number) => (await api.get<CorrectionRun>(`/corrections/${kind}/checks/${id}/progress`)).data,
  pause: async (kind: CorrectionKind, id: number, runId: number) => (await api.post<CorrectionRun>(`/corrections/${kind}/checks/${id}/pause`, { run_id: runId })).data,
  resume: async (kind: CorrectionKind, id: number, runId: number) => (await api.post<CorrectionRun>(`/corrections/${kind}/checks/${id}/resume`, { run_id: runId })).data,
  summary: async (kind: CorrectionKind, scope: CorrectionScope) => (await api.get<CorrectionSummary>(`/corrections/${kind}/summary`, { params: scope })).data,
  mapSummary: async (kind: CorrectionKind, process_id: number, generation: number, radius_meters: number, signal: AbortSignal) => (await api.get<MapRadiusSummary>(`/corrections/${kind}/map-summary`, { params: { process_id, generation, radius_meters }, signal })).data,
  rows: async (kind: CorrectionKind, params: CorrectionScope & { q: string; status: CorrectionFilter; skip: number; limit: number }, signal?: AbortSignal) => (await api.get<SearchPage<CorrectionRow>>(`/corrections/${kind}/records`, { params, signal })).data,
  detail: async (kind: CorrectionKind, id: number, scope: CorrectionScope, skip: number, radius_meters?: number) => (await api.get<CorrectionDetail>(`/corrections/${kind}/records/${id}`, { params: { ...scope, skip, limit: 10, radius_meters: radius_meters ?? scope.radius_meters } })).data,
  allRows: async (kind: CorrectionKind, scope: CorrectionScope, signal: AbortSignal) => {
    const items: CorrectionRow[] = [];
    let total = 0;
    do {
      const response = await api.get<{ total: number; items: CorrectionRow[] }>(`/corrections/${kind}/records`, { params: { ...scope, saved_only: true, skip: items.length, limit: 100 }, signal });
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
  choice: async (kind: CorrectionKind, process: number, record: number, generation?: number) => (await api.get<CorrectionChoice>(`/corrections/${kind}/checks/${process}/records/${record}/choice`, { params: { generation } })).data,
  choose: async (kind: CorrectionKind, process: number, record: number, body: ChoiceRequest) => (await api.post<CorrectionChoice>(`/corrections/${kind}/checks/${process}/records/${record}/choice`, body)).data,
};
