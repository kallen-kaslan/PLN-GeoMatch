import { MetricCard } from "@/components/data/MetricCard";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, LoaderCircle, RefreshCw, Database, FileCheck2 } from "lucide-react";
import { api } from "@/lib/api";
import { buttonClass } from "@/lib/button";
import { CORRECTION_TYPES } from "@/lib/corrections";

interface ProcessItem {
  id: number; process_name: string; radius_meters: number;
  matching_status: string; review_status: string; total_targets: number;
  matched_targets: number; created_at: string; processing_state?: string;
  category?: string; batch_id?: number; generation?: number; saved_rows?: number;
}
const count = (value: number) => value.toLocaleString("id-ID");
function processLink(process: ProcessItem) {
  const descriptor = CORRECTION_TYPES.find((item) => item.key === process.category);
  if (!descriptor) return `/candidates?process_id=${process.id}`;
  if (process.matching_status !== "completed") return `/koreksi/${descriptor.slug}?batch_id=${process.batch_id}&process_id=${process.id}`;
  return `/peta-koreksi?category=${process.category}&batch_id=${process.batch_id}&process_id=${process.id}`;
}
function status(process: ProcessItem) {
  if (process.processing_state === "paused") return "Dijeda";
  if (process.matching_status === "failed") return "Terhenti";
  if (process.matching_status === "queued") return "Menunggu antrean";
  if (process.matching_status === "running") return "Dalam pemeriksaan";
  return process.review_status === "finalized" ? "Selesai ditinjau" : "Siap ditinjau";
}
export default function DashboardPage() {
  const history = useQuery({ queryKey: ["process-history"], queryFn: async ({ signal }) => (await api.get<ProcessItem[]>("/history/processes", { signal })).data });
  const processes = history.data ?? [];
  const pending = processes.filter((item) => item.review_status !== "finalized");
  const metrics = [
    ["Pemeriksaan tersimpan", processes.length, "primary"],
    ["Belum selesai ditinjau", pending.length, "warning"],
    ["Baris seluruh pemeriksaan", processes.reduce((total, item) => total + (item.total_targets || 0), 0), "violet"],
    ["Baris memiliki kandidat", processes.reduce((total, item) => total + (item.matched_targets || 0), 0), "success"],
  ] as const;
  return <div className="space-y-5">
    <header className="geo-page-heading"><div><h1>Dashboard</h1><p>Pantau pekerjaan dan lanjutkan pemeriksaan yang tersimpan.</p></div><div className="flex flex-wrap gap-2"><Link to="/master/prabayar" className={buttonClass.secondary}><Database size={16} />Data Master</Link><Link to="/pdpj" className={buttonClass.primary}><FileCheck2 size={16} />Buka Data PDPJ</Link></div></header>
    <nav aria-label="Alur rekonsiliasi" className="flex flex-wrap items-center gap-2 text-xs text-ui-muted">{[["/master/prabayar", "Data Master"], ["/pdpj", "Validasi PDPJ"], ["/koreksi/idpel-tidak-ketemu", "Data Koreksi"], ["/result", "Hasil dan Riwayat"]].map(([to, label], index) => <span key={to} className="flex items-center gap-2"><Link to={to} className="rounded px-1 py-1 hover:text-neo-black">{label}</Link>{index < 3 && <ArrowRight size={12} />}</span>)}</nav>
    {history.isError && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">Riwayat belum dapat dimuat. <button type="button" onClick={() => void history.refetch()} className="underline">Coba lagi</button></p>}
    <section aria-label="Ringkasan aktivitas" className="geo-metrics geo-metrics-4">{metrics.map(([label, value, tone]) => <MetricCard key={label} label={label} value={history.isPending || history.isError ? "—" : count(value)} tone={value > 0 || tone === "primary" ? tone : "neutral"} />)}</section>
    <section className="geo-panel overflow-hidden" aria-label="Pekerjaan rekonsiliasi"><header className="flex items-center justify-between gap-3 border-b border-ui-border px-5 py-4"><div><h2 className="text-base font-semibold">Pekerjaan yang memerlukan tindakan</h2><p className="mt-1 text-xs text-ui-muted">Pemeriksaan yang belum selesai ditinjau, dari yang terbaru.</p></div><button type="button" onClick={() => void history.refetch()} disabled={history.isFetching} aria-label="Muat ulang pekerjaan" className={buttonClass.secondary}><RefreshCw size={15} className={history.isFetching ? "animate-spin" : ""} /></button></header>
      {history.isPending ? <p role="status" className="flex items-center gap-2 p-8 text-sm text-ui-muted"><LoaderCircle size={16} className="animate-spin" />Memuat pekerjaan tersimpan…</p> : !pending.length && !history.isError ? <div className="px-5 py-12"><p className="font-medium">Tidak ada pekerjaan yang menunggu tindakan.</p><p className="mt-2 text-sm text-ui-muted">Mulai dengan menyiapkan sumber master dan memeriksa Data PDPJ.</p></div> : <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left"><thead><tr>{["Pemeriksaan", "Status", "Baris tersimpan / target", "Radius", "Tindakan"].map((label) => <th key={label} className="px-5 py-3">{label}</th>)}</tr></thead><tbody>{pending.slice(0, 8).map((process) => <tr key={process.id} className="border-t border-ui-border"><td className="px-5 py-4"><p className="font-medium">{process.process_name}</p><p className="mt-1 text-xs text-ui-muted">Pemeriksaan #{process.id}{process.generation ? ` · Versi ${process.generation}` : ""}</p></td><td className="px-5 py-4"><span className={`rounded-md px-2 py-1 text-xs ${process.matching_status === "failed" ? "bg-red-50 text-red-800" : process.processing_state === "paused" ? "bg-amber-50 text-amber-900" : "bg-blue-50 text-blue-800"}`}>{status(process)}</span></td><td className="px-5 py-4 tabular-nums">{process.saved_rows === undefined ? count(process.total_targets || 0) : `${count(process.saved_rows)} / ${count(process.total_targets || 0)}`}</td><td className="px-5 py-4 tabular-nums">{count(process.radius_meters || 0)} m</td><td className="px-5 py-4"><Link to={processLink(process)} className="inline-flex items-center gap-2 text-[13px] font-medium hover:underline">{process.matching_status === "completed" ? "Tinjau hasil" : "Lanjutkan pemeriksaan"}<ArrowRight size={14} /></Link></td></tr>)}</tbody></table></div>}
      <footer className="flex justify-between border-t border-ui-border px-5 py-3 text-xs text-ui-muted"><span>Jumlah baris mencakup seluruh pemeriksaan, termasuk pemeriksaan ulang.</span><Link to="/history" className="shrink-0 font-medium text-neo-black hover:underline">Lihat riwayat</Link></footer>
    </section>
  </div>;
}
