import { api } from "@/lib/api";

export interface RadiusAnalysis {
  id: number; batch_id: number; pdpj_review_id: number; actor: string;
  state: "running" | "paused" | "failed" | "ready";
  stage: "preparing" | "analyzing" | "done"; revision: number;
  total_rows: number; processed_rows: number; eligible_rows: number; invalid_rows: number;
  coordinate_rows: number; category_rows: number; elapsed_seconds: number;
  covered_rows: number; outside_limit_rows: number;
  recommended_radius_meters: number | null; partial_radius_meters: number | null;
  max_analysis_radius_meters: number; selected_radius_meters: number | null;
  coverage_rows: number | null; error: string | null;
  farthest_rows: { row_number: number; distance_meters: number }[];
  progress: { search_process_id?: number; preparation?: { phase: string; work_done: number; work_total: number } };
}
export interface EmptySearchProgress {
  process_id: number; run_id: number; generation: number; status: string;
  state: string; stage: string; total_rows: number; processed_rows: number;
  matched_rows: number; no_candidate_rows: number; coordinate_rows: number;
  other_issue_rows: number; elapsed_seconds: number; radius_meters: number; error: string | null;
}
export interface EmptyWorkflow {
  analysis: RadiusAnalysis; search: EmptySearchProgress | null;
  activity: { active: boolean; operation: string | null; started_at: string | null };
  job_kind: "analysis" | "search" | null;
}
const base = "/corrections/idpel_kosong/radius-analyses";
export const radiusAnalysisApi = {
  workflow: async (batch_id: number, radius_meters?: number, signal?: AbortSignal, analysis_id?: number) => (await api.get<EmptyWorkflow | null>(`${base}/workflow`, { params: { batch_id, radius_meters, analysis_id }, signal })).data,
  analysisJob: async (id: number, state: "running" | "paused") => (await api.post<EmptyWorkflow>(`${base}/${id}/analysis-job`, { state })).data,
  searchJob: async (id: number, body: { state: "running" | "paused"; radius_meters?: number; request_key?: string }) => (await api.post<EmptyWorkflow>(`${base}/${id}/search-job`, body)).data,
  latest: async (batch_id: number) => (await api.get<RadiusAnalysis | null>(base, { params: { batch_id } })).data,
  get: async (id: number, radius_meters?: number, signal?: AbortSignal) => (await api.get<RadiusAnalysis>(`${base}/${id}`, { params: { radius_meters }, signal })).data,
  start: async (body: { batch_id: number; actor: string; request_key: string }) => (await api.post<RadiusAnalysis>(base, body)).data,
  advance: async (item: RadiusAnalysis) => (await api.post<RadiusAnalysis>(`${base}/${item.id}/advance`, { revision: item.revision })).data,
  state: async (item: RadiusAnalysis, state: "running" | "paused") => (await api.post<RadiusAnalysis>(`${base}/${item.id}/state`, { revision: item.revision, state })).data,
  saveRadius: async (item: RadiusAnalysis, radius_meters: number) => (await api.put<RadiusAnalysis>(`${base}/${item.id}/radius`, { revision: item.revision, radius_meters })).data,
  search: async (item: RadiusAnalysis, request_key: string) => (await api.post<{ batch_id: number; process_id: number }>(`${base}/${item.id}/search`, { revision: item.revision, request_key })).data,
};

export const validRadius = (value: string) => value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) > 0 && Number(value) <= 100000;
