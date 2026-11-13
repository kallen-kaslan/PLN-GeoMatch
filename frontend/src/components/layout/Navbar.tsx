import { useNavigate, useLocation } from "react-router-dom";
import { useAppStore } from "@/store/app";
import { ChevronDown, User, LogOut, Menu, PanelLeftClose, PanelLeft, MapPin } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import PasswordDialog from "./PasswordDialog";
import type { ApiError } from "@/lib/api";

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, isMobileMenuOpen, toggleMobileMenu, isSidebarCollapsed, toggleSidebarCollapsed } = useAppStore();
  const [open, setOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [logoutBusy, setLogoutBusy] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const signOut = async () => {
    if (logoutBusy) return;
    setLogoutBusy(true); setLogoutError("");
    try { await logout(); navigate("/login", { replace: true }); setOpen(false); }
    catch (error) { setLogoutError((error as ApiError).message); }
    finally { setLogoutBusy(false); }
  };
  const dropdown = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  const page =
    location.pathname.startsWith("/master") ? "Data Master" :
    location.pathname.startsWith("/pdpj") ? "Data PDPJ" :
    location.pathname === "/koreksi/pemilihan-otomatis" ? "Data Koreksi / Pemilihan Otomatis" :
    location.pathname.startsWith("/koreksi") ? "Data Koreksi" :
    location.pathname.startsWith("/peta-koreksi") ? "Peta Koreksi" :
    location.pathname.startsWith("/result") ? "Hasil Rekonsiliasi" :
    location.pathname.startsWith("/history") ? "Riwayat Proses" :
    location.pathname.startsWith("/admin") ? "Manajemen Pengguna" :
    location.pathname.startsWith("/process") ? "Input Manual & Matching" :
    location.pathname.startsWith("/candidates") ? "Review Kandidat" :
    "Dashboard";


  useEffect(() => {
    const outside = (event: MouseEvent) => {
      if (dropdown.current && !dropdown.current.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && open) { setOpen(false); trigger.current?.focus(); }
    };
    document.addEventListener("mousedown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  return <><header className="geo-topbar sticky top-0 z-40 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-ui-border bg-white px-4 lg:px-5">
    <a href="#main-content" className="sr-only rounded-md bg-white px-3 py-2 focus:not-sr-only">Lewati navigasi</a>
    <div className="flex min-w-0 items-center gap-3">
      <button type="button" onClick={toggleMobileMenu} className="touch-min rounded-md text-ui-muted hover:bg-slate-100 lg:hidden" aria-label={isMobileMenuOpen ? "Tutup menu navigasi" : "Buka menu navigasi"} aria-expanded={isMobileMenuOpen} aria-controls="app-sidebar-drawer"><Menu size={20} /></button>
      <div className="flex items-center gap-2.5"><span className="flex size-8 items-center justify-center rounded-lg bg-neo-accent text-white"><MapPin size={19} /></span><span className="whitespace-nowrap text-[15px] font-semibold tracking-tight">PLN GeoMatch</span></div>
      <button type="button" onClick={toggleSidebarCollapsed} className="touch-min ml-3 hidden rounded-md text-ui-muted hover:bg-slate-100 lg:flex" aria-label={isSidebarCollapsed ? "Perluas Sidebar" : "Perkecil Sidebar"} title={isSidebarCollapsed ? "Perluas Sidebar" : "Perkecil Sidebar"}>{isSidebarCollapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}</button>
      <span className="hidden rounded-md bg-ui-context px-3 py-1 text-[13px] font-medium text-ui-primary-text md:inline">{page}</span>
    </div>
    <div ref={dropdown} className="relative shrink-0">
      <button ref={trigger} type="button" onClick={() => setOpen(!open)} aria-label="Menu akun pengguna" aria-haspopup="menu" aria-expanded={open} className="flex min-h-10 items-center gap-2 rounded-md px-2 text-[13px] hover:bg-slate-50"><span className="flex size-7 items-center justify-center rounded-full bg-ui-accent-soft text-ui-accent-text"><User size={15} /></span><span className="hidden sm:inline">{user?.username ?? "Pengguna"}</span><ChevronDown size={14} /></button>
      {open && <div role="menu" className="absolute right-0 top-full mt-2 w-56 rounded-lg border border-ui-border bg-white p-1.5 shadow-lg"><div className="mb-1 border-b border-ui-border px-3 py-3"><p className="truncate text-sm font-medium">{user?.username ?? "Pengguna"}</p><p className="mt-1 text-xs text-ui-muted">Peran: {user?.role ?? "analis"}</p></div><button type="button" role="menuitem" onClick={() => { setOpen(false); setPasswordOpen(true); }} className="w-full rounded-md px-3 py-2 text-left text-sm hover:bg-slate-50">Ubah password</button>{logoutError && <p role="alert" className="p-2 text-xs text-red-700">{logoutError}</p>}<button type="button" role="menuitem" disabled={logoutBusy} onClick={() => void signOut()} className="flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left text-sm text-red-700 hover:bg-red-50"><LogOut size={16} />Keluar dari Sistem</button></div>}
    </div>
  </header>{passwordOpen && <PasswordDialog onClose={() => setPasswordOpen(false)} />}</>;
}
