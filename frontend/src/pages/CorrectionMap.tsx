import { MapRadiusControls } from "@/components/corrections/MapRadiusControls";
import { radiusAnalysisApiFor } from "@/lib/radius-analysis";
import { TablePagination } from "@/components/data/TablePagination";
import { SearchFeedback } from "@/components/data/SearchFeedback";
import { useDebouncedSearch } from "@/hooks/useDebouncedSearch";
import { CandidateCoordinateSource } from "@/components/corrections/CandidateCoordinateSource";
import { buttonClass } from "@/lib/button";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams, type SetURLSearchParams } from "react-router-dom";
import { LoaderCircle, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CorrectionMap } from "@/components/corrections/CorrectionMap";
import { PreviewPagination } from "@/components/data/PreviewPagination";
import { MapRadiusSummary } from "@/components/corrections/MapRadiusSummary";
import { coordinates } from "@/lib/correction-map";
import { CORRECTION_TYPES, correctionApi, mergeCheckProgress, searchLabel, type CorrectionCandidate, type CorrectionCheck } from "@/lib/corrections";
import { displayValue, type CorrectionKind } from "@/lib/master";
import { PDPJ_FIELDS } from "@/lib/pdpj";
import type { ApiError } from "@/lib/api";
import { useAppStore } from "@/store/app";
import { usePdpjUpdate } from "@/hooks/usePdpjUpdate";
import { useMapRadiusSummary } from "@/hooks/useMapRadiusSummary";

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
  const actor = user?.username?.trim() ?? "";
  const [reason, setReason] = useState("");
  const selected = Number(params.get("record_id")) || null;
  const radiusChoice = params.get("radius_meters");
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
  const [candidatePageSize, setCandidatePageSize] = useState(10);
  const [notice, setNotice] = useState("");
  const viewParam = params.get("map_view");
  const mobileView = viewParam === "targets" || viewParam === "detail" ? viewParam : "map";
  const [focusedCandidate, setFocusedCandidate] = useState<number | null>(null);
  const descriptor = CORRECTION_TYPES.find((item) => item.key === kind)!;
  const batches = useQuery({ queryKey: ["correction-batches", kind], queryFn: () => correctionApi.batches(kind) });
  const batch = batchParam ?? batches.data?.find((item) => item.status === "completed")?.id;
  const checks = useQuery({ queryKey: ["corrections", kind, "checks", batch], queryFn: ({ signal }) => correctionApi.checks(kind, batch!, signal), enabled: Boolean(batch) });
  const process = processParam ?? checks.data?.find((item) => item.runs.some((run) => run.status === "completed"))?.process_id ?? checks.data?.[0]?.process_id;
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
  const defaultGeneration = check.data?.runs.filter((item) => item.status === "completed").sort((a, b) => b.generation - a.generation)[0]?.generation ?? latestGeneration;
  const generation = generationParam ?? defaultGeneration;
  const run = check.data?.runs.find((item) => item.generation === generation && (item.status === "completed" || item.processing));
  const partial = !!run?.processing && run.status !== "completed";
  const scope = { batch_id: batch, process_id: process, generation };
  const rows = useQuery({ queryKey: ["correction-map-rows", kind, process, scope], queryFn: ({ signal }) => correctionApi.allRows(kind, scope, signal), enabled: Boolean(scopeReady && run && batch) });
  const analysisId = run?.processing?.radius_analysis_id;
  const analysis = useQuery({ queryKey: ["correction-map-analysis", kind, analysisId], queryFn: ({ signal }) => radiusAnalysisApiFor(kind).get(analysisId!, undefined, signal), enabled: scopeReady && !!analysisId, staleTime: 60_000 });
  const recommendation = analysis.data?.recommended_radius_meters;
  const recommendedRadius = analysis.data?.state === "ready" && analysis.data.batch_id === batch && analysis.data.pdpj_review_id === check.data?.pdpj_review_id && recommendation != null && recommendation > 0 && recommendation <= (run?.radius_meters ?? 0) ? recommendation : null;
  const radiusLimit = recommendedRadius ?? run?.radius_meters ?? 100;
  const requestedRadius = Number(radiusChoice ?? radiusLimit);
  const radius = Number.isFinite(requestedRadius) && requestedRadius > 0 ? Math.min(requestedRadius, radiusLimit) : radiusLimit;
  const validRadius = Number.isFinite(radius) && radius > 0 && radius <= 100000;
  const displayRadius = validRadius && run ? Math.min(radius, run.radius_meters) : null;
  const radiusSummary = useMapRadiusSummary(kind, process, run, displayRadius, scopeReady);
  const [preview, setPreview] = useState<{ run: number; applied: number; value: string } | null>(null);
  const previewValue = preview?.run === run?.id && preview?.applied === radius ? preview.value : String(radius);
  const previewValid = previewValue.trim() !== "" && Number.isFinite(Number(previewValue)) && Number(previewValue) > 0 && Number(previewValue) <= radiusLimit;
  const previewRadius = previewValid ? Number(previewValue) : radius;
  const settledPreview = useDebouncedSearch(String(previewRadius), 200);
  const previewSettled = Number(settledPreview) === previewRadius;
  const previewSummary = useMapRadiusSummary(kind, process, run, previewRadius !== radius && previewSettled ? previewRadius : displayRadius, scopeReady);
  const previewChanged = previewRadius !== radius;
  const summaryForCards = previewChanged ? (previewSettled ? previewSummary.data : undefined) : radiusSummary.data;

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
  const radiusFilterLocked = !completedView && (blockedBySearch || run?.processing?.state === "running");
  const historical = Boolean(check.data && generation !== latestGeneration);
  const targetLoading = restoring || rows.isPending || (!!run && validRadius && radiusSummary.isPending);
  const searchableTarget = Boolean(active && coordinates(active.fields) && ["matched", "no_candidates"].includes(active.search_status));
  const requested = selected && validRadius && (!active || searchableTarget) ? { id: selected, radius } : null;
  const candidateQuery = useQuery({ queryKey: ["correction-map-candidates", kind, process, generation, requested], queryFn: ({ signal }) => correctionApi.mapCandidates(kind, requested!.id, scope, requested!.radius, signal), enabled: Boolean(scopeReady && searchableTarget && run && requested && requested.radius <= run.radius_meters && !readSearchBlocked) });
  const candidates = useMemo(() => requested?.id === selected && requested?.radius === radius ? candidateQuery.data ?? [] : [], [requested?.id, requested?.radius, selected, radius, candidateQuery.data]);
  const waitingForTarget = Boolean(requested && partial && !active && !targetLoading);
  const choiceKey = ["correction-choice", kind, process, selected, generation];
  const choice = useQuery({ queryKey: choiceKey, queryFn: () => correctionApi.choice(kind, process!, selected!, generation), enabled: Boolean(process && selected && active) });
  const choose = useMutation({
    mutationFn: (candidate: number | null) => {
      if (!actor) throw new Error("Masuk ke akun untuk menyimpan pilihan kandidat.");
      return correctionApi.choose(kind, process!, selected!, { generation: generation!, expected_revision: choice.data!.revision, candidate_id: candidate, actor, reason: reason.trim(), request_key: crypto.randomUUID() });
    },
    onSuccess: (result) => { client.setQueryData(choiceKey, result); setReason(""); setNotice(result.current?.candidate_id ? "Pilihan kandidat tersimpan." : "Pilihan dibatalkan. Riwayat tetap tersimpan."); void client.invalidateQueries({ queryKey: ["process-history"] }); void client.invalidateQueries({ queryKey: ["correction-results", process] }); void client.invalidateQueries({ queryKey: ["correction-decisions", process] }); },
    onError: () => { void client.invalidateQueries({ queryKey: choiceKey }); void client.invalidateQueries({ queryKey: checkKey }); },
  });
  const select = useCallback((id: number) => {
    if (choose.isPending) return;
    updateView({ record_id: String(id), map_view: "map" });
    setCandidatePage(1); setReason(""); setNotice(""); setFocusedCandidate(null);
  }, [choose.isPending, updateView]);
  const clearTarget = () => {
    if (choose.isPending) return;
    updateView({ record_id: null, map_view: "map" });
    requestAnimationFrame(() => document.getElementById("map-canvas")?.focus({ preventScroll: true }));
    setCandidatePage(1); setReason(""); setNotice(""); setFocusedCandidate(null);
  };
  const candidateFocus = useCallback((id: number) => { updateView({ map_view: "detail" }); const index = candidates.findIndex((item) => item.id === id); if (index >= 0) { setCandidatePage(Math.floor(index / candidatePageSize) + 1); setFocusedCandidate(id); } }, [updateView, candidates, candidatePageSize]);
  useEffect(() => { if (focusedCandidate !== null) { const element = document.getElementById(`candidate-${focusedCandidate}`); element?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" }); element?.focus({ preventScroll: true }); } }, [focusedCandidate, candidatePage]);
  const searchableRows = useMemo(() => statusRows.map((row) => ({ row, values: Object.values(row.fields).map((value) => String(value ?? "").toLowerCase()) })), [statusRows]);
  const filtered = useMemo(() => {
    const needle = searchQuery.trim().toLowerCase();
    return searchableRows.filter((item) => !needle || item.values.some((value) => value.includes(needle))).map((item) => item.row);
  }, [searchableRows, searchQuery]);
  const activePage = Math.min(page, Math.max(1, Math.ceil(filtered.length / pageSize)));
  const pageRows = filtered.slice((activePage - 1) * pageSize, activePage * pageSize);
  const candidatePages = Math.max(1, Math.ceil(candidates.length / candidatePageSize));
  const activeCandidatePage = Math.min(candidatePage, candidatePages);
  const visibleCandidates = candidates.slice((activeCandidatePage - 1) * candidatePageSize, activeCandidatePage * candidatePageSize);
  const canChoose = Boolean(scopeReady && !historical && !blockedBySearch && !choose.isPending && choice.data && !choice.isFetching && actor.trim() && (!choice.data.current || reason.trim()));
  const selectedChoice = choice.data?.current?.candidate;
  const dataError = batches.error || checks.error || check.error || rows.error;
  const noCoordinates = mapRows.filter((row) => !coordinates(row.fields)).length;
  return <div className="space-y-4">
    {pdpjUpdate.update && <aside aria-label="Pembaruan versi PDPJ" className="space-y-2 rounded-lg border border-amber-700 bg-amber-50 p-4 text-sm text-amber-950"><p>Hasil PDPJ yang lebih baru tersedia. Peta ini tetap memakai versi PDPJ #{check.data?.pdpj_review_id} yang dipilih saat pemeriksaan dimulai.</p>{pdpjUpdate.pending && <p role="status">Memeriksa benturan pilihan dengan PDPJ terbaru...</p>}{pdpjUpdate.error && <p role="alert">Benturan PDPJ terbaru belum dapat diperiksa. <button type="button" className="underline" onClick={pdpjUpdate.retry}>Coba lagi</button></p>}{pdpjUpdate.update.conflicts.length > 0 && <p role="alert" className="font-semibold">{pdpjUpdate.update.conflicts.length.toLocaleString("id-ID")} keputusan berbenturan dengan PDPJ terbaru dan perlu ditinjau ulang.</p>}<Link to={`/koreksi/${descriptor.slug}?batch_id=${batch}&process_id=${process}`} className="font-semibold underline">Tinjau versi PDPJ dan hasil koreksi</Link></aside>}
    <header><h1 className="text-lg font-semibold">Peta Koreksi</h1></header>
    <section className="space-y-3 rounded-lg border border-ui-border bg-white p-4 sm:p-5" aria-label="Filter peta koreksi">
      {restoring && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Memulihkan pemeriksaan dan status proses dari server…</p>}
      <fieldset disabled={restoring} className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs font-semibold">Kategori<select disabled={choose.isPending} aria-label="Kategori peta" value={kind} onChange={(event) => changeParams({ category: event.target.value })} className={control}>{CORRECTION_TYPES.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
        <label className="flex flex-col gap-1 text-xs font-semibold">Berkas<select disabled={choose.isPending} aria-label="Berkas peta" value={batch ?? ""} onChange={(event) => changeParams({ category: kind, batch_id: event.target.value })} className={control}><option value="" disabled>Pilih berkas</option>{batches.data?.filter((item) => item.status === "completed").map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.filename}</option>)}</select></label>
      </fieldset>
      {dataError && <p role="alert" className="text-sm text-red-700">{message(dataError)}</p>}
      {!process && !checks.isPending && <p className="text-sm">Belum ada pemeriksaan. Selesaikan pemeriksaan pada Data Koreksi untuk menampilkan peta.</p>}
      {check.data && batch && check.data.batch_id !== batch && <p role="alert" className="text-red-700">Pemeriksaan tidak sesuai dengan berkas terpilih.</p>}
      {historical && <p className="text-xs text-ui-muted">Hasil terdahulu hanya dapat dilihat.</p>}
      {partial && <p role="status" className="text-sm">{run.processing!.processed_rows.toLocaleString("id-ID")} dari {run.processing!.total_rows.toLocaleString("id-ID")} baris sudah tersimpan dan tersedia untuk koreksi di peta. Pilihan kandidat langsung disimpan. Pemeriksaan sisa baris dapat dilanjutkan melalui Data Koreksi tanpa mengubah pilihan yang sudah tersimpan.</p>}
      {check.data?.latest_run.status === "failed" && <p role="alert" className="text-sm text-red-700">Pencarian terakhir terhenti. Hasil yang sudah tersimpan tetap tersedia. Lanjutkan pemeriksaan melalui Data Koreksi.</p>}
    </section>
    {scopeReady && run && <MapRadiusControls key={`${run.id}-${radius}-${radiusLimit}`} radius={radius} maximum={radiusLimit} recommended={recommendedRadius} disabled={radiusFilterLocked || choose.isPending || (!!analysisId && analysis.isPending)} loading={radiusSummary.isFetching} onPreview={(value) => { if (run) setPreview({ run: run.id, applied: radius, value }); }} onApply={(value) => { setPage(1); setCandidatePage(1); setFocusedCandidate(null); updateView({ radius_meters: String(value) }); }} />}
    {scopeReady && run && validRadius && <MapRadiusSummary kind={kind} preview={previewChanged} data={summaryForCards} loading={previewChanged ? !previewSettled || previewSummary.isFetching : radiusSummary.isFetching} failed={previewChanged ? previewSummary.isError : radiusSummary.isError} onRetry={() => void (previewChanged ? previewSummary.refetch() : radiusSummary.refetch())} />}
    {choose.error && <p role="alert" className="text-sm text-red-700">{message(choose.error)}</p>}
    {notice && <p role="status" className="rounded-lg border border-green-700 bg-green-50 p-3 text-sm">{notice}</p>}
    <div role="tablist" aria-label="Tampilan ruang kerja peta" onKeyDown={(event) => {
      const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
      const index = tabs.indexOf(document.activeElement as HTMLButtonElement);
      const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
      if (next !== null) { event.preventDefault(); tabs[next]?.click(); tabs[next]?.focus({ preventScroll: true }); }
    }} className="sticky top-0 z-20 flex gap-1 rounded-lg border border-ui-border bg-white p-1 xl:hidden">{([['map', 'Peta'], ['targets', 'Daftar'], ['detail', 'Detail']] as const).map(([value, label]) => <button key={value} type="button" role="tab" tabIndex={mobileView === value ? 0 : -1} aria-selected={mobileView === value} onClick={() => updateView({ map_view: value })} className={`flex-1 rounded-md px-3 py-2 text-sm ${mobileView === value ? 'bg-ui-accent-soft font-semibold text-ui-accent-text' : 'text-ui-muted'}`}>{label}</button>)}</div>
    <div id="map-workspace" className="geo-map-layout scroll-mt-16">
      <div className="geo-map-main">
        <div className={mobileView === "map" ? "block" : "hidden xl:block"}>    <section className={panel} aria-label="Pemetaan koreksi">
      <div className="flex min-h-10 items-center justify-between gap-3" role="group" aria-label="Pilihan peta">
        <p className="text-xs font-medium text-ui-muted">Radius peta aktif: {radius.toLocaleString("id-ID")} m</p>
        {selected !== null && <button type="button" onClick={clearTarget} disabled={choose.isPending} className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg border border-ui-border px-2.5 text-xs font-medium text-ui-accent-text hover:bg-ui-accent-soft focus-visible:outline-2 focus-visible:outline-ui-primary"><X size={14} />Lepas pilihan target</button>}
      </div>
      <p className="text-sm font-semibold">{rows.isFetching || (run && validRadius && radiusSummary.isPending) ? "Memuat seluruh target…" : `${mapRows.length} baris · ${mapRows.length - noCoordinates} bertitik · ${noCoordinates} tanpa koordinat`} · {descriptor.label}</p>
      <CorrectionMap scopeKey={`${kind}-${process}-${generation}`} rows={statusRows} selected={selected} candidates={candidates} radius={requested?.id === selected && requested.radius === radius ? radius : null} onSelect={select} onCandidate={candidateFocus} />
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
      {choice.data?.current?.candidate_id && <div className="space-y-2 border border-green-700 bg-green-50 p-3 text-sm"><p className="font-semibold">Pilihan aktif: {displayValue(selectedChoice?.fields?.idpel)} · {selectedChoice?.distance_meters?.toFixed(2)} m</p><p>Dipilih oleh {choice.data.current.actor}. Pilihan ini tetap disimpan ketika radius berubah.</p><details><summary className="cursor-pointer font-semibold">Detail pilihan aktif</summary><Fields fields={selectedChoice?.fields ?? {}} /></details><button disabled={!canChoose} className={button} onClick={() => choose.mutate(null)}>Batalkan pilihan</button></div>}
      {!actor && <p className="text-xs text-ui-muted">Masuk ke akun untuk menyimpan pilihan kandidat. Riwayat akan memakai nama akun yang masuk.</p>}
      <label className="flex flex-col gap-1 text-xs font-semibold">Alasan perubahan pilihan<textarea aria-label="Alasan perubahan pilihan" disabled={choose.isPending} placeholder="Wajib untuk mengganti atau membatalkan pilihan" maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} className={control} /></label>
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
      <div className="grid gap-3">{visibleCandidates.map((candidate) => <CandidateCard key={candidate.id} candidate={candidate} selected={choice.data?.current?.candidate_id === candidate.id} disabled={!canChoose || !candidates.some((item) => item.id === candidate.id)} choose={() => choose.mutate(candidate.id)} />)}</div>
      <TablePagination context="kandidat peta" previousLabel="Kandidat sebelumnya" nextLabel="Kandidat berikutnya" page={activeCandidatePage} pageSize={candidatePageSize} total={candidates.length} loading={candidateQuery.isFetching} unit="kandidat" onPageChange={setCandidatePage} onPageSizeChange={(size) => { setCandidatePageSize(size); setCandidatePage(1); }} />
    </section>}
      </aside>
    </div>
  </div>;
}

