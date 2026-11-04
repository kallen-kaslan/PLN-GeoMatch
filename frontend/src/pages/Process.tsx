import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { Compass, FolderCheck, MapPin, Play, ArrowRight, CheckCircle2 } from "lucide-react";
import { useAppStore } from "@/store/app";

export default function ProcessPage() {
  const { user } = useAppStore();
  const canOperate = user?.role === "admin" || user?.role === "analis";
  const navigate = useNavigate();

  // Lazy initializer to avoid impure Date call during render
  const [processName, setProcessName] = useState(() => {
    return "Pencocokan Koordinat PLN - " + new Date().toISOString().slice(0, 10);
  });
  const [batches, setBatches] = useState<any[]>([]);
  const [targetBatchId, setTargetBatchId] = useState<string>("");
  const [radiusMeters, setRadiusMeters] = useState<number>(150);
  const [maxCandidates, setMaxCandidates] = useState<number>(5);

  // Tab mode: Batch Matching vs Manual Single Coordinate Test
  const [activeTab, setActiveTab] = useState<"batch" | "manual">("batch");
  const [manualLat, setManualLat] = useState<string>("-6.20890");
  const [manualLon, setManualLon] = useState<string>("106.84570");
  const [manualRef, setManualRef] = useState<string>("TIANG-UJI-01");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    api.get("/upload/batches")
      .then((res) => {
        if (!isMounted) return;
        setBatches(res.data);
        const targetBatch = res.data.find(
          (b: any) => b.dataset_type === "koordinat_kosong" || b.dataset_type === "target"
        );
        if (targetBatch) {
          setTargetBatchId(String(targetBatch.id));
        } else if (res.data.length > 0) {
          setTargetBatchId(String(res.data[0].id));
        }
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, []);

  const handleStartMatching = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      let batchIdToUse = targetBatchId;

      if (activeTab === "manual") {
        const manualFormData = new FormData();
        const csvContent = `NOMOR_METER,LATITUDEY,LONGITUDEX,KETERANGAN\n${manualRef},${manualLat},${manualLon},Input Manual Petugas\n`;
        const blob = new Blob([csvContent], { type: "text/csv" });
        manualFormData.append("file", blob, "manual_single_target.csv");
        manualFormData.append("dataset_type", "koordinat_kosong");

        const uploadRes = await api.post("/upload/", manualFormData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        batchIdToUse = String(uploadRes.data.id);
        await api.post("/upload/confirm-mapping", {
          batch_id: Number(batchIdToUse),
          column_mapping: {
            nomor_meter: "NOMOR_METER",
            lat: "LATITUDEY",
            lon: "LONGITUDEX",
          },
        });
      }

      if (!batchIdToUse) {
        throw new Error("Pilih batch target / koordinat kosong yang valid.");
      }

      const res = await api.post("/process/run-matching", {
        process_name: processName,
        target_batch_id: Number(batchIdToUse),
        radius_meters: Number(radiusMeters),
        max_candidates: Number(maxCandidates),
      });

      setResult(res.data);
    } catch (err: any) {
      setError(err.message || "Gagal menjalankan proses pencocokan spasial.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5 sm:space-y-6">
      <div className="border-b border-ui-border pb-3">
        <h1 className="fluid-h1 font-semibold tracking-tight text-neo-black">
          Input Manual & Konfigurasi Pencocokan
        </h1>
        <p className="text-xs sm:text-sm text-ui-muted mt-0.5">
          Tentukan parameter spasial, pilih batch koordinat kosong, atau input manual satu titik untuk dicari kandidat IDPEL-nya di Master Sisa.
        </p>
      </div>

      {error && (
        <div className="p-3.5 sm:p-4 border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded-lg text-xs sm:text-sm font-semibold ">
          Error: {error}
        </div>
      )}

      {/* Tab Switcher: Batch vs Single Manual Coordinate */}
      <div className="flex flex-col sm:flex-row gap-2 border-b border-ui-border pb-2.5">
        <button
          type="button"
          onClick={() => setActiveTab("batch")}
          className={`flex items-center justify-center gap-2 px-4 py-2.5 touch-min border rounded-lg text-xs sm:text-sm font-semibold transition  ${
            activeTab === "batch"
              ? "border-neo-black bg-ui-primary text-white "
              : "border-ui-border bg-white text-neo-black hover:bg-slate-100 "
          }`}
        >
          <FolderCheck size={16} />
          <span>Pencocokan Berdasarkan Batch Data</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("manual")}
          className={`flex items-center justify-center gap-2 px-4 py-2.5 touch-min border rounded-lg text-xs sm:text-sm font-semibold transition  ${
            activeTab === "manual"
              ? "border-neo-black bg-ui-primary text-white "
              : "border-ui-border bg-white text-neo-black hover:bg-slate-100 "
          }`}
        >
          <MapPin size={16} />
          <span>Input Manual 1 Titik Koordinat</span>
        </button>
      </div>

      {/* Main Form Container */}
      <div className="p-4 sm:p-6 border border-ui-border rounded-lg bg-white  max-w-2xl w-full">
        <form onSubmit={handleStartMatching} className="space-y-4 sm:space-y-5">
          <div>
            <label className="block text-xs sm:text-sm font-semibold text-neo-black mb-1.5">
              Nama Sesi Pencocokan <span className="text-[#dc2626]">*</span>
            </label>
            <input
              type="text"
              required
              value={processName}
              onChange={(e) => setProcessName(e.target.value)}
              className="w-full border border-ui-border p-2.5 rounded-lg mobile-input bg-white text-neo-black focus:outline-none focus:ring-2 focus:ring-neo-accent"
              placeholder="Contoh: Pencocokan Koordinat PLN Gardu A"
            />
          </div>

          {activeTab === "batch" ? (
            <div>
              <label className="block text-xs sm:text-sm font-semibold text-neo-black mb-1.5">
                Pilih Batch Koordinat Kosong / Target <span className="text-[#dc2626]">*</span>
              </label>
              {batches.length === 0 ? (
                <div className="p-3.5 border border-dashed border-ui-border rounded-lg text-xs text-ui-muted bg-neo-white">
                  Belum ada batch terupload. Silakan unggah data di menu <strong>Upload & Bentuk Master</strong> atau jalankan Quick Demo.
                </div>
              ) : (
                <select
                  required
                  value={targetBatchId}
                  onChange={(e) => setTargetBatchId(e.target.value)}
                  className="w-full border border-ui-border p-2.5 rounded-lg mobile-input bg-white text-neo-black focus:outline-none focus:ring-2 focus:ring-neo-accent"
                >
                  <option value="">-- Pilih Batch Target --</option>
                  {batches.map((b) => (
                    <option key={b.id} value={b.id}>
                      #{b.id} - {b.filename} ({b.dataset_type.toUpperCase()} - {b.total_rows} baris)
                    </option>
                  ))}
                </select>
              )}
            </div>
          ) : (
            <div className="p-3.5 sm:p-4 border border-ui-border bg-[#fafafa] rounded-lg space-y-3.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-neo-black uppercase tracking-wide">
                <Compass size={16} />
                <span>Data Titik Lapangan Manual</span>
              </div>
              <div>
                <label className="block text-xs font-semibold text-neo-black mb-1">
                  Nama / ID Titik / No. Tiang <span className="text-[#dc2626]">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={manualRef}
                  onChange={(e) => setManualRef(e.target.value)}
                  className="w-full border border-ui-border p-2 rounded-lg mobile-input bg-white text-neo-black"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-neo-black mb-1">
                    Latitude (Y) <span className="text-[#dc2626]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={manualLat}
                    onChange={(e) => setManualLat(e.target.value)}
                    className="w-full border border-ui-border p-2 rounded-lg mobile-input bg-white text-neo-black font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-neo-black mb-1">
                    Longitude (X) <span className="text-[#dc2626]">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={manualLon}
                    onChange={(e) => setManualLon(e.target.value)}
                    className="w-full border border-ui-border p-2 rounded-lg mobile-input bg-white text-neo-black font-mono"
                  />
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            <div>
              <label className="block text-xs sm:text-sm font-semibold text-neo-black mb-1">
                Radius Maksimal (Meter)
              </label>
              <input
                type="number"
                min="5"
                max="1000"
                value={radiusMeters}
                onChange={(e) => setRadiusMeters(Number(e.target.value))}
                className="w-full border border-ui-border p-2 rounded-lg mobile-input bg-white text-neo-black font-mono"
              />
              <span className="text-xs text-ui-muted mt-0.5 block">Default rekomendasi: 150 meter</span>
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-semibold text-neo-black mb-1">
                Max Kandidat / Titik
              </label>
              <input
                type="number"
                min="1"
                max="10"
                value={maxCandidates}
                onChange={(e) => setMaxCandidates(Number(e.target.value))}
                className="w-full border border-ui-border p-2 rounded-lg mobile-input bg-white text-neo-black font-mono"
              />
              <span className="text-xs text-ui-muted mt-0.5 block">Urutan ranking jarak terdekat</span>
            </div>
          </div>

          {canOperate ? (
            <button
              type="submit"
              disabled={loading}
              className="w-full touch-min py-3 px-4 border border-neo-black bg-ui-primary text-white text-xs sm:text-sm font-semibold rounded-lg  hover:bg-ui-primary-hover transition  disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Menjalankan Pencocokan Spasial...</span>
                </>
              ) : (
                <>
                  <Play size={16} />
                  <span>Jalankan Pencocokan Koordinat</span>
                </>
              )}
            </button>
          ) : (
            <div className="p-3 text-center rounded-lg border border-ui-border bg-gray-50 text-xs text-ui-muted">
              Akun auditor memiliki akses lihat data saja. Proses pencocokan hanya dapat dijalankan oleh admin dan analis.
            </div>
          )}
        </form>
      </div>

      {/* Matching Result Summary */}
      {result && (
        <div className="p-4 sm:p-6 border border-[#16a34a] bg-[#dcfce7] rounded-lg  max-w-2xl w-full space-y-3.5">
          <div className="flex items-center gap-2 text-[#16a34a]">
            <CheckCircle2 size={22} />
            <h2 className="text-base sm:text-lg font-semibold">Pencocokan Spasial Selesai!</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-neo-black bg-white/70 p-3 rounded-lg border border-[#16a34a]/30">
            <p>ID Sesi: <strong>#{result.process_id}</strong></p>
            <p>Total Titik: <strong>{result.total_targets}</strong></p>
            <p className="text-[#16a34a]">Menemukan Kandidat: <strong>{result.matched_targets}</strong></p>
            <p className="text-[#dc2626]">Di Luar Radius: <strong>{result.unmatched_targets}</strong></p>
            <p className="sm:col-span-2">Total Pasangan Terhubung: <strong>{result.total_candidates_found}</strong></p>
          </div>

          <button
            onClick={() => navigate(`/candidates?process_id=${result.process_id}`)}
            className="w-full touch-min py-3 px-4 border border-ui-border bg-ui-primary text-white text-xs sm:text-sm font-semibold rounded-lg  hover:bg-ui-primary-hover transition  flex items-center justify-center gap-2"
          >
            <span>Buka Peta & Review Spasial Koordinat</span>
            <ArrowRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

