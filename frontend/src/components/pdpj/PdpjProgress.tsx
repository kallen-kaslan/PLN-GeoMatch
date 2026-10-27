import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle, Pause, Play } from "lucide-react";
import { buttonClass } from "@/lib/button";
import type { ApiError } from "@/lib/api";
import { pdpjApi, type PdpjReview, type PdpjSummary } from "@/lib/pdpj";

const count = (value: number) => value.toLocaleString("id-ID");
const duration = (seconds: number) => `${Math.floor(seconds / 60)} menit ${Math.floor(seconds % 60)} detik`;

export function PdpjProgress({ review, autoStart }: { review: PdpjSummary; autoStart: boolean }) {
  const queryClient = useQueryClient();
  const generation = useRef(0);
  const activeRequest = useRef<Promise<PdpjReview> | null>(null);
  const [working, setWorking] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState("");
  const [waitingSeconds, setWaitingSeconds] = useState(0);
  const progress = review.processing;
  const { mutateAsync: resume } = useMutation({ mutationFn: pdpjApi.resume, retry: false });
  const { mutateAsync: advance } = useMutation({ mutationFn: (checkpoint: PdpjReview) => pdpjApi.advance(checkpoint.id, checkpoint.revision), retry: false });
  const { mutateAsync: stop } = useMutation({ mutationFn: pdpjApi.pause, retry: false });

  const publish = useCallback(async (result: PdpjReview) => {
    await queryClient.cancelQueries({ queryKey: ["pdpj", result.id] });
    // A slow response must never replace a newer pause/resume checkpoint.
    queryClient.setQueryData<PdpjSummary>(["pdpj", result.id, "summary"], (old) => old && old.revision <= result.revision ? { ...old, ...result } : old);
    queryClient.setQueryData<PdpjReview[]>(["pdpj", "reviews", result.batch_id], (old) => old?.map((item) => item.id === result.id && item.revision <= result.revision ? result : item));
    await queryClient.invalidateQueries({ queryKey: ["pdpj", result.id] });
  }, [queryClient]);

  const run = useCallback(async () => {
    const token = ++generation.current;
    setWorking(true); setError("");
    try {
      activeRequest.current = resume(review.id);
      let checkpoint = await activeRequest.current;
      await publish(checkpoint);
      while (generation.current === token && checkpoint.processing?.state === "running") {
        activeRequest.current = advance(checkpoint);
        checkpoint = await activeRequest.current;
        await publish(checkpoint);
      }
    } catch (cause) {
      if (generation.current === token) {
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
    if (!working) return;
    const started = Date.now();
    const timer = window.setInterval(() => setWaitingSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [working, review.revision]);

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
  const percent = Math.floor(100 * (progress.processed_rows + progress.validated_rows) / Math.max(1, progress.total_rows * 2));
  const stage = progress.stage === "matching" ? "Mencocokkan IDPEL dan menyimpan rekomendasi" : progress.stage === "validating" ? "Memvalidasi hasil seluruh baris" : "Pemeriksaan otomatis selesai";
  return <section aria-label="Progres pemeriksaan PDPJ" className="space-y-3 rounded-sm border-2 border-neo-border bg-white p-4 sm:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="flex items-center gap-2 text-sm font-black">{ready ? <CheckCircle2 size={18} className="text-green-700" /> : working ? <LoaderCircle size={18} className="animate-spin" /> : <Pause size={18} />}{stage}</h2>
        <p role="status" className="mt-1 text-xs">{ready ? "Menunggu tinjauan petugas" : stopping ? "Menghentikan setelah bagian aktif selesai disimpan…" : working ? "Proses berjalan · hasil disimpan bertahap" : progress.state === "failed" || error ? "Proses terhenti · hasil tersimpan dapat dilanjutkan" : "Proses dijeda · siap dilanjutkan"}</p></div>
      {!ready && (working ? <button type="button" onClick={() => void pause()} className={buttonClass.secondary}><Pause size={16} />Hentikan sementara</button> : <button type="button" disabled={stopping} onClick={() => void run()} className={buttonClass.primary}><Play size={16} />{stopping ? "Menyimpan bagian aktif…" : "Lanjutkan pemeriksaan"}</button>)}
    </div>
    <div className="flex items-center gap-3"><progress aria-label="Kemajuan keseluruhan pemeriksaan PDPJ" max={100} value={percent} className="h-3 min-w-0 flex-1 accent-neo-accent" /><span className="text-sm font-black">{percent}%</span></div>
    <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
      <div><dt className="font-bold">Dicocokkan dan tersimpan</dt><dd>{count(progress.processed_rows)} / {count(progress.total_rows)} baris</dd></div>
      <div><dt className="font-bold">Validasi akhir tersimpan</dt><dd>{count(progress.validated_rows)} / {count(progress.total_rows)} baris</dd></div>
      <div><dt className="font-bold">Baris sumber terakhir tersimpan</dt><dd>{progress.last_row_number === null ? "Belum ada" : count(progress.last_row_number)}</dd></div>
      <div><dt className="font-bold">Durasi pemrosesan</dt><dd>{duration(progress.elapsed_seconds)}{working && waitingSeconds > 0 ? ` · bagian aktif ${duration(waitingSeconds)}` : ""}</dd></div>
    </dl>
    <p className="text-xs text-neo-border">Pembaruan terakhir: {new Date(`${progress.updated_at}Z`).toLocaleString("id-ID")}. {ready ? "Seluruh hasil otomatis telah tersimpan. Tinjau temuan sebelum menyelesaikan validasi." : "Hasil di bawah masih parsial. Jika halaman ditutup atau koneksi terputus, buka kembali dan lanjutkan dari baris terakhir yang tersimpan."}</p>
    {(error || progress.error) && <p role="alert" className="text-sm text-red-700">{error || progress.error}</p>}
  </section>;
}
