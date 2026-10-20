import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/store/app";
import { User, Lock, Mail, UserPlus } from "lucide-react";

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (mode === "register") {
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
      setError(mode === "login" ? "Login gagal. Coba lagi." : "Registrasi gagal. Coba lagi.");
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setUsername("");
    setEmail("");
    setPassword("");
    setConfirmPassword("");
    setError("");
  };

  const switchMode = (newMode: AuthMode) => {
    setMode(newMode);
    resetForm();
  };

  return (
    <div className="min-h-screen bg-linear-to-br from-neo-accent via-[#f7931e] to-[#fdc830] flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated Background Elements - Cinema Style */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-10 left-10 w-72 h-72 bg-neo-black/10 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-10 right-10 w-96 h-96 bg-white/10 rounded-full blur-3xl animate-pulse delay-700"></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-150 h-150 bg-neo-accent/20 rounded-full blur-3xl animate-pulse delay-1000"></div>
      </div>

      {/* Main Container */}
      <div className="relative z-10 w-full max-w-6xl">
        {/* Top Brand Header */}
        <div className="text-center mb-8">
          <div className="inline-block p-4 bg-neo-black border-4 border-white rounded-lg shadow-[8px_8px_0_rgba(255,255,255,0.3)] mb-4">
            <h1 className="text-4xl md:text-5xl font-black text-white tracking-tight">
              PLN GeoMatch
            </h1>
          </div>
          <p className="text-white text-lg font-bold drop-shadow-lg">
            Sistem Verifikasi Koordinat Pelanggan PLN
          </p>
        </div>

        {/* Dual Card Container */}
        <div className="grid md:grid-cols-2 gap-6 max-w-5xl mx-auto">
          {/* LOGIN CARD */}
          <div
            className={`relative p-8 bg-white border-4 rounded-xl transition-all duration-300 ${
              mode === "login"
                ? "border-neo-black shadow-[12px_12px_0_#0a0a0a] scale-105 z-20"
                : "border-neo-border shadow-[6px_6px_0_#333333] opacity-80 hover:opacity-100 cursor-pointer"
            }`}
            onClick={() => mode !== "login" && switchMode("login")}
          >
            {/* Corner Badge */}
            <div className="absolute -top-3 -right-3 bg-[#16a34a] border-3 border-neo-black px-4 py-1 rounded-full shadow-[4px_4px_0_#0a0a0a]">
              <span className="text-white text-xs font-black">MASUK</span>
            </div>

            <div className="flex items-center gap-3 mb-6">
              <div className="p-3 bg-neo-black rounded-lg border-3 border-neo-black">
                <User className="w-6 h-6 text-white" strokeWidth={3} />
              </div>
              <div>
                <h2 className="text-2xl font-black text-neo-black">Login</h2>
                <p className="text-sm text-[#666] font-semibold">Masuk ke akun Anda</p>
              </div>
            </div>

            {mode === "login" && (
              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <div className="p-3 border-3 border-[#dc2626] bg-[#fee2e2] text-[#dc2626] text-sm font-bold rounded-lg shadow-[4px_4px_0_#dc2626]">
                    ⚠️ {error}
                  </div>
                )}

                <div>
                  <label className="block text-sm font-black mb-2 text-neo-black">Username</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#666]" strokeWidth={2.5} />
                    <input
                      className="w-full border-3 border-neo-black pl-11 pr-4 py-3 rounded-lg font-semibold text-neo-black focus:outline-none focus:ring-4 focus:ring-neo-accent/30 shadow-[4px_4px_0_#0a0a0a] transition-all"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="petugas / admin"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-black mb-2 text-neo-black">Password</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#666]" strokeWidth={2.5} />
                    <input
                      className="w-full border-3 border-neo-black pl-11 pr-4 py-3 rounded-lg font-semibold text-neo-black focus:outline-none focus:ring-4 focus:ring-neo-accent/30 shadow-[4px_4px_0_#0a0a0a] transition-all"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full border-3 border-neo-black bg-neo-black text-white px-6 py-4 rounded-lg font-black text-lg shadow-[6px_6px_0_#ff6b35] hover:shadow-[8px_8px_0_#ff6b35] hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
                >
                  {loading ? "Memproses..." : "🚀 MASUK SEKARANG"}
                </button>
              </form>
            )}

            {mode !== "login" && (
              <div className="text-center py-12">
                <p className="text-[#666] font-semibold mb-4">Sudah punya akun?</p>
                <button
                  onClick={() => switchMode("login")}
                  className="px-6 py-2 border-3 border-neo-black bg-neo-black text-white font-black rounded-lg shadow-[4px_4px_0_#333] hover:shadow-[6px_6px_0_#333] hover:-translate-y-0.5 transition-all"
                >
                  Klik untuk Login
                </button>
              </div>
            )}
          </div>

          {/* REGISTER CARD */}
          <div
            className={`relative p-8 bg-white border-4 rounded-xl transition-all duration-300 ${
              mode === "register"
                ? "border-neo-black shadow-[12px_12px_0_#0a0a0a] scale-105 z-20"
                : "border-neo-border shadow-[6px_6px_0_#333333] opacity-80 hover:opacity-100 cursor-pointer"
            }`}
            onClick={() => mode !== "register" && switchMode("register")}
          >
            {/* Corner Badge */}
            <div className="absolute -top-3 -right-3 bg-[#2563eb] border-3 border-neo-black px-4 py-1 rounded-full shadow-[4px_4px_0_#0a0a0a]">
              <span className="text-white text-xs font-black">DAFTAR</span>
            </div>

            <div className="flex items-center gap-3 mb-6">
              <div className="p-3 bg-neo-accent rounded-lg border-3 border-neo-black">
                <UserPlus className="w-6 h-6 text-white" strokeWidth={3} />
              </div>
              <div>
                <h2 className="text-2xl font-black text-neo-black">Register</h2>
                <p className="text-sm text-[#666] font-semibold">Buat akun baru</p>
              </div>
            </div>

            {mode === "register" && (
              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <div className="p-3 border-3 border-[#dc2626] bg-[#fee2e2] text-[#dc2626] text-sm font-bold rounded-lg shadow-[4px_4px_0_#dc2626]">
                    ⚠️ {error}
                  </div>
                )}

                <div>
                  <label className="block text-sm font-black mb-2 text-neo-black">Username</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#666]" strokeWidth={2.5} />
                    <input
                      className="w-full border-3 border-neo-black pl-11 pr-4 py-3 rounded-lg font-semibold text-neo-black focus:outline-none focus:ring-4 focus:ring-[#2563eb]/30 shadow-[4px_4px_0_#0a0a0a] transition-all"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="pilih username"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-black mb-2 text-neo-black">Email</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#666]" strokeWidth={2.5} />
                    <input
                      className="w-full border-3 border-neo-black pl-11 pr-4 py-3 rounded-lg font-semibold text-neo-black focus:outline-none focus:ring-4 focus:ring-[#2563eb]/30 shadow-[4px_4px_0_#0a0a0a] transition-all"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="email@pln.co.id"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-black mb-2 text-neo-black">Password</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#666]" strokeWidth={2.5} />
                    <input
                      className="w-full border-3 border-neo-black pl-11 pr-4 py-3 rounded-lg font-semibold text-neo-black focus:outline-none focus:ring-4 focus:ring-[#2563eb]/30 shadow-[4px_4px_0_#0a0a0a] transition-all"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="min. 6 karakter"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-black mb-2 text-neo-black">Konfirmasi Password</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#666]" strokeWidth={2.5} />
                    <input
                      className="w-full border-3 border-neo-black pl-11 pr-4 py-3 rounded-lg font-semibold text-neo-black focus:outline-none focus:ring-4 focus:ring-[#2563eb]/30 shadow-[4px_4px_0_#0a0a0a] transition-all"
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="ulangi password"
                      required
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full border-3 border-neo-black bg-neo-accent text-white px-6 py-4 rounded-lg font-black text-lg shadow-[6px_6px_0_#2563eb] hover:shadow-[8px_8px_0_#2563eb] hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
                >
                  {loading ? "Memproses..." : "✨ DAFTAR SEKARANG"}
                </button>
              </form>
            )}

            {mode !== "register" && (
              <div className="text-center py-12">
                <p className="text-[#666] font-semibold mb-4">Belum punya akun?</p>
                <button
                  onClick={() => switchMode("register")}
                  className="px-6 py-2 border-3 border-neo-black bg-neo-accent text-white font-black rounded-lg shadow-[4px_4px_0_#333] hover:shadow-[6px_6px_0_#333] hover:-translate-y-0.5 transition-all"
                >
                  Klik untuk Daftar
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Footer Note */}
        <div className="mt-8 text-center">
          <div className="inline-block p-3 bg-white/90 backdrop-blur border-2 border-neo-black rounded-lg shadow-[4px_4px_0_rgba(0,0,0,0.3)]">
            <p className="text-xs text-neo-black font-bold">
              🔒 Phase 1: Mock Auth (Backend integration Phase 1C+)
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
