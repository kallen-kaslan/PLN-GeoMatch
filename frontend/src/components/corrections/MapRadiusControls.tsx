import { useState } from "react";
import { buttonClass } from "@/lib/button";

type Props = { radius: number; maximum: number; recommended: number | null; disabled: boolean; loading: boolean; onApply: (radius: number) => void; onPreview: (radius: string) => void };

export function MapRadiusControls({ radius, maximum, recommended, disabled, loading, onApply, onPreview }: Props) {
  const [draft, setDraft] = useState(String(radius));
  const edit = (value: string) => { setDraft(value); onPreview(value); };
  const minimum = Math.min(1, maximum);
  const value = Number(draft);
  const valid = draft.trim() !== "" && Number.isFinite(value) && value > 0 && value <= maximum;
  const changed = valid && value !== radius;
  const suggested = recommended ?? maximum;
  return <section aria-label="Kontrol radius" className="space-y-4 rounded-lg border border-ui-border bg-white p-4 sm:p-5">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-sm font-semibold">Radius Pencarian</h2><span className="rounded-md bg-ui-accent-soft px-2.5 py-1 text-xs font-medium text-ui-accent-text">{recommended !== null ? "Rekomendasi" : "Radius Tersimpan"}: {suggested.toLocaleString("id-ID")} m</span></div>
    <form noValidate onSubmit={event => { event.preventDefault(); if (valid && !disabled && !loading) onApply(value); }} className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem_auto] sm:items-center">
      <div className="min-w-0"><label htmlFor="map-radius-slider" className="sr-only">Atur radius peta</label><input id="map-radius-slider" type="range" min={minimum} max={maximum} step="any" value={Math.min(maximum, Math.max(minimum, Number.isFinite(value) ? value : minimum))} onChange={event => edit(event.target.value)} disabled={disabled || loading} className="w-full cursor-pointer accent-ui-primary disabled:cursor-not-allowed disabled:opacity-50" /><div className="mt-1 flex justify-between text-xs text-ui-muted"><span>{minimum.toLocaleString("id-ID")} m</span><span>{maximum.toLocaleString("id-ID")} m</span></div></div>
      <label className="flex items-center gap-2"><span className="sr-only">Radius peta (meter)</span><input aria-label="Radius peta (meter)" type="number" inputMode="decimal" min="0.01" max={maximum} step="any" value={draft} onChange={event => edit(event.target.value)} disabled={disabled || loading} aria-invalid={!valid} aria-describedby={!valid ? "map-radius-error" : "map-radius-status"} className="h-10 w-full min-w-0 rounded-md border border-ui-border bg-white px-3 text-sm tabular-nums disabled:opacity-50" /><span className="text-xs text-ui-muted">m</span></label>
      <button type="submit" disabled={!changed || disabled || loading} className={buttonClass.primary}>{loading ? "Memuat Hasil..." : "Terapkan Radius"}</button>
    </form>
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs"><p id="map-radius-status" role="status" className={changed ? "text-amber-800" : "text-ui-muted"}>{changed ? "Perubahan belum diterapkan. Ringkasan mengikuti radius ini. Klik Terapkan Radius untuk memperbarui peta dan tabel." : `Radius aktif ${radius.toLocaleString("id-ID")} m. Ringkasan dan peta mengikuti radius ini.`}</p><button type="button" disabled={disabled || loading || value === suggested} onClick={() => edit(String(suggested))} className="font-medium text-ui-primary-text underline underline-offset-2 disabled:opacity-40">{recommended !== null ? "Gunakan Rekomendasi" : "Reset Radius"}</button></div>
    {!valid && <p id="map-radius-error" role="alert" className="text-xs text-red-700">Radius harus lebih dari 0 dan maksimal {maximum.toLocaleString("id-ID")} meter.</p>}
  </section>;
}
