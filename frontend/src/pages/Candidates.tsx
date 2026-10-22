import { useState, useEffect, useRef, useCallback } from "react";
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
  const [searchParams, setSearchParams] = useSearchParams();
  const processId = searchParams.get("process_id") || "1";

  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [totalCandidates, setTotalCandidates] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null);

  // Filter States
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [validityFilters, setValidityFilters] = useState<string[]>([]);
  const [layananFilters, setLayananFilters] = useState<string[]>([]);
  const [idpelFilters, setIdpelFilters] = useState<string[]>([]);

  // Pagination States
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [rowsPerPage, setRowsPerPage] = useState<number>(50);
  const [processStatus, setProcessStatus] = useState<string>("none");

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
      setTotalCandidates(0);
      setSearchParams({ process_id: "" });
      setError(null);
    } catch (err: any) {
      setError(err.message || "Gagal mereset data.");
    } finally {
      setLoading(false);
    }
  };

  const fetchCandidates = useCallback(() => {
    if (!processId) return;

    // Cek status proses rekonsiliasi
    api.get(`/history/process/${processId}/summary`)
      .then((sRes) => {
        const st = String(sRes.data.matching_status || "").toLowerCase();
        setProcessStatus(st);
      })
      .catch(() => {});

    const skip = (currentPage - 1) * rowsPerPage;
    let url = `/process/${processId}/candidates?skip=${skip}&limit=${rowsPerPage}`;
    if (statusFilter !== "all") {
      url += `&status_filter=${statusFilter}`;
    }
    if (validityFilters.length > 0) {
      url += `&validity_filters=${validityFilters.join(",")}`;
    }
    if (layananFilters.length > 0) {
      url += `&layanan_filters=${layananFilters.join(",")}`;
    }
    if (idpelFilters.length > 0) {
      url += `&idpel_filters=${idpelFilters.join(",")}`;
    }

    api.get(url)
      .then((res) => {
        setCandidates(res.data.items);
        setTotalCandidates(res.data.total);
        setError(null);
        if (res.data.items.length > 0 && res.data.items[0].process_id && String(res.data.items[0].process_id) !== processId) {
          setSearchParams({ process_id: String(res.data.items[0].process_id) });
        }
      })
      .catch((err: any) => {
        setError(err.message || "Gagal memuat kandidat.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [processId, currentPage, rowsPerPage, statusFilter, validityFilters, layananFilters, idpelFilters, setSearchParams]);

  // Polling otomatis jika worker masih memproses di background
  useEffect(() => {
    if (processStatus === "queued" || processStatus === "running") {
      const timer = setTimeout(() => {
        fetchCandidates();
      }, 2500);
      return () => clearTimeout(timer);
    }
  }, [processStatus, fetchCandidates]);

  const handleQuickDemoHere = async () => {
    setSeedingQuick(true);
    setError(null);
    try {
      const res = await api.post("/upload/seed-dummy");
      const pid = res.data.process_id || 1;
      setSearchParams({ process_id: String(pid) });
      const candRes = await api.get(`/process/${pid}/candidates`);
      setCandidates(candRes.data.items);
      setTotalCandidates(candRes.data.total);
    } catch (err: any) {
      setError(err.message || "Gagal memuat data demo.");
    } finally {
      setSeedingQuick(false);
    }
  };

  useEffect(() => {
    fetchCandidates();
  }, [fetchCandidates]);

  // Inisialisasi Peta Leaflet dengan proteksi scroll-trapping & resize observer
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current && window.L) {
      const map = window.L.map(mapContainerRef.current, {
        scrollWheelZoom: false, // Menghindari trapping saat scrolling layar mobile
      }).setView([-6.2088, 106.8456], 16);

      window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      markersLayerRef.current = window.L.layerGroup().addTo(map);
      mapInstanceRef.current = map;
    }

    const handleResize = () => {
      mapInstanceRef.current?.invalidateSize();
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  // Update Markers di Peta saat data atau halaman berubah
  useEffect(() => {
    const map = mapInstanceRef.current;
    const L = window.L;
    if (!map || !L || !markersLayerRef.current) return;

    markersLayerRef.current.clearLayers();
    markerRegistryRef.current = {};

    if (candidates.length === 0) return;

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

    candidates.forEach((c) => {
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

      const markerShape = isOutOfRadius ? "square" : "circle";

      const candMarker = L.marker([c.candidate_lat, c.candidate_lon], {
        icon: createCustomIcon(candColor, labelIcon, markerShape),
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
  }, [candidates]);

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
    const candidateIds = candidates.map((candidate) => candidate.id);
    if (candidateIds.length === 0) return;
    const allAccepted = candidates.every((candidate) => candidate.is_accepted === 1);
    const decision = allAccepted ? 0 : 1;
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
    }
  };

  // Summary Counts
  const totalCount = totalCandidates;

  const totalPages = Math.ceil(totalCandidates / rowsPerPage);

  return (
    <div className="space-y-6">
      {/* Top Header & Finish Button */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 sm:gap-4 border-b border-neo-border pb-3">
        <div>
          <h1 className="fluid-h1 font-black tracking-tight text-neo-black">
            Review & Peta Spasial Koordinat
          </h1>
          <p className="text-xs sm:text-sm text-neo-border mt-0.5">
            Klik baris pada tabel untuk melacak langsung (auto-track) lokasi di peta dan periksa kelayakan IDPEL.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:gap-2.5">
          <div className="flex items-center gap-1.5 border-2 border-neo-border px-2.5 py-1.5 rounded-sm bg-white shadow-[2px_2px_0_#0a0a0a]">
            <label className="text-xs font-bold text-neo-black">ID:</label>
            <input
              type="number"
              value={processId}
              onChange={(e) => setSearchParams({ process_id: e.target.value })}
              className="w-14 text-xs font-bold text-neo-black focus:outline-none"
            />
          </div>

          <button
            onClick={fetchCandidates}
            className="touch-min px-3 py-1.5 min-h-[38px] border-2 border-neo-border bg-neo-white hover:bg-[#e5e4e7] text-xs font-bold rounded-sm shadow-[2px_2px_0_#0a0a0a] transition active:translate-y-0.5"
          >
            🔄 Refresh
          </button>

          <button
            onClick={handleReset}
            disabled={loading}
            className="touch-min px-3 py-1.5 min-h-[38px] border-2 border-[#dc2626] bg-[#fee2e2] hover:bg-[#fef2f2] text-[#dc2626] text-xs font-bold rounded-sm shadow-[2px_2px_0_#dc2626] transition active:translate-y-0.5 disabled:opacity-50"
            title="Hapus semua data dan mulai dari awal"
          >
            🗑️ Reset
          </button>

          <button
            onClick={handleFinishReview}
            disabled={loading}
            className="touch-min px-4 py-2 min-h-[38px] border-2 border-neo-border bg-neo-accent hover:bg-[#e85a26] text-white text-xs font-bold rounded-sm shadow-[2px_2px_0_#0a0a0a] flex items-center gap-1.5 transition active:translate-y-0.5 disabled:opacity-50"
            title="Selesaikan verifikasi dan lihat rekapitulasi serta download CSV"
          >
            <span>✅ Selesai & Buka Hasil</span>
            <span>→</span>
          </button>
        </div>
      </div>

      {/* Banner Celery Worker Background Processing */}
      {(processStatus === "queued" || processStatus === "running") && (
        <div className="p-3.5 sm:p-4 border-2 border-neo-black bg-[#fef9c3] rounded-sm shadow-[3px_3px_0_#0a0a0a] flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-5 h-5 border-3 border-neo-black border-t-transparent rounded-full animate-spin shrink-0"></div>
            <div>
              <p className="text-xs sm:text-sm font-black text-neo-black">
                {processStatus === "queued" ? "⏳ Proses Masuk Antrean (QUEUED)" : "⚙️ Celery Worker Sedang Memproses Matching (RUNNING)..."}
              </p>
              <p className="text-[11px] text-neo-border">
                Halaman ini otomatis me-refresh data begitu worker menyelesaikan perhitungan spasial.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={fetchCandidates}
            className="px-3 py-1.5 border border-neo-black bg-white text-xs font-bold rounded-xs shadow-[1px_1px_0_#0a0a0a] hover:bg-neo-white shrink-0"
          >
            🔄 Refresh Manual
          </button>
        </div>
      )}

      {/* SUMMARY STATS BOX */}
      {candidates.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 sm:gap-4">
          <div className="p-3.5 sm:p-4 border-2 border-neo-border rounded-sm bg-white shadow-[3px_3px_0_#0a0a0a]">
            <p className="text-[11px] sm:text-xs font-bold text-neo-border uppercase">TOTAL KANDIDAT</p>
            <p className="text-2xl sm:text-3xl font-black mt-1 text-neo-black">{totalCount}</p>
          </div>
          <div className="p-3.5 sm:p-4 border-2 border-[#16a34a] rounded-sm bg-[#dcfce7] shadow-[3px_3px_0_#16a34a]">
            <p className="text-[11px] sm:text-xs font-bold text-[#16a34a] uppercase">VALID</p>
            <p className="text-2xl sm:text-3xl font-black mt-1 text-[#16a34a]">
              {candidates.filter(c => c.is_accepted === 1).length}
            </p>
          </div>
          <div className="p-3.5 sm:p-4 border-2 border-[#dc2626] rounded-sm bg-[#fee2e2] shadow-[3px_3px_0_#dc2626]">
            <p className="text-[11px] sm:text-xs font-bold text-[#dc2626] uppercase">DITOLAK</p>
            <p className="text-2xl sm:text-3xl font-black mt-1 text-[#dc2626]">
              {candidates.filter(c => c.is_accepted === -1).length}
            </p>
          </div>
          <div className="p-3.5 sm:p-4 border-2 border-[#d97706] rounded-sm bg-[#fef3c7] shadow-[3px_3px_0_#d97706]">
            <p className="text-[11px] sm:text-xs font-bold text-[#d97706] uppercase">PENDING</p>
            <p className="text-2xl sm:text-3xl font-black mt-1 text-[#d97706]">
              {candidates.filter(c => c.is_accepted === 0).length}
            </p>
          </div>
        </div>
      )}

      {/* PETA INTERAKTIF */}
      <div className="p-3.5 sm:p-4 border-2 border-neo-border rounded-sm bg-white shadow-[3px_3px_0_#0a0a0a] space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-xs sm:text-sm font-black text-neo-black">
              📍 Peta Geografis Spasial (Tracking Interaktif)
            </h2>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-[10px] sm:text-[11px] font-bold">
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 bg-[#2563eb] rounded-xs inline-block"></span>
              <span>Target</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 bg-[#16a34a] rounded-full inline-block"></span>
              <span>Valid</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 bg-[#ea580c] rounded-full inline-block"></span>
              <span>Tanpa IDPEL</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 bg-[#7c3aed] rounded-full inline-block"></span>
              <span>&lt; 5m</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 bg-[#dc2626] rounded-xs inline-block"></span>
              <span>Luar Jangkauan</span>
            </span>
          </div>
        </div>

        {/* Map Canvas dengan tinggi adaptif & perlindungan gesture */}
        <div
          ref={mapContainerRef}
          className="border-2 border-neo-border rounded-sm bg-[#e5e4e7] w-full h-[270px] sm:h-[350px] md:h-[420px] relative z-10"
        ></div>

        <p className="text-[11px] text-neo-border bg-neo-white p-2.5 border border-neo-border rounded-xs">
          💡 <strong>Interaktivitas Peta:</strong> Klik salah satu baris pada tabel di bawah untuk membuat peta langsung <strong>terbang (fly-to)</strong> dan fokus pada koordinat titik tersebut. Klik marker untuk membuka langsung di <strong>Google Maps</strong>.
        </p>
      </div>

      {/* MULTI-FILTER CHECKBOX PANEL */}
      <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] space-y-4">
        <h3 className="text-sm font-bold flex items-center gap-2">
          🔍 Filter Multi-Kriteria (Bisa pilih lebih dari satu)
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* KELAYAKAN DATA */}
          <div>
            <h4 className="text-xs font-bold mb-2 flex items-center gap-1">
              <span className="w-2 h-2 bg-[#16a34a] rounded-full"></span>
              Kelayakan Data
            </h4>
            <div className="space-y-1.5">
              {[
                { value: "valid", label: "Valid (Ada IDPEL)", color: "#16a34a" },
                { value: "no-idpel", label: "Tanpa IDPEL", color: "#ea580c" },
                { value: "idpel-kosong", label: "IDPEL Kosong", color: "#f97316" },
                { value: "luar-jangkauan", label: "Luar Jangkauan", color: "#dc2626" },
                { value: "kurang-5m", label: "< 5m (Anomali Jarak)", color: "#7c3aed" },
              ].map(({ value, label, color }) => (
                <label key={value} className="flex items-center gap-2 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={validityFilters.includes(value)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setValidityFilters([...validityFilters, value]);
                      } else {
                        setValidityFilters(validityFilters.filter(v => v !== value));
                      }
                      setCurrentPage(1);
                    }}
                    className="border border-neo-border rounded-sm"
                  />
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }}></span>
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* LAYANAN */}
          <div>
            <h4 className="text-xs font-bold mb-2 flex items-center gap-1">
              <span className="w-2 h-2 bg-[#2563eb] rounded-full"></span>
              Jenis Layanan
            </h4>
            <div className="space-y-1.5">
              {["PASCABAYAR", "PRABAYAR"].map((layanan) => (
                <label key={layanan} className="flex items-center gap-2 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={layananFilters.includes(layanan)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setLayananFilters([...layananFilters, layanan]);
                      } else {
                        setLayananFilters(layananFilters.filter(v => v !== layanan));
                      }
                      setCurrentPage(1);
                    }}
                    className="border border-neo-border rounded-sm"
                  />
                  <span className={`neo-highlight px-2 py-0.5 text-[10px] rounded ${layanan === "PRABAYAR" ? "bg-blue-100 text-blue-800" : "bg-gray-100 text-gray-800"}`}>
                    {layanan}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* IDPEL STATUS */}
          <div>
            <h4 className="text-xs font-bold mb-2 flex items-center gap-1">
              <span className="w-2 h-2 bg-[#ff6b35] rounded-full"></span>
              Status IDPEL
            </h4>
            <div className="space-y-1.5">
              {[
                { value: "ada", label: "IDPEL Valid (Ada)" },
                { value: "kosong", label: "IDPEL Kosong" },
                { value: "tidak-ditemukan", label: "IDPEL Tidak Ditemukan" },
                { value: "unassigned", label: "IDPEL UNASSIGNED-*" },
              ].map(({ value, label }) => (
                <label key={value} className="flex items-center gap-2 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={idpelFilters.includes(value)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setIdpelFilters([...idpelFilters, value]);
                      } else {
                        setIdpelFilters(idpelFilters.filter(v => v !== value));
                      }
                      setCurrentPage(1);
                    }}
                    className="border border-neo-border rounded-sm"
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* STATUS REVIEW (existing) */}
        <div className="pt-2 border-t border-neo-border">
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <label className="font-bold mr-2 text-xs">Status Review:</label>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="border border-neo-border p-1.5 rounded-sm bg-white text-xs"
              >
                <option value="all">Semua</option>
                <option value="0">Menunggu (Pending)</option>
                <option value="1">Valid (Disetujui)</option>
                <option value="-1">Ditolak</option>
              </select>
            </div>

            <div className="ml-auto text-[11px] text-neo-border">
              Total data: <strong>{totalCount}</strong> | Menampilkan halaman <strong>{currentPage}</strong> dari <strong>{totalPages}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* BULK ACTION BUTTON */}
      {candidates.length > 0 && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={handleBulkDecision}
            className={`px-4 py-2 text-xs font-bold border rounded-sm transition ${
              candidates.every((c) => c.is_accepted === 1)
                ? "border-[#dc2626] bg-[#fee2e2] text-[#dc2626] shadow-[0_2px_0_#dc2626] hover:bg-[#fef2f2]"
                : "border-[#16a34a] bg-[#dcfce7] text-[#16a34a] shadow-[0_2px_0_#16a34a] hover:bg-[#f0fdf4]"
            }`}
          >
            {candidates.every((c) => c.is_accepted === 1) ? (
              "✕ Hapus Semua (Halaman Ini)"
            ) : (
              "✓ Validasi Semua (Halaman Ini)"
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
      ) : candidates.length === 0 ? (
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
        <div className="border-2 border-neo-border rounded-sm bg-white shadow-[3px_3px_0_#0a0a0a] overflow-x-auto neo-scrollbar">
          <table className="w-full text-left text-xs border-collapse whitespace-nowrap min-w-[950px]">
            <thead className="bg-[#e5e4e7] border-b-2 border-neo-border font-bold">
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
              {candidates.map((c, index) => {
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
                      isSelected ? "bg-[#fef9c3] font-semibold" : "hover:bg-[#f5f5f5]"
                    }`}
                  >
                    <td className="p-3 border-r border-neo-border font-bold text-center">
                      #{(currentPage - 1) * rowsPerPage + index + 1}
                    </td>
                    <td className="p-3 border-r border-neo-border">
                      <div className="font-semibold text-neo-black">{c.target_ref}</div>
                      <div className="text-[10px] text-gray-500 font-mono">
                        {c.target_lat.toFixed(5)}, {c.target_lon.toFixed(5)}
                      </div>
                    </td>
                    <td className="p-3 border-r border-neo-border font-semibold">
                      {c.validity_status === "DILUAR_RADIUS" ? (
                        <span className="text-[#dc2626] font-bold">🔴 Di Luar Radius</span>
                      ) : c.validity_status === "IDPEL_KOSONG" ? (
                        <span className="text-[#ea580c] font-bold">IDPEL KOSONG</span>
                      ) : c.validity_status === "TIDAK_DITEMUKAN" ? (
                        <span className="text-[#f97316]">TIDAK DITEMUKAN</span>
                      ) : c.validity_status === "VALID" && c.candidate_idpel && !c.candidate_idpel.startsWith("UNASSIGNED-") && c.candidate_idpel !== "IDPEL_KOSONG" ? (
                        <div>
                          <span className="text-[#16a34a] font-bold">✓ VALID</span>
                          <div className="text-[10px] font-mono text-gray-500">{c.candidate_idpel}</div>
                        </div>
                      ) : c.validity_status === "VALID" ? (
                        <span className="text-[#16a34a] font-bold">✓ VALID</span>
                      ) : c.validity_status === "PERLU_KONFIRMASI_IDPEL" ? (
                        <span className="text-[#ca8a04]">PERLU KONFIRMASI</span>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                    <td className="p-3 border-r border-neo-border">{c.candidate_nama || "-"}</td>
                    <td className="p-3 border-r border-neo-border">
                      <span className={`neo-highlight px-1.5 py-1 rounded text-[10px] font-bold ${
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
                        <span className="neo-highlight px-2 py-1 border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded text-[10px] font-bold">
                          🔴 LUAR JANGKAUAN
                        </span>
                      ) : hasRealIdpel ? (
                        <span className="neo-highlight px-2 py-1 border border-[#16a34a] bg-[#dcfce7] text-[#16a34a] rounded text-[10px] font-bold">
                          ✓ VALID (ASLI)
                        </span>
                      ) : (
                        <span className="neo-highlight px-2 py-1 border border-[#ea580c] bg-[#ffedd5] text-[#ea580c] rounded text-[10px] font-bold">
                          ⚠️ KONFIRMASI ULANG
                        </span>
                      )}
                    </td>
                    <td className="p-3 border-r border-neo-border text-center" onClick={(e) => e.stopPropagation()}>
                      <a
                        href={gmapsUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="touch-min px-2.5 py-1 border border-neo-border bg-white hover:bg-[#e5e4e7] rounded text-[10px] font-bold inline-flex items-center gap-1 shadow-[0_1px_0_#0a0a0a]"
                      >
                        📍 GMaps
                      </a>
                    </td>
                    <td className="p-3 border-r border-neo-border">
                      {c.is_accepted === 1 && (
                        <span className="neo-highlight px-2 py-1 border border-[#16a34a] bg-[#dcfce7] text-[#16a34a] rounded text-[10px] font-bold">
                          VALID
                        </span>
                      )}
                      {c.is_accepted === -1 && (
                        <span className="neo-highlight px-2 py-1 border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded text-[10px] font-bold">
                          DITOLAK
                        </span>
                      )}
                      {c.is_accepted === 0 && (
                        <span className="px-2 py-1 border border-[#d97706] bg-[#fef3c7] text-[#d97706] rounded text-[10px] font-bold">
                          PENDING
                        </span>
                      )}
                    </td>
                    <td className="p-3 text-center" onClick={(e) => e.stopPropagation()}>
                      <div className="flex justify-center items-center gap-1.5">
                        <button
                          onClick={(e) => handleDecision(c.id, 1, e)}
                          className={`touch-min px-3 py-1.5 min-h-[36px] border-2 border-neo-border rounded text-xs font-bold shadow-[1px_1px_0_#0a0a0a] transition active:translate-y-0.5 ${
                            c.is_accepted === 1
                              ? "bg-[#16a34a] text-white"
                              : "bg-white text-[#16a34a] hover:bg-[#dcfce7]"
                          }`}
                        >
                          ✓ Valid
                        </button>
                        <button
                          onClick={(e) => handleDecision(c.id, -1, e)}
                          className={`touch-min px-3 py-1.5 min-h-[36px] border-2 border-neo-border rounded text-xs font-bold shadow-[1px_1px_0_#0a0a0a] transition active:translate-y-0.5 ${
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

      {/* PAGINATION CONTROLS */}
      {totalCandidates > rowsPerPage && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 sm:p-4 border-2 border-neo-border rounded-sm bg-white shadow-[2px_2px_0_#0a0a0a]">
          <div className="flex items-center gap-2">
            <label className="text-xs font-bold text-neo-black">Baris per halaman:</label>
            <select
              value={rowsPerPage}
              onChange={(e) => {
                setRowsPerPage(Number(e.target.value));
                setCurrentPage(1);
              }}
              className="border-2 border-neo-border p-1.5 rounded-sm text-xs bg-white font-bold"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={250}>250</option>
            </select>
          </div>

          <div className="text-xs font-bold text-neo-black">
            Halaman <strong>{currentPage}</strong> dari <strong>{totalPages}</strong> ({totalCandidates} total)
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <button
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="touch-min px-4 py-2 min-h-[40px] border-2 border-neo-border bg-white hover:bg-[#e5e4e7] text-xs font-bold rounded-sm shadow-[1px_1px_0_#0a0a0a] transition active:translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed flex-1 sm:flex-initial"
            >
              ← Sebelumnya
            </button>
            <button
              onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
              disabled={currentPage === totalPages}
              className="touch-min px-4 py-2 min-h-[40px] border-2 border-neo-border bg-white hover:bg-[#e5e4e7] text-xs font-bold rounded-sm shadow-[1px_1px_0_#0a0a0a] transition active:translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed flex-1 sm:flex-initial"
            >
              Selanjutnya →
            </button>
          </div>
        </div>
      )}

      {/* Bottom Action Finish */}
      {candidates.length > 0 && (
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between p-4 sm:p-5 border-2 border-neo-border rounded-sm bg-white shadow-[3px_3px_0_#0a0a0a] gap-3">
          <div>
            <span className="text-xs sm:text-sm font-bold text-neo-black block">Sudah selesai memverifikasi kandidat?</span>
            <p className="text-[11px] sm:text-xs text-neo-border mt-0.5">Lanjutkan untuk melihat statistik final dan mengunduh laporan CSV.</p>
          </div>
          <button
            onClick={handleFinishReview}
            disabled={loading}
            className="touch-min px-5 py-3 min-h-[44px] border-2 border-neo-border bg-neo-black text-white text-xs sm:text-sm font-bold rounded-sm shadow-[2px_2px_0_#ff6b35] hover:bg-[#222] transition active:translate-y-0.5 disabled:opacity-50 shrink-0 text-center"
          >
            ✅ Selesaikan Review & Buka Hasil Rekonsiliasi →
          </button>
        </div>
      )}
    </div>
  );
}
