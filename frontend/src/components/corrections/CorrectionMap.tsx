import { useEffect, useRef, useState } from "react";
import { createCorrectionMap, type MapProvider, type MapScene } from "@/lib/correction-map";

export function CorrectionMap(scene: MapScene) {
  const container = useRef<HTMLDivElement>(null);
  const provider = useRef<MapProvider | null>(null);
  const [available] = useState(() => Boolean((window as unknown as { L?: unknown }).L));
  useEffect(() => {
    if (container.current) provider.current = createCorrectionMap(container.current);
    return () => { provider.current?.destroy(); provider.current = null; };
  }, []);
  useEffect(() => { provider.current?.render(scene); }, [scene]);
  return <div>
    {!available && <p role="alert" className="border-2 border-amber-600 bg-amber-50 p-3 text-sm">Peta belum dapat dimuat. Periksa koneksi lalu muat ulang. Anda tetap dapat memilih target dan kandidat melalui tabel.</p>}
    <div ref={container} aria-label="Peta target koreksi" className="relative z-0 h-[420px] w-full rounded-sm border-2 border-neo-border sm:h-[520px]" />
    <p className="mt-2 text-xs">Jingga: target · Biru: target terpilih · Abu-abu: target lain · Hijau: kandidat. Titik bertumpuk menyediakan daftar pilihan saat diklik.</p>
  </div>;
}
