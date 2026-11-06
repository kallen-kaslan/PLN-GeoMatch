import Papa from "papaparse";
import * as XLSX from "xlsx";
import { guessMasterMapping, hasSourceHeaders, masterFields, normalizeSourceHeaders, type SourceKind } from "@/lib/master";

let lastReported = 0;
let paused = false;
let resumeReading: (() => void) | null = null;
async function checkpoint() {
  // Let queued pause commands run between reads and workbook parsing passes.
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
  if (!paused) return;
  self.postMessage({ type: "paused" });
  await new Promise<void>((resolve) => { resumeReading = resolve; });
  self.postMessage({ type: "resumed" });
}
function reportRead(processed: number, total: number) {
  const now = performance.now();
  if (now - lastReported >= 100 || processed >= total) {
    self.postMessage({ type: "progress", processed, total });
    lastReported = now;
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
  let processed = 0;
  try {
    while (true) {
      await checkpoint();
      const { done, value } = await stream.read();
      if (done) break;
      decoder.decode(value, { stream: true });
      processed += value.byteLength;
      reportRead(processed, file.size);
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

async function readExcelPreview(content: ArrayBuffer): Promise<XLSX.WorkBook> {
  let rowLimit = 64;
  while (true) {
    await checkpoint();
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

self.onmessage = async (event: MessageEvent<{ file: File; kind: SourceKind; type?: string }>) => {
  if (event.data.type === "pause") { paused = true; return; }
  if (event.data.type === "resume") { paused = false; resumeReading?.(); resumeReading = null; return; }
  const { file, kind } = event.data;
  try {
    await checkpoint();
    if (file.name.toLowerCase().endsWith(".csv")) {
      const preview = await readCsv(file);
      await checkpoint();
      self.postMessage({ type: "complete", sheet: "", preview });
      return;
    }
    const content = await new Promise<ArrayBuffer>((resolve, reject) => {
      const reader = new FileReader();
      reader.onprogress = (progress) => reportRead(progress.loaded, progress.total);
      reader.onload = () => resolve(reader.result as ArrayBuffer);
      reader.onerror = () => reject(new Error("Berkas Excel tidak dapat dibaca."));
      reader.readAsArrayBuffer(file);
    });
    const book = await readExcelPreview(content);
    const visible = book.SheetNames.filter((_, index) => !book.Workbook?.Sheets?.[index]?.Hidden);
    const candidates = visible.length ? visible : book.SheetNames;
    const previews = candidates.flatMap((name) => {
      try { return [{ name, preview: sheetPreview(book, name) }]; } catch { return []; }
    });
    const detected = previews.find(({ preview }) => {
      const mapping = guessMasterMapping(preview.headers, kind, preview.rows);
      return masterFields(kind).every((field) => !field.required || mapping[field.key]);
    }) ?? previews[0];
    const first = detected?.name ?? candidates[0];
    if (!first) throw new Error("Berkas Excel tidak memiliki sheet.");
    await checkpoint();
    self.postMessage({ type: "complete", sheet: first, preview: detected?.preview });
  } catch (error) {
    self.postMessage({ type: "error", message: error instanceof Error ? error.message : "Berkas tidak dapat dibaca." });
  }
};
