import { useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { buttonClass } from "@/lib/button";

type PreviewPaginationProps = {
  context: "master" | "koreksi";
  page: number;
  pageSize: number;
  total?: number;
  loading: boolean;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
};

const count = (value: number) => value.toLocaleString("id-ID");
const control = "min-w-0 rounded-sm border-2 border-neo-border bg-white px-3 py-2 text-sm disabled:opacity-50";

export function PreviewPagination({ context, page, pageSize, total, loading, onPageChange, onPageSizeChange }: PreviewPaginationProps) {
  const [input, setInput] = useState<string | null>(null);
  const [error, setError] = useState("");
  const pages = Math.max(1, Math.ceil((total ?? 0) / pageSize));
  const disabled = loading || !total;
  const first = total ? (page - 1) * pageSize + 1 : 0;
  const last = Math.min(page * pageSize, total ?? 0);
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
  return <footer aria-label={`Navigasi halaman ${context}`} className="flex flex-wrap items-center justify-between gap-3 text-xs">
    <p aria-live="polite">{total === undefined ? "Memuat jumlah baris..." : `${count(total)} baris sesuai filter. Menampilkan ${count(first)}–${count(last)}. Halaman ${count(page)} dari ${count(pages)}`}</p>
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex items-center gap-2 font-bold">Baris per halaman
        <select aria-label={`Baris per halaman ${context}`} value={pageSize} onChange={(event) => { onPageSizeChange(Number(event.target.value)); navigate(1); }} className={control}>
          {[10, 25, 50, 100].map((size) => <option key={size} value={size}>{size} baris</option>)}
        </select>
      </label>
      <form noValidate onSubmit={submit} className="flex flex-wrap items-center gap-2">
        <label htmlFor={`${context}-page-number`} className="font-bold">Ke halaman</label>
        <input id={`${context}-page-number`} aria-label={`Nomor halaman ${context}`} aria-invalid={!!error} aria-describedby={error ? `${context}-page-error` : undefined} type="number" inputMode="numeric" min={1} max={pages} step={1} value={input ?? page} onChange={(event) => { setInput(event.target.value); setError(""); }} disabled={disabled} className={`${control} w-24`} />
        <button type="submit" disabled={disabled} className={buttonClass.secondary}>Buka halaman</button>
      </form>
      <div className="flex gap-2">
        <button type="button" aria-label={context === "master" ? "Halaman sebelumnya" : "Halaman koreksi sebelumnya"} disabled={page <= 1 || loading} onClick={() => navigate(page - 1)} className={buttonClass.secondary}><ArrowLeft size={16} /></button>
        <button type="button" aria-label={context === "master" ? "Halaman berikutnya" : "Halaman koreksi berikutnya"} disabled={page >= pages || loading} onClick={() => navigate(page + 1)} className={buttonClass.secondary}><ArrowRight size={16} /></button>
      </div>
    </div>
    {error && <p id={`${context}-page-error`} role="alert" className="w-full text-red-700">{error}</p>}
  </footer>;
}
