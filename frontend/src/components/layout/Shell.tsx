import { useEffect, useLayoutEffect, useRef } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import { useAppStore } from "@/store/app";

export default function Shell() {
  const { user, authStatus } = useAppStore();
  const navigate = useNavigate();
  const location = useLocation();
  const content = useRef<HTMLElement>(null);
  const initialized = authStatus !== "checking";
  const map = location.pathname === "/peta-koreksi";

  useEffect(() => {
    if (initialized && !user) {
      navigate("/login", { state: { from: location } });
    }
  }, [user, initialized, navigate, location]);

  useLayoutEffect(() => { content.current?.scrollTo({ top: 0, left: 0, behavior: "instant" }); }, [location.pathname]);

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

  return (
    <div className="fixed inset-0 flex min-h-0 flex-col overflow-clip bg-neo-white text-neo-black">
      <Navbar />
      <div className="flex min-h-0 flex-1 overflow-clip">
        <Sidebar />
        <main ref={content} id="main-content" tabIndex={-1} className={`min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-y-contain neo-scrollbar focus:outline-none ${map ? "p-3 md:p-4" : "p-4 md:p-6"}`}>
          <div className="mx-auto w-full max-w-[1680px]">
            {user.role === "auditor" && <p role="status" className="mb-4 rounded-lg border border-ui-border bg-white p-3 text-sm text-ui-muted">Akses auditor: hanya melihat dan mengunduh data.</p>}
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
