import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { authApi } from "@/lib/accounts";
import type { ApiError } from "@/lib/api";
import { buttonClass } from "@/lib/button";
import { useAppStore } from "@/store/app";

export default function PasswordDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close(); }, []);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (password !== confirm) { setError("Konfirmasi password tidak sama."); return; }
    setBusy(true); setError("");
    try {
      await authApi.changePassword(current, password);
      useAppStore.getState().endSession("Password berhasil diubah. Silakan login kembali.");
      navigate("/login", { replace: true, state: { message: "Password berhasil diubah. Silakan login kembali." } });
      onClose();
    } catch (err) { setError((err as ApiError).message); setCurrent(""); }
    finally { setBusy(false); }
  };
  const control = "w-full rounded-lg border border-ui-border bg-white px-3 py-2";
  return <dialog ref={dialog} onCancel={(event) => { if (busy) event.preventDefault(); else onClose(); }} aria-labelledby="password-title" className="fixed inset-0 m-auto w-[calc(100%_-_2rem)] max-w-md rounded-lg border border-ui-border bg-white p-6 backdrop:bg-black/50">
    <form onSubmit={submit} className="space-y-4"><h2 id="password-title" className="text-lg font-semibold">Ubah password</h2><fieldset disabled={busy} className="space-y-4">
      <label className="block space-y-1 text-sm">Password saat ini<input type="password" required autoComplete="current-password" maxLength={128} value={current} onChange={(event) => setCurrent(event.target.value)} className={control} /></label>
      <label className="block space-y-1 text-sm">Password baru<input type="password" required autoComplete="new-password" minLength={15} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} className={control} /></label>
      <label className="block space-y-1 text-sm">Konfirmasi password baru<input type="password" required autoComplete="new-password" minLength={15} maxLength={128} value={confirm} onChange={(event) => setConfirm(event.target.value)} className={control} /></label>
      <p className="text-xs text-ui-muted">Gunakan passphrase 15–128 karakter. Semua sesi akan dicabut setelah password diubah.</p>
      <div className="flex gap-2"><button type="submit" className={buttonClass.primary}>{busy ? "Menyimpan..." : "Simpan password"}</button><button type="button" onClick={onClose} className={buttonClass.secondary}>Batal</button></div>
    </fieldset>{error && <p role="alert" className="text-sm text-red-700">{error}</p>}</form>
  </dialog>;
}