function Fields({ fields }: { fields: CorrectionCandidate["fields"] }) {
  return <dl className="mt-3 grid gap-2 sm:grid-cols-2">{PDPJ_FIELDS.filter((field) => fields[field.key] !== undefined && fields[field.key] !== null && fields[field.key] !== "").map((field) => <div key={field.key} className="min-w-0 text-xs"><dt className="font-semibold">{field.label}</dt><dd className="break-words">{displayValue(fields[field.key])}</dd></div>)}</dl>;
}

function CandidateCard({ candidate, selected, disabled, choose }: { candidate: CorrectionCandidate; selected: boolean; disabled: boolean; choose: () => void }) {
  return <article id={`candidate-${candidate.id}`} tabIndex={-1} className={`space-y-3 rounded-lg border p-4 focus:ring-2 focus:ring-blue-500 ${selected ? "border-green-700 bg-green-50" : "border-ui-border"}`} aria-label={`Kandidat peta ${candidate.rank}`}><h3 className="text-sm font-semibold">Kandidat {candidate.rank} · {displayValue(candidate.fields.idpel)}</h3><p className="text-sm">{displayValue(candidate.fields.nama)} · <strong>{candidate.distance_meters.toFixed(2)} m</strong></p><p className="font-mono text-xs text-ui-muted">{displayValue(candidate.fields.lat)}, {displayValue(candidate.fields.lon)}</p><details><summary className="text-xs font-medium">Detail kandidat</summary><Fields fields={candidate.fields} /></details><CandidateCoordinateSource fields={candidate.fields} /><details><summary className="cursor-pointer text-xs font-semibold">Sumber kandidat ({candidate.observations.length})</summary>{candidate.observations.map((source, index) => <div key={index} className="mt-3 border p-3 text-xs"><p className="font-semibold">{source.dataset_type} · {source.filename} · Baris {source.row_number}</p><p>{source.source_sheet}</p><Fields fields={source.fields} /></div>)}</details><button type="button" disabled={disabled || selected} onClick={choose} className={selected ? buttonClass.success : buttonClass.primary}>{selected ? "Kandidat terpilih" : `Pilih kandidat ${candidate.rank}`}</button></article>;
}
