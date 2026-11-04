import { Navigate, useLocation } from "react-router-dom";
import { LoaderCircle } from "lucide-react";
import { useAppStore } from "@/store/app";
import Shell from "./Shell";

export default function RequireAuth() {
  const { authStatus, authError, initialize } = useAppStore();
  const location = useLocation();
  if (authStatus === "checking") return <p role="status" className="flex min-h-dvh items-center justify-center gap-2"><LoaderCircle className="animate-spin" size={20} />Memeriksa sesi...</p>;
  if (authStatus === "error") return <div className="m-auto max-w-lg space-y-4 p-6"><p role="alert">Sesi belum dapat diperiksa: {authError}</p><button type="button" onClick={() => void initialize()} className="underline">Coba lagi</button></div>;
  if (authStatus === "anonymous") return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <Shell />;
}
