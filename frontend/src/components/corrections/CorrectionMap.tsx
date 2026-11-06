import { memo, useEffect, useRef, useState } from "react";
import { MAP_COLORS, createCorrectionMap, type MapProvider, type MapScene } from "@/lib/correction-map";

export const CorrectionMap = memo(function CorrectionMap(scene: MapScene) {
  const container = useRef<HTMLDivElement>(null);
  const provider = useRef<MapProvider | null>(null);
  const [available] = useState(() => Boolean((window as unknown as { L?: unknown }).L));
  useEffect(() => {
    if (container.current) provider.current = createCorrectionMap(container.current);
    return () => { provider.current?.destroy(); provider.current = null; };
  }, []);
  useEffect(() => { provider.current?.render(scene); }, [scene]);
  return <div>
    {!available && <p role="alert" className="border border-amber-600 bg-amber-50 p-3 text-sm">Peta belum dapat dimuat. Periksa koneksi lalu muat ulang. Anda tetap dapat memilih target dan kandidat melalui tabel.</p>}
    <div id="map-canvas" ref={container} tabIndex={-1} aria-label="Peta target koreksi" className="relative z-0 h-[clamp(280px,55dvh,440px)] w-full rounded-lg border border-ui-border focus-visible:outline-2 focus-visible:outline-ui-primary xl:h-[clamp(320px,48dvh,560px)]" />
    <ul aria-label="Legenda peta" className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-ui-muted">
      {[[MAP_COLORS.target.fill, "Data Koreksi"], [MAP_COLORS.selected.fill, "Data Dipilih"], [MAP_COLORS.candidate.fill, "Kandidat"]].map(([color, label]) => <li key={label} className="flex items-center gap-2"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full ring-1 ring-black/10" style={{ backgroundColor: color }} />{label}</li>)}
    </ul>
  </div>;
});
