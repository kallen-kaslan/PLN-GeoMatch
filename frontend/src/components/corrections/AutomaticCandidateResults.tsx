import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDebouncedSearch } from "@/hooks/useDebouncedSearch";
import { MetricCard } from "@/components/data/MetricCard";
import { PreviewPagination } from "@/components/data/PreviewPagination";
import { SearchFeedback } from "@/components/data/SearchFeedback";
import { CorrectionDetail } from "@/components/corrections/CorrectionDetail";
import { buttonClass } from "@/lib/button";
import { correctionApi, identityLabel, searchLabel, type CorrectionFilter, type CorrectionRun } from "@/lib/corrections";
import { displayValue, type CorrectionKind } from "@/lib/master";
import { searchPreparing, searchRefreshInterval } from "@/lib/search";

const control = "min-w-0 rounded-lg border border-ui-border bg-white px-3 py-2 text-sm";
const count = (value: number | undefined) => value === undefined ? "—" : value.toLocaleString("id-ID");

export function AutomaticCandidateResults({ kind, label, batchId, processId, run, radius }: {
  kind: CorrectionKind; label: string; batchId: number; processId: number; run: CorrectionRun; radius: string;
}) {
  const [search, setSearch] = useState("");
  const q = useDebouncedSearch(search);
  const settledRadius = useDebouncedSearch(radius);
  const [status, setStatus] = useState<CorrectionFilter>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [recordId, setRecordId] = useState<number | null>(null);
  const radiusMeters = Number(radius);
  const valid = Number.isFinite(radiusMeters) && radiusMeters > 0 && radiusMeters <= run.radius_meters;
  const settled = radius === settledRadius;
  const scope = { batch_id: batchId, process_id: processId, generation: run.generation, radius_meters: radiusMeters };
  const summary = useQuery({ queryKey: ["corrections", kind, "summary", batchId, processId, run.generation, radiusMeters],
    queryFn: () => correctionApi.summary(kind, scope), enabled: valid && settled });
  const records = useQuery({ queryKey: ["corrections", kind, "rows", batchId, processId, run.generation, radiusMeters, q, status, page, pageSize],
    queryFn: ({ signal }) => correctionApi.rows(kind, { ...scope, q, status, skip: (page - 1) * pageSize, limit: pageSize }, signal),
    enabled: valid && settled && search === q, refetchInterval: searchRefreshInterval });
  const busy = !settled || search !== q || searchPreparing(records.data);
  const data = valid && settled ? summary.data : undefined;
  return <>
    <p className="text-xs text-ui-muted">Kandidat ditemukan menghitung target yang memiliki setidaknya satu kandidat dalam radius. Kandidat yang sama dapat muncul pada beberapa target; angka ini tidak menunjukkan jumlah pasangan IDPEL unik yang sudah dipilih.</p>
    <section aria-label={`Ringkasan ${label}`} className="geo-metrics geo-metrics-4">{[
      ["Total baris", data?.total_rows], ["Kandidat ditemukan", data?.matched],
      ["Tanpa kandidat dalam radius", data?.no_candidates], ["Benturan dengan PDPJ", data?.pdpj_conflicts],
    ].map(([title, value]) => <MetricCard key={String(title)} label={String(title)} value={count(typeof value === "number" ? value : undefined)} tone="neutral" compact />)}</section>
    <section aria-label="Kandidat untuk pemilihan otomatis" className="space-y-4 rounded-lg border border-ui-border bg-white p-4 sm:p-5">
      <div><h2 className="text-sm font-semibold">Kandidat tersimpan · {label}</h2><p className="mt-1 text-xs text-ui-muted">Tabel, detail, dan pratinjau mengikuti radius {valid ? count(radiusMeters) : "—"} m dari hasil versi {run.generation}, dengan radius pemeriksaan tersimpan {count(run.radius_meters)} m. Pencarian tabel tidak membatasi cakupan pemilihan otomatis.</p></div>
      <div className="flex flex-col gap-3 sm:flex-row"><input aria-label="Cari data koreksi" type="search" value={search} maxLength={120} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Cari IDPEL, nama, atau referensi..." className={`${control} flex-1`} /><select aria-label="Filter hasil koreksi" value={status} onChange={(event) => { setStatus(event.target.value as CorrectionFilter); setPage(1); }} className={control}><option value="all">Semua kondisi</option>{Object.entries(searchLabel).map(([key, title]) => <option key={key} value={key}>{title}</option>)}<option value="identity_found">IDPEL ditemukan di master</option><option value="identity_not_found">IDPEL tidak ditemukan di master</option></select></div>
      {summary.isError && <p role="alert" className="text-sm text-red-700">Ringkasan belum dapat dimuat. <button type="button" className="underline" onClick={() => void summary.refetch()}>Coba lagi</button></p>}
      <div className="overflow-x-auto rounded-lg border border-ui-border"><table className="w-full min-w-[1000px] text-left text-[13px]"><thead className="bg-ui-table-head"><tr>{["Baris", "IDPEL / Nama", "Referensi", "Koordinat", "Keberadaan IDPEL", "Hasil pemeriksaan", "Kandidat", "Detail"].map((title) => <th key={title} className="p-3">{title}</th>)}</tr></thead><tbody>
        {!valid ? <tr><td colSpan={8} className="p-8 text-center">Masukkan radius pilihan otomatis yang valid untuk memuat kandidat.</td></tr>
          : busy || records.isPending ? <tr><td colSpan={8} className="p-8 text-center">Memuat kandidat sesuai radius...</td></tr>
          : records.isError ? <tr><td colSpan={8} className="p-8 text-center text-red-700">Kandidat belum dapat dimuat. <button type="button" className="underline" onClick={() => void records.refetch()}>Coba lagi</button></td></tr>
          : records.data.items.length ? records.data.items.map((row) => <tr key={row.id} className="border-t border-gray-200 hover:bg-neo-white"><td className="p-3 font-mono">{row.row_number}</td><td className="p-3"><p className="font-mono font-semibold">{displayValue(row.fields.idpel)}</p><p className="mt-1 max-w-48 truncate">{displayValue(row.fields.nama)}</p></td><td className="p-3 font-mono">{displayValue(row.fields.meter_ref || row.fields.agenda_ref || row.fields.survey_ref || row.fields.target_ref)}</td><td className="p-3 font-mono">{displayValue(row.fields.lat)}, {displayValue(row.fields.lon)}</td><td className="p-3">{identityLabel[row.identity_status]}</td><td className="p-3 font-semibold">{searchLabel[row.search_status]}</td><td className="p-3">{row.candidate_count}</td><td className="p-3"><button type="button" aria-label={`Detail koreksi baris ${row.row_number}`} onClick={() => setRecordId(row.id)} className={buttonClass.secondary}>Detail</button></td></tr>)
          : <tr><td colSpan={8} className="p-8 text-center">Belum ada data sesuai filter.</td></tr>}
      </tbody></table></div>
      <SearchFeedback state={records.data?.search_index} waiting={search !== q} fetching={Boolean(search) && records.isFetching} />
      <PreviewPagination context="koreksi" page={page} pageSize={pageSize} total={valid && !busy ? records.data?.total : undefined} loading={records.isFetching || busy || !valid} onPageChange={setPage} onPageSizeChange={setPageSize} />
    </section>
    {recordId !== null && valid && settled && <CorrectionDetail key={`detail-${recordId}-${radiusMeters}`} kind={kind} recordId={recordId} scope={scope} onClose={() => setRecordId(null)} />}
  </>;
}
