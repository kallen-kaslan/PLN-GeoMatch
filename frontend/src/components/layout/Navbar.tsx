import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAppStore } from "@/store/app";
import { ChevronDown, User, LogOut } from "lucide-react";
import { useState, useRef, useEffect } from "react";

export default function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAppStore();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const menu = [
    { to: "/", label: "Dashboard" },
    { to: "/upload", label: "Upload & Master" },
    { to: "/process", label: "Input & Matching" },
    { to: "/candidates", label: "Review & Peta Spasial" },
    { to: "/result", label: "Hasil" },
    { to: "/history", label: "Riwayat" },
    ...(user?.role === "admin" ? [{ to: "/admin", label: "Manajemen User" }] : []),
  ];

  return (
    <header className="border-b-2 border-neo-border bg-neo-white px-6 py-3 flex items-center justify-between shadow-[0_4px_0_#0a0a0a]">
      <div className="flex items-center gap-3">
        <span className="font-bold text-lg tracking-tighter">PLN GeoMatch</span>
        <span className="text-xs text-neo-border border border-neo-border px-2 py-0.5 rounded">
          Verifikasi Koordinat Pelanggan
        </span>
      </div>
      <nav className="flex gap-2">
        {menu.map((m) => (
          <Link
            key={m.to}
            to={m.to}
            className={`px-4 py-2 border border-neo-border rounded-sm text-sm font-medium transition ${
              location.pathname === m.to
                ? "bg-neo-black text-white shadow-[0_2px_0_#0a0a0a]"
                : "text-neo-black hover:bg-[#e5e4e7]"
            }`}
          >
            {m.label}
          </Link>
        ))}
      </nav>
      <div className="flex items-center gap-3 relative" ref={dropdownRef}>
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="flex items-center gap-2 px-4 py-2 border-2 border-neo-border rounded-sm text-sm font-medium text-neo-black hover:bg-[#e5e4e7] shadow-[0_2px_0_#0a0a0a] transition"
        >
          <User size={16} />
          <span className="hidden sm:block">{user?.username ?? "User"}</span>
          <ChevronDown size={16} className={`transition-transform ${dropdownOpen ? "rotate-180" : ""}`} />
        </button>

        {dropdownOpen && (
          <div className="absolute right-0 top-full mt-2 w-48 bg-neo-white border-2 border-neo-border rounded-sm shadow-[4px_4px_0_#0a0a0a] z-50">
            <div className="px-4 py-3 border-b-2 border-neo-border">
              <p className="text-sm font-medium text-neo-black">{user?.username ?? "-"}</p>
              <p className="text-xs text-neo-border mt-1">
                Role: <span className="font-black uppercase">{user?.role ?? "user"}</span>
              </p>
            </div>
            <button
              onClick={() => {
                logout();
                navigate("/login");
                setDropdownOpen(false);
              }}
              className="w-full flex items-center gap-2 px-4 py-3 text-sm font-medium text-[#dc2626] hover:bg-[#fee2e2] transition"
            >
              <LogOut size={16} />
              Keluar
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
