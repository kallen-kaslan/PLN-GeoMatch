import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/store/app";
import { Lock, Mail, User, UserPlus } from "lucide-react";

type AuthMode = "login" | "register";

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAppStore();
  const isRegister = mode === "register";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (isRegister) {
      if (password !== confirmPassword) {
        setError("Password tidak cocok!");
        return;
      }
      if (password.length < 6) {
        setError("Password minimal 6 karakter!");
        return;
      }
    }

    setLoading(true);
    try {
      // Phase 1 scaffold: mock login/register until backend auth ready
      await login(username, password);
      navigate("/");
    } catch {
      setError(isRegister ? "Registrasi gagal. Coba lagi." : "Login gagal. Coba lagi.");
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (newMode: AuthMode) => {
    setMode(newMode);
    setUsername("");
    setEmail("");
    setPassword("");
    setConfirmPassword("");
    setError("");
  };

  return (
    <main className="min-h-[100dvh] bg-neo-white px-3 sm:px-4 py-6 sm:py-12 flex flex-col items-center justify-center text-neo-black safe-top safe-bottom">
      <div className="w-full max-w-md">
        <header className="mb-6 sm:mb-8 text-center">
          <p className="text-xs sm:text-sm font-bold uppercase tracking-[0.18em] text-neo-border">PLN GeoMatch</p>
          <h1 className="mt-2 sm:mt-3 text-2xl sm:text-3xl font-black tracking-tight">
            Verifikasi Koordinat Pelanggan
          </h1>
        </header>

        <section className="border-2 sm:border-3 border-neo-black bg-white shadow-[4px_4px_0_#0a0a0a] sm:shadow-[6px_6px_0_#0a0a0a]">
          <div className="border-b-2 sm:border-b-3 border-neo-black px-5 py-4 sm:px-8 sm:py-5">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 sm:h-11 sm:w-11 shrink-0 items-center justify-center border-2 border-neo-black bg-neo-black text-white">
                {isRegister ? <UserPlus size={20} aria-hidden="true" /> : <User size={20} aria-hidden="true" />}
              </span>
              <div>
                <h2 className="text-lg sm:text-xl font-black">{isRegister ? "Buat akun" : "Masuk"}</h2>
                <p className="text-xs sm:text-sm text-neo-border">
                  {isRegister ? "Daftarkan akun GeoMatch Anda" : "Masuk ke akun GeoMatch Anda"}
                </p>
              </div>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5 px-5 py-5 sm:px-8 sm:py-8">
            {error && (
              <div role="alert" className="border-2 border-[#dc2626] bg-[#fee2e2] px-3 py-2 text-xs sm:text-sm font-semibold text-[#991b1b]">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="username" className="mb-1.5 block text-xs sm:text-sm font-bold">Username</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neo-border" aria-hidden="true" />
                <input
                  id="username"
                  autoComplete="username"
                  className="mobile-input w-full border-2 border-neo-black bg-white py-2.5 sm:py-3 pl-10 pr-3 text-neo-black placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-neo-accent text-sm"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Username"
                  required
                />
              </div>
            </div>

            {isRegister && (
              <div>
                <label htmlFor="email" className="mb-1.5 block text-xs sm:text-sm font-bold">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neo-border" aria-hidden="true" />
                  <input
                    id="email"
                    autoComplete="email"
                    className="mobile-input w-full border-2 border-neo-black bg-white py-2.5 sm:py-3 pl-10 pr-3 text-neo-black placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-neo-accent text-sm"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="nama@pln.co.id"
                    required
                  />
                </div>
              </div>
            )}

            <div>
              <label htmlFor="password" className="mb-1.5 block text-xs sm:text-sm font-bold">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neo-border" aria-hidden="true" />
                <input
                  id="password"
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  className="mobile-input w-full border-2 border-neo-black bg-white py-2.5 sm:py-3 pl-10 pr-3 text-neo-black placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-neo-accent text-sm"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={isRegister ? "Minimal 6 karakter" : "Password"}
                  required
                />
              </div>
            </div>

            {isRegister && (
              <div>
                <label htmlFor="confirm-password" className="mb-1.5 block text-xs sm:text-sm font-bold">Konfirmasi password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neo-border" aria-hidden="true" />
                  <input
                    id="confirm-password"
                    autoComplete="new-password"
                    className="mobile-input w-full border-2 border-neo-black bg-white py-2.5 sm:py-3 pl-10 pr-3 text-neo-black placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-neo-accent text-sm"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Ulangi password"
                    required
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="touch-min w-full border-2 border-neo-black bg-neo-black px-4 py-3 sm:py-3.5 font-bold text-white shadow-[3px_3px_0_#ff6b35] transition hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[2px_2px_0_#ff6b35] active:translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Memproses..." : isRegister ? "Daftar" : "Masuk"}
            </button>

            <p className="border-t border-neo-border pt-4 sm:pt-5 text-center text-xs sm:text-sm text-neo-border">
              {isRegister ? "Sudah punya akun?" : "Belum punya akun?"}{" "}
              <button
                type="button"
                onClick={() => switchMode(isRegister ? "login" : "register")}
                className="font-bold text-neo-black underline decoration-neo-accent decoration-2 underline-offset-4 hover:text-neo-border focus:outline-none focus:ring-2 focus:ring-neo-accent p-1"
              >
                {isRegister ? "Masuk" : "Daftar sekarang"}
              </button>
            </p>
          </form>
        </section>

        <p className="mt-5 sm:mt-6 text-center text-xs text-neo-border">
          Phase 1 · Autentikasi simulasi
        </p>
      </div>
    </main>
  );
}
