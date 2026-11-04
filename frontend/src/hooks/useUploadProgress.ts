import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { uploadFilesApi } from "@/lib/upload-files";

export interface ImportActivity {
  id?: string;
  mode: "preview" | "validation";
  filename: string;
  phase: string;
  processed: number;
  total: number | null;
  unit: "bytes" | "rows";
  startedAt: number;
  phaseStartedAt: number;
  status: "running" | "paused" | "completed" | "failed";
  pauseRequested: boolean;
  pausedAt: number | null;
  phasePausedMs: number;
}

export interface LocalImportControl { pause: () => void; resume: () => void }

export function useUploadProgress() {
  const [activity, setActivity] = useState<ImportActivity | null>(null);
  const [controlBusy, setControlBusy] = useState(false);
  const [controlError, setControlError] = useState<string | null>(null);
  const pauseRequested = useRef(false);
  const localControl = useRef<LocalImportControl | null>(null);
  const waiting = useRef<(() => void)[]>([]);
  const server = useQuery({
    queryKey: ["upload-progress", activity?.id],
    queryFn: ({ signal }) => uploadFilesApi.progress(activity!.id!, signal),
    enabled: !!activity?.id && (activity.status === "running" || activity.status === "paused") && activity.phase !== "preview",
    refetchInterval: 500,
    retry: 1,
  });
  const begin = async (mode: ImportActivity["mode"], filename: string, phase: string, total: number | null = null) => {
    const now = Date.now();
    pauseRequested.current = false;
    localControl.current = null;
    setControlError(null);
    setActivity({ mode, filename, phase, processed: 0, total, unit: phase === "uploading" ? "bytes" : "rows", startedAt: now, phaseStartedAt: now, status: "running", pauseRequested: false, pausedAt: null, phasePausedMs: 0 });
    const snapshot = await uploadFilesApi.createProgress();
    setActivity((current) => current ? { ...current, id: snapshot.id } : current);
    return snapshot.id;
  };
  const stage = (phase: string, total: number | null = null, unit: ImportActivity["unit"] = "rows") => {
    setActivity((current) => current ? { ...current, phase, processed: 0, total, unit, phaseStartedAt: Date.now(), phasePausedMs: 0 } : current);
  };
  const update = (processed: number, total?: number) => setActivity((current) => current ? { ...current, processed, total: total ?? current.total } : current);
  const finish = (status: "completed" | "failed") => setActivity((current) => current ? { ...current, status } : current);
  const localPaused = (paused: boolean) => {
    const now = Date.now();
    setActivity((current) => current ? { ...current, status: paused ? "paused" : "running", pausedAt: paused ? current.pausedAt ?? now : null, phasePausedMs: !paused && current.pausedAt ? current.phasePausedMs + now - current.pausedAt : current.phasePausedMs } : current);
  };
  const registerLocal = (control: LocalImportControl | null) => {
    localControl.current = control;
    if (pauseRequested.current) control?.pause();
  };
  const waitForResume = async () => {
    if (!pauseRequested.current) return;
    localPaused(true);
    await new Promise<void>((resolve) => waiting.current.push(resolve));
  };
  const togglePause = async () => {
    if (!activity?.id || controlBusy) return;
    setControlBusy(true);
    setControlError(null);
    const resume = pauseRequested.current;
    try {
      if (resume) await uploadFilesApi.resume(activity.id);
      else await uploadFilesApi.pause(activity.id);
      pauseRequested.current = !resume;
      setActivity((current) => current ? { ...current, pauseRequested: !resume } : current);
      if (resume) {
        localControl.current?.resume();
        localPaused(false);
        waiting.current.splice(0).forEach((resolve) => resolve());
      } else localControl.current?.pause();
      void server.refetch();
    } catch (error) {
      setControlError((error as { message?: string }).message ?? "Perintah jeda belum dapat dikirim. Coba lagi.");
    } finally { setControlBusy(false); }
  };
  return { activity, server, begin, stage, update, finish, togglePause, controlBusy, controlError, registerLocal, localPaused, waitForResume };
}
