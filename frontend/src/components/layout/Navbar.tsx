import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAppStore } from "@/store/app";

export default function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAppStore();

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
      <div className="flex items-center gap-3">
        {user?.role && (
          <span className="text-xs font-black px-2 py-1 border border-neo-border rounded-sm bg-[#e5e4e7] text-neo-black uppercase tracking-tighter">
            {user.role}
          </span>
        )}
        <span className="text-sm hidden sm:block">{user?.username ?? "-"}</span>
        <button
          onClick={() => {
            logout();
            navigate("/login");
          }}
          className="px-4 py-2 border border-neo-border rounded-sm text-sm font-medium text-[#dc2626] hover:bg-[#fee2e2] shadow-[0_2px_0_#0a0a0a]"
        >
          Keluar
        </button>
      </div>
    </header>
  );
}
