import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle, Pause, Play } from "lucide-react";
import type { ApiError } from "@/lib/api";
import { buttonClass } from "@/lib/button";
import { correctionApi, type CorrectionCheck, type CorrectionRun } from "@/lib/corrections";
import type { CorrectionKind } from "@/lib/master";
import { useProcessMonitor } from "@/hooks/useProcessMonitor";
import { newestCheckpoint, progressLabel, progressPercent } from "@/lib/progress";

const revision = (value: CorrectionRun) => value.processing?.revision ?? 0;
const count = (value: number) => value.toLocaleString("id-ID");

export function CorrectionProgress({ kind, check, autoStart, onStarted, onBusyChange }: {
  kind: CorrectionKind; check: CorrectionCheck; autoStart: boolean; onStarted: (runId: number) => void; onBusyChange?: (busy: boolean) => void;
}) {
  const client = useQueryClient();
  const generation = useRef(0);
  const request = useRef<Promise<CorrectionRun> | null>(null);
  const lastResultsRefresh = useRef(0);
  const resultsRefreshTimer = useRef<number | undefined>(undefined);
  const [live, setLive] = useState<CorrectionRun | null>(null);
  const [working, setWorking] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState("");
  const [waiting, setWaiting] = useState({ revision: 0, seconds: 0 });
  const runId = check.latest_run.id;
  const run = newestCheckpoint(check.latest_run, live?.id === runId ? live : check.latest_run, revision);
  const progress = run.processing;
  const { mutateAsync: resume } = useMutation({ mutationFn: () => correctionApi.resume(kind, check.process_id, runId), retry: false });
  const { mutateAsync: advance } = useMutation({ mutationFn: (value: CorrectionRun) => correctionApi.advance(kind, check.process_id, value), retry: false });
  const { mutateAsync: stop } = useMutation({ mutationFn: () => correctionApi.pause(kind, check.process_id, runId), retry: false });
  const publish = useCallback(async (result: CorrectionRun, refresh = true) => {
    setLive((old) => newestCheckpoint(old, result, revision));
    const key = ["corrections", kind, "check", check.process_id];
    client.setQueryData<CorrectionCheck>(key, (old) => old && old.latest_run.id === result.id && newestCheckpoint(old.latest_run, result, revision) === result ? {
      ...old, status: result.status, latest_run: result,
      current_generation: result.status === "completed" ? result.generation : old.current_generation,
      runs: old.runs.map((item) => item.id === result.id ? result : item),
    } : old);
    if (refresh) {
      const force = result.status === "completed" || result.processing?.state !== "running";
      const refreshResults = () => {
        resultsRefreshTimer.current = undefined;
        lastResultsRefresh.current = Date.now();
        if (result.status === "completed") {
          void client.invalidateQueries({ queryKey: ["corrections", kind] });
        } else {
          void client.invalidateQueries({ queryKey: key }, { cancelRefetch: force });
          for (const section of ["rows", "summary", "detail"]) {
            void client.invalidateQueries({ queryKey: ["corrections", kind, section] }, { cancelRefetch: force });
          }
        }
      };
      const remaining = 3000 - (Date.now() - lastResultsRefresh.current);
      if (force || remaining <= 0) {
        window.clearTimeout(resultsRefreshTimer.current);
        refreshResults();
      } else if (resultsRefreshTimer.current === undefined) {
        resultsRefreshTimer.current = window.setTimeout(refreshResults, remaining);
      }
    }
  }, [client, kind, check.process_id]);
  useEffect(() => () => window.clearTimeout(resultsRefreshTimer.current), []);
  const serverActive = run.activity?.active === true;
  const monitor = useProcessMonitor({ queryKey: ["process-monitor", "correction", check.process_id, runId],
    queryFn: () => correctionApi.progress(kind, check.process_id), checkpoint: run, revision,
    enabled: !!progress && (progress.state !== "ready" || serverActive), publish });
  const start = useCallback(async () => {
    const token = ++generation.current;
    setWorking(true); setError(""); onStarted(runId);
    try {
      request.current = resume();
      let checkpoint = await request.current;
      await publish(checkpoint);
      while (generation.current === token && checkpoint.processing?.state === "running") {
        try {
          request.current = advance(checkpoint);
          checkpoint = await request.current;
        } catch (cause) {
          if ((cause as ApiError).status !== 409) throw cause;
          checkpoint = await correctionApi.progress(kind, check.process_id);
          await publish(checkpoint);
          if (checkpoint.activity?.active || checkpoint.processing?.state !== "running") break;
          continue;
        }
        await publish(checkpoint);
      }
    } catch (cause) {
      if (generation.current === token) {
        if ((cause as ApiError).status === 409) {
          try { await publish(await correctionApi.progress(kind, check.process_id)); return; } catch { /* Preserve the original error if monitoring also fails. */ }
        }
        setError((cause as ApiError).message ?? "Proses terputus. Lanjutkan dari hasil tersimpan.");
        void client.invalidateQueries({ queryKey: ["corrections", kind, "check", check.process_id] });
      }
    } finally { if (generation.current === token) setWorking(false); }
  }, [resume, advance, publish, onStarted, runId, client, kind, check.process_id]);
  useEffect(() => {
    const timer = autoStart ? window.setTimeout(() => void start(), 0) : undefined;
    return () => { window.clearTimeout(timer); generation.current += 1; };
  }, [autoStart, start]);
  const busy = working || stopping || serverActive;
  useEffect(() => { onBusyChange?.(busy); return () => onBusyChange?.(false); }, [busy, onBusyChange]);
  useEffect(() => {
    if (!busy) return;
    const started = serverActive && run.activity?.started_at ? Date.parse(`${run.activity.started_at}Z`) : Date.now();
    const revision = progress?.revision ?? 0;
    const timer = window.setInterval(() => setWaiting({ revision, seconds: Math.floor((Date.now() - started) / 1000) }), 1000);
    return () => window.clearInterval(timer);
  }, [busy, progress?.revision, serverActive, run.activity?.started_at]);
  const pause = async () => {
    generation.current += 1; setWorking(false); setStopping(true); setError("");
    try { await request.current?.catch(() => undefined); await publish(await stop()); }
    catch (cause) { setError((cause as ApiError).message ?? "Status jeda belum dapat dikonfirmasi. Muat ulang pemeriksaan."); }
    finally { setStopping(false); }
  };
  if (!progress) return null;
  const ready = progress.state === "ready";
  const preparation = progress.preparation;
  const percent = progressPercent(progress.processed_rows, progress.validated_rows, progress.total_rows, ready,
    preparation?.reused ? 0 : preparation?.work_done ?? 0, preparation?.reused ? 0 : preparation?.work_total ?? 0);
  const stages = { preparing: "Menyiapkan master dan pengecualian PDPJ", matching: "Memeriksa benturan dan menyimpan kandidat", validating: "Memvalidasi hasil dan bukti kandidat tersimpan", publishing: "Menyimpan penyelesaian pemeriksaan", done: "Pemeriksaan koreksi selesai" };
  const preparationStages = { reading: "Membaca master dan menyimpan identitas", reserving: "Mencadangkan IDPEL PDPJ", materializing: "Menyimpan master gabungan dan master sisa", ready: "Persiapan master selesai" };
  const stageLabel = progress.stage === "preparing" && preparation ? preparationStages[preparation.phase] : stages[progress.stage];
  const seconds = Math.floor(progress.elapsed_seconds) + (busy && waiting.revision === progress.revision ? waiting.seconds : 0);
  return <section aria-label="Progres pemeriksaan koreksi" aria-busy={busy} className="space-y-3 rounded-sm border-2 border-neo-border bg-white p-4 sm:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="flex items-center gap-2 text-sm font-black">{busy ? <LoaderCircle size={18} className="animate-spin" /> : ready ? <CheckCircle2 size={18} className="text-green-700" /> : <Pause size={18} />}{stageLabel}</h2><p role="status" className="mt-1 text-xs">{stopping || (serverActive && run.activity?.operation === "pausing") ? "Menghentikan setelah bagian aktif tersimpan…" : ready ? "Seluruh hasil dan validasi akhir telah tersimpan" : working || serverActive ? "Pemeriksaan berjalan · hasil disimpan bertahap" : progress.state === "failed" || error ? "Proses terhenti · hasil tersimpan dapat dilanjutkan" : progress.state === "running" ? "Menunggu dilanjutkan dari hasil tersimpan" : "Proses dijeda · siap dilanjutkan"}</p></div>
      {!ready && (working || serverActive ? <button type="button" onClick={() => void pause()} disabled={stopping || run.activity?.operation === "pausing"} className={buttonClass.secondary}><Pause size={16} />Hentikan sementara koreksi</button> : <button type="button" disabled={stopping || monitor.isError} onClick={() => void start()} className={buttonClass.primary}>{stopping ? <LoaderCircle size={16} className="animate-spin" /> : <Play size={16} />}{stopping ? "Menyimpan bagian aktif…" : "Lanjutkan pemeriksaan koreksi"}</button>)}
    </div>
    <div className="flex items-center gap-3"><progress aria-label="Kemajuan keseluruhan pemeriksaan koreksi" value={percent} max={100} className="h-3 min-w-0 flex-1 accent-neo-accent" /><span className="text-sm font-black">{progressLabel(percent)}</span></div>
    {preparation && <div aria-label="Progres persiapan master" className="space-y-3 rounded-sm border border-blue-700 bg-blue-50 p-3 text-xs text-blue-950"><p className="font-black">{preparation.reused ? "Snapshot master yang sesuai digunakan kembali" : preparationStages[preparation.phase]}</p>{preparation.source_total !== undefined && <><dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><div><dt className="font-bold">Baris master dibaca dan tersimpan</dt><dd aria-live="polite">{count(preparation.source_rows ?? 0)} / {count(preparation.source_total)} baris</dd></div><div><dt className="font-bold">IDPEL unik ditemukan</dt><dd>{count(preparation.unique_rows ?? 0)}</dd></div><div><dt className="font-bold">Normalisasi tersimpan dipakai ulang</dt><dd>{count(preparation.cached_rows ?? 0)} baris</dd></div><div><dt className="font-bold">Baris PDPJ diperiksa untuk pengecualian</dt><dd>{count(preparation.pdpj_rows ?? 0)} / {count(preparation.pdpj_total ?? 0)} baris</dd></div><div><dt className="font-bold">Master gabungan tersimpan</dt><dd>{count(preparation.materialized_rows ?? 0)} / {count(preparation.unique_rows ?? 0)} baris</dd></div><div><dt className="font-bold">Master sisa tersedia</dt><dd>{count(preparation.eligible_rows ?? 0)} baris · {count(preparation.excluded_rows ?? 0)} dikecualikan</dd></div></dl>{preparation.phase === "reading" && <p className="break-words">Berkas {Math.min((preparation.file_index ?? 0) + 1, preparation.file_count ?? 0)} / {preparation.file_count}: {preparation.current_file}</p>}</>}<p>Persentase mencakup baris persiapan master, pemeriksaan koreksi, dan validasi akhir. Data persiapan disimpan per bagian dan dapat dilanjutkan.</p></div>}
    {busy && <p className="flex animate-pulse items-center gap-2 rounded-sm border border-amber-600 bg-amber-50 p-3 text-xs font-bold text-amber-950"><LoaderCircle size={16} className="animate-spin" />{progress.stage === "preparing" ? "Menyiapkan sumber master yang dipilih…" : progress.stage === "validating" ? "Memeriksa dan menyimpan validasi akhir bagian aktif…" : "Memproses dan menyimpan bagian aktif…"} Angka berikut menunjukkan hasil yang sudah tersimpan.</p>}
    <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4"><div><dt className="font-bold">Baris koreksi tersimpan</dt><dd aria-live="polite">{count(progress.processed_rows)} / {count(progress.total_rows)} baris</dd></div><div><dt className="font-bold">Validasi akhir tersimpan</dt><dd aria-live="polite">{count(progress.validated_rows)} / {count(progress.total_rows)} baris</dd>{["preparing", "matching"].includes(progress.stage) && <p className="mt-1 text-neo-border">Dimulai setelah pemeriksaan seluruh baris selesai.</p>}</div><div><dt className="font-bold">Baris sumber terakhir tersimpan</dt><dd>{progress.last_row_number === null ? "Belum ada" : count(progress.last_row_number)}</dd></div><div><dt className="font-bold">Durasi pemrosesan</dt><dd>{Math.floor(seconds / 60)} menit {seconds % 60} detik</dd></div></dl>
    <p className="text-xs text-neo-border">Pembaruan terakhir: {new Date(`${progress.updated_at}Z`).toLocaleString("id-ID")}. {ready ? "Hasil pemeriksaan ini siap ditinjau." : "Kandidat dan bukti disimpan per bagian. Setelah halaman ditutup atau koneksi terputus, lanjutkan pemeriksaan yang sama dari posisi tersimpan. Tabel tetap menampilkan versi hasil yang telah selesai."}</p>
    {monitor.isError && <p role="alert" className="text-sm text-amber-900">Status server belum dapat dipastikan. Memeriksa ulang sebelum melanjutkan.</p>}
    {(error || progress.error) && <p role="alert" className="text-sm text-red-700">{error || progress.error}</p>}
  </section>;
}
