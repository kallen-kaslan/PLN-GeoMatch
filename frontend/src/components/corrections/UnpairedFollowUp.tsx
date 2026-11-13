import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { LoaderCircle, Search } from "lucide-react";
import { correctionApi, type AutomaticPreview, type UnpairedSearchResults } from "@/lib/corrections";
import { displayValue, type CorrectionKind } from "@/lib/master";
import type { ApiError } from "@/lib/api";
import { buttonClass } from "@/lib/button";
import { downloadSpreadsheet } from "@/lib/results";
import { ReviewTarget } from "./GroupedCorrectionReview";

const control = "rounded-lg border border-ui-border bg-white px-3 py-2 text-sm disabled:opacity-50";
const labels: Record<string, string> = { no_available_idpel: "Tidak ada IDPEL bebas dalam radius", shared_candidates: "Kandidat menjadi pasangan target lain", candidate_found: "Kandidat tambahan ditemukan; perlu verifikasi", missing_coordinates: "Koordinat belum lengkap", fix_target: "Perbaiki data target terlebih dahulu", outside_radius: "Di luar radius pilihan", no_candidates: "Tanpa kandidat", pdpj_conflict: "Benturan PDPJ", invalid_data: "Data perlu diperbaiki", incomplete_coordinates: "Koordinat belum lengkap" };
const count = (value: number) => value.toLocaleString("id-ID");

