import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useAppStore } from "@/store/app";
import {
  LayoutDashboard,
  FolderUp,
  SlidersHorizontal,
  Map,
  FileCheck2,
  History,
  ShieldCheck,
  LogOut,
  X,
  ChevronLeft,
  ChevronRight,
  User,
  Database,
  ChevronDown,
  type LucideIcon,
} from "lucide-react";

type MenuItem = { to: string; label: string; icon: LucideIcon; children?: { to: string; label: string }[] };

function MasterNavigation({ item, collapsed = false }: { item: MenuItem; collapsed?: boolean }) {
  const location = useLocation();
  const [expanded, setExpanded] = useState(true);
  const active = location.pathname.startsWith(item.to);
  const Icon = item.icon;
  const classes = `flex w-full items-center gap-2.5 rounded-sm border px-3 py-2 text-xs font-bold transition ${active ? "border-neo-black bg-neo-black text-white shadow-[0_2px_0_#ff6b35]" : "border-neo-border bg-white text-neo-black shadow-[0_1px_0_#0a0a0a] hover:bg-gray-100"}`;
  if (collapsed) return <Link to={item.children?.[0]?.to ?? item.to} title={item.label} className={`${classes} justify-center px-2`} aria-label={item.label}><Icon size={16} /></Link>;
  return <div className="space-y-1.5">
    <button type="button" onClick={() => setExpanded((previous) => !previous)} aria-expanded={expanded} className={classes}><Icon size={17} className="shrink-0" /><span className="flex-1 text-left">{item.label}</span><ChevronDown size={14} className={expanded ? "rotate-180" : ""} /></button>
    {expanded && <div className="ml-3 space-y-1 border-l-2 border-neo-border pl-3">{item.children?.map((child) => <Link key={child.to} to={child.to} aria-current={location.pathname === child.to ? "page" : undefined} className={`block rounded-sm border px-3 py-2.5 text-xs font-semibold ${location.pathname === child.to ? "border-neo-black bg-amber-50 shadow-[2px_2px_0_#ff6b35]" : "border-transparent hover:border-neo-border hover:bg-gray-100"}`}>{child.label}</Link>)}</div>}
  </div>;
}

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const {
    user,
    logout,
    isMobileMenuOpen,
    setIsMobileMenuOpen,
    isSidebarCollapsed,
    toggleSidebarCollapsed,
  } = useAppStore();

  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  const menu: MenuItem[] = [
    { to: "/", label: "Dashboard", icon: LayoutDashboard },
    { to: "/master", label: "Data Master", icon: Database, children: [
      { to: "/master/prabayar", label: "Prabayar" },
      { to: "/master/pascabayar", label: "Pascabayar" },
      { to: "/master/dil", label: "DIL" },
    ] },
    { to: "/pdpj", label: "Data PDPJ", icon: FileCheck2 },
    { to: "/koreksi", label: "Data Koreksi", icon: FolderUp, children: [
      { to: "/koreksi/idpel-tidak-ketemu", label: "IDPEL Tidak Ketemu" },
      { to: "/koreksi/idpel-kosong", label: "IDPEL Kosong" },
    ] },
    { to: "/process", label: "Input Manual & Matching", icon: SlidersHorizontal },
    { to: "/peta-koreksi", label: "Peta Koreksi", icon: Map },
    { to: "/result", label: "Hasil Rekonsiliasi", icon: FileCheck2 },
    { to: "/history", label: "Riwayat Proses", icon: History },
  ];

  // Tambahkan menu Admin jika pengguna memiliki role admin atau untuk eksplorasi admin
  if (user?.role === "admin") {
    menu.push({ to: "/admin", label: "Manajemen Pengguna", icon: ShieldCheck });
  }

  // Auto-close drawer saat rute berpindah
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname, setIsMobileMenuOpen]);

  // Body Scroll Lock & Focus Trap saat Mobile Drawer terbuka
  useEffect(() => {
    if (isMobileMenuOpen) {
      previousActiveElementRef.current = document.activeElement as HTMLElement;
      document.body.style.overflow = "hidden";

      // Beri fokus ke tombol Close di drawer
      const timer = setTimeout(() => {
        closeButtonRef.current?.focus();
      }, 50);

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          setIsMobileMenuOpen(false);
        }
      };

      document.addEventListener("keydown", handleKeyDown);
      return () => {
        document.body.style.overflow = "";
        document.removeEventListener("keydown", handleKeyDown);
        clearTimeout(timer);
        previousActiveElementRef.current?.focus();
      };
    } else {
      document.body.style.overflow = "";
    }
  }, [isMobileMenuOpen, setIsMobileMenuOpen]);

  return (
    <>
      {/* ============================================================== */}
      {/* 1. MOBILE & TABLET OFF-CANVAS DRAWER (< 1024px)               */}
      {/* ============================================================== */}
      <div
        className={`fixed inset-0 z-50 lg:hidden transition-visibility duration-200 ${
          isMobileMenuOpen ? "pointer-events-auto visible" : "pointer-events-none invisible"
        }`}
        aria-hidden={!isMobileMenuOpen}
      >
        {/* Backdrop Overlay */}
        <div
          onClick={() => setIsMobileMenuOpen(false)}
          className={`absolute inset-0 bg-[#0a0a0a]/75 backdrop-blur-xs transition-opacity duration-200 ${
            isMobileMenuOpen ? "opacity-100" : "opacity-0"
          }`}
          aria-label="Tutup menu navigasi"
        />

        {/* Drawer Panel */}
        <aside
          id="app-sidebar-drawer"
          role="dialog"
          aria-modal="true"
          aria-label="Menu Navigasi Mobile"
          className={`relative w-[82vw] max-w-[310px] h-full bg-[#fafafa] border-r-3 border-neo-border flex flex-col shadow-[8px_0_0_#0a0a0a] transition-transform duration-250 ease-out ${
            isMobileMenuOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          {/* Drawer Header */}
          <div className="p-4 border-b-2 border-neo-border bg-white flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-black text-base tracking-tight text-neo-black">PLN GeoMatch</span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 border border-neo-border bg-neo-white rounded-xs">
                v1.0
              </span>
            </div>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={() => setIsMobileMenuOpen(false)}
              className="p-2 border border-neo-border rounded-sm bg-neo-white text-neo-black hover:bg-[#fee2e2] hover:text-[#dc2626] touch-min transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neo-accent"
              aria-label="Tutup menu"
            >
              <X size={20} />
            </button>
          </div>

          {/* Drawer Navigation Links */}
          <nav className="flex-1 overflow-y-auto p-4 space-y-1.5 neo-scrollbar">
            <h2 className="text-[11px] font-bold text-neo-border uppercase tracking-widest px-2 mb-2">
              Menu Utama
            </h2>
            {menu.map((m) => {
              if (m.children) return <MasterNavigation key={m.to} item={m} />;
              const isActive = location.pathname === m.to;
              const Icon = m.icon;
              return (
                <Link
                  key={m.to}
                  to={m.to}
                  aria-current={isActive ? "page" : undefined}
                  className={`flex items-center gap-3 px-3.5 py-3 border-2 rounded-sm text-xs font-bold transition active:translate-y-0.5 ${
                    isActive
                      ? "border-neo-black bg-neo-black text-white shadow-[2px_2px_0_#ff6b35]"
                      : "border-neo-border bg-white text-neo-black hover:bg-[#e5e4e7] shadow-[2px_2px_0_#0a0a0a]"
                  }`}
                >
                  <Icon size={18} className="shrink-0" />
                  <span className="truncate">{m.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* Drawer User Profile & Logout Footer */}
          <div className="p-4 border-t-2 border-neo-border bg-white space-y-3">
            <div className="flex items-center gap-3 p-2 border border-neo-border bg-neo-white rounded-sm">
              <div className="w-8 h-8 rounded-xs border border-neo-border bg-neo-black text-white flex items-center justify-center shrink-0">
                <User size={16} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-neo-black truncate">{user?.username ?? "Pengguna"}</p>
                <p className="text-[10px] text-neo-border font-semibold uppercase">{user?.role ?? "analis"}</p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => {
                logout();
                setIsMobileMenuOpen(false);
                navigate("/login");
              }}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 border-2 border-[#dc2626] rounded-sm text-xs font-bold text-[#dc2626] bg-[#fee2e2] hover:bg-[#fecaca] shadow-[2px_2px_0_#dc2626] transition active:translate-y-0.5"
            >
              <LogOut size={16} />
              Keluar Akun
            </button>
          </div>
        </aside>
      </div>

      {/* ============================================================== */}
      {/* 2. DESKTOP & TABLET PERSISTENT SIDEBAR (>= 1024px)             */}
      {/* ============================================================== */}
      <aside
        id="app-sidebar"
        className={`hidden lg:flex flex-col border-r-2 border-neo-border bg-[#fafafa] shrink-0 transition-all duration-200 ease-in-out ${
          isSidebarCollapsed ? "w-[72px]" : "w-64"
        }`}
        aria-label="Navigasi Utama Aplikasi"
      >
        {/* Collapse Control Header */}
        <div className="p-3 border-b border-neo-border bg-white flex items-center justify-between">
          {!isSidebarCollapsed && (
            <h2 className="text-[11px] font-bold text-neo-border uppercase tracking-widest px-1">
              Navigasi Utama
            </h2>
          )}
          <button
            type="button"
            onClick={toggleSidebarCollapsed}
            className={`p-1.5 border border-neo-border rounded-xs bg-neo-white text-neo-black hover:bg-[#e5e4e7] transition active:translate-y-0.5 ${
              isSidebarCollapsed ? "mx-auto" : ""
            }`}
            title={isSidebarCollapsed ? "Perluas Sidebar" : "Perkecil Sidebar"}
            aria-label={isSidebarCollapsed ? "Perluas Sidebar" : "Perkecil Sidebar"}
          >
            {isSidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1.5 neo-scrollbar">
          {menu.map((m) => {
            if (m.children) return <MasterNavigation key={m.to} item={m} collapsed={isSidebarCollapsed} />;
            const isActive = location.pathname === m.to;
            const Icon = m.icon;
            return (
              <Link
                key={m.to}
                to={m.to}
                aria-current={isActive ? "page" : undefined}
                title={isSidebarCollapsed ? m.label : undefined}
                className={`flex items-center gap-2.5 px-3 py-2 border rounded-sm text-xs font-semibold transition active:translate-y-0.5 ${
                  isSidebarCollapsed ? "justify-center px-2" : ""
                } ${
                  isActive
                    ? "border-neo-black bg-neo-black text-white shadow-[0_2px_0_#ff6b35]"
                    : "border-neo-border bg-white text-neo-black hover:bg-[#e5e4e7] shadow-[0_1px_0_#0a0a0a]"
                }`}
              >
                <Icon size={16} className="shrink-0" />
                {!isSidebarCollapsed && <span className="truncate">{m.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Sidebar Footer Info */}
        <div className="p-3 border-t border-neo-border bg-white">
          {!isSidebarCollapsed ? (
            <div className="flex items-center justify-between text-[11px] text-neo-border">
              <span className="font-semibold truncate max-w-[140px]">{user?.username ?? "Petugas"}</span>
              <span className="font-mono text-[10px] uppercase font-bold px-1 bg-neo-white border border-neo-border rounded-xs">
                {user?.role ?? "analis"}
              </span>
            </div>
          ) : (
            <div className="flex justify-center" title={`${user?.username ?? "User"} (${user?.role ?? "analis"})`}>
              <div className="w-7 h-7 rounded-xs border border-neo-border bg-neo-black text-white flex items-center justify-center">
                <User size={14} />
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

