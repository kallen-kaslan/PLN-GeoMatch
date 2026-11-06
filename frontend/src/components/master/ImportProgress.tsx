import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Circle, LoaderCircle, Pause, Play } from "lucide-react";
import { buttonClass } from "@/lib/button";
import type { ImportActivity } from "@/hooks/useUploadProgress";
import type { UploadProgressSnapshot } from "@/lib/upload-files";

const labels: Record<string, string> = {
  uploading: "Mengirim berkas ke server", "server-file": "Memeriksa dan menyimpan berkas asli",
  inspecting: "Memeriksa struktur berkas", archiving: "Menyalin berkas asli ke penyimpanan",
  registering: "Mencatat berkas dalam riwayat", preview: "Membaca pratinjau dan mendeteksi kolom",
  importing: "Membaca dan menyimpan baris sumber", preparing: "Menyiapkan impor dan akses database",
  reading: "Membaca dan menyimpan baris sumber", saving: "Menyelesaikan penyimpanan baris sumber",
  validating: "Memetakan kolom dan memvalidasi baris", finalizing: "Menyelesaikan penyimpanan hasil validasi",
};
const count = (value: number) => Math.round(value).toLocaleString("id-ID");
const bytes = (value: number) => value >= 1024 * 1024 ? `${(value / 1024 / 1024).toLocaleString("id-ID", { maximumFractionDigits: 1 })} MB` : `${(value / 1024).toLocaleString("id-ID", { maximumFractionDigits: 1 })} KB`;
const duration = (seconds: number) => seconds < 60 ? `${Math.ceil(seconds)} detik` : `${Math.floor(seconds / 60)} menit ${Math.ceil(seconds % 60)} detik`;

