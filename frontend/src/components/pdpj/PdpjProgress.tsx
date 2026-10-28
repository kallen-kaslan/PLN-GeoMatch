import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle, Pause, Play } from "lucide-react";
import { buttonClass } from "@/lib/button";
import type { ApiError } from "@/lib/api";
import { pdpjApi, type PdpjReview, type PdpjSummary } from "@/lib/pdpj";
import { useProcessMonitor } from "@/hooks/useProcessMonitor";
import { newestCheckpoint, progressLabel, progressPercent } from "@/lib/progress";

const revision = (value: PdpjReview) => value.revision;
const count = (value: number) => value.toLocaleString("id-ID");
const duration = (seconds: number) => `${Math.floor(seconds / 60)} menit ${Math.floor(seconds % 60)} detik`;

export function PdpjProgress({ review, autoStart, saving = false, onBusyChange }: { review: PdpjSummary; autoStart: boolean; saving?: boolean; onBusyChange?: (busy: boolean) => void }) {
  const queryClient = useQueryClient();
  const generation = useRef(0);
  const activeRequest = useRef<Promise<PdpjReview> | null>(null);
  const [working, setWorking] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState("");
  const [waiting, setWaiting] = useState({ revision: 0, seconds: 0 });
  const [live, setLive] = useState<PdpjReview | null>(null);
  const checkpoint = newestCheckpoint<PdpjReview>(review, live ?? review, revision);
  const progress = checkpoint.processing;
  const serverActive = checkpoint.activity?.active === true;
  const serverSaving = serverActive && checkpoint.activity?.operation === "publishing";
  const busy = working || stopping || saving || serverActive;
  const waitingSeconds = waiting.revision === checkpoint.revision ? waiting.seconds : 0;
  useEffect(() => { onBusyChange?.(busy); return () => onBusyChange?.(false); }, [busy, onBusyChange]);
  const { mutateAsync: resume } = useMutation({ mutationFn: pdpjApi.resume, retry: false });
  const { mutateAsync: advance } = useMutation({ mutationFn: (checkpoint: PdpjReview) => pdpjApi.advance(checkpoint.id, checkpoint.revision), retry: false });
  const { mutateAsync: stop } = useMutation({ mutationFn: pdpjApi.pause, retry: false });

  const publish = useCallback(async (result: PdpjReview, refresh = true) => {
    setLive((old) => newestCheckpoint(old, result, revision));
    await queryClient.cancelQueries({ queryKey: ["pdpj", result.id] });
    // A slow response must never replace a newer pause/resume checkpoint.
    queryClient.setQueryData<PdpjSummary>(["pdpj", result.id, "summary"], (old) => old && newestCheckpoint<PdpjReview>(old, result, revision) === result ? { ...old, ...result } : old);
    queryClient.setQueryData<PdpjReview[]>(["pdpj", "reviews", result.batch_id], (old) => old?.map((item) => item.id === result.id && newestCheckpoint(item, result, revision) === result ? result : item));
    if (refresh) void queryClient.invalidateQueries({ queryKey: ["pdpj", result.id] });
  }, [queryClient]);

  const monitor = useProcessMonitor({ queryKey: ["process-monitor", "pdpj", review.id], queryFn: () => pdpjApi.progress(review.id),
    checkpoint, revision, enabled: !!progress && (checkpoint.status !== "completed" || serverActive), publish });

  const run = useCallback(async () => {
    const token = ++generation.current;
    setWorking(true); setError("");
    try {
      activeRequest.current = resume(review.id);
      let checkpoint = await activeRequest.current;
      await publish(checkpoint);
      while (generation.current === token && checkpoint.processing?.state === "running") {
        try {
          activeRequest.current = advance(checkpoint);
          checkpoint = await activeRequest.current;
        } catch (cause) {
          if ((cause as ApiError).status !== 409) throw cause;
          checkpoint = await pdpjApi.progress(review.id);
          await publish(checkpoint);
          if (checkpoint.activity?.active || checkpoint.processing?.state !== "running") break;
          continue;
        }
        await publish(checkpoint);
      }
    } catch (cause) {
      if (generation.current === token) {
        if ((cause as ApiError).status === 409) {
          try { await publish(await pdpjApi.progress(review.id)); return; } catch { /* Preserve the original error if monitoring also fails. */ }
        }
        setError((cause as ApiError).message ?? "Koneksi terputus. Muat ulang dan lanjutkan dari hasil terakhir yang tersimpan.");
        void queryClient.invalidateQueries({ queryKey: ["pdpj", review.id] });
      }
    } finally {
      if (generation.current === token) setWorking(false);
    }
  }, [publish, queryClient, review.id, resume, advance]);

  useEffect(() => {
    const timer = autoStart ? window.setTimeout(() => void run(), 0) : undefined;
    return () => { window.clearTimeout(timer); generation.current += 1; };
  }, [autoStart, run]);

  useEffect(() => {
    if (!busy) return;
    const started = serverActive && checkpoint.activity?.started_at ? Date.parse(`${checkpoint.activity.started_at}Z`) : Date.now();
    const timer = window.setInterval(() => setWaiting({ revision: checkpoint.revision, seconds: Math.floor((Date.now() - started) / 1000) }), 1000);
    return () => window.clearInterval(timer);
  }, [busy, checkpoint.revision, serverActive, checkpoint.activity?.started_at]);

  const pause = async () => {
    generation.current += 1;
    setWorking(false); setStopping(true); setError("");
    try {
      // Let the active save finish before persisting the stop, including a
      // resume request that was still in flight when the user clicked stop.
      await activeRequest.current?.catch(() => undefined);
      await publish(await stop(review.id));
    }
    catch (cause) { setError((cause as ApiError).message ?? "Status jeda belum dapat dikonfirmasi. Muat ulang untuk memeriksa hasil tersimpan."); }
    finally { setStopping(false); }
  };

  if (!progress) return null;
  const ready = progress.state === "ready";
  const percent = progressPercent(progress.processed_rows, progress.validated_rows, progress.total_rows, ready);
  const stage = serverActive && !checkpoint.activity?.operation && !working && !saving ? "Memproses permintaan di server" : saving || serverSaving ? "Menyimpan hasil validasi yang disetujui" : progress.stage === "matching" ? "Mencocokkan IDPEL dan menyimpan rekomendasi" : progress.stage === "validating" ? "Memvalidasi dan menyimpan hasil akhir" : "Pemeriksaan otomatis selesai";
  return <section aria-label="Progres pemeriksaan PDPJ" aria-busy={busy} className="space-y-3 rounded-sm border-2 border-neo-border bg-white p-4 sm:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="flex items-center gap-2 text-sm font-black">{busy ? <LoaderCircle size={18} className="animate-spin" /> : ready ? <CheckCircle2 size={18} className="text-green-700" /> : <Pause size={18} />}{stage}</h2>
        <p role="status" className="mt-1 text-xs">{saving || serverSaving ? "Menyimpan versi hasil validasi…" : stopping || (serverActive && checkpoint.activity?.operation === "pausing") ? "Menghentikan setelah bagian aktif selesai disimpan…" : serverActive && !checkpoint.activity?.operation ? "Proses berjalan di server" : ready ? checkpoint.status === "completed" ? "Validasi PDPJ telah disetujui dan tersimpan" : "Menunggu tinjauan petugas" : working || serverActive ? "Proses berjalan · hasil disimpan bertahap" : progress.state === "failed" || error ? "Proses terhenti · hasil tersimpan dapat dilanjutkan" : progress.state === "running" ? "Menunggu dilanjutkan dari hasil tersimpan" : "Proses dijeda · siap dilanjutkan"}</p></div>
      {!ready && (working || serverActive ? <button type="button" onClick={() => void pause()} disabled={saving || serverSaving || stopping || checkpoint.activity?.operation === "pausing"} className={buttonClass.secondary}><Pause size={16} />Hentikan sementara</button> : <button type="button" disabled={stopping || saving || monitor.isError} onClick={() => void run()} className={buttonClass.primary}>{stopping || saving ? <LoaderCircle size={16} className="animate-spin" /> : <Play size={16} />}{stopping ? "Menyimpan bagian aktif…" : "Lanjutkan pemeriksaan"}</button>)}
      {!ready && !working && !stopping && !serverActive && progress.state === "running" && <button type="button" onClick={() => void pause()} className={buttonClass.secondary}>Jeda untuk validasi</button>}
    </div>
    <div className="flex items-center gap-3"><progress aria-label="Kemajuan keseluruhan pemeriksaan PDPJ" max={100} value={percent} className="h-3 min-w-0 flex-1 accent-neo-accent" /><span className="text-sm font-black">{progressLabel(percent)}</span></div>
    {busy && <p className="flex animate-pulse items-center gap-2 rounded-sm border border-amber-600 bg-amber-50 p-3 text-xs font-bold text-amber-950"><LoaderCircle size={16} className="animate-spin" />{saving || serverSaving ? "Persetujuan dan versi data sedang disimpan." : progress.stage === "validating" ? "Memeriksa dan menyimpan validasi akhir bagian aktif…" : "Memproses dan menyimpan bagian aktif…"} Angka di bawah menunjukkan hasil yang sudah berhasil disimpan.</p>}
    <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
      <div><dt className="font-bold">Dicocokkan dan tersimpan</dt><dd>{count(progress.processed_rows)} / {count(progress.total_rows)} baris</dd></div>
      <div><dt className="font-bold">Validasi akhir tersimpan</dt><dd aria-live="polite">{count(progress.validated_rows)} / {count(progress.total_rows)} baris</dd>{progress.stage === "matching" && <p className="mt-1 text-neo-border">Dimulai setelah pencocokan seluruh baris selesai.</p>}</div>
      <div><dt className="font-bold">Baris sumber terakhir tersimpan</dt><dd>{progress.last_row_number === null ? "Belum ada" : count(progress.last_row_number)}</dd></div>
      <div><dt className="font-bold">Durasi pemrosesan</dt><dd>{duration(progress.elapsed_seconds)}{busy && waitingSeconds > 0 ? ` · bagian aktif ${duration(waitingSeconds)}` : ""}</dd></div>
    </dl>
    <p className="text-xs text-neo-border">Pembaruan terakhir: {new Date(`${progress.updated_at}Z`).toLocaleString("id-ID")}. {ready ? "Seluruh hasil otomatis telah tersimpan. Tinjau temuan sebelum menyelesaikan validasi." : "Jeda proses untuk meninjau dan menyelesaikan validasi data tersimpan. Versi yang disetujui dapat dipakai untuk koreksi, lalu PDPJ dapat dilanjutkan dari baris terakhir yang tersimpan."}</p>
    {monitor.isError && <p role="alert" className="text-sm text-amber-900">Status server belum dapat dipastikan. Memeriksa ulang sebelum melanjutkan.</p>}
    {(error || progress.error) && <p role="alert" className="text-sm text-red-700">{error || progress.error}</p>}
  </section>;
}
