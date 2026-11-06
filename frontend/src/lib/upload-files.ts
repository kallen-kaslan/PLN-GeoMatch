import { api } from "@/lib/api";
import type { SourceKind } from "@/lib/master";
import type { AxiosProgressEvent } from "axios";

export interface SheetImport {
  batch_id: number; dataset_type: SourceKind; source_sheet: string | null;
  period: string | null; status: string; total_rows: number;
}
export interface UploadFileHistory {
  id: number; filename: string; size_bytes: number; sheet_names: string[];
  created_at: string; imports: SheetImport[];
}
export interface FilePreview { headers: string[]; rows: Record<string, unknown>[]; headerRow?: number }
export interface UploadProgressSnapshot {
  id: string; phase: string; status: "running" | "paused" | "completed" | "failed";
  processed: number; total: number | null; unit: "bytes" | "rows";
  started_at: number; phase_started_at: number; updated_at: number;
  pause_requested?: boolean;
  paused_at?: number | null;
}
export const progressHeaders = (id?: string) => id ? { "X-Upload-Progress": id } : {};
export const uploadFilesApi = {
  createProgress: async () => (await api.post<UploadProgressSnapshot>("/upload/progress")).data,
  progress: async (id: string, signal?: AbortSignal) => (await api.get<UploadProgressSnapshot>(`/upload/progress/${id}`, { signal })).data,
  pause: async (id: string) => { await api.post(`/upload/progress/${id}/pause`); },
  resume: async (id: string) => { await api.post(`/upload/progress/${id}/resume`); },
  list: async () => (await api.get<UploadFileHistory[]>("/upload/files")).data,
  store: async (file: File, id?: string, onUploadProgress?: (event: AxiosProgressEvent) => void) => {
    const body = new FormData(); body.append("file", file);
    return (await api.post<UploadFileHistory>("/upload/files", body, { headers: { "Content-Type": "multipart/form-data", ...progressHeaders(id) }, onUploadProgress })).data;
  },
  preview: async (id: number, sheet?: string) => (await api.get<FilePreview>(`/upload/files/${id}/preview`, { params: { sheet_name: sheet || undefined } })).data,
  importSheet: async (id: number, kind: SourceKind, sheet: string, period: string, progressId?: string) => (await api.post<{ id: number; status: string }>(`/upload/files/${id}/import-sheet`, { dataset_type: kind, sheet_name: sheet || null, period: period || null }, { headers: progressHeaders(progressId) })).data,
};