export function ImportProgress({ activity, snapshot, disconnected, onTogglePause, controlBusy, controlError }: {
  activity: ImportActivity; snapshot?: UploadProgressSnapshot; disconnected: boolean;
  onTogglePause: () => void; controlBusy: boolean; controlError: string | null;
}) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (activity.status !== "running" && activity.status !== "paused") return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [activity.status]);
  const serverPhase = activity.phase === "server-file" || activity.phase === "importing" || activity.phase === "validating";
  const lostConnection = serverPhase && disconnected;
  const matches = snapshot && snapshot.id === activity.id && snapshot.phase !== "waiting"
    && (activity.phase !== "validating" || ["preparing", "validating", "finalizing"].includes(snapshot.phase));
  const live = serverPhase && matches ? snapshot : undefined;
  const phase = live?.phase ?? activity.phase;
  const processed = live?.processed ?? activity.processed;
  const total = live?.total ?? activity.total;
  const unit = live?.unit ?? activity.unit;
  const running = activity.status === "running" || activity.status === "paused";
  const paused = running && (activity.status === "paused" || live?.status === "paused");
  const resuming = paused && !activity.pauseRequested;
  const failed = activity.status === "failed";
  const phaseNow = paused ? live?.paused_at ? live.paused_at * 1000 : activity.pausedAt ?? now : now;
  const seconds = Math.max(0, (phaseNow - (live ? live.phase_started_at * 1000 : activity.phaseStartedAt + activity.phasePausedMs)) / 1000);
  const rate = seconds > 0 ? processed / seconds : 0;
  const percentage = total && total > 0 ? Math.min(100, processed / total * 100) : null;
  const stale = running && !paused && live && now - live.updated_at * 1000 > 10000;
  const eta = !paused && !activity.pauseRequested && !lostConnection && !stale && total && processed > 0 && processed < total && seconds >= 1 ? (total - processed) / rate : null;
  const steps = activity.mode === "preview" ? ["Kirim berkas", "Simpan berkas asli", "Siapkan pratinjau"] : ["Simpan baris sumber", "Validasi baris", "Simpan hasil"];
  const activeStep = activity.mode === "preview" ? activity.phase === "uploading" ? 0 : activity.phase === "server-file" ? 1 : 2
    : phase === "finalizing" ? 2 : activity.phase === "validating" ? 1 : 0;
  const formatted = (value: number) => unit === "bytes" ? bytes(value) : `${count(value)} baris`;
  return <section aria-label="Progres impor data" aria-busy={running && !paused} className={`space-y-4 rounded-lg border p-4 ${failed ? "border-red-600 bg-red-50" : "border-ui-context-border bg-ui-context"}`}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div className="flex min-w-0 flex-1 items-start gap-3">
      {paused ? <Pause size={22} aria-hidden="true" className="shrink-0 text-amber-800" /> : running ? <LoaderCircle size={22} aria-hidden="true" className="shrink-0 animate-spin text-ui-primary" /> : failed ? <AlertCircle size={22} className="shrink-0 text-red-700" /> : <CheckCircle2 size={22} className="shrink-0 text-green-700" />}
      <div className="min-w-0"><p role="status" className="text-sm font-semibold">{failed ? "Proses terhenti. Silakan coba lagi." : !running ? activity.mode === "preview" ? "Pratinjau siap. Periksa pemetaan kolom, lalu simpan dan validasi." : "Impor selesai. Data sudah disimpan dan divalidasi." : resuming ? "Melanjutkan proses..." : paused ? "Proses dijeda. Klik Lanjutkan untuk meneruskan." : activity.pauseRequested ? "Jeda diminta. Menunggu bagian yang sedang dikerjakan selesai..." : labels[phase] ?? "Menyiapkan proses impor"}</p><p className="mt-1 break-words text-xs text-ui-muted">{activity.filename}</p>{running && activity.pauseRequested && <p className="mt-1 text-xs text-ui-muted">Tahap: {labels[phase] ?? phase}</p>}</div>
    </div>{running && <button type="button" onClick={onTogglePause} disabled={!activity.id || controlBusy || resuming} className={`${buttonClass.secondary} shrink-0`}>
      {controlBusy ? <LoaderCircle size={16} className="animate-spin" /> : activity.pauseRequested ? <Play size={16} /> : <Pause size={16} />}{activity.pauseRequested ? "Lanjutkan" : "Pause"}
    </button>}
    </div>
    {controlError && <p role="alert" className="text-xs text-red-700">{controlError}</p>}
    {running && <p className="text-xs text-ui-muted">Jeda diterapkan setelah pengiriman atau bagian proses saat ini selesai. Biarkan halaman ini terbuka selama proses dijeda.</p>}
    <ol aria-label="Tahapan impor" className="grid gap-2 text-xs sm:grid-cols-3">{steps.map((step, index) => <li key={step} aria-current={running && index === activeStep ? "step" : undefined} className="flex items-center gap-2">
      {index < activeStep || !running && !failed ? <CheckCircle2 size={16} className="shrink-0 text-green-700" /> : index === activeStep ? paused ? <Pause size={16} className="shrink-0" /> : <LoaderCircle size={16} className={running ? "shrink-0 animate-spin" : "shrink-0"} /> : <Circle size={16} className="shrink-0 text-ui-muted" />}<span>{step}</span>
    </li>)}</ol>
    {running && <>
      {percentage !== null ? <div><div className="mb-1 flex justify-between gap-3 text-xs"><span>{formatted(processed)} dari {formatted(total!)}</span><span className="font-semibold">{percentage.toLocaleString("id-ID", { maximumFractionDigits: 1 })}% tahap ini</span></div><progress aria-label="Progres tahap impor" value={processed} max={total!} className="h-2 w-full overflow-hidden rounded-full accent-ui-primary" /></div>
        : <p className="text-xs font-medium">{processed > 0 ? `${formatted(processed)} sudah diproses. ` : ""}{phase === "reading" ? "Total baris diketahui setelah pembacaan sheet selesai." : "Menunggu hasil tahap ini dari proses yang berjalan."}</p>}
      <dl className="grid gap-3 text-xs sm:grid-cols-3">
        <div><dt className="text-ui-muted">Waktu sejak mulai</dt><dd className="mt-1 font-semibold">{duration(Math.max(0, (now - activity.startedAt) / 1000))}</dd></div>
        <div><dt className="text-ui-muted">Kecepatan tahap ini</dt><dd className="mt-1 font-semibold">{paused ? "Dijeda" : rate > 0 && !stale && !lostConnection ? `${unit === "bytes" ? bytes(rate) : `${rate.toLocaleString("id-ID", { maximumFractionDigits: 1 })} baris`}/detik` : "Mengukur..."}</dd></div>
        <div><dt className="text-ui-muted">Estimasi sisa tahap ini</dt><dd className="mt-1 font-semibold">{paused ? "Dijeda" : eta !== null ? `Sekitar ${duration(eta)}` : percentage === 100 ? "Menyelesaikan tahap ini" : "Belum dapat dihitung"}</dd></div>
      </dl>
      <p className="text-xs text-ui-muted">Persentase mengikuti byte terkirim atau baris yang diproses. Estimasi dihitung dari kecepatan aktual dan dapat berubah.</p>
      {(lostConnection || stale) && <p role="status" className="text-xs font-semibold text-amber-900">{lostConnection ? "Pembaruan progres belum tersambung. Mencoba menghubungkan kembali; proses belum dinyatakan selesai." : "Belum ada pembaruan baru dari server. Proses mungkin sedang membaca berkas atau menunggu database."}</p>}
    </>}
  </section>;
}
