import { useRef, useState, type ChangeEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Papa from "papaparse";
import * as XLSX from "xlsx";
import { AlertCircle, ArrowRight, FileSpreadsheet, LoaderCircle, Upload, X } from "lucide-react";
import { api, type ApiError } from "@/lib/api";
import { uploadFilesApi, type UploadFileHistory } from "@/lib/upload-files";
import { MASTER_TYPES, displayValue, guessMasterMapping, hasSourceHeaders, masterFields, normalizeSourceHeaders, type ImportResult, type MasterBatchPreview, type SourceKind } from "@/lib/master";

const inputClass = "w-full rounded-sm border-2 border-neo-border bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neo-accent disabled:opacity-60";
const MAX_UPLOAD_BYTES = 500 * 1024 * 1024;
type ImportPreview = { headers: string[]; rows: Record<string, unknown>[]; headerRow?: number };
const readError = (error: unknown) => error instanceof Error ? error.message : (error as ApiError)?.message ?? "Berkas tidak dapat dibaca.";

async function previewExcelSheet(book: XLSX.WorkBook, name: string, file: File, archivedPreview?: () => Promise<ImportPreview>): Promise<ImportPreview> {
  try { return sheetPreview(book, name); } catch {
    if (archivedPreview) return archivedPreview();
    // Incorrect sheet dimensions can hide all cells from the bounded browser
    // preview. The server streams the actual cells and never saves this preview.
    const body = new FormData();
    body.append("file", file);
    body.append("sheet_name", name);
    return (await api.post<ImportPreview>("/upload/preview", body, { headers: { "Content-Type": "multipart/form-data" } })).data;
  }
}

async function detectCsvEncoding(file: File): Promise<string> {
  const marker = new Uint8Array(await file.slice(0, 4).arrayBuffer());
  if ((marker[0] === 0xff && marker[1] === 0xfe && marker[2] === 0 && marker[3] === 0) ||
      (marker[0] === 0 && marker[1] === 0 && marker[2] === 0xfe && marker[3] === 0xff)) {
    throw new Error("CSV UTF-32 belum didukung. Simpan ulang sebagai CSV UTF-8.");
  }
  if (marker[0] === 0xff && marker[1] === 0xfe) return "utf-16le";
  if (marker[0] === 0xfe && marker[1] === 0xff) return "utf-16be";
  if (marker[0] === 0xef && marker[1] === 0xbb && marker[2] === 0xbf) return "utf-8";
  const decoder = new TextDecoder("utf-8", { fatal: true });
  const stream = file.stream().getReader();
  try {
    while (true) {
      const { done, value } = await stream.read();
      if (done) break;
      decoder.decode(value, { stream: true });
    }
    decoder.decode();
    return "utf-8";
  } catch (error) {
    if (error instanceof TypeError) return "windows-1252";
    throw error;
  } finally {
    await stream.cancel();
    stream.releaseLock();
  }
}

async function readCsv(file: File): Promise<{ headers: string[]; rows: Record<string, unknown>[] }> {
  const encoding = await detectCsvEncoding(file);
  return new Promise((resolve, reject) => {
    Papa.parse<string[]>(file, {
      header: false, preview: 6, skipEmptyLines: false, chunkSize: 64 * 1024, encoding,
      complete: (result) => {
        try {
          const headers = normalizeSourceHeaders(result.data[0] ?? []);
          resolve({ headers, rows: result.data.slice(1, 6).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ""]))) });
        } catch (error) { reject(error); }
      },
      error: () => reject(new Error("Berkas CSV tidak dapat dibaca.")),
    });
  });
}

