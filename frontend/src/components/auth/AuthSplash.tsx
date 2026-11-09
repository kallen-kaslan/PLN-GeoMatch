import { PlnLogo } from "./PlnLogo";
import "@/styles/login.css";

export function AuthSplash({ message = "Menyiapkan halaman masuk..." }: { message?: string }) {
  return <main className="auth-splash" aria-label="Memuat PLN GeoMatch">
    <div className="auth-splash-halo" aria-hidden="true" />
    <div className="auth-splash-content">
      <div className="auth-splash-mark"><PlnLogo /></div>
      <p className="auth-splash-name">PLN <span>GeoMatch</span></p>
      <p className="auth-splash-caption">Verifikasi Koordinat Pelanggan</p>
      <div role="status" className="auth-splash-status"><span className="auth-loading-dots" aria-hidden="true"><i /><i /><i /></span><span>{message}</span></div>
    </div>
  </main>;
}
