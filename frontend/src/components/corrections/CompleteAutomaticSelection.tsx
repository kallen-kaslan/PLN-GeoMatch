import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, LoaderCircle, WandSparkles } from "lucide-react";
import { correctionApi, type AutomaticMode, type CompletePreview, type CompleteRequest, type CompleteResult, type CorrectionRun } from "@/lib/corrections";
import type { CorrectionKind } from "@/lib/master";
import type { ApiError } from "@/lib/api";
import { buttonClass } from "@/lib/button";
import { downloadSpreadsheet, resultsApi } from "@/lib/results";

const control = "rounded-lg border border-ui-border bg-white px-3 py-2 text-sm disabled:opacity-50";
const count = (value: number) => value.toLocaleString("id-ID");
const methods = { nearest: "Jarak terdekat", equal_distance: "Pasangan jarak sama", expanded_radius: "Radius tambahan" };
export function CompleteAutomaticSelection({ kind, processId, batchId, run, radius, onRadiusChange, onModeChange, onBusyChange, onCompleted }: {
  kind: CorrectionKind; processId: number; batchId: number; run: CorrectionRun; radius: string;
  onRadiusChange: (value: string) => void; onModeChange: (value: AutomaticMode) => void;
  onBusyChange: (value: boolean) => void; onCompleted: (result: CompleteResult) => void;
}) {
  const client = useQueryClient();
  const [maximum, setMaximum] = useState(String(Math.max(500, Number(radius))));
  const [saved, setSaved] = useState<CompleteResult | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const operation = useRef<{ fingerprint: string; key: string } | null>(null);
  const preview = useMutation<CompletePreview, ApiError, CompleteRequest>({ mutationFn: (body) => correctionApi.completePreview(kind, processId, body) });
  const plan = preview.data;
  const download = useMutation<void, ApiError, Pick<CompleteResult, "generation" | "radius_meters">>({ mutationFn: async (result) => {
    const file = await resultsApi.download(kind, processId, result.generation, result.radius_meters);
    downloadSpreadsheet(file.blob, file.filename);
  } });
  const save = useMutation<CompleteResult, ApiError, CompletePreview>({
    mutationFn: (value) => {
      if (operation.current?.fingerprint !== value.fingerprint) operation.current = { fingerprint: value.fingerprint, key: crypto.randomUUID() };
      return correctionApi.completeApply(kind, processId, { generation: value.generation, radius_meters: value.radius_meters, max_radius_meters: value.max_radius_meters, fingerprint: value.fingerprint, request_key: operation.current.key });
    },
    onSuccess: async (result) => {
      setSaved(result);
      void client.invalidateQueries({ queryKey: ["corrections", kind, "summary"] });
      try { await download.mutateAsync(result); } catch { /* Saving succeeded; retry the download independently. */ }
      try {
        const updated = await correctionApi.check(kind, processId);
        client.setQueryData(["corrections", kind, "check", processId], updated);
        onCompleted(result);
        for (const key of ["process-history", "correction-results", "correction-result-versions", "correction-choice", "correction-decisions", "correction-map-candidates", "correction-map-rows"]) void client.invalidateQueries({ queryKey: [key] });
      } catch { /* Keep the saved result and links available if refresh fails. */ }
    },
  });
  const busy = preview.isPending || save.isPending || download.isPending;
  useEffect(() => { onBusyChange(busy); return () => onBusyChange(false); }, [busy, onBusyChange]);
  const valid = Number(radius) > 0 && Number(radius) <= run.radius_meters && Number(maximum) >= Number(radius) && Number(maximum) <= 5000;
  const reset = () => { preview.reset(); save.reset(); download.reset(); setSaved(null); setPage(1); operation.current = null; };
  const filtered = (plan?.selections ?? []).filter((item) => !search.trim() || item.idpel.includes(search.trim()) || String(item.row_number).includes(search.trim()));
  const pages = Math.max(1, Math.ceil(filtered.length / 20));
  const visible = filtered.slice((Math.min(page, pages) - 1) * 20, Math.min(page, pages) * 20);
  const viewGeneration = saved?.generation ?? run.generation;
  const viewRadius = saved?.radius_meters ?? Number(radius);
  const mapUrl = `/peta-koreksi?category=${kind}&batch_id=${batchId}&process_id=${processId}&generation=${viewGeneration}&radius_meters=${viewRadius}`;
  return <section aria-label="Pemilihan otomatis lengkap" className="space-y-4 rounded-lg border border-ui-border bg-white p-4 sm:p-5">
    <h2 className="flex items-center gap-2 text-sm font-semibold"><WandSparkles size={18} />Pemilihan otomatis lengkap</h2>
    <p className="text-xs">Satu IDPEL untuk satu target. Pilihan tersimpan tetap dipertahankan. Sistem menyimpan pasangan terdekat dan jarak sama, lalu mencari kandidat bebas hingga batas radius hanya untuk target yang tersisa. Hasil dicatat sebagai pilihan otomatis dengan identitas belum diverifikasi.</p>
    <p className="text-xs text-ui-muted">Ringkasan pilihan tersimpan di atas mengikuti radius awal. Pratinjau di bawah menghitung pilihan baru hingga batas radius otomatis. Keputusan lama pada semua radius, termasuk pembatalan, tetap dipertahankan.</p>
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1.5 text-xs font-semibold">Penanganan jarak sama<select aria-label="Penanganan jarak sama" value="complete" disabled={busy} onChange={(event) => onModeChange(event.target.value as AutomaticMode)} className={control}><option value="review">Tinjau manual</option><option value="suggest">Usulkan pasangan untuk jarak sama</option><option value="complete">Pemilihan otomatis lengkap</option></select></label>
      <label className="flex flex-col gap-1.5 text-xs font-semibold">Radius pilihan otomatis (meter)<input aria-label="Radius pilihan otomatis (meter)" type="number" min="0.01" max={run.radius_meters} step="any" value={radius} disabled={busy} onChange={(event) => { reset(); onRadiusChange(event.target.value); }} className={`${control} w-52`} /></label>
      <label className="flex flex-col gap-1.5 text-xs font-semibold">Batas radius otomatis (meter)<input aria-label="Batas radius otomatis (meter)" type="number" min={Number(radius)} max={5000} step="any" value={maximum} disabled={busy} onChange={(event) => { reset(); setMaximum(event.target.value); }} className={`${control} w-52`} /></label>
      <button type="button" disabled={busy || !valid} className={buttonClass.secondary} onClick={() => { reset(); preview.mutate({ generation: run.generation, radius_meters: Number(radius), max_radius_meters: Number(maximum) }); }}>Pratinjau lengkap</button>
    </div>
    {!valid && <p role="alert" className="text-sm text-red-700">Radius awal harus berada dalam radius tersimpan. Batas radius harus sama atau lebih besar dari radius awal, maksimal 5.000 m.</p>}
    {busy && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />{preview.isPending ? "Menghitung pasangan, menyelesaikan jarak sama, dan mencari kandidat tambahan. Pilihan belum diubah..." : save.isPending && !saved ? "Memvalidasi pasangan dan menyimpan pilihan beserta versi radius dan riwayatnya..." : "Pilihan tersimpan. Menyiapkan XLSX dan memperbarui hasil..."}</p>}
    {(preview.error || save.error) && <p role="alert" className="text-sm text-red-700">{preview.error?.message ?? save.error?.message}{save.error?.status === 409 && " Buat pratinjau lengkap ulang."}</p>}
    {plan && <>
      <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">{[["Pilihan baru yang akan disimpan", plan.selected_count], ["Keputusan tersimpan dipertahankan", plan.protected_count], ["Pasangan jarak sama", plan.equal_distance_count], ["Pasangan radius tambahan", plan.expanded_count], ["Belum mendapat pasangan", plan.unpaired_count]].map(([label, value]) => <div key={String(label)} className="rounded-lg bg-gray-50 p-3"><dt className="text-xs text-ui-muted">{label}</dt><dd className="mt-1 text-lg font-semibold">{count(Number(value))}</dd></div>)}</dl>
      <p className="text-xs">Radius hasil dan ekspor: {count(plan.result_radius_meters)} m. {plan.creates_version ? "Penyimpanan membuat versi baru untuk kandidat tambahan terpilih; kandidat lama dan pilihan sebelumnya tetap tersedia." : "Pilihan disimpan pada versi pemeriksaan ini."} Target dengan data bermasalah atau tanpa IDPEL bebas tetap dilaporkan.</p>
      <label className="flex flex-col gap-1.5 text-xs font-semibold">Cari pasangan otomatis<input aria-label="Cari pasangan otomatis lengkap" type="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} className={control} /></label>
      <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left text-xs"><thead className="bg-ui-table-head"><tr>{["Baris target", "IDPEL terpilih", "Jarak", "Metode", "Peta"].map((label) => <th key={label} className="p-3">{label}</th>)}</tr></thead><tbody>{visible.map((item) => <tr key={item.record_id} className="border-t border-ui-border"><td className="p-3">{item.row_number}</td><td className="p-3 font-mono font-semibold">{item.idpel}</td><td className="p-3">{item.distance_meters.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m</td><td className="p-3">{methods[item.method]}</td><td className="p-3"><Link to={`${mapUrl}&record_id=${item.record_id}&map_view=detail&suggested_idpel=${encodeURIComponent(item.idpel)}`} className="font-semibold underline">Tinjau baris {item.row_number}</Link></td></tr>)}</tbody></table></div>
      <div className="flex flex-wrap justify-between gap-3 text-xs"><p>{count(filtered.length)} pasangan · Halaman {Math.min(page, pages)} dari {pages}</p><div className="flex gap-2"><button type="button" disabled={busy || page <= 1} onClick={() => setPage(page - 1)} className={buttonClass.secondary}>Pasangan sebelumnya</button><button type="button" disabled={busy || page >= pages} onClick={() => setPage(page + 1)} className={buttonClass.secondary}>Pasangan berikutnya</button></div></div>
      {!!plan.unpaired_count && <details className="text-xs"><summary className="cursor-pointer font-semibold">Target belum mendapat pasangan ({count(plan.unpaired_count)})</summary><ul className="mt-3 space-y-2">{plan.unpaired.slice(0, 50).map((item) => <li key={item.record_id}>Baris {item.row_number} · {item.reason} · <Link to={`${mapUrl}&record_id=${item.record_id}&map_view=detail`} className="underline">Tinjau target</Link></li>)}</ul></details>}
      {saved && <p role="status" className="rounded-lg bg-green-50 p-3 text-sm text-green-800">{count(saved.selected_count)} pilihan otomatis lengkap tersimpan pada versi {saved.generation}, radius {count(saved.radius_meters)} m. Hasil dan ekspor sudah mencakup pasangan tersebut.</p>}
      {download.error && <p role="alert" className="text-sm text-red-700">Pilihan sudah tersimpan. Unduhan belum berhasil; gunakan Unduh ulang XLSX.</p>}
      <div className="flex flex-wrap items-center gap-3">{saved ? <><button type="button" disabled={busy} onClick={() => download.mutate(saved)} className={buttonClass.primary}><Download size={16} />Unduh ulang XLSX</button><Link to={`/result?category=${kind}&process_id=${processId}&generation=${saved.generation}&radius_meters=${saved.radius_meters}`} className="text-xs font-semibold underline">Lihat hasil tersimpan</Link></> : plan.selected_count === 0 ? <button type="button" disabled={busy} onClick={() => download.mutate({ generation: plan.generation, radius_meters: plan.result_radius_meters })} className={buttonClass.primary}><Download size={16} />Ekspor pilihan tersimpan dalam radius</button> : <button type="button" disabled={busy || save.error?.status === 409} onClick={() => save.mutate(plan)} className={buttonClass.primary}><Download size={16} />Simpan seluruh pasangan otomatis &amp; ekspor</button>}<Link to={mapUrl} className="text-xs font-semibold underline">Buka Peta Koreksi</Link></div>
      {!saved && plan.selected_count === 0 && <p className="text-xs text-ui-muted">Tidak ada pilihan baru untuk disimpan. Ekspor menggunakan pilihan aktif dalam radius hasil {count(plan.result_radius_meters)} m.</p>}
    </>}
  </section>;
}
