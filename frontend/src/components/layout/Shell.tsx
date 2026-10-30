import { Outlet } from "react-router-dom";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";

export default function Shell() {
  return (
    <div className="min-h-[100dvh] flex flex-col bg-neo-white text-neo-black border-neo-border border-l-0 lg:border-l-2 border-r-0 lg:border-r-2 max-w-[1920px] mx-auto w-full">
      <Navbar />
      <div className="flex-1 flex overflow-hidden relative">
        <Sidebar />
        <main
          className="flex-1 overflow-y-auto overflow-x-hidden p-3.5 sm:p-5 lg:p-6 neo-scrollbar focus:outline-none"
          role="main"
          id="main-content"
          tabIndex={-1}
        >
          <div className="max-w-[1600px] mx-auto w-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
