import type { CorrectionProcessing } from "@/lib/corrections";

export function AutomaticExtensionNote({ extension }: { extension?: CorrectionProcessing["automatic_extension"] }) {
  if (!extension) return null;
  return <p role="status" className="rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-950">Perluasan hingga {extension.search_radius_meters.toLocaleString("id-ID")} m untuk {extension.target_count.toLocaleString("id-ID")} target. Kandidat lama dan pilihan tersimpan tetap tersedia. Identitas pilihan otomatis belum diverifikasi.</p>;
}
