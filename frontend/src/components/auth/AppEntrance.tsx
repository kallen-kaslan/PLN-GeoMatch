import { useEffect, useState, type ReactNode } from "react";
import { useAppStore } from "@/store/app";
import { AuthSplash } from "./AuthSplash";

/** Presentation only: session checks and routing continue behind the entrance. */
export function AppEntrance({ children }: { children: ReactNode }) {
  const checking = useAppStore((state) => state.authStatus === "checking");
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [introComplete, setIntroComplete] = useState(false);
  const [finished, setFinished] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => setIntroComplete(true), reducedMotion ? 0 : 2000);
    return () => window.clearTimeout(timer);
  }, [reducedMotion]);

  const revealing = introComplete && !checking;
  useEffect(() => {
    if (!revealing || finished) return;
    const timer = window.setTimeout(() => setFinished(true), reducedMotion ? 0 : 700);
    return () => window.clearTimeout(timer);
  }, [revealing, finished, reducedMotion]);

  return <div className={revealing && !finished ? "app-entrance app-entrance-revealing" : "app-entrance"}>
    <div className="app-entrance-content" inert={!finished} aria-hidden={!finished || undefined}>{children}</div>
    {!finished && <div className="app-entrance-overlay"><AuthSplash message={checking ? "Memeriksa sesi..." : "Membuka ruang kerja..."} /></div>}
  </div>;
}
