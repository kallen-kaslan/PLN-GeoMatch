import type { ReactNode } from "react";
import { buttonClass } from "@/lib/button";
import { validRadius, type RadiusAnalysis } from "@/lib/radius-analysis";

const count = (value?: number | null) => value == null ? "—" : value.toLocaleString("id-ID");
const panel = "space-y-5 rounded-sm border border-gray-200 bg-white p-5 sm:p-6";

export function AnalysisStep({ analysis, preview, busy, pauseRequested = false, error, onStart, onPause, onNext, footer }: {
  analysis?: RadiusAnalysis | null; preview: boolean; busy: boolean; pauseRequested?: boolean; error?: string;
  onStart: () => void; onPause: () => void; onNext: () => void; footer?: ReactNode;
}) {
  const ready = analysis?.state === "ready";
  const progress = analysis ? Math.min(100, analysis.processed_rows / Math.max(1, analysis.total_rows) * 100) : 0;
  const status = ready ? "Analisis selesai" : pauseRequested ? "Menunggu bagian aktif selesai…" : busy ? analysis?.stage === "preparing" ? "Menyiapkan data master…" : "Memproses koordinat…" : analysis?.state === "paused" ? "Analisis dijeda" : analysis?.state === "failed" ? "Analisis terhenti" : preview ? "Analisis belum dijalankan dalam pratinjau." : "Klik Mulai analisis untuk memproses koordinat.";
  return <section className={panel}>
    <div><h2 className="text-lg font-bold">Analisis radius</h2><p className="mt-2 text-sm text-gray-600">Koordinat dicocokkan ke master setelah IDPEL yang ada di PDPJ dikecualikan, untuk mencari rekomendasi radius.</p></div>
    <div role="status" className="space-y-3"><p className="text-sm font-semibold">{status}</p>{analysis && <><p className="text-sm text-gray-600">{count(analysis.processed_rows)} dari {count(analysis.total_rows)} baris diproses</p><div role="progressbar" aria-label="Progres analisis radius" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress)} className="h-2 overflow-hidden rounded-full bg-gray-100"><div className="h-full bg-neo-black" style={{ width: `${progress}%` }} /></div></>}</div>
    {ready && <div className="space-y-2 border-t border-gray-200 pt-4"><p className="text-sm">Rekomendasi radius: <strong>{analysis.recommended_radius_meters != null ? `${count(analysis.recommended_radius_meters)} meter` : "Belum tersedia"}</strong></p>{analysis.invalid_rows > 0 && <p className="text-sm text-gray-600">{count(analysis.invalid_rows)} baris dengan koordinat bermasalah tidak ikut dihitung.</p>}{analysis.outside_limit_rows > 0 && <p className="text-sm text-amber-800">{count(analysis.outside_limit_rows)} baris belum memiliki kandidat sampai batas pencarian 100.000 meter.</p>}</div>}
    {(error || analysis?.error) && <p role="alert" className="text-sm text-red-700">{error || analysis?.error}</p>}
    {footer ?? (!preview && <div className="flex flex-wrap gap-3">{busy ? <button type="button" disabled={pauseRequested} onClick={onPause} className={buttonClass.secondary}>Jeda</button> : ready ? <button type="button" onClick={onNext} className={buttonClass.primary}>Lanjut ke atur radius</button> : <button type="button" onClick={onStart} className={buttonClass.primary}>{analysis ? "Lanjutkan analisis" : error ? "Coba lagi" : "Mulai analisis"}</button>}</div>)}
  </section>;
}

export function RadiusStep({ analysis, radius, onRadius, preview, busy, error, onSave, footer }: {
  analysis?: RadiusAnalysis | null; radius: string; onRadius: (value: string) => void;
  preview: boolean; busy: boolean; error?: string; onSave: () => void; footer?: ReactNode;
}) {
  const valid = validRadius(radius);
  const coverage = analysis?.coverage_rows;
  const missing = coverage == null || !analysis ? null : analysis.eligible_rows - coverage;
  return <section className={panel}>
    <div><h2 className="text-lg font-bold">Atur radius</h2><p className="mt-2 text-sm text-gray-600">Gunakan rekomendasi atau isi radius sendiri. Radius ini berlaku untuk data yang baru diunggah.</p></div>
    <div className="flex flex-wrap items-center gap-3 text-sm"><p>Rekomendasi: <strong>{analysis?.recommended_radius_meters != null ? `${count(analysis.recommended_radius_meters)} meter` : "Belum tersedia"}</strong></p>{analysis?.recommended_radius_meters != null && <button type="button" disabled={busy} onClick={() => onRadius(String(analysis.recommended_radius_meters))} className="font-bold underline disabled:opacity-50">Gunakan rekomendasi</button>}</div>
    <div className="max-w-sm"><label htmlFor="empty-radius" className="text-sm font-bold">Radius (meter)</label><input id="empty-radius" type="number" inputMode="decimal" min="0.01" max="100000" step="any" value={radius} disabled={busy} aria-invalid={!!radius && !valid} aria-describedby="empty-radius-help" onChange={(event) => onRadius(event.target.value)} placeholder="Masukkan radius" className="mt-2 w-full rounded-sm border-2 border-neo-border px-3 py-2.5 text-sm disabled:bg-gray-50" /><p id="empty-radius-help" className={`mt-2 text-xs ${radius && !valid ? "text-red-700" : "text-gray-500"}`}>Lebih dari 0 hingga 100.000 meter. Rekomendasi dibulatkan ke atas kelipatan 5 meter.</p></div>
    {valid && coverage != null && <p className="text-sm">{count(coverage)} baris memiliki kandidat dalam radius ini.{missing != null && missing > 0 && <span className="mt-1 block text-amber-800">{count(missing)} baris di luar radius. Anda tetap bisa melanjutkan.</span>}</p>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {footer ?? (!preview && <button type="button" disabled={busy || !valid || analysis?.state !== "ready"} onClick={onSave} className={buttonClass.primary}>Simpan dan lanjutkan</button>)}
  </section>;
}

export function CandidateSearchStep({ radius, preview, busy, created = false, error, onStart, footer }: { radius: string; preview: boolean; busy: boolean; created?: boolean; error?: string; onStart: () => void; footer?: ReactNode }) {
  return <section className={panel}>
    <div><h2 className="text-lg font-bold">Cari kandidat</h2><p className="mt-2 text-sm text-gray-600">Cari dan simpan kandidat dalam radius {validRadius(radius) ? `${count(Number(radius))} meter` : "yang ditentukan"}.</p></div>
    <p role="status" className="text-sm">{preview ? "Pencarian belum dijalankan dalam pratinjau." : busy ? "Menyiapkan pencarian…" : created ? "Pencarian tersimpan dan bisa dilanjutkan." : "Siap memproses data."}</p>
    {footer ?? (!preview && <button type="button" disabled={busy || !validRadius(radius)} onClick={onStart} className={buttonClass.primary}>{created ? "Lanjutkan pencarian" : "Mulai pencarian"}</button>)}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
  </section>;
}
