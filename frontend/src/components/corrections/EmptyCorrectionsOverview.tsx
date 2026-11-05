import { useDeferredValue, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw } from "lucide-react";
import { buttonClass } from "@/lib/button";
import { correctionApi, CORRECTION_TYPES, emptyStatusLabel, correctionOverviewStatusLabel, type OverviewStatus } from "@/lib/corrections";
import { displayValue, type CorrectionKind } from "@/lib/master";
import { PreviewPagination } from "@/components/data/PreviewPagination";
import { EmptyPendingWork } from "./EmptyPendingWork";

const overviewCardTitles: Record<OverviewStatus, string> = {
  not_processed: "Belum Diproses",
  coordinate_issues: "Koordinat Bermasalah",
  no_candidates: "Tanpa Kandidat",
  candidates_found: "Kandidat Ditemukan",
  idpel_in_pdpj: "IDPEL Sudah Ada di PDPJ",
};

const control = "min-w-0 rounded-lg border border-ui-border bg-white px-3 py-2 text-sm";

export function EmptyCorrectionsOverview({ kind = "idpel_kosong" }: { kind?: CorrectionKind }) {
  const notFound = kind === "idpel_tidak_ketemu";
  const descriptor = CORRECTION_TYPES.find((item) => item.key === kind)!;
  const labels = notFound ? correctionOverviewStatusLabel : emptyStatusLabel;
  const columnCount = notFound ? 10 : 9;
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [status, setStatus] = useState<OverviewStatus | "all">("all");
  const [source, setSource] = useState("all");
  const sources = useQuery({ queryKey: ["corrections", kind, "overview", "sources"], queryFn: ({ signal }) => correctionApi.overviewSources(kind, signal), refetchInterval: 5000 });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const summary = useQuery({ queryKey: ["corrections", kind, "overview", "summary"], queryFn: ({ signal }) => correctionApi.overviewSummary(kind, signal), staleTime: 0, refetchInterval: 5000 });
  const empty = summary.isSuccess && summary.data.total_rows === 0;
  const rows = useQuery({ queryKey: ["corrections", kind, "overview", "rows", deferredSearch, status, source, page, pageSize], queryFn: ({ signal }) => correctionApi.overviewRows(kind, { q: deferredSearch, status, source: source === "all" || source === "manual" ? source : "document", batch_id: source.startsWith("batch:") ? Number(source.slice(6)) : undefined, skip: (page - 1) * pageSize, limit: pageSize }, signal), staleTime: 0, refetchInterval: 5000 });
  const filter = (next: OverviewStatus | "all") => { setStatus(next); setPage(1); };
  const cards: { key: OverviewStatus | "all"; label: string; value: number | undefined }[] = [
    { key: "all", label: "Total Data", value: empty ? 0 : summary.data?.total_rows },
    ...Object.keys(labels).map((key) => ({ key: key as OverviewStatus, label: overviewCardTitles[key as OverviewStatus], value: empty ? 0 : summary.data ? summary.data.counts[key as OverviewStatus] ?? 0 : undefined })),
  ];
  return <div className="space-y-5 sm:space-y-6">
    <section aria-label={`Ringkasan ${descriptor.label}`} className={`grid grid-cols-1 gap-3 sm:grid-cols-2 ${notFound ? "lg:grid-cols-3" : "xl:grid-cols-5"}`}>{cards.map((card) => <div key={card.key} className={`min-w-0 rounded-lg border border-ui-border bg-white p-4 shadow-sm ${!notFound && card.key === "all" ? "sm:col-span-2 xl:col-span-1" : ""}`}><span className="block text-xs font-semibold">{card.label}</span><span className="mt-2 block text-2xl font-semibold">{card.value === undefined ? "—" : card.value.toLocaleString("id-ID")}</span></div>)}</section>
    {summary.isError && <p role="alert" className="text-sm text-red-700">Ringkasan belum dapat dimuat. <button type="button" className="font-semibold underline" onClick={() => void summary.refetch()}>Coba lagi</button></p>}
    <EmptyPendingWork enabled kind={kind} />
    <section className="space-y-4 rounded-lg border border-ui-border bg-white p-4 sm:p-5">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-ui-border pb-4">
        <h1 className="text-base font-semibold">Daftar Data</h1>
        <div className="flex items-center gap-2">
          <button type="button" aria-label={`Muat ulang ${descriptor.label}`} className={buttonClass.secondary} onClick={() => { void client.invalidateQueries({ queryKey: ["corrections", kind] }); }}><RefreshCw size={16} /></button>
          <Link to="?flow=upload" className={buttonClass.primary}><Plus size={16} />Unggah data</Link>
        </div>
      </header>
      <div className="flex flex-col gap-3 lg:flex-row"><input type="search" maxLength={120} aria-label={`Cari ${descriptor.label}`} placeholder={notFound ? "Cari IDPEL, agenda, nama, atau nomor meter..." : "Cari agenda, nama, atau nomor meter..."} value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} className={`${control} flex-1`} /><select aria-label={`Filter sumber ${descriptor.label}`} value={source} onChange={(event) => { setSource(event.target.value); setPage(1); }} className={`${control} lg:max-w-sm`}><option value="all">Semua Sumber</option><option value="manual">Input Manual</option><optgroup label="Berkas Unggahan">{sources.data?.map((item) => <option key={item.id} value={`batch:${item.id}`}>{item.filename}{item.source_sheet ? ` \u00b7 Sheet ${item.source_sheet}` : ""} (#{item.id})</option>)}</optgroup></select><select aria-label={`Filter status ${descriptor.label}`} value={status} onChange={(event) => filter(event.target.value as OverviewStatus | "all")} className={control}><option value="all">Semua status</option>{Object.entries(labels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>
      {sources.isError && <p role="alert" className="text-sm text-red-700">Daftar sumber belum dapat dimuat. <button type="button" className="underline" onClick={() => void sources.refetch()}>Coba lagi</button></p>}
      <div className="overflow-x-auto"><table className={`w-full text-left text-xs ${notFound ? "min-w-[1050px]" : "min-w-[950px]"}`}><thead className="bg-gray-100"><tr>{["No", "Objek ID", "Nomor agenda", ...(notFound ? ["IDPEL"] : []), "Nama pelanggan", "Koordinat X", "Koordinat Y", "Status", "Kandidat", "Aksi"].map((label) => <th key={label} className="p-3">{label}</th>)}</tr></thead><tbody>
        {empty ? <tr><td colSpan={columnCount} className="p-8 text-center">Belum ada data. Klik Unggah data untuk memulai.</td></tr> : rows.isError ? <tr><td colSpan={columnCount} className="p-8 text-center">Data belum dapat dimuat.</td></tr> : rows.isPending ? <tr><td colSpan={columnCount} className="p-8 text-center">Memuat data…</td></tr> : !rows.data?.items.length ? <tr><td colSpan={columnCount} className="p-8 text-center">{search || status !== "all" || source !== "all" ? "Tidak ada data sesuai pencarian atau filter." : "Belum ada data. Klik Unggah data untuk memulai."}</td></tr> : rows.data.items.map((row, index) => <tr key={row.id} className="border-t border-gray-200">
          <td className="p-3 tabular-nums">{(page - 1) * pageSize + index + 1}</td><td className="p-3 font-mono">{displayValue(row.object_id)}</td><td className="p-3 font-mono">{displayValue(row.fields.agenda_ref)}</td>{notFound && <td className="p-3 font-mono">{displayValue(row.fields.idpel)}</td>}<td className="p-3">{displayValue(row.fields.nama)}</td><td className="p-3 font-mono">{displayValue(row.fields.lon)}</td><td className="p-3 font-mono">{displayValue(row.fields.lat)}</td><td className="p-3 font-semibold">{correctionOverviewStatusLabel[row.status]}</td><td className="p-3">{row.candidate_count}</td><td className="p-3"><div className="flex gap-2"><Link className={buttonClass.secondary} to={`?detail_record_id=${row.id}&batch_id=${row.batch_id}${row.process_id ? `&process_id=${row.process_id}` : ""}${row.generation ? `&generation=${row.generation}` : ""}${notFound && row.analysis_id ? `&analysis_id=${row.analysis_id}` : ""}`}>Detail</Link></div></td>
        </tr>)}
      </tbody></table></div>
      <PreviewPagination context="koreksi" page={page} pageSize={pageSize} total={empty ? 0 : rows.data?.total} loading={rows.isFetching} onPageChange={(next) => { setPage(next); }} onPageSizeChange={(size) => { setPageSize(size); setPage(1); }} />
    </section>

  </div>;
}
