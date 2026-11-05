import { useDeferredValue, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderUp, Plus, RefreshCw } from "lucide-react";
import { buttonClass } from "@/lib/button";
import { correctionApi, CORRECTION_TYPES, emptyStatusLabel, type EmptyStatus } from "@/lib/corrections";
import { displayValue } from "@/lib/master";
import { PreviewPagination } from "@/components/data/PreviewPagination";
import { EmptyPendingWork } from "./EmptyPendingWork";

const control = "min-w-0 rounded-lg border border-ui-border bg-white px-3 py-2 text-sm";
const kind = "idpel_kosong" as const;

export function EmptyCorrectionsOverview() {
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [status, setStatus] = useState<EmptyStatus | "all">("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const summary = useQuery({ queryKey: ["corrections", kind, "overview", "summary"], queryFn: ({ signal }) => correctionApi.emptySummary(signal), staleTime: 0, refetchInterval: 5000 });
  const empty = summary.isSuccess && summary.data.total_rows === 0;
  const rows = useQuery({ queryKey: ["corrections", kind, "overview", "rows", deferredSearch, status, page, pageSize], queryFn: ({ signal }) => correctionApi.emptyRows({ q: deferredSearch, status, skip: (page - 1) * pageSize, limit: pageSize }, signal), staleTime: 0, refetchInterval: 5000 });
  const filter = (next: EmptyStatus | "all") => { setStatus(next); setPage(1); };
  const cards: { key: EmptyStatus | "all"; label: string; value: number | undefined }[] = [
    { key: "all", label: "Total data", value: empty ? 0 : summary.data?.total_rows },
    ...Object.entries(emptyStatusLabel).map(([key, label]) => ({ key: key as EmptyStatus, label, value: empty ? 0 : summary.data ? summary.data.counts[key as EmptyStatus] ?? 0 : undefined })),
  ];
  return <div className="space-y-5 sm:space-y-6">
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-ui-border pb-4">
      <div><h1 className="fluid-h1 flex items-center gap-2 font-semibold"><FolderUp size={26} />IDPEL Kosong</h1><p className="mt-1 text-sm">Seluruh data unggahan dan hasil pencarian kandidat.</p></div>
      <div className="flex gap-2"><button type="button" aria-label="Muat ulang IDPEL Kosong" className={buttonClass.secondary} onClick={() => { void client.invalidateQueries({ queryKey: ["corrections", kind] }); }}><RefreshCw size={16} /></button><Link to="?flow=upload" className={buttonClass.primary}><Plus size={16} />Unggah data</Link></div>
    </header>
    <nav aria-label="Kategori data koreksi" className="flex flex-wrap gap-2">{CORRECTION_TYPES.map((item) => <Link key={item.key} to={`/koreksi/${item.slug}`} aria-current={item.key === kind ? "page" : undefined} className={item.key === kind ? buttonClass.primary : buttonClass.secondary}>{item.label}</Link>)}</nav>
    <section aria-label="Ringkasan IDPEL Kosong" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">{cards.map((card) => <div key={card.key} className={`min-w-0 rounded-lg border border-ui-border bg-white p-4 shadow-sm ${card.key === "all" ? "sm:col-span-2 xl:col-span-1" : ""}`}><span className="block text-xs font-semibold">{card.label}</span><span className="mt-2 block text-2xl font-semibold">{card.value === undefined ? "—" : card.value.toLocaleString("id-ID")}</span></div>)}</section>
    <EmptyPendingWork enabled />
    <section className="space-y-4 rounded-lg border border-ui-border bg-white p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row"><input type="search" aria-label="Cari IDPEL Kosong" placeholder="Cari agenda, nama, atau nomor meter…" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} className={`${control} flex-1`} /><select aria-label="Filter status IDPEL Kosong" value={status} onChange={(event) => filter(event.target.value as EmptyStatus | "all")} className={control}><option value="all">Semua status</option>{Object.entries(emptyStatusLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[950px] text-left text-xs"><thead className="bg-gray-100"><tr>{["No", "Objek ID", "Nomor agenda", "Nama pelanggan", "Koordinat X", "Koordinat Y", "Status", "Kandidat", "Aksi"].map((label) => <th key={label} className="p-3">{label}</th>)}</tr></thead><tbody>
        {empty ? <tr><td colSpan={9} className="p-8 text-center">Belum ada data. Klik Unggah data untuk memulai.</td></tr> : rows.isError ? <tr><td colSpan={9} className="p-8 text-center">Data belum dapat dimuat.</td></tr> : rows.isPending ? <tr><td colSpan={9} className="p-8 text-center">Memuat data…</td></tr> : !rows.data?.items.length ? <tr><td colSpan={9} className="p-8 text-center">{search || status !== "all" ? "Tidak ada data sesuai pencarian atau status." : "Belum ada data. Klik Unggah data untuk memulai."}</td></tr> : rows.data.items.map((row, index) => <tr key={row.id} className="border-t border-gray-200">
          <td className="p-3 tabular-nums">{(page - 1) * pageSize + index + 1}</td><td className="p-3 font-mono">{displayValue(row.object_id)}</td><td className="p-3 font-mono">{displayValue(row.fields.agenda_ref)}</td><td className="p-3">{displayValue(row.fields.nama)}</td><td className="p-3 font-mono">{displayValue(row.fields.lon)}</td><td className="p-3 font-mono">{displayValue(row.fields.lat)}</td><td className="p-3 font-semibold">{emptyStatusLabel[row.status]}</td><td className="p-3">{row.candidate_count}</td><td className="p-3"><div className="flex gap-2"><Link className={buttonClass.secondary} to={`?detail_record_id=${row.id}&batch_id=${row.batch_id}${row.process_id ? `&process_id=${row.process_id}` : ""}${row.generation ? `&generation=${row.generation}` : ""}`}>Detail</Link></div></td>
        </tr>)}
      </tbody></table></div>
      <PreviewPagination context="koreksi" page={page} pageSize={pageSize} total={empty ? 0 : rows.data?.total} loading={rows.isFetching} onPageChange={(next) => { setPage(next); }} onPageSizeChange={(size) => { setPageSize(size); setPage(1); }} />
    </section>

  </div>;
}