function sheetPreview(workbook: XLSX.WorkBook, sheet: string) {
  const worksheet = workbook.Sheets[sheet];
  // !ref from external exporters can be incorrect. Use the cells actually read
  // for both the header and preview bounds, including columns beyond !ref.
  const range = { s: { r: 0, c: 0 }, e: { r: 0, c: 0 } };
  let headerStart: number | undefined;
  for (const address of Object.keys(worksheet)) {
    if (address.startsWith("!") || !hasSourceHeaders([worksheet[address]?.v])) continue;
    const cell = XLSX.utils.decode_cell(address);
    range.e.r = Math.max(range.e.r, cell.r);
    range.e.c = Math.max(range.e.c, cell.c);
    if (headerStart === undefined || cell.r < headerStart) headerStart = cell.r;
  }
  if (headerStart === undefined) {
    throw new Error(`Sheet "${sheet}" kosong atau tidak memiliki nama kolom. Pilih sheet yang berisi tabel data.`);
  }
  range.s.c = 0;
  range.s.r = headerStart;
  range.e.r = Math.min(range.e.r, headerStart + 5);
  const rows = XLSX.utils.sheet_to_json<unknown[]>(worksheet, { header: 1, defval: "", raw: false, range, blankrows: true });
  const headers = normalizeSourceHeaders(rows[0] ?? []);
  return { headers, headerRow: headerStart + 1, rows: rows.slice(1, 6).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ""]))) };
}

