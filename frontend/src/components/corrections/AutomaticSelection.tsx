import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, LoaderCircle, WandSparkles } from "lucide-react";
import { buttonClass } from "@/lib/button";
import type { ApiError } from "@/lib/api";
import { correctionApi, type AutomaticPreview, type CorrectionRun } from "@/lib/corrections";
import type { CorrectionKind } from "@/lib/master";
import { downloadSpreadsheet, resultsApi } from "@/lib/results";
import { useDebouncedSearch } from "@/hooks/useDebouncedSearch";

const reasons: Record<string, string> = {
  equal_distance: "Jarak sama, perlu ditinjau",
  candidates_used: "Seluruh kandidat sudah digunakan atau dicadangkan untuk tinjauan jarak sama",
  outside_radius: "Tanpa kandidat dalam radius pilihan",
  no_candidates: "Tanpa kandidat dalam radius pemeriksaan",
  pdpj_conflict: "Benturan dengan PDPJ",
  invalid_data: "Data perlu diperbaiki",
  incomplete_coordinates: "Koordinat belum lengkap",
};
const count = (value: number) => value.toLocaleString("id-ID");

export function AutomaticSelection({ kind, processId, batchId, run, radius, onRadiusChange, onBusyChange }: {
  kind: CorrectionKind; processId: number; batchId: number; run: CorrectionRun;
  radius: string; onRadiusChange: (value: string) => void;
  onBusyChange?: (value: boolean) => void;
}) {
  const client = useQueryClient();
  const [saved, setSaved] = useState<number | null>(null);
  const [visibleReviews, setVisibleReviews] = useState(10);
  const requestKey = useRef<{ fingerprint: string; key: string } | null>(null);
  const settledRadius = useDebouncedSearch(radius);
  const radiusMeters = Number(radius);
  const validRadius = Number.isFinite(radiusMeters) && radiusMeters > 0 && radiusMeters <= run.radius_meters;
  const settled = radius === settledRadius;
  const inspect = useQuery<AutomaticPreview, ApiError>({
    queryKey: ["automatic-preview", kind, processId, run.id, radiusMeters],
    queryFn: ({ signal }) => correctionApi.automaticPreview(kind, processId, { generation: run.generation, radius_meters: radiusMeters }, signal),
    enabled: validRadius && settled && saved === null,
    retry: false, gcTime: 0, refetchOnWindowFocus: false, refetchOnReconnect: false,
  });
  const filtering = validRadius && (!settled || inspect.isFetching);
  const preview = validRadius && settled && !inspect.isFetching ? inspect.data : undefined;
  const mapUrl = `/peta-koreksi?category=${kind}&batch_id=${batchId}&process_id=${processId}&generation=${run.generation}&radius_meters=${validRadius ? radiusMeters : run.radius_meters}`;
  const resultUrl = `/result?category=${kind}&process_id=${processId}&generation=${run.generation}&radius_meters=${validRadius ? radiusMeters : run.radius_meters}`;
  const download = useMutation<void, ApiError, number>({
    mutationFn: async (exportRadius) => {
      const file = await resultsApi.download(kind, processId, run.generation, exportRadius);
      downloadSpreadsheet(file.blob, file.filename);
    },
  });
  const save = useMutation<{ selected_count: number; already_applied: boolean }, ApiError, AutomaticPreview>({
    mutationFn: (plan) => {
      if (requestKey.current?.fingerprint !== plan.fingerprint) requestKey.current = { fingerprint: plan.fingerprint, key: crypto.randomUUID() };
      return correctionApi.automaticApply(kind, processId, {
        generation: run.generation, radius_meters: plan.radius_meters,
        fingerprint: plan.fingerprint, request_key: requestKey.current.key,
      });
    },
    onSuccess: (data, plan) => {
      setSaved(data.selected_count);
      void client.invalidateQueries({ queryKey: ["corrections", kind] });
      for (const key of ["process-history", "correction-results", "correction-decisions", "correction-choice", "correction-map-choice", "correction-map-candidates"]) {
        void client.invalidateQueries({ queryKey: [key] });
      }
      download.mutate(plan.radius_meters);
    },
  });
  const writing = save.isPending || download.isPending;
  useEffect(() => { onBusyChange?.(writing); return () => onBusyChange?.(false); }, [writing, onBusyChange]);
  const busy = filtering || writing;
  const reset = () => { setSaved(null); setVisibleReviews(10); save.reset(); download.reset(); requestKey.current = null; };
  return <section aria-label="Pilihan kandidat otomatis" className="space-y-4 rounded-lg border border-ui-border bg-white p-4 sm:p-5">
    <div><h2 className="flex items-center gap-2 text-sm font-semibold"><WandSparkles size={18} />Pilih Terdekat &amp; Ekspor</h2>
      <p className="mt-2 text-xs text-ui-muted">Satu IDPEL untuk satu target dalam pemeriksaan ini. Pasangan berjarak terkecil dipilih lebih dahulu; target lain mencoba kandidat berikutnya dalam radius. Pilihan dan pembatalan tersimpan tetap dipertahankan. Jarak sama memerlukan tinjauan melalui peta.</p>
      <p className="mt-1 text-xs text-ui-muted">Menggunakan kandidat dan sumber pada hasil versi {run.generation}. Pratinjau mencakup seluruh berkas, termasuk baris di luar halaman atau pencarian tabel.</p>
    </div>
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1.5 text-xs font-semibold">Radius pilihan otomatis (meter)
        <input aria-label="Radius pilihan otomatis (meter)" type="number" min="0.01" max={run.radius_meters} step="any" value={radius} disabled={writing}
          onChange={(event) => { reset(); onRadiusChange(event.target.value); }} className="w-52 rounded-lg border border-ui-border px-3 py-2 text-sm" />
      </label>
      <button type="button" disabled={busy || !validRadius} onClick={() => { reset(); void inspect.refetch(); }} className={buttonClass.secondary}>
        {filtering && <LoaderCircle size={16} className="animate-spin" />}Pratinjau pilihan otomatis
      </button>
    </div>
    <p className="text-xs text-ui-muted">Radius ini otomatis memfilter ringkasan, kandidat pada tabel dan detail, serta pratinjau pilihan. Radius pemeriksaan tersimpan {count(run.radius_meters)} m.</p>
    {!validRadius && <p role="alert" className="text-sm text-red-700">Radius harus lebih dari 0 dan paling besar {count(run.radius_meters)} meter.</p>}
    {busy && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />{filtering ? `Memuat kandidat dan pratinjau radius ${count(radiusMeters)} m. Data besar dapat memerlukan beberapa saat; pilihan belum diubah.` : save.isPending ? "Memvalidasi dan menyimpan pilihan beserta riwayatnya..." : "Menyiapkan berkas XLSX..."}</p>}
    {validRadius && settled && inspect.error && <p role="alert" className="text-sm text-red-700">{inspect.error.message}</p>}
    {preview && <>
      <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">{[
        ["Akan dipilih otomatis", preview.selected_count], ["Memakai kandidat alternatif", preview.fallback_count],
        ["Keputusan tersimpan dipertahankan", preview.protected_count], ["Belum dipilih / perlu tinjauan", preview.review_count],
      ].map(([label, value]) => <div key={String(label)} className="rounded-lg bg-gray-50 p-3"><dt className="text-xs text-ui-muted">{label}</dt><dd className="mt-1 text-lg font-semibold">{count(Number(value))}</dd></div>)}</dl>
      {Object.entries(preview.review_reasons).length > 0 && <ul className="list-inside list-disc space-y-1 text-xs">{Object.entries(preview.review_reasons).map(([reason, total]) => <li key={reason}>{reasons[reason] ?? reason}: {count(total)} target</li>)}</ul>}
      {preview.review.length > 0 && <details className="rounded-lg border border-ui-border p-3 text-xs"><summary className="cursor-pointer font-semibold">Target yang perlu diperiksa ({count(preview.review_count)})</summary>
        <ul className="mt-3 space-y-2">{preview.review.slice(0, visibleReviews).map((item) => <li key={item.record_id} className="flex flex-wrap justify-between gap-2"><span>Baris {item.row_number}: {reasons[item.reason] ?? item.reason}</span><Link className="font-semibold underline" to={`${mapUrl}&record_id=${item.record_id}&map_view=map`}>Tinjau baris {item.row_number} di peta</Link></li>)}</ul>
        {visibleReviews < preview.review.length && <button type="button" onClick={() => setVisibleReviews((value) => value + 20)} className="mt-3 font-semibold underline">Tampilkan berikutnya</button>}
      </details>}
      {save.error && <p role="alert" className="text-sm text-red-700">{save.error.message}{save.error.status === 409 && " Gunakan Pratinjau pilihan otomatis untuk memperbarui ringkasan."}</p>}
      {saved !== null && <p role="status" className="rounded-lg bg-green-50 p-3 text-sm text-green-800">{count(saved)} pilihan otomatis sudah tersimpan beserta petugas dan riwayat. Pilihan dapat ditinjau melalui Peta Koreksi.</p>}
      {download.error && <p role="alert" className="text-sm text-red-700">Pilihan sudah tersimpan. Berkas belum berhasil diunduh: {download.error.message}. Gunakan Unduh ulang XLSX.</p>}
      <div className="flex flex-wrap items-center gap-3">
        {saved === null ? <button type="button" disabled={busy || save.error?.status === 409} onClick={() => save.mutate(preview)} className={buttonClass.primary}><Download size={16} />Simpan &amp; ekspor XLSX</button>
          : <button type="button" disabled={busy} onClick={() => download.mutate(preview.radius_meters)} className={buttonClass.primary}><Download size={16} />Unduh ulang XLSX</button>}
        <Link to={mapUrl} className="text-xs font-semibold underline">Buka Peta Koreksi</Link>
        {saved !== null && <Link to={resultUrl} className="text-xs font-semibold underline">Lihat hasil tersimpan</Link>}
      </div>
      <p className="text-xs text-ui-muted">XLSX berisi pilihan aktif dalam radius {count(preview.radius_meters)} m, termasuk pilihan tersimpan sebelumnya yang memenuhi radius. Target tanpa pilihan tidak dimasukkan dalam ekspor.</p>
    </>}
  </section>;
}
