import { ArrowLeft, ArrowRight, Check, Clock3, LoaderCircle, Pause, Play } from "lucide-react";
import type { FlowDocument } from "./CorrectionFlowLayout";
import { validRadius } from "@/lib/radius-analysis";
import { previewButton } from "@/lib/empty-correction-preview";

type State = "idle" | "running" | "pausing" | "paused" | "failed" | "finished";
export interface ProcessView {
  state: State; processed: number; total: number; elapsed: number; actionDisabled: boolean;
  preparation?: { phase: string; work_done: number; work_total: number };
  finalizing?: boolean;
}
const count = (value: number) => value.toLocaleString("id-ID");
const duration = (milliseconds: number) => {
  const seconds = Math.floor(milliseconds / 1000);
  return [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60].map((part) => String(part).padStart(2, "0")).join(":");
};

function Progress({ process, label }: { process: ProcessView; label: string }) {
  const { processed, total, elapsed, state, preparation } = process;
  const percent = total ? Math.min(100, Math.floor(processed / total * 100)) : state === "finished" ? 100 : 0;
  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span className="text-gray-600"><strong className="font-semibold tabular-nums text-gray-900">{count(processed)}</strong> dari {count(total)} baris selesai</span><span className="font-semibold tabular-nums">{percent}%</span></div>
    <div role="progressbar" aria-label={label} aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} className="h-2 overflow-hidden rounded-full bg-gray-100"><div style={{ width: `${percent}%` }} className={`h-full rounded-full ${state === "finished" ? "bg-green-700" : state === "paused" || state === "pausing" ? "bg-gray-400" : "bg-gray-900"}`} /></div>
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500"><span className="inline-flex items-center gap-1.5"><Clock3 size={14} />Waktu proses <span className="font-medium tabular-nums">{duration(elapsed)}</span></span><span>{count(Math.max(0, total - processed))} baris tersisa</span></div>
    {preparation && state !== "finished" && <p role="status" className="text-xs text-gray-500">Menyiapkan master dan indeks koordinat{preparation.work_total > 0 ? `: ${count(preparation.work_done)} dari ${count(preparation.work_total)} tahap data` : "…"}</p>}
  </div>;
}

function ProcessButton({ process, onClick, disabled, kind }: { process: ProcessView; onClick: () => void; disabled?: boolean; kind: "analisis" | "pencarian" }) {
  const { state } = process;
  if (state === "finished") return <p role="status" className="flex min-h-11 items-center gap-2 text-sm font-medium text-green-700"><Check size={16} />{kind === "analisis" ? "Analisis selesai" : "Pencarian selesai"}</p>;
  const label = state === "pausing" ? "Menjeda…" : state === "running" ? `Jeda ${kind}` : state === "paused" || state === "failed" ? `Lanjutkan ${kind}` : kind === "analisis" ? "Mulai analisis" : "Mulai pencarian kandidat";
  return <button type="button" disabled={disabled || process.actionDisabled || state === "pausing"} onClick={onClick} className={state === "running" || state === "pausing" ? previewButton.secondary : previewButton.primary}>{state === "pausing" ? <LoaderCircle size={16} className="animate-spin" /> : state === "running" ? <Pause size={16} /> : <Play size={16} />}{label}</button>;
}

