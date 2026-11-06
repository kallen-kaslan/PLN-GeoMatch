import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { LoaderCircle, Lock, User } from "lucide-react";
import { useAppStore } from "@/store/app";
import type { ApiError } from "@/lib/api";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, authStatus, authNotice } = useAppStore();
  const navigate = useNavigate();
  const location = useLocation();
  const from = typeof location.state?.from === "string" && location.state.from.startsWith("/") && !location.state.from.startsWith("//") && !location.state.from.startsWith("/login") ? location.state.from : "/";

  if (authStatus === "authenticated") return <Navigate to={from} replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (loading || authStatus === "checking") return;
    setLoading(true); setError("");
    try {
      await login(username.trim(), password);
      setPassword("");
      navigate(from, { replace: true });
    } catch (err) {
      setError((err as ApiError).message || "Login belum berhasil. Silakan coba lagi.");
      setPassword("");
    } finally { setLoading(false); }
  };

  return <main className="flex min-h-dvh items-center justify-center bg-neo-white px-4 py-8 text-neo-black">
    <div className="w-full max-w-md">
      <header className="mb-6 text-center"><p className="text-sm font-semibold uppercase tracking-widest text-ui-muted">PLN GeoMatch</p><h1 className="mt-3 text-2xl font-semibold">Verifikasi Koordinat Pelanggan</h1></header>
      <section className="geo-panel overflow-hidden">
        <div className="flex items-center gap-3 border-b border-ui-border bg-ui-context px-6 py-5"><Lock size={24} /><div><h2 className="text-xl font-semibold">Masuk</h2><p className="mt-1 text-sm text-ui-muted">Gunakan akun yang diberikan administrator.</p></div></div>
        <form onSubmit={submit} className="space-y-5 p-6 sm:p-8">
          {(authNotice || location.state?.message) && <p role="status" className="text-sm text-green-800">{authNotice || location.state.message}</p>}
          {error && <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
          <fieldset disabled={loading || authStatus === "checking"} className="space-y-5 disabled:opacity-70">
            <label className="block space-y-2 text-sm font-semibold"><span className="flex items-center gap-2"><User size={16} />Username</span><input autoComplete="username" autoCapitalize="none" spellCheck={false} value={username} onChange={(event) => setUsername(event.target.value)} required maxLength={64} className="w-full rounded-lg border border-ui-border bg-white px-3 py-3" /></label>
            <label className="block space-y-2 text-sm font-semibold"><span>Password</span><input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required maxLength={128} className="w-full rounded-lg border border-ui-border bg-white px-3 py-3" /></label>
            <button type="submit" className="flex w-full items-center justify-center gap-2 rounded-lg bg-ui-primary px-4 py-3 font-semibold text-white hover:bg-ui-primary-hover">{(loading || authStatus === "checking") && <LoaderCircle size={18} className="animate-spin" />}{authStatus === "checking" ? "Memeriksa sesi..." : loading ? "Memproses..." : "Masuk"}</button>
          </fieldset>
          <p className="border-t border-ui-border pt-4 text-center text-sm text-ui-muted">Untuk akun baru atau pemulihan akses, hubungi administrator.</p>
        </form>
      </section>
    </div>
  </main>;
}
