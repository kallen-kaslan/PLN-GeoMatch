import { Outlet, useLocation } from "react-router-dom";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";

export default function Shell() {
  const map = useLocation().pathname === "/peta-koreksi";
  return <div className="flex h-dvh min-h-0 bg-neo-white text-neo-black">
    <Sidebar />
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <Navbar />
      <main id="main-content" tabIndex={-1} className={`min-w-0 flex-1 overflow-y-auto overflow-x-hidden neo-scrollbar focus:outline-none ${map ? "p-3 md:p-4" : "p-4 md:p-6"}`}>
        <div className="mx-auto w-full max-w-[1680px]"><Outlet /></div>
      </main>
    </div>
  </div>;
}
