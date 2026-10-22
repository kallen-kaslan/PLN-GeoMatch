import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/store/app";
import { ChevronDown, User, LogOut, MapPin, Radio, Menu, X, PanelLeftClose, PanelLeft } from "lucide-react";
import { useState, useRef, useEffect } from "react";

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
    <header className="sticky top-0 z-40 border-b-2 border-neo-border bg-neo-white px-3 sm:px-6 py-2.5 sm:py-3 flex items-center justify-between shadow-[0_4px_0_#0a0a0a]">
      {/* Left: Hamburger & Brand */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Mobile / Tablet Drawer Toggle */}
        <button
          type="button"
          onClick={toggleMobileMenu}
          className="lg:hidden p-2 border-2 border-neo-border rounded-sm bg-neo-white text-neo-black hover:bg-[#e5e4e7] touch-min shadow-[0_2px_0_#0a0a0a] transition active:translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neo-accent"
          aria-label={isMobileMenuOpen ? "Tutup menu navigasi" : "Buka menu navigasi"}
          aria-expanded={isMobileMenuOpen}
          aria-controls="app-sidebar"
        >
          {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>

        {/* Desktop Sidebar Collapse Toggle */}
        <button
          type="button"
          onClick={toggleSidebarCollapsed}
          className="hidden lg:flex items-center justify-center p-2 border-2 border-neo-border rounded-sm bg-neo-white text-neo-black hover:bg-[#e5e4e7] shadow-[0_2px_0_#0a0a0a] transition active:translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neo-accent"
          title={isSidebarCollapsed ? "Perluas Sidebar" : "Perkecil Sidebar"}
          aria-label={isSidebarCollapsed ? "Perluas Sidebar" : "Perkecil Sidebar"}
        >
          {isSidebarCollapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
        </button>

        <div className="flex items-center gap-2">
          <span className="font-bold text-base sm:text-lg tracking-tighter truncate max-w-[140px] sm:max-w-none text-neo-black">
            PLN GeoMatch
          </span>
          <span className="hidden sm:inline-block text-[11px] text-neo-border border border-neo-border px-2 py-0.5 neo-highlight rounded-xs bg-white">
            Verifikasi Koordinat Pelanggan
          </span>
        </div>
      </div>

      {/* Center Animation: Sembunyikan di Mobile (<768px) agar tidak tabrakan layout */}
      <div className="hidden md:flex items-center gap-2">
        <div className="relative w-7 h-7 animate-pulse">
          <div className="absolute inset-0 bg-[#ff6b35] rounded-full animate-ping opacity-20"></div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-5 h-5 bg-[#ff6b35] rounded-full border-2 border-neo-border shadow-[0_2px_0_#0a0a0a]"></div>
          </div>
        </div>
        <div className="flex flex-col">
          <div className="h-1 w-10 bg-[#0a0a0a] rounded-full"></div>
          <div className="h-1 w-6 bg-[#333333] rounded-full mt-1"></div>
        </div>
        <MapPin className="w-5 h-5 text-[#2563eb]" aria-hidden="true" />
        <Radio className="w-4 h-4 text-[#16a34a] animate-pulse" aria-hidden="true" />
      </div>

      {/* Right: User Profile & Actions */}
      <div className="flex items-center gap-2 sm:gap-3 relative" ref={dropdownRef}>
        <button
          type="button"
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="flex items-center gap-2 px-3 sm:px-4 py-2 min-h-[40px] sm:min-h-[44px] border-2 border-neo-border rounded-sm text-sm font-medium text-neo-black hover:bg-[#e5e4e7] shadow-[0_2px_0_#0a0a0a] transition active:translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neo-accent"
          aria-haspopup="menu"
          aria-expanded={dropdownOpen}
          aria-label="Menu akun pengguna"
        >
          <User size={16} />
          <span className="hidden sm:block font-semibold">{user?.username ?? "User"}</span>
          <ChevronDown size={16} className={`transition-transform duration-200 ${dropdownOpen ? "rotate-180" : ""}`} />
        </button>

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

