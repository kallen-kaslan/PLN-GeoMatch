import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { useAppStore } from "@/store/app";
import { setTokenGetter } from "@/lib/api";

// Hubungkan axios ke token Supabase dari store
setTokenGetter(() => useAppStore.getState().token);

// Inisialisasi session sebelum render pertama
useAppStore.getState().initAuth();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
