import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { buttonClass } from "@/lib/button";
import { correctionApi, type EmptyPendingProcess } from "@/lib/corrections";

function resumeLink(item: EmptyPendingProcess) {
  return item.process_id && !item.analysis_id
    ? `?workspace=1&batch_id=${item.batch_id}&process_id=${item.process_id}`
    : `?flow=upload&batch_id=${item.batch_id}${item.analysis_id ? `&analysis_id=${item.analysis_id}` : ""}`;
}

const stageLabel: Record<string, string> = {
  upload: "Simpan data unggahan", analysis: "Analisis jarak", search: "Pencarian kandidat",
  radius: "Tentukan radius dan mulai pencarian", analyzing: "Analisis jarak",
  preparing: "Persiapan master", matching: "Pencarian kandidat",
  validating: "Pemeriksaan hasil tersimpan", publishing: "Penyelesaian pemeriksaan",
};
const stateLabel: Record<string, string> = {
  running: "Belum selesai", paused: "Dijeda", failed: "Proses terhenti",
  queued: "Menunggu pemrosesan", waiting: "Menunggu langkah berikutnya",
  ready: "Analisis selesai",
};

export function EmptyPendingWork({ enabled }: { enabled: boolean }) {
  const work = useQuery({ queryKey: ["corrections", "idpel_kosong", "pending"], queryFn: ({ signal }) => correctionApi.emptyPending(signal), enabled, staleTime: 0, refetchInterval: 5000 });
  if (!enabled) return null;
  if (work.isError) return <p className="text-sm">Daftar proses tertunda belum dapat dimuat. <button type="button" className="font-semibold underline" onClick={() => void work.refetch()}>Coba lagi</button></p>;
  if (!work.data?.length) return null;
  return <section aria-label="Proses IDPEL Kosong belum selesai" className="space-y-3">
    <h2 className="text-base font-semibold">Proses belum selesai</h2>
    <div className="grid gap-3">{work.data.map((item) => <article key={item.batch_id} className="grid min-w-0 items-center gap-3 rounded-lg border border-ui-border bg-white px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:gap-5">
      <div className="min-w-0 space-y-1"><h3 className="text-sm font-semibold [overflow-wrap:anywhere]">{item.filename}</h3>{item.source_sheet && <p className="mt-1 text-xs text-ui-muted [overflow-wrap:anywhere]">Sheet: {item.source_sheet}</p>}
        <div className="space-y-1 pt-1">
        <p className="text-sm">Tahap: <strong>{stageLabel[item.processing_stage ?? item.stage] ?? stageLabel[item.stage]}</strong></p>
        {item.stage === "search" ? <p className="text-xs leading-relaxed text-ui-muted">Hasil tersimpan: {item.processed_rows.toLocaleString("id-ID")} dari {item.total_rows.toLocaleString("id-ID")} baris. Belum diproses: {Math.max(0, item.total_rows - item.processed_rows).toLocaleString("id-ID")} baris.</p> : <p className="text-xs leading-relaxed text-ui-muted">{item.total_rows.toLocaleString("id-ID")} baris {item.stage === "upload" ? "menunggu penyimpanan dan validasi" : item.stage === "radius" ? "sudah dianalisis; siap menentukan radius" : `sudah disimpan; ${item.processed_rows.toLocaleString("id-ID")} baris telah dianalisis`}.</p>}
        </div>
      </div>
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 border-t border-ui-border pt-3 sm:flex-col sm:items-end sm:justify-center sm:border-t-0 sm:pt-0">
        <span className="rounded-md bg-ui-context px-2 py-1 text-xs font-medium text-ui-primary-text">{stateLabel[item.state] ?? "Belum selesai"}</span>
        <Link to={resumeLink(item)} className={buttonClass.secondary}>{item.stage === "search" && item.state === "running" ? "Lihat progres" : "Lanjutkan proses"}</Link>
      </div>
    </article>)}</div>
  </section>;
}
