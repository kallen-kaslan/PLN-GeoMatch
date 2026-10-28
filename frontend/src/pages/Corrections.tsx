import { buttonClass } from "@/lib/button";
import { useDeferredValue, useEffect, useRef, useState } from "react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, FolderUp, LoaderCircle, Pause, Plus, RefreshCw } from "lucide-react";
import { MasterImport } from "@/components/master/MasterImport";
import { CorrectionProgress } from "@/components/corrections/CorrectionProgress";
import { CorrectionDetail } from "@/components/corrections/CorrectionDetail";
import type { ApiError } from "@/lib/api";
import { displayValue, type CorrectionKind, type ImportResult } from "@/lib/master";
import { CORRECTION_TYPES, correctionApi, identityLabel, searchLabel, type CorrectionFilter, type CorrectionRun, type CorrectionScope } from "@/lib/corrections";
import { useAppStore } from "@/store/app";

const control = "min-w-0 rounded-sm border-2 border-neo-border bg-white px-3 py-2 text-sm disabled:opacity-50";
const button = buttonClass.secondary;
const count = (value: number | undefined) => value === undefined ? "—" : value.toLocaleString("id-ID");

function CompletedDialog({ run, onClose }: { run: CorrectionRun; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close(); }, []);
  return <dialog ref={dialog} onCancel={onClose} aria-labelledby="correction-complete-title" className="fixed inset-0 m-auto w-[calc(100%_-_2rem)] max-w-md space-y-4 rounded-sm border-2 border-neo-border bg-white p-6 shadow-[5px_5px_0_#0a0a0a] backdrop:bg-black/50">
    <CheckCircle2 size={32} className="text-green-700" /><h2 id="correction-complete-title" className="text-lg font-black">Pemeriksaan koreksi selesai</h2>
    <p className="text-sm">Hasil versi {run.generation} untuk {count(run.total_targets)} baris sudah tersimpan. {count(run.matched_targets)} baris memiliki kandidat dalam radius {count(run.radius_meters)} m.</p>
    <p className="text-xs text-neo-border">Selesai pemeriksaan belum berarti semua baris sudah dipilih kandidatnya. Tinjau ringkasan dan detail setiap baris.</p>
    <button type="button" onClick={onClose} className={button}>Lihat hasil pemeriksaan</button>
  </dialog>;
}

