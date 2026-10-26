import { useDeferredValue, useEffect, useRef, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, Database, FileSpreadsheet, LoaderCircle, MapPin, Plus, RefreshCw, Search, X } from "lucide-react";
import { MasterImport } from "@/components/master/MasterImport";
import { MASTER_TYPES, displayValue, masterApi, masterFieldLabel, masterFields, validationMessage, type ImportResult, type MasterKind, type MasterRecord, type MasterStatus } from "@/lib/master";

const controlClass = "rounded-sm border-2 border-neo-border bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neo-accent";
const count = (value: number | undefined) => value === undefined ? "—" : value.toLocaleString("id-ID");

function RecordBadge({ record }: { record: MasterRecord }) {
  const label = !record.is_valid ? "Perlu perbaikan" : record.coordinates_complete ? "Lengkap" : "Koordinat belum lengkap";
  return <span className={`inline-block whitespace-nowrap rounded-xs border px-2 py-1 text-[10px] font-bold ${!record.is_valid ? "border-red-600 bg-red-50 text-red-700" : record.coordinates_complete ? "border-green-600 bg-green-50 text-green-700" : "border-amber-600 bg-amber-50 text-amber-800"}`}>{label}</span>;
}

function RecordDetail({ kind, id, onClose }: { kind: MasterKind; id: number; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const detail = useQuery({ queryKey: ["masters", kind, "detail", id], queryFn: () => masterApi.detail(kind, id) });
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  const record = detail.data;
  return <dialog ref={dialog} onCancel={onClose} aria-labelledby="master-detail-title" className="fixed inset-y-0 right-0 left-auto m-0 h-dvh max-h-none w-full max-w-2xl border-0 border-l-2 border-neo-border bg-white p-0 text-neo-black shadow-xl backdrop:bg-black/50">
    <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b-2 border-neo-border bg-white px-5 py-4">
      <div><p className="text-[10px] font-bold uppercase tracking-widest text-neo-border">Data Master · {MASTER_TYPES.find((item) => item.key === kind)?.label}</p><h2 id="master-detail-title" className="mt-1 text-lg font-black">Detail sumber pelanggan</h2></div>
      <button type="button" onClick={onClose} aria-label="Tutup detail data" className="touch-min rounded-sm border-2 border-neo-border hover:bg-neo-white"><X size={20} /></button>
    </div>
    <div className="space-y-6 p-5">
      {detail.isPending && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Memuat detail…</p>}
      {detail.isError && <p role="alert" className="border border-red-600 bg-red-50 p-3 text-sm text-red-700">Detail tidak dapat dimuat. <button type="button" onClick={() => void detail.refetch()} className="font-bold underline">Coba lagi</button></p>}
      {record && <>
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border-2 border-neo-border bg-neo-white p-4"><div><p className="font-mono text-lg font-black">{displayValue(record.fields.idpel)}</p><p className="mt-1 text-sm">{displayValue(record.fields.nama)}</p></div><RecordBadge record={record} /></div>
        <section><h3 className="mb-3 text-sm font-black">Asal data</h3><dl className="grid grid-cols-2 gap-3 text-xs">
          {[["Nama berkas", record.filename], ["Jenis master", MASTER_TYPES.find((item) => item.key === kind)?.label], ["Sheet", record.source_sheet], ["Baris sumber", record.row_number], ["Periode", record.period]].map(([label, value]) => <div key={String(label)} className="rounded-sm border border-gray-300 p-3"><dt className="font-bold text-neo-border">{label}</dt><dd className="mt-1 break-words font-medium">{displayValue(value)}</dd></div>)}
        </dl></section>
        {record.validation_errors.length > 0 && <section className="space-y-2 rounded-sm border-2 border-red-600 bg-red-50 p-4 text-xs text-red-700"><h3 className="font-black">Data yang perlu diperbaiki</h3><ul className="list-disc space-y-1 pl-4">{record.validation_errors.map((error, index) => <li key={`${error.field}-${index}`}><strong>{masterFieldLabel(error.field)}:</strong> {validationMessage(error.code)}</li>)}</ul></section>}
        <section><h3 className="mb-3 text-sm font-black">Data hasil pemetaan kolom</h3><dl className="grid gap-3 sm:grid-cols-2">
          {masterFields(kind).map((field) => <div key={field.key} className="border-b border-gray-200 pb-2"><dt className="text-[11px] font-bold text-neo-border">{field.label}</dt><dd className="mt-1 break-words text-sm">{displayValue(record.fields[field.key === "nomor_meter" ? "target_ref" : field.key])}</dd></div>)}
        </dl></section>
        <section><h3 className="mb-1 text-sm font-black">Data asli berkas</h3><p className="mb-3 text-xs text-neo-border">Nama kolom dan nilai sumber dipertahankan untuk pemeriksaan.</p><dl className="divide-y divide-gray-200 rounded-sm border border-neo-border">
          {Object.entries(record.raw_data).map(([field, value]) => <div key={field} className="grid grid-cols-2 gap-3 px-3 py-2 text-xs"><dt className="break-words font-bold">{field}</dt><dd className="break-words font-mono">{displayValue(value)}</dd></div>)}
        </dl></section>
      </>}
    </div>
  </dialog>;
}

function ImportPanel({ kind, resumeId, onSaved, onCancel }: { kind: MasterKind; resumeId: number | null; onSaved: (result: ImportResult, filename: string) => void; onCancel: () => void }) {
  const saved = useQuery({ queryKey: ["masters", kind, "batch", resumeId], queryFn: () => masterApi.batch(kind, resumeId!), enabled: resumeId !== null });
  if (resumeId !== null && saved.isPending) return <p role="status" className="rounded-sm border-2 border-neo-border bg-white p-4 text-sm">Memuat mapping berkas…</p>;
  if (resumeId !== null && saved.isError) return <div role="alert" className="flex items-center justify-between gap-3 border-2 border-red-600 bg-red-50 p-4 text-sm text-red-700">Berkas tidak dapat dimuat.<button type="button" onClick={onCancel} className="font-bold underline">Tutup</button></div>;
  return <MasterImport key={resumeId ?? "new"} kind={kind} saved={saved.data} onSaved={onSaved} onCancel={onCancel} />;
}

function MasterWorkspace({ kind }: { kind: MasterKind }) {
  const queryClient = useQueryClient();
  const descriptor = MASTER_TYPES.find((item) => item.key === kind)!;
  const [batchId, setBatchId] = useState<number | undefined>();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [status, setStatus] = useState<MasterStatus>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [showImport, setShowImport] = useState(false);
  const [resumeId, setResumeId] = useState<number | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [notice, setNotice] = useState<ImportResult & { filename: string } | null>(null);

  const batches = useQuery({ queryKey: ["masters", kind, "batches"], queryFn: () => masterApi.batches(kind) });
  const summary = useQuery({ queryKey: ["masters", kind, "summary", batchId], queryFn: () => masterApi.summary(kind, batchId) });
  const records = useQuery({ queryKey: ["masters", kind, "records", batchId, deferredSearch, status, page, pageSize], queryFn: () => masterApi.records(kind, { batch_id: batchId, q: deferredSearch, status, skip: (page - 1) * pageSize, limit: pageSize }) });
  const selectedBatch = batches.data?.find((batch) => batch.id === batchId);
  const totalPages = Math.max(1, Math.ceil((records.data?.total ?? 0) / pageSize));
  const failed = batches.isError || summary.isError || records.isError;

  const imported = (result: ImportResult, filename: string) => {
    setNotice({ ...result, filename }); setShowImport(false); setResumeId(null);
    setBatchId(result.batch_id); setSearch(""); setStatus("all"); setPage(1);
    void queryClient.invalidateQueries({ queryKey: ["masters", kind] });
    void queryClient.invalidateQueries({ queryKey: ["upload", "batches"] });
  };

  return <div className="space-y-5 sm:space-y-6">
    <header className="flex flex-col justify-between gap-4 border-b border-neo-border pb-4 sm:flex-row sm:items-center">
      <div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-neo-border">Referensi pelanggan</p><h1 className="fluid-h1 mt-1 flex items-center gap-2 font-black"><Database size={25} className="shrink-0" />Data Master {descriptor.label}</h1><p className="mt-1 text-xs text-neo-border sm:text-sm">{descriptor.description}</p></div>
      <div className="flex gap-2"><button type="button" aria-label="Muat ulang data master" onClick={() => void queryClient.invalidateQueries({ queryKey: ["masters", kind] })} className="touch-min rounded-sm border-2 border-neo-border bg-white px-3 shadow-[2px_2px_0_#0a0a0a] hover:bg-gray-100"><RefreshCw size={16} className={batches.isFetching || summary.isFetching || records.isFetching ? "animate-spin" : ""} /></button>
        <button type="button" onClick={() => { setResumeId(null); setShowImport(true); }} disabled={showImport} className="touch-min gap-2 rounded-sm border-2 border-neo-border bg-neo-black px-4 text-xs font-bold text-white shadow-[2px_2px_0_#ff6b35] hover:bg-neutral-800 disabled:opacity-40"><Plus size={16} />Unggah berkas</button></div>
    </header>
    <nav aria-label="Jenis data master" className="flex gap-2 overflow-x-auto pb-1">
      {MASTER_TYPES.map((item) => <Link key={item.key} to={`/master/${item.key}`} aria-current={kind === item.key ? "page" : undefined} className={`touch-min whitespace-nowrap rounded-sm border-2 border-neo-border px-5 text-xs font-bold ${kind === item.key ? "bg-neo-black text-white shadow-[2px_2px_0_#ff6b35]" : "bg-white hover:bg-gray-100"}`}>{item.label}</Link>)}
    </nav>
    {notice && <div role="status" className={`flex items-start justify-between gap-3 rounded-sm border-2 p-4 text-xs ${notice.error_rows ? "border-amber-600 bg-amber-50 text-amber-900" : "border-green-600 bg-green-50 text-green-800"}`}>
      <div><p className="font-black">{notice.filename} berhasil disimpan.</p><p className="mt-1">{count(notice.valid_rows)} baris lolos validasi · {count(notice.error_rows)} baris perlu diperbaiki. Data asli tetap tersimpan.</p>{notice.error_rows > 0 && <button type="button" onClick={() => { setStatus("invalid"); setPage(1); }} className="mt-2 font-bold underline">Lihat baris bermasalah</button>}</div>
      <button type="button" onClick={() => setNotice(null)} aria-label="Tutup pemberitahuan" className="p-1"><X size={16} /></button>
    </div>}
    {showImport && <ImportPanel key={`${kind}-${resumeId ?? "new"}`} kind={kind} resumeId={resumeId} onSaved={imported} onCancel={() => { setShowImport(false); setResumeId(null); }} />}
    {failed && <div role="alert" className="flex items-start gap-2 rounded-sm border-2 border-red-600 bg-red-50 p-4 text-sm text-red-700"><AlertCircle size={18} className="shrink-0" />Data master belum dapat dimuat. Periksa koneksi dan gunakan tombol muat ulang.</div>}
    <section aria-label="Ringkasan data master" className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {[
        { label: "Total baris", value: summary.data?.total_rows, icon: FileSpreadsheet, color: "bg-white" },
        { label: "Lolos validasi", value: summary.data?.valid_rows, icon: CheckCircle2, color: "bg-green-50" },
        { label: "Koordinat belum lengkap", value: summary.data?.incomplete_coordinates, icon: MapPin, color: "bg-amber-50" },
        { label: "Perlu perbaikan", value: summary.data?.invalid_rows, icon: AlertCircle, color: "bg-red-50" },
      ].map((card) => <div key={card.label} className={`rounded-sm border-2 border-neo-border p-3 shadow-[2px_2px_0_#0a0a0a] sm:p-4 ${card.color}`}><div className="flex items-start justify-between gap-2"><p className="text-[10px] font-bold uppercase tracking-wide text-neo-border">{card.label}</p><card.icon size={16} className="shrink-0" /></div><p className={`mt-2 text-2xl font-black sm:text-3xl ${summary.isFetching ? "animate-pulse" : ""}`}>{count(card.value)}</p></div>)}
    </section>
    <section className="space-y-4 rounded-sm border-2 border-neo-border bg-white p-4 shadow-[3px_3px_0_#0a0a0a] sm:p-5">
      <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-end">
        <div><h2 className="text-sm font-black">Daftar sumber master</h2><p className="mt-1 text-xs text-neo-border">{count(summary.data?.ready_files)} berkas siap · {count(summary.data?.unique_idpels)} IDPEL unik · {count(summary.data?.duplicate_observations)} observasi berulang</p></div>
        <label className="flex flex-col gap-1.5 text-xs font-bold lg:min-w-80">Berkas sumber
          <select aria-label="Berkas sumber" value={batchId ?? ""} onChange={(event) => { setBatchId(event.target.value ? Number(event.target.value) : undefined); setPage(1); }} className={controlClass}><option value="">Semua berkas {descriptor.label}</option>{batches.data?.map((batch) => <option key={batch.id} value={batch.id}>{batch.filename}{batch.period ? ` · ${batch.period}` : ""}{batch.status !== "completed" ? " · Menunggu mapping" : ""}</option>)}</select>
        </label>
      </div>
      {!!summary.data?.pending_files && !selectedBatch && <div className="rounded-sm border border-amber-600 bg-amber-50 p-3 text-xs text-amber-900">Ada {summary.data.pending_files} berkas menunggu mapping. Pilih berkas tersebut untuk melanjutkan impor.</div>}
      {selectedBatch && selectedBatch.status !== "completed" && <div className="flex flex-col justify-between gap-3 rounded-sm border border-amber-600 bg-amber-50 p-3 text-xs text-amber-900 sm:flex-row sm:items-center"><p><strong>{selectedBatch.filename}</strong> memiliki {count(selectedBatch.total_rows)} baris. Selesaikan mapping agar masuk data referensi.</p><button type="button" onClick={() => { setResumeId(selectedBatch.id); setShowImport(true); }} className="touch-min shrink-0 rounded-sm border border-amber-700 bg-white px-3 font-bold">Lanjutkan mapping</button></div>}
      <div className="flex flex-col gap-3 sm:flex-row"><label className="relative flex-1"><span className="sr-only">Cari data master</span><Search size={16} className="pointer-events-none absolute top-3 left-3 text-neo-border" /><input type="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Cari IDPEL, nama, kode, atau nomor meter…" className={`${controlClass} w-full pl-9`} /></label>
        <select aria-label="Status kelengkapan data" value={status} onChange={(event) => { setStatus(event.target.value as MasterStatus); setPage(1); }} className={controlClass}><option value="all">Semua kondisi</option><option value="valid">Lolos validasi</option><option value="incomplete">Koordinat belum lengkap</option><option value="invalid">Perlu perbaikan</option></select></div>
      <p className="text-[11px] text-neo-border">Ringkasan menghitung seluruh data pada berkas terpilih. Observasi IDPEL yang berulang tetap dapat ditelusuri per sumber.</p>
      <div className="neo-scrollbar overflow-x-auto rounded-sm border border-neo-border" aria-busy={records.isFetching}>
        <table className="w-full min-w-[1050px] whitespace-nowrap text-left text-xs">
          <thead className="border-b-2 border-neo-border bg-gray-100"><tr>{["Baris", "IDPEL / Nama", "Koordinat", "Kode sumber / Gardu", "Periode", "Berkas sumber", "Kondisi", "Detail"].map((label) => <th key={label} className="p-3 font-bold">{label}</th>)}</tr></thead>
          <tbody>{records.isPending ? <tr><td colSpan={8} className="p-10 text-center text-sm" role="status">Memuat data master…</td></tr> : records.isError ? <tr><td colSpan={8} className="p-10 text-center text-red-700">Daftar data tidak dapat dimuat.</td></tr> : records.data?.items.length ? records.data.items.map((record) => <tr key={record.id} className="border-b border-gray-200 hover:bg-neo-white">
            <td className="p-3 font-mono">{displayValue(record.row_number)}</td>
            <td className="p-3"><p className="font-mono font-bold">{displayValue(record.fields.idpel)}</p><p className="mt-1 max-w-56 truncate text-neo-border">{displayValue(record.fields.nama)}</p></td>
            <td className="p-3 font-mono"><p>{displayValue(record.fields.lat)}</p><p className="mt-1">{displayValue(record.fields.lon)}</p></td>
            <td className="p-3">{kind === "dil" && <><p>KODEDLPD: <span className="font-mono">{displayValue(record.fields.kode_dlpd)}</span></p><p className="mt-1">KDDK: <span className="font-mono">{displayValue(record.fields.kddk)}</span></p></>}{record.fields.kode_dil && <p className="mt-1">Kode DIL: <span className="font-mono">{displayValue(record.fields.kode_dil)}</span></p>}<p className="mt-1">Gardu: <span className="font-mono">{displayValue(record.fields.kode_gardu)}</span></p></td>
            <td className="p-3">{displayValue(record.period)}</td><td className="p-3"><p className="max-w-48 truncate" title={record.filename}>{record.filename}</p>{record.source_sheet && <p className="mt-1 text-[10px] text-neo-border">Sheet: {record.source_sheet}</p>}</td><td className="p-3"><RecordBadge record={record} />{kind === "dil" && <p className="mt-1 text-[10px] text-neo-border">STATUS_DIL: {displayValue(record.fields.status_dil)}</p>}</td>
            <td className="p-3"><button type="button" onClick={() => setDetailId(record.id)} aria-label={`Lihat detail baris ${record.row_number ?? record.id}`} className="touch-min rounded-sm border border-neo-border px-3 font-bold hover:bg-gray-100">Detail</button></td>
          </tr>) : <tr><td colSpan={8} className="p-10 text-center"><Database size={28} className="mx-auto mb-3 text-neo-border" /><p className="text-sm font-bold">{search || status !== "all" ? "Tidak ada data sesuai pencarian." : "Belum ada data master yang siap ditampilkan."}</p><p className="mt-1 text-xs text-neo-border">{search || status !== "all" ? "Sesuaikan pencarian atau filter kondisi data." : "Unggah berkas dan konfirmasi pemetaan kolom untuk menambahkan referensi."}</p></td></tr>}</tbody>
        </table>
      </div>
      <footer className="flex flex-col justify-between gap-3 text-xs sm:flex-row sm:items-center"><p>{count(records.data?.total)} baris sesuai filter · Halaman {Math.min(page, totalPages)} dari {totalPages}</p><div className="flex items-center gap-2"><label className="sr-only" htmlFor="master-page-size">Baris per halaman</label><select id="master-page-size" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }} className={`${controlClass} text-xs`}>{[25, 50, 100].map((size) => <option key={size} value={size}>{size} baris</option>)}</select><button type="button" aria-label="Halaman sebelumnya" disabled={page <= 1 || records.isFetching} onClick={() => setPage((previous) => previous - 1)} className="touch-min rounded-sm border border-neo-border hover:bg-gray-100 disabled:opacity-30"><ArrowLeft size={16} /></button><button type="button" aria-label="Halaman berikutnya" disabled={page >= totalPages || records.isFetching} onClick={() => setPage((previous) => previous + 1)} className="touch-min rounded-sm border border-neo-border hover:bg-gray-100 disabled:opacity-30"><ArrowRight size={16} /></button></div></footer>
    </section>
    {detailId !== null && <RecordDetail key={detailId} kind={kind} id={detailId} onClose={() => setDetailId(null)} />}
  </div>;
}

export default function MasterPage() {
  const { kind } = useParams();
  if (!MASTER_TYPES.some((item) => item.key === kind)) return <Navigate to="/master/prabayar" replace />;
  return <MasterWorkspace key={kind} kind={kind as MasterKind} />;
}
