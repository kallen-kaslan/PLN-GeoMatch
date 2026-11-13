import { MetricCard } from "@/components/data/MetricCard";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, LoaderCircle, RefreshCw, Database, FileCheck2 } from "lucide-react";
import { api } from "@/lib/api";
import { buttonClass } from "@/lib/button";
import { CORRECTION_TYPES } from "@/lib/corrections";
import { PlnLogo } from "@/components/auth/PlnLogo";
import { useAppStore } from "@/store/app";

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
  const user = useAppStore((store) => store.user);
  const history = useQuery({ queryKey: ["process-history"], queryFn: async ({ signal }) => (await api.get<ProcessItem[]>("/history/processes", { signal })).data });
  const processes = history.data ?? [];
  const pending = processes.filter((item) => item.review_status !== "finalized");
  const completed = processes.length - pending.length;
  const ready = !history.isPending && !history.isError;
  const groups = [
    { label: "Dalam proses", color: "#4256be", count: pending.filter((item) => ["queued", "running"].includes(item.matching_status) && item.processing_state !== "paused").length },
    { label: "Siap ditinjau", color: "#0c8b91", count: pending.filter((item) => item.matching_status === "completed").length },
    { label: "Dijeda", color: "#b78027", count: pending.filter((item) => item.processing_state === "paused" && item.matching_status !== "completed").length },
    { label: "Terhenti", color: "#bf536a", count: pending.filter((item) => item.matching_status === "failed" && item.processing_state !== "paused").length },
    { label: "Selesai ditinjau", color: "#228468", count: completed },
  ];
  const metrics = [
    ["Pemeriksaan tersimpan", processes.length, "primary"],
    ["Belum selesai ditinjau", pending.length, "warning"],
    ["Baris seluruh pemeriksaan", processes.reduce((total, item) => total + (item.total_targets || 0), 0), "violet"],
    ["Baris memiliki kandidat", processes.reduce((total, item) => total + (item.matched_targets || 0), 0), "success"],
  ] as const;
  return <div className="geo-dashboard space-y-5">
    <header className="geo-dashboard-hero">
      <div className="relative z-10 flex min-w-0 items-start gap-5"><div className="geo-dashboard-logo"><PlnLogo /></div><div className="min-w-0"><p className="geo-dashboard-eyebrow">PLN GeoMatch · Ruang kerja operasional</p><h1>Dashboard</h1><p className="mt-2 max-w-xl text-sm leading-6 text-white/80">Selamat datang, {user?.username ?? "Pengguna"}. Pantau pemeriksaan dan lanjutkan pekerjaan Anda.</p><div className="mt-4 flex flex-wrap gap-2">{ready && pending[0] ? <Link to={processLink(pending[0])} className="geo-hero-action">Lanjutkan pekerjaan<ArrowRight size={16} /></Link> : <Link to="/pdpj" className="geo-hero-action">Buka Data PDPJ<ArrowRight size={16} /></Link>}<Link to="/history" className="geo-hero-link">Lihat riwayat</Link></div></div></div>
      <div className="geo-dashboard-hero-status"><span className="text-xs text-white/75">Peninjauan selesai</span><p className="mt-1 text-3xl font-semibold tabular-nums">{ready ? count(completed) : "—"}<span className="ml-2 text-sm font-normal text-white/65">/ {ready ? count(processes.length) : "—"}</span></p><span className="text-xs text-white/70">pemeriksaan tersimpan</span><progress aria-label="Pemeriksaan selesai ditinjau" value={completed} max={Math.max(1, processes.length)} className="mt-3 h-1.5 w-full" /></div>
    </header>
    <nav aria-label="Alur rekonsiliasi" className="flex flex-wrap items-center gap-2 text-xs text-ui-muted">{[["/master/prabayar", "Data Master"], ["/pdpj", "Validasi PDPJ"], ["/koreksi/idpel-tidak-ketemu", "Data Koreksi"], ["/result", "Hasil dan Riwayat"]].map(([to, label], index) => <span key={to} className="flex items-center gap-2"><Link to={to} className="rounded px-1 py-1 hover:text-neo-black">{label}</Link>{index < 3 && <ArrowRight size={12} />}</span>)}</nav>
    {history.isError && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">Riwayat belum dapat dimuat. <button type="button" onClick={() => void history.refetch()} className="underline">Coba lagi</button></p>}
    <section aria-label="Ringkasan aktivitas" className="geo-metrics geo-metrics-4">{metrics.map(([label, value, tone]) => <MetricCard key={label} label={label} value={history.isPending || history.isError ? "—" : count(value)} tone={value > 0 || tone === "primary" ? tone : "neutral"} />)}</section>
    <p className="text-xs text-ui-muted">Jumlah baris mencakup seluruh pemeriksaan, termasuk pemeriksaan ulang. Memiliki kandidat belum berarti pilihan sudah disimpan.</p>
    <div className="grid min-w-0 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_260px]">
    <section className="geo-panel min-w-0 overflow-hidden" aria-label="Pekerjaan rekonsiliasi"><header className="flex items-center justify-between gap-3 border-b border-ui-border px-5 py-4"><div><h2 className="text-base font-semibold">Pekerjaan yang memerlukan tindakan</h2><p className="mt-1 text-xs text-ui-muted">Pemeriksaan yang belum selesai ditinjau, dari yang terbaru.</p></div><button type="button" onClick={() => void history.refetch()} disabled={history.isFetching} aria-label="Muat ulang pekerjaan" className={buttonClass.secondary}><RefreshCw size={15} className={history.isFetching ? "animate-spin" : ""} /></button></header>
      {history.isPending ? <p role="status" className="flex items-center gap-2 p-8 text-sm text-ui-muted"><LoaderCircle size={16} className="animate-spin" />Memuat pekerjaan tersimpan…</p> : !pending.length && !history.isError ? <div className="px-5 py-12"><p className="font-medium">Tidak ada pekerjaan yang menunggu tindakan.</p><p className="mt-2 text-sm text-ui-muted">Mulai dengan menyiapkan sumber master dan memeriksa Data PDPJ.</p></div> : <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left"><thead><tr>{["Pemeriksaan", "Status", "Baris tersimpan / target", "Radius", "Tindakan"].map((label) => <th key={label} className="px-5 py-3">{label}</th>)}</tr></thead><tbody>{pending.slice(0, 8).map((process) => <tr key={process.id} className="border-t border-ui-border"><td className="px-5 py-4"><p className="font-medium">{process.process_name}</p><p className="mt-1 text-xs text-ui-muted">Pemeriksaan #{process.id}{process.generation ? ` · Versi ${process.generation}` : ""}</p></td><td className="px-5 py-4"><span className={`rounded-md px-2 py-1 text-xs ${process.matching_status === "failed" ? "bg-red-50 text-red-800" : process.processing_state === "paused" ? "bg-amber-50 text-amber-900" : "bg-blue-50 text-blue-800"}`}>{status(process)}</span></td><td className="px-5 py-4 tabular-nums">{process.saved_rows === undefined ? count(process.total_targets || 0) : `${count(process.saved_rows)} / ${count(process.total_targets || 0)}`}</td><td className="px-5 py-4 tabular-nums">{count(process.radius_meters || 0)} m</td><td className="px-5 py-4"><Link to={processLink(process)} className="inline-flex items-center gap-2 text-[13px] font-medium hover:underline">{process.matching_status === "completed" ? "Tinjau hasil" : "Lanjutkan pemeriksaan"}<ArrowRight size={14} /></Link></td></tr>)}</tbody></table></div>}
      <footer className="flex justify-between border-t border-ui-border px-5 py-3 text-xs text-ui-muted"><span>Menampilkan hingga 8 pekerjaan terbaru.</span><Link to="/history" className="shrink-0 font-medium text-neo-black hover:underline">Lihat riwayat</Link></footer>
    </section>
    <aside className="space-y-4" aria-label="Ikhtisar ruang kerja"><section className="geo-panel p-5"><h2 className="text-sm font-semibold">Status pekerjaan</h2><p className="mt-1 text-xs text-ui-muted">Seluruh pemeriksaan tersimpan</p><div className="mt-4 space-y-3">{groups.map((group) => <div key={group.label}><div className="flex items-center justify-between gap-3 text-[13px]"><span className="flex items-center gap-2"><span aria-hidden="true" className="size-2 rounded-full" style={{ background: group.color }} />{group.label}</span><strong className="tabular-nums">{ready ? count(group.count) : "—"}</strong></div><div aria-hidden="true" className="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full" style={{ width: `${ready && processes.length ? group.count / processes.length * 100 : 0}%`, background: group.color }} /></div></div>)}</div></section><section className="geo-panel p-5"><h2 className="mb-3 text-sm font-semibold">Sumber dan validasi</h2><Link to="/master/prabayar" className="geo-dashboard-shortcut"><Database size={17} /><span className="flex-1">Data Master</span><ArrowRight size={14} /></Link><Link to="/pdpj" className="geo-dashboard-shortcut"><FileCheck2 size={17} /><span className="flex-1">Data PDPJ</span><ArrowRight size={14} /></Link></section></aside>
    </div>
  </div>;
}
