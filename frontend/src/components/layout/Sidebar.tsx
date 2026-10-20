import { Link, useLocation } from "react-router-dom";

export default function Sidebar() {
  const location = useLocation();

  const menu = [
    { to: "/", label: "Dashboard", icon: "📊" },
    { to: "/upload", label: "Upload & Bentuk Master", icon: "📁" },
    { to: "/process", label: "Input Manual & Matching", icon: "⚙️" },
    { to: "/candidates", label: "Review & Peta Spasial", icon: "🗺️" },
    { to: "/result", label: "Hasil Rekonsiliasi", icon: "📋" },
    { to: "/history", label: "Riwayat Proses", icon: "📜" },
  ];

  return (
    <aside className="w-64 border-r-[2px] border-[#333333] bg-[#fafafa] hidden md:block">
      <nav className="p-4 space-y-2">
        <h2 className="text-xs font-bold text-[#333333] uppercase tracking-widest mb-3">Navigasi Utama</h2>
        <div className="space-y-1.5">
          {menu.map((m) => {
            const isActive = location.pathname === m.to;
            return (
              <Link
                key={m.to}
                to={m.to}
                className={`flex items-center gap-2.5 px-3 py-2 border border-[#333333] rounded-sm text-xs font-semibold transition ${
                  isActive
                    ? "bg-[#0a0a0a] text-white shadow-[0_2px_0_#0a0a0a]"
                    : "bg-white text-[#0a0a0a] hover:bg-[#e5e4e7]"
                }`}
              >
                <span>{m.icon}</span>
                <span>{m.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </aside>
  );
}
