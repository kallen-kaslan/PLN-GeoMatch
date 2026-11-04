import { useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, FileClock, FileSpreadsheet, LoaderCircle, Upload } from "lucide-react";
import { api, type ApiError } from "@/lib/api";
import { buttonClass } from "@/lib/button";
import { previewButton } from "@/lib/empty-correction-preview";
import { correctionApi } from "@/lib/corrections";
import { guessMasterMapping, type ImportResult, type MasterBatchPreview } from "@/lib/master";
import { uploadFilesApi, type UploadFileHistory } from "@/lib/upload-files";
import { SearchableSelect } from "@/components/data/SearchableSelect";
import type { FlowDocument } from "./CorrectionFlowLayout";

const control = "w-full min-h-11 rounded-md border border-gray-300 bg-white px-3 py-2.5 text-sm disabled:opacity-50";
const cell = (value: unknown) => value === null || value === undefined ? "" : String(value);
const errorText = (error: unknown) => error instanceof Error ? error.message : (error as ApiError)?.message ?? "Permintaan belum berhasil. Coba lagi.";
const size = (bytes: number) => `${(bytes / 1024 / 1024).toLocaleString("id-ID", { maximumFractionDigits: 1 })} MB`;

export function EmptyCorrectionFileStep({ saved, onBatchCreated, onSaved, previewOnly = false, onDocumentChange, footer, hideFooter = false }: {
  saved?: MasterBatchPreview; onBatchCreated: (id: number) => void;
  onSaved: (result: ImportResult, filename: string) => void; onCancel: () => void;
  previewOnly?: boolean;
  onDocumentChange?: (document: FlowDocument) => void;
  footer?: ReactNode;
  hideFooter?: boolean;
}) {
  const client = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"new" | "stored">(saved ? "stored" : "new");
  const [restoreSaved, setRestoreSaved] = useState(!!saved);
  const [picked, setPicked] = useState<UploadFileHistory | null>(null);
  const [sheetKey, setSheetKey] = useState<string | null>(saved?.status === "completed" ? saved.source_sheet ?? "__csv__" : null);
  const [dragging, setDragging] = useState(false);
  const history = useQuery({ queryKey: ["upload-files"], queryFn: uploadFilesApi.list, enabled: mode === "stored", staleTime: 0 });
  const recovered = restoreSaved && saved ? history.data?.find((item) => item.imports.some((entry) => entry.batch_id === saved.id)) : undefined;
  const archive = picked ?? recovered;
  const sheetName = sheetKey === null ? null : archive?.sheet_names.length ? sheetKey : "";
  const period = archive && saved && archive.imports.some((item) => item.batch_id === saved.id) && sheetName === (saved.source_sheet ?? "") ? saved.period ?? "" : "";
  const imported = (name: string) => archive?.imports.find((item) => item.dataset_type === "idpel_kosong" && (item.period ?? "") === period && (item.source_sheet ?? "") === name);
  const restoredCompleted = saved?.status === "completed" && archive?.imports.some((item) => item.batch_id === saved.id) && sheetName === (saved.source_sheet ?? "");
  const alreadySaved = sheetName !== null && imported(sheetName)?.status === "completed";
  const preview = useQuery({ queryKey: ["original-file-preview", archive?.id, sheetName], queryFn: ({ signal }) => uploadFilesApi.originalPreview(archive!.id, sheetName!, signal), enabled: !!archive && sheetName !== null, staleTime: Infinity });
  useEffect(() => {
    onDocumentChange?.({ filename: archive?.filename, sheet: sheetName === null ? null : sheetName || "Tabel CSV", previewRows: sheetName !== null ? preview.data?.rows.length : undefined });
  }, [archive?.filename, sheetName, preview.data?.rows.length, onDocumentChange]);
  const store = useMutation({
    mutationFn: async (file: File) => {
      if (previewOnly) throw new Error("Unggah dinonaktifkan dalam pratinjau alur.");
      if (!/\.(csv|xlsx)$/i.test(file.name)) throw new Error("Pilih berkas Excel (.xlsx) atau CSV (.csv).");
      if (file.size > 500 * 1024 * 1024) throw new Error("Ukuran berkas maksimal 500 MB.");
      return uploadFilesApi.store(file);
    },
    onSuccess: (value) => {
      setPicked(value); setSheetKey(null);
      client.setQueryData<UploadFileHistory[]>(["upload-files"], (old) => [value, ...(old ?? []).filter((item) => item.id !== value.id)]);
    },
  });
  const save = useMutation<ImportResult, ApiError | Error>({
    mutationFn: async () => {
      if (previewOnly) throw new Error("Penyimpanan dinonaktifkan dalam pratinjau alur.");
      if (restoredCompleted && saved) return { batch_id: saved.id, rows: saved.total_rows, valid_rows: saved.valid_rows, error_rows: saved.error_rows };
      if (!archive || sheetName === null || !preview.data?.rows.length) throw new Error("Pilih dokumen dan sheet terlebih dahulu.");
      const uploaded = await uploadFilesApi.importSheet(archive.id, "idpel_kosong", sheetName, period);
      onBatchCreated(uploaded.id);
      const batch = await correctionApi.batch("idpel_kosong", uploaded.id);
      if (batch.status === "completed") return { batch_id: batch.id, rows: batch.total_rows, valid_rows: batch.valid_rows, error_rows: batch.error_rows };
      const mapping = guessMasterMapping(batch.headers, "idpel_kosong", batch.preview);
      return (await api.post<ImportResult>("/upload/confirm-mapping", { batch_id: uploaded.id, column_mapping: mapping })).data;
    },
    onSuccess: (result) => {
      void client.invalidateQueries({ queryKey: ["upload-files"] });
      onSaved(result, archive?.filename ?? saved?.filename ?? "Dokumen");
    },
    onError: () => { void client.invalidateQueries({ queryKey: ["corrections", "idpel_kosong"] }); },
  });
  const busy = store.isPending || save.isPending;
  const resetDocument = () => { setPicked(null); setRestoreSaved(false); setSheetKey(null); save.reset(); store.reset(); };
  const chooseFile = (file?: File) => { if (!file || busy || previewOnly) return; resetDocument(); store.mutate(file); };
  const drop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files[0]); };
  return <div className="space-y-5"><section aria-label="Pilih dokumen IDPEL Kosong" className="overflow-hidden rounded-lg border border-gray-200 bg-white">
    <div className="space-y-6 px-5 py-6 sm:px-7 sm:py-7">
      <div><h2 className="text-lg font-semibold">Pilih dokumen</h2><p className="mt-1 text-sm text-gray-600">Unggah berkas baru atau gunakan dokumen yang sudah tersimpan.</p></div>
      <fieldset className="grid gap-3 sm:grid-cols-2" disabled={busy}><legend className="sr-only">Sumber dokumen</legend>{([
        { key: "new", title: "Unggah berkas baru", description: "Pilih berkas dari perangkat Anda.", Icon: Upload },
        { key: "stored", title: "Gunakan berkas tersimpan", description: "Pilih dokumen tanpa mengunggah ulang.", Icon: FileClock },
      ] as const).map(({ key, title, description, Icon }) => <label key={key} className={`flex cursor-pointer items-start gap-3 rounded-md border p-4 has-focus-visible:ring-2 has-focus-visible:ring-gray-700 ${mode === key ? "border-gray-900 bg-gray-50" : "border-gray-200 bg-white hover:border-gray-400"} ${busy ? "cursor-wait opacity-60" : ""}`}><input type="radio" name="empty-document-source" value={key} checked={mode === key} onChange={() => { resetDocument(); setMode(key); }} className="mt-1 accent-gray-900" /><Icon size={20} className="mt-0.5 shrink-0" /><span><span className="block text-sm font-bold">{title}</span><span className="mt-1 block text-xs text-gray-600">{description}</span></span></label>)}</fieldset>
      {mode === "new" ? <div onDragOver={(event) => { event.preventDefault(); if (!busy) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop} className={`flex flex-col items-center gap-3 rounded-md border border-dashed px-4 py-7 text-center ${dragging ? "border-gray-900 bg-gray-50" : "border-gray-300 bg-gray-50"}`}>
        <Upload size={28} className="text-gray-500" /><p className="text-sm font-semibold">Tarik berkas ke sini atau pilih dari perangkat</p><p className="text-xs text-gray-600">Excel (.xlsx) atau CSV (.csv) · Maksimal 500 MB</p>
        <input ref={input} type="file" accept=".xlsx,.csv" aria-label="Berkas IDPEL Kosong" className="sr-only" disabled={busy || previewOnly} onChange={(event) => { chooseFile(event.target.files?.[0]); event.target.value = ""; }} />
        <button type="button" disabled={busy || previewOnly} className={buttonClass.secondary} onClick={() => input.current?.click()}>{store.isPending ? <><LoaderCircle size={16} className="animate-spin" />Mengunggah dokumen…</> : "Pilih berkas"}</button>
      </div> : <div className="space-y-3"><SearchableSelect label="Dokumen tersimpan" value={archive ? String(archive.id) : ""} disabled={busy || history.isPending || history.isError} placeholder={history.isPending ? "Memuat dokumen…" : "Pilih dokumen atau ketik nama berkas…"} options={(history.data ?? []).map((item) => ({ value: String(item.id), label: `${item.filename} · ${size(item.size_bytes)}` }))} onChange={(id) => { const value = history.data?.find((item) => item.id === Number(id)); resetDocument(); setPicked(value ?? null); }} />{history.isSuccess && !history.data.length && <p className="text-sm text-gray-600">Belum ada dokumen tersimpan. Pilih Unggah berkas baru.</p>}{history.isError && <p role="alert" className="text-sm">Dokumen tersimpan belum dapat dimuat. <button type="button" className="font-bold underline" onClick={() => void history.refetch()}>Coba lagi</button></p>}</div>}
      {store.error && <p role="alert" className="text-sm text-red-700">{errorText(store.error)}</p>}
      {archive && <div className="space-y-4 border-t border-gray-200 pt-5"><div className="flex items-start gap-3"><FileSpreadsheet size={22} className="shrink-0 text-gray-500" /><div><p className="break-words text-sm font-bold">{archive.filename}</p><p className="mt-1 text-xs text-gray-600">{size(archive.size_bytes)} · {archive.sheet_names.length ? `${archive.sheet_names.length} sheet` : "Tabel CSV"}</p></div></div><label className="grid max-w-xl gap-3 text-sm font-bold"><span>{archive.sheet_names.length ? "Pilih sheet" : "Pilih tabel"}</span><select aria-label="Pilih sheet atau tabel" value={sheetKey ?? ""} disabled={busy} onChange={(event) => { setSheetKey(event.target.value); save.reset(); }} className={control}><option value="" disabled>{archive.sheet_names.length ? "Pilih sheet untuk melihat data" : "Pilih tabel untuk melihat data"}</option>{(archive.sheet_names.length ? archive.sheet_names : ["__csv__"]).map((name) => { const done = imported(archive.sheet_names.length ? name : "")?.status === "completed"; return <option key={name} value={name} disabled={done}>{archive.sheet_names.length ? name : "Tabel CSV"}{done ? " · Sudah disimpan" : ""}</option>; })}</select></label></div>}
      {archive && sheetName !== null && <div className="space-y-3 border-t border-gray-200 pt-5"><div><h3 className="text-sm font-bold">Isi sheet</h3><p className="mt-1 text-xs text-gray-600">{archive.sheet_names.length ? `Sheet ${sheetName}` : "Tabel CSV"} · {preview.data?.rows.length ?? 0} baris pertama. Nama kolom dan urutan data mengikuti dokumen.</p></div>{preview.isPending ? <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Membaca isi sheet…</p> : preview.isError ? <p role="alert" className="text-sm text-red-700">{errorText(preview.error)} <button type="button" className="font-bold underline" onClick={() => void preview.refetch()}>Coba lagi</button></p> : preview.data?.headers.length ? <div className="max-h-80 overflow-auto rounded-sm border border-gray-200"><table aria-label="Tabel asli" className="w-full whitespace-pre text-left text-xs"><thead className="sticky top-0 bg-gray-100"><tr>{preview.data.headers.map((value, index) => <th key={index} className="border-b border-gray-200 px-4 py-3">{cell(value)}</th>)}</tr></thead><tbody>{preview.data.rows.map((row, index) => <tr key={index} className="border-b border-gray-100 last:border-0">{row.map((value, column) => <td key={column} className="px-4 py-3">{cell(value)}</td>)}</tr>)}</tbody></table></div> : <p className="text-sm text-gray-600">Sheet ini tidak memiliki data.</p>}</div>}
      {save.error && <p role="alert" className="text-sm text-red-700">{errorText(save.error)}</p>}
    </div>
  </section>
    {!hideFooter && <nav aria-label="Navigasi tahap" className="flex flex-wrap justify-end gap-3">{footer ?? <button type="button" disabled={previewOnly || busy || (!restoredCompleted && (sheetName === null || !preview.isSuccess || !preview.data.rows.length || alreadySaved))} onClick={() => save.mutate()} className={previewButton.primary}>{save.isPending ? <><LoaderCircle size={16} className="animate-spin" />Menyimpan data...</> : <><ArrowRight size={16} />{restoredCompleted ? "Berikutnya" : "Simpan dan berikutnya"}</>}</button>}</nav>}
  </div>;
}
