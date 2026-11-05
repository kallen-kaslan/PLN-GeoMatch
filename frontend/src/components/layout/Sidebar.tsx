import { Link, useLocation } from "react-router-dom";
import { useEffect, useRef, useState, Fragment } from "react";
import { LayoutDashboard, FolderUp, SlidersHorizontal, Map, FileCheck2, History, ShieldCheck, Database, ChevronDown, X, MapPin, type LucideIcon } from "lucide-react";
import { useAppStore } from "@/store/app";

type Item = { to: string; label: string; icon: LucideIcon; group?: string; children?: { to: string; label: string }[] };
const menu: Item[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/master", label: "Data Master", icon: Database, group: "Data", children: [
    { to: "/master/prabayar", label: "Prabayar" }, { to: "/master/pascabayar", label: "Pascabayar" }, { to: "/master/dil", label: "DIL" },
  ] },
  { to: "/pdpj", label: "Data PDPJ", icon: FileCheck2 },
  { to: "/koreksi", label: "Data Koreksi", icon: FolderUp, children: [
    { to: "/koreksi/idpel-tidak-ketemu", label: "IDPEL Tidak Ketemu" }, { to: "/koreksi/idpel-kosong", label: "IDPEL Kosong" },
  ] },
  { to: "/peta-koreksi", label: "Peta Koreksi", icon: Map, group: "Pemeriksaan" },
  { to: "/process", label: "Input Manual & Matching", icon: SlidersHorizontal },
  { to: "/result", label: "Hasil Rekonsiliasi", icon: FileCheck2, group: "Hasil" },
  { to: "/history", label: "Riwayat Proses", icon: History },
];
function NavigationItem({ item, collapsed }: { item: Item; collapsed: boolean }) {
  const { pathname } = useLocation();
  const [expanded, setExpanded] = useState(true);
  const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
  const Icon = item.icon;
  if (!item.children || collapsed) return <Link to={item.children?.[0]?.to ?? item.to} aria-current={active ? "page" : undefined} aria-label={collapsed ? item.label : undefined} title={collapsed ? item.label : undefined} className={`geo-nav-link ${collapsed ? "justify-center px-2" : ""}`}><Icon size={18} className="shrink-0" />{!collapsed && <span>{item.label}</span>}</Link>;
  return <div><button type="button" onClick={() => setExpanded(!expanded)} aria-expanded={expanded} className={`geo-nav-link w-full ${active ? "geo-nav-parent-active" : ""}`}><Icon size={18} /><span className="flex-1 text-left">{item.label}</span><ChevronDown size={14} className={expanded ? "rotate-180" : ""} /></button>{expanded && <div className="ml-5 space-y-0.5 border-l border-ui-nav-border py-1 pl-3">{item.children.map((child) => <Link key={child.to} to={child.to} aria-current={pathname === child.to ? "page" : undefined} className="geo-nav-link min-h-9 py-1.5 text-xs">{child.label}</Link>)}</div>}</div>;
}
export default function Sidebar() {
  const { user, isMobileMenuOpen, setIsMobileMenuOpen, isSidebarCollapsed } = useAppStore();
  const { pathname } = useLocation();
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { setIsMobileMenuOpen(false); }, [pathname, setIsMobileMenuOpen]);
  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 1024px)");
    const closeOnDesktop = () => { if (desktop.matches) setIsMobileMenuOpen(false); };
    desktop.addEventListener("change", closeOnDesktop);
    return () => desktop.removeEventListener("change", closeOnDesktop);
  }, [setIsMobileMenuOpen]);
  useEffect(() => {
    const element = dialog.current;
    if (isMobileMenuOpen && !element?.open) element?.showModal();
    if (!isMobileMenuOpen && element?.open) element.close();
    if (!isMobileMenuOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [isMobileMenuOpen]);
  const brand = (collapsed: boolean) => <Link to="/" aria-label="PLN GeoMatch ? Dashboard" title={collapsed ? "PLN GeoMatch" : undefined} className={`flex min-w-0 items-center rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 ${collapsed ? "justify-center" : "gap-2.5"}`}><span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-neo-accent text-white"><MapPin aria-hidden="true" size={19} /></span>{!collapsed && <span className="whitespace-nowrap text-[15px] font-semibold tracking-tight text-white">PLN GeoMatch</span>}</Link>;
  const navigation = (collapsed: boolean) => <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto p-3 neo-scrollbar" aria-label="Menu utama">{menu.map((item) => <Fragment key={item.to}>{item.group && (!collapsed ? <p className="geo-nav-group">{item.group}</p> : <div className="my-3 border-t border-ui-nav-border" />)}<NavigationItem item={item} collapsed={collapsed} /></Fragment>)}{user?.role === "admin" && <><div className="my-4 border-t border-ui-nav-border" /><NavigationItem item={{ to: "/admin", label: "Manajemen Pengguna", icon: ShieldCheck }} collapsed={collapsed} /></>}</nav>;
  return <>
    <aside id="app-sidebar" aria-label="Navigasi Utama Aplikasi" className={`geo-sidebar hidden shrink-0 flex-col border-r lg:flex ${isSidebarCollapsed ? "w-16" : "w-60"}`}><div className={`flex h-18 shrink-0 items-center border-b border-ui-nav-border ${isSidebarCollapsed ? "justify-center px-2" : "px-4"}`}>{brand(isSidebarCollapsed)}</div>{navigation(isSidebarCollapsed)}</aside>
    <dialog ref={dialog} id="app-sidebar-drawer" aria-label="Menu Navigasi Mobile" onCancel={() => setIsMobileMenuOpen(false)} onClose={() => setIsMobileMenuOpen(false)} className="fixed inset-y-0 left-0 right-auto m-0 h-dvh max-h-none w-[85vw] max-w-72 border-0 border-r border-ui-nav-border geo-sidebar p-0 shadow-xl lg:hidden"><div className="flex h-full flex-col"><header className="flex h-18 shrink-0 items-center justify-between border-b border-ui-nav-border px-4">{brand(false)}<button type="button" onClick={() => setIsMobileMenuOpen(false)} aria-label="Tutup menu" className="touch-min rounded-md text-ui-nav-text hover:bg-ui-nav-hover"><X size={20} /></button></header>{navigation(false)}</div></dialog>
  </>;
}
