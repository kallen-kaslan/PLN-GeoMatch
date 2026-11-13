import type { CorrectionProcessing } from "@/lib/corrections";

export function AutomaticExtensionNote({ extension }: { extension?: CorrectionProcessing["automatic_extension"] }) {
  if (!extension) return null;
  return <p role="status" className="rounded-lg bg-blue-50 p-3 text-xs text-blue-950">Perluasan otomatis hingga {extension.search_radius_meters.toLocaleString("id-ID")} m diterapkan pada {extension.target_count.toLocaleString("id-ID")} target yang tersisa. Versi ini menambahkan kandidat terpilih; kandidat lama dan pilihan sebelumnya tetap tersedia. Pilihan otomatis belum merupakan verifikasi identitas.</p>;
}
