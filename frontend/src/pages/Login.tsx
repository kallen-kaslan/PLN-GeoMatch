import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, LoaderCircle, LockKeyhole, MapPin, UserRound } from "lucide-react";
import { AuthSplash } from "@/components/auth/AuthSplash";
import { PlnLogo } from "@/components/auth/PlnLogo";
import { useAppStore } from "@/store/app";
import type { ApiError } from "@/lib/api";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [intro, setIntro] = useState(true);
  const { login, authStatus, authNotice } = useAppStore();
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => {
    const delay = 0;
    const timer = window.setTimeout(() => setIntro(false), delay);
    return () => window.clearTimeout(timer);
  }, []);
  const from = typeof location.state?.from === "string" && location.state.from.startsWith("/") && !location.state.from.startsWith("//") && !location.state.from.startsWith("/login") ? location.state.from : "/";
  if (authStatus === "authenticated") return <Navigate to={from} replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (loading || authStatus === "checking") return;
    setLoading(true); setShowPassword(false); setError("");
    try {
      await login(username.trim(), password);
      setPassword("");
      setShowPassword(false);
      navigate(from, { replace: true });
    } catch (err) {
      setError((err as ApiError).message || "Login belum berhasil. Silakan coba lagi.");
      setPassword("");
      setShowPassword(false);
    } finally { setLoading(false); }
  };

  if (intro || authStatus === "checking") return <AuthSplash message={authStatus === "checking" ? "Memeriksa sesi..." : "Menyiapkan halaman masuk..."} />;

  return <main className="auth-page">
    <section className="auth-card" aria-label="Login PLN GeoMatch">
      <div className="auth-brand">
        <svg className="auth-route-map" aria-hidden="true" viewBox="0 0 480 630" fill="none" preserveAspectRatio="xMidYMid slice">
          <circle cx="426" cy="416" r="146" stroke="#8ed8d4" strokeOpacity=".22" />
          <circle cx="426" cy="416" r="205" stroke="#8ed8d4" strokeOpacity=".12" />
          <path d="M-20 540H126L203 463H305L389 379H500" stroke="#80d2cb" strokeOpacity=".45" />
          <path d="M0 563H153L228 488H332L418 402H500" stroke="#b8e5df" strokeWidth="1.5" className="auth-route-flow" />
          <path d="M130 630V558L203 485V397L268 332V248" stroke="#8ed8d4" strokeOpacity=".25" />
          <circle cx="228" cy="488" r="5" fill="#e9dc65" />
          <circle cx="228" cy="488" r="13" stroke="#e9dc65" className="auth-map-pulse" />
          <circle cx="418" cy="402" r="4" fill="#b6e5de" />
          <circle cx="268" cy="332" r="3" fill="#b6e5de" />
        </svg>
        <div className="auth-brand-top"><div className="auth-logo-plate"><PlnLogo /></div><p className="auth-brand-owner"><strong>PT PLN (Persero)</strong>Data pelanggan &amp; koordinat</p></div>
        <div className="auth-brand-copy"><p className="auth-eyebrow">Verifikasi Koordinat Pelanggan</p><h1>PLN <span>GeoMatch</span></h1><p className="auth-brand-description">Kelola data pelanggan, temukan pasangan yang sesuai, dan tinjau hasil koreksi dalam satu ruang kerja.</p></div>
        <p className="auth-brand-bottom"><MapPin size={15} aria-hidden="true" />Data pelanggan · Peta koreksi · Rekonsiliasi</p>
      </div>
      <div className="auth-form-panel">
        <header><p className="auth-eyebrow">Selamat datang kembali</p><h2>Masuk</h2><p className="auth-form-intro">Gunakan akun yang diberikan administrator untuk mengakses ruang kerja Anda.</p></header>
        <form onSubmit={submit} className="auth-form" aria-label="Form login">
          {(authNotice || location.state?.message) && <p role="status" className="auth-notice">{authNotice || location.state.message}</p>}
          {error && <p role="alert" className="auth-error">{error}</p>}
          <fieldset disabled={loading}>
            <div className="auth-field"><label htmlFor="login-username">Username</label><div className="auth-input-wrap"><UserRound size={17} className="auth-input-icon" aria-hidden="true" /><input id="login-username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} value={username} onChange={(event) => setUsername(event.target.value)} required maxLength={64} placeholder="Masukkan username" /></div></div>
            <div className="auth-field"><label htmlFor="login-password">Password</label><div className="auth-input-wrap"><LockKeyhole size={17} className="auth-input-icon" aria-hidden="true" /><input id="login-password" name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required maxLength={128} placeholder="Masukkan password" className="auth-password-input" /><button type="button" aria-label={showPassword ? "Sembunyikan password" : "Tampilkan password"} aria-pressed={showPassword} aria-controls="login-password" onClick={() => setShowPassword(!showPassword)} className="auth-password-toggle">{showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}</button></div></div>
            <button type="submit" className="auth-submit">{loading ? <><LoaderCircle size={17} className="animate-spin" aria-hidden="true" />Memproses...</> : <>Masuk<ArrowRight size={17} aria-hidden="true" /></>}</button>
          </fieldset>
        </form>
        <p className="auth-help"><strong>Butuh bantuan untuk masuk?</strong>Untuk akun baru atau pemulihan akses, hubungi administrator.</p>
      </div>
    </section>
  </main>;
}