function CorrectionWorkspace({ kind }: { kind: CorrectionKind }) {
  const descriptor = CORRECTION_TYPES.find((item) => item.key === kind)!;
  const user = useAppStore((state) => state.user);
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [actor, setActor] = useState(user?.username ?? "");
  const [reviewChoice, setReviewChoice] = useState<number | null>(null);
  const [radiusChoice, setRadiusChoice] = useState<string | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [resumeId, setResumeId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [status, setStatus] = useState<CorrectionFilter>("all");
  const [page, setPage] = useState(1);
  const [recordId, setRecordId] = useState<number | null>(null);
  const [notice, setNotice] = useState("");
  const [processBusy, setProcessBusy] = useState(false);
  const [waitingRun, setWaitingRun] = useState<number | null>(null);
  const [autoRunId, setAutoRunId] = useState<number | null>(null);
  const [dismissedRun, setDismissedRun] = useState<number | null>(null);
  const requestedBatch = Number(params.get("batch_id")) || null;
  const requestedProcess = Number(params.get("process_id")) || null;
  const generation = Number(params.get("generation")) || undefined;

  const batches = useQuery({ queryKey: ["corrections", kind, "batches"], queryFn: () => correctionApi.batches(kind) });
  const batchId = requestedBatch ?? batches.data?.[0]?.id ?? null;
  const batch = batches.data?.find((item) => item.id === batchId);
  const readyPdpj = useQuery({ queryKey: ["pdpj", "ready-for-correction"], queryFn: correctionApi.readyPdpj });
  const checks = useQuery({ queryKey: ["corrections", kind, "checks", batchId], queryFn: () => correctionApi.checks(kind, batchId!), enabled: batchId !== null });
  const processId = requestedProcess ?? checks.data?.[0]?.process_id ?? null;
  const check = useQuery({ queryKey: ["corrections", kind, "check", processId], queryFn: () => correctionApi.check(kind, processId!), enabled: processId !== null,
    refetchInterval: (query) => !query.state.data?.latest_run?.processing && ["queued", "running"].includes(query.state.data?.latest_run?.status ?? "") ? 1500 : false });
  const activeGeneration = (generation ?? (check.data?.latest_run.processing ? check.data.latest_run.generation : check.data?.current_generation)) || undefined;
  const displayedRun = check.data?.runs.find((run) => run.generation === activeGeneration);
  const partialResults = !!displayedRun?.processing && displayedRun.status !== "completed";
  const scope: CorrectionScope = { batch_id: batchId ?? undefined, process_id: processId ?? undefined, generation: activeGeneration };
  const summary = useQuery({ queryKey: ["corrections", kind, "summary", batchId, processId, activeGeneration], queryFn: () => correctionApi.summary(kind, scope) });
  const records = useQuery({ queryKey: ["corrections", kind, "rows", batchId, processId, activeGeneration, deferredSearch, status, page], queryFn: () => correctionApi.rows(kind, { ...scope, q: deferredSearch, status, skip: (page - 1) * 25, limit: 25 }) });
  const saved = useQuery({ queryKey: ["corrections", kind, "batch", resumeId], queryFn: () => correctionApi.batch(kind, resumeId!), enabled: resumeId !== null });
  const reviewId = reviewChoice ?? check.data?.pdpj_review_id ?? readyPdpj.data?.[0]?.review_id ?? null;
  const radius = radiusChoice ?? String(check.data?.latest_run.radius_meters ?? 100);
  const pending = check.data?.latest_run.status === "queued" || check.data?.latest_run.status === "running";
  const paused = check.data?.latest_run.processing?.state === "paused";
  const processingActive = processBusy || check.data?.latest_run.activity?.active === true;
  const waitingToResume = !!check.data?.latest_run.processing && !paused && !processingActive;
  const newSource = check.data && reviewId !== check.data.pdpj_review_id;
  const totalPages = Math.max(1, Math.ceil((records.data?.total ?? 0) / 25));

  const awaitedRun = check.data?.runs.find((item) => item.id === waitingRun);
  const completed = awaitedRun?.status === "completed" && awaitedRun.id !== dismissedRun ? awaitedRun : null;
  useEffect(() => {
    if (awaitedRun?.status === "completed") {
      void queryClient.invalidateQueries({ queryKey: ["corrections", kind] });
    }
  }, [awaitedRun?.id, awaitedRun?.status, queryClient, kind]);

  const execute = useMutation<Awaited<ReturnType<typeof correctionApi.start>>, ApiError | Error, { requestKey: string; fresh: boolean }>({
    mutationFn: async ({ requestKey, fresh }) => {
      if (!batchId || !reviewId) throw new Error("Pilih berkas koreksi dan PDPJ yang selesai divalidasi.");
      const radiusMeters = Number(radius);
      if (!Number.isFinite(radiusMeters) || radiusMeters <= 0 || radiusMeters > 100000) throw new Error("Radius harus lebih dari 0 dan paling besar 100.000 meter.");
      if (!actor.trim()) throw new Error("Isi nama petugas untuk riwayat pemeriksaan.");
      const body = { request_key: requestKey, radius_meters: radiusMeters, actor: actor.trim(), incremental: true };
      return !fresh && check.data ? correctionApi.retry(kind, check.data.process_id, { ...body, latest_run_id: check.data.latest_run.id }) : correctionApi.start(kind, { ...body, batch_id: batchId, pdpj_review_id: reviewId });
    },
    onSuccess: (result) => {
      setParams({ batch_id: String(result.batch_id), process_id: String(result.process_id) });
      setWaitingRun(result.requested_run_id ?? null); setRecordId(null); setPage(1); setStatus("all"); setSearch(""); setNotice("");
      setAutoRunId(result.latest_run.processing?.state === "running" ? result.latest_run.id : null);
      void queryClient.invalidateQueries({ queryKey: ["corrections", kind] });
    },
  });
  const imported = (result: ImportResult, filename: string) => {
    setParams({ batch_id: String(result.batch_id) }); setShowImport(false); setResumeId(null); setRecordId(null); setPage(1);
    setStatus("all"); setSearch(""); setRadiusChoice(null); setReviewChoice(null);
    setNotice(`${filename} tersimpan: ${count(result.rows)} baris. Jalankan pemeriksaan untuk menyiapkan hasil dan kandidat.`);
    void queryClient.invalidateQueries({ queryKey: ["corrections", kind] });
  };
  const changeBatch = (value: number) => {
    setParams({ batch_id: String(value) }); setRecordId(null); setPage(1); setStatus("all"); setSearch(""); setNotice("");
    setRadiusChoice(null); setReviewChoice(null); setShowImport(false); setResumeId(null); setWaitingRun(null);
  };
  const failure = batches.isError || readyPdpj.isError || checks.isError || check.isError || summary.isError || records.isError;
  const blocked = checks.isPending || (!!processId && (check.isPending || check.isError)) || execute.isPending || pending || batch?.status !== "completed" || !reviewId || !actor.trim();
  return <div className="space-y-5 sm:space-y-6">
    <header className="flex flex-col justify-between gap-4 border-b border-neo-border pb-4 sm:flex-row sm:items-center"><div><h1 className="fluid-h1 flex items-center gap-2 font-black"><FolderUp size={26} />Data Koreksi</h1><p className="mt-1 text-sm font-bold">{descriptor.label}</p><p className="mt-1 text-xs text-neo-border">Periksa benturan dengan PDPJ dan cari kandidat dari master yang tersisa.</p></div><div className="flex gap-2"><button type="button" aria-label="Muat ulang data koreksi" onClick={() => { void queryClient.invalidateQueries({ queryKey: ["corrections", kind] }); void readyPdpj.refetch(); }} className={button}><RefreshCw size={16} /></button><button type="button" disabled={showImport} onClick={() => { setShowImport(true); setResumeId(null); }} className={buttonClass.primary}><Plus size={16} />Unggah data koreksi</button></div></header>
    <nav aria-label="Kategori data koreksi" className="flex flex-wrap gap-2">{CORRECTION_TYPES.map((item) => <Link key={item.key} to={`/koreksi/${item.slug}`} aria-current={item.key === kind ? "page" : undefined} className={`${item.key === kind ? buttonClass.primary : button}`}>{item.label}</Link>)}</nav>
    {notice && <p role="status" className="rounded-sm border-2 border-green-700 bg-green-50 p-4 text-sm text-green-800">{notice}</p>}
    {failure && <p role="alert" className="flex gap-2 rounded-sm border-2 border-red-700 bg-red-50 p-4 text-sm text-red-800"><AlertCircle size={18} />Data belum dapat dimuat. Periksa berkas/versi yang dipilih dan gunakan tombol muat ulang.</p>}
    {showImport && (resumeId !== null && saved.isPending ? <p role="status" className="text-sm">Memuat mapping berkas…</p> : saved.isError ? <p role="alert" className="text-sm text-red-700">Mapping tidak dapat dimuat.</p> : <MasterImport key={resumeId ?? "new"} kind={kind} saved={resumeId !== null ? saved.data : undefined} onSaved={imported} onCancel={() => { setShowImport(false); setResumeId(null); }} />)}
    <section className="space-y-4 rounded-sm border-2 border-neo-border bg-white p-4 shadow-[3px_3px_0_#0a0a0a] sm:p-5">
      <fieldset disabled={showImport || execute.isPending} className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2"><label className="flex min-w-0 flex-col gap-1.5 text-xs font-bold">Berkas koreksi<select aria-label="Berkas koreksi" value={batchId ?? ""} onChange={(event) => changeBatch(Number(event.target.value))} className={control}><option value="" disabled>Pilih berkas {descriptor.label}</option>{batches.data?.map((item) => <option key={item.id} value={item.id}>{item.filename} · {count(item.total_rows)} baris{item.status !== "completed" ? " · Menunggu mapping" : ""}</option>)}</select></label><label className="flex min-w-0 flex-col gap-1.5 text-xs font-bold">PDPJ selesai divalidasi<select aria-label="PDPJ selesai divalidasi" value={reviewId ?? ""} onChange={(event) => setReviewChoice(Number(event.target.value) || null)} disabled={pending || execute.isPending} className={control}><option value="">Pilih PDPJ sebagai acuan pengecualian master</option>{check.data && !readyPdpj.data?.some((item) => item.review_id === check.data.pdpj_review_id) && <option value={check.data.pdpj_review_id}>PDPJ tersimpan pada pemeriksaan ini · #{check.data.pdpj_review_id}</option>}{readyPdpj.data?.map((item) => <option key={item.review_id} value={item.review_id}>{item.filename} · Pemeriksaan #{item.review_id} · {item.completed_by}{item.publication ? ` (versi ${item.publication.version}, ${count(item.publication.row_count)}/${count(item.publication.total_rows)} baris)` : ""}</option>)}</select></label></div>
      {!readyPdpj.isPending && !readyPdpj.data?.length && !check.data && <p className="rounded-sm border border-amber-700 bg-amber-50 p-3 text-xs text-amber-900">Selesaikan pemeriksaan melalui <Link to="/pdpj" className="font-bold underline">Data PDPJ</Link> sebelum menjalankan koreksi.</p>}
      {batch && batch.status !== "completed" && <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-amber-700 bg-amber-50 p-3 text-xs text-amber-900"><p>Berkas menunggu konfirmasi mapping.</p><button type="button" onClick={() => { setResumeId(batch.id); setShowImport(true); }} className={button}>Lanjutkan mapping koreksi</button></div>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><label className="flex flex-col gap-1.5 text-xs font-bold">Petugas untuk riwayat<input aria-label="Petugas untuk riwayat" value={actor} onChange={(event) => setActor(event.target.value)} maxLength={80} className={control} placeholder="Isi nama petugas" /></label><label className="flex flex-col gap-1.5 text-xs font-bold">Radius pemeriksaan (meter)<input aria-label="Radius pemeriksaan (meter)" type="number" min="0.01" max="100000" step="any" value={radius} onChange={(event) => setRadiusChoice(event.target.value)} disabled={pending || execute.isPending} className={control} /></label><div className="flex flex-wrap items-end gap-2"><button type="button" onClick={() => execute.mutate({ requestKey: crypto.randomUUID(), fresh: !check.data || !!newSource })} disabled={blocked} className={buttonClass.primary}>{execute.isPending || (pending && processingActive) ? <LoaderCircle size={16} className="animate-spin" /> : paused ? <Pause size={16} /> : <CheckCircle2 size={16} />}{execute.isPending || pending ? paused ? "Pemeriksaan dijeda" : waitingToResume ? "Menunggu dilanjutkan" : "Pemeriksaan berjalan…" : check.data && !newSource ? "Periksa ulang" : "Jalankan pemeriksaan"}</button>{check.data && <button type="button" disabled={blocked} onClick={() => execute.mutate({ requestKey: crypto.randomUUID(), fresh: true })} className={button}>Pemeriksaan baru</button>}</div></div>
      {check.data && <p className="text-xs text-neo-border">Pemeriksaan tersimpan menggunakan PDPJ #{check.data.pdpj_review_id}. Periksa ulang mempertahankan sumber tersebut dan seluruh riwayat kandidat. Pilih PDPJ lain untuk membuat pemeriksaan baru.</p>}
      {execute.error && <p role="alert" className="text-sm text-red-700">{execute.error.message}</p>}
      {pending && !check.data?.latest_run.processing && <p role="status" className="rounded-sm border border-amber-700 bg-amber-50 p-3 text-xs text-amber-900">{check.data?.latest_run.status === "queued" ? "Pemeriksaan menunggu giliran pemrosesan." : "Pemeriksaan sedang diproses."} Popup selesai muncul setelah hasil tersimpan.{!!check.data?.current_generation && ` Tabel sementara menampilkan hasil versi ${check.data.current_generation}.`}</p>}
      {execute.isPending && <p role="status" className="rounded-sm border border-amber-700 bg-amber-50 p-3 text-xs text-amber-900">Menyiapkan pemeriksaan. Pemrosesan lokal data besar dapat memerlukan beberapa menit. Tunggu sampai hasil tersimpan.</p>}
      {check.data?.latest_run.status === "failed" && <p role="alert" className="rounded-sm border-2 border-red-700 bg-red-50 p-3 text-sm text-red-800">{check.data.latest_run.failure_code === "worker_unavailable" ? "Pemeriksaan belum berjalan karena layanan antrean tidak tersedia. Pengelola perlu menjalankan Redis dan worker, atau mengaktifkan pemrosesan lokal. Setelah itu, isi nama petugas lalu klik Periksa ulang." : "Pemeriksaan gagal. Isi nama petugas lalu klik Periksa ulang. Jika masih gagal, hubungi pengelola untuk memeriksa log server."} Hasil pemeriksaan sebelumnya tetap tersimpan.</p>}
      </fieldset>
    </section>
    {check.data?.latest_run.processing && <CorrectionProgress key={`${check.data.process_id}-${check.data.latest_run.id}`} kind={kind} check={check.data} autoStart={autoRunId === check.data.latest_run.id} onStarted={setWaitingRun} onBusyChange={setProcessBusy} />}
    {check.data?.pdpj_update && <section aria-label="Pembaruan versi PDPJ" className="space-y-3 rounded-sm border-2 border-amber-700 bg-amber-50 p-4 text-sm text-amber-950"><p>Versi PDPJ yang lebih baru tersedia: #{check.data.pdpj_update.review_id}. Pemeriksaan ini tetap menggunakan PDPJ #{check.data.pdpj_review_id}. Pilih versi terbaru di atas untuk membuat pemeriksaan baru; hasil dan keputusan sebelumnya tetap tersimpan.</p>{check.data.pdpj_update.conflicts.length > 0 && <><p role="alert" className="font-bold">{count(check.data.pdpj_update.conflicts.length)} keputusan koreksi berbenturan dengan hasil PDPJ terbaru dan perlu ditinjau ulang.</p><div className="flex flex-wrap gap-2">{check.data.pdpj_update.conflicts.map((item) => <button key={item.record_id} type="button" onClick={() => setRecordId(item.record_id)} className={button}>Tinjau data #{item.record_id}</button>)}</div></>}</section>}
    {partialResults && <p role="status" className="rounded-sm border border-amber-700 bg-amber-50 p-3 text-xs text-amber-900">Menampilkan hasil sementara versi {activeGeneration} yang sudah tersimpan. Baris yang belum diproses tetap berstatus Belum diperiksa. Validasi akhir belum selesai.</p>}
    <section aria-label={`Ringkasan ${descriptor.label}`} className="grid grid-cols-2 gap-3 xl:grid-cols-4">{[
      ["Total baris", summary.data?.total_rows, "bg-white"], ["Kandidat ditemukan", summary.data?.matched, "bg-green-50"], ["Tanpa kandidat dalam radius", summary.data?.no_candidates, "bg-amber-50"], ["Benturan dengan PDPJ", summary.data?.pdpj_conflicts, "bg-red-50"],
      ["Koordinat belum lengkap", summary.data?.incomplete_coordinates, "bg-amber-50"], ["Data perlu diperbaiki", summary.data?.invalid_data, "bg-red-50"], ["IDPEL ditemukan di master", summary.data?.identity_found, "bg-green-50"], ["Belum diperiksa", summary.data?.not_checked, "bg-white"],
    ].map(([label, value, color]) => <div key={String(label)} className={`rounded-sm border-2 border-neo-border p-3 shadow-[2px_2px_0_#0a0a0a] sm:p-4 ${color}`}><p className="text-[10px] font-bold uppercase tracking-wide text-neo-border">{label}</p><p className="mt-2 text-2xl font-black">{typeof value === "number" ? count(value) : "—"}</p></div>)}</section>
    <section className="space-y-4 rounded-sm border-2 border-neo-border bg-white p-4 shadow-[3px_3px_0_#0a0a0a] sm:p-5">
      <div><h2 className="text-sm font-black">Daftar {descriptor.label}</h2><p className="mt-1 text-xs text-neo-border">Kategori mengikuti berkas asal. Ringkasan menghitung seluruh baris pada berkas/versi terpilih, terpisah dari pencarian dan halaman tabel.</p>{processId && displayedRun && (displayedRun.status === "completed" || (displayedRun.processing?.processed_rows ?? 0) > 0) ? <Link to={`/peta-koreksi?category=${kind}&batch_id=${batchId}&process_id=${processId}${activeGeneration ? `&generation=${activeGeneration}` : ""}`} className="mt-3 inline-block text-xs font-bold underline">Buka Peta Koreksi</Link> : null}</div>
      <div className="grid gap-3 md:grid-cols-2"><label className="flex min-w-0 flex-col gap-1.5 text-xs font-bold">Pemeriksaan tersimpan<select aria-label="Pemeriksaan tersimpan" value={processId ?? ""} disabled={!checks.data?.length || execute.isPending} onChange={(event) => { setParams({ batch_id: String(batchId), process_id: event.target.value }); setRecordId(null); setRadiusChoice(null); setReviewChoice(null); setPage(1); setWaitingRun(null); }} className={control}><option value="" disabled>Belum ada pemeriksaan</option>{checks.data?.map((item) => <option key={item.process_id} value={item.process_id}>Pemeriksaan #{item.process_id} · PDPJ #{item.pdpj_review_id}</option>)}</select></label><label className="flex min-w-0 flex-col gap-1.5 text-xs font-bold">Versi hasil<select aria-label="Versi hasil" value={generation ?? ""} disabled={!check.data?.runs.some((run) => run.status === "completed" || run.processing)} onChange={(event) => { const next = { batch_id: String(batchId), process_id: String(processId), ...(event.target.value ? { generation: event.target.value } : {}) }; setParams(next); setRecordId(null); setPage(1); }} className={control}><option value="">Hasil terbaru tersimpan</option>{check.data?.runs.filter((run) => run.status === "completed" || run.processing).map((run) => <option key={run.id} value={run.generation}>Versi {run.generation} · Radius {count(run.radius_meters)} m{run.status !== "completed" ? " (hasil sementara)" : ""}</option>)}</select></label></div>
      <div className="flex flex-col gap-3 sm:flex-row"><input type="search" aria-label="Cari data koreksi" placeholder="Cari IDPEL, nama, meter, agenda, atau referensi…" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} className={`${control} flex-1`} /><select aria-label="Filter hasil koreksi" value={status} onChange={(event) => { setStatus(event.target.value as CorrectionFilter); setPage(1); }} className={control}><option value="all">Semua kondisi</option>{Object.entries(searchLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}<option value="identity_found">IDPEL ditemukan di master</option><option value="identity_not_found">IDPEL tidak ditemukan di master</option></select></div>
      <div className="overflow-x-auto rounded-sm border border-neo-border"><table className="w-full min-w-[1000px] text-left text-xs"><thead className="bg-gray-100"><tr>{["Baris", "IDPEL / Nama", "Referensi", "Koordinat", "Keberadaan IDPEL", "Hasil pemeriksaan", "Kandidat", "Detail"].map((label) => <th key={label} className="p-3">{label}</th>)}</tr></thead><tbody>{records.isPending ? <tr><td colSpan={8} className="p-8 text-center">Memuat data koreksi…</td></tr> : records.isError ? <tr><td colSpan={8} className="p-8 text-center text-red-700">Data belum dapat dimuat.</td></tr> : records.data?.items.length ? records.data.items.map((row) => <tr key={row.id} className={`border-t border-gray-200 ${recordId === row.id ? "bg-amber-50" : "hover:bg-neo-white"}`}><td className="p-3 font-mono">{row.row_number}</td><td className="p-3"><p className="font-mono font-bold">{displayValue(row.fields.idpel)}</p><p className="mt-1 max-w-48 truncate">{displayValue(row.fields.nama)}</p></td><td className="p-3 font-mono">{displayValue(row.fields.meter_ref || row.fields.agenda_ref || row.fields.survey_ref || row.fields.target_ref)}</td><td className="p-3 font-mono">{displayValue(row.fields.lat)}, {displayValue(row.fields.lon)}</td><td className="p-3">{identityLabel[row.identity_status]}</td><td className={`p-3 font-semibold ${row.search_status === "pdpj_conflict" || row.search_status === "invalid_data" ? "text-red-700" : row.search_status === "matched" ? "text-green-800" : "text-amber-900"}`}>{searchLabel[row.search_status]}</td><td className="p-3">{row.candidate_count}</td><td className="p-3"><button type="button" aria-label={`Detail koreksi baris ${row.row_number}`} onClick={() => setRecordId(row.id)} className={button}>Detail</button></td></tr>) : <tr><td colSpan={8} className="p-8 text-center">{batch?.status !== "completed" && batch ? "Selesaikan mapping untuk menampilkan baris koreksi." : "Belum ada data sesuai berkas atau filter yang dipilih."}</td></tr>}</tbody></table></div>
      <footer className="flex flex-wrap items-center justify-between gap-3 text-xs"><p>{count(records.data?.total)} baris sesuai filter · Halaman {page} dari {totalPages}</p><div className="flex gap-2"><button type="button" aria-label="Halaman koreksi sebelumnya" disabled={page <= 1 || records.isFetching} onClick={() => setPage((value) => value - 1)} className={button}><ArrowLeft size={16} /></button><button type="button" aria-label="Halaman koreksi berikutnya" disabled={page >= totalPages || records.isFetching} onClick={() => setPage((value) => value + 1)} className={button}><ArrowRight size={16} /></button></div></footer>
    </section>
    {recordId !== null && <CorrectionDetail key={`${recordId}-${processId}-${generation ?? check.data?.current_generation}`} kind={kind} recordId={recordId} scope={scope} onClose={() => setRecordId(null)} />}
    {completed && <CompletedDialog run={completed} onClose={() => setDismissedRun(completed.id)} />}
  </div>;
}

export default function CorrectionsPage() {
  const { category } = useParams();
  const descriptor = CORRECTION_TYPES.find((item) => item.slug === category);
  if (!descriptor) return <Navigate to="/koreksi/idpel-tidak-ketemu" replace />;
  return <CorrectionWorkspace key={descriptor.key} kind={descriptor.key} />;
}
