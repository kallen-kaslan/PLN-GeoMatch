import type { Fields } from "@/lib/pdpj";
import { displayValue } from "@/lib/master";

export function CandidateCoordinateSource({ fields }: { fields: Fields }) {
  if (!fields.coordinate_source_file) return null;
  const difference = Number(fields.coordinate_max_difference_meters ?? 0);
  return <div className="space-y-2 text-xs">
    <p>Sumber koordinat terpilih: <strong>{displayValue(fields.coordinate_source_file)}</strong> · Sheet {displayValue(fields.coordinate_source_sheet)} · Baris {displayValue(fields.coordinate_source_row)} · Periode {displayValue(fields.coordinate_source_period)}</p>
    {difference > 50 && <p className="rounded-sm border border-amber-700 bg-amber-50 p-3 text-amber-950">Lokasi IDPEL ini berbeda antar sumber hingga {difference.toLocaleString("id-ID", { maximumFractionDigits: 2 })} m dari koordinat terpilih. Periksa sumber dan periodenya sebelum menyetujui kandidat.</p>}
  </div>;
}
