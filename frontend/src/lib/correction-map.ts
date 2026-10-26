import type { CorrectionCandidate, CorrectionRow } from "@/lib/corrections";
import { displayValue } from "@/lib/master";

type Position = [number, number];
interface Layer {
  addTo: (map: Layer | LeafletMap) => Layer;
  bindTooltip: (content: HTMLElement) => Layer;
  bindPopup: (content: HTMLElement) => Layer;
  on: (event: string, callback: () => void) => Layer;
  getElement?: () => HTMLElement | undefined;
}
interface Group extends Layer { clearLayers: () => void }
interface LeafletMap {
  setView: (position: Position, zoom: number) => LeafletMap;
  fitBounds: (positions: Position[], options: object) => void;
  invalidateSize: () => void;
  remove: () => void;
  closePopup: () => void;
  stop: () => void;
}
interface Leaflet {
  map: (element: HTMLElement, options: object) => LeafletMap;
  tileLayer: (url: string, options: object) => Layer;
  layerGroup: () => Group;
  circleMarker: (position: Position, options: object) => Layer;
  circle: (position: Position, options: object) => Layer;
}
export interface MapScene {
  rows: CorrectionRow[]; selected: number | null; candidates: CorrectionCandidate[];
  radius: number | null; onSelect: (id: number) => void; onCandidate: (id: number) => void;
}
export interface MapProvider { render: (scene: MapScene) => void; destroy: () => void }

export function coordinates(fields: CorrectionRow["fields"]): Position | null {
  const { lat, lon } = fields;
  return typeof lat === "number" && typeof lon === "number" && Number.isFinite(lat) && Number.isFinite(lon)
    && Math.abs(lat) <= 90 && Math.abs(lon) <= 180 && (lat !== 0 || lon !== 0) ? [lat, lon] : null;
}

function description(lines: string[]) {
  const content = document.createElement("div");
  content.className = "space-y-1 text-xs";
  for (const line of lines) {
    const paragraph = document.createElement("p");
    paragraph.textContent = line;
    content.append(paragraph);
  }
  return content;
}

/** Keep the existing Leaflet renderer behind a small provider boundary. */
export function createCorrectionMap(element: HTMLElement): MapProvider | null {
  const leaflet = (window as unknown as { L?: Leaflet }).L;
  if (!leaflet) return null;
  const map = leaflet.map(element, { scrollWheelZoom: false, zoomAnimation: false, fadeAnimation: false, markerZoomAnimation: false }).setView([-2.5, 118], 5);
  leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom: 20,
  }).addTo(map);
  const targets = leaflet.layerGroup(); targets.addTo(map);
  const candidates = leaflet.layerGroup(); candidates.addTo(map);
  const observer = new ResizeObserver(() => map.invalidateSize()); observer.observe(element);
  let previousView = "";
  return {
    render(scene) {
      map.stop(); map.closePopup(); targets.clearLayers(); candidates.clearLayers();
      const groups = new Map<string, CorrectionRow[]>();
      for (const row of scene.rows) {
        const point = coordinates(row.fields);
        if (point) { const key = point.join(","); const group = groups.get(key) ?? []; group.push(row); groups.set(key, group); }
      }
      for (const rows of groups.values()) {
        const point = coordinates(rows[0].fields)!;
        const active = rows.some((row) => row.id === scene.selected);
        const marker = leaflet.circleMarker(point, {
          radius: active ? 10 : 7, color: active ? "#1d4ed8" : scene.selected ? "#6b7280" : "#9a3412",
          fillColor: active ? "#2563eb" : scene.selected ? "#9ca3af" : "#f97316", fillOpacity: active || !scene.selected ? 0.9 : 0.4, weight: 2,
        }).addTo(targets);
        marker.bindTooltip(description([...rows.slice(0, 5).map((row) => `Baris ${row.row_number} · ${displayValue(row.fields.idpel)} · ${displayValue(row.fields.nama)} · ${row.candidate_count} kandidat`), ...(rows.length > 5 ? [`${rows.length} target pada titik ini. Klik untuk memilih baris.`] : [])]));
        if (rows.length === 1) marker.on("click", () => scene.onSelect(rows[0].id));
        else {
          const popup = description([`${rows.length} target pada koordinat yang sama. Pilih baris:`]);
          popup.classList.add("max-h-64", "overflow-y-auto");
          for (const row of rows) {
            const button = document.createElement("button");
            button.className = "block w-full rounded border p-2 text-left text-xs hover:bg-amber-50";
            button.textContent = `Pilih baris ${row.row_number} · ${displayValue(row.fields.nama)}`;
            button.onclick = () => { map.closePopup(); scene.onSelect(row.id); };
            popup.append(button);
          }
          marker.bindPopup(popup);
        }
        const svg = marker.getElement?.();
        svg?.setAttribute("role", "button"); svg?.setAttribute("tabindex", "0");
        svg?.setAttribute("aria-label", rows.length === 1 ? `Titik koreksi baris ${rows[0].row_number}` : `${rows.length} target bertumpuk`);
        svg?.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); svg.dispatchEvent(new MouseEvent("click", { bubbles: true })); }
        });
      }
      const selected = scene.rows.find((row) => row.id === scene.selected);
      const center = selected && coordinates(selected.fields);
      if (center && scene.radius) leaflet.circle(center, { radius: scene.radius, color: "#2563eb", weight: 1, fillOpacity: 0.04, interactive: false }).addTo(targets);
      // Group overlapping candidates so every candidate remains reachable on the map.
      const candidateGroups = new Map<string, CorrectionCandidate[]>();
      for (const item of scene.candidates) {
        const point = coordinates(item.fields);
        if (point) { const key = point.join(","); const group = candidateGroups.get(key) ?? []; group.push(item); candidateGroups.set(key, group); }
      }
      for (const items of candidateGroups.values()) {
        const marker = leaflet.circleMarker(coordinates(items[0].fields)!, { radius: 5, color: "#166534", fillColor: "#22c55e", fillOpacity: 0.85, weight: 2 }).addTo(candidates);
        marker.bindTooltip(description(items.map((item) => `${displayValue(item.fields.idpel)} · ${item.distance_meters.toFixed(2)} m`)));
        const popup = description(["Lihat detail kandidat:"]);
        popup.classList.add("max-h-64", "overflow-y-auto");
        for (const item of items) {
          const button = document.createElement("button");
          button.className = "block w-full rounded border p-2 text-left text-xs hover:bg-green-50";
          button.textContent = `Kandidat ${item.rank} · ${displayValue(item.fields.idpel)} · ${item.distance_meters.toFixed(2)} m`;
          button.onclick = () => scene.onCandidate(item.id); popup.append(button);
        }
        marker.bindPopup(popup);
      }
      const viewKey = `${scene.rows.length}:${scene.selected}:${scene.radius}:${scene.candidates.map((item) => item.id).join(",")}`;
      if (viewKey !== previousView) {
        const positions = center ? [center, ...scene.candidates.map((item) => coordinates(item.fields)).filter((point): point is Position => point !== null)] : [...groups.values()].map((items) => coordinates(items[0].fields)!);
        if (positions.length) map.fitBounds(positions, { padding: [35, 35], maxZoom: center ? 19 : 16, animate: false });
        previousView = viewKey;
      }
    },
    destroy() { observer.disconnect(); map.stop(); map.remove(); },
  };
}
