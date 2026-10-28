import { useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/store/app";
import { Eye, EyeOff, Lock, Mail, User, UserPlus } from "lucide-react";

type AuthMode = "login" | "register";

const inputClass =
  "mobile-input w-full border-2 border-neo-black bg-white py-2.5 sm:py-3 pl-10 pr-11 text-sm text-neo-black placeholder:text-gray-500 transition-colors focus:outline-none focus:ring-2 focus:ring-neo-accent focus:ring-offset-0";
const iconClass = "pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-neo-border transition-[color,transform] duration-150";

/** Decorative spatial panel: coordinate grid + route with pulsing nodes. Pure SVG + CSS, no assets. */
function SpatialPanel() {
  return (
    <aside aria-hidden="true" className="relative hidden overflow-hidden bg-[#111111] lg:flex lg:w-[44%] lg:min-w-[420px] lg:flex-col lg:justify-between">
      <svg className="absolute inset-0 h-full w-full text-white/[0.07]" preserveAspectRatio="none">
        {/* Grid koordinat tipis */}
        <defs>
          <pattern id="geo-grid" width="64" height="64" patternUnits="userSpaceOnUse">
            <path d="M64 0H0V64" fill="none" stroke="currentColor" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#geo-grid)" />
      </svg>

      {/* Lintasan dan node — viewBox tetap, posisi proporsional */}
      <svg viewBox="0 0 600 800" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full">
        {/* Pulse ring pada focal point */}
        <circle cx="388" cy="322" r="14" fill="none" stroke="#ff6b35" strokeWidth="1.5" className="geo-pulse-ring" />
        <circle cx="388" cy="322" r="14" fill="none" stroke="#ff6b35" strokeWidth="1" className="geo-pulse-ring geo-pulse-delay" />

        {/* Garis lintasan utama */}
        <polyline points="96,596 188,472 312,506 388,322 502,368" fill="none" stroke="#fafafa" strokeOpacity="0.28" strokeWidth="1.5" strokeLinejoin="round" />
        {/* Cahaya berjalan di sepanjang lintasan */}
        <polyline points="96,596 188,472 312,506 388,322 502,368" fill="none" stroke="#ff6b35" strokeWidth="2" strokeLinecap="round" strokeDasharray="90 520" className="geo-travel" />

        {/* Cabang sekunder, lebih redup */}
        <polyline points="188,472 152,318 246,208" fill="none" stroke="#fafafa" strokeOpacity="0.14" strokeWidth="1" className="geo-breathe" />
        <polyline points="502,368 548,506 468,624" fill="none" stroke="#fafafa" strokeOpacity="0.14" strokeWidth="1" className="geo-breathe geo-breathe-alt" />

        {/* Titik-titik kecil dekoratif */}
        <circle cx="152" cy="318" r="3" fill="#fafafa" fillOpacity="0.35" />
        <circle cx="246" cy="208" r="3" fill="#fafafa" fillOpacity="0.25" className="geo-breathe" />
        <circle cx="548" cy="506" r="3" fill="#fafafa" fillOpacity="0.25" className="geo-breathe geo-breathe-alt" />
        <circle cx="468" cy="624" r="3" fill="#fafafa" fillOpacity="0.35" />

        {/* Node biasa */}
        <circle cx="96" cy="596" r="5" fill="#fafafa" fillOpacity="0.7" />
        <circle cx="188" cy="472" r="5" fill="#fafafa" fillOpacity="0.7" />
        <circle cx="312" cy="506" r="5" fill="#fafafa" fillOpacity="0.7" />
        <circle cx="502" cy="368" r="5" fill="#fafafa" fillOpacity="0.7" />

        {/* Focal point oranye */}
        <circle cx="388" cy="322" r="8" fill="#ff6b35" />
        <circle cx="388" cy="322" r="3" fill="#111111" />

        {/* Garis pengukuran dekoratif */}
        <g stroke="#fafafa" strokeOpacity="0.3" strokeWidth="1">
          <line x1="388" y1="286" x2="388" y2="298" />
          <line x1="424" y1="322" x2="412" y2="322" />
        </g>
      </svg>

      {/* Label koordinat dekoratif — bukan data pelanggan asli */}
      <span className="geo-coord-label absolute right-[16%] top-[36%] font-mono text-[10px] tracking-wider text-neo-accent/80">-6.2088, 106.8456</span>
      <span className="geo-coord-label geo-coord-alt absolute bottom-[34%] left-[18%] font-mono text-[10px] tracking-wider text-white/40">R=150m · Δ 4.2m</span>

      {/* Branding */}
      <div className="relative z-10 p-10 xl:p-14">
        <p className="font-mono text-xs font-bold uppercase tracking-[0.3em] text-neo-accent">PLN GeoMatch</p>
      </div>
      <div className="relative z-10 space-y-4 p-10 pb-14 xl:p-14 xl:pb-20">
        <h2 className="max-w-sm text-3xl font-black leading-tight tracking-tight text-neo-white xl:text-4xl">
          Verifikasi Koordinat Pelanggan
        </h2>
        <p className="max-w-xs text-sm leading-relaxed text-white/60">
          Ruang kerja verifikasi dan rekonsiliasi data koordinat pelanggan.
        </p>
      </div>
    </aside>
  );
}

/** Subtle right-side spatial background: warm off-white, defined coordinate grid, trajectory lines & soft orange nodes. */
function RightSpatialBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* Defined warm coordinate grid (subtly enhanced visibility) */}
      <svg className="absolute inset-0 h-full w-full text-[#111111]/[0.075]" preserveAspectRatio="none">
        <defs>
          <pattern id="geo-grid-light" width="64" height="64" patternUnits="userSpaceOnUse">
            <path d="M64 0H0V64" fill="none" stroke="currentColor" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#geo-grid-light)" />
      </svg>

      {/* Trajectory polylines, range rings, and soft focal nodes */}
      <svg viewBox="0 0 600 800" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full">
        {/* Faint concentric range rings */}
        <circle cx="480" cy="180" r="160" fill="none" stroke="#111111" strokeOpacity="0.05" strokeWidth="1" />
        <circle cx="480" cy="180" r="90" fill="none" stroke="#111111" strokeOpacity="0.06" strokeWidth="1" strokeDasharray="4 6" />

        {/* Pulse ring on subtle orange node */}
        <circle cx="480" cy="180" r="14" fill="none" stroke="#ff6b35" strokeWidth="1.2" className="geo-pulse-light" />

        {/* Diagonal trajectory lines connecting coordinates */}
        <polyline
          points="20,140 160,90 320,170 480,180 580,260"
          fill="none"
          stroke="#111111"
          strokeOpacity="0.10"
          strokeWidth="1.5"
          strokeDasharray="4 4"
        />
        <polyline
          points="60,690 190,560 350,510 520,580"
          fill="none"
          stroke="#111111"
          strokeOpacity="0.09"
          strokeWidth="1.2"
        />

        {/* Soft orange nodes with low opacity */}
        <circle cx="480" cy="180" r="5" fill="#ff6b35" fillOpacity="0.45" />
        <circle cx="190" cy="560" r="4" fill="#ff6b35" fillOpacity="0.3" />

        {/* Subtle coordinate nodes */}
        <circle cx="160" cy="90" r="3.5" fill="#111111" fillOpacity="0.25" />
        <circle cx="320" cy="170" r="3.5" fill="#111111" fillOpacity="0.25" />
        <circle cx="350" cy="510" r="3.5" fill="#111111" fillOpacity="0.25" />

        {/* Crosshair marker at focal node */}
        <g stroke="#111111" strokeOpacity="0.18" strokeWidth="1">
          <line x1="480" y1="165" x2="480" y2="195" />
          <line x1="465" y1="180" x2="495" y2="180" />
        </g>

        {/* Decorative coordinate text labels */}
        <text x="496" y="174" fill="#111111" fillOpacity="0.32" fontSize="10" fontFamily="IBM Plex Mono, monospace" letterSpacing="0.05em">
          -6.2104, 106.8482
        </text>
        <text x="202" y="564" fill="#111111" fillOpacity="0.28" fontSize="9" fontFamily="IBM Plex Mono, monospace" letterSpacing="0.05em">
          ZONE 48S · ELEV 18M
        </text>
      </svg>
    </div>
  );
}

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
    setShowPassword(false);
    setError("");
  };

  return (
    <div className="flex min-h-[100dvh] flex-col bg-[#F0EFEB] text-neo-black lg:flex-row">
      <SpatialPanel />

      {/* Header branding versi mobile/tablet — ringkas, selaras dengan dark panel */}
      <header className="border-b-2 border-neo-black bg-[#111111] px-4 py-5 lg:hidden">
        <p className="font-mono text-[10px] font-bold uppercase tracking-[0.3em] text-neo-accent">PLN GeoMatch</p>
        <h1 className="mt-1.5 text-lg font-black tracking-tight text-neo-white">Verifikasi Koordinat Pelanggan</h1>
      </header>

      {/* Right panel: warm off-white background (#F0EFEB) + enhanced subtle spatial grid + refined glass card */}
      <main className="relative flex flex-1 items-center justify-center overflow-hidden bg-[#F0EFEB] px-4 py-8 sm:px-6 lg:px-10 safe-top safe-bottom before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:z-[5] before:hidden before:w-48 before:bg-gradient-to-r before:from-[#111111]/35 before:to-transparent before:content-[''] lg:before:block">
        <RightSpatialBackground />

        {/* Frosted glass neo-brutalist card: white/88 semi-transparent + restrained offset shadow */}
        <MotionConfig reducedMotion="user">
        <motion.section
          layout
          transition={{ layout: { type: "spring", stiffness: 280, damping: 30 } }}
          className="relative z-10 w-full max-w-[460px] rounded-[4px] border-2 border-neo-black bg-white/88 p-6 sm:p-8 lg:p-9 backdrop-blur-[12px] shadow-[5px_5px_0_#111111,7px_7px_0_rgba(255,107,53,0.22)] transition-[box-shadow,transform] duration-200"
          aria-labelledby="auth-title"
        >
          <AnimatePresence mode="wait" initial={false} custom={isRegister ? 1 : -1}>
          <motion.div
            key={mode}
            custom={isRegister ? 1 : -1}
            variants={{
              enter: (direction: number) => ({ opacity: 0, x: direction * 14 }),
              center: { opacity: 1, x: 0 },
              exit: (direction: number) => ({ opacity: 0, x: direction * -14 }),
            }}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
          <div className="mb-6 sm:mb-7">
            <div className="flex items-center gap-3">
              <span className="flex size-10 shrink-0 items-center justify-center border-2 border-neo-black bg-[#111111] text-white shadow-[2px_2px_0_rgba(255,107,53,0.7)]">
                {isRegister ? <UserPlus size={18} aria-hidden="true" /> : <User size={18} aria-hidden="true" />}
              </span>
              <div>
                <h2 id="auth-title" className="text-xl font-black tracking-tight text-neo-black sm:text-2xl">
                  {isRegister ? "Buat akun GeoMatch" : "Masuk ke GeoMatch"}
                </h2>
                <p className="mt-0.5 text-xs text-neo-border sm:text-sm">
                  {isRegister ? "Daftarkan akun untuk ruang kerja Anda" : "Gunakan akun GeoMatch Anda untuk melanjutkan"}
                </p>
              </div>
            </div>
          </div>

          <form onSubmit={handleSubmit} noValidate={false} className="space-y-4 sm:space-y-4.5">
            <AnimatePresence initial={false}>
              {error && (
                <motion.div
                  role="alert"
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.16 }}
                  className="border-2 border-[#dc2626] bg-[#fee2e2] px-3 py-2.5 text-xs font-semibold text-[#991b1b] sm:text-sm"
                >
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            <div>
              <label htmlFor="username" className="mb-1.5 block text-xs font-bold uppercase tracking-wide sm:text-sm">Username</label>
              <div className="group relative has-[:focus-visible]:[&>svg]:translate-x-0.5 has-[:focus-visible]:[&>svg]:text-neo-accent">
                <User className={iconClass} aria-hidden="true" />
                <input
                  id="username"
                  autoComplete="username"
                  className={`${inputClass} peer`}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Username"
                  required
                />
              </div>
            </div>

            {isRegister && (
              <div>
                <label htmlFor="email" className="mb-1.5 block text-xs font-bold uppercase tracking-wide sm:text-sm">Email</label>
                <div className="group relative has-[:focus-visible]:[&>svg]:translate-x-0.5 has-[:focus-visible]:[&>svg]:text-neo-accent">
                  <Mail className={iconClass} aria-hidden="true" />
                  <input
                    id="email"
                    autoComplete="email"
                    className={`${inputClass} peer`}
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
              <label htmlFor="password" className="mb-1.5 block text-xs font-bold uppercase tracking-wide sm:text-sm">Password</label>
              <div className="group relative has-[:focus-visible]:[&>svg]:translate-x-0.5 has-[:focus-visible]:[&>svg]:text-neo-accent">
                <Lock className={iconClass} aria-hidden="true" />
                <input
                  id="password"
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  className={`${inputClass} peer`}
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={isRegister ? "Minimal 6 karakter" : "Password"}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((previous) => !previous)}
                  aria-label={showPassword ? "Sembunyikan password" : "Tampilkan password"}
                  aria-pressed={showPassword}
                  className="absolute right-1.5 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-sm text-neo-border transition-colors hover:bg-gray-100 hover:text-neo-black focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neo-accent"
                >
                  {showPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                </button>
              </div>
            </div>

            {isRegister && (
              <div>
                <label htmlFor="confirm-password" className="mb-1.5 block text-xs font-bold uppercase tracking-wide sm:text-sm">Konfirmasi password</label>
                <div className="group relative has-[:focus-visible]:[&>svg]:translate-x-0.5 has-[:focus-visible]:[&>svg]:text-neo-accent">
                  <Lock className={iconClass} aria-hidden="true" />
                  <input
                    id="confirm-password"
                    autoComplete="new-password"
                    className={`${inputClass} peer`}
                    type={showPassword ? "text" : "password"}
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
              className="touch-min w-full border-2 border-neo-black bg-[#111111] px-4 py-3 text-sm font-bold text-white shadow-[3px_3px_0_#ff6b35] transition-[transform,box-shadow,background-color] duration-200 hover:translate-x-[1px] hover:translate-y-[1px] hover:bg-neutral-800 hover:shadow-[2px_2px_0_#ff6b35] active:translate-x-[3px] active:translate-y-[3px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-x-0 disabled:hover:translate-y-0 disabled:hover:shadow-[3px_3px_0_#ff6b35]"
            >
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={loading ? "loading" : mode}
                  initial={{ opacity: 0, y: 3 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -3 }}
                  transition={{ duration: 0.12 }}
                >
                  {loading ? "Memproses..." : isRegister ? "Daftar" : "Masuk"}
                </motion.span>
              </AnimatePresence>
            </button>

            <p className="border-t border-neo-border/20 pt-4 text-center text-xs text-neo-border sm:text-sm">
              {isRegister ? "Sudah punya akun?" : "Belum punya akun?"}{" "}
              <button
                type="button"
                onClick={() => switchMode(isRegister ? "login" : "register")}
                className="font-bold text-neo-black underline decoration-neo-accent decoration-2 underline-offset-4 transition-colors hover:text-neo-border focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neo-accent"
              >
                {isRegister ? "Masuk" : "Daftar sekarang"}
              </button>
            </p>
          </form>

          <p className="mt-5 text-center font-mono text-[10px] uppercase tracking-widest text-neo-border/70 sm:text-[11px]">
            Fase 1 · Autentikasi simulasi
          </p>
        </motion.div>
        </AnimatePresence>
        </motion.section>
        </MotionConfig>
      </main>
    </div>
  );
}