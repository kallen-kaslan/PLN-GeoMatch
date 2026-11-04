import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAppStore } from "@/store/app";
import { ChevronDown, ChevronRight, User, LogOut, Menu, PanelLeftClose, PanelLeft } from "lucide-react";
import { useState, useRef, useEffect } from "react";

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, isMobileMenuOpen, toggleMobileMenu, isSidebarCollapsed, toggleSidebarCollapsed } = useAppStore();
  const [open, setOpen] = useState(false);
  const dropdown = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const titles: Record<string, string> = {
    "/": "Dashboard", "/master": "Data Master",
    "/master/prabayar": "Prabayar", "/master/pascabayar": "Pascabayar", "/master/dil": "DIL",
    "/pdpj": "Data PDPJ", "/koreksi": "Data Koreksi",
    "/koreksi/idpel-kosong": "IDPEL Kosong", "/koreksi/idpel-tidak-ketemu": "IDPEL Tidak Ketemu",
    "/peta-koreksi": "Peta Koreksi", "/result": "Hasil Rekonsiliasi",
    "/history": "Riwayat Proses", "/admin": "Manajemen Pengguna",
    "/process": "Input Manual & Matching", "/candidates": "Review Kandidat", "/upload": "Unggah Data",
  };
  const pathname = location.pathname.replace(/\/$/, "") || "/";
  const feature = titles[pathname] ?? "PLN GeoMatch";
  const params = new URLSearchParams(location.search);
  // Only separate pages add a breadcrumb. Filters, dialogs and workflow steps do not.
  const child = pathname === "/koreksi/idpel-kosong"
    ? params.get("flow") === "upload" ? "Unggah Data"
      : params.has("workspace") || params.has("batch_id") || params.has("process_id") ? "Pemeriksaan" : null
    : null;
  const page = child ?? feature;
  useEffect(() => {
    const outside = (event: MouseEvent) => { if (dropdown.current && !dropdown.current.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape" && open) { setOpen(false); trigger.current?.focus(); } };
    document.addEventListener("mousedown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("mousedown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);
  return <header className="geo-topbar sticky top-0 z-40 flex min-h-18 shrink-0 items-center justify-between gap-3 py-2 border-b border-ui-border bg-white px-4 lg:px-5">
    <a href="#main-content" className="sr-only rounded-md bg-white px-3 py-2 focus:not-sr-only">Lewati navigasi</a>
    <div className="flex min-w-0 flex-1 items-center gap-3">
      <button type="button" onClick={toggleMobileMenu} className="touch-min rounded-md text-ui-muted hover:bg-slate-100 lg:hidden" aria-label={isMobileMenuOpen ? "Tutup menu navigasi" : "Buka menu navigasi"} aria-expanded={isMobileMenuOpen} aria-controls="app-sidebar-drawer"><Menu size={20} /></button>
      <button type="button" onClick={toggleSidebarCollapsed} className="touch-min hidden rounded-md text-ui-muted hover:bg-slate-100 lg:flex" aria-label={isSidebarCollapsed ? "Perluas Sidebar" : "Perkecil Sidebar"} title={isSidebarCollapsed ? "Perluas Sidebar" : "Perkecil Sidebar"} aria-controls="app-sidebar" aria-expanded={!isSidebarCollapsed}>{isSidebarCollapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}</button>
      <div className="min-w-0 space-y-1">
        <p aria-label={child ? "Judul fitur" : "Halaman aktif"} className="text-sm font-semibold leading-snug sm:text-base">{feature}</p>
        {child && <nav aria-label="Jejak halaman" className="text-xs leading-snug text-ui-muted"><ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1"><li><Link to={pathname} className="rounded-sm hover:text-ui-primary-text hover:underline focus-visible:outline-2 focus-visible:outline-offset-2">{feature}</Link></li><li className="flex min-w-0 items-center gap-1.5"><ChevronRight aria-hidden="true" size={12} className="shrink-0" /><span aria-label="Halaman aktif" aria-current="page" className="text-neo-black">{page}</span></li></ol></nav>}
      </div>
    </div>
    <div ref={dropdown} className="relative shrink-0">
      <button ref={trigger} type="button" onClick={() => setOpen(!open)} aria-label="Menu akun pengguna" aria-haspopup="menu" aria-expanded={open} className="flex min-h-10 items-center gap-2 rounded-md px-2 text-[13px] hover:bg-slate-50"><span className="flex size-7 items-center justify-center rounded-full bg-ui-accent-soft text-ui-accent-text"><User size={15} /></span><span className="hidden sm:inline">{user?.username ?? "Pengguna"}</span><ChevronDown size={14} /></button>
      {open && <div role="menu" className="absolute right-0 top-full mt-2 w-56 rounded-lg border border-ui-border bg-white p-1.5 shadow-lg"><div className="mb-1 border-b border-ui-border px-3 py-3"><p className="truncate text-sm font-medium">{user?.username ?? "Pengguna"}</p><p className="mt-1 text-xs text-ui-muted">Peran: {user?.role ?? "analis"}</p></div><button type="button" role="menuitem" onClick={() => { logout(); navigate("/login"); setOpen(false); }} className="flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left text-sm text-red-700 hover:bg-red-50"><LogOut size={16} />Keluar dari Sistem</button></div>}
    </div>
  </header>;
}
