import { buttonClass } from "@/lib/button";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, LoaderCircle, X } from "lucide-react";
import type { ApiError } from "@/lib/api";
import { displayValue, masterFieldLabel, validationMessage } from "@/lib/master";
import { PDPJ_FIELDS, existenceLabel, pdpjApi, type Fields, type PdpjDetail, type PdpjSummary, type Recommendation } from "@/lib/pdpj";

const control = "w-full rounded-sm border-2 border-neo-border bg-white px-3 py-2 text-sm disabled:opacity-50";
const button = buttonClass.secondary;
const empty = (value: unknown) => value === null || value === undefined || value === "" || value === "-";
const historyLabel: Record<string, string> = { manual: "Pengisian manual", recommendation: "Pelengkapan dari rekomendasi", reviewed: "Disetujui petugas", exception: "Pengecualian kelengkapan", reopen: "Dibuka untuk ditinjau", finalized: "Disetujui saat penyelesaian", carried_forward: "Dibawa dari pemeriksaan sebelumnya" };

function HistorySources({ sources }: { sources: Record<string, unknown> }) {
  if (sources.bulk) return <p className="mt-2 text-neo-border">Keputusan pengecualian massal untuk {Number(sources.affected_rows ?? 0).toLocaleString("id-ID")} baris bermasalah pada pemeriksaan ini.</p>;
  if (sources.previous_review_id) return <p className="mt-2 text-neo-border">Nilai dibawa dari pemeriksaan #{String(sources.previous_review_id)}. Riwayat lengkapnya tetap tersedia pada versi tersebut.</p>;
  return <dl className="mt-3 space-y-2 border-t border-gray-200 pt-2">{Object.entries(sources).map(([field, value]) => {
    const source = value as { manual?: boolean; filename?: string; row_number?: number; period?: string | null; source_sheet?: string | null };
    return <div key={field}><dt className="font-bold">Sumber {masterFieldLabel(field)}</dt><dd className="mt-1 break-words">{source.manual ? "Pengisian manual oleh petugas" : `${source.filename ?? "Berkas master"} · Baris ${source.row_number ?? "—"} · Periode ${displayValue(source.period)}${source.source_sheet ? ` · Sheet ${source.source_sheet}` : ""}`}</dd></div>;
  })}</dl>;
}

function RecommendationCard({ item, record, disabled, onApply }: { item: Recommendation; record: PdpjDetail; disabled: boolean; onApply: (fields: string[], overwrite: boolean) => void }) {
  const available = PDPJ_FIELDS.filter((field) => !empty(item.fields[field.key]) && !item.validation_errors.some((error) => error.field === field.key));
  const [selected, setSelected] = useState<string[]>(available.filter((field) => empty(record.fields[field.key])).map((field) => field.key));
  const [overwrite, setOverwrite] = useState(false);
  const conflict = selected.some((key) => !empty(record.fields[key]) && record.fields[key] !== item.fields[key]);
  return <article className={`space-y-3 rounded-sm border-2 p-4 ${item.current ? "border-neo-border bg-white" : "border-gray-300 bg-gray-50"}`}>
    <div><h4 className="break-words text-sm font-black">{item.provenance.filename}</h4><p className="mt-1 text-xs text-neo-border">{item.provenance.dataset_type.toUpperCase()} · Baris {item.provenance.row_number} · Periode {displayValue(item.provenance.period)}{item.provenance.source_sheet ? ` · Sheet ${item.provenance.source_sheet}` : ""}</p></div>
    {!item.current && <p className="text-xs font-bold text-amber-800">Riwayat rekomendasi untuk IDPEL sebelumnya. Tidak dapat diterapkan ke IDPEL saat ini.</p>}
    <fieldset disabled={disabled || !item.current} className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
      {available.map((field) => <label key={field.key} className="flex min-w-0 items-start gap-2 rounded-sm border border-gray-200 p-2 text-xs"><input type="checkbox" checked={selected.includes(field.key)} onChange={(event) => setSelected((previous) => event.target.checked ? [...previous, field.key] : previous.filter((key) => key !== field.key))} aria-label={`Pilih ${field.label} dari rekomendasi ${item.id}`} className="mt-0.5 size-4 shrink-0 accent-neo-accent" /><span className="min-w-0"><span className="block font-bold text-neo-border">{field.label}</span><span className="mt-1 block break-words">{displayValue(item.fields[field.key])}</span></span></label>)}
    </fieldset>
    {!!item.validation_errors.length && <p className="text-xs text-red-700">Sebagian nilai sumber tidak valid: {item.validation_errors.map((error) => masterFieldLabel(error.field)).join(", ")}. Nilai tersebut tidak dapat dipilih.</p>}
    {item.current && <div className="flex flex-col gap-3 border-t border-gray-200 pt-3 sm:items-start">{conflict && <label className="flex items-start gap-2 text-xs font-semibold text-amber-900"><input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} disabled={disabled} className="size-4 accent-neo-accent" />Saya menyetujui penggantian nilai terisi pada kolom yang dipilih. Isi alasan perubahan di atas.</label>}
      <button type="button" disabled={disabled || !selected.length || (conflict && !overwrite)} onClick={() => onApply(selected, overwrite)} className={buttonClass.primary}>Terapkan kolom pilihan</button>
    </div>}
  </article>;
}

