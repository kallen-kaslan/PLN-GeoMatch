import { useEffect, useRef, useState } from "react";
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

  const ambientCanvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ambientCanvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context || !window.matchMedia("(hover: hover) and (pointer: fine)").matches || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let frame = 0;
    let width = window.innerWidth;
    let height = window.innerHeight;
    let pointer = { x: width / 2, y: height / 2 };
    let light = { ...pointer };
    let speed = 0;
    let lastMove = 0;
    let lastTime = 0;
    let points: Array<{ x: number; y: number; time: number }> = [];

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const move = (event: PointerEvent) => {
      if (event.pointerType === "touch") return;
      const now = performance.now();
      const elapsed = Math.max(1, now - lastTime);
      const distance = Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y);
      speed = Math.min(1, distance / elapsed / 1.2);
      pointer = { x: event.clientX, y: event.clientY };
      points.push({ ...pointer, time: now });
      if (points.length > 24) points.shift();
      lastMove = now;
      if (!frame) frame = requestAnimationFrame(draw);
      lastTime = now;
    };
    const draw = (now: number) => {
      frame = 0;
      context.clearRect(0, 0, width, height);
      const settle = now - lastMove > 1000;
      const targetSpeed = settle ? 0 : speed;
      speed += (targetSpeed - speed) * 0.035;
      light.x += (pointer.x - light.x) * 0.16;
      light.y += (pointer.y - light.y) * 0.16;
      points = points.filter((point) => now - point.time < 520);

      if (points.length > 1) {
        for (let index = 1; index < points.length; index += 1) {
          const start = points[index - 1];
          const end = points[index];
          const age = now - end.time;
          const fade = Math.max(0, 1 - age / 520);
          const midpointX = (start.x + end.x) / 2;
          const onDarkPanel = window.innerWidth >= 1024 && midpointX < width * 0.44;
          const alpha = fade * (onDarkPanel ? 0.24 : 0.3) * (0.72 + speed * 0.28);
          const color = onDarkPanel ? "120, 221, 242" : "79, 134, 247";
          context.beginPath();
          context.moveTo(start.x, start.y);
          context.lineTo(end.x, end.y);
          context.lineCap = "round";
          context.lineWidth = 1.6;
          context.strokeStyle = `rgba(${color}, ${alpha})`;
          context.shadowBlur = 7;
          context.shadowColor = onDarkPanel ? "rgba(120, 221, 242, 0.42)" : "rgba(79, 134, 247, 0.32)";
          context.stroke();
        }
      }

      const opacity = Math.max(0, 0.7 - (now - lastMove) / 2200);
      const radius = 150 + speed * 24;
      const onDarkPanel = window.innerWidth >= 1024 && light.x < width * 0.44;
      const glow = context.createRadialGradient(light.x, light.y, 0, light.x, light.y, radius);
      if (onDarkPanel) {
        glow.addColorStop(0, `rgba(120, 221, 242, ${opacity * (0.14 + speed * 0.05)})`);
        glow.addColorStop(0.34, `rgba(79, 134, 247, ${opacity * 0.075})`);
      } else {
        glow.addColorStop(0, `rgba(79, 134, 247, ${opacity * (0.16 + speed * 0.05)})`);
        glow.addColorStop(0.34, `rgba(107, 130, 203, ${opacity * 0.09})`);
      }
      glow.addColorStop(0.72, `rgba(157, 140, 255, ${opacity * 0.025})`);
      glow.addColorStop(1, "rgba(157, 140, 255, 0)");
      context.shadowBlur = 0;
      context.fillStyle = glow;
      context.fillRect(light.x - radius, light.y - radius, radius * 2, radius * 2);

      if (now - lastMove < 2400 || points.length > 0) frame = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", move, { passive: true });
    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", move);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

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
    <div className="auth-page relative flex min-h-[100dvh] flex-col bg-[#F1F0ED] text-neo-black lg:flex-row">
      <canvas ref={ambientCanvasRef} aria-hidden="true" className="auth-ambient-canvas" />
      <SpatialPanel />

      {/* Header branding versi mobile/tablet — ringkas, selaras dengan dark panel */}
      <header className="border-b-2 border-neo-black bg-[#111111] px-4 py-5 lg:hidden">
        <p className="font-mono text-[10px] font-bold uppercase tracking-[0.3em] text-neo-accent">PLN GeoMatch</p>
        <h1 className="mt-1.5 text-lg font-black tracking-tight text-neo-white">Verifikasi Koordinat Pelanggan</h1>
      </header>

      {/* Right panel: warm off-white background (#F0EFEB) + enhanced subtle spatial grid + refined glass card */}
      <main className="relative flex flex-1 items-center justify-center overflow-x-hidden overflow-y-auto bg-[#F0EFEB] px-4 py-8 sm:px-6 lg:px-10 safe-top safe-bottom before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:z-[5] before:hidden before:w-48 before:bg-gradient-to-r before:from-[#111111]/35 before:to-transparent before:content-[''] lg:before:block">
        <RightSpatialBackground />

        {/* Frosted glass neo-brutalist card: white/88 semi-transparent + restrained offset shadow */}
        <div className="auth-flip-viewport relative z-10 w-full max-w-[460px]">
          <div className={`auth-flip-card ${isRegister ? "is-flipped" : ""}`}>
            {/* FRONT FACE: LOGIN */}
            <section
              className={`auth-flip-face ${isRegister ? "auth-flip-face-inactive" : ""} auth-spotlight-card rounded-[4px] border-2 border-neo-black bg-white/88 p-6 sm:p-8 lg:p-9 backdrop-blur-[12px] shadow-[5px_5px_0_#111111,7px_7px_0_rgba(107,130,203,0.22)] overflow-hidden`}
              style={{ "--pointer-x": "50%", "--pointer-y": "50%", "--border-alpha": "0" } as React.CSSProperties}
              aria-labelledby="auth-title-login"
              aria-hidden={isRegister}
              inert={isRegister}
            >
              <div className="mb-6 sm:mb-7">
                <div className="flex items-center gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center border-2 border-neo-black bg-[#111111] text-white shadow-[2px_2px_0_rgba(107,130,203,0.7)]">
                    <User size={18} aria-hidden="true" />
                  </span>
                  <div>
                    <h2 id="auth-title-login" className="text-xl font-black tracking-tight text-neo-black sm:text-2xl">
                      Masuk ke GeoMatch
                    </h2>
                    <p className="mt-0.5 text-xs text-neo-border sm:text-sm">
                      Gunakan akun GeoMatch Anda untuk melanjutkan
                    </p>
                  </div>
                </div>
              </div>

              <form onSubmit={handleSubmit} noValidate={false} className="space-y-4 sm:space-y-4.5">
                {error && !isRegister && (
                  <div role="alert" className="border-2 border-[#dc2626] bg-[#fee2e2] px-3 py-2.5 text-xs font-semibold text-[#991b1b] sm:text-sm">
                    {error}
                  </div>
                )}

                <div>
                  <label htmlFor="username-login" className="mb-1.5 block text-xs font-bold uppercase tracking-wide sm:text-sm">Username</label>
                  <div className="group relative has-[:focus-visible]:[&>svg]:translate-x-0.5 has-[:focus-visible]:[&>svg]:text-neo-accent">
                    <User className={iconClass} aria-hidden="true" />
                    <input
                      id="username-login"
                      autoComplete="username"
                      className={`${inputClass} peer`}
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="Username"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="password-login" className="mb-1.5 block text-xs font-bold uppercase tracking-wide sm:text-sm">Password</label>
                  <div className="group relative has-[:focus-visible]:[&>svg]:translate-x-0.5 has-[:focus-visible]:[&>svg]:text-neo-accent">
                    <Lock className={iconClass} aria-hidden="true" />
                    <input
                      id="password-login"
                      autoComplete="current-password"
                      className={`${inputClass} peer`}
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Password"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((p) => !p)}
                      aria-label="Tampilkan password"
                      className="absolute right-1.5 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-sm text-neo-border transition-colors hover:bg-gray-100 hover:text-neo-black"
                    >
                      {showPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="touch-min w-full border-2 border-neo-black bg-[#111111] px-4 py-3 text-sm font-bold text-white shadow-[3px_3px_0_#6B82CB] transition-[transform,box-shadow,background-color] duration-200 hover:translate-x-[1px] hover:translate-y-[1px] hover:bg-neutral-800 hover:shadow-[2px_2px_0_#4F86F7] active:translate-x-[3px] active:translate-y-[3px] active:shadow-none disabled:opacity-50"
                >
                  {loading ? "Memproses..." : "Masuk"}
                </button>

                <p className="border-t border-neo-border/20 pt-4 text-center text-xs text-neo-border sm:text-sm">
                  Belum punya akun?{" "}
                  <button
                    type="button"
                    onClick={() => switchMode("register")}
                    className="font-bold text-neo-black underline decoration-neo-accent decoration-2 underline-offset-4 transition-colors hover:text-neo-border"
                  >
                    Daftar sekarang
                  </button>
                </p>
              </form>
              <p className="mt-5 text-center font-mono text-[10px] uppercase tracking-widest text-neo-border/70 sm:text-[11px]">
                Fase 1 · Autentikasi simulasi
              </p>
            </section>

            {/* BACK FACE: REGISTER */}
            <section
              className={`auth-flip-face auth-flip-face-back ${!isRegister ? "auth-flip-face-inactive" : ""} auth-spotlight-card rounded-[4px] border-2 border-neo-black bg-white/88 p-6 sm:p-8 lg:p-9 backdrop-blur-[12px] shadow-[5px_5px_0_#111111,7px_7px_0_rgba(107,130,203,0.22)] overflow-hidden`}
              style={{ "--pointer-x": "50%", "--pointer-y": "50%", "--border-alpha": "0" } as React.CSSProperties}
              aria-labelledby="auth-title-register"
              aria-hidden={!isRegister}
              inert={!isRegister}
            >
              <div className="mb-6 sm:mb-7">
                <div className="flex items-center gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center border-2 border-neo-black bg-[#111111] text-white shadow-[2px_2px_0_rgba(107,130,203,0.7)]">
                    <UserPlus size={18} aria-hidden="true" />
                  </span>
                  <div>
                    <h2 id="auth-title-register" className="text-xl font-black tracking-tight text-neo-black sm:text-2xl">
                      Buat akun GeoMatch
                    </h2>
                    <p className="mt-0.5 text-xs text-neo-border sm:text-sm">
                      Daftarkan akun untuk ruang kerja Anda
                    </p>
                  </div>
                </div>
              </div>

              <form onSubmit={handleSubmit} noValidate={false} className="space-y-4 sm:space-y-4.5">
                {error && isRegister && (
                  <div role="alert" className="border-2 border-[#dc2626] bg-[#fee2e2] px-3 py-2.5 text-xs font-semibold text-[#991b1b] sm:text-sm">
                    {error}
                  </div>
                )}

                <div>
                  <label htmlFor="username-register" className="mb-1.5 block text-xs font-bold uppercase tracking-wide sm:text-sm">Username</label>
                  <div className="group relative has-[:focus-visible]:[&>svg]:translate-x-0.5 has-[:focus-visible]:[&>svg]:text-neo-accent">
                    <User className={iconClass} aria-hidden="true" />
                    <input
                      id="username-register"
                      autoComplete="username"
                      className={`${inputClass} peer`}
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="Username"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="email-register" className="mb-1.5 block text-xs font-bold uppercase tracking-wide sm:text-sm">Email</label>
                  <div className="group relative has-[:focus-visible]:[&>svg]:translate-x-0.5 has-[:focus-visible]:[&>svg]:text-neo-accent">
                    <Mail className={iconClass} aria-hidden="true" />
                    <input
                      id="email-register"
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

                <div>
                  <label htmlFor="password-register" className="mb-1.5 block text-xs font-bold uppercase tracking-wide sm:text-sm">Password</label>
                  <div className="group relative has-[:focus-visible]:[&>svg]:translate-x-0.5 has-[:focus-visible]:[&>svg]:text-neo-accent">
                    <Lock className={iconClass} aria-hidden="true" />
                    <input
                      id="password-register"
                      autoComplete="new-password"
                      className={`${inputClass} peer`}
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Minimal 6 karakter"
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

                <button
                  type="submit"
                  disabled={loading}
                  className="touch-min w-full border-2 border-neo-black bg-[#111111] px-4 py-3 text-sm font-bold text-white shadow-[3px_3px_0_#6B82CB] transition-[transform,box-shadow,background-color] duration-200 hover:translate-x-[1px] hover:translate-y-[1px] hover:bg-neutral-800 hover:shadow-[2px_2px_0_#4F86F7] active:translate-x-[3px] active:translate-y-[3px] active:shadow-none disabled:opacity-50"
                >
                  {loading ? "Memproses..." : "Daftar"}
                </button>

                <p className="border-t border-neo-border/20 pt-4 text-center text-xs text-neo-border sm:text-sm">
                  Sudah punya akun?{" "}
                  <button
                    type="button"
                    onClick={() => switchMode("login")}
                    className="font-bold text-neo-black underline decoration-neo-accent decoration-2 underline-offset-4 transition-colors hover:text-neo-border"
                  >
                    Masuk
                  </button>
                </p>
              </form>
              <p className="mt-5 text-center font-mono text-[10px] uppercase tracking-widest text-neo-border/70 sm:text-[11px]">
                Fase 1 · Autentikasi simulasi
              </p>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}