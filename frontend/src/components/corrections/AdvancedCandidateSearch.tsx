import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { LoaderCircle, Search } from "lucide-react";
import { SearchFeedback } from "@/components/data/SearchFeedback";
import { correctionApi, type AdvancedSearchField, type AdvancedSearchResults, type CorrectionCandidate } from "@/lib/corrections";
import { buttonClass } from "@/lib/button";
import { displayValue, type CorrectionKind } from "@/lib/master";
import type { Fields } from "@/lib/pdpj";
import type { ApiError } from "@/lib/api";
import { searchPreparing, searchRefreshInterval } from "@/lib/search";

const control = "min-w-0 rounded-lg border border-ui-border bg-white px-3 py-2 text-sm disabled:opacity-50";
const actionLabel = {
  missing_coordinates: "Koordinat target atau bukti lokasi master belum lengkap. Lengkapi sumber lalu buat pemeriksaan baru.",
  expand_search: "Lokasi kandidat berada di luar radius pemeriksaan tersimpan. Perluas pemeriksaan sebelum memilih.",
  change_filter: "Kandidat berada di luar filter radius pilihan. Tinjau dengan radius tersimpan melalui peta.",
  rerun_search: "Kandidat ini belum tersedia pada hasil tersimpan. Periksa ulang sumber yang sama sebelum memilih.",
  fix_target: "Data target belum memenuhi syarat pemilihan kandidat. Perbaiki sumber dan periksa ulang.",
  choose: "Kandidat tersedia pada hasil tersimpan dalam radius pilihan.",
};

