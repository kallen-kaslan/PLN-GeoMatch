import { useId, useState, type FormEvent } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export type TablePaginationProps = {
  context: string;
  page: number;
  pageSize: number;
  total?: number;
  loading: boolean;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  pageSizes?: number[];
  unit?: string;
  sizeLabel?: string;
  previousLabel?: string;
  nextLabel?: string;
  openLabel?: string;
};

const count = (value: number) => value.toLocaleString("id-ID");
const button = "inline-flex h-8 min-w-8 items-center justify-center rounded-md border border-ui-border bg-white px-2 text-xs font-medium text-ui-muted transition-colors hover:bg-slate-50 hover:text-ui-primary-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ui-primary disabled:cursor-not-allowed disabled:opacity-40";
const control = "h-8 min-w-0 rounded-md border border-ui-border bg-white px-2 py-1 text-xs text-neo-black disabled:opacity-50";

export function TablePagination(props: TablePaginationProps) {
  return <PaginationControls key={`${props.context}-${props.page}-${props.pageSize}`} {...props} />;
}

function PaginationControls({ context, page, pageSize, total, loading, onPageChange, onPageSizeChange, pageSizes = [5, 10, 25, 50, 100], unit = "baris", sizeLabel = `Baris per halaman ${context}`, previousLabel = `Halaman ${context} sebelumnya`, nextLabel = `Halaman ${context} berikutnya`, openLabel = "Buka halaman" }: TablePaginationProps) {
  const id = useId();
  const [input, setInput] = useState<string | null>(null);
  const [error, setError] = useState("");
  const pages = Math.max(1, Math.ceil((total ?? 0) / pageSize));
  const disabled = loading || !total;
  const first = total ? (page - 1) * pageSize + 1 : 0;
  const last = Math.min(page * pageSize, total ?? 0);
  const visible = Array.from(new Set([1, ...Array.from({ length: 3 }, (_, i) => Math.min(Math.max(page - 1, 2), Math.max(pages - 3, 2)) + i).filter(value => value > 1 && value < pages), pages])).sort((a, b) => a - b);
  const sizes = [...new Set([...pageSizes, pageSize])].sort((a, b) => a - b);
  const navigate = (next: number) => { setInput(null); setError(""); onPageChange(next); };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const requested = Number(input ?? page);
    if (!Number.isInteger(requested) || requested < 1 || requested > pages) {
      setError(`Masukkan nomor halaman antara 1 dan ${count(pages)}.`);
      return;
    }
    navigate(requested);
  };
  return <footer aria-label={`Navigasi halaman ${context}`} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-ui-border pt-3 text-xs">
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <label className="flex items-center gap-2 text-ui-muted">Tampilkan
        <select aria-label={sizeLabel} value={pageSize} disabled={loading} onChange={event => { onPageSizeChange(Number(event.target.value)); navigate(1); }} className={`${control} pr-7`}>{sizes.map(size => <option key={size} value={size}>{size}</option>)}</select>
        <span>per halaman</span>
      </label>
      <p aria-live="polite" className="text-ui-muted">{total === undefined ? "Memuat jumlah baris..." : <>{count(total)} {unit} sesuai filter. {count(first)}&ndash;{count(last)}.</>}</p>
    </div>
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <form noValidate onSubmit={submit} aria-label={`Buka halaman ${context}`} className="flex items-center gap-2">
        <label htmlFor={id} className="whitespace-nowrap text-ui-muted">Ke halaman</label>
        <input id={id} aria-label={`Nomor halaman ${context}`} aria-invalid={!!error} aria-describedby={error ? `${id}-error` : undefined} type="number" inputMode="numeric" min={1} max={pages} step={1} value={input ?? page} onChange={event => { setInput(event.target.value); setError(""); }} disabled={disabled} className={`${control} w-12 px-1.5 text-center tabular-nums`} />
        <span className="whitespace-nowrap text-ui-muted">dari {count(pages)}</span>
        <button type="submit" disabled={disabled} className={button}>{openLabel}</button>
      </form>
      <nav aria-label={`Pilih halaman ${context}`} className="flex items-center gap-1">
        <button type="button" aria-label={previousLabel} disabled={page <= 1 || disabled} onClick={() => navigate(page - 1)} className={button}><ChevronLeft size={14} aria-hidden="true" /></button>
        {visible.map((value, index) => <span key={value} className="flex items-center gap-1">{index > 0 && value - visible[index - 1] > 1 && <span aria-hidden="true" className="px-1 text-ui-muted">...</span>}<button type="button" aria-label={`Halaman ${context} ${value}`} aria-current={value === page ? "page" : undefined} disabled={disabled} onClick={() => navigate(value)} className={`flex h-8 min-w-8 items-center justify-center rounded-md border px-2 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ui-primary disabled:cursor-not-allowed disabled:opacity-40 ${value === page ? "border-ui-accent-text bg-ui-accent-soft text-ui-accent-text" : "border-transparent bg-white text-ui-muted hover:bg-slate-50"}`}>{count(value)}</button></span>)}
        <button type="button" aria-label={nextLabel} disabled={page >= pages || disabled} onClick={() => navigate(page + 1)} className={button}><ChevronRight size={14} aria-hidden="true" /></button>
      </nav>
    </div>
    {error && <p id={`${id}-error`} role="alert" className="w-full text-red-700">{error}</p>}
  </footer>;
}
