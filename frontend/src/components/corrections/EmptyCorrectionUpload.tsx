import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { EmptyCorrectionFileStep } from "./EmptyCorrectionFileStep";
import { buttonClass } from "@/lib/button";
import { CorrectionFlowLayout } from "./CorrectionFlowLayout";
import { EmptyRadiusWorkflow } from "./EmptyRadiusWorkflow";
import { correctionApi, CORRECTION_TYPES } from "@/lib/corrections";
import type { CorrectionKind, ImportResult } from "@/lib/master";


export function EmptyCorrectionUpload({ kind = "idpel_kosong" }: { kind?: CorrectionKind }) {
  return <SavedEmptyCorrectionUpload key={kind} kind={kind} />;
}

function SavedEmptyCorrectionUpload({ kind }: { kind: CorrectionKind }) {
  const root = `/koreksi/${CORRECTION_TYPES.find((item) => item.key === kind)!.slug}`;
  const [params, setParams] = useSearchParams();
  const client = useQueryClient();
  const navigate = useNavigate();
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const parsed = Number(params.get("batch_id"));
  const batchId = Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  const [createdHere, setCreatedHere] = useState<number | null>(null);
  const [completed, setCompleted] = useState<{ result: ImportResult; filename: string } | null>(null);
  const batch = useQuery({ queryKey: ["corrections", kind, "upload", batchId], queryFn: () => correctionApi.batch(kind, batchId!), enabled: batchId !== null, staleTime: 0 });
  const saved = completed?.result.batch_id === batchId ? completed : null;
  const confirmed = !!saved || batch.data?.status === "completed";
  const stage = confirmed && params.get("workflow_step") !== "1" ? 2 : 1;
  const recovering = batchId !== null && createdHere !== batchId;

  const rememberBatch = (id: number) => {
    void client.invalidateQueries({ queryKey: ["corrections", kind, "batches"] });
    void client.invalidateQueries({ queryKey: ["corrections", kind, "pending"] });
    if (!mounted.current) return;
    setCreatedHere(id);
    setParams({ flow: "upload", batch_id: String(id) }, { replace: true });
  };
  const onSaved = (result: ImportResult, filename: string) => {
    void client.invalidateQueries({ queryKey: ["corrections", kind] });
    if (!mounted.current) return;
    setCompleted({ result, filename });
    setParams({ flow: "upload", batch_id: String(result.batch_id), workflow_step: "2", ...(batchId === result.batch_id && params.get("analysis_id") ? { analysis_id: params.get("analysis_id")! } : {}) }, { replace: true });
  };

  if (stage === 2 && batchId !== null) return <EmptyRadiusWorkflow kind={kind} key={`${kind}-${batchId}`} batchId={batchId} document={{ filename: saved?.filename ?? batch.data?.filename, sheet: batch.data?.source_sheet, totalRows: saved?.result.rows ?? batch.data?.total_rows }} />;
  return <div className="w-full pb-6"><CorrectionFlowLayout kind={kind} stage={1} steps={["Unggah data", "Cari kandidat"]} onStep={confirmed ? (step) => { if (step === 2 && batchId) { const next = new URLSearchParams(params); next.set("workflow_step", "2"); setParams(next); } } : undefined} document={{ filename: batch.data?.filename, sheet: batch.data?.source_sheet }}>
    {recovering && batch.isPending ? <p role="status" className="text-sm">Memulihkan unggahan tersimpan...</p> : recovering && batch.isError ? <section className="space-y-3 rounded-sm border border-gray-200 bg-white p-5"><p role="alert" className="text-sm">Unggahan belum dapat dibuka. Data tidak dihapus.</p><button type="button" className={buttonClass.secondary} onClick={() => void batch.refetch()}>Coba lagi</button></section> : <EmptyCorrectionFileStep kind={kind} saved={recovering ? batch.data : undefined} onBatchCreated={rememberBatch} onSaved={onSaved} onCancel={() => navigate(root)} />}
  </CorrectionFlowLayout></div>;
}
