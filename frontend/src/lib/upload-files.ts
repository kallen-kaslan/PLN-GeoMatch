import { api } from "@/lib/api";
import type { SourceKind } from "@/lib/master";

export interface SheetImport {
  batch_id: number; dataset_type: SourceKind; source_sheet: string | null;
  period: string | null; status: string; total_rows: number;
}
export interface UploadFileHistory {
  id: number; filename: string; size_bytes: number; sheet_names: string[];
  created_at: string; imports: SheetImport[];
}
export interface FilePreview { headers: string[]; rows: Record<string, unknown>[]; headerRow?: number }
export const uploadFilesApi = {
  list: async () => (await api.get<UploadFileHistory[]>("/upload/files")).data,
  store: async (file: File) => {
    const body = new FormData(); body.append("file", file);
    return (await api.post<UploadFileHistory>("/upload/files", body, { headers: { "Content-Type": "multipart/form-data" } })).data;
  },
  preview: async (id: number, sheet?: string) => (await api.get<FilePreview>(`/upload/files/${id}/preview`, { params: { sheet_name: sheet || undefined } })).data,
  importSheet: async (id: number, kind: SourceKind, sheet: string, period: string) => (await api.post<{ id: number; status: string }>(`/upload/files/${id}/import-sheet`, { dataset_type: kind, sheet_name: sheet || null, period: period || null })).data,
};
