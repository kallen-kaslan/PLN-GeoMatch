import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/store/app";
import { ChevronDown, User, LogOut, MapPin, Menu, X, PanelLeftClose, PanelLeft } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { motion, useReducedMotion } from "motion/react";

export default function Navbar() {
  const navigate = useNavigate();
  const {
    user,
    logout,
    isMobileMenuOpen,
    toggleMobileMenu,
    isSidebarCollapsed,
    toggleSidebarCollapsed,
  } = useAppStore();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();
  const controlMotion = reduceMotion ? {} : {
    whileHover: { rotateX: -2, rotateY: 2, y: -1 },
    whileTap: { rotateX: 0, rotateY: 0, y: 1, scale: 0.99 },
    transition: { type: "spring" as const, stiffness: 400, damping: 28 },
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setDropdownOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <header className="spatial-navbar sticky top-0 z-[900] flex items-center justify-between border-b-2 border-[#10141B] bg-gradient-to-r from-[var(--console-charcoal)] via-[var(--console-graphite)] to-[#252B35] px-3 py-2.5 text-[var(--console-ivory)] shadow-[0_3px_0_rgba(10,14,20,0.75),0_6px_16px_rgba(10,14,20,0.12)] sm:px-6 sm:py-3">
      <svg
        className="spatial-wave-svg"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="nav-wave-blue" x1="0" y1="0" x2="100" y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#168BFF" stopOpacity="0" />
            <stop offset="0.28" stopColor="#168BFF" stopOpacity="0.9" />
            <stop offset="0.5" stopColor="#DDFBFF" />
            <stop offset="0.72" stopColor="#22D3FF" stopOpacity="0.95" />
            <stop offset="1" stopColor="#168BFF" stopOpacity="0" />
          </linearGradient>
          <path id="nav-wave-top-path" pathLength="340" d="M -2 12 C 8 3, 18 18, 30 10 C 43 2, 51 17, 64 9 C 77 1, 87 16, 102 8" />
          <path id="nav-wave-top-fine-path" pathLength="340" d="M -2 13 C 10 9, 18 18, 31 12 C 44 6, 54 15, 67 10 C 80 5, 91 15, 102 11" />
          <path id="nav-wave-top-short-path" pathLength="340" d="M -2 11 C 6 8, 12 14, 20 10 C 28 6, 35 13, 43 9 C 51 5, 57 11, 64 8 C 72 5, 77 10, 84 7 C 91 4, 97 8, 102 6" />
          <path id="nav-wave-bottom-short-path" pathLength="340" d="M -2 90 C 6 93, 12 87, 20 91 C 28 95, 35 88, 43 92 C 51 96, 57 90, 64 93 C 72 96, 77 91, 84 94 C 91 97, 97 93, 102 95" />
          <path id="nav-wave-bottom-path" pathLength="340" d="M -2 88 C 8 97, 18 82, 30 90 C 43 98, 51 83, 64 91 C 77 99, 87 84, 102 92" />
          <path id="nav-wave-bottom-fine-path" pathLength="340" d="M -2 89 C 10 93, 18 82, 31 88 C 44 94, 54 85, 67 90 C 80 95, 91 85, 102 89" />
        </defs>
        <use href="#nav-wave-top-path" className="wave-support wave-support-one wave-top-track" transform="translate(0 -3)" />
        <use href="#nav-wave-top-fine-path" className="wave-support wave-support-two wave-top-track" transform="translate(0 3)" />
        <use href="#nav-wave-top-fine-path" className="wave-filament wave-top-track" transform="translate(0 -5)" />
        <use href="#nav-wave-top-short-path" className="wave-thread-short wave-top-track" transform="translate(0 5)" />
        <use href="#nav-wave-top-path" className="wave-main wave-top wave-top-track" />
        <use href="#nav-wave-bottom-path" className="wave-support wave-support-one wave-bottom-track" transform="translate(0 3)" />
        <use href="#nav-wave-bottom-fine-path" className="wave-support wave-support-two wave-bottom-track" transform="translate(0 -3)" />
        <use href="#nav-wave-bottom-fine-path" className="wave-filament wave-bottom-track" transform="translate(0 5)" />
        <use href="#nav-wave-bottom-short-path" className="wave-thread-short wave-bottom-track" transform="translate(0 -5)" />
        <use href="#nav-wave-bottom-path" className="wave-main wave-bottom wave-bottom-track" />
        <g className="wave-particles" fill="#A7F5FF">
          <circle cx="8" cy="11" r="0.6" opacity="0.62" />
          <circle cx="20" cy="7" r="0.38" opacity="0.45" />
          <circle cx="36" cy="13" r="0.28" opacity="0.34" />
          <circle cx="57" cy="6" r="0.5" opacity="0.52" />
          <circle cx="75" cy="12" r="0.32" opacity="0.38" />
          <circle cx="92" cy="8" r="0.58" opacity="0.62" />
          <circle cx="8" cy="89" r="0.58" opacity="0.62" />
          <circle cx="24" cy="94" r="0.3" opacity="0.34" />
          <circle cx="43" cy="88" r="0.44" opacity="0.48" />
          <circle cx="62" cy="95" r="0.28" opacity="0.32" />
          <circle cx="81" cy="87" r="0.38" opacity="0.42" />
          <circle cx="95" cy="92" r="0.55" opacity="0.58" />
        </g>
      </svg>
      {/* Left: Hamburger & Brand */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Mobile / Tablet Drawer Toggle */}
        <motion.button
          type="button"
          onClick={toggleMobileMenu}
          {...controlMotion}
          className="lg:hidden flex items-center justify-center rounded-sm border border-white/25 bg-white/10 p-2 text-[var(--console-ivory)] shadow-[0_2px_0_rgba(0,0,0,0.4)] transition-colors hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--console-cobalt)]"
          aria-label={isMobileMenuOpen ? "Tutup menu navigasi" : "Buka menu navigasi"}
          aria-expanded={isMobileMenuOpen}
          aria-controls="app-sidebar-drawer"
        >
          {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
        </motion.button>

        {/* Desktop Sidebar Collapse Toggle */}
        <motion.button
          type="button"
          onClick={toggleSidebarCollapsed}
          {...controlMotion}
          className="hidden lg:flex items-center justify-center rounded-sm border border-white/25 bg-white/10 p-2 text-[var(--console-ivory)] shadow-[0_2px_0_rgba(0,0,0,0.4)] transition-colors hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--console-cobalt)]"
          title={isSidebarCollapsed ? "Perluas Sidebar" : "Perkecil Sidebar"}
          aria-label={isSidebarCollapsed ? "Perluas Sidebar" : "Perkecil Sidebar"}
        >
          {isSidebarCollapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
        </motion.button>

        <div className="flex items-center gap-2">
          <span className="max-w-[140px] truncate font-bold tracking-tighter text-[var(--console-ivory)] sm:max-w-none sm:text-lg">
            PLN GeoMatch
          </span>
          <span className="neo-highlight hidden rounded-xs border border-white/20 bg-white/8 px-2 py-0.5 text-[11px] text-[var(--console-cool-gray)] sm:inline-block">
            Verifikasi Koordinat Pelanggan
          </span>
        </div>
      </div>

      {/* Spatial status cluster: decorative location + signal state, not navigation. */}
      <div className="hidden items-center gap-2 rounded-sm border border-white/15 bg-black/15 px-3 py-1.5 md:flex" aria-label="Status spasial GeoMatch">
        <span className="spatial-orb relative flex size-5 items-center justify-center">
          <span className="absolute size-5 rounded-full border border-[var(--console-copper)]/50" />
          <span className="size-2 rounded-full bg-[var(--console-copper)] shadow-[0_0_8px_rgba(200,146,99,0.65)]" />
        </span>
        <span className="spatial-signal-line h-px w-8" />
        <MapPin className="size-4 text-[var(--console-cobalt)]" aria-hidden="true" />
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-hidden="true" />
        <span className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--console-cool-gray)]">Spatial ready</span>
      </div>

      {/* Right: User Profile & Actions */}
      <div className="flex items-center gap-2 sm:gap-3 relative" ref={dropdownRef}>
        <motion.button
          type="button"
          onClick={() => setDropdownOpen(!dropdownOpen)}
          {...controlMotion}
          className="flex min-h-[40px] items-center gap-2 rounded-sm border border-white/25 bg-white/10 px-3 py-2 text-sm font-medium text-[var(--console-ivory)] shadow-[0_2px_0_rgba(0,0,0,0.4)] transition-colors hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--console-cobalt)] sm:min-h-[44px] sm:px-4"
          aria-haspopup="menu"
          aria-expanded={dropdownOpen}
          aria-label="Menu akun pengguna"
        >
          <User size={16} />
          <span className="hidden sm:block font-semibold">{user?.username ?? "User"}</span>
          <ChevronDown size={16} className={`transition-transform duration-200 motion-reduce:transition-none ${dropdownOpen ? "rotate-180" : ""}`} />
        </motion.button>

        {dropdownOpen && (
          <div
            role="menu"
            className="absolute right-0 top-full mt-2 w-52 bg-neo-white border-2 border-neo-border rounded-sm shadow-[4px_4px_0_#0a0a0a] z-50 animate-in fade-in zoom-in-95 duration-150"
          >
            <div className="px-4 py-3 border-b-2 border-neo-border bg-white">
              <p className="text-sm font-bold text-neo-black truncate">{user?.username ?? "Pengguna"}</p>
              <p className="text-xs text-neo-border mt-1">
                Role: <span className="font-black uppercase text-neo-black">{user?.role ?? "analis"}</span>
              </p>
            </div>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                logout();
                navigate("/login");
                setDropdownOpen(false);
              }}
              className="w-full flex items-center gap-2 px-4 py-3 text-sm font-bold text-[#dc2626] hover:bg-[#fee2e2] transition text-left"
            >
              <LogOut size={16} />
              Keluar dari Sistem
            </button>
          </div>
        )}
      </div>
    </header>
  );
}

