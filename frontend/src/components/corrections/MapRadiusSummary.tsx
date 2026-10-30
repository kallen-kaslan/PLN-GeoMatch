import { LoaderCircle } from "lucide-react";
import type { MapRadiusSummary as RadiusSummary } from "@/lib/corrections";

export function MapRadiusSummary({ data, loading, failed, onRetry }: {
  data: RadiusSummary | undefined; loading: boolean; failed: boolean; onRetry: () => void;
}) {
  return <section aria-label="Ringkasan radius peta" aria-busy={loading} className="space-y-3 rounded-sm border-2 border-neo-border bg-white p-4 sm:p-5">
    <div className="flex items-center gap-2"><h2 className="text-sm font-black">Ringkasan hasil dalam radius</h2>{loading && <LoaderCircle size={16} className="animate-spin" />}</div>
    {failed ? <p role="alert" className="text-sm text-red-700">Ringkasan radius belum dapat dimuat. <button className="underline" onClick={onRetry}>Coba lagi ringkasan radius</button></p> : !data ? <p role="status" className="text-sm">Memuat hitungan dari hasil koreksi tersimpan…</p> : <>
      <p className="text-xs font-bold">Radius {data.radius_meters.toLocaleString("id-ID")} m · Versi {data.generation} · Seluruh berkas</p>
      {data.partial && <p role="status" className="text-xs text-amber-900">Hasil sementara: {data.saved_rows.toLocaleString("id-ID")} dari {data.total_rows.toLocaleString("id-ID")} baris tersimpan. Baris belum diperiksa tidak dihitung sebagai tanpa kandidat.</p>}
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[["Total baris", data.total_rows], ["Baris tersimpan", data.saved_rows], ["Baris dengan kandidat", data.matched], ["Baris tanpa kandidat", data.no_candidates], ["Belum diperiksa", data.not_checked], ["Benturan PDPJ", data.pdpj_conflicts], ["Data bermasalah", data.invalid_data], ["Koordinat belum lengkap", data.incomplete_coordinates]].map(([label, value]) => <div key={label} className="rounded-sm border border-gray-300 p-3"><dt className="text-[11px] font-bold">{label}</dt><dd className="mt-1 text-xl font-black">{Number(value).toLocaleString("id-ID")}</dd></div>)}
      </dl>
      <p className="text-xs">Jumlah kandidat: {data.candidate_total.toLocaleString("id-ID")}. Satu baris dapat mempunyai lebih dari satu kandidat.</p>
      {(data.baseline.generation !== data.generation || data.baseline.radius_meters !== data.radius_meters) && <p aria-label="Perbandingan hasil radius" className="rounded-sm border border-blue-700 bg-blue-50 p-3 text-xs text-blue-950">Acuan tersimpan versi {data.baseline.generation}, radius {data.baseline.radius_meters} m: {data.baseline.no_candidates.toLocaleString("id-ID")} baris tanpa kandidat dan {data.baseline.matched.toLocaleString("id-ID")} baris dengan kandidat. Pada hasil radius {data.radius_meters} m, {data.newly_matched.toLocaleString("id-ID")} baris yang sebelumnya tanpa kandidat kini mendapat kandidat.{data.partial && " Perbandingan masih sementara sampai seluruh baris selesai diperiksa."}</p>}
    </>}
  </section>;
}
