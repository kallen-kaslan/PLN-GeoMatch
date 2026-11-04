import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAppStore } from "@/store/app";
import { radiusAnalysisApi, validRadius, type EmptyWorkflow } from "@/lib/radius-analysis";
import { CorrectionFlowLayout, type FlowDocument } from "./CorrectionFlowLayout";
import { EmptyCandidatePanel, type ProcessView } from "./EmptyCandidatePreview";

type Command = "analysis-start" | "analysis-pause" | "search-start" | "search-pause";
const errorText = (error: unknown) => (error as { message?: string })?.message ?? "Permintaan belum berhasil. Hasil terakhir tetap tersimpan.";

export function EmptyRadiusWorkflow({ batchId, document }: { batchId: number; document: FlowDocument }) {
  const [params, setParams] = useSearchParams();
  const parsedAnalysis = Number(params.get("analysis_id"));
  const analysisId = Number.isInteger(parsedAnalysis) && parsedAnalysis > 0 ? parsedAnalysis : undefined;
  const navigate = useNavigate();
  const client = useQueryClient();
  const actor = useAppStore((state) => state.user?.username) ?? "Pengguna";
  const [radiusInput, setRadius] = useState<string | null>(null);
  const [debouncedRadius, setDebouncedRadius] = useState("");
  const [command, setCommand] = useState<Command | null>(null);
  const [error, setError] = useState("");
  const gate = useRef(false);
  const mounted = useRef(true);
  const startKey = useRef(crypto.randomUUID());
  const searchKey = useRef(crypto.randomUUID());
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const key = ["corrections", "idpel_kosong", "workflow", batchId, analysisId ?? "latest"];
  const saved = useQuery({
    queryKey: key, queryFn: ({ signal }) => radiusAnalysisApi.workflow(batchId, undefined, signal, analysisId),
    refetchInterval: (query) => command || query.state.data?.activity.active || query.state.data?.analysis.state === "running" || query.state.data?.search?.state === "running" ? 1000 : false,
    refetchIntervalInBackground: true, staleTime: 0,
  });
  const data = saved.data;
  const item = data?.analysis;
  useEffect(() => {
    if (!analysisId && data) {
      client.setQueryData(["corrections", "idpel_kosong", "workflow", batchId, data.analysis.id], data);
      const next = new URLSearchParams(params);
      next.set("analysis_id", String(data.analysis.id));
      setParams(next, { replace: true });
    }
  }, [analysisId, data, client, batchId, params, setParams]);
  const radius = data?.search ? String(data.search.radius_meters) : radiusInput ?? String(item?.selected_radius_meters ?? item?.recommended_radius_meters ?? item?.partial_radius_meters ?? "");
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedRadius(radius), 250);
    return () => window.clearTimeout(timer);
  }, [radius]);
  const coverage = useQuery({
    queryKey: [...key, "coverage", item?.id, debouncedRadius],
    queryFn: ({ signal }) => radiusAnalysisApi.workflow(batchId, Number(debouncedRadius), signal, item?.id),
    enabled: item?.state === "ready" && validRadius(debouncedRadius) && debouncedRadius === radius,
    staleTime: 30000,
  });
  const remember = (next: EmptyWorkflow) => {
    client.setQueryData(key, next);
    void client.invalidateQueries({ queryKey: ["corrections", "idpel_kosong", "pending"] });
    void client.invalidateQueries({ queryKey: ["corrections", "idpel_kosong", "overview"] });
  };
  const perform = async (action: Command) => {
    if (gate.current) return;
    gate.current = true; setCommand(action); setError("");
    try {
      let current = data;
      if (!current && action === "analysis-start") {
        const created = await radiusAnalysisApi.start({ batch_id: batchId, actor, request_key: startKey.current });
        current = await radiusAnalysisApi.workflow(batchId, undefined, undefined, created.id);
      }
      if (!current) throw { message: "Analisis belum tersedia. Mulai analisis terlebih dahulu." };
      const next = action.startsWith("analysis")
        ? await radiusAnalysisApi.analysisJob(current.analysis.id, action === "analysis-pause" ? "paused" : "running")
        : await radiusAnalysisApi.searchJob(current.analysis.id, action === "search-pause" ? { state: "paused" } : { state: "running", ...(current.search ? {} : { radius_meters: Number(radius), request_key: searchKey.current }) });
      remember(next);
    } catch (reason) { if (mounted.current) setError(errorText(reason)); }
    finally {
      gate.current = false;
      if (mounted.current) setCommand(null);
      void client.invalidateQueries({ queryKey: key });
    }
  };
  const toView = (kind: "analysis" | "search"): ProcessView => {
    const isAnalysis = kind === "analysis";
    const value = isAnalysis ? item : data?.search;
    const status = isAnalysis ? item?.state : data?.search?.state;
    const active = data?.activity.active && data.job_kind === kind;
    const pausing = command === `${kind}-pause` || active && data?.activity.operation === "pausing";
    const starting = command === `${kind}-start`;
    const done = isAnalysis ? item?.state === "ready" : data?.search?.status === "completed";
    const state = done ? "finished" : pausing ? "pausing" : starting || active && status === "running" ? "running" : status === "failed" ? "failed" : value ? "paused" : "idle";
    return {
      state, processed: value?.processed_rows ?? 0, total: value?.total_rows ?? document.totalRows ?? 0,
      elapsed: (value?.elapsed_seconds ?? 0) * 1000,
      preparation: isAnalysis && item?.stage === "preparing" ? item.progress.preparation : undefined,
      finalizing: !isAnalysis && !!data?.search && ["validating", "publishing"].includes(data.search.stage),
      actionDisabled: !!command || saved.isPending || saved.isError,
    };
  };
  const back = () => { const next = new URLSearchParams(params); next.set("workflow_step", "1"); setParams(next); };
  const analysisView = toView("analysis");
  const searchView = toView("search");
  const coverageReady = item?.state === "ready" && radius === debouncedRadius && coverage.isSuccess;
  const coverageData = coverageReady ? coverage.data?.analysis : undefined;
  return <div className="mx-auto w-full max-w-5xl pb-6">
    <CorrectionFlowLayout stage={2} steps={["Unggah data", "Cari kandidat"]} onStep={(step) => { if (step === 1) back(); }}>
      {saved.isPending ? <p role="status" className="py-4 text-sm text-gray-500">Memuat progres tersimpan…</p> : saved.isError ? <p role="alert" className="py-4 text-sm text-red-700">Progres belum dapat dimuat. <button type="button" onClick={() => void saved.refetch()} className="font-semibold underline">Coba lagi</button></p> : <EmptyCandidatePanel
        document={document} analysis={analysisView} search={searchView}
        recommendation={item?.recommended_radius_meters ?? item?.partial_radius_meters ?? null}
        recommendationComplete={item?.recommended_radius_meters != null}
        outsideLimit={item?.outside_limit_rows ?? 0} categoryIssues={item?.category_rows ?? 0}
        radius={radius} onRadius={setRadius}
        coverage={coverageData ? { found: coverageData.coverage_rows ?? 0, outside: coverageData.eligible_rows - (coverageData.coverage_rows ?? 0), invalid: coverageData.coordinate_rows } : null}
        coverageLoading={item?.state === "ready" && validRadius(radius) && !coverageReady && !coverage.isError}
        error={error || item?.error || data?.search?.error || (coverage.isError ? "Cakupan radius belum dapat dimuat. Ubah radius atau muat ulang halaman." : "")}
        found={data?.search?.matched_rows ?? 0} noCandidates={data?.search?.no_candidate_rows ?? 0}
        coordinateIssues={data?.search?.coordinate_rows ?? 0} otherIssues={data?.search?.other_issue_rows ?? 0}
        onAnalysisAction={() => void perform(analysisView.state === "running" ? "analysis-pause" : "analysis-start")}
        onSearchAction={() => void perform(searchView.state === "running" ? "search-pause" : "search-start")}
        onBack={back} onResults={() => { void client.invalidateQueries({ queryKey: ["corrections", "idpel_kosong"] }); navigate("/koreksi/idpel-kosong"); }}
      />}
    </CorrectionFlowLayout>
  </div>;
}