function DetailEditor({ record, review, actor }: { record: PdpjDetail; review: PdpjSummary; actor: string }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [manual, setManual] = useState<Record<string, string>>(() => Object.fromEntries(PDPJ_FIELDS.map((field) => [field.key, empty(record.fields[field.key]) ? "" : String(record.fields[field.key])])));
  const mutation = useMutation<unknown, ApiError | Error, { type: "manual" } | { type: "apply"; item: Recommendation; fields: string[]; overwrite: boolean } | { type: "decision"; action: "reviewed" | "exception" | "reopen" }>({
    mutationFn: async (request) => {
      if (!actor.trim()) throw new Error("Isi nama petugas untuk riwayat terlebih dahulu.");
      const common = { revision: review.revision, actor: actor.trim(), reason };
      if (request.type === "apply") return pdpjApi.apply(review.id, record.id, { ...common, recommendation_id: request.item.id, fields: request.fields, overwrite: request.overwrite });
      if (request.type === "decision") return pdpjApi.decide(review.id, record.id, { ...common, action: request.action });
      const fields: Fields = {};
      for (const field of PDPJ_FIELDS) {
        const value = manual[field.key].trim();
        const previous = empty(record.fields[field.key]) ? "" : String(record.fields[field.key]);
        if (value !== previous) fields[field.key] = value || null;
      }
      if (!Object.keys(fields).length) throw new Error("Belum ada nilai manual yang berubah.");
      return pdpjApi.edit(review.id, record.id, { ...common, fields });
    },
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["pdpj"] }); },
  });
  const disabled = review.status === "completed" || mutation.isPending;
  return <div className="space-y-5">
    <div className="flex flex-wrap gap-2 text-xs font-bold"><span className="rounded-sm border border-neo-border bg-white px-3 py-2">{existenceLabel[record.existence]}</span><span className={`rounded-sm border px-3 py-2 ${record.coordinates_complete ? "border-green-600 bg-green-50 text-green-800" : "border-amber-600 bg-amber-50 text-amber-900"}`}>{record.coordinates_complete ? "Koordinat lengkap" : "Koordinat belum lengkap"}</span>{record.exception && <span className="rounded-sm border border-amber-600 bg-amber-50 px-3 py-2 text-amber-900">Pengecualian: {record.exception_reason}</span>}</div>
    {!!record.issues.length && <ul className="list-disc space-y-1 rounded-sm border border-amber-600 bg-amber-50 py-3 pr-3 pl-7 text-xs text-amber-900">{record.issues.map((error, index) => <li key={index}>{masterFieldLabel(error.field)}: {validationMessage(error.code)}</li>)}</ul>}
    <section><h3 className="mb-2 text-sm font-black">Data awal dan data saat ini</h3><p className="mb-3 break-words text-xs text-neo-border">{record.filename} · Baris {record.row_number}{record.source_sheet ? ` · Sheet ${record.source_sheet}` : ""}</p><div className="overflow-x-auto rounded-sm border border-neo-border"><table className="w-full min-w-[440px] text-left text-xs"><thead className="bg-gray-100"><tr><th className="p-2">Kolom</th><th className="p-2">Data awal</th><th className="p-2">Saat ini</th></tr></thead><tbody>{PDPJ_FIELDS.filter((field) => ["idpel", "nama", "lat", "lon"].includes(field.key) || !empty(record.original_fields[field.key]) || !empty(record.fields[field.key])).map((field) => <tr key={field.key} className="border-t border-gray-200"><th className="p-2 font-semibold">{field.label}</th><td className="max-w-64 break-words p-2">{displayValue(record.original_fields[field.key])}</td><td className={`max-w-64 break-words p-2 ${record.original_fields[field.key] !== record.fields[field.key] ? "bg-green-50 font-bold" : ""}`}>{displayValue(record.fields[field.key])}</td></tr>)}</tbody></table></div></section>
    {review.status !== "completed" && <div className="space-y-3 rounded-sm border border-neo-border bg-neo-white p-4"><label className="block space-y-1.5 text-xs font-bold">Alasan perubahan / pengecualian<textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={1000} disabled={disabled} rows={2} className={control} /></label><p className="text-xs text-neo-border">Alasan wajib untuk mengganti nilai terisi atau memberi pengecualian. Setiap aksi dicatat atas nama petugas di bagian atas halaman.</p>
      <div className="flex flex-wrap gap-2"><button type="button" onClick={() => mutation.mutate({ type: "decision", action: "reviewed" })} disabled={disabled || !!record.issues.length || !actor.trim()} className={buttonClass.success}><CheckCircle2 size={15} />Setujui baris</button>{record.exception ? <button type="button" disabled={disabled || !actor.trim()} onClick={() => mutation.mutate({ type: "decision", action: "reopen" })} className={button}>Batalkan pengecualian</button> : <button type="button" disabled={disabled || !reason.trim() || !actor.trim()} onClick={() => mutation.mutate({ type: "decision", action: "exception" })} className={buttonClass.warning}>Simpan pengecualian kelengkapan</button>}</div></div>}
    {mutation.error && <p role="alert" className="rounded-sm border-2 border-red-600 bg-red-50 p-3 text-sm text-red-700">{mutation.error.message} <button type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ["pdpj"] })} className="font-bold underline">Muat ulang pemeriksaan</button></p>}
    <section className="space-y-3"><h3 className="text-sm font-black">Rekomendasi dari seluruh sumber ({record.recommendations_total})</h3><p className="text-xs text-neo-border">Pilih kolom yang ingin dilengkapi dari setiap sumber. Kolom kosong dipilih otomatis bila sumber memiliki nilai yang valid.</p>{record.recommendations.length ? record.recommendations.map((item) => <RecommendationCard key={`${item.id}-${review.revision}`} item={item} record={record} disabled={disabled || !actor.trim()} onApply={(fields, overwrite) => mutation.mutate({ type: "apply", item, fields, overwrite })} />) : <p className="rounded-sm border border-gray-300 bg-gray-50 p-4 text-xs">Belum ada rekomendasi untuk IDPEL ini. Periksa IDPEL atau lengkapi data secara manual.</p>}</section>
    <details className="rounded-sm border-2 border-neo-border bg-white p-4"><summary className="cursor-pointer text-sm font-black">Isi atau perbaiki data secara manual</summary><fieldset disabled={disabled} className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{PDPJ_FIELDS.map((field) => <label key={field.key} className="space-y-1 text-xs font-bold">{field.label}<input aria-label={`Manual ${field.label}`} type="text" value={manual[field.key]} onChange={(event) => setManual((previous) => ({ ...previous, [field.key]: event.target.value }))} className={control} /></label>)}</fieldset><button type="button" disabled={disabled || !actor.trim()} onClick={() => mutation.mutate({ type: "manual" })} className={`${buttonClass.primary} mt-4`}>Simpan perubahan manual</button></details>
    <details className="rounded-sm border border-neo-border bg-white p-4"><summary className="cursor-pointer text-sm font-black">Data asli berkas PDPJ</summary><dl className="mt-3 divide-y divide-gray-200">{Object.entries(record.raw_data).map(([key, value]) => <div key={key} className="grid grid-cols-2 gap-3 py-2 text-xs"><dt className="break-words font-bold">{key}</dt><dd className="break-words font-mono">{displayValue(value)}</dd></div>)}</dl></details>
    <section><h3 className="mb-3 text-sm font-black">Riwayat perubahan dan keputusan</h3>{record.history.length ? <ol className="space-y-3">{record.history.map((change) => <li key={change.id} className="rounded-sm border border-gray-300 bg-white p-3 text-xs"><p className="font-bold">{historyLabel[change.action] ?? change.action} · {change.actor}</p><p className="mt-1 text-neo-border">{new Date(`${change.created_at}Z`).toLocaleString("id-ID")}</p>{change.reason && <p className="mt-2">{change.reason}</p>}<details className="mt-2"><summary className="cursor-pointer font-semibold">Lihat perubahan dan sumber</summary><dl className="mt-2 space-y-2">{PDPJ_FIELDS.filter((field) => change.before.fields[field.key] !== change.after.fields[field.key]).map((field) => <div key={field.key}><dt className="font-bold">{field.label}</dt><dd className="mt-1 break-words">{displayValue(change.before.fields[field.key])} → {displayValue(change.after.fields[field.key])}</dd></div>)}</dl>{Object.keys(change.sources).length > 0 && <HistorySources sources={change.sources} />}</details></li>)}</ol> : <p className="text-xs text-neo-border">Belum ada perubahan pada baris ini.</p>}</section>
  </div>;
}

