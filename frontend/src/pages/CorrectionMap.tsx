import { usePermissions } from "@/hooks/usePermissions";
import { SearchFeedback } from "@/components/data/SearchFeedback";
import { useDebouncedSearch } from "@/hooks/useDebouncedSearch";
import { CandidateCoordinateSource } from "@/components/corrections/CandidateCoordinateSource";
import { buttonClass } from "@/lib/button";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams, type SetURLSearchParams } from "react-router-dom";
import { LoaderCircle, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CorrectionMap } from "@/components/corrections/CorrectionMap";
import { CorrectionProgress } from "@/components/corrections/CorrectionProgress";
import { AutomaticExtensionNote } from "@/components/corrections/AutomaticExtensionNote";
import { PreviewPagination } from "@/components/data/PreviewPagination";
import { MapRadiusSummary } from "@/components/corrections/MapRadiusSummary";
import { coordinates } from "@/lib/correction-map";
import { CORRECTION_TYPES, correctionApi, mergeCheckProgress, searchLabel, type CorrectionCandidate, type CorrectionCheck, type CorrectionRun } from "@/lib/corrections";
import { displayValue, type CorrectionKind } from "@/lib/master";
import { PDPJ_FIELDS } from "@/lib/pdpj";
import type { ApiError } from "@/lib/api";
import { useAppStore } from "@/store/app";
import { usePdpjUpdate } from "@/hooks/usePdpjUpdate";
import { useMapRadiusSummary } from "@/hooks/useMapRadiusSummary";
import { downloadSpreadsheet, resultsApi } from "@/lib/results";

const control = "min-w-0 rounded-lg border border-ui-border bg-white px-3 py-2 text-sm disabled:opacity-50";
const button = buttonClass.secondary;
const panel = "space-y-4 rounded-lg border border-ui-border bg-white p-4 sm:p-5";
const message = (error: unknown) => {
  const value = (error as ApiError)?.message;
  return typeof value === "string" ? value : "Proses belum berhasil. Coba lagi.";
};

export default function CorrectionMapPage() {
  const [params, setParams] = useSearchParams();
  const kind: CorrectionKind = params.get("category") === "idpel_kosong" ? "idpel_kosong" : "idpel_tidak_ketemu";
  const process = Number(params.get("process_id")) || null;
  const batch = Number(params.get("batch_id")) || null;
  return <MapWorkspace key={`${kind}-${batch}-${process}`} kind={kind} batchParam={batch} processParam={process} generationParam={Number(params.get("generation")) || null} params={params} changeParams={setParams} />;
}

