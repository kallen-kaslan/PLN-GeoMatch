import { Link } from "react-router-dom";
import { MetricCard } from "@/components/data/MetricCard";
import type { SavedChoiceCounts } from "@/lib/corrections";

export function SavedChoicesSummary({ data, resultUrl }: { data?: SavedChoiceCounts; resultUrl?: string }) {
  if (!data) return null;
  const radius = data.radius_meters.toLocaleString("id-ID");
  return <section aria-label="Pilihan tersimpan menurut radius" className="space-y-2">
    <div className="geo-metrics md:grid-cols-3">
      <MetricCard label="Total pilihan aktif (semua radius)" value={data.active_count} compact tone="neutral" />
      <MetricCard label="Pilihan aktif dalam radius" value={data.within_radius_count} compact tone="success" />
      <MetricCard label="Pilihan aktif di luar radius" value={data.outside_radius_count} compact tone={data.outside_radius_count ? "warning" : "neutral"} />
    </div>
    <div className="geo-metadata"><span>Filter {radius} m · Seluruh berkas</span><span>Jarak pilihan terjauh (semua radius): <strong>{data.max_distance_meters === null ? "—" : `${data.max_distance_meters.toLocaleString("id-ID", { maximumFractionDigits: 2 })} m`}</strong></span><span>Pilihan lama tetap tersimpan saat radius berubah.</span></div>
    {data.outside_radius_count > 0 && <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
      {data.outside_radius_count.toLocaleString("id-ID")} pilihan aktif berada di luar radius {radius} m dan tetap tersimpan. Pilihan tersebut tidak dimasukkan dalam tabel hasil atau ekspor dengan filter {radius} m.
      {resultUrl && <> <Link to={resultUrl} className="font-semibold underline">Lihat hasil dalam radius</Link>.</>}
    </p>}
    {data.unknown_distance_count > 0 && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">{data.unknown_distance_count.toLocaleString("id-ID")} pilihan aktif belum memiliki jarak yang valid dan tidak dimasukkan dalam hasil berfilter radius.</p>}
  </section>;
}
