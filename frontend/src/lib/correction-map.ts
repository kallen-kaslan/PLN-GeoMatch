import type { CorrectionCandidate, CorrectionRow } from "@/lib/corrections";

export const MAP_COLORS = {
  target: { fill: "#7f9fcd", stroke: "#5678a7" },
  selected: { fill: "#e4a36d", stroke: "#b87943" },
  candidate: { fill: "#83b58b", stroke: "#578b61" },
} as const;

type Position = [number, number];
interface Layer {
  addTo: (map: Layer | LeafletMap) => Layer;
  bindTooltip: (content: HTMLElement, options?: object) => Layer;
  bindPopup: (content: HTMLElement) => Layer;
  on: (event: string, callback: () => void) => Layer;
  getElement?: () => HTMLElement | undefined;
}
interface Group extends Layer { clearLayers: () => void }
interface LeafletMap {
  setView: (position: Position, zoom: number) => LeafletMap;
  fitBounds: (positions: Position[], options: object) => void;
  panTo: (position: Position, options: object) => void;
  invalidateSize: (options?: object) => void;
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
  scopeKey: string; rows: CorrectionRow[]; selected: number | null; candidates: CorrectionCandidate[];
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
  content.className = "max-w-64 space-y-1 whitespace-normal text-xs leading-relaxed";
  for (const line of lines) {
    const paragraph = document.createElement("p");
    paragraph.className = content.childElementCount === 0 ? "font-semibold text-slate-800" : "text-slate-600";
    paragraph.textContent = line;
    content.append(paragraph);
  }
  return content;
}

function textValue(value: unknown): string | null {
  const text = String(value ?? "").trim();
  return text && !["-", "\u2014", "null", "undefined", "nan"].includes(text.toLowerCase()) ? text : null;
}

function identity(fields: CorrectionRow["fields"], fallback = "Data Koreksi"): string[] {
  const name = textValue(fields.nama);
  const idpel = textValue(fields.idpel);
  const identifiers = [idpel ? `IDPEL ${idpel}` : null].filter((line): line is string => line !== null);
  return [name ?? identifiers.shift() ?? fallback, ...identifiers];
}

const objectLabel = (row: CorrectionRow) => `Objek ID: ${textValue(row.object_id) ?? "Tidak tersedia"}`;

