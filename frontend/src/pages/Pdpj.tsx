import { buttonClass } from "@/lib/button";
import { useDeferredValue, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, FileCheck2, LoaderCircle, Plus, RefreshCw } from "lucide-react";
import { MasterImport } from "@/components/master/MasterImport";
import { PdpjRowDetail } from "@/components/pdpj/PdpjRowDetail";
import { CompleteWithExceptionsDialog } from "@/components/pdpj/CompleteWithExceptionsDialog";
import { PdpjProgress } from "@/components/pdpj/PdpjProgress";
import type { ApiError } from "@/lib/api";
import { MASTER_TYPES, displayValue, masterApi, type ImportResult } from "@/lib/master";
import { existenceLabel, pdpjApi, reviewLabel, type PdpjCompletion, type PdpjStatus, type PdpjSummary } from "@/lib/pdpj";
import { useAppStore } from "@/store/app";

const control = "rounded-sm border-2 border-neo-border bg-white px-3 py-2 text-sm disabled:opacity-50";
const button = buttonClass.secondary;
const count = (value: number | undefined) => value === undefined ? "—" : value.toLocaleString("id-ID");

function CompletionDialog({ result, onClose }: { result: PdpjCompletion; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close(); }, []);
  const partial = result.published_review.id !== result.id;
  return <dialog ref={dialog} onCancel={onClose} aria-labelledby="pdpj-complete-title" className="fixed inset-0 m-auto w-[calc(100%-2rem)] max-w-md space-y-4 rounded-sm border-2 border-neo-border bg-white p-6 shadow-[5px_5px_0_#0a0a0a] backdrop:bg-black/50"><CheckCircle2 size={32} className="text-green-700" /><h2 id="pdpj-complete-title" className="text-lg font-black">{partial ? "Data tersimpan selesai divalidasi" : "PDPJ selesai divalidasi"}</h2><p className="text-sm">{partial ? `Versi ${result.published_review.publication?.version} dengan ${count(result.published_review.publication?.row_count)} baris siap dipakai untuk koreksi. Pemrosesan PDPJ dapat dilanjutkan dari posisi terakhir.` : "Pemeriksaan tersimpan. Data PDPJ ini siap dipakai sebagai acuan pengecualian pada proses koreksi."}</p><div className="flex flex-wrap gap-3"><button type="button" onClick={onClose} className={button}>{partial ? "Kembali ke proses PDPJ" : "Lihat hasil validasi"}</button><Link to="/upload" className={buttonClass.primary}>Buka Data Koreksi</Link></div></dialog>;
}