export function AdvancedCandidateSearch({ kind, processId, recordId, rowNumber, generation, radius, fingerprint, fields, mapUrl, disabled, canChoose, onChoose }: {
  kind: CorrectionKind; processId: number; recordId: number; rowNumber: number; generation: number; radius: number;
  fingerprint: string; fields: Fields; mapUrl: string; disabled: boolean; canChoose: boolean; onChoose: (candidate: CorrectionCandidate) => void;
}) {
  const initialMeter = fields.meter_ref || fields.nomor_meter_kwh || fields.nomor_meter_prepaid;
  const [open, setOpen] = useState(false);
  const [field, setField] = useState<AdvancedSearchField>(initialMeter ? "meter" : "idpel");
  const [input, setInput] = useState(String(initialMeter || fields.idpel || ""));
  const [request, setRequest] = useState<{ field: AdvancedSearchField; q: string; skip: number } | null>(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<number[]>([]);
  const results = useQuery<AdvancedSearchResults, ApiError>({
    queryKey: ["corrections", kind, "advanced-candidates", processId, generation, recordId, radius, fingerprint, request],
    queryFn: ({ signal }) => correctionApi.advancedCandidates(kind, processId, recordId, { ...request!, generation, radius_meters: radius }, signal),
    enabled: open && request !== null, retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: false, refetchInterval: searchRefreshInterval,
  });
  const pendingIndex = searchPreparing(results.data);
  return <section aria-label="Pencarian kandidat lanjutan" className="space-y-3 rounded-lg border border-ui-border bg-white p-3 sm:p-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h6 className="text-sm font-semibold">Pencarian identitas di master sisa</h6><p className="mt-1 text-xs text-ui-muted">Gunakan bukti tambahan untuk target baris {rowNumber}. Pencarian memakai sumber pemeriksaan yang sama, mencakup lokasi di luar radius, serta mengecualikan IDPEL yang dipilih target lain.</p></div><button type="button" disabled={disabled} onClick={() => setOpen(!open)} className={buttonClass.secondary}><Search size={16} />{open ? "Tutup pencarian lanjutan" : "Cari Kandidat Lanjutan"}</button></div>
    {open && <>
      <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={(event) => { event.preventDefault(); if (disabled || results.isFetching) return; if (input.trim().length < 3) { setError("Isi sedikitnya 3 karakter identitas pencarian."); return; } setError(""); setHistory([]); if (request?.field === field && request.q === input.trim() && request.skip === 0) { void results.refetch(); } else { setRequest({ field, q: input.trim(), skip: 0 }); } }}>
        <label className="flex flex-col gap-1.5 text-xs font-semibold">Cari berdasarkan<select aria-label="Cari kandidat lanjutan berdasarkan" value={field} disabled={disabled} onChange={(event) => { const value = event.target.value as AdvancedSearchField; setField(value); setInput(String(value === "meter" ? initialMeter || "" : value === "idpel" ? fields.idpel || "" : value === "nama" ? fields.nama === "-" ? "" : fields.nama || "" : fields.kode_gardu || "")); setRequest(null); setError(""); }} className={control}><option value="idpel">IDPEL lengkap</option><option value="meter">Nomor meter lengkap</option><option value="nama">Nama pelanggan</option><option value="gardu">Kode gardu lengkap</option></select></label>
        <label className="flex min-w-0 flex-1 flex-col gap-1.5 text-xs font-semibold">Identitas pencarian<input aria-label="Identitas untuk kandidat lanjutan" type="search" maxLength={100} value={input} disabled={disabled} onChange={(event) => { setInput(event.target.value); setRequest(null); setError(""); }} className={control} placeholder="Masukkan identitas dari bukti yang tersedia" /></label>
        <button type="submit" disabled={disabled || results.isFetching} className={buttonClass.primary}>Cari di master sisa</button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {results.isFetching && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Mencari identitas dan memeriksa sumber serta pemakaian IDPEL...</p>}
      {request && results.error && <p role="alert" className="text-sm text-red-700">{results.error.message} <button type="button" onClick={() => void results.refetch()} className="font-semibold underline">Coba lagi</button></p>}
      {request && <SearchFeedback state={results.data?.search_index} waiting={false} fetching={results.isFetching} />}
      {request && results.data && !results.isFetching && !pendingIndex && <>
        <p className="text-xs text-ui-muted">Hasil merupakan usulan untuk diverifikasi. Kecocokan identitas dan alasan pendukung ditampilkan untuk setiap IDPEL.</p>
        {!results.data.items.length && <p role="status" className="text-sm">Tidak ada IDPEL tersedia yang cocok pada halaman ini. Periksa identitas, lanjutkan hasil berikutnya jika tersedia, atau tinjau sumber master.</p>}
        {results.data.items.map((item) => {
          const targetParams = new URLSearchParams(mapUrl.split("?")[1]);
          targetParams.set("record_id", String(recordId)); targetParams.set("map_view", "map");
          if (item.suggested_radius_meters !== null) targetParams.set("expansion_radius_meters", String(item.suggested_radius_meters));
          else if (item.action === "change_filter") targetParams.set("radius_meters", String(item.distance_meters === null ? radius : Math.min(Math.ceil(item.distance_meters) + 1, results.data!.stored_radius_meters ?? Math.ceil(item.distance_meters))));
          return <article key={item.idpel} aria-label={`Kandidat lanjutan IDPEL ${item.idpel}`} className="space-y-3 rounded-lg border border-ui-border bg-slate-50 p-3 text-xs">
            <div className="flex flex-wrap justify-between gap-3"><div><p className="font-mono font-semibold">IDPEL {item.idpel}</p><p className="mt-1">{displayValue(item.fields.nama)}</p></div><p className="font-semibold">{item.distance_meters === null ? "Jarak belum tersedia" : `${item.distance_meters.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m`}</p></div>
            <dl className="grid gap-3 sm:grid-cols-3">{[["Meter", item.fields.nomor_meter_kwh || item.fields.nomor_meter_prepaid || item.fields.meter_ref || item.fields.target_ref], ["Alamat", item.fields.alamat], ["Gardu", item.fields.kode_gardu]].map(([label, value]) => <div key={String(label)}><dt className="font-semibold text-ui-muted">{label}</dt><dd className="mt-1 break-words">{displayValue(value)}</dd></div>)}</dl>
            <ul className="list-inside list-disc space-y-1">{item.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
            {item.coordinate_source && <p className="break-words">Sumber koordinat: {item.coordinate_source.filename} · Sheet {item.coordinate_source.source_sheet || "—"} · Baris {item.coordinate_source.row_number} · Periode {displayValue(item.coordinate_source.fields.tglbaca)}</p>}
            <details><summary className="cursor-pointer font-semibold">Bukti identitas dari sumber ({item.matched_sources.length})</summary><ul className="mt-2 space-y-2">{item.matched_sources.map((source, index) => <li key={index} className="rounded border border-ui-border bg-white p-2"><p className="break-words">{source.filename} · Sheet {source.source_sheet || "—"} · Baris {source.row_number}</p><p className="mt-1">Nama: {displayValue(source.fields.nama)} · Meter: {displayValue(source.fields.nomor_meter_kwh || source.fields.nomor_meter_prepaid || source.fields.meter_ref)} · Alamat: {displayValue(source.fields.alamat)} · Gardu: {displayValue(source.fields.kode_gardu)}</p></li>)}</ul></details>
            <p>{actionLabel[item.action]}</p>
            {item.candidate ? <button type="button" aria-label={`Pilih kandidat lanjutan IDPEL ${item.idpel} untuk baris ${rowNumber}`} disabled={disabled || !canChoose} onClick={() => onChoose(item.candidate!)} className={buttonClass.primary}>Pilih hasil terverifikasi</button>
              : <Link className="inline-block font-semibold underline" to={`/peta-koreksi?${targetParams}`}>{item.action === "expand_search" && item.suggested_radius_meters !== null ? `Tinjau perluasan pemeriksaan ke ${item.suggested_radius_meters} m` : "Tinjau target melalui Peta Koreksi"}</Link>}
          </article>;
        })}
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs"><p>Halaman {history.length + 1}</p><div className="flex gap-2"><button type="button" disabled={disabled || !history.length} onClick={() => { setRequest({ ...request, skip: history[history.length - 1] }); setHistory(history.slice(0, -1)); }} className={buttonClass.secondary}>Hasil sebelumnya</button><button type="button" disabled={disabled || !results.data.has_more || results.data.next_skip == null} onClick={() => { setHistory([...history, request.skip]); setRequest({ ...request, skip: results.data!.next_skip! }); }} className={buttonClass.secondary}>Hasil berikutnya</button></div></div>
      </>}
    </>}
  </section>;
}