function MapWorkspace({ kind, batchParam, processParam, generationParam, params, changeParams }: {
  kind: CorrectionKind; batchParam: number | null; processParam: number | null; generationParam: number | null;
  params: URLSearchParams; changeParams: SetURLSearchParams;
}) {
  const client = useQueryClient();
  const user = useAppStore((state) => state.user);
  const { canWrite } = usePermissions();
  const actor = user?.username ?? "";
  const [reason, setReason] = useState("");
  const selected = Number(params.get("record_id")) || null;
  const radiusChoice = params.get("radius_meters");
  const expansionChoice = canWrite ? params.get("expansion_radius_meters") ?? "" : "";
  const [expansionOpen, setExpansionOpen] = useState(expansionChoice !== "");
  const [filterMessage, setFilterMessage] = useState("");
  const [autoRunId, setAutoRunId] = useState<number | null>(null);
  const updateView = useCallback((values: Record<string, string | null>) => {
    // Preserve edits already written to the URL while the router is still
    // committing the previous navigation to the rendered controls.
    const next = new URLSearchParams(window.location.search);
    next.delete("show_candidates");
    for (const [key, value] of Object.entries(values)) {
      if (value === null) next.delete(key); else next.set(key, value);
    }
    changeParams(next, { replace: true });
  }, [changeParams]);
  const [search, setSearch] = useState("");
  const searchQuery = useDebouncedSearch(search);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [candidatePage, setCandidatePage] = useState(1);
  const [notice, setNotice] = useState("");
  const [contextOpen, setContextOpen] = useState(false);
  const viewParam = params.get("map_view");
  const mobileView = viewParam === "targets" || viewParam === "detail" ? viewParam : "map";
  const viewMounted = useRef(false);
  const returnFocusToTargets = useRef(false);
  useEffect(() => {
    if (!viewMounted.current) { viewMounted.current = true; return; }
    if (window.matchMedia("(max-width: 1279px)").matches) document.getElementById("map-workspace")?.scrollIntoView({ block: "start", behavior: "auto" });
  }, [mobileView]);
  const [focusedCandidate, setFocusedCandidate] = useState<number | null>(null);
  const descriptor = CORRECTION_TYPES.find((item) => item.key === kind)!;
  const batches = useQuery({ queryKey: ["correction-batches", kind], queryFn: () => correctionApi.batches(kind) });
  const batch = batchParam ?? batches.data?.find((item) => item.status === "completed")?.id;
  const checks = useQuery({ queryKey: ["corrections", kind, "checks", batch], queryFn: ({ signal }) => correctionApi.checks(kind, batch!, signal), enabled: Boolean(batch) });
  const process = processParam ?? checks.data?.[0]?.process_id;
  const checkKey = ["corrections", kind, "check", process];
  const check = useQuery({ queryKey: checkKey, queryFn: async ({ signal }) => {
    const response = await correctionApi.check(kind, process!, signal);
    return mergeCheckProgress(client.getQueryData<CorrectionCheck>(["corrections", kind, "check", process]), response);
  }, enabled: Boolean(process), refetchInterval: (query) => !query.state.data?.latest_run.processing && ["queued", "running"].includes(query.state.data?.latest_run.status ?? "") ? 1500 : false });
  const restoring = batches.isPending || (!!batch && checks.isPending) || (!!process && check.isPending);
  const scopeReady = !restoring && !batches.isError && !checks.isError && !check.isError && (!process || check.data?.batch_id === batch);
  useEffect(() => {
    if (scopeReady && batch && process && (batch !== batchParam || process !== processParam)) {
      updateView({ batch_id: String(batch), process_id: String(process) });
    }
  }, [scopeReady, batch, process, batchParam, processParam, updateView]);
  const pdpjUpdate = usePdpjUpdate(kind, check.data);
  const latestGeneration = check.data?.latest_run.generation;
  const radiusExpansion = Boolean(check.data?.runs.some((item) => item.status === "completed" && item.generation < check.data!.latest_run.generation && item.radius_meters < check.data!.latest_run.radius_meters));
  const expanding = !!check.data?.current_generation && check.data.latest_run.generation > check.data.current_generation;
  const generation = generationParam ?? latestGeneration;
  const run = check.data?.runs.find((item) => item.generation === generation && (item.status === "completed" || item.processing));
  const partial = !!run?.processing && run.status !== "completed";
  const scope = { batch_id: batch, process_id: process, generation };
  const rows = useQuery({ queryKey: ["correction-map-rows", kind, process, scope], queryFn: ({ signal }) => correctionApi.allRows(kind, scope, signal), enabled: Boolean(scopeReady && run && batch) });
  const requestedRadius = Number(radiusChoice ?? run?.radius_meters ?? check.data?.latest_run.radius_meters ?? 100);
  const exceedsStoredRadius = !!run && Number.isFinite(requestedRadius) && requestedRadius > run.radius_meters;
  const radius = exceedsStoredRadius ? run!.radius_meters : requestedRadius;
  const expansionRadius = Number(expansionChoice);
  const latestRadius = check.data?.latest_run.radius_meters;
  const validExpansion = latestRadius !== undefined && Number.isFinite(expansionRadius) && expansionRadius > latestRadius && expansionRadius <= 100000;
  const validRadius = Number.isFinite(radius) && radius > 0 && radius <= 100000;
  const displayRadius = validRadius && run ? Math.min(radius, run.radius_meters) : null;
  const radiusSummary = useMapRadiusSummary(kind, process, run, displayRadius, scopeReady);
  const mapRows = useMemo(() => radiusSummary.data ? (rows.data ?? []).map((row) => {
    if (!["matched", "no_candidates"].includes(row.search_status)) return row;
    const count = radiusSummary.data.candidate_counts[row.id] ?? 0;
    return { ...row, candidate_count: count, search_status: count ? "matched" as const : "no_candidates" as const };
  }) : [], [rows.data, radiusSummary.data]);
  const active = mapRows.find((row) => row.id === selected);
  const statusChoice = params.get("status") ?? "all";
  const statusRows = useMemo(() => mapRows.filter((row) => statusChoice === "all" || row.search_status === statusChoice), [mapRows, statusChoice]);
  const busy = ["queued", "running"].includes(check.data?.latest_run.status ?? "");
  const blockedBySearch = busy && !check.data?.latest_run.processing;
  const completedView = run?.status === "completed";
  const readSearchBlocked = blockedBySearch && !completedView;
  const radiusFilterLocked = !completedView && (blockedBySearch || (busy && expanding));
  const expansionBlocked = !canWrite || busy || partial;
  const historical = Boolean(generationParam && check.data && generation !== latestGeneration);
  const targetLoading = restoring || rows.isPending || (!!run && validRadius && radiusSummary.isPending);
  const searchableTarget = Boolean(active && coordinates(active.fields) && ["matched", "no_candidates"].includes(active.search_status));
  const requested = selected && validRadius && (!active || searchableTarget) ? { id: selected, radius } : null;
  const candidateQuery = useQuery({ queryKey: ["correction-map-candidates", kind, process, generation, requested], queryFn: ({ signal }) => correctionApi.mapCandidates(kind, requested!.id, scope, requested!.radius, signal), enabled: Boolean(scopeReady && searchableTarget && run && requested && requested.radius <= run.radius_meters && !readSearchBlocked) });
  const candidates = useMemo(() => requested?.id === selected && requested?.radius === radius ? candidateQuery.data ?? [] : [], [requested?.id, requested?.radius, selected, radius, candidateQuery.data]);
  const suggestedIdpel = params.get("suggested_idpel");
  const suggestionId = (Number(params.get("suggested_candidate_id")) || null) ?? candidates.find((candidate) => String(candidate.fields.idpel) === suggestedIdpel)?.id ?? null;
  const suggestedCandidate = candidates.find((candidate) => candidate.id === suggestionId);
  const focusedSuggestion = useRef("");
  useEffect(() => {
    const index = candidates.findIndex((candidate) => candidate.id === suggestionId);
    const key = `${selected}-${generation}-${suggestionId}`;
    if (index >= 0 && suggestionId && focusedSuggestion.current !== key) {
      focusedSuggestion.current = key; setFocusedCandidate(suggestionId); setCandidatePage(Math.floor(index / 10) + 1);
    }
  }, [candidates, suggestionId, selected, generation]);
  const waitingForExpansion = Boolean(run?.id === check.data?.latest_run.id && expanding && busy && check.data?.latest_run.processing?.state === "running" && (check.data.latest_run.activity?.active || autoRunId === check.data.latest_run.id));
  const waitingForTarget = Boolean(requested && partial && !active && !targetLoading);
  const processStarted = useCallback(() => setNotice(""), []);
  const choiceKey = ["correction-choice", kind, process, selected, generation];
  const choice = useQuery({ queryKey: choiceKey, queryFn: () => correctionApi.choice(kind, process!, selected!, generation), enabled: Boolean(process && selected && active) });
  const download = useMutation({ mutationFn: () => resultsApi.download(kind, process!, run!.generation, displayRadius!, "", "all"), onSuccess: (file) => downloadSpreadsheet(file.blob, file.filename) });
  const expand = useMutation({
    mutationFn: () => {
      if (!canWrite) throw new Error("Perluasan radius hanya tersedia untuk admin dan analis.");
      if (!validExpansion || historical || expansionBlocked || !actor.trim()) throw new Error("Isi radius perluasan yang lebih besar dari radius terbaru dan nama petugas.");
      return correctionApi.retry(kind, process!, { latest_run_id: check.data!.latest_run.id, radius_meters: expansionRadius, actor: actor.trim(), request_key: crypto.randomUUID(), incremental: true });
    },
    onSuccess: (result) => { client.setQueryData(checkKey, result); setAutoRunId(result.latest_run.id); updateView({ generation: null, radius_meters: String(result.latest_run.radius_meters), expansion_radius_meters: null }); setFilterMessage(""); setPage(1); setCandidatePage(1); setNotice("Perluasan radius dimulai untuk seluruh berkas. Panel proses menampilkan progres dan durasi; pilihan sebelumnya tetap tersimpan."); },
    onError: () => { void client.invalidateQueries({ queryKey: checkKey }); },
  });
  const choose = useMutation({
    mutationFn: (candidate: number | null) => correctionApi.choose(kind, process!, selected!, { generation: generation!, expected_revision: choice.data!.revision, candidate_id: candidate, actor: actor.trim(), reason: reason.trim(), request_key: crypto.randomUUID() }),
    onSuccess: (result) => { client.setQueryData(choiceKey, result); setReason(""); setNotice(result.current?.candidate_id ? "Pilihan kandidat tersimpan." : "Pilihan dibatalkan. Riwayat tetap tersimpan."); void client.invalidateQueries({ queryKey: ["process-history"] }); void client.invalidateQueries({ queryKey: ["correction-results", process] }); void client.invalidateQueries({ queryKey: ["correction-decisions", process] }); },
    onError: () => { void client.invalidateQueries({ queryKey: choiceKey }); void client.invalidateQueries({ queryKey: checkKey }); },
  });
  const select = useCallback((id: number) => {
    if (choose.isPending || expand.isPending) return;
    updateView({ record_id: String(id), map_view: "map" });
    setCandidatePage(1); setReason(""); setNotice(""); setFocusedCandidate(null);
    document.getElementById("map-workspace")?.scrollIntoView({ block: "start", behavior: "auto" });
  }, [choose.isPending, expand.isPending, updateView]);
  const clearTarget = () => {
    if (choose.isPending || expand.isPending) return;
    returnFocusToTargets.current = true;
    updateView({ record_id: null, map_view: "targets" });
    setCandidatePage(1); setReason(""); setNotice(""); setFocusedCandidate(null);
  };
  useEffect(() => {
    if (selected !== null || !returnFocusToTargets.current) return;
    returnFocusToTargets.current = false;
    const heading = document.getElementById("map-target-list-title");
    const dock = heading?.closest("details");
    if (dock instanceof HTMLDetailsElement) dock.open = true;
    heading?.scrollIntoView({ block: "start", behavior: "auto" });
    heading?.focus({ preventScroll: true });
  }, [selected, mobileView]);
  const candidateFocus = useCallback((id: number) => { updateView({ map_view: "detail" }); const index = candidates.findIndex((item) => item.id === id); if (index >= 0) { setCandidatePage(Math.floor(index / 10) + 1); setFocusedCandidate(id); } }, [updateView, candidates]);
  useEffect(() => { if (focusedCandidate !== null) { const element = document.getElementById(`candidate-${focusedCandidate}`); element?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" }); element?.focus({ preventScroll: true }); } }, [focusedCandidate, candidatePage]);
  const searchableRows = useMemo(() => statusRows.map((row) => ({ row, values: Object.values(row.fields).map((value) => String(value ?? "").toLowerCase()) })), [statusRows]);
  const filtered = useMemo(() => {
    const needle = searchQuery.trim().toLowerCase();
    return searchableRows.filter((item) => !needle || item.values.some((value) => value.includes(needle))).map((item) => item.row);
  }, [searchableRows, searchQuery]);
  const activePage = Math.min(page, Math.max(1, Math.ceil(filtered.length / pageSize)));
  const pageRows = filtered.slice((activePage - 1) * pageSize, activePage * pageSize);
  const candidatePages = Math.max(1, Math.ceil(candidates.length / 10));
  const activeCandidatePage = Math.min(candidatePage, candidatePages);
  const visibleCandidates = candidates.slice((activeCandidatePage - 1) * 10, activeCandidatePage * 10);
  const canChoose = Boolean(canWrite && scopeReady && !historical && !blockedBySearch && !expand.isPending && !choose.isPending && choice.data && !choice.isFetching && actor.trim() && (!(choice.data.current || suggestedCandidate || suggestedIdpel) || reason.trim()));
  const selectedChoice = choice.data?.current?.candidate;
  const dataError = batches.error || checks.error || check.error || rows.error;
  const noCoordinates = mapRows.filter((row) => !coordinates(row.fields)).length;
  return <div className="space-y-4">
    {pdpjUpdate.update && <aside aria-label="Pembaruan versi PDPJ" className="space-y-2 rounded-lg border border-amber-700 bg-amber-50 p-4 text-sm text-amber-950"><p>Hasil PDPJ yang lebih baru tersedia. Peta ini tetap memakai versi PDPJ #{check.data?.pdpj_review_id} yang dipilih saat pemeriksaan dimulai.</p>{pdpjUpdate.pending && <p role="status">Memeriksa benturan pilihan dengan PDPJ terbaru...</p>}{pdpjUpdate.error && <p role="alert">Benturan PDPJ terbaru belum dapat diperiksa. <button type="button" className="underline" onClick={pdpjUpdate.retry}>Coba lagi</button></p>}{pdpjUpdate.update.conflicts.length > 0 && <p role="alert" className="font-semibold">{pdpjUpdate.update.conflicts.length.toLocaleString("id-ID")} keputusan berbenturan dengan PDPJ terbaru dan perlu ditinjau ulang.</p>}<Link to={`/koreksi/${descriptor.slug}?batch_id=${batch}&process_id=${process}`} className="font-semibold underline">Tinjau versi PDPJ dan hasil koreksi</Link></aside>}
    <header><p className="text-xs font-semibold uppercase text-ui-muted">Rekonsiliasi pelanggan</p><h1 className="mt-1 text-2xl font-semibold">Peta Koreksi</h1><p className="mt-2 text-sm">Pilih target dari tabel atau titik. Peta dan kandidat dalam radius tersimpan ditampilkan otomatis, lalu pilih kandidat yang sesuai.</p></header>
    <section className="geo-context space-y-4 sm:p-5" aria-label="Filter peta koreksi">
      {restoring && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Memulihkan pemeriksaan dan status proses dari server…</p>}
      <button type="button" aria-expanded={contextOpen} aria-controls="map-dataset-context" onClick={() => setContextOpen(!contextOpen)} className="flex w-full items-center justify-between text-left text-sm font-medium xl:hidden"><span>{descriptor.label} {run ? ` / Versi ${run.generation} / ${run.radius_meters} m` : ""}</span><span className="text-xs text-ui-muted">{contextOpen ? "Tutup konteks" : "Ubah konteks"}</span></button><div id="map-dataset-context" className={contextOpen ? "block" : "hidden xl:block"}><fieldset disabled={restoring} className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <label className="flex flex-col gap-1 text-xs font-semibold">Kategori<select disabled={choose.isPending || expand.isPending} aria-label="Kategori peta" value={kind} onChange={(event) => changeParams({ category: event.target.value })} className={control}>{CORRECTION_TYPES.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
        <label className="flex flex-col gap-1 text-xs font-semibold">Berkas<select disabled={choose.isPending || expand.isPending} aria-label="Berkas peta" value={batch ?? ""} onChange={(event) => changeParams({ category: kind, batch_id: event.target.value })} className={control}><option value="" disabled>Pilih berkas</option>{batches.data?.filter((item) => item.status === "completed").map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.filename}</option>)}</select></label>
        <label className="flex flex-col gap-1 text-xs font-semibold">Pemeriksaan<select disabled={choose.isPending || expand.isPending} aria-label="Pemeriksaan peta" value={process ?? ""} onChange={(event) => changeParams({ category: kind, batch_id: String(batch), process_id: event.target.value })} className={control}><option value="" disabled>Pilih pemeriksaan</option>{checks.data?.map((item) => <option key={item.process_id} value={item.process_id}>#{item.process_id} · PDPJ #{item.pdpj_review_id}</option>)}</select></label>
        <label className="flex flex-col gap-1 text-xs font-semibold">Versi radius pemeriksaan<select aria-label="Versi radius pemeriksaan" disabled={!check.data || choose.isPending || expand.isPending || download.isPending} value={generation ?? ""} onChange={(event) => {
          const picked = check.data!.runs.find((item) => item.generation === Number(event.target.value));
          if (!picked) return;
          setPage(1); setCandidatePage(1); setReason(""); setNotice(""); setFilterMessage("");
          updateView({ generation: picked.generation === latestGeneration ? null : String(picked.generation), radius_meters: String(picked.radius_meters), expansion_radius_meters: null });
        }} className={control}><option value="" disabled>Pilih versi radius</option>{check.data?.runs.map((item) => <option key={item.id} value={item.generation} disabled={item.status !== "completed" && !item.processing}>{item.radius_meters.toLocaleString("id-ID")} m · Versi {item.generation} · {item.status === "completed" ? "Selesai" : item.processing?.state === "paused" ? "Dijeda" : item.status === "failed" ? "Terhenti" : "Belum selesai"}{item.generation === latestGeneration ? " · Terbaru" : ""}</option>)}</select></label>
      </fieldset>
      </div>
      <Link className="inline-block text-xs font-semibold underline" to={`/koreksi/${descriptor.slug}${batch ? `?batch_id=${batch}${process ? `&process_id=${process}` : ""}` : ""}`}>Buka data dan riwayat pemeriksaan</Link>
      {process && <div className="flex flex-wrap gap-4 text-xs font-semibold"><Link to={`/result?category=${kind}&process_id=${process}${generation ? `&generation=${generation}` : ""}${displayRadius !== null ? `&radius_meters=${displayRadius}` : ""}`} className="underline">Lihat Hasil Koreksi</Link><Link to={`/history?process_id=${process}${generation ? `&generation=${generation}` : ""}`} className="underline">Lihat Riwayat Proses</Link><button type="button" className="underline disabled:opacity-50" disabled={!run || displayRadius === null || download.isPending || !scopeReady} onClick={() => download.mutate()}>{download.isPending ? "Menyiapkan XLSX…" : `Unduh hasil radius ${displayRadius ?? ""} m XLSX`}</button></div>}
      <details className="text-xs"><summary>Cakupan ekspor</summary>      {run && <p className="text-xs">Ekspor mengikuti filter radius {displayRadius ?? "?"} m pada versi {run.generation} (pencarian tersimpan {run.radius_meters} m). Pilihan kandidat di luar filter tidak disertakan. Baris tanpa pilihan tetap disertakan dengan jarak kosong.</p>}</details>
      {download.isError && <p role="alert" className="text-sm text-red-700">{message(download.error)}</p>}
      {dataError && <p role="alert" className="text-sm text-red-700">{message(dataError)}</p>}
      {!process && !checks.isPending && <p className="text-sm">Belum ada pemeriksaan. Selesaikan pemeriksaan pada Data Koreksi untuk menampilkan peta.</p>}
      {check.data && batch && check.data.batch_id !== batch && <p role="alert" className="text-red-700">Pemeriksaan tidak sesuai dengan berkas terpilih.</p>}
      {historical && <p role="status" className="text-sm text-amber-900">Anda melihat versi historis {generation}. Pilihan mengikuti riwayat hingga versi ini dan tidak dapat diubah. <button className="underline" onClick={() => updateView({ generation: null, radius_meters: String(check.data!.latest_run.radius_meters) })}>Buka versi terbaru</button></p>}
      <AutomaticExtensionNote extension={run?.processing?.automatic_extension} />
      {partial && <p role="status" className="text-sm">{run.processing!.processed_rows.toLocaleString("id-ID")} dari {run.processing!.total_rows.toLocaleString("id-ID")} baris sudah tersimpan dan tersedia untuk koreksi di peta. Pilihan kandidat langsung disimpan. Pemeriksaan sisa baris dapat dilanjutkan melalui Data Koreksi tanpa mengubah pilihan yang sudah tersimpan.</p>}
      {radiusExpansion && busy && !check.data?.latest_run.processing && <LegacySearchProgress run={check.data!.latest_run} />}
      {check.data?.latest_run.status === "failed" && <p role="alert" className="text-sm text-red-700">Pencarian terakhir terhenti. Hasil yang sudah tersimpan tetap tersedia. Lanjutkan pemeriksaan melalui Data Koreksi.</p>}
    </section>
    {scopeReady && check.data?.latest_run.processing && check.data.latest_run.status !== "completed" && <CorrectionProgress key={check.data.latest_run.id} kind={kind} check={check.data} autoStart={autoRunId === check.data.latest_run.id} onStarted={processStarted} showDetails={radiusExpansion} />}
    {scopeReady && run && validRadius && <MapRadiusSummary data={radiusSummary.data} loading={radiusSummary.isFetching} failed={radiusSummary.isError} onRetry={() => void radiusSummary.refetch()} />}
<section className="geo-panel space-y-3 p-4" aria-label="Kontrol radius">
      <fieldset disabled={!scopeReady} className="grid grid-cols-2 items-end gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
        <label className="flex flex-col gap-1 text-xs font-semibold">Filter radius (meter)<input aria-label="Radius peta (meter)" type="number" min="0.01" max={run?.radius_meters ?? 100000} step="any" value={exceedsStoredRadius ? String(radius) : radiusChoice ?? (restoring ? "" : run?.radius_meters ?? check.data?.latest_run.radius_meters ?? 100)} onChange={(event) => {
          const value = Number(event.target.value);
          const exceeds = !!run && Number.isFinite(value) && value > run.radius_meters;
          setFilterMessage(exceeds ? `Filter radius maksimal ${run!.radius_meters} m. ${canWrite ? "Gunakan Radius perluasan untuk pemeriksaan yang lebih besar." : "Auditor hanya dapat melihat kandidat dalam radius pemeriksaan tersimpan."}` : "");
          setPage(1); setCandidatePage(1); updateView({ radius_meters: exceeds ? String(run!.radius_meters) : event.target.value });
        }} disabled={radiusFilterLocked || expand.isPending || choose.isPending} className={control} /></label>          <label className="flex flex-col gap-1 text-xs font-semibold">Petugas<input aria-label="Petugas peta" disabled={choose.isPending} value={actor} maxLength={80} readOnly className={control} /></label>
        {canWrite && <button type="button" disabled={choose.isPending || !validRadius || readSearchBlocked || expand.isPending || !run} onClick={() => void radiusSummary.refetch()} className={`${button} col-span-2 self-end xl:col-span-1`}>Perbarui ringkasan radius</button>}

      </fieldset>
      {(filterMessage || exceedsStoredRadius) && <p role="alert" className="text-xs text-amber-900">{filterMessage || `Filter radius dibatasi maksimal ${run?.radius_meters} m sesuai versi tersimpan.`}</p>}
      {!validRadius && <p role="alert" className="text-xs text-red-700">Filter radius harus lebih dari 0 dan maksimal {run?.radius_meters ?? 100000} meter.</p>}
      <p className="text-xs">{run ? `Filter maksimal ${run.radius_meters} m pada versi ini dan hanya membaca kandidat tersimpan.` : "Selesaikan pemeriksaan terlebih dahulu."} {!active ? " Pilih target untuk menampilkan peta dan kandidat secara otomatis." : " Kandidat diperbarui otomatis mengikuti target dan radius terpilih."}</p>
      {!canWrite && <p className="text-xs text-ui-muted">Perluasan radius hanya tersedia untuk admin dan analis. Auditor dapat mengubah filter hingga batas radius tersimpan atau melihat versi pemeriksaan yang tersedia.</p>}
      {canWrite && <details open={expansionOpen} onToggle={(event) => setExpansionOpen(event.currentTarget.open)} className="space-y-2 border-t border-ui-border pt-3" aria-label="Perluasan radius seluruh berkas"><summary className="text-sm font-medium">Perluasan radius seluruh berkas</summary>
        <p className="text-xs text-ui-muted">Radius lebih besar menjalankan pemeriksaan baru untuk seluruh berkas dan menyimpan versi baru.{historical ? " Buka versi terbaru untuk menjalankan perluasan." : partial ? " Selesaikan pemeriksaan aktif terlebih dahulu." : ""}</p>
        <fieldset disabled={!scopeReady} className="grid gap-3 sm:grid-cols-[minmax(160px,1fr)_auto]">
          <label className="flex flex-col gap-1 text-xs font-semibold">Radius perluasan (meter)<input aria-label="Radius perluasan (meter)" type="number" min={latestRadius ?? 0} max="100000" step="any" value={expansionChoice} placeholder={latestRadius === undefined ? "Radius baru" : `Lebih dari ${latestRadius} m`} onChange={(event) => updateView({ expansion_radius_meters: event.target.value })} disabled={historical || expansionBlocked || expand.isPending || choose.isPending} className={control} /></label>

          <button type="button" aria-busy={expand.isPending || waitingForExpansion} disabled={choose.isPending || expand.isPending || !validExpansion || !run || historical || expansionBlocked || !actor.trim()} onClick={() => { setNotice(""); expand.mutate(); }} className={`${buttonClass.primary} self-end`}>{expand.isPending || waitingForExpansion ? <><LoaderCircle size={16} className="animate-spin" />Memproses pencarian…</> : "Perluas pemeriksaan dan tampilkan kandidat"}</button>
        </fieldset>
        {expansionChoice !== "" && !validExpansion && <p role="alert" className="text-xs text-red-700">Radius perluasan harus lebih dari {latestRadius} m dan paling besar 100.000 m.</p>}
      </details>}
      {(expand.error || choose.error) && <p role="alert" className="text-sm text-red-700">{message(expand.error || choose.error)}</p>}
      {notice && <p role="status" className="border border-green-700 bg-green-50 p-3 text-sm">{notice}</p>}
</section>
    <div role="tablist" aria-label="Tampilan ruang kerja peta" onKeyDown={(event) => {
      const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
      const index = tabs.indexOf(document.activeElement as HTMLButtonElement);
      const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
      if (next !== null) { event.preventDefault(); tabs[next]?.click(); tabs[next]?.focus({ preventScroll: true }); }
    }} className="sticky top-0 z-20 flex gap-1 rounded-lg border border-ui-border bg-white p-1 xl:hidden">{([['map', 'Peta'], ['targets', 'Daftar'], ['detail', 'Detail']] as const).map(([value, label]) => <button key={value} type="button" role="tab" tabIndex={mobileView === value ? 0 : -1} aria-selected={mobileView === value} onClick={() => updateView({ map_view: value })} className={`flex-1 rounded-md px-3 py-2 text-sm ${mobileView === value ? 'bg-ui-accent-soft font-semibold text-ui-accent-text' : 'text-ui-muted'}`}>{label}</button>)}</div>
    <div id="map-workspace" className="geo-map-layout scroll-mt-16">
      {selected !== null && <div role="group" aria-label="Target yang dipilih" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-ui-context-border bg-ui-context px-3 py-2 xl:col-span-2">
        <p className="text-sm font-medium">{active ? `Target baris ${active.row_number}` : "Target terpilih"}</p>
        <button type="button" onClick={clearTarget} disabled={choose.isPending || expand.isPending} aria-describedby="clear-map-target-note" className={button}><X size={15} />Lepas pilihan target</button>
        <span id="clear-map-target-note" className="sr-only">Mengosongkan sorotan target dan tampilan kandidat. Keputusan kandidat yang sudah tersimpan tetap dipertahankan.</span>
      </div>}
      <div className="geo-map-main">
        <div className={mobileView === "map" ? "block" : "hidden xl:block"}>    <section className={panel} aria-label="Pemetaan koreksi">
      <p className="text-sm font-semibold">{rows.isFetching || (run && validRadius && radiusSummary.isPending) ? "Memuat seluruh target…" : `${mapRows.length} baris · ${mapRows.length - noCoordinates} bertitik · ${noCoordinates} tanpa koordinat`} · {descriptor.label}</p>
      {run && displayRadius !== null && <p className="text-xs">Tabel dan titik memakai hasil versi {run.generation}, radius {displayRadius} m.{partial && " Hanya baris versi terbaru yang sudah tersimpan yang ditampilkan."}</p>}
      <CorrectionMap rows={statusRows} selected={selected} candidates={candidates} radius={requested?.id === selected && requested.radius === radius ? radius : null} onSelect={select} onCandidate={candidateFocus} />
    </section>
</div>
        <div className={mobileView === "targets" ? "block" : "hidden xl:block"}><details open className="geo-map-dock"><summary className="font-medium">Daftar target · {descriptor.label}</summary>    <section className="geo-dock-body" aria-label="Tabel target peta">
      <h2 id="map-target-list-title" tabIndex={-1} className="scroll-mt-16 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ui-primary">Target {descriptor.label}</h2><input type="search" aria-label="Cari target peta" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Cari data target…" className={`${control} w-full`} />
      <SearchFeedback waiting={search !== searchQuery} fetching={false} />
      <label className="flex flex-col gap-1 text-xs font-semibold">Filter hasil pada radius terpilih<select aria-label="Filter hasil peta" value={statusChoice} onChange={(event) => { setPage(1); updateView({ status: event.target.value, record_id: null }); }} className={control}><option value="all">Semua hasil tersimpan</option>{Object.entries(searchLabel).filter(([key]) => key !== "not_checked").map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <div className="geo-dock-table neo-scrollbar resize-y"><table className="w-full min-w-[620px] text-left text-[13px]"><thead><tr>{["Baris", "IDPEL / Nama", "Koordinat", "Hasil", "Kandidat", "Aksi"].map((label) => <th className="p-3" key={label}>{label}</th>)}</tr></thead><tbody>{pageRows.map((row) => <tr key={row.id} onClick={() => { if (!choose.isPending) select(row.id); }} aria-selected={selected === row.id} className={`cursor-pointer border-t ${selected === row.id ? "bg-blue-50" : "hover:bg-gray-50"}`}><td className="p-3">{row.row_number}</td><td className="p-3">{displayValue(row.fields.idpel)}<p>{displayValue(row.fields.nama)}</p></td><td className="p-3">{coordinates(row.fields) ? `${row.fields.lat}, ${row.fields.lon}` : "Koordinat belum lengkap"}</td><td className="p-3">{searchLabel[row.search_status]}</td><td className="p-3">{row.candidate_count}</td><td className="p-3"><button aria-label={`Pilih target baris ${row.row_number}`} disabled={choose.isPending} onClick={(event) => { event.stopPropagation(); select(row.id); }} className={selected === row.id ? buttonClass.primary : button}>{selected === row.id ? "Terpilih" : "Pilih target"}</button></td></tr>)}</tbody></table>{!rows.isFetching && !pageRows.length && <p className="p-5 text-center text-sm">Tidak ada target sesuai cakupan atau pencarian.</p>}</div>
      <PreviewPagination key={`${generation}-${radius}-${statusChoice}-${search}-${pageSize}`} context="peta" page={activePage} pageSize={pageSize} total={run ? rows.data && radiusSummary.data ? filtered.length : undefined : 0} loading={restoring || rows.isFetching || radiusSummary.isFetching} onPageChange={setPage} onPageSizeChange={setPageSize} />
    </section>
</details>
</div>
      </div>
      <aside aria-label="Inspeksi target dan kandidat" className={`geo-map-inspector ${mobileView === "detail" || (mobileView === "map" && selected) ? 'block' : 'hidden xl:block'}`}>
        {!active && <section className="geo-panel space-y-3 p-5"><h2 className="text-base font-semibold">Periksa target</h2><p className="text-sm text-ui-muted">Pilih titik pada peta atau baris pada daftar target. Identitas, bukti sumber, dan kandidat akan tampil di sini.</p></section>}
    {active && <section className={panel} aria-label="Detail target terpilih"><h2 className="font-semibold">Target baris {active.row_number}</h2><p className="text-sm">{displayValue(active.fields.idpel)} · {displayValue(active.fields.nama)} · {searchLabel[active.search_status]}</p>
      <details><summary className="cursor-pointer text-xs font-semibold">Seluruh data target</summary><Fields fields={active.fields} /></details>
      {!coordinates(active.fields) && <p className="text-sm text-amber-900">Target belum mempunyai koordinat lengkap. Perbaiki data sumber dan unggah sebagai berkas baru sebelum mencari kandidat.</p>}
      {active.conflicts.length > 0 && <p className="text-sm text-red-700">Target berbenturan dengan PDPJ dan tidak dapat dipilihkan kandidat. Lihat rincian benturan di Data Koreksi.</p>}
      {active.search_status === "invalid_data" && <p className="text-sm text-amber-900">Data target perlu diperbaiki sebelum kandidat dapat ditampilkan. Tinjau rincian pada Data Koreksi.</p>}
      {active.warnings.length > 0 && <p className="text-sm text-amber-900">Koordinat sama dengan baris PDPJ; periksa bukti identitas dan detail sumber sebelum memilih.</p>}
      {choice.isError && <p role="alert" className="text-sm text-red-700">{message(choice.error)}</p>}
      {choice.data?.current?.candidate_id && <div className="space-y-2 border border-green-700 bg-green-50 p-3 text-sm"><p className="font-semibold">Pilihan aktif: {displayValue(selectedChoice?.fields?.idpel)} · {selectedChoice?.distance_meters?.toFixed(2)} m</p><p>Dipilih oleh {choice.data.current.actor} · Versi pencarian {choice.data.current.generation}. Pilihan ini tetap disimpan ketika radius berubah.</p><details><summary className="cursor-pointer font-semibold">Detail pilihan aktif</summary><Fields fields={selectedChoice?.fields ?? {}} /></details>{canWrite && <button disabled={!canChoose} className={button} onClick={() => choose.mutate(null)}>Batalkan pilihan</button>}</div>}
      {suggestedCandidate && choice.data?.current?.candidate_id !== suggestedCandidate.id && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">Usulan IDPEL {displayValue(suggestedCandidate.fields.idpel)} untuk target ini masih perlu verifikasi identitas. Isi dasar verifikasi pada alasan perubahan sebelum memilih kandidat.</p>}
      {suggestedIdpel && !suggestedCandidate && !candidateQuery.isFetching && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">Usulan lanjutan IDPEL {suggestedIdpel} belum tersedia pada kandidat dalam radius ini. Tinjau perluasan pemeriksaan dan verifikasi identitas sebelum menyimpan pilihan.</p>}
      {(suggestedCandidate || suggestedIdpel) && <Link to={`/koreksi/pemilihan-otomatis?category=${kind}&batch_id=${batch}&process_id=${process}&generation=${generation}&radius_meters=${displayRadius}&tie_strategy=suggest`} className="inline-block text-xs font-semibold underline">Kembali ke usulan pasangan</Link>}
      {canWrite && <label className="flex flex-col gap-1 text-xs font-semibold">Alasan perubahan pilihan<textarea aria-label="Alasan perubahan pilihan" disabled={choose.isPending} placeholder="Wajib untuk mengganti atau membatalkan pilihan" maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} className={control} /></label>}
      {choice.data && choice.data.history.length > 0 && <details><summary className="cursor-pointer text-xs font-semibold">Riwayat pilihan ({choice.data.history.length})</summary><ol className="mt-3 space-y-3">{choice.data.history.map((event) => <li key={event.id} className="border p-3 text-xs"><p>Revisi {event.revision} · {event.actor} · {new Date(event.created_at + "Z").toLocaleString("id-ID")}</p><p>{event.candidate_id ? `IDPEL ${displayValue(event.candidate.fields?.idpel)} · ${event.candidate.distance_meters?.toFixed(2)} m` : "Pilihan dibatalkan"} · Versi {event.generation}</p><p>{event.reason}</p></li>)}</ol></details>}
    </section>}
    {requested && requested.id === selected && <section className={panel} aria-label="Kandidat target peta" aria-busy={targetLoading || candidateQuery.isFetching || readSearchBlocked}>
      <h2 className="font-semibold">Kandidat dalam radius {requested.radius} m</h2>
      {targetLoading || candidateQuery.isFetching || readSearchBlocked ? <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Memuat kandidat…</p>
        : waitingForTarget ? <p role="status" className="text-sm">Target ini belum tersimpan pada versi terbaru. Lanjutkan pemeriksaan untuk menampilkan kandidatnya.</p>
        : !active ? <p role="status" className="text-sm">Target tidak tersedia pada versi ini. Pilih baris yang sudah tersimpan dari daftar target.</p>
        : candidateQuery.isError ? <p role="alert" className="text-sm text-red-700">{message(candidateQuery.error)} <button type="button" onClick={() => void candidateQuery.refetch()} className={button}>Coba lagi kandidat</button></p>
        : candidateQuery.isSuccess && !candidates.length ? <p className="text-sm">Tidak ada kandidat dalam radius ini.</p> : null}
      {active && candidateQuery.isSuccess && !targetLoading && !readSearchBlocked && <p className="text-xs">{candidates.length} kandidat tersimpan. Jarak dihitung dari koordinat target sebelum koreksi.</p>}
      <div className="grid gap-3">{visibleCandidates.map((candidate) => <CandidateCard key={candidate.id} candidate={candidate} selected={choice.data?.current?.candidate_id === candidate.id} readOnly={!canWrite} disabled={!canChoose || !candidates.some((item) => item.id === candidate.id)} choose={() => choose.mutate(candidate.id)} />)}</div>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs"><span>Halaman kandidat {activeCandidatePage} dari {candidatePages}</span><div className="flex gap-3"><button className={button} disabled={activeCandidatePage <= 1} onClick={() => setCandidatePage(activeCandidatePage - 1)}>Kandidat sebelumnya</button><button className={button} disabled={activeCandidatePage >= candidatePages} onClick={() => setCandidatePage(activeCandidatePage + 1)}>Kandidat berikutnya</button></div></div>
    </section>}
      </aside>
    </div>
  </div>;
}

function LegacySearchProgress({ run }: { run: CorrectionRun }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  const seconds = Math.max(0, Math.floor((now - Date.parse(run.created_at.endsWith("Z") || /[+-]\d\d:\d\d$/.test(run.created_at) ? run.created_at : `${run.created_at}Z`)) / 1000));
  return <div role="status" aria-label="Progres pencarian sebelumnya" aria-busy="true" className="space-y-2 rounded-lg border border-amber-700 bg-amber-50 p-3 text-sm"><p className="flex items-center gap-2 font-semibold"><LoaderCircle size={16} className="animate-spin" />{run.status === "queued" ? "Menunggu antrean pencarian" : "Pencarian sedang diproses"} · Radius {run.radius_meters} m</p><p>Waktu sejak permintaan: {Math.floor(seconds / 60)} menit {seconds % 60} detik. Pekerjaan ini belum menyediakan progres per baris; estimasi selesai belum tersedia. Hasil sebelumnya tetap terlihat sampai versi baru selesai.</p></div>;
}

function Fields({ fields }: { fields: CorrectionCandidate["fields"] }) {
  return <dl className="mt-3 grid gap-2 sm:grid-cols-2">{PDPJ_FIELDS.filter((field) => fields[field.key] !== undefined && fields[field.key] !== null && fields[field.key] !== "").map((field) => <div key={field.key} className="min-w-0 text-xs"><dt className="font-semibold">{field.label}</dt><dd className="break-words">{displayValue(fields[field.key])}</dd></div>)}</dl>;
}

function CandidateCard({ candidate, selected, disabled, choose, readOnly }: { candidate: CorrectionCandidate; selected: boolean; disabled: boolean; choose: () => void; readOnly: boolean }) {
  return <article id={`candidate-${candidate.id}`} tabIndex={-1} className={`space-y-3 rounded-lg border p-4 focus:ring-2 focus:ring-blue-500 ${selected ? "border-green-700 bg-green-50" : "border-ui-border"}`} aria-label={`Kandidat peta ${candidate.rank}`}><h3 className="text-sm font-semibold">Kandidat {candidate.rank} · {displayValue(candidate.fields.idpel)}</h3><p className="text-sm">{displayValue(candidate.fields.nama)} · <strong>{candidate.distance_meters.toFixed(2)} m</strong></p><p className="font-mono text-xs text-ui-muted">{displayValue(candidate.fields.lat)}, {displayValue(candidate.fields.lon)}</p><details><summary className="text-xs font-medium">Detail kandidat</summary><Fields fields={candidate.fields} /></details><CandidateCoordinateSource fields={candidate.fields} /><details><summary className="cursor-pointer text-xs font-semibold">Sumber kandidat ({candidate.observations.length})</summary>{candidate.observations.map((source, index) => <div key={index} className="mt-3 border p-3 text-xs"><p className="font-semibold">{source.dataset_type} · {source.filename} · Baris {source.row_number}</p><p>{source.source_sheet}</p><Fields fields={source.fields} /></div>)}</details>{!readOnly && <button type="button" disabled={disabled || selected} onClick={choose} className={selected ? buttonClass.success : buttonClass.primary}>{selected ? "Kandidat terpilih" : `Pilih kandidat ${candidate.rank}`}</button>}</article>;
}
