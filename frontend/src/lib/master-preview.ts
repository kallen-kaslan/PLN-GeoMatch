import type { SourceKind } from "@/lib/master";
import type { FilePreview } from "@/lib/upload-files";

export function readMasterPreview(file: File, kind: SourceKind, onProgress: (processed: number, total: number) => void, onPaused: (paused: boolean) => void) {
  const worker = new Worker(new URL("./master-preview.worker.ts", import.meta.url), { type: "module" });
  const result = new Promise<{ sheet: string; preview?: FilePreview }>((resolve, reject) => {
    worker.onmessage = (event: MessageEvent<{ type: string; sheet: string; preview?: FilePreview; processed: number; total: number; message: string }>) => {
      if (event.data.type === "progress") {
        onProgress(event.data.processed, event.data.total);
        return;
      }
      if (event.data.type === "paused" || event.data.type === "resumed") {
        onPaused(event.data.type === "paused");
        return;
      }
      worker.terminate();
      if (event.data.type === "error") reject(new Error(event.data.message));
      else resolve({ sheet: event.data.sheet, preview: event.data.preview });
    };
    worker.onerror = () => {
      worker.terminate();
      reject(new Error("Pratinjau tidak dapat dibaca. Silakan pilih ulang berkas."));
    };
    worker.postMessage({ file, kind });
  });
  return { result, pause: () => worker.postMessage({ type: "pause" }), resume: () => worker.postMessage({ type: "resume" }) };
}