export function UnpairedFollowUp({ kind, processId, preview, mapUrl, disabled, onResolved, onBusyChange, onSearchBusyChange }: {
  kind: CorrectionKind; processId: number; preview: AutomaticPreview; mapUrl: string; disabled: boolean;
  onResolved: (notice: string) => void; onBusyChange: (value: boolean) => void; onSearchBusyChange: (value: boolean) => void;
}) {
  const [radius, setRadius] = useState(String(Math.max(500, preview.radius_meters * 2)));
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(null);
  const scan = useMutation<UnpairedSearchResults, ApiError, number>({
    mutationFn: (value) => correctionApi.searchUnpaired(kind, processId, { generation: preview.generation, radius_meters: preview.radius_meters, tie_strategy: "suggest", fingerprint: preview.fingerprint, search_radius_meters: value }),
    onSuccess: () => { setPage(1); setFilter("all"); },
  });
  const download = useMutation<void, ApiError, number>({ mutationFn: async (value) => {
    const file = await correctionApi.downloadUnpaired(kind, processId, { generation: preview.generation, radius_meters: preview.radius_meters, tie_strategy: "suggest", fingerprint: preview.fingerprint, search_radius_meters: value });
    downloadSpreadsheet(file.blob, file.filename);
  } });
  const working = scan.isPending || download.isPending;
  useEffect(() => { onSearchBusyChange(working); return () => onSearchBusyChange(false); }, [working, onSearchBusyChange]);
  const items = scan.data?.items ?? (preview.unpaired ?? []).map((item) => ({ ...item, available_count: 0, candidate: null }));
  const filtered = items.filter((item) => (filter === "all" || item.reason === filter) && (!query.trim() || String(item.row_number).includes(query.trim()) || item.candidate?.idpel.includes(query.trim())));
  const pages = Math.max(1, Math.ceil(filtered.length / 10));
  const currentPage = Math.min(page, pages);
  const visible = filtered.slice((currentPage - 1) * 10, currentPage * 10);
  const target = preview.unpaired?.find((item) => item.record_id === selected);
  const validRadius = Number.isFinite(Number(radius)) && Number(radius) > preview.radius_meters && Number(radius) <= 5000;
  return <section aria-label="Penanganan target tanpa pasangan" className="rounded-lg border border-ui-border bg-white p-3 sm:p-4">
    <details>
      <summary className="cursor-pointer text-sm font-semibold">Tinjau target tanpa pasangan ({count(preview.unpaired_count ?? 0)})</summary>
      <div className="mt-4 space-y-4">
        <p className="text-xs">Cari identitas berdasarkan meter, nama, atau gardu; atau periksa kandidat tambahan dengan radius lebih besar. Pilihan tersimpan, pilihan otomatis, dan usulan pasangan yang sudah ada dikecualikan dari pencarian radius lanjutan.</p>
        <form className="flex flex-wrap items-end gap-3" onSubmit={(event) => { event.preventDefault(); if (validRadius && !disabled) scan.mutate(Number(radius)); }}>
          <label className="flex flex-col gap-1.5 text-xs font-semibold">Radius pencarian lanjutan (meter)<input aria-label="Radius pencarian lanjutan (meter)" type="number" value={radius} min={preview.radius_meters + 0.01} max={5000} step="any" disabled={disabled} onChange={(event) => setRadius(event.target.value)} className={`${control} w-52`} /></label>
          {[500, 1000].filter((value) => value > preview.radius_meters).map((value) => <button key={value} type="button" disabled={disabled} onClick={() => setRadius(String(value))} className={buttonClass.secondary}>{count(value)} m</button>)}
          <button type="submit" disabled={disabled || !validRadius} className={buttonClass.primary}><Search size={16} />Cari kandidat tambahan</button>
        </form>
        {!validRadius && <p role="alert" className="text-xs text-red-700">Radius lanjutan harus lebih besar dari {count(preview.radius_meters)} m dan paling besar 5.000 m.</p>}
        {scan.isPending && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Mencari kandidat bebas untuk {count(preview.unpaired_count ?? 0)} target pada radius {count(scan.variables ?? Number(radius))} m. Pilihan belum diubah.</p>}
        {scan.error && <p role="alert" className="text-sm text-red-700">{scan.error.message}</p>}
        {scan.data && <><p role="status" className="rounded-lg bg-blue-50 p-3 text-sm">Radius {count(scan.data.search_radius_meters)} m: {count(scan.data.found_count)} target mendapat kandidat tambahan, {count(scan.data.unpaired_count)} target belum mendapat pasangan. Hasil perlu verifikasi identitas dan pemeriksaan ulang sebelum dapat dipilih.</p><button type="button" disabled={disabled || !scan.data.found_count} onClick={() => download.mutate(scan.data!.search_radius_meters)} className={buttonClass.secondary}>Unduh Usulan Lanjutan XLSX</button></>}
        {download.isPending && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Memvalidasi ulang dan menyiapkan XLSX usulan lanjutan...</p>}
        {download.error && <p role="alert" className="text-sm text-red-700">{download.error.message}</p>}
        <div className="flex flex-wrap gap-3"><label className="flex flex-col gap-1.5 text-xs font-semibold">Cari baris atau IDPEL<input aria-label="Cari target tanpa pasangan" type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} className={control} /></label><label className="flex flex-col gap-1.5 text-xs font-semibold">Status tindak lanjut<select aria-label="Status target tanpa pasangan" value={filter} onChange={(event) => { setFilter(event.target.value); setPage(1); }} className={control}><option value="all">Seluruh status</option>{Array.from(new Set(items.map((item) => item.reason))).map((reason) => <option value={reason} key={reason}>{labels[reason] ?? reason}</option>)}</select></label></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-xs"><thead className="bg-ui-table-head"><tr>{["Baris target", "Status", "Kandidat tambahan", "Tindak lanjut"].map((label) => <th key={label} className="p-3">{label}</th>)}</tr></thead><tbody>{visible.map((item) => {
          const candidate = item.candidate;
          const expansion = candidate?.suggested_radius_meters;
          const params = new URLSearchParams(mapUrl.split("?")[1]);
          params.set("record_id", String(item.record_id)); params.set("map_view", "detail");
          if (candidate) params.set("suggested_idpel", candidate.idpel);
          if (expansion) params.set("expansion_radius_meters", String(expansion));
          if (candidate?.action === "change_filter") params.set("radius_meters", String(Math.min(scan.data!.stored_radius_meters, Math.ceil(candidate.distance_meters) + 1)));
          const url = `/peta-koreksi?${params}`;
          return <tr key={item.record_id} className="border-t border-ui-border"><td className="p-3">{item.row_number}</td><td className="p-3">{labels[item.reason] ?? item.reason}</td><td className="space-y-1 p-3">{candidate ? <><p className="font-mono font-semibold">IDPEL {candidate.idpel}</p><p>{candidate.distance_meters.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m · {displayValue(candidate.fields.nama)}</p><p className="break-words">{candidate.source.filename} · Baris {candidate.source.row_number}</p><p>Meter: {displayValue(candidate.fields.nomor_meter_kwh || candidate.fields.nomor_meter_prepaid || candidate.fields.meter_ref)} · Gardu: {displayValue(candidate.fields.kode_gardu)}</p></> : "Belum ditemukan"}</td><td className="space-y-3 p-3"><button type="button" disabled={disabled} onClick={() => setSelected(item.record_id)} className="block font-semibold underline">Cari identitas baris {item.row_number}</button><Link to={url} className="block font-semibold underline">{candidate ? expansion ? `Tinjau perluasan baris ${item.row_number} ke ${expansion} m` : candidate.action === "change_filter" ? `Tinjau filter baris ${item.row_number}` : `Tinjau pemeriksaan ulang baris ${item.row_number}` : `Tinjau target baris ${item.row_number}`}</Link></td></tr>;
        })}{!visible.length && <tr><td colSpan={4} className="p-5 text-center">Tidak ada target sesuai filter.</td></tr>}</tbody></table></div>
        <div className="flex flex-wrap justify-between gap-3 text-xs"><p>{count(filtered.length)} target · Halaman {currentPage} dari {pages}</p><div className="flex gap-2"><button type="button" disabled={disabled || currentPage <= 1} onClick={() => setPage(currentPage - 1)} className={buttonClass.secondary}>Target sebelumnya</button><button type="button" disabled={disabled || currentPage >= pages} onClick={() => setPage(currentPage + 1)} className={buttonClass.secondary}>Target berikutnya</button></div></div>
        {target && <div className="space-y-3 rounded-lg border border-ui-border bg-slate-50 p-3"><ReviewTarget key={`${preview.fingerprint}-${target.record_id}`} kind={kind} processId={processId} preview={preview} target={target} groupCandidates={[]} mapUrl={mapUrl} disabled={disabled} onResolved={onResolved} onBusyChange={onBusyChange} /></div>}
      </div>
    </details>
  </section>;
}