export function PdpjRowDetail({ review, rowId, actor, onClose }: { review: PdpjSummary; rowId: number; actor: string; onClose: () => void }) {
  const [offset, setOffset] = useState(0);
  const section = useRef<HTMLElement>(null);
  useEffect(() => { section.current?.scrollIntoView({ block: "start" }); }, [rowId]);
  const detail = useQuery({ queryKey: ["pdpj", review.id, "row", rowId, review.revision, offset], queryFn: () => pdpjApi.detail(review.id, rowId, offset) });
  return <section ref={section} aria-label="Detail pemeriksaan PDPJ" className="scroll-mt-20 space-y-5 rounded-sm border-2 border-neo-border bg-white p-4 shadow-[3px_3px_0_#0a0a0a] sm:p-6"><header className="flex items-start justify-between gap-3 border-b border-neo-border pb-3"><div><h2 className="text-base font-black">Detail PDPJ · Baris {detail.data?.row_number ?? "…"}</h2><p className="mt-1 text-xs text-neo-border">Pelengkapan, rekomendasi sumber, dan riwayat pemeriksaan.</p></div><button type="button" onClick={onClose} aria-label="Tutup detail PDPJ" className={button}><X size={18} /></button></header>
    {detail.isPending && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Memuat detail PDPJ…</p>}{detail.isError && <p role="alert" className="flex gap-2 text-sm text-red-700"><AlertCircle size={16} />Detail tidak dapat dimuat. <button type="button" onClick={() => void detail.refetch()} className="font-bold underline">Coba lagi</button></p>}
    {detail.data && <><DetailEditor key={`${rowId}-${review.revision}-${offset}`} record={detail.data} review={review} actor={actor} />{detail.data.recommendations_total > 10 && <div className="flex flex-wrap items-center justify-between gap-3 text-xs"><p>Rekomendasi {offset + 1}–{Math.min(offset + 10, detail.data.recommendations_total)} dari {detail.data.recommendations_total}</p><div className="flex gap-2"><button type="button" disabled={offset === 0} onClick={() => setOffset((previous) => previous - 10)} className={button}>Sumber sebelumnya</button><button type="button" disabled={offset + 10 >= detail.data.recommendations_total} onClick={() => setOffset((previous) => previous + 10)} className={button}>Sumber berikutnya</button></div></div>}</>}
  </section>;
}
