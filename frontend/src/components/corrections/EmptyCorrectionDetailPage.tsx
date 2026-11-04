import { CorrectionPageHeader } from "./CorrectionPageHeader";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowDownNarrowWide, ArrowDownWideNarrow, ChevronLeft, ChevronRight, FileSpreadsheet, LoaderCircle, X } from "lucide-react";
import { correctionApi, searchLabel, type CorrectionCandidate } from "@/lib/corrections";
import { displayValue } from "@/lib/master";
import { PDPJ_FIELDS } from "@/lib/pdpj";
import { buttonClass } from "@/lib/button";
import { emptySourceFields } from "@/lib/empty-correction-fields";
import { CandidateCoordinateSource } from "./CandidateCoordinateSource";

const cell = "px-4 py-3.5 align-middle";

function CandidateSources({ candidate, onClose }: { candidate: CorrectionCandidate; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const pressedOutside = useRef(false);
  const outside = (element: HTMLDialogElement, x: number, y: number) => {
    const bounds = element.getBoundingClientRect();
    return x < bounds.left || x > bounds.right || y < bounds.top || y > bounds.bottom;
  };
  useEffect(() => {
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const element = dialog.current;
    element?.showModal();
    return () => { element?.close(); document.body.style.overflow = overflow; if (previous instanceof HTMLElement && previous.isConnected) previous.focus(); };
  }, []);
  return createPortal(<dialog ref={dialog} aria-labelledby="candidate-source-title"
    onPointerDown={(event) => { pressedOutside.current = event.target === event.currentTarget && outside(event.currentTarget, event.clientX, event.clientY); }}
    onClick={(event) => {
      if (pressedOutside.current && event.target === event.currentTarget && outside(event.currentTarget, event.clientX, event.clientY)) onClose();
      pressedOutside.current = false;
    }}
    onCancel={(event) => { event.preventDefault(); onClose(); }} className="fixed inset-0 m-auto max-h-[85dvh] w-[calc(100%_-_2rem)] max-w-3xl overflow-y-auto rounded-xl border border-ui-border bg-white p-5 text-neo-black shadow-xl backdrop:bg-black/50 sm:p-6">
    <header className="mb-5 flex items-start justify-between gap-4 border-b border-ui-border pb-4"><div><h2 id="candidate-source-title" className="text-lg font-semibold">Detail Sumber Kandidat</h2><p className="mt-1 text-sm text-ui-muted">{displayValue(candidate.fields.idpel)} &#183; {displayValue(candidate.fields.nama)}</p></div><button autoFocus type="button" aria-label="Tutup detail sumber kandidat" onClick={onClose} className={buttonClass.secondary}><X size={18} /></button></header>
    <CandidateCoordinateSource fields={candidate.fields} />
    <div className="mt-4 space-y-4">{candidate.observations.length ? candidate.observations.map((source, index) => <section key={index} className="rounded-lg border border-ui-border p-4">
      <div className="flex items-start gap-3"><FileSpreadsheet size={20} className="mt-0.5 shrink-0 text-ui-muted" /><div className="min-w-0"><h3 className="break-words text-sm font-semibold">{source.filename}</h3><p className="mt-1 text-xs text-ui-muted">{source.dataset_type.toUpperCase()} &#183; Sheet {displayValue(source.source_sheet)} &#183; Baris {source.row_number}</p></div></div>
      <dl className="mt-4 grid gap-x-6 gap-y-3 sm:grid-cols-2">{PDPJ_FIELDS.filter((field) => source.fields[field.key] !== null && source.fields[field.key] !== undefined && source.fields[field.key] !== "").map((field) => <div key={field.key} className="min-w-0 border-b border-ui-border pb-2"><dt className="text-xs font-semibold text-ui-muted">{field.label}</dt><dd className="mt-1 break-words text-sm [overflow-wrap:anywhere]">{displayValue(source.fields[field.key])}</dd></div>)}</dl>
    </section>) : <p className="text-sm text-ui-muted">Rincian sumber belum tersedia untuk kandidat ini.</p>}</div>
  </dialog>, document.body);
}

export function EmptyCorrectionDetailPage() {
  const [params] = useSearchParams();
  const recordId = Number(params.get("detail_record_id"));
  const processId = Number(params.get("process_id")) || undefined;
  const generation = Number(params.get("generation")) || undefined;
  const batchId = Number(params.get("batch_id")) || undefined;
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [sortOrder, setSortOrder] = useState<"nearest" | "farthest">("nearest");
  const [candidate, setCandidate] = useState<CorrectionCandidate | null>(null);
  const valid = Number.isSafeInteger(recordId) && recordId > 0;
  const detail = useQuery({ queryKey: ["corrections", "idpel_kosong", "detail", recordId, processId, generation, offset, pageSize, sortOrder], queryFn: () => correctionApi.detail("idpel_kosong", recordId, { batch_id: batchId, process_id: processId, generation }, offset, undefined, pageSize, sortOrder), placeholderData: keepPreviousData, enabled: valid });
  const record = detail.data;
  const page = Math.floor(offset / pageSize) + 1;
  const pages = Math.max(1, Math.ceil((record?.candidates_total ?? 0) / pageSize));
  const visiblePages = Array.from(new Set([1, ...Array.from({ length: 3 }, (_, index) => Math.min(Math.max(page - 1, 2), Math.max(pages - 3, 2)) + index).filter((value) => value > 1 && value < pages), pages])).sort((a, b) => a - b);
  const original = Object.fromEntries(Object.entries(record?.raw_data ?? {}).map(([key, value]) => [key.toLowerCase().replace(/[^a-z0-9]/g, ""), value]));
  return <div className="space-y-5 sm:space-y-6">
    <CorrectionPageHeader title="Detail Data" />
    {!valid ? <p role="alert">Data tidak ditemukan. Pilih data dari halaman IDPEL Kosong.</p> : detail.isPending ? <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={18} className="animate-spin" />Memuat detail data...</p> : detail.isError ? <p role="alert" className="text-sm text-red-700">Detail belum dapat dimuat. <button type="button" onClick={() => void detail.refetch()} className="font-semibold underline">Coba lagi</button></p> : record && <>
      <section aria-label="Data pelanggan" className="rounded-xl border border-ui-border bg-white p-5 sm:p-6">
        <header className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-ui-border pb-4"><div><h2 className="text-base font-semibold">Data Pelanggan</h2><p className="mt-1 break-words text-xs text-ui-muted">{record.filename} &#183; Sheet {displayValue(record.source_sheet)} &#183; Baris {record.row_number}</p></div><span className="rounded-md bg-ui-accent-soft px-3 py-1.5 text-xs font-semibold text-ui-accent-text">{searchLabel[record.search_status]}</span></header>
        <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2 xl:grid-cols-3">{emptySourceFields.map((field) => <div key={field.key} className={`min-w-0 border-b border-ui-border pb-3 ${field.key === "alamatlengkap" ? "sm:col-span-2 xl:col-span-1" : ""}`}><dt className="text-xs font-semibold text-ui-muted">{field.label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm [overflow-wrap:anywhere]">{displayValue(original[field.key])}</dd></div>)}</dl>
      </section>
      <section aria-label="Daftar kandidat" className="space-y-4 rounded-xl border border-ui-border bg-white p-4 sm:p-6">
        <header className="flex items-center justify-between gap-3">
          <div><h2 className="text-base font-semibold">Kandidat ({record.candidates_total.toLocaleString("id-ID")})</h2>{record.radius_meters !== null && <p className="mt-1 text-xs text-ui-muted">Radius {record.radius_meters.toLocaleString("id-ID")} m</p>}</div>
          <div className="group relative shrink-0">
          <button type="button" aria-describedby="candidate-sort-tooltip" aria-label="Urutan jarak kandidat" aria-pressed={sortOrder === "farthest"} disabled={detail.isFetching || record.candidates_total === 0} onClick={() => { setSortOrder(sortOrder === "nearest" ? "farthest" : "nearest"); setOffset(0); }} className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-ui-border bg-white text-ui-primary-text transition-colors hover:border-ui-accent-text hover:bg-ui-accent-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ui-primary disabled:cursor-not-allowed disabled:opacity-50">{sortOrder === "nearest" ? <ArrowDownNarrowWide size={19} aria-hidden="true" /> : <ArrowDownWideNarrow size={19} aria-hidden="true" />}</button>
          <div id="candidate-sort-tooltip" role="tooltip" className="pointer-events-none absolute right-0 top-full z-20 mt-2 w-48 translate-y-1 rounded-lg border border-ui-border bg-white px-3 py-2.5 text-left shadow-lg opacity-0 invisible transition-[opacity,transform,visibility] duration-150 group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100">
            <p className="text-xs font-semibold text-neo-black">{sortOrder === "nearest" ? "Jarak terdekat" : "Jarak terjauh"}</p>
            <p className="mt-1 text-xs leading-relaxed text-ui-muted">{sortOrder === "nearest" ? "Klik untuk urutkan dari terjauh" : "Klik untuk urutkan dari terdekat"}</p>
          </div>
          </div>
          <span role="status" className="sr-only">{sortOrder === "nearest" ? "Kandidat diurutkan dari jarak terdekat" : "Kandidat diurutkan dari jarak terjauh"}</span>
        </header>
        <div className="overflow-x-auto rounded-lg border border-ui-border"><table aria-busy={detail.isFetching} className="w-full min-w-[980px] text-left text-sm"><thead className="bg-ui-table-head text-xs text-ui-muted"><tr>{["No", "IDPEL", "Nama Pelanggan", "Nomor Agenda", "Koordinat X", "Koordinat Y", "Jarak", "Aksi"].map((label) => <th key={label} scope="col" className={`${cell} whitespace-nowrap font-semibold`}>{label}</th>)}</tr></thead><tbody>{detail.isPlaceholderData ? <tr><td colSpan={8} className="p-8 text-center text-sm text-ui-muted">Memuat kandidat...</td></tr> : record.candidates.length ? record.candidates.map((item, index) => <tr key={item.id} className="border-t border-ui-border hover:bg-slate-50"><td className={`${cell} w-14 tabular-nums text-ui-muted`}>{offset + index + 1}</td><td className={`${cell} whitespace-nowrap font-mono`}>{displayValue(item.fields.idpel)}</td><td className={`${cell} min-w-44 max-w-72 break-words font-medium`}>{displayValue(item.fields.nama)}</td><td className={`${cell} whitespace-nowrap font-mono tabular-nums`}>{displayValue(item.fields.agenda_ref)}</td><td className={`${cell} whitespace-nowrap font-mono tabular-nums`}>{displayValue(item.fields.lon)}</td><td className={`${cell} whitespace-nowrap font-mono tabular-nums`}>{displayValue(item.fields.lat)}</td><td className={`${cell} whitespace-nowrap tabular-nums`}>{item.distance_meters.toLocaleString("id-ID", { maximumFractionDigits: 2 })} m</td><td className={cell}><button type="button" className={buttonClass.secondary} aria-label={`Detail sumber kandidat ${item.fields.idpel}`} onClick={() => setCandidate(item)}>Detail</button></td></tr>) : <tr><td colSpan={8} className="p-8 text-center text-sm text-ui-muted">{record.search_status === "not_checked" ? "Data ini belum diproses untuk pencarian kandidat." : record.search_status === "incomplete_coordinates" || record.search_status === "invalid_data" ? "Periksa data dan koordinat sumber sebelum mencari kandidat." : "Tidak ada kandidat tersimpan untuk data ini."}</td></tr>}</tbody></table></div>
        <footer aria-label="Navigasi halaman kandidat" className="flex flex-wrap items-center justify-between gap-x-5 gap-y-3 text-xs">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
            <label className="flex items-center gap-2 text-ui-muted">Tampilkan
              <select aria-label="Kandidat per halaman" value={pageSize} disabled={detail.isFetching} onChange={(event) => { setPageSize(Number(event.target.value)); setOffset(0); }} className="min-h-9 rounded-md border border-ui-border bg-white py-1.5 pl-3 pr-9 text-sm font-medium text-neo-black disabled:opacity-50">{[5, 10, 25, 50].map((size) => <option key={size} value={size}>{size}</option>)}</select>
              <span>per halaman</span>
            </label>
            <p aria-live="polite" className="text-ui-muted">{record.candidates_total ? offset + 1 : 0}&ndash;{Math.min(offset + pageSize, record.candidates_total)} dari <span className="font-semibold text-neo-black">{record.candidates_total.toLocaleString("id-ID")}</span> kandidat</p>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <form key={`${page}-${pageSize}-${sortOrder}`} aria-label="Buka halaman kandidat" onSubmit={(event) => {
            event.preventDefault();
            const requested = Number(new FormData(event.currentTarget).get("candidate_page"));
            if (Number.isInteger(requested) && requested >= 1 && requested <= pages) setOffset((requested - 1) * pageSize);
          }} className="flex items-center gap-2">
            <label htmlFor="candidate-page-number" className="whitespace-nowrap text-ui-muted">Ke halaman</label>
            <input id="candidate-page-number" name="candidate_page" aria-label="Nomor halaman kandidat" type="number" inputMode="numeric" min={1} max={pages} step={1} required defaultValue={page} disabled={detail.isFetching || record.candidates_total === 0} className="min-h-9 w-16 rounded-md border border-ui-border bg-white px-2 py-1.5 text-center text-sm tabular-nums disabled:opacity-50" />
            <span className="whitespace-nowrap text-ui-muted">dari {pages.toLocaleString("id-ID")}</span>
            <button type="submit" disabled={detail.isFetching || record.candidates_total === 0} className={buttonClass.secondary}>Buka</button>
          </form>
          <nav aria-label="Pilih halaman kandidat" className="flex flex-wrap items-center gap-1.5">
            <button type="button" aria-label="Halaman kandidat sebelumnya" disabled={page <= 1 || detail.isFetching} onClick={() => setOffset(Math.max(0, offset - pageSize))} className={`${buttonClass.secondary} gap-1.5`}><ChevronLeft size={16} /><span className="hidden sm:inline">Sebelumnya</span></button>
            {visiblePages.map((value, index) => <span key={value} className="flex items-center gap-1.5">{index > 0 && value - visiblePages[index - 1] > 1 && <span aria-hidden="true" className="px-1 text-ui-muted">...</span>}<button type="button" aria-label={`Halaman kandidat ${value}`} aria-current={value === page ? "page" : undefined} disabled={detail.isFetching || record.candidates_total === 0} onClick={() => setOffset((value - 1) * pageSize)} className={`flex min-h-9 min-w-9 items-center justify-center rounded-md border px-2.5 text-sm font-medium transition-colors disabled:opacity-50 ${value === page ? "border-ui-accent-text bg-ui-accent-soft text-ui-accent-text" : "border-ui-border bg-white hover:bg-slate-50"}`}>{value}</button></span>)}
            <button type="button" aria-label="Halaman kandidat berikutnya" disabled={page >= pages || detail.isFetching} onClick={() => setOffset(offset + pageSize)} className={`${buttonClass.secondary} gap-1.5`}><span className="hidden sm:inline">Berikutnya</span><ChevronRight size={16} /></button>
          </nav>
          </div>
        </footer>
      </section>
    </>}
    {candidate && <CandidateSources candidate={candidate} onClose={() => setCandidate(null)} />}
  </div>;
}
