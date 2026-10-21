import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/store/app";
import { ChevronDown, User, LogOut, MapPin, Radio } from "lucide-react";
import { useState, useRef, useEffect } from "react";

export default function Navbar() {
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

  return (
    <header className="border-b-2 border-neo-border bg-neo-white px-6 py-3 flex items-center justify-between shadow-[0_4px_0_#0a0a0a]">
      <div className="flex items-center gap-3">
        <span className="font-bold text-lg tracking-tighter">PLN GeoMatch</span>
        <span className="text-xs text-neo-border border border-neo-border px-2 py-1 neo-highlight rounded">
          Verifikasi Koordinat Pelanggan
        </span>
      </div>

      {/* Center Animation */}
      <div className="flex items-center gap-2">
        <div className="relative w-8 h-8 animate-pulse">
          <div className="absolute inset-0 bg-[#ff6b35] rounded-full animate-ping opacity-20"></div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-6 h-6 bg-[#ff6b35] rounded-full border-2 border-neo-border shadow-[0_2px_0_#0a0a0a]"></div>
          </div>
        </div>
        <div className="flex flex-col">
          <div className="h-1 w-12 bg-[#0a0a0a] rounded-full animate-[width_2s_ease-in-out_infinite]"></div>
          <div className="h-1 w-8 bg-[#333333] rounded-full mt-1 animate-[width_2s_ease-in-out_infinite_0.5s]"></div>
        </div>
        <MapPin className="w-6 h-6 text-[#2563eb] animate-bounce" aria-hidden="true" />
        <Radio className="w-4 h-4 text-[#16a34a] animate-pulse" aria-hidden="true" />
      </div>
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