export function EmptyCandidatePanel({ document, analysis, search, recommendation, recommendationComplete, outsideLimit, categoryIssues, radius, onRadius, coverage, coverageLoading, error, found, noCandidates, coordinateIssues, otherIssues, onAnalysisAction, onSearchAction, onBack, onResults }: {
  document: FlowDocument; analysis: ProcessView; search: ProcessView;
  recommendation: number | null; recommendationComplete: boolean; outsideLimit: number; categoryIssues: number;
  radius: string; onRadius: (value: string) => void;
  coverage: { found: number; outside: number; invalid: number } | null;
  coverageLoading: boolean; error?: string; found: number; noCandidates: number;
  coordinateIssues: number; otherIssues: number;
  onAnalysisAction: () => void; onSearchAction: () => void; onBack: () => void; onResults: () => void;
}) {
  const analysisReady = analysis.state === "finished";
  const radiusValid = validRadius(radius);
  const searchStarted = search.state !== "idle";
  const finished = search.state === "finished";
  const pausing = analysis.state === "pausing" || search.state === "pausing";
  const results = [["Kandidat ditemukan", found], ["Tanpa kandidat", noCandidates], ["Belum diproses", Math.max(0, search.total - search.processed)], ["Koordinat bermasalah", coordinateIssues]] as const;
  const coverageRows = [["Memiliki kandidat", coverage?.found], ["Tanpa kandidat dalam radius", coverage?.outside], ["Koordinat bermasalah", coverage?.invalid]] as const;
  return <div className="space-y-5"><section aria-label="Cari kandidat" className="overflow-hidden rounded-lg border border-gray-200 bg-white">
    {pausing && <div role="status" className="fixed right-4 top-5 z-50 flex max-w-[calc(100vw-2rem)] items-start gap-3 rounded-lg border border-gray-200 bg-white p-4 text-sm shadow-lg sm:w-80"><LoaderCircle size={18} className="mt-0.5 shrink-0 animate-spin text-gray-600" /><div><p className="font-semibold text-gray-900">Permintaan jeda diterima</p><p className="mt-1 text-xs leading-relaxed text-gray-500">Menyelesaikan data yang sedang diproses.</p></div></div>}
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 px-5 py-4 sm:px-7">
      <div className="min-w-0"><p className="break-words text-sm font-semibold text-gray-900">{document.filename ?? "Data IDPEL Kosong"}</p>{document.sheet && <p className="mt-1 text-xs text-gray-500">{document.sheet}</p>}</div>
      <p className="text-sm text-gray-600">Total <strong className="ml-1 text-gray-900">{count(analysis.total)} baris</strong></p>
    </header>
    {error && <p role="alert" className="mx-5 mt-5 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800 sm:mx-7">{error}</p>}
    <div className="divide-y divide-gray-200 px-5 sm:px-7">
      <section aria-labelledby="radius-analysis" className="space-y-5 py-6 sm:py-7">
        <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 id="radius-analysis" className="text-lg font-semibold text-gray-900">Analisis radius</h2><p className="mt-2 text-sm text-gray-500">Cari radius agar setiap koordinat valid memiliki kandidat.</p></div><ProcessButton process={analysis} onClick={onAnalysisAction} kind="analisis" /></div>
        <Progress process={analysis} label="Progres analisis radius" />
        {(analysis.state === "paused" || analysis.state === "pausing") && <p role="status" className="text-xs text-gray-500">{analysis.state === "pausing" ? "Menyelesaikan data aktif sebelum jeda…" : "Analisis belum berjalan. Lanjutkan dari posisi terakhir."}</p>}
      </section>
      <section aria-labelledby="radius-settings" className="space-y-5 py-6 sm:py-7">
        <div><h2 id="radius-settings" className="text-lg font-semibold text-gray-900">Atur radius</h2><p className="mt-2 text-sm text-gray-500">Gunakan rekomendasi atau masukkan radius sendiri.</p></div>
        <div className="grid items-start gap-6 md:grid-cols-2 md:gap-8">
          <div className="space-y-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm"><span className="text-gray-600">Rekomendasi radius{analysisReady && recommendation != null && !recommendationComplete ? " (cakupan sebagian)" : ""}</span><strong className="font-semibold tabular-nums text-gray-900">{analysisReady ? recommendation != null ? `${count(recommendation)} meter` : "Tidak tersedia" : "Menunggu analisis"}</strong></div>
            <div><label htmlFor="candidate-radius" className="block text-sm font-medium text-gray-800">Radius pencarian</label><div className="relative mt-2"><input id="candidate-radius" type="number" min="0.01" max="100000" step="any" value={radius} placeholder="Masukkan radius" disabled={!analysisReady || searchStarted || search.actionDisabled} onChange={(event) => onRadius(event.target.value)} aria-invalid={analysisReady && !radiusValid} aria-describedby="candidate-radius-help" className="min-h-12 w-full rounded-md border border-gray-300 bg-white py-3 pl-4 pr-20 text-base tabular-nums focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900 disabled:bg-gray-50 disabled:text-gray-500" /><span className="pointer-events-none absolute right-4 top-3 text-sm text-gray-500">meter</span></div><div className="mt-2 flex flex-wrap items-center justify-between gap-2"><p id="candidate-radius-help" className="text-xs text-gray-500">Rekomendasi dibulatkan ke kelipatan 5 meter.</p><button type="button" disabled={!analysisReady || searchStarted || recommendation == null || search.actionDisabled} onClick={() => { if (recommendation != null) onRadius(String(recommendation)); }} className="min-h-9 text-xs font-semibold text-gray-700 underline underline-offset-4 disabled:cursor-not-allowed disabled:text-gray-400">Gunakan rekomendasi</button></div>{analysisReady && !radiusValid && <p role="alert" className="mt-2 text-xs text-red-700">Isi radius lebih dari 0 hingga 100.000 meter.</p>}</div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50/60 p-5"><h3 className="text-sm font-semibold text-gray-900">Perkiraan cakupan</h3><dl aria-busy={coverageLoading} className="mt-4 divide-y divide-gray-200/70 text-sm">{coverageRows.map(([label, value]) => <div key={label} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"><dt className="text-gray-600">{label}</dt><dd className="font-semibold tabular-nums text-gray-900">{value == null || coverageLoading ? "—" : count(value)}</dd></div>)}</dl>{coverageLoading && <p role="status" className="mt-3 text-xs text-gray-500">Menghitung cakupan…</p>}</div>
        </div>
        {analysisReady && outsideLimit > 0 && <p className="text-sm text-amber-800">{count(outsideLimit)} baris belum memiliki kandidat sampai batas pencarian 100.000 meter. Rekomendasi belum mencakup seluruh koordinat valid.</p>}
        {categoryIssues > 0 && <p className="text-sm text-amber-800">{count(categoryIssues)} baris memiliki IDPEL terisi dan tidak sesuai kategori IDPEL Kosong.</p>}
        {!searchStarted && <ProcessButton process={search} onClick={onSearchAction} disabled={!analysisReady || !radiusValid} kind="pencarian" />}
      </section>
      <section aria-labelledby="candidate-search" className="space-y-5 py-6 sm:py-7">
        <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 id="candidate-search" className="text-lg font-semibold text-gray-900">Pencarian kandidat</h2>{searchStarted && <p className="mt-2 text-sm text-gray-500">{finished ? "Seluruh baris selesai diproses." : search.state === "pausing" ? "Menyelesaikan baris aktif sebelum jeda…" : search.state === "paused" ? "Pencarian belum berjalan. Hasil terakhir tetap tersedia." : search.finalizing ? "Memeriksa kelengkapan hasil tersimpan…" : `Radius pencarian: ${count(Number(radius))} meter.`}</p>}</div>{searchStarted && <ProcessButton process={search} onClick={onSearchAction} kind="pencarian" />}</div>
        <Progress process={search} label="Progres pencarian kandidat" />
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">{results.map(([label, value]) => <div key={label} className="rounded-lg border border-gray-200 px-4 py-4"><dt className="text-xs leading-relaxed text-gray-500">{label}</dt><dd className="mt-2 text-2xl font-semibold tabular-nums text-gray-900">{count(value)}</dd></div>)}</dl>
        {otherIssues > 0 && <p className="text-sm text-amber-800">{count(otherIssues)} baris tidak sesuai kategori dan tidak dapat dicari. Alasannya tersedia pada detail hasil.</p>}
      </section>
    </div>
  </section>
    <nav aria-label="Navigasi tahap" className="flex flex-wrap items-center justify-between gap-3">
      <button type="button" onClick={onBack} className={previewButton.secondary}><ArrowLeft size={16} />Sebelumnya</button>
      <button type="button" disabled={!finished} onClick={onResults} className={previewButton.primary}>Lihat hasil<ArrowRight size={16} /></button>
    </nav>
  </div>;
}