const tooltipOptions = { className: "geo-map-tooltip", direction: "top", offset: [0, -10], opacity: 1 };
const distance = (meters: number) => `${meters.toLocaleString("id-ID", { maximumFractionDigits: 2 })} m`;

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
  let fitVisibleView = () => {};
  const observer = new ResizeObserver(() => { map.invalidateSize({ pan: false }); fitVisibleView(); }); observer.observe(element);
  let previousScope: string | undefined;
  let fitted = false;
  let previousFocus: string | null = null;
  return {
    render(scene) {
      map.stop(); map.closePopup(); targets.clearLayers(); candidates.clearLayers();
      const groups = new Map<string, CorrectionRow[]>();
      for (const row of scene.rows) {
        // While inspecting one record, hide every other correction target,
        // including records that share exactly the same coordinates.
        if (scene.selected !== null && row.id !== scene.selected) continue;
        const point = coordinates(row.fields);
        if (point) { const key = point.join(","); const group = groups.get(key) ?? []; group.push(row); groups.set(key, group); }
      }
      for (const rows of groups.values()) {
        const point = coordinates(rows[0].fields)!;
        const active = rows.some((row) => row.id === scene.selected);
        const marker = leaflet.circleMarker(point, {
          className: active ? "geo-map-target geo-map-target-active" : "geo-map-target",
          radius: active ? 8 : 4.5, color: active ? MAP_COLORS.selected.stroke : MAP_COLORS.target.stroke,
          fillColor: active ? MAP_COLORS.selected.fill : MAP_COLORS.target.fill, fillOpacity: active ? 0.9 : 0.7, weight: active ? 2 : 1,
        }).addTo(targets);
        marker.bindTooltip(description(rows.length === 1
          ? [objectLabel(rows[0]), `Jumlah Kandidat: ${rows[0].candidate_count.toLocaleString("id-ID")}`]
          : [`${rows.length.toLocaleString("id-ID")} data di lokasi ini`, ...rows.slice(0, 3).map((row) => `${objectLabel(row)} \u00b7 Jumlah Kandidat: ${row.candidate_count.toLocaleString("id-ID")}`), "Klik untuk memilih data."]), tooltipOptions);
        if (rows.length === 1) marker.on("click", () => scene.onSelect(rows[0].id));
        else {
          const popup = description([`${rows.length} data di lokasi ini. Pilih data koreksi:`]);
          popup.classList.add("max-h-64", "overflow-y-auto");
          for (const row of rows) {
            const button = document.createElement("button");
            button.className = "block w-full rounded border p-2 text-left text-xs hover:bg-blue-50 focus-visible:outline-blue-600";
            button.setAttribute("data-record-id", String(row.id));
            button.append(description([objectLabel(row), ...identity(row.fields), [row.filename, row.source_sheet].filter(Boolean).join(" \u00b7 ")]));
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
      if (center && scene.radius) leaflet.circle(center, { className: "geo-map-radius", radius: scene.radius, color: MAP_COLORS.selected.stroke, weight: 1, opacity: 0.65, fillOpacity: 0.045, interactive: false }).addTo(targets);
      // Group overlapping candidates so every candidate remains reachable on the map.
      const candidateGroups = new Map<string, CorrectionCandidate[]>();
      for (const item of scene.selected !== null ? scene.candidates : []) {
        const point = coordinates(item.fields);
        if (point) { const key = point.join(","); const group = candidateGroups.get(key) ?? []; group.push(item); candidateGroups.set(key, group); }
      }
      for (const items of candidateGroups.values()) {
        const marker = leaflet.circleMarker(coordinates(items[0].fields)!, { className: "geo-map-candidate", radius: 4, color: MAP_COLORS.candidate.stroke, fillColor: MAP_COLORS.candidate.fill, fillOpacity: 0.75, weight: 1.25 }).addTo(candidates);
        marker.bindTooltip(description(items.length === 1
          ? [...identity(items[0].fields, "Kandidat"), `Jarak ${distance(items[0].distance_meters)}`]
          : [`${items.length.toLocaleString("id-ID")} kandidat di lokasi ini`, ...items.slice(0, 3).map((item) => identity(item.fields, "Kandidat").join(" \u00b7 ")), "Klik untuk melihat kandidat."]), tooltipOptions);
        const popup = description(["Lihat detail kandidat:"]);
        popup.classList.add("max-h-64", "overflow-y-auto");
        for (const item of items) {
          const button = document.createElement("button");
          button.className = "block w-full rounded border p-2 text-left text-xs hover:bg-green-50";
          button.append(description([...identity(item.fields, "Kandidat"), `Jarak ${distance(item.distance_meters)}`]));
          button.onclick = () => scene.onCandidate(item.id); popup.append(button);
        }
        marker.bindPopup(popup);
      }
      // Fit once per saved data scope. Selection pans without replacing user zoom;
      // candidate requests, radius changes and clearing selection preserve the view.
      if (previousScope !== scene.scopeKey) {
        fitted = false; previousFocus = null; previousScope = scene.scopeKey;
      }
      fitVisibleView = () => {
        if (!fitted && groups.size && element.clientWidth > 0 && element.clientHeight > 0) {
          map.fitBounds([...groups.values()].map((items) => coordinates(items[0].fields)!), { padding: [35, 35], maxZoom: 16, animate: false });
          fitted = true;
          if (center) map.panTo(center, { animate: false });
        }
      };
      fitVisibleView();
      const focus = center ? `${scene.selected}:${center.join(",")}` : null;
      if (center && focus !== previousFocus) map.panTo(center, { animate: false });
      previousFocus = focus;
    },
    destroy() { observer.disconnect(); map.stop(); map.remove(); },
  };
}
