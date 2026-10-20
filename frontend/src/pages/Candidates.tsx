import { useState, useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";

declare global {
  interface Window {
    L: any;
  }
}

interface Candidate {
  id: number;
  process_id?: number;
  target_ref: string;
  target_lat: number;
  target_lon: number;
  candidate_idpel: string;
  candidate_nama: string;
  candidate_lat: number;
  candidate_lon: number;
  distance_meters: number;
  rank: number;
  jenis_layanan?: string; // PRABAYAR / PASCABAYAR
  validity_status?: string; // VALID / PERLU_KONFIRMASI_IDPEL / DILUAR_RADIUS
  is_under_5m?: number; // 1 jika < 5m
  is_accepted: number; // 0 = Pending, 1 = Valid, -1 = Tolak
}

export default function CandidatesPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialProcessId = searchParams.get("process_id") || "1";

  const [processId, setProcessId] = useState<string>(initialProcessId);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null);

  // Filter States
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [colorFilter, setColorFilter] = useState<"all" | "valid" | "unassigned" | "luar_jangkauan" | "under5m">("all");
  const [bulkUpdating, setBulkUpdating] = useState(false);
  const [distanceThresholdFilter, setDistanceThresholdFilter] = useState<string>("all");
  const [layananFilter, setLayananFilter] = useState<string>("all");

  // Map references
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const markersLayerRef = useRef<any>(null);
  const markerRegistryRef = useRef<Record<number, any>>({});

  const [seedingQuick, setSeedingQuick] = useState(false);

  const handleFinishReview = async () => {
    if (!processId) return;
    setLoading(true);
    try {
      await api.post(`/process/${processId}/finalize-review`);
      navigate(`/result?process_id=${processId}`);
    } catch (err: any) {
      setError(err.message || "Gagal menyelesaikan review. Coba lagi.");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!confirm("Yakin ingin mereset semua data? Tindakan ini tidak bisa diurungkan.")) return;
    setLoading(true);
    setError(null);
    try {
      await api.post("/upload/reset");
      setCandidates([]);
      setProcessId("");
      setError(null);
    } catch (err: any) {
      setError(err.message || "Gagal mereset data.");
    } finally {
      setLoading(false);
    }
  };

  const fetchCandidates = async () => {
    if (!processId) return;
    setLoading(true);
    setError(null);
    try {
      let url = `/process/${processId}/candidates`;
      if (statusFilter !== "all") {
        url += `?status_filter=${statusFilter}`;
      }
      const res = await api.get(url);
      setCandidates(res.data);
      if (res.data.length > 0 && res.data[0].process_id && String(res.data[0].process_id) !== processId) {
        setProcessId(String(res.data[0].process_id));
      }
    } catch (err: any) {
      setError(err.message || "Gagal memuat kandidat.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickDemoHere = async () => {
    setSeedingQuick(true);
    setError(null);
    try {
      const res = await api.post("/upload/seed-dummy");
      const pid = res.data.process_id || 1;
      setProcessId(String(pid));
      let url = `/process/${pid}/candidates`;
      const candRes = await api.get(url);
      setCandidates(candRes.data);
    } catch (err: any) {
      setError(err.message || "Gagal memuat data demo.");
    } finally {
      setSeedingQuick(false);
    }
  };

  useEffect(() => {
    fetchCandidates();
  }, [processId, statusFilter]);

  // Inisialisasi Peta Leaflet
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current && window.L) {
      const map = window.L.map(mapContainerRef.current).setView([-6.2088, 106.8456], 16);

      window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      markersLayerRef.current = window.L.layerGroup().addTo(map);
      mapInstanceRef.current = map;
    }
  }, []);

  // Update Markers di Peta saat data atau filter berubah
  useEffect(() => {
    const map = mapInstanceRef.current;
    const L = window.L;
    if (!map || !L || !markersLayerRef.current) return;

    markersLayerRef.current.clearLayers();
    markerRegistryRef.current = {};

    const filtered = getFilteredCandidates();
    if (filtered.length === 0) return;

    const bounds: [number, number][] = [];

    const createCustomIcon = (bgColor: string, text: string, shape: "square" | "circle" = "square") => {
      const radius = shape === "circle" ? "50%" : "4px";
      return L.divIcon({
        className: "custom-div-icon",
        html: `<div style="background-color: ${bgColor}; width: 28px; height: 28px; border-radius: ${radius}; border: 2px solid #0a0a0a; display: flex; align-items: center; justify-content: center; color: white; font-size: 10px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">${text}</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });
    };

    filtered.forEach((c) => {
      // 1. Marker Target Lapangan
      const targetGmapsUrl = `https://www.google.com/maps/search/?api=1&query=${c.target_lat},${c.target_lon}`;
      const targetMarker = L.marker([c.target_lat, c.target_lon], {
        icon: createCustomIcon("#2563eb", "TRG", "square"),
      }).bindPopup(`
        <div style="font-family: sans-serif; font-size: 12px; min-width: 190px;">
          <strong style="color: #2563eb; font-size: 13px;">Titik Target: ${c.target_ref}</strong><br/>
          <span>Koordinat: ${c.target_lat.toFixed(5)}, ${c.target_lon.toFixed(5)}</span><br/><br/>
          <a href="${targetGmapsUrl}" target="_blank" style="display: inline-block; padding: 4px 8px; background: #2563eb; color: white; text-decoration: none; border-radius: 2px; font-size: 11px;">📍 Buka di Google Maps</a>
        </div>
      `);
      markersLayerRef.current.addLayer(targetMarker);
      bounds.push([c.target_lat, c.target_lon]);

      // 2. Marker Pelanggan
      const isOutOfRadius = c.validity_status === "DILUAR_RADIUS" || c.candidate_idpel.startsWith("DILUAR_RADIUS") || c.candidate_idpel === "TIDAK_DITEMUKAN";
      const hasRealIdpel = !isOutOfRadius && !c.candidate_idpel.startsWith("UNASSIGNED-") && c.candidate_idpel !== "";
      const isUnder5m = !isOutOfRadius && c.distance_meters < 5.0 && c.distance_meters > 0;

      let candColor = "#16a34a"; // Hijau (Valid)
      let labelIcon = "PLN";

      if (isOutOfRadius) {
        candColor = "#dc2626"; // Merah (Di Luar Radius / Anomali)
        labelIcon = "!";
      } else if (!hasRealIdpel) {
        candColor = "#ea580c"; // Oranye (Tanpa IDPEL / Perlu Konfirmasi)
        labelIcon = "?";
      } else if (isUnder5m) {
        candColor = "#7c3aed"; // Ungu (< 5m)
        labelIcon = "<5m";
      }

      const candGmapsUrl = `https://www.google.com/maps/search/?api=1&query=${c.candidate_lat},${c.candidate_lon}`;

      const candMarker = L.marker([c.candidate_lat, c.candidate_lon], {
        icon: createCustomIcon(candColor, labelIcon, "circle"),
      }).bindPopup(`
        <div style="font-family: sans-serif; font-size: 12px; min-width: 210px;">
          <strong style="font-size: 13px; color: ${candColor};">${c.candidate_nama || "Tanpa Nama"}</strong><br/>
          <span>IDPEL: <strong>${c.candidate_idpel}</strong></span><br/>
          <span>Layanan: <strong>${c.jenis_layanan || "PASCABAYAR"}</strong></span><br/>
          <span>Jarak ke Target: <strong style="color: #ff6b35;">${c.distance_meters} m</strong></span><br/>
          <span>Status Data: <strong style="color: ${candColor};">${isOutOfRadius ? "🔴 LUAR JANGKAUAN / DI LUAR RADIUS" : hasRealIdpel ? "🟢 VALID (Ada IDPEL)" : "🟠 PERLU KONFIRMASI (Tanpa IDPEL)"}</strong></span><br/>
          ${isUnder5m ? '<span style="color: #7c3aed; font-weight: bold;">⚠️ Jarak < 5m (Jarak antar rumah min. 5m)</span><br/>' : ''}
          <br/>
          <a href="${candGmapsUrl}" target="_blank" style="display: inline-block; padding: 4px 8px; background: #0a0a0a; color: white; text-decoration: none; border-radius: 2px; font-size: 11px;">📍 Buka di Google Maps</a>
        </div>
      `);

      markersLayerRef.current.addLayer(candMarker);
      markerRegistryRef.current[c.id] = candMarker;
      bounds.push([c.candidate_lat, c.candidate_lon]);

      // 3. Garis Penghubung Target ke Kandidat
      const line = L.polyline(
        [
          [c.target_lat, c.target_lon],
          [c.candidate_lat, c.candidate_lon],
        ],
        {
          color: isOutOfRadius ? "#dc2626" : isUnder5m ? "#7c3aed" : "#ff6b35",
          weight: 2,
          dashArray: "4, 4",
        }
      );
      markersLayerRef.current.addLayer(line);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 18 });
    }
  }, [candidates, statusFilter, colorFilter, distanceThresholdFilter, layananFilter]);

  // Track & FlyTo Koordinat saat Baris Tabel di-klik
  const handleSelectRow = (candidate: Candidate) => {
    setSelectedCandidateId(candidate.id);
    const map = mapInstanceRef.current;
    if (map) {
      map.flyTo([candidate.candidate_lat, candidate.candidate_lon], 18, {
        animate: true,
        duration: 1.0,
      });

      const marker = markerRegistryRef.current[candidate.id];
      if (marker) {
        marker.openPopup();
      }
    }
  };

  const handleDecision = async (candidateId: number, decision: number, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      await api.post(`/process/candidates/${candidateId}/decision`, {
        is_accepted: decision,
      });
      setCandidates((prev) =>
        prev.map((c) => (c.id === candidateId ? { ...c, is_accepted: decision } : c))
      );
    } catch (err: any) {
      alert("Gagal menyimpan keputusan: " + err.message);
    }
  };

  const handleBulkDecision = async () => {
    const candidateIds = filteredCandidates.map((candidate) => candidate.id);
    if (candidateIds.length === 0) return;
    const decision = bulkAccepted ? 0 : 1;
    setBulkUpdating(true);
    setError(null);
    try {
      await api.post("/process/candidates/bulk-decision", {
        candidate_ids: candidateIds,
        is_accepted: decision,
      });
      setCandidates((prev) => prev.map((candidate) =>
        candidateIds.includes(candidate.id) ? { ...candidate, is_accepted: decision } : candidate
      ));
    } catch (err: any) {
      setError(err.message || "Gagal memperbarui keputusan kandidat.");
    } finally {
      setBulkUpdating(false);
    }
  };

  // Helper Pemilahan Data (Filter Client-Side)
  const getFilteredCandidates = () => {
    return candidates.filter((c) => {
      const isOutOfRadius = c.validity_status === "DILUAR_RADIUS" || c.candidate_idpel.startsWith("DILUAR_RADIUS") || c.candidate_idpel === "TIDAK_DITEMUKAN";
      const hasRealIdpel = !isOutOfRadius && !c.candidate_idpel.startsWith("UNASSIGNED-") && c.candidate_idpel !== "";
      const isUnder5m = !isOutOfRadius && c.distance_meters < 5.0 && c.distance_meters > 0;

      // Color card interactive filter
      if (colorFilter === "valid" && (!hasRealIdpel || isOutOfRadius)) return false;
      if (colorFilter === "unassigned" && (hasRealIdpel || isOutOfRadius)) return false;
      if (colorFilter === "luar_jangkauan" && !isOutOfRadius) return false;
      if (colorFilter === "under5m" && !isUnder5m) return false;

      // Jarak Threshold Filter
      if (distanceThresholdFilter === "under_5m" && !isUnder5m) return false;
      if (distanceThresholdFilter === "above_5m" && isUnder5m) return false;

      // Layanan Filter
      const layanan = (c.jenis_layanan || "PASCABAYAR").toUpperCase();
      if (layananFilter === "prabayar" && !layanan.includes("PRABAYAR")) return false;
      if (layananFilter === "pascabayar" && !layanan.includes("PASCABAYAR")) return false;

      return true;
    });
  };

  const filteredCandidates = getFilteredCandidates();
  const bulkAccepted = filteredCandidates.length > 0 && filteredCandidates.every((candidate) => candidate.is_accepted === 1);

  // Summary Counts
  const totalCount = candidates.length;
  const luarJangkauanCount = candidates.filter((c) => c.validity_status === "DILUAR_RADIUS" || c.candidate_idpel.startsWith("DILUAR_RADIUS") || c.candidate_idpel === "TIDAK_DITEMUKAN").length;
  const validIdpelCount = candidates.filter((c) => {
    const isOOR = c.validity_status === "DILUAR_RADIUS" || c.candidate_idpel.startsWith("DILUAR_RADIUS") || c.candidate_idpel === "TIDAK_DITEMUKAN";
    return !isOOR && !c.candidate_idpel.startsWith("UNASSIGNED-") && c.candidate_idpel !== "";
  }).length;
  const unassignedIdpelCount = totalCount - validIdpelCount - luarJangkauanCount;
  const under5mCount = candidates.filter((c) => {
    const isOOR = c.validity_status === "DILUAR_RADIUS" || c.candidate_idpel.startsWith("DILUAR_RADIUS") || c.candidate_idpel === "TIDAK_DITEMUKAN";
    return !isOOR && c.distance_meters < 5.0 && c.distance_meters > 0;
  }).length;

  return (
    <div className="space-y-6">
      {/* Top Header & Finish Button */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold mb-1">Review & Peta Spasial Koordinat</h1>
          <p className="text-sm text-neo-border">
            Klik baris pada tabel untuk melacak langsung (auto-track) lokasi di peta dan periksa kelayakan IDPEL.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold text-neo-black">ID Proses:</label>
            <input
              type="number"
              value={processId}
              onChange={(e) => setProcessId(e.target.value)}
              className="w-16 border border-neo-border p-1.5 rounded-sm text-xs bg-white font-bold"
            />
          </div>

          <button
            onClick={fetchCandidates}
            className="px-3 py-1.5 border border-neo-border bg-neo-white hover:bg-[#e5e4e7] text-xs font-semibold rounded-sm shadow-[0_2px_0_#0a0a0a]"
          >
            🔄 Refresh
          </button>

          <button
            onClick={handleReset}
            disabled={loading}
            className="px-3 py-1.5 border border-[#dc2626] bg-[#fee2e2] hover:bg-[#fef2f2] text-[#dc2626] text-xs font-semibold rounded-sm shadow-[0_2px_0_#0a0a0a] disabled:opacity-50"
            title="Hapus semua data dan mulai dari awal"
          >
            🗑️ Reset Data
          </button>

          {/* Tombol Konfirmasi Selesai -> Langsung ke Hasil */}
          <button
            onClick={handleFinishReview}
            disabled={loading}
            className="px-4 py-2 border border-neo-border bg-neo-accent hover:bg-[#e85a26] text-white text-xs font-bold rounded-sm shadow-[0_2px_0_#0a0a0a] flex items-center gap-1.5 disabled:opacity-50"
            title="Selesaikan verifikasi dan lihat rekapitulasi serta download CSV"
          >
            <span>✅ Selesai & Buka Hasil Rekonsiliasi</span>
            <span>→</span>
          </button>
        </div>
      </div>

      {/* Interactive Color Filter Cards (Bisa di-klik langsung) */}
      <div>
        <div className="text-xs font-bold text-neo-black mb-2 flex items-center gap-2">
          <span>Pilih Kategori Visual (Klik Kartu untuk Menyaring Peta & Tabel):</span>
          {colorFilter !== "all" && (
            <button
              onClick={() => setColorFilter("all")}
              className="text-[10px] text-[#2563eb] underline font-semibold"
            >
              Reset Filter
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {/* Card 1: Semua */}
          <button
            type="button"
            onClick={() => setColorFilter("all")}
            className={`p-3 text-left border rounded-sm transition ${
              colorFilter === "all"
                ? "border-neo-black bg-white shadow-[0_4px_0_#0a0a0a] ring-2 ring-[#0a0a0a]"
                : "border-neo-border bg-white shadow-[0_2px_0_#0a0a0a] hover:bg-[#f5f5f5]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-neo-border">SEMUA DATA</span>
              <span className="w-3 h-3 bg-neo-black rounded-xs"></span>
            </div>
            <div className="text-xl font-black mt-1 text-neo-black">{totalCount}</div>
            <div className="text-[10px] text-neo-border">Seluruh titik koordinat</div>
          </button>

          {/* Card 2: Hijau - Valid */}
          <button
            type="button"
            onClick={() => setColorFilter("valid")}
            className={`p-3 text-left border rounded-sm transition ${
              colorFilter === "valid"
                ? "border-[#16a34a] bg-[#dcfce7] shadow-[0_4px_0_#16a34a] ring-2 ring-[#16a34a]"
                : "border-[#16a34a] bg-[#f0fdf4] shadow-[0_2px_0_#16a34a] hover:bg-[#dcfce7]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-[#16a34a]">🟢 VALID</span>
              <span className="w-3 h-3 bg-[#16a34a] rounded-full"></span>
            </div>
            <div className="text-xl font-black mt-1 text-[#16a34a]">{validIdpelCount}</div>
            <div className="text-[10px] text-[#16a34a]">Dalam radius & ber-IDPEL</div>
          </button>

          {/* Card 3: Oranye - Perlu Konfirmasi */}
          <button
            type="button"
            onClick={() => setColorFilter("unassigned")}
            className={`p-3 text-left border rounded-sm transition ${
              colorFilter === "unassigned"
                ? "border-[#ea580c] bg-[#ffedd5] shadow-[0_4px_0_#ea580c] ring-2 ring-[#ea580c]"
                : "border-[#ea580c] bg-[#fff7ed] shadow-[0_2px_0_#ea580c] hover:bg-[#ffedd5]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-[#ea580c]">🟠 KONFIRMASI</span>
              <span className="w-3 h-3 bg-[#ea580c] rounded-full"></span>
            </div>
            <div className="text-xl font-black mt-1 text-[#ea580c]">{unassignedIdpelCount}</div>
            <div className="text-[10px] text-[#ea580c]">Ada koordinat, tanpa IDPEL</div>
          </button>

          {/* Card 4: Merah - Luar Jangkauan */}
          <button
            type="button"
            onClick={() => setColorFilter("luar_jangkauan")}
            className={`p-3 text-left border rounded-sm transition ${
              colorFilter === "luar_jangkauan"
                ? "border-[#dc2626] bg-[#fee2e2] shadow-[0_4px_0_#dc2626] ring-2 ring-[#dc2626]"
                : "border-[#dc2626] bg-[#fef2f2] shadow-[0_2px_0_#dc2626] hover:bg-[#fee2e2]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-[#dc2626]">🔴 LUAR JANGKAUAN</span>
              <span className="w-3 h-3 bg-[#dc2626] rounded-full"></span>
            </div>
            <div className="text-xl font-black mt-1 text-[#dc2626]">{luarJangkauanCount}</div>
            <div className="text-[10px] text-[#dc2626]">Di luar radius / tidak ditemukan</div>
          </button>

          {/* Card 5: Ungu - Sangat Dekat <5m */}
          <button
            type="button"
            onClick={() => setColorFilter("under5m")}
            className={`p-3 text-left border rounded-sm transition ${
              colorFilter === "under5m"
                ? "border-[#7c3aed] bg-[#f3e8ff] shadow-[0_4px_0_#7c3aed] ring-2 ring-[#7c3aed]"
                : "border-[#7c3aed] bg-[#faf5ff] shadow-[0_2px_0_#7c3aed] hover:bg-[#f3e8ff]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-[#7c3aed]">🟣 &lt;5M</span>
              <span className="w-3 h-3 bg-[#7c3aed] rounded-full"></span>
            </div>
            <div className="text-xl font-black mt-1 text-[#7c3aed]">{under5mCount}</div>
            <div className="text-[10px] text-[#7c3aed]">Jarak &lt;5m (min normal 5m)</div>
          </button>
        </div>
      </div>

      {/* PETA INTERAKTIF */}
      <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold">📍 Peta Geografis Spasial (Tracking Interaktif)</h2>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-[11px]">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 bg-[#2563eb] rounded-xs inline-block"></span>
              <span>🟦 Target</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 bg-[#16a34a] rounded-full inline-block"></span>
              <span>🟢 Valid</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 bg-[#ea580c] rounded-full inline-block"></span>
              <span>🟠 Tanpa IDPEL</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 bg-[#7c3aed] rounded-full inline-block"></span>
              <span>🟣 &lt; 5m</span>
            </span>
          </div>
        </div>

        {/* Map Canvas */}
        <div
          ref={mapContainerRef}
          style={{ height: "400px", width: "100%", zIndex: 10 }}
          className="border border-neo-border rounded-sm bg-[#e5e4e7]"
        ></div>

        <p className="text-[11px] text-neo-border bg-neo-white p-2 border border-neo-border rounded-xs">
          💡 <strong>Interaktivitas Peta:</strong> Klik salah satu baris pada tabel di bawah untuk membuat peta langsung <strong>terbang (fly-to)</strong> dan fokus pada koordinat titik tersebut. Klik marker untuk membuka langsung di <strong>Google Maps</strong>.
        </p>
      </div>

      {/* FILTER TAMBAHAN */}
      <div className="p-3 border border-neo-border rounded-sm bg-white shadow-[0_2px_0_#0a0a0a] flex flex-wrap gap-4 text-xs items-center">
        <div>
          <label className="font-bold mr-2">Status Review:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-neo-border p-1 rounded-sm bg-white"
          >
            <option value="all">Semua</option>
            <option value="0">Menunggu (Pending)</option>
            <option value="1">Valid (Disetujui)</option>
            <option value="-1">Ditolak</option>
          </select>
        </div>

        <div>
          <label className="font-bold mr-2">Jarak Antar Rumah (Min 5m):</label>
          <select
            value={distanceThresholdFilter}
            onChange={(e) => setDistanceThresholdFilter(e.target.value)}
            className="border border-neo-border p-1 rounded-sm bg-white"
          >
            <option value="all">Semua Jarak (5m - 50m+)</option>
            <option value="under_5m">&lt; 5m (Potensi Tetangga Dekat)</option>
            <option value="above_5m">&ge; 5m (Jarak Normal Antar Rumah)</option>
          </select>
        </div>

        <div>
          <label className="font-bold mr-2">Layanan:</label>
          <select
            value={layananFilter}
            onChange={(e) => setLayananFilter(e.target.value)}
            className="border border-neo-border p-1 rounded-sm bg-white"
          >
            <option value="all">Semua</option>
            <option value="prabayar">Prabayar</option>
            <option value="pascabayar">Pascabayar</option>
          </select>
        </div>

        <div className="ml-auto text-[11px] text-neo-border">
          Menampilkan <strong>{filteredCandidates.length}</strong> dari {candidates.length} data
        </div>
      </div>

      {/* BULK ACTION BUTTON */}
      {filteredCandidates.length > 0 && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={handleBulkDecision}
            disabled={bulkUpdating}
            className={`px-4 py-2 text-xs font-bold border rounded-sm transition ${
              bulkAccepted
                ? "border-[#dc2626] bg-[#fee2e2] text-[#dc2626] shadow-[0_2px_0_#dc2626] hover:bg-[#fef2f2]"
                : "border-[#16a34a] bg-[#dcfce7] text-[#16a34a] shadow-[0_2px_0_#16a34a] hover:bg-[#f0fdf4]"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {bulkUpdating ? (
              "Memproses..."
            ) : bulkAccepted ? (
              "✕ Hapus Semua"
            ) : (
              "✓ Validasi Semua"
            )}
          </button>
        </div>
      )}

      {error && (
        <div className="p-4 border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded-sm text-sm">
          {error}
        </div>
      )}

      {/* TABEL HASIL */}
      {loading ? (
        <div className="p-8 text-center text-sm text-neo-border">Memuat data kandidat...</div>
      ) : filteredCandidates.length === 0 ? (
        <div className="p-8 border border-dashed border-neo-border rounded-sm text-center bg-white space-y-3 shadow-[0_2px_0_#0a0a0a]">
          <p className="text-sm font-semibold text-neo-black">Belum Ada Data Kandidat untuk Proses #{processId}</p>
          <p className="text-xs text-neo-border max-w-md mx-auto">
            Proses ini belum memiliki data kandidat atau pencocokan belum dijalankan. Anda dapat menjalankan alur data demo secara instan atau upload file baru.
          </p>
          <div className="flex justify-center gap-3 pt-2">
            <button
              onClick={handleQuickDemoHere}
              disabled={seedingQuick}
              className="px-4 py-2 border border-neo-border bg-neo-accent text-white text-xs font-bold rounded-sm shadow-[0_2px_0_#0a0a0a] hover:bg-[#e85a26] disabled:opacity-50"
            >
              {seedingQuick ? "Memproses Data Demo..." : "⚡ Muat Data Demo Lengkap Langsung"}
            </button>
            <button
              onClick={() => navigate("/upload")}
              className="px-4 py-2 border border-neo-border bg-white text-neo-black text-xs font-semibold rounded-sm shadow-[0_2px_0_#0a0a0a] hover:bg-[#e5e4e7]"
            >
              📤 Buka Menu Upload
            </button>
          </div>
        </div>
      ) : (
        <div className="border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-[#e5e4e7] border-b border-neo-border">
              <tr>
                <th className="p-3 border-r border-neo-border">Rank</th>
                <th className="p-3 border-r border-neo-border">Target Koordinat Kosong</th>
                <th className="p-3 border-r border-neo-border">Kandidat IDPEL</th>
                <th className="p-3 border-r border-neo-border">Nama Pelanggan</th>
                <th className="p-3 border-r border-neo-border">Layanan</th>
                <th className="p-3 border-r border-neo-border">Jarak</th>
                <th className="p-3 border-r border-neo-border">Kelayakan Data</th>
                <th className="p-3 border-r border-neo-border text-center">Google Maps</th>
                <th className="p-3 border-r border-neo-border">Status</th>
                <th className="p-3 text-center">Aksi Petugas</th>
              </tr>
            </thead>
            <tbody>
              {filteredCandidates.map((c) => {
                const isOutOfRadius = c.validity_status === "DILUAR_RADIUS" || c.candidate_idpel.startsWith("DILUAR_RADIUS") || c.candidate_idpel === "TIDAK_DITEMUKAN";
                const hasRealIdpel = !isOutOfRadius && !c.candidate_idpel.startsWith("UNASSIGNED-") && c.candidate_idpel !== "";
                const isUnder5m = !isOutOfRadius && c.distance_meters < 5.0 && c.distance_meters > 0;
                const isSelected = selectedCandidateId === c.id;
                const gmapsUrl = `https://www.google.com/maps/search/?api=1&query=${c.candidate_lat},${c.candidate_lon}`;

                return (
                  <tr
                    key={c.id}
                    onClick={() => handleSelectRow(c)}
                    className={`border-b border-neo-border cursor-pointer transition ${
                      isSelected ? "bg-[#fef9c3] font-semibold neo-highlight" : "hover:bg-[#f5f5f5]"
                    }`}
                  >
                    <td className="p-3 border-r border-neo-border font-bold text-center">
                      #{c.rank}
                    </td>
                    <td className="p-3 border-r border-neo-border">
                      <div className="font-semibold text-neo-black">{c.target_ref}</div>
                      <div className="text-[10px] text-gray-500 font-mono">
                        {c.target_lat.toFixed(5)}, {c.target_lon.toFixed(5)}
                      </div>
                    </td>
                    <td className="p-3 border-r border-neo-border font-semibold">
                      {isOutOfRadius ? (
                        <span className="text-[#dc2626] font-bold">🔴 Di Luar Radius</span>
                      ) : hasRealIdpel ? (
                        <span className="text-neo-black">{c.candidate_idpel}</span>
                      ) : (
                        <span className="text-[#ea580c] italic font-normal">
                          Belum Ada IDPEL
                        </span>
                      )}
                    </td>
                    <td className="p-3 border-r border-neo-border">{c.candidate_nama || "-"}</td>
                    <td className="p-3 border-r border-neo-border">
                      <span className={`px-1.5 py-1 rounded neo-highlight text-[10px] font-bold ${
                        (c.jenis_layanan || "PASCABAYAR") === "PRABAYAR"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-gray-100 text-gray-800"
                      }`}>
                        {c.jenis_layanan || "PASCABAYAR"}
                      </span>
                    </td>
                    <td className="p-3 border-r border-neo-border font-mono">
                      <span className={`font-bold ${isOutOfRadius ? "text-[#dc2626]" : isUnder5m ? "text-[#7c3aed]" : "text-[#ff6b35]"}`}>
                        {c.distance_meters} m
                      </span>
                      {isUnder5m && (
                        <span className="block text-[10px] text-[#7c3aed] font-semibold">&lt; 5m (Min 5m)</span>
                      )}
                    </td>
                    <td className="p-3 border-r border-neo-border">
                      {isOutOfRadius ? (
                        <span className="px-2 py-1 neo-highlight border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded text-[10px] font-bold">
                          🔴 LUAR JANGKAUAN
                        </span>
                      ) : hasRealIdpel ? (
                        <span className="px-2 py-1 neo-highlight border border-[#16a34a] bg-[#dcfce7] text-[#16a34a] rounded text-[10px] font-bold">
                          ✓ VALID (ASLI)
                        </span>
                      ) : (
                        <span className="px-2 py-1 neo-highlight border border-[#ea580c] bg-[#ffedd5] text-[#ea580c] rounded text-[10px] font-bold">
                          ⚠️ KONFIRMASI ULANG
                        </span>
                      )}
                    </td>
                    <td className="p-3 border-r border-neo-border text-center" onClick={(e) => e.stopPropagation()}>
                      <a
                        href={gmapsUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="px-2 py-1 border border-neo-border bg-white hover:bg-[#e5e4e7] rounded text-[10px] font-bold inline-flex items-center gap-1 shadow-[0_1px_0_#0a0a0a]"
                      >
                        📍 GMaps
                      </a>
                    </td>
                    <td className="p-3 border-r border-neo-border">
                      {c.is_accepted === 1 && (
                        <span className="px-2 py-1 neo-highlight border border-[#16a34a] bg-[#dcfce7] text-[#16a34a] rounded text-[10px] font-bold">
                          VALID
                        </span>
                      )}
                      {c.is_accepted === -1 && (
                        <span className="px-2 py-1 neo-highlight border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded text-[10px] font-bold">
                          DITOLAK
                        </span>
                      )}
                      {c.is_accepted === 0 && (
                        <span className="px-2 py-1 neo-highlight border border-[#d97706] bg-[#fef3c7] text-[#d97706] rounded text-[10px] font-bold">
                          PENDING
                        </span>
                      )}
                    </td>
                    <td className="p-3 text-center" onClick={(e) => e.stopPropagation()}>
                      <div className="flex justify-center gap-1.5">
                        <button
                          onClick={(e) => handleDecision(c.id, 1, e)}
                          className={`px-2.5 py-1 border border-neo-border rounded text-[11px] font-semibold shadow-[0_1px_0_#0a0a0a] ${
                            c.is_accepted === 1
                              ? "bg-[#16a34a] text-white"
                              : "bg-white text-[#16a34a] hover:bg-[#dcfce7]"
                          }`}
                        >
                          ✓ Valid
                        </button>
                        <button
                          onClick={(e) => handleDecision(c.id, -1, e)}
                          className={`px-2.5 py-1 border border-neo-border rounded text-[11px] font-semibold shadow-[0_1px_0_#0a0a0a] ${
                            c.is_accepted === -1
                              ? "bg-[#dc2626] text-white"
                              : "bg-white text-[#dc2626] hover:bg-[#fee2e2]"
                          }`}
                        >
                          ✕ Tolak
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Bottom Action Finish */}
      {candidates.length > 0 && (
        <div className="flex items-center justify-between p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a]">
          <div>
            <span className="text-xs font-bold text-neo-black">Sudah selesai memverifikasi kandidat?</span>
            <p className="text-[11px] text-neo-border">Lanjutkan untuk melihat statistik final dan mengunduh laporan CSV.</p>
          </div>
          <button
            onClick={handleFinishReview}
            disabled={loading}
            className="px-5 py-2.5 border border-neo-border bg-neo-black text-white text-xs font-bold rounded-sm shadow-[0_2px_0_#0a0a0a] hover:bg-[#222] disabled:opacity-50"
          >
            ✅ Selesaikan Review & Buka Hasil Rekonsiliasi →
          </button>
        </div>
      )}
    </div>
  );
}
