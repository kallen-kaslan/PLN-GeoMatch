import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Download } from "lucide-react";
import type { AutomaticPreview } from "@/lib/corrections";
import { buttonClass } from "@/lib/button";

const count = (value: number) => value.toLocaleString("id-ID");
export function TieSuggestions({ preview, mapUrl, disabled, onDownload, children }: {
  preview: AutomaticPreview; mapUrl: string; disabled: boolean; onDownload: () => void; children?: ReactNode;
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const filtered = (preview.suggestions ?? []).filter((item) => !search.trim() || item.idpel.includes(search.trim()) || String(item.row_number).includes(search.trim()));
  const pages = Math.max(1, Math.ceil(filtered.length / 20));
  const visible = filtered.slice((Math.min(page, pages) - 1) * 20, Math.min(page, pages) * 20);
  const unpairedLabels: Record<string, string> = { no_available_idpel: "Tidak memiliki IDPEL bebas dalam radius", shared_candidates: "Belum mendapat pasangan setelah perebutan kandidat", outside_radius: "Di luar radius", no_candidates: "Tanpa kandidat", pdpj_conflict: "Benturan PDPJ", invalid_data: "Data perlu diperbaiki", incomplete_coordinates: "Koordinat belum lengkap", candidates_used: "Kandidat sudah digunakan", equal_distance: "Jarak sama, perlu ditinjau" };
  return <section aria-label="Usulan pasangan jarak sama" className="space-y-4 rounded-lg border border-amber-600 bg-amber-50 p-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-sm font-semibold">Usulan pasangan untuk jarak sama: {count(preview.suggestion_count ?? 0)} target</h3><p className="mt-2 text-xs">Satu IDPEL untuk satu target. Pilihan tersimpan dan {count(preview.selected_count)} pilihan otomatis tanpa ambiguitas tetap dipertahankan. Pasangan pada jarak yang sama disusun bersama, kemudian kandidat berikutnya dipertimbangkan untuk target yang tersisa.</p></div><button type="button" disabled={disabled || !preview.suggestion_count} onClick={onDownload} className={buttonClass.secondary}><Download size={16} />Unduh Usulan XLSX</button></div>
    <p className="text-sm font-semibold text-amber-950">Perlu verifikasi identitas. Usulan disimpan sebagai pilihan setelah diverifikasi melalui peta atau tinjauan kelompok. Berkas usulan memuat label Perlu verifikasi.</p>
    <p className="text-xs">{count(preview.suggestion_count ?? 0)} target memiliki usulan · {count(preview.unpaired_count ?? 0)} target belum mendapat pasangan.</p>
    {Object.entries(preview.unpaired_reasons ?? {}).length > 0 && <ul className="list-inside list-disc space-y-1 text-xs">{Object.entries(preview.unpaired_reasons ?? {}).map(([reason, total]) => <li key={reason}>{unpairedLabels[reason] ?? reason}: {count(total)} target</li>)}</ul>}
    {children}
    <label className="flex flex-col gap-1.5 text-xs font-semibold">Cari usulan berdasarkan IDPEL atau baris<input aria-label="Cari usulan IDPEL atau baris" type="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} className="rounded-lg border border-ui-border bg-white px-3 py-2 text-sm" /></label>
    <div className="overflow-x-auto rounded-lg border border-ui-border bg-white"><table className="w-full min-w-[650px] text-left text-xs"><thead className="bg-ui-table-head"><tr>{["Baris target", "IDPEL usulan", "Jarak", "Status", "Tinjauan"].map((label) => <th key={label} className="p-3">{label}</th>)}</tr></thead><tbody>{visible.length ? visible.map((item) => <tr key={item.record_id} className="border-t border-ui-border"><td className="p-3">{item.row_number}</td><td className="p-3 font-mono font-semibold">{item.idpel}</td><td className="p-3">{item.distance_meters.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m</td><td className="p-3 font-semibold text-amber-950">Perlu verifikasi</td><td className="p-3"><Link to={`${mapUrl}&record_id=${item.record_id}&suggested_candidate_id=${item.candidate_id}&map_view=detail`} className="font-semibold underline">Verifikasi usulan baris {item.row_number}</Link></td></tr>) : <tr><td colSpan={5} className="p-6 text-center">Tidak ada usulan sesuai filter.</td></tr>}</tbody></table></div>
    <div className="flex flex-wrap items-center justify-between gap-3 text-xs"><p>{count(filtered.length)} usulan · Halaman {Math.min(page, pages)} dari {pages}</p><div className="flex gap-2"><button type="button" disabled={disabled || page <= 1} onClick={() => setPage(page - 1)} className={buttonClass.secondary}>Usulan sebelumnya</button><button type="button" disabled={disabled || page >= pages} onClick={() => setPage(page + 1)} className={buttonClass.secondary}>Usulan berikutnya</button></div></div>
  </section>;
}
