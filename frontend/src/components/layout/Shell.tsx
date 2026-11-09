import { Outlet, useNavigate, useLocation } from "react-router-dom";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import { useAppStore } from "@/store/app";
import { useEffect } from "react";

export default function Shell() {
  const { user, authStatus } = useAppStore();
  const navigate = useNavigate();
  const location = useLocation();
  const initialized = authStatus !== "checking";

  useEffect(() => {
    if (initialized && !user) {
      navigate("/login", { state: { from: location } });
    }
  }, [user, initialized, navigate, location]);

  if (!initialized) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center bg-neo-white">
        <div className="font-mono text-xs uppercase tracking-widest text-neo-border animate-pulse">
          Memuat sesi...
        </div>
      </div>
    );
  }

  if (!user) return null;

  const isMap = location.pathname === "/peta-koreksi";

  return (
    <div className="flex h-dvh min-h-0 flex-col bg-neo-white text-neo-black">
      <Navbar />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main
          id="main-content"
          tabIndex={-1}
          className={`min-w-0 flex-1 overflow-y-auto overflow-x-hidden neo-scrollbar focus:outline-none ${
            isMap ? "p-3 md:p-4" : "p-4 md:p-6"
          }`}
        >
          <div className="mx-auto w-full max-w-[1680px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
