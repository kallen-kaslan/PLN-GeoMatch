import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, RefreshCw, WandSparkles } from "lucide-react";
import { AutomaticSelection } from "@/components/corrections/AutomaticSelection";
import { CompleteAutomaticSelection } from "@/components/corrections/CompleteAutomaticSelection";
import { AutomaticExtensionNote } from "@/components/corrections/AutomaticExtensionNote";
import { AutomaticCandidateResults } from "@/components/corrections/AutomaticCandidateResults";
import { SavedChoicesSummary } from "@/components/corrections/SavedChoicesSummary";
import { buttonClass } from "@/lib/button";
import { CORRECTION_TYPES, correctionApi, mergeCheckProgress, type AutomaticMode, type CompleteResult, type CorrectionCheck } from "@/lib/corrections";
import { usePermissions } from "@/hooks/usePermissions";
import { useDebouncedSearch } from "@/hooks/useDebouncedSearch";
import { usePdpjUpdate } from "@/hooks/usePdpjUpdate";

const control = "min-w-0 rounded-lg border border-ui-border bg-white px-3 py-2 text-sm disabled:opacity-50";
const count = (value: number) => value.toLocaleString("id-ID");

export default function AutomaticCorrectionsPage() {
  const [params, setParams] = useSearchParams();
  const client = useQueryClient();
  const { canWrite } = usePermissions();
  const [writing, setWriting] = useState(false);
  const [radiusDraft, setRadiusDraft] = useState<{ scope: string; value: string } | null>(null);
  const descriptor = CORRECTION_TYPES.find((item) => item.key === params.get("category")) ?? CORRECTION_TYPES[0];
  const kind = descriptor.key;
  const requestedBatch = Number(params.get("batch_id")) || null;
  const requestedProcess = Number(params.get("process_id")) || null;
  const requestedGeneration = Number(params.get("generation")) || null;
  const batches = useQuery({ queryKey: ["corrections", kind, "batches"], queryFn: () => correctionApi.batches(kind) });
  const batchId = requestedBatch ?? batches.data?.find((batch) => batch.status === "completed")?.id ?? null;
  const batch = batches.data?.find((item) => item.id === batchId);
  const checks = useQuery({ queryKey: ["corrections", kind, "checks", batchId], queryFn: ({ signal }) => correctionApi.checks(kind, batchId!, signal), enabled: !!batch && batch.status === "completed" });
  const processId = requestedProcess ?? checks.data?.find((item) => item.latest_run.status === "completed")?.process_id ?? checks.data?.[0]?.process_id ?? null;
  const matchingCheck = checks.data?.find((item) => item.process_id === processId);
  const check = useQuery({ queryKey: ["corrections", kind, "check", processId],
    queryFn: async ({ signal }) => mergeCheckProgress(client.getQueryData<CorrectionCheck>(["corrections", kind, "check", processId]), await correctionApi.check(kind, processId!, signal)),
    enabled: !!matchingCheck, staleTime: 0 });
  const selected = check.data;
  const generation = requestedGeneration ?? selected?.latest_run.generation;
  const run = selected?.runs.find((item) => item.generation === generation);
  const radiusScope = `${kind}-${batchId}-${processId}-${run?.id}`;
  const radius = radiusDraft?.scope === radiusScope ? radiusDraft.value : params.get("radius_meters") ?? String(run?.radius_meters ?? "");
  const settledRadius = useDebouncedSearch(radius);
  const tieStrategy: AutomaticMode = params.get("tie_strategy") === "complete" ? "complete" : params.get("tie_strategy") === "suggest" ? "suggest" : "review";
  const setTieStrategy = (value: AutomaticMode) => { const next = new URLSearchParams(window.location.search); next.set("tie_strategy", value); setParams(next, { replace: true }); };
  const completed = (result: CompleteResult) => { setRadiusDraft(null); const next = new URLSearchParams(window.location.search); next.set("generation", String(result.generation)); next.set("radius_meters", String(result.radius_meters)); setParams(next, { replace: true }); };
  const loading = batches.isPending || (!!batch && batch.status === "completed" && checks.isPending) || (!!matchingCheck && check.isPending);
  const failed = batches.isError || (!!batch && checks.isError) || (!!matchingCheck && check.isError);
  const invalidScope = !loading && !failed && (
    (!!params.get("category") && params.get("category") !== kind)
    || ["batch_id", "process_id", "generation"].some((key) => params.has(key) && (!Number.isSafeInteger(Number(params.get(key))) || Number(params.get(key)) <= 0))
    || (!!requestedBatch && !batch) || (!!requestedProcess && !matchingCheck) || (!!requestedGeneration && !run)
    || (!!selected && (selected.batch_id !== batchId || selected.category !== kind))
  );
  const ready = !loading && !failed && !invalidScope && !!run && run.status === "completed" && selected?.latest_run.id === run.id && selected.current_generation === run.generation;
  const pdpjUpdate = usePdpjUpdate(kind, ready ? selected : undefined);
  const setRadius = (value: string) => {
    setRadiusDraft({ scope: radiusScope, value });
    const next = new URLSearchParams(window.location.search);
    next.set("radius_meters", value);
    setParams(next, { replace: true });
  };
  const selectScope = (next: Record<string, string>) => { setRadiusDraft(null); setParams(next); };
  const selectedRadius = Number(radius);
  const mapRadius = run && Number.isFinite(selectedRadius) && selectedRadius > 0 && selectedRadius <= run.radius_meters ? selectedRadius : run?.radius_meters;
  const validRadius = !!run && Number.isFinite(selectedRadius) && selectedRadius > 0 && selectedRadius <= run.radius_meters;
  const savedSummary = useQuery({
    queryKey: ["corrections", kind, "summary", batchId, processId, run?.generation, selectedRadius],
    queryFn: () => correctionApi.summary(kind, { batch_id: batchId!, process_id: processId!, generation: run!.generation, radius_meters: selectedRadius }),
    enabled: ready && validRadius && radius === settledRadius,
  });
  const mapUrl = `/peta-koreksi?category=${kind}&batch_id=${batchId}&process_id=${processId}&generation=${generation}&radius_meters=${mapRadius}`;
  const backParams = new URLSearchParams();
  if (batchId) backParams.set("batch_id", String(batchId));
  if (processId) backParams.set("process_id", String(processId));
  if (generation) backParams.set("generation", String(generation));
  if (radius) backParams.set("candidate_radius_meters", radius);
  const backUrl = `/koreksi/${descriptor.slug}?${backParams}`;
  useEffect(() => {
    if (!loading && !failed && !invalidScope && batchId && processId && matchingCheck && selected) {
      if (params.get("category") !== kind || requestedBatch !== batchId || requestedProcess !== processId) {
        const next = new URLSearchParams(params);
        next.set("category", kind); next.set("batch_id", String(batchId)); next.set("process_id", String(processId));
        setParams(next, { replace: true });
      }
    }
  }, [loading, failed, invalidScope, batchId, processId, matchingCheck, selected, params, kind, requestedBatch, requestedProcess, setParams]);
  const refresh = () => { void client.invalidateQueries({ queryKey: ["corrections", kind] }); void client.invalidateQueries({ queryKey: ["automatic-preview", kind] }); };
  return <div className="space-y-5 sm:space-y-6">
    <header className="geo-page-heading"><div><p className="mb-1 text-xs font-semibold text-ui-muted">Data Koreksi</p><h1 className="fluid-h1 flex items-center gap-2 font-semibold"><WandSparkles size={26} />Pemilihan Otomatis</h1><p className="mt-1 text-xs text-ui-muted">Pilih kandidat terdekat dari hasil pemeriksaan tersimpan, tinjau benturan, lalu ekspor XLSX.</p></div><button type="button" aria-label="Muat ulang pemilihan otomatis" className={buttonClass.secondary} disabled={writing} onClick={refresh}><RefreshCw size={16} />Muat ulang</button></header>
    <nav aria-label="Kategori data koreksi" className="flex flex-wrap gap-2">{CORRECTION_TYPES.map((item) => <Link key={item.key} to={`/koreksi/${item.slug}`} className={buttonClass.secondary}>{item.label}</Link>)}<Link to="/koreksi/pemilihan-otomatis" aria-current="page" className={buttonClass.primary}>Pemilihan Otomatis</Link></nav>
    <section aria-label="Sumber pemilihan otomatis" className="geo-context space-y-3 sm:p-5"><fieldset disabled={writing} className="grid gap-4 md:grid-cols-2">
      <label className="flex flex-col gap-1.5 text-xs font-semibold">Kategori koreksi<select aria-label="Kategori koreksi otomatis" value={kind} onChange={(event) => selectScope({ category: event.target.value })} className={control}>{CORRECTION_TYPES.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
      <label className="flex min-w-0 flex-col gap-1.5 text-xs font-semibold">Berkas koreksi<select aria-label="Berkas koreksi otomatis" value={batchId ?? ""} disabled={batches.isPending || !batches.data?.length} onChange={(event) => selectScope({ category: kind, batch_id: event.target.value })} className={control}><option value="" disabled>Pilih berkas koreksi</option>{requestedBatch && !batch && !batches.isPending && <option value={requestedBatch}>Berkas tidak ditemukan</option>}{batches.data?.map((item) => <option key={item.id} value={item.id} disabled={item.status !== "completed"}>{item.filename} · {count(item.total_rows)} baris{item.status !== "completed" ? " · Menunggu mapping" : ""}</option>)}</select></label>
      <label className="flex flex-col gap-1.5 text-xs font-semibold">Pemeriksaan tersimpan<select aria-label="Pemeriksaan otomatis" value={processId ?? ""} disabled={checks.isPending || !checks.data?.length} onChange={(event) => selectScope({ category: kind, batch_id: String(batchId), process_id: event.target.value })} className={control}><option value="" disabled>Pilih pemeriksaan</option>{requestedProcess && !matchingCheck && !checks.isPending && <option value={requestedProcess}>Pemeriksaan tidak ditemukan pada berkas ini</option>}{checks.data?.map((item) => <option key={item.process_id} value={item.process_id}>Pemeriksaan #{item.process_id} · PDPJ #{item.pdpj_review_id}</option>)}</select></label>
      <label className="flex flex-col gap-1.5 text-xs font-semibold">Versi hasil<select aria-label="Versi hasil otomatis" value={generation ?? ""} disabled={!selected || check.isPending} onChange={(event) => selectScope({ category: kind, batch_id: String(batchId), process_id: String(processId), generation: event.target.value })} className={control}><option value="" disabled>Pilih versi hasil</option>{requestedGeneration && !run && <option value={requestedGeneration}>Versi tidak ditemukan</option>}{selected?.runs.map((item) => <option key={item.id} value={item.generation}>Versi {item.generation} · Radius {count(item.radius_meters)} m{item.status !== "completed" ? " · Belum selesai" : ""}</option>)}</select></label>
    </fieldset>{batch && selected && !invalidScope && <p className="text-xs text-ui-muted">{batch.filename}{batch.source_sheet ? ` · Sheet ${batch.source_sheet}` : ""} · Pemeriksaan #{processId} · PDPJ #{selected.pdpj_review_id}. Pilihan tersimpan tetap terhubung dengan pemeriksaan ini.</p>}</section>
    {loading && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Memuat berkas dan pemeriksaan tersimpan...</p>}
    {failed && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">Data belum dapat dimuat. <button type="button" className="underline" onClick={refresh}>Coba lagi</button></p>}
    {invalidScope && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">Berkas, pemeriksaan, atau versi tidak sesuai. Pilih kembali sumber pemilihan otomatis.</p>}
    {ready && pdpjUpdate.update && <p role="status" className="rounded-lg bg-amber-50 p-4 text-sm text-amber-950">Versi PDPJ yang lebih baru tersedia. Pilihan otomatis ini tetap menggunakan PDPJ #{selected?.pdpj_review_id} pada pemeriksaan asal.{pdpjUpdate.update.conflicts.length > 0 && ` ${count(pdpjUpdate.update.conflicts.length)} pilihan tersimpan perlu ditinjau.`} <Link to={backUrl} className="font-semibold underline">Tinjau pembaruan melalui Data Koreksi</Link>.</p>}
    {!loading && !failed && !invalidScope && (!batch || !processId) && <p role="status" className="rounded-lg border border-ui-border bg-white p-4 text-sm">Belum ada pemeriksaan untuk pemilihan otomatis. <Link to={`/koreksi/${descriptor.slug}`} className="font-semibold underline">Buka Data Koreksi</Link> untuk mengunggah berkas dan menyelesaikan pemeriksaan.</p>}
    {!loading && !failed && !invalidScope && run && !ready && <p role="status" className="rounded-lg bg-amber-50 p-4 text-sm text-amber-950">Pemilihan otomatis hanya tersedia pada hasil terbaru yang sudah selesai. <Link to={backUrl} className="font-semibold underline">Buka pemeriksaan asal</Link> untuk melihat progres atau melanjutkan pemeriksaan.</p>}
    {ready && batchId && processId && run && <>
      <AutomaticExtensionNote extension={run.processing?.automatic_extension} />
      {validRadius && radius === settledRadius && <SavedChoicesSummary data={savedSummary.data?.saved_choices} resultUrl={`/result?category=${kind}&process_id=${processId}&generation=${generation}&radius_meters=${selectedRadius}`} />}
      <div className="flex flex-wrap gap-4 text-xs font-semibold"><Link to={mapUrl} className="underline">Tinjau melalui Peta Koreksi</Link><Link to={`/result?category=${kind}&process_id=${processId}&generation=${generation}&radius_meters=${mapRadius}`} className="underline">Hasil pemeriksaan ini</Link></div>
      {!canWrite ? <p role="status" className="rounded-lg bg-blue-50 p-4 text-sm">Auditor dapat meninjau kandidat. Penyimpanan pilihan otomatis tersedia bagi admin dan analis.</p> : tieStrategy === "complete" ? <CompleteAutomaticSelection key={`complete-${kind}-${processId}`} kind={kind} processId={processId} batchId={batchId} run={run} radius={radius} onRadiusChange={setRadius} onModeChange={setTieStrategy} onBusyChange={setWriting} onCompleted={completed} /> : <AutomaticSelection key={`automatic-${kind}-${processId}-${run.id}`} kind={kind} processId={processId} batchId={batchId} run={run} radius={radius} onRadiusChange={setRadius} onBusyChange={setWriting} tieStrategy={tieStrategy} onTieStrategyChange={setTieStrategy} />}
      {radius === settledRadius ? <AutomaticCandidateResults key={`candidates-${kind}-${processId}-${run.id}-${radius}`} kind={kind} label={descriptor.label} batchId={batchId} processId={processId} run={run} radius={radius} /> : <p role="status" className="text-sm">Memuat kandidat sesuai radius...</p>}
    </>}
    {batchId && <Link to={backUrl} className="inline-block text-xs font-semibold underline">Kembali ke pemeriksaan asal</Link>}
  </div>;
}
