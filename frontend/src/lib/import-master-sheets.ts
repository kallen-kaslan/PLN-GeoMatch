import type { ImportResult } from "./master.ts";

export interface SheetProgress {
  sheet: string;
  status: "preparing" | "importing" | "completed" | "skipped" | "failed";
  message?: string;
}

interface SheetImportActions {
  prepare: (sheet: string) => Promise<Record<string, string>>;
  upload: (sheet: string) => Promise<{ id: number; status: string }>;
  confirm: (id: number, mapping: Record<string, string>) => Promise<ImportResult>;
  progress: (event: SheetProgress) => void;
}

// Each sheet retains its own mapping, transaction and validation. Stop on a
// failure so completed sheets stay saved and the remaining sheets can be retried.
export async function importMasterSheets(sheets: string[], actions: SheetImportActions) {
  const results: ImportResult[] = [];
  for (const sheet of [...new Set(sheets)]) {
    try {
      actions.progress({ sheet, status: "preparing" });
      const mapping = await actions.prepare(sheet);
      actions.progress({ sheet, status: "importing" });
      const batch = await actions.upload(sheet);
      if (batch.status === "completed") {
        actions.progress({ sheet, status: "skipped" });
        continue;
      }
      results.push(await actions.confirm(batch.id, mapping));
      actions.progress({ sheet, status: "completed" });
    } catch (error) {
      const message = error instanceof Error ? error.message : (error as { message?: string })?.message ?? "Terjadi kesalahan.";
      actions.progress({ sheet, status: "failed", message });
      throw new Error(`Impor dihentikan pada sheet "${sheet}": ${message} Sheet yang sudah selesai tetap tersimpan; sheet berikutnya belum diproses.`);
    }
  }
  return results;
}
