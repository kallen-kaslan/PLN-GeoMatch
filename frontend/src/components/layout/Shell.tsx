import { Outlet, useLocation } from "react-router-dom";
import { useLayoutEffect, useRef } from "react";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";

export default function Shell() {
  const { pathname } = useLocation();
  const map = pathname === "/peta-koreksi";
  const content = useRef<HTMLElement>(null);
  useLayoutEffect(() => { content.current?.scrollTo({ top: 0, left: 0, behavior: "instant" }); }, [pathname]);
  return <div className="fixed inset-0 flex min-h-0 flex-col overflow-clip bg-neo-white text-neo-black">
    <Navbar />
    <div className="flex min-h-0 flex-1 overflow-clip">
      <Sidebar />
      <main ref={content} id="main-content" tabIndex={-1} className={`min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-y-contain neo-scrollbar focus:outline-none ${map ? "p-3 md:p-4" : "p-4 md:p-6"}`}>
        <div className="mx-auto w-full max-w-[1680px]"><Outlet /></div>
      </main>
    </div>
  </div>;
}
