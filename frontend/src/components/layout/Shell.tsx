import { Outlet } from "react-router-dom";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";

export default function Shell() {
  return (
    <div className="min-h-screen flex flex-col bg-neo-white text-neo-black border-neo-border border-l-2 border-r-2">
      <Navbar />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto p-6" role="main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
