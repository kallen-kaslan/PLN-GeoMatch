import { MetricCard, type MetricTone } from "@/components/data/MetricCard";
import { LoaderCircle } from "lucide-react";
import type { CorrectionKind } from "@/lib/master";
import type { MapRadiusSummary as RadiusSummary } from "@/lib/corrections";

export function MapRadiusSummary({ kind, data, loading, failed, onRetry, preview = false }: {
  preview?: boolean; kind: CorrectionKind; data: RadiusSummary | undefined; loading: boolean; failed: boolean; onRetry: () => void;
}) {
  const counts = data?.overview_counts;
  const notFound = kind === "idpel_tidak_ketemu";
  const cards: [string, number, MetricTone][] = data ? [
    ["Total Data", data.total_rows, "primary"],
    ["Belum Diproses", counts?.not_processed ?? data.not_checked + data.invalid_data + data.pdpj_conflicts, "neutral"],
    ["Koordinat Bermasalah", counts?.coordinate_issues ?? data.incomplete_coordinates, "warning"],
    ["Tanpa Kandidat", data.no_candidates, "warning"],
    ["Kandidat Ditemukan", data.matched, "success"],
    ...(notFound ? [["IDPEL Sudah Ada di PDPJ", counts?.idpel_in_pdpj ?? 0, "danger"] as [string, number, MetricTone]] : []),
  ] : [];
  return <section aria-label="Ringkasan radius peta" aria-busy={loading} className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ui-muted"><h2 className="font-semibold text-neo-black">Ringkasan Hasil</h2>{loading ? <span role="status" className="flex items-center gap-2"><LoaderCircle size={14} className="animate-spin" />Memperbarui hasil...</span> : data && <span>{preview ? "Pratinjau radius" : "Radius aktif"} {data.radius_meters.toLocaleString("id-ID")} m</span>}</div>
    {failed ? <p role="alert" className="text-sm text-red-700">Ringkasan radius belum dapat dimuat. <button className="underline" onClick={onRetry}>Coba lagi ringkasan radius</button></p> : !data ? <p role="status" className="rounded-lg border border-ui-border bg-white p-4 text-sm">Memuat ringkasan hasil...</p> : <>
      {data.partial && <p role="status" className="text-xs text-amber-900">Hasil sementara: {data.saved_rows.toLocaleString("id-ID")} dari {data.total_rows.toLocaleString("id-ID")} baris tersimpan. Baris belum diperiksa tidak dihitung sebagai tanpa kandidat.</p>}
      <dl className={`grid grid-cols-1 gap-3 sm:grid-cols-2 ${notFound ? "lg:grid-cols-3" : "xl:grid-cols-5"}`}>{cards.map(([label, value, tone]) => <MetricCard key={label} label={label} value={value} definition compact tone={tone === "primary" || value > 0 ? tone : "neutral"} />)}</dl>
      <p className="text-xs text-ui-muted">Jumlah kandidat: {data.candidate_total.toLocaleString("id-ID")}. Satu data dapat memiliki lebih dari satu kandidat.</p>
    </>}
  </section>;
}