export default function PdpjPage() {
  const queryClient = useQueryClient();
  const user = useAppStore((state) => state.user);
  const [params, setParams] = useSearchParams();
  const requestedBatch = Number(params.get("batch_id")) || null;
  const requestedReview = Number(params.get("review_id")) || null;
  const [actor, setActor] = useState(user?.username ?? "");
  const [showImport, setShowImport] = useState(false);
  const [resumeId, setResumeId] = useState<number | null>(null);
  const [selectedMasters, setSelectedMasters] = useState<number[] | null>(null);
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [status, setStatus] = useState<PdpjStatus>("all");
  const [page, setPage] = useState(1);
  const [rowId, setRowId] = useState<number | null>(null);
  const [notice, setNotice] = useState("");
  const [completion, setCompletion] = useState<PdpjCompletion | null>(null);
  const [bulkReview, setBulkReview] = useState<PdpjSummary | null>(null);
  const [bulkSaving, setBulkSaving] = useState(false);
  const [autoRunId, setAutoRunId] = useState<number | null>(null);

  const batches = useQuery({ queryKey: ["pdpj", "batches"], queryFn: pdpjApi.batches });
  const batchId = requestedBatch ?? batches.data?.[0]?.id ?? null;
  const batch = batches.data?.find((item) => item.id === batchId);
  const reviews = useQuery({ queryKey: ["pdpj", "reviews", batchId], queryFn: () => pdpjApi.reviews(batchId!), enabled: batchId !== null });
  const selectedReview = requestedReview ? reviews.data?.find((item) => item.id === requestedReview) : reviews.data?.[0];
  const reviewId = selectedReview?.id;
  const review = useQuery({ queryKey: ["pdpj", reviewId, "summary"], queryFn: () => pdpjApi.summary(reviewId!), enabled: reviewId !== undefined });
  const records = useQuery({ queryKey: ["pdpj", reviewId, "rows", deferredSearch, status, page], queryFn: () => pdpjApi.rows(reviewId!, { q: deferredSearch, status, skip: (page - 1) * 25, limit: 25 }), enabled: reviewId !== undefined });
  const masters = useQuery({ queryKey: ["masters", "all-ready"], queryFn: async () => (await Promise.all(MASTER_TYPES.map((item) => masterApi.batches(item.key)))).flat().filter((item) => item.status === "completed") });
  const saved = useQuery({ queryKey: ["pdpj", "batch", resumeId], queryFn: () => pdpjApi.batch(resumeId!), enabled: resumeId !== null });
  const activeMasterIds = selectedMasters ?? masters.data?.map((item) => item.id) ?? [];
  const latestReview = reviews.data?.[0];

  const start = useMutation({
    mutationFn: () => pdpjApi.start(batchId!, selectedMasters ?? undefined),
    onSuccess: (result) => {
      setParams({ batch_id: String(result.batch_id), review_id: String(result.id) });
      setAutoRunId(result.processing?.state === "running" ? result.id : null);
      setRowId(null); setPage(1); setSearch(""); setStatus("all"); setNotice("Pemeriksaan PDPJ tersimpan. Progres dan hasil akan diperbarui selama proses berjalan.");
      void queryClient.invalidateQueries({ queryKey: ["pdpj"] });
    },
  });
  const approved = (result: PdpjCompletion) => {
    setBulkReview(null); setCompletion(result);
    setNotice(result.published_review.id !== result.id ? "Versi data tersimpan siap digunakan untuk koreksi. PDPJ tetap bisa dilanjutkan." : "PDPJ selesai divalidasi dan siap digunakan untuk proses koreksi.");
    void queryClient.invalidateQueries({ queryKey: ["pdpj"] });
    void queryClient.invalidateQueries({ queryKey: ["corrections"] });
  };
  const finish = useMutation<PdpjCompletion, ApiError | Error>({
    mutationFn: () => pdpjApi.complete(reviewId!, review.data!.revision, actor.trim()),
    onSuccess: approved,
  });

  const changeBatch = (id: number) => {
    setParams({ batch_id: String(id) }); setRowId(null); setPage(1); setStatus("all"); setSearch("");
    setShowImport(false); setResumeId(null); setNotice("");
  };
  const imported = (result: ImportResult, filename: string) => {
    setParams({ batch_id: String(result.batch_id) }); setShowImport(false); setResumeId(null); setRowId(null); setPage(1);
    setNotice(`${filename} tersimpan: ${count(result.rows)} baris. Jalankan pemeriksaan IDPEL terhadap master.`);
    void queryClient.invalidateQueries({ queryKey: ["pdpj"] });
  };
  const failure = batches.isError || reviews.isError || review.isError || records.isError || masters.isError;
  const totalPages = Math.max(1, Math.ceil((records.data?.total ?? 0) / 25));
  const processingIncomplete = !!review.data?.processing && review.data.processing.state !== "ready";
  const processingLocked = !!review.data?.processing && (review.data.processing.state === "running" || review.data.processing.processed_rows === 0);
  return <div className="space-y-5 sm:space-y-6">
    <header className="flex flex-col justify-between gap-4 border-b border-neo-border pb-4 sm:flex-row sm:items-center"><div><h1 className="fluid-h1 flex items-center gap-2 font-black"><FileCheck2 size={26} />Data PDPJ</h1><p className="mt-1 text-xs text-neo-border sm:text-sm">Periksa IDPEL ke seluruh master, lengkapi data, lalu selesaikan validasi sebelum koreksi.</p></div><div className="flex gap-2"><button type="button" aria-label="Muat ulang PDPJ" onClick={() => { void queryClient.invalidateQueries({ queryKey: ["pdpj"] }); void queryClient.invalidateQueries({ queryKey: ["masters", "all-ready"] }); }} className={button}><RefreshCw size={16} /></button><button type="button" onClick={() => { setShowImport(true); setResumeId(null); }} disabled={showImport} className={buttonClass.primary}><Plus size={16} />Unggah PDPJ</button></div></header>
    {notice && <p role="status" className="rounded-sm border-2 border-green-700 bg-green-50 p-4 text-sm text-green-800">{notice}</p>}
    {failure && <p role="alert" className="flex gap-2 rounded-sm border-2 border-red-600 bg-red-50 p-4 text-sm text-red-700"><AlertCircle size={18} />Data belum dapat dimuat. Gunakan tombol muat ulang PDPJ.</p>}
    {showImport && (resumeId !== null && saved.isPending ? <p role="status" className="text-sm">Memuat mapping PDPJ…</p> : saved.isError ? <p role="alert" className="text-sm text-red-700">Mapping tidak dapat dimuat.</p> : <MasterImport key={resumeId ?? "new"} kind="pdpj" saved={resumeId !== null ? saved.data : undefined} onSaved={imported} onCancel={() => { setShowImport(false); setResumeId(null); }} />)}
    <section className="space-y-4 rounded-sm border-2 border-neo-border bg-white p-4 shadow-[3px_3px_0_#0a0a0a] sm:p-5">
      <div className="grid gap-4 md:grid-cols-2"><label className="flex flex-col gap-1.5 text-xs font-bold">Berkas PDPJ<select aria-label="Berkas PDPJ" value={batchId ?? ""} onChange={(event) => changeBatch(Number(event.target.value))} className={control}><option value="" disabled>Pilih berkas PDPJ</option>{batches.data?.map((item) => <option key={item.id} value={item.id}>{item.filename} · {count(item.total_rows)} baris{item.status !== "completed" ? " · Menunggu mapping" : ""}</option>)}</select></label><label className="flex flex-col gap-1.5 text-xs font-bold">Petugas untuk riwayat<input aria-label="Petugas untuk riwayat" value={actor} onChange={(event) => setActor(event.target.value)} maxLength={80} placeholder="Isi nama petugas" className={control} /></label></div>
      {batch?.status !== "completed" && batch && <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-amber-700 bg-amber-50 p-3 text-xs text-amber-900"><p>Selesaikan mapping berkas sebelum pemeriksaan.</p><button type="button" onClick={() => { setResumeId(batch.id); setShowImport(true); }} className={button}>Lanjutkan mapping PDPJ</button></div>}
      {!batches.isPending && !batches.data?.length && <p className="text-sm text-neo-border">Belum ada berkas PDPJ. Mulai dengan tombol Unggah PDPJ.</p>}
      <details className="rounded-sm border border-gray-300 p-3"><summary className="cursor-pointer text-xs font-bold">Sumber master untuk pemeriksaan baru ({activeMasterIds.length} berkas)</summary><p className="mt-2 text-xs text-neo-border">Secara bawaan seluruh master siap dipakai. Pemeriksaan menyimpan daftar sumbernya agar hasil tidak berubah saat ada unggahan baru.</p><div className="mt-3 grid gap-2 sm:grid-cols-2">{masters.data?.map((item) => <label key={item.id} className="flex min-w-0 items-start gap-2 text-xs"><input type="checkbox" checked={activeMasterIds.includes(item.id)} onChange={(event) => setSelectedMasters(event.target.checked ? [...activeMasterIds, item.id] : activeMasterIds.filter((id) => id !== item.id))} disabled={start.isPending || latestReview?.status === "in_progress"} className="mt-0.5 size-4 shrink-0 accent-neo-accent" /><span className="break-words">{item.dataset_type.toUpperCase()} · {item.filename}{item.period ? ` · ${item.period}` : ""}</span></label>)}</div>{!masters.isPending && !masters.data?.length && <p className="mt-2 text-xs text-amber-900">Unggah referensi melalui <Link to="/master/prabayar" className="font-bold underline">Data Master</Link> terlebih dahulu.</p>}</details>
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><label className="flex flex-1 flex-col gap-1.5 text-xs font-bold">Versi pemeriksaan<select aria-label="Versi pemeriksaan" disabled={!reviews.data?.length} value={reviewId ?? ""} onChange={(event) => { setParams({ batch_id: String(batchId), review_id: event.target.value }); setRowId(null); setPage(1); }} className={control}><option value="" disabled>Belum diperiksa</option>{reviews.data?.map((item) => <option key={item.id} value={item.id}>Pemeriksaan #{item.id} · {reviewLabel(item.status, item.processing)}</option>)}</select></label><button type="button" onClick={() => start.mutate()} disabled={batch?.status !== "completed" || !activeMasterIds.length || start.isPending || reviews.isPending || latestReview?.status === "in_progress"} className={buttonClass.primary}>{start.isPending && <LoaderCircle size={16} className="animate-spin" />}{latestReview ? "Periksa ulang PDPJ" : "Periksa IDPEL ke master"}</button></div>
      {latestReview?.status === "in_progress" && <p className="text-xs text-neo-border">Lanjutkan pemeriksaan otomatis yang belum selesai atau tinjau hasilnya sebelum membuat versi baru.</p>}
      {start.isError && <p role="alert" className="text-sm text-red-700">{(start.error as unknown as ApiError).message}</p>}
    </section>
    {review.data && <>
      <PdpjProgress key={review.data.id} review={review.data} autoStart={autoRunId === review.data.id} saving={finish.isPending || bulkSaving} />
      {review.data.source_review_id !== null && <p className="rounded-sm border-2 border-blue-700 bg-blue-50 p-4 text-sm text-blue-900">Versi {review.data.publication?.version} yang disetujui: {count(review.data.publication?.row_count)} dari {count(review.data.publication?.total_rows)} baris. Versi ini tetap menjadi acuan bagi koreksi yang sudah menggunakannya. <Link to={`/pdpj?batch_id=${batchId}&review_id=${review.data.source_review_id}`} className="font-bold underline">Kembali ke pemrosesan PDPJ</Link></p>}
      {!!review.data.publications?.length && <section aria-label="Versi PDPJ untuk koreksi" className="space-y-3 rounded-sm border-2 border-green-700 bg-green-50 p-4 text-sm"><h2 className="font-black">Versi yang sudah disetujui untuk koreksi</h2>{review.data.publications.map((item) => <p key={item.id}><Link to={`/pdpj?batch_id=${batchId}&review_id=${item.id}`} className="font-bold underline">Versi {item.publication?.version} · {count(item.publication?.row_count)} / {count(item.publication?.total_rows)} baris</Link> · {item.completed_by}</p>)}<Link to="/upload" className={button}>Buka Data Koreksi</Link></section>}
      <section aria-label="Ringkasan pemeriksaan PDPJ" className="grid grid-cols-2 gap-3 xl:grid-cols-3">{[
        ["Total baris", review.data.summary.total_rows, "bg-white"], ["IDPEL ditemukan", review.data.summary.found, "bg-green-50"],
        ["IDPEL tidak ditemukan", review.data.summary.not_found, "bg-red-50"], ["IDPEL kosong / format bermasalah", review.data.summary.empty + review.data.summary.invalid, "bg-amber-50"],
        ["Koordinat belum lengkap", review.data.summary.incomplete_coordinates, "bg-amber-50"], ["Masalah belum selesai", review.data.summary.unresolved, "bg-red-50"],
      ].map(([label, value, color]) => <div key={String(label)} className={`rounded-sm border-2 border-neo-border p-3 shadow-[2px_2px_0_#0a0a0a] sm:p-4 ${color}`}><p className="text-[10px] font-bold uppercase tracking-wide text-neo-border">{label}</p><p className="mt-2 text-2xl font-black">{count(Number(value))}</p></div>)}</section>
      <section className="space-y-4 rounded-sm border-2 border-neo-border bg-white p-4 shadow-[3px_3px_0_#0a0a0a] sm:p-5"><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><h2 className="text-sm font-black">Hasil pemeriksaan · {reviewLabel(review.data.status, review.data.processing)}</h2><p className="mt-1 text-xs text-neo-border">{review.data.masters.length} sumber tersimpan · {count(review.data.summary.ready)} baris siap · {count(review.data.summary.exceptions)} pengecualian</p></div>{review.data.status === "completed" ? <Link to="/upload" className={button}><CheckCircle2 size={16} />Lanjut ke Data Koreksi</Link> : <button type="button" onClick={() => finish.mutate()} disabled={processingLocked || review.data.summary.total_rows === 0 || review.data.summary.unresolved > 0 || !actor.trim() || finish.isPending || review.isFetching} className={buttonClass.success}>{finish.isPending && <LoaderCircle size={16} className="animate-spin" />}{processingIncomplete ? "Selesaikan validasi data tersimpan" : "Selesaikan validasi PDPJ"}</button>}</div>
        <p className="text-xs text-neo-border">IDPEL ditemukan belum berarti datanya lengkap. Penyelesaian menyetujui seluruh baris lengkap; baris bermasalah memerlukan perbaikan atau alasan pengecualian.</p>
        {review.data.status !== "completed" && <div className="space-y-3 rounded-sm border border-amber-600 bg-amber-50 p-3 text-xs text-amber-950">
          {!actor.trim() && <p>Isi <strong>Petugas untuk riwayat</strong> agar tindakan penyimpanan dan penyelesaian aktif.</p>}
          {review.data.summary.unresolved > 0 && <><p>Ada {count(review.data.summary.unresolved)} baris yang masih perlu ditindaklanjuti. Anda dapat mencatat pengecualian massal dengan alasan agar proses koreksi tetap berjalan.</p><button type="button" disabled={processingLocked || review.isFetching || finish.isPending} onClick={() => setBulkReview(review.data!)} className={buttonClass.warning}>Lanjutkan dengan pengecualian massal</button></>}
        </div>}
        {review.data.status === "completed" && <p className="rounded-sm border border-green-700 bg-green-50 p-3 text-xs text-green-900">Diselesaikan oleh {review.data.completed_by}. Pemeriksaan ini terkunci; gunakan Periksa ulang PDPJ untuk pemeriksaan berikutnya.</p>}
        <details className="text-xs"><summary className="cursor-pointer font-semibold">Lihat sumber master pemeriksaan ini</summary><ul className="mt-2 list-disc space-y-1 pl-4">{review.data.masters.map((item) => <li key={item.id} className="break-words">{item.dataset_type.toUpperCase()} · {item.filename}{item.source_sheet ? ` · Sheet ${item.source_sheet}` : ""}</li>)}</ul></details>
        {finish.error && <p role="alert" className="text-sm text-red-700">{finish.error.message}</p>}
        <div className="flex flex-col gap-3 sm:flex-row"><input type="search" aria-label="Cari data PDPJ" placeholder="Cari IDPEL, nama, atau nomor meter…" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} className={`${control} min-w-0 flex-1`} /><select aria-label="Filter pemeriksaan PDPJ" value={status} onChange={(event) => { setStatus(event.target.value as PdpjStatus); setPage(1); }} className={control}>{[["all", "Semua kondisi"], ["found", "IDPEL ditemukan"], ["not_found", "IDPEL tidak ditemukan"], ["empty", "IDPEL kosong"], ["invalid", "Format IDPEL bermasalah"], ["incomplete", "Koordinat belum lengkap"], ["unresolved", "Masalah belum selesai"], ["ready", "Siap diselesaikan"], ["exception", "Dengan pengecualian"]].map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>
        <div className="overflow-x-auto rounded-sm border border-neo-border"><table className="w-full min-w-[900px] text-left text-xs"><thead className="bg-gray-100"><tr>{["Baris", "IDPEL / Nama", "Keberadaan IDPEL", "Koordinat", "Rekomendasi", "Review", "Detail"].map((label) => <th key={label} className="p-3">{label}</th>)}</tr></thead><tbody>{records.isPending ? <tr><td colSpan={7} className="p-8 text-center">Memuat hasil pemeriksaan…</td></tr> : records.isError ? <tr><td colSpan={7} className="p-8 text-center text-red-700">Hasil belum dapat dimuat.</td></tr> : records.data?.items.length ? records.data.items.map((row) => <tr key={row.id} className={`border-t border-gray-200 ${row.id === rowId ? "bg-amber-50" : "hover:bg-neo-white"}`}><td className="p-3 font-mono">{row.row_number}</td><td className="p-3"><p className="font-mono font-bold">{displayValue(row.fields.idpel)}</p><p className="mt-1 max-w-48 truncate">{displayValue(row.fields.nama)}</p></td><td className={`p-3 font-semibold ${row.existence === "found" ? "text-green-800" : "text-red-700"}`}>{existenceLabel[row.existence]}</td><td className="p-3"><p className="font-mono">{displayValue(row.fields.lat)}, {displayValue(row.fields.lon)}</p><p className="mt-1 text-[10px]">{row.coordinates_complete ? "Lengkap" : "Belum lengkap"}</p></td><td className="p-3">{row.recommendation_count} sumber</td><td className="p-3">{row.exception ? "Pengecualian beralasan" : row.issues.length ? `${row.issues.length} masalah` : row.reviewed ? "Sudah ditinjau" : "Siap disetujui"}{!!row.warnings?.length && <p className="mt-1 text-[10px] text-blue-800">IDPEL berulang · boleh dilanjutkan</p>}</td><td className="p-3"><button type="button" aria-label={`Detail PDPJ baris ${row.row_number}`} disabled={processingLocked} onClick={() => setRowId(row.id)} className={button}>Detail</button></td></tr>) : <tr><td colSpan={7} className="p-8 text-center">Tidak ada baris sesuai filter.</td></tr>}</tbody></table></div>
        <footer className="flex flex-wrap items-center justify-between gap-3 text-xs"><p>{count(records.data?.total)} baris sesuai filter · Halaman {page} dari {totalPages}</p><div className="flex gap-2"><button type="button" aria-label="Halaman PDPJ sebelumnya" disabled={page <= 1 || records.isFetching} onClick={() => setPage((previous) => previous - 1)} className={button}><ArrowLeft size={16} /></button><button type="button" aria-label="Halaman PDPJ berikutnya" disabled={page >= totalPages || records.isFetching} onClick={() => setPage((previous) => previous + 1)} className={button}><ArrowRight size={16} /></button></div></footer>
      </section>
      {rowId !== null && !processingLocked && <PdpjRowDetail key={`${reviewId}-${rowId}`} review={review.data} rowId={rowId} actor={actor} onClose={() => setRowId(null)} />}
    </>}
    {bulkReview && <CompleteWithExceptionsDialog review={bulkReview} actor={actor} onActorChange={setActor} onClose={() => setBulkReview(null)} onCompleted={approved} onPendingChange={setBulkSaving} />}
    {completion && <CompletionDialog result={completion} onClose={() => setCompletion(null)} />}
  </div>;
}