function readExcelPreview(content: ArrayBuffer): XLSX.WorkBook {
  let rowLimit = 64;
  while (true) {
    const book = XLSX.read(content, { type: "array", sheetRows: rowLimit });
    let nextLimit = rowLimit;
    for (const name of book.SheetNames) {
      const fullRef = book.Sheets[name]["!fullref"];
      if (!fullRef) continue;
      const fullRange = XLSX.utils.decode_range(fullRef);
      let neededRows: number;
      try {
        neededRows = sheetPreview(book, name).headerRow + 5;
      } catch {
        neededRows = Math.max(rowLimit * 2, fullRange.s.r + 6);
      }
      nextLimit = Math.max(nextLimit, Math.min(neededRows, fullRange.e.r + 1));
    }
    if (nextLimit <= rowLimit) return book;
    rowLimit = nextLimit;
  }
}

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
  const [mapping, setMapping] = useState<Record<string, string>>(saved?.column_mapping && Object.keys(saved.column_mapping).length ? saved.column_mapping : guessMasterMapping(saved?.headers ?? [], kind));
  const [period, setPeriod] = useState(saved?.period ?? "");
  const [sheet, setSheet] = useState(saved?.source_sheet ?? "");
  const [workbook, setWorkbook] = useState<XLSX.WorkBook | null>(null);
  const [reading, setReading] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [uploadId, setUploadId] = useState<number | null>(saved?.id ?? null);
  const [archiveId, setArchiveId] = useState<number | null>(null);
  const queryClient = useQueryClient();
  const history = useQuery({ queryKey: ["upload-files"], queryFn: uploadFilesApi.list });
  const storeFile = useMutation({ mutationFn: uploadFilesApi.store });
  const loadPreview = useMutation({ mutationFn: ({ id, name }: { id: number; name: string }) => uploadFilesApi.preview(id, name) });
  const selectedArchive = history.data?.find((item) => item.id === archiveId) ?? (archiveId === null && saved ? history.data?.find((item) => item.imports.some((entry) => entry.batch_id === saved.id)) : undefined);
  const activeArchiveId = archiveId ?? selectedArchive?.id;
  const sheetNames = selectedArchive?.sheet_names ?? workbook?.SheetNames ?? [];
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
    setMapping(guessMasterMapping(preview.headers, kind));
  };

  const mutation = useMutation<ImportResult, ApiError | Error>({
    mutationFn: async () => {
      if (fields.some((field) => field.required && !mapping[field.key])) throw new Error("Pilih kolom wajib terlebih dahulu.");
      let batchId = uploadId;
      if (batchId === null) {
        if (!activeArchiveId) throw new Error(`Pilih berkas ${noun} dari riwayat atau unggah terlebih dahulu.`);
        const uploaded = await uploadFilesApi.importSheet(activeArchiveId, kind, sheet, period);
        if (uploaded.status === "completed") {
          await queryClient.invalidateQueries({ queryKey: ["upload-files"] });
          throw new Error("Sheet ini sudah disimpan dan divalidasi. Pilih sheet lain.");
        }
        batchId = uploaded.id;
        setUploadId(batchId);
      }
      return (await api.post<ImportResult>("/upload/confirm-mapping", { batch_id: batchId, column_mapping: mapping })).data;
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["upload-files"] });
      onSaved(result, selectedArchive?.filename ?? file?.name ?? saved?.filename ?? "Berkas master");
    },
  });

  const chooseFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0];
    if (!chosen) return;
    const version = ++readVersion.current;
    setFile(chosen); setHeaders([]); setRows([]); setMapping({}); setWorkbook(null); setSheet("");
    setParseError(null); setReading(true); mutation.reset(); setUploadId(null); setArchiveId(null);
    try {
      if (chosen.size > MAX_UPLOAD_BYTES) throw new Error("Ukuran file maksimal 500 MB.");
      const archived = await storeFile.mutateAsync(chosen);
      await queryClient.cancelQueries({ queryKey: ["upload-files"] });
      queryClient.setQueryData<UploadFileHistory[]>(["upload-files"], (previous) => [archived, ...(previous ?? []).filter((item) => item.id !== archived.id)]);
      if (version !== readVersion.current) return;
      setArchiveId(archived.id);
      if (chosen.name.toLowerCase().endsWith(".csv")) {
        const preview = await readCsv(chosen);
        if (version === readVersion.current) acceptPreview(preview);
      } else {
        const content = await chosen.arrayBuffer();
        if (version !== readVersion.current) return;
        const book = readExcelPreview(content);
        const visibleSheets = book.SheetNames.filter((_, index) => !book.Workbook?.Sheets?.[index]?.Hidden);
        const candidates = visibleSheets.length ? visibleSheets : book.SheetNames;
        const previews = candidates.flatMap((name) => {
          try { return [{ name, preview: sheetPreview(book, name) }]; } catch { return []; }
        });
        const detected = previews.find(({ preview }) => {
          const guessed = guessMasterMapping(preview.headers, kind);
          return fields.every((field) => !field.required || guessed[field.key]);
        }) ?? previews[0];
        const first = detected?.name ?? candidates[0];
        if (!first) throw new Error("Berkas Excel tidak memiliki sheet.");
        // Keep the selector available even when the selected sheet cannot be previewed.
        setWorkbook(book); setSheet(first);
        const preview = detected?.preview ?? await previewExcelSheet(book, first, chosen, () => loadPreview.mutateAsync({ id: archived.id, name: first }));
        if (version === readVersion.current) acceptPreview(preview);
      }
    } catch (error) {
      if (version === readVersion.current) setParseError(readError(error));
    } finally {
      if (version === readVersion.current) setReading(false);
    }
  };

  const selectArchivedSheet = async (name: string, id = activeArchiveId) => {
    if (!id) return;
    const version = ++readVersion.current;
    setSheet(name); setUploadId(null); setParseError(null); setHeaders([]); setRows([]); setMapping({}); setReading(true); mutation.reset();
    try {
      const preview = await loadPreview.mutateAsync({ id, name });
      if (version === readVersion.current) acceptPreview(preview);
    } catch (error) {
      if (version === readVersion.current) setParseError(readError(error));
    } finally { if (version === readVersion.current) setReading(false); }
  };
  const lockedFile = mutation.isPending;
  return (
    <section aria-label={kind === "pdpj" ? "Impor PDPJ" : correction ? `Impor koreksi ${label}` : `Impor master ${label}`} className="space-y-5 rounded-sm border-2 border-neo-border bg-white p-4 shadow-[3px_3px_0_#0a0a0a] sm:p-6">
      <div className="flex items-start justify-between gap-3 border-b border-neo-border pb-3">
        <div><h2 className="flex items-center gap-2 text-base font-black"><Upload size={18} />{saved ? "Lanjutkan mapping" : kind === "pdpj" || correction ? "Unggah" : "Unggah master"} {label}</h2>
          <p className="mt-1 text-xs text-neo-border">{kind === "idpel_kosong" ? "IDPEL boleh kosong. Petakan referensi dan koordinat yang tersedia; semua baris tetap disimpan." : "IDPEL wajib dipetakan. Koordinat dan informasi lain dapat dilengkapi kemudian."}</p></div>
        <button type="button" onClick={onCancel} disabled={mutation.isPending} aria-label="Tutup formulir unggah" className="touch-min rounded-sm border border-neo-border hover:bg-neo-white disabled:opacity-40"><X size={18} /></button>
      </div>
      <label className="block space-y-2 text-xs font-bold">Riwayat berkas unggahan
        <select aria-label="Riwayat berkas unggahan" value={activeArchiveId ?? ""} disabled={lockedFile || reading || history.isPending} onChange={(event) => {
          const archive = history.data?.find((item) => item.id === Number(event.target.value));
          if (!archive) return;
          setArchiveId(archive.id); setFile(null); setWorkbook(null);
          void selectArchivedSheet(archive.sheet_names[0] ?? "", archive.id);
        }} className={inputClass}>
          <option value="" disabled>{history.isPending ? "Memuat riwayat berkas…" : "Pilih berkas yang pernah diunggah"}</option>
          {history.data?.map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.filename} · {item.sheet_names.length || 1} {item.sheet_names.length ? "sheet" : "tabel CSV"}</option>)}
        </select>
        <span className="block font-normal">Pilih file dari riwayat untuk menyimpan sheet lain tanpa mengunggah file yang sama. Tanda ✓ berlaku untuk kategori dan periode yang dipilih.</span>
      </label>
      {history.isError && <p role="alert" className="text-xs text-red-700">Riwayat berkas belum dapat dimuat. <button type="button" onClick={() => void history.refetch()} className="underline">Coba lagi</button></p>}
      {!saved && <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2 text-xs font-bold">Berkas CSV atau Excel
          <input type="file" accept=".csv,.xlsx" disabled={lockedFile || reading} onChange={chooseFile} className="block w-full text-xs file:mr-3 file:rounded-sm file:border-2 file:border-neo-border file:bg-neo-white file:px-3 file:py-2 file:font-bold" />
          <span className="block font-normal">Maksimal 500 MB per berkas.</span>
        </label>
        <label className="space-y-2 text-xs font-bold">Periode berkas (opsional)
          <input type="month" value={period} onChange={(event) => { setPeriod(event.target.value); setUploadId(null); mutation.reset(); }} disabled={lockedFile || reading} className={inputClass} />
        </label>
      </div>}
      {saved && <p className="flex items-center gap-2 text-sm font-semibold"><FileSpreadsheet size={17} />{selectedArchive?.filename ?? saved.filename}</p>}
      {sheetNames.length > 0 && <label className="block max-w-md space-y-2 text-xs font-bold">Sheet yang diimpor
        <select aria-label="Sheet yang diimpor" value={sheet} disabled={lockedFile || reading} onChange={(event) => void selectArchivedSheet(event.target.value)} className={`${inputClass} ${alreadySaved ? "border-green-700 bg-green-50" : ""}`}>
          {sheetNames.map((name) => <option key={name} value={name}>{sheetImport(name)?.status === "completed" ? "✓ " : sheetImport(name) ? "◷ " : ""}{name}{sheetImport(name)?.status === "completed" ? " — Sudah disimpan" : sheetImport(name) ? " — Belum divalidasi" : " — Belum disimpan"}</option>)}
        </select>
      </label>}
      {alreadySaved && <p role="status" className="rounded-sm border-2 border-green-700 bg-green-50 p-3 text-xs text-green-900">✓ Sheet ini sudah disimpan dan divalidasi untuk {label}{period ? ` periode ${period}` : " tanpa periode"}. Pilih sheet lain untuk menyimpan data berikutnya.</p>}
      {activeArchiveId && !alreadySaved && <p className="text-xs text-neo-border">Pratinjau belum menjadi data acuan. Sheet hanya diaktifkan setelah Anda menekan Simpan dan validasi.</p>}
      {reading && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Membaca pratinjau berkas…</p>}
      {(parseError || mutation.error) && <p role="alert" className="flex items-start gap-2 rounded-sm border-2 border-red-600 bg-red-50 p-3 text-sm text-red-700"><AlertCircle size={17} className="mt-0.5 shrink-0" />{parseError ?? mutation.error?.message}</p>}
      {headers.length > 0 && <>
        {sheetNames.length > 0 && <p className="text-xs text-neo-border">Nama kolom dibaca dari baris {firstDataRow - 1}. Baris kosong di awal dilewati.</p>}
        <div><h3 className="text-sm font-black">Pemetaan kolom</h3><p className="mt-1 text-xs text-neo-border">{correction || kind === "pdpj" ? "Petakan nomor meter, agenda, dan referensi survei secara terpisah agar pemeriksaan benturan membandingkan jenis referensi yang sama." : "Periksa hasil deteksi kolom. KODEDLPD, KDDK, kode gardu, dan kode lain disimpan terpisah. Kolom tanpa nama diberi label sesuai posisinya."}</p></div>
        <fieldset disabled={mutation.isPending} className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {fields.map((field) => <label key={field.key} className="space-y-1.5 text-xs font-bold">{field.label}{field.required && <span className="text-red-600"> *</span>}
            <select aria-label={`Kolom ${field.label}`} value={mapping[field.key] ?? ""} onChange={(event) => setMapping((previous) => ({ ...previous, [field.key]: event.target.value }))} className={inputClass}>
              <option value="">{field.required ? "Pilih kolom IDPEL" : "Otomatis bila tersedia"}</option>
              {headers.map((header) => <option key={header} value={header}>{header}</option>)}
            </select>
          </label>)}
        </fieldset>
        <div><h3 className="mb-2 text-sm font-black">Pratinjau lima baris pertama</h3>
          <div className="neo-scrollbar max-h-64 overflow-auto rounded-sm border border-neo-border"><table className="w-full whitespace-nowrap text-left text-xs">
            <thead className="sticky top-0 bg-gray-100"><tr><th className="border-b border-neo-border p-2">Baris</th>{headers.map((header) => <th key={header} className="border-b border-neo-border p-2">{header}</th>)}</tr></thead>
            <tbody>{rows.map((row, index) => <tr key={index} className="border-b border-gray-200"><td className="p-2 font-mono">{(uploadId === saved?.id ? saved?.row_numbers?.[index] : undefined) ?? firstDataRow + index}</td>{headers.map((header) => <td key={header} className="max-w-64 truncate p-2">{displayValue(row[header])}</td>)}</tr>)}</tbody>
          </table></div>
        </div>
      </>}
      <div className="flex flex-col justify-between gap-3 border-t border-neo-border pt-4 sm:flex-row sm:items-center">
        <p className="max-w-xl text-xs text-neo-border">Simpan IDPEL sebagai teks agar nol di depan tetap utuh. Data asli tetap tersedia pada detail setiap baris.</p>
        <button type="button" disabled={alreadySaved || !headers.length || fields.some((field) => field.required && !mapping[field.key]) || reading || mutation.isPending || !!parseError} onClick={() => mutation.mutate()} className="touch-min shrink-0 gap-2 rounded-sm border-2 border-neo-border bg-neo-black px-4 py-2.5 text-xs font-bold text-white shadow-[2px_2px_0_#ff6b35] hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40">
          {mutation.isPending ? <LoaderCircle size={16} className="animate-spin" /> : <ArrowRight size={16} />}{mutation.isPending ? "Menyimpan dan memvalidasi…" : `Simpan dan validasi ${noun}`}
        </button>
      </div>
    </section>
  );
}
