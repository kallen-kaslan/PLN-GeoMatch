import { LoaderCircle } from "lucide-react";
import type { SearchIndexState } from "@/lib/search";

export function SearchFeedback({ state, waiting, fetching }: { state?: SearchIndexState; waiting: boolean; fetching: boolean }) {
  if (!waiting && !fetching && state?.ready !== false) return null;
  return <p role="status" className="flex items-center gap-2 text-xs text-ui-muted">
    <LoaderCircle size={14} className="shrink-0 animate-spin" />
    {state?.ready === false
      ? `Menyiapkan pencarian pada data tersimpan: ${state.processed_rows.toLocaleString("id-ID")} baris sudah disiapkan. Setelah selesai, pencarian berikutnya memakai hasil persiapan ini.`
      : "Memuat hasil pencarian…"}
  </p>;
}
