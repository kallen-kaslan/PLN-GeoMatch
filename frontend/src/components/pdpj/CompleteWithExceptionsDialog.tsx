import { buttonClass } from "@/lib/button";
import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import type { ApiError } from "@/lib/api";
import { pdpjApi, type PdpjCompletion, type PdpjSummary } from "@/lib/pdpj";

const control = "w-full rounded-sm border-2 border-neo-border bg-white px-3 py-2 text-sm disabled:opacity-50";
const button = buttonClass.secondary;

export function CompleteWithExceptionsDialog({ review, actor, onActorChange, onClose, onCompleted, onPendingChange }: {
  review: PdpjSummary; actor: string; onActorChange: (value: string) => void;
  onClose: () => void; onCompleted: (result: PdpjCompletion) => void;
  onPendingChange?: (pending: boolean) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const amount = review.summary.unresolved.toLocaleString("id-ID");
  const partial = !!review.processing && review.processing.state !== "ready";
  const mutation = useMutation<PdpjCompletion, ApiError | Error>({
    mutationFn: () => pdpjApi.completeWithExceptions(review.id, {
      revision: review.revision, actor: actor.trim(), reason: reason.trim(),
      expected_unresolved: review.summary.unresolved, confirmed: true,
    }),
    onSuccess: onCompleted,
    onMutate: () => { onPendingChange?.(true); },
    onSettled: () => { onPendingChange?.(false); },
  });
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  return <dialog ref={dialog} aria-labelledby="pdpj-bulk-title" onCancel={(event) => {
    if (mutation.isPending) event.preventDefault(); else onClose();
  }} className="fixed inset-0 m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-xl overflow-y-auto rounded-sm border-2 border-neo-border bg-white p-5 text-neo-black shadow-xl backdrop:bg-black/50 sm:p-6">
    <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (confirmed && actor.trim() && reason.trim()) mutation.mutate(); }}>
      <h2 id="pdpj-bulk-title" className="text-lg font-black">Lanjutkan dengan pengecualian massal</h2>
      <p className="text-sm"><strong>{amount} baris bermasalah</strong> akan dicatat sebagai pengecualian dengan alasan yang sama. {partial ? "Versi data yang sudah tersimpan akan disetujui untuk koreksi. Pemrosesan PDPJ sisanya tetap bisa dilanjutkan." : "Pemeriksaan kemudian diselesaikan agar dapat digunakan pada Data Koreksi dan Peta Koreksi."}</p>
      <p className="rounded-sm border border-amber-600 bg-amber-50 p-3 text-xs text-amber-950">Masalah dan data asli tetap tersimpan. Pengecualian tetap ditandai untuk tindak lanjut. IDPEL PDPJ tetap dilindungi dari penggunaan ulang sebagai kandidat koreksi. {partial ? "Versi yang disetujui tetap tersimpan saat PDPJ dilanjutkan dari posisi terakhir." : "Pemeriksaan selesai dikunci; peninjauan berikutnya memakai Periksa ulang PDPJ."}</p>
      <label className="block space-y-1.5 text-xs font-bold">Petugas penanggung jawab<input required maxLength={80} value={actor} onChange={(event) => onActorChange(event.target.value)} disabled={mutation.isPending} className={control} /></label>
      <label className="block space-y-1.5 text-xs font-bold">Alasan pengecualian massal<textarea required maxLength={1000} rows={3} value={reason} onChange={(event) => setReason(event.target.value)} disabled={mutation.isPending} className={control} /></label>
      <label className="flex items-start gap-2 text-xs"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} disabled={mutation.isPending} className="mt-0.5 size-4 shrink-0 accent-neo-accent" /><span>Saya menyetujui pengecualian untuk seluruh {amount} baris bermasalah pada pemeriksaan ini.</span></label>
      {(!actor.trim() || !reason.trim() || !confirmed) && <p className="text-xs text-amber-900">Isi nama petugas, alasan, dan centang persetujuan untuk mengaktifkan tombol simpan.</p>}
      {mutation.error && <p role="alert" className="rounded-sm border border-red-600 bg-red-50 p-3 text-sm text-red-700">{mutation.error.message}</p>}
      <div className="flex flex-wrap justify-end gap-2 border-t border-gray-300 pt-4">
        <button type="button" onClick={onClose} disabled={mutation.isPending} className={button}>Batal</button>
        <button type="submit" disabled={mutation.isPending || !confirmed || !actor.trim() || !reason.trim()} className={buttonClass.warning}>{mutation.isPending && <LoaderCircle size={16} className="animate-spin" />}{mutation.isPending ? "Menyimpan pengecualian…" : "Simpan pengecualian dan lanjutkan"}</button>
      </div>
    </form>
  </dialog>;
}
