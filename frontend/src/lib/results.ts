import { api } from "@/lib/api";
import type { CorrectionDecision } from "@/lib/corrections";
import type { CorrectionKind } from "@/lib/master";
import type { Fields } from "@/lib/pdpj";

export interface ProcessHistory {
  id: number; process_name: string; radius_meters: number; matching_status: string;
  review_status: string; total_targets: number; matched_targets: number; unmatched_targets: number; created_at: string;
  category?: CorrectionKind; batch_id?: number; filename?: string; generation?: number;
  chosen_count?: number; saved_rows?: number; not_processed?: number; decision_events?: number;
  partial?: boolean; processing_state?: string;
}
export interface ResultSummary {
  process_id: number; process_name: string; category: CorrectionKind; batch_id: number; filename: string;
  pdpj_review_id: number; generation: number; radius_meters: number; matching_status: string;
  review_status: string; processing_state: string; partial: boolean; total_targets: number;
  saved_rows: number; not_processed: number; matched_targets: number; unmatched_targets: number;
  chosen_count: number; cancelled_count: number; not_selected: number; decision_events: number;
}
export type ResultFilter = "selected" | "all" | "not_selected" | "cancelled" | "not_processed";
export interface SavedResult { record_id: number; row_number: number; status: ResultFilter | "not_processed";
  search_status: string; target_fields: Fields; choice: CorrectionDecision | null }
export interface DecisionEvent extends CorrectionDecision { record_id: number; row_number: number }
export interface SpreadsheetDownload { blob: Blob; filename: string }
export function radiusFilename(prefix: "hasil" | "riwayat", kind: CorrectionKind, process: number, generation: number, radius: number): string {
  return `${prefix}_koreksi_${kind}_${process}_radius_${String(radius).replace(".", "_")}m_v${generation}.xlsx`;
}
async function spreadsheet(path: string, params: Record<string, unknown>, fallback: string): Promise<SpreadsheetDownload> {
  const response = await api.get<Blob>(path, { params, responseType: "blob" });
  const filename = /filename="([^"\\/]+)"/.exec(String(response.headers["content-disposition"] ?? ""))?.[1] ?? fallback;
  return { blob: response.data, filename };
}
export const resultsApi = {
  processes: async (signal?: AbortSignal) => (await api.get<ProcessHistory[]>("/history/processes", { signal })).data,
  rows: async (kind: CorrectionKind, id: number, params: { q: string; status: ResultFilter; skip: number; limit: number; generation?: number }, signal?: AbortSignal) =>
    (await api.get<{ summary: ResultSummary; total: number; items: SavedResult[] }>(`/corrections/${kind}/checks/${id}/results`, { params, signal })).data,
  history: async (kind: CorrectionKind, id: number, record_id: number | undefined, skip: number, signal?: AbortSignal, generation?: number) =>
    (await api.get<{ total: number; items: DecisionEvent[] }>(`/corrections/${kind}/checks/${id}/results/history`, { params: { record_id, skip, limit: 20, generation }, signal })).data,
  export: async (kind: CorrectionKind, id: number, params: { q: string; status: ResultFilter; generation?: number }) =>
    (await api.get<Blob>(`/corrections/${kind}/checks/${id}/results/export`, { params, responseType: "blob" })).data,
  exportHistory: async (kind: CorrectionKind, id: number, record_id?: number) =>
    (await api.get<Blob>(`/corrections/${kind}/checks/${id}/results/history/export`, { params: { record_id }, responseType: "blob" })).data,
  download: (kind: CorrectionKind, id: number, generation: number, radius: number, q = "", status: ResultFilter = "selected") => spreadsheet(`/corrections/${kind}/checks/${id}/results/export`, { generation, q, status }, radiusFilename("hasil", kind, id, generation, radius)),
  downloadHistory: (kind: CorrectionKind, id: number, generation: number, radius: number, record_id?: number) => spreadsheet(`/corrections/${kind}/checks/${id}/results/history/export`, { generation, record_id }, radiusFilename("riwayat", kind, id, generation, radius)),
};

export function downloadSpreadsheet(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const resultStatus = { selected: "Kandidat dipilih", not_selected: "Belum dipilih", cancelled: "Pilihan dibatalkan", not_processed: "Belum diproses", all: "Semua baris" };
export const localTime = (value: string) => new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`).toLocaleString("id-ID");
