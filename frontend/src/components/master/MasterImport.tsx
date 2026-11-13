import { useRef, useState, type ChangeEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, FileSpreadsheet, LoaderCircle, Upload, X } from "lucide-react";
import { api, type ApiError } from "@/lib/api";
import { uploadFilesApi, progressHeaders, type UploadFileHistory } from "@/lib/upload-files";
import { MASTER_TYPES, displayValue, guessMasterMapping, masterFields, type ImportResult, type MasterBatchPreview, type SourceKind } from "@/lib/master";

import { useUploadProgress } from "@/hooks/useUploadProgress";
import { ImportProgress } from "@/components/master/ImportProgress";
import { readMasterPreview } from "@/lib/master-preview";

const inputClass = "w-full rounded-lg border border-ui-border bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neo-accent disabled:opacity-60";
const MAX_UPLOAD_BYTES = 500 * 1024 * 1024;
type ImportPreview = { headers: string[]; rows: Record<string, unknown>[]; headerRow?: number };
const readError = (error: unknown) => error instanceof Error ? error.message : (error as ApiError)?.message ?? "Berkas tidak dapat dibaca.";

export function MasterImport({ kind, saved, onSaved, onCancel }: {
  kind: SourceKind; saved?: MasterBatchPreview; onSaved: (result: ImportResult, filename: string) => void; onCancel: () => void;
}) {
  const correction = kind === "idpel_tidak_ketemu" || kind === "idpel_kosong";
  const label = kind === "pdpj" ? "PDPJ" : kind === "idpel_tidak_ketemu" ? "IDPEL Tidak Ketemu" : kind === "idpel_kosong" ? "IDPEL Kosong" : MASTER_TYPES.find((item) => item.key === kind)!.label;
  const noun = kind === "pdpj" ? "PDPJ" : correction ? "data koreksi" : "master";
  const fields = masterFields(kind);
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>(saved?.headers ?? []);
  const [rows, setRows] = useState<Record<string, unknown>[]>(saved?.preview ?? []);
  const [firstDataRow, setFirstDataRow] = useState(saved?.row_numbers?.[0] ?? 2);
  const [mapping, setMapping] = useState<Record<string, string>>(saved?.column_mapping && Object.keys(saved.column_mapping).length ? saved.column_mapping : guessMasterMapping(saved?.headers ?? [], kind, saved?.preview));
  const [period, setPeriod] = useState(saved?.period ?? "");
  const [sheet, setSheet] = useState(saved?.source_sheet ?? "");
  const [reading, setReading] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [uploadId, setUploadId] = useState<number | null>(saved?.id ?? null);
  const [archiveId, setArchiveId] = useState<number | null>(null);
  const queryClient = useQueryClient();
  const progress = useUploadProgress();
  const history = useQuery({ queryKey: ["upload-files"], queryFn: uploadFilesApi.list });
  const loadPreview = useMutation({ mutationFn: ({ id, name }: { id: number; name: string }) => uploadFilesApi.preview(id, name) });
  const selectedArchive = history.data?.find((item) => item.id === archiveId) ?? (archiveId === null && saved ? history.data?.find((item) => item.imports.some((entry) => entry.batch_id === saved.id)) : undefined);
  const activeArchiveId = archiveId ?? selectedArchive?.id;
  const sheetNames = selectedArchive?.sheet_names ?? [];
  const sheetImport = (name: string) => selectedArchive?.imports.find((item) => item.dataset_type === kind && (item.period ?? "") === period && (item.source_sheet ?? "") === name);
  const alreadySaved = sheetImport(sheet)?.status === "completed";
  const readVersion = useRef(0);

  const acceptPreview = (preview: ImportPreview) => {
    if (!preview.headers.length || preview.headers.some((header) => !header.trim()) || new Set(preview.headers).size !== preview.headers.length) {
      throw new Error("Gunakan nama kolom yang terisi dan berbeda pada baris header.");
    }
    setHeaders(preview.headers);
    setRows(preview.rows);
    setFirstDataRow((preview.headerRow ?? 1) + 1);
    setMapping(guessMasterMapping(preview.headers, kind, preview.rows));
  };

  const mutation = useMutation<ImportResult, ApiError | Error>({
    mutationFn: async () => {
      if (fields.some((field) => field.required && !mapping[field.key])) throw new Error("Pilih kolom wajib terlebih dahulu.");
      const progressId = await progress.begin("validation", selectedArchive?.filename ?? file?.name ?? saved?.filename ?? "Berkas master", uploadId === null ? "importing" : "validating");
      await progress.waitForResume();
      let batchId = uploadId;
      if (batchId === null) {
        if (!activeArchiveId) throw new Error(`Pilih berkas ${noun} dari riwayat atau unggah terlebih dahulu.`);
        const uploaded = await uploadFilesApi.importSheet(activeArchiveId, kind, sheet, period, progressId);
        if (uploaded.status === "completed") {
          await queryClient.invalidateQueries({ queryKey: ["upload-files"] });
          throw new Error("Sheet ini sudah disimpan dan divalidasi. Pilih sheet lain.");
        }
        batchId = uploaded.id;
        setUploadId(batchId);
      }
      await progress.waitForResume();
      progress.stage("validating");
      return (await api.post<ImportResult>("/upload/confirm-mapping", { batch_id: batchId, column_mapping: mapping }, { headers: progressHeaders(progressId) })).data;
    },
    onError: () => progress.finish("failed"),
    onSuccess: async (result) => {
      progress.finish("completed");
      await queryClient.invalidateQueries({ queryKey: ["upload-files"] });
      onSaved(result, selectedArchive?.filename ?? file?.name ?? saved?.filename ?? "Berkas master");
    },
  });

  const chooseFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0];
    if (!chosen) return;
    const version = ++readVersion.current;
    setFile(chosen); setHeaders([]); setRows([]); setMapping({}); setSheet("");
    setParseError(null); setReading(true); mutation.reset(); setUploadId(null); setArchiveId(null);
    try {
      if (chosen.size > MAX_UPLOAD_BYTES) throw new Error("Ukuran file maksimal 500 MB.");
      const progressId = await progress.begin("preview", chosen.name, "uploading", chosen.size);
      const archived = await uploadFilesApi.store(chosen, progressId, (event) => {
        if (version !== readVersion.current) return;
        progress.update(event.loaded, event.total ?? chosen.size);
        if (event.total && event.loaded >= event.total) progress.stage("server-file");
      });
      await queryClient.cancelQueries({ queryKey: ["upload-files"] });
      queryClient.setQueryData<UploadFileHistory[]>(["upload-files"], (previous) => [archived, ...(previous ?? []).filter((item) => item.id !== archived.id)]);
      if (version !== readVersion.current) return;
      setArchiveId(archived.id);
      await progress.waitForResume();
      progress.stage("preview", chosen.size, "bytes");
      const previewTask = readMasterPreview(chosen, kind, (processed, total) => {
        if (version === readVersion.current) progress.update(processed, total);
      }, progress.localPaused);
      progress.registerLocal(previewTask);
      const result = await previewTask.result;
      progress.registerLocal(null);
      if (version !== readVersion.current) return;
      setSheet(result.sheet);
      const preview = result.preview ?? await loadPreview.mutateAsync({ id: archived.id, name: result.sheet });
      await progress.waitForResume();
      if (version === readVersion.current) {
        acceptPreview(preview);
        progress.finish("completed");
      }
    } catch (error) {
      if (version === readVersion.current) { setParseError(readError(error)); progress.finish("failed"); }
    } finally {
      if (version === readVersion.current) setReading(false);
    }
  };

  const selectArchivedSheet = async (name: string, id = activeArchiveId) => {
    if (!id) return;
    const version = ++readVersion.current;
    setSheet(name); setUploadId(null); setParseError(null); setHeaders([]); setRows([]); setMapping({}); setReading(true); mutation.reset();
    try {
      await progress.begin("preview", history.data?.find((item) => item.id === id)?.filename ?? saved?.filename ?? "Berkas tersimpan", "preview");
      const preview = await loadPreview.mutateAsync({ id, name });
      await progress.waitForResume();
      if (version === readVersion.current) { acceptPreview(preview); progress.finish("completed"); }
    } catch (error) {
      if (version === readVersion.current) { setParseError(readError(error)); progress.finish("failed"); }
    } finally { if (version === readVersion.current) setReading(false); }
  };
  const lockedFile = mutation.isPending;
  const mainMappingKeys = new Set(["idpel", "nama", "lat", "lon", "tglbaca", "meter_ref", "survey_ref", "agenda_ref", "kode_gardu"]);
  const mappingControl = (field: (typeof fields)[number]) => <label key={field.key} className="space-y-1.5 text-xs font-semibold">{field.label}{field.required && <span className="text-red-600"> *</span>}
    <select aria-label={`Kolom ${field.label}`} value={mapping[field.key] ?? ""} onChange={(event) => setMapping((previous) => ({ ...previous, [field.key]: event.target.value }))} className={inputClass}>
      <option value="">{field.required ? "Pilih kolom IDPEL" : "Otomatis bila tersedia"}</option>
      {headers.map((header) => <option key={header} value={header}>{header}</option>)}
    </select>
  </label>;
  return (
    <section aria-label={kind === "pdpj" ? "Impor PDPJ" : correction ? `Impor koreksi ${label}` : `Impor master ${label}`} className="geo-panel space-y-5 p-4 sm:p-6">
      <div className="flex items-start justify-between gap-3 border-b border-ui-border pb-3">
        <div><h2 className="flex items-center gap-2 text-base font-semibold"><Upload size={18} />{saved ? "Lanjutkan mapping" : kind === "pdpj" || correction ? "Unggah" : "Unggah master"} {label}</h2>
          <p className="mt-1 text-xs text-ui-muted">{kind === "idpel_kosong" ? "IDPEL boleh kosong. Petakan referensi dan koordinat yang tersedia; semua baris tetap disimpan." : "IDPEL wajib dipetakan. Koordinat dan informasi lain dapat dilengkapi kemudian."}</p></div>
        <button type="button" onClick={onCancel} disabled={mutation.isPending || reading} aria-label="Tutup formulir unggah" className="touch-min rounded-lg border border-ui-border hover:bg-neo-white disabled:opacity-40"><X size={18} /></button>
      </div>
      <label className="block space-y-2 text-xs font-semibold">Riwayat berkas unggahan
        <select aria-label="Riwayat berkas unggahan" value={activeArchiveId ?? ""} disabled={lockedFile || reading || history.isPending} onChange={(event) => {
          const archive = history.data?.find((item) => item.id === Number(event.target.value));
          if (!archive) return;
          setArchiveId(archive.id); setFile(null);
          void selectArchivedSheet(archive.sheet_names[0] ?? "", archive.id);
        }} className={inputClass}>
          <option value="" disabled>{history.isPending ? "Memuat riwayat berkas…" : "Pilih berkas yang pernah diunggah"}</option>
          {history.data?.map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.filename} · {item.sheet_names.length || 1} {item.sheet_names.length ? "sheet" : "tabel CSV"}</option>)}
        </select>
        <span className="block font-normal">Pilih file dari riwayat untuk menyimpan sheet lain tanpa mengunggah file yang sama. Tanda ✓ berlaku untuk kategori dan periode yang dipilih.</span>
      </label>
      {history.isError && <p role="alert" className="text-xs text-red-700">Riwayat berkas belum dapat dimuat. <button type="button" onClick={() => void history.refetch()} className="underline">Coba lagi</button></p>}
      {!saved && <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2 text-xs font-semibold">Berkas CSV atau Excel
          <input type="file" accept=".csv,.xlsx" disabled={lockedFile || reading} onChange={chooseFile} className="block w-full text-xs file:mr-3 file:rounded-lg file:border file:border-ui-border file:bg-neo-white file:px-3 file:py-2 file:font-semibold" />
          <span className="block font-normal">Maksimal 500 MB per berkas.</span>
        </label>
        <label className="space-y-2 text-xs font-semibold">Periode berkas (opsional)
          <input type="month" value={period} onChange={(event) => { setPeriod(event.target.value); setUploadId(null); mutation.reset(); }} disabled={lockedFile || reading} className={inputClass} />
        </label>
      </div>}
      {saved && <p className="flex items-center gap-2 text-sm font-semibold"><FileSpreadsheet size={17} />{selectedArchive?.filename ?? saved.filename}</p>}
      {sheetNames.length > 0 && <label className="block max-w-md space-y-2 text-xs font-semibold">Sheet yang diimpor
        <select aria-label="Sheet yang diimpor" value={sheet} disabled={lockedFile || reading} onChange={(event) => void selectArchivedSheet(event.target.value)} className={`${inputClass} ${alreadySaved ? "border-green-700 bg-green-50" : ""}`}>
          {sheetNames.map((name) => <option key={name} value={name}>{sheetImport(name)?.status === "completed" ? "✓ " : ""}{name}</option>)}
        </select>
      </label>}
      {alreadySaved && <p role="status" className="rounded-lg border border-green-700 bg-green-50 p-3 text-xs text-green-900">✓ Sheet ini sudah disimpan dan divalidasi untuk {label}{period ? ` periode ${period}` : " tanpa periode"}. Pilih sheet lain untuk menyimpan data berikutnya.</p>}
      {activeArchiveId && !alreadySaved && <p className="text-xs text-ui-muted">Pratinjau belum menjadi data acuan. Sheet hanya diaktifkan setelah Anda menekan Simpan dan validasi.</p>}
      {progress.activity && <ImportProgress activity={progress.activity} snapshot={progress.server.data} disconnected={progress.server.isError} onTogglePause={() => void progress.togglePause()} controlBusy={progress.controlBusy} controlError={progress.controlError} />}
      {(parseError || mutation.error) && <p role="alert" className="flex items-start gap-2 rounded-lg border border-red-600 bg-red-50 p-3 text-sm text-red-700"><AlertCircle size={17} className="mt-0.5 shrink-0" />{parseError ?? mutation.error?.message}</p>}
      {headers.length > 0 && <>
        {sheetNames.length > 0 && <p className="text-xs text-ui-muted">Nama kolom dibaca dari baris {firstDataRow - 1}. Baris kosong di awal dilewati.</p>}
        <div><h3 className="text-sm font-semibold">Pemetaan kolom</h3><p className="mt-1 text-xs text-ui-muted">{correction || kind === "pdpj" ? "Nomor agenda boleh sama dengan PDPJ. Petakan nomor meter dan referensi survei secara terpisah untuk memeriksa benturan identitas." : "Periksa hasil deteksi kolom. KODEDLPD, KDDK, kode gardu, dan kode lain disimpan terpisah. Kolom tanpa nama diberi label sesuai posisinya."}</p></div>
        <fieldset disabled={mutation.isPending} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{fields.filter((field) => field.required || mainMappingKeys.has(field.key)).map(mappingControl)}</div>
          <details><summary className="text-sm font-medium">Pemetaan kolom lainnya</summary><div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{fields.filter((field) => !field.required && !mainMappingKeys.has(field.key)).map(mappingControl)}</div></details>
        </fieldset>
        <div><h3 className="mb-2 text-sm font-semibold">Pratinjau lima baris pertama</h3>
          <div className="neo-scrollbar max-h-64 overflow-auto rounded-lg border border-ui-border"><table className="w-full whitespace-nowrap text-left text-[13px]">
            <thead className="sticky top-0 bg-gray-100"><tr><th className="border-b border-ui-border p-2">Baris</th>{headers.map((header) => <th key={header} className="border-b border-ui-border p-2">{header}</th>)}</tr></thead>
            <tbody>{rows.map((row, index) => <tr key={index} className="border-b border-gray-200"><td className="p-2 font-mono">{(uploadId === saved?.id ? saved?.row_numbers?.[index] : undefined) ?? firstDataRow + index}</td>{headers.map((header) => <td key={header} className="max-w-64 truncate p-2">{displayValue(row[header])}</td>)}</tr>)}</tbody>
          </table></div>
        </div>
      </>}
      <div className="flex flex-col justify-between gap-3 border-t border-ui-border pt-4 sm:flex-row sm:items-center">
        <p className="max-w-xl text-xs text-ui-muted">Simpan IDPEL sebagai teks agar nol di depan tetap utuh. Data asli tetap tersedia pada detail setiap baris.</p>
        <button type="button" disabled={alreadySaved || !headers.length || fields.some((field) => field.required && !mapping[field.key]) || reading || mutation.isPending || !!parseError} onClick={() => mutation.mutate()} className="touch-min shrink-0 gap-2 rounded-lg border border-ui-border bg-ui-primary px-4 py-2.5 text-xs font-semibold text-white  hover:bg-ui-primary-hover disabled:cursor-not-allowed disabled:opacity-40">
          {mutation.isPending ? <LoaderCircle size={16} className="animate-spin" /> : <ArrowRight size={16} />}{mutation.isPending ? "Menyimpan dan memvalidasi…" : `Simpan dan validasi ${noun}`}
        </button>
      </div>
    </section>
  );
}
