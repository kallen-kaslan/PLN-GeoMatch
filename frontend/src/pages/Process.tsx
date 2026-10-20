import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useNavigate } from "react-router-dom";

export default function ProcessPage() {
  const navigate = useNavigate();

  const [processName, setProcessName] = useState("Pencocokan Koordinat PLN - " + new Date().toISOString().slice(0, 10));
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
    // Ambil daftar batch yang tersedia
    api.get("/upload/batches")
      .then((res) => {
        setBatches(res.data);
        // Default ke batch target / koordinat kosong jika ada
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
  }, []);

  const handleStartMatching = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      let batchIdToUse = targetBatchId;

      // Jika mode manual single koordinat, kita buat batch sementara atau gunakan batch aktif
      if (activeTab === "manual") {
        // Upload batch koordinat manual
        const manualFormData = new FormData();
        const csvContent = `NOMOR_METER,LATITUDEY,LONGITUDEX,KETERANGAN\n${manualRef},${manualLat},${manualLon},Input Manual Petugas\n`;
        const blob = new Blob([csvContent], { type: "text/csv" });
        manualFormData.append("file", blob, "manual_single_target.csv");
        manualFormData.append("dataset_type", "koordinat_kosong");

        const uploadRes = await api.post("/upload/", manualFormData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        batchIdToUse = String(uploadRes.data.id);
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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-1">Input Manual & Konfigurasi Pencocokan</h1>
        <p className="text-sm text-[#333333]">
          Tentukan parameter spasial, pilih batch koordinat kosong, atau input manual satu titik untuk dicari kandidat IDPEL-nya di Master Sisa.
        </p>
      </div>

      {error && (
        <div className="p-4 border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded-sm text-sm font-medium">
          Error: {error}
        </div>
      )}

      {/* Tab Switcher: Batch vs Single Manual Coordinate */}
      <div className="flex gap-2 border-b border-[#333333] pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("batch")}
          className={`px-4 py-2 border border-[#333333] rounded-sm text-xs font-bold transition ${
            activeTab === "batch"
              ? "bg-[#0a0a0a] text-white shadow-[0_2px_0_#0a0a0a]"
              : "bg-white text-[#0a0a0a] hover:bg-[#e5e4e7]"
          }`}
        >
          📂 Pencocokan Berdasarkan Batch Data
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("manual")}
          className={`px-4 py-2 border border-[#333333] rounded-sm text-xs font-bold transition ${
            activeTab === "manual"
              ? "bg-[#0a0a0a] text-white shadow-[0_2px_0_#0a0a0a]"
              : "bg-white text-[#0a0a0a] hover:bg-[#e5e4e7]"
          }`}
        >
          📍 Input Manual 1 Titik Koordinat Lapangan
        </button>
      </div>

      <div className="p-6 border border-[#333333] rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] max-w-xl">
        <form onSubmit={handleStartMatching} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[#0a0a0a] mb-1">
              Nama Sesi Pencocokan
            </label>
            <input
              type="text"
              required
              value={processName}
              onChange={(e) => setProcessName(e.target.value)}
              className="w-full border border-[#333333] p-2 rounded-sm text-xs bg-white"
            />
          </div>

          {activeTab === "batch" ? (
            <div>
              <label className="block text-xs font-semibold text-[#0a0a0a] mb-1">
                Pilih Batch Koordinat Kosong / Target
              </label>
              {batches.length === 0 ? (
                <div className="p-3 border border-dashed border-[#333333] text-xs text-[#333333]">
                  Belum ada batch terupload. Silakan unggah data di menu <strong>Upload & Bentuk Master</strong> atau gunakan Quick Demo.
                </div>
              ) : (
                <select
                  required
                  value={targetBatchId}
                  onChange={(e) => setTargetBatchId(e.target.value)}
                  className="w-full border border-[#333333] p-2 rounded-sm text-xs bg-white"
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
            <div className="p-4 border border-[#333333] bg-[#fafafa] rounded-sm space-y-3">
              <h3 className="text-xs font-bold text-[#0a0a0a]">Data Titik Lapangan Manual:</h3>
              <div>
                <label className="block text-[11px] font-semibold text-[#333333] mb-1">Nama / ID Titik / No. Tiang</label>
                <input
                  type="text"
                  required
                  value={manualRef}
                  onChange={(e) => setManualRef(e.target.value)}
                  className="w-full border border-[#333333] p-1.5 rounded-sm text-xs bg-white"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] font-semibold text-[#333333] mb-1">Latitude (Y)</label>
                  <input
                    type="text"
                    required
                    value={manualLat}
                    onChange={(e) => setManualLat(e.target.value)}
                    className="w-full border border-[#333333] p-1.5 rounded-sm text-xs bg-white"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-[#333333] mb-1">Longitude (X)</label>
                  <input
                    type="text"
                    required
                    value={manualLon}
                    onChange={(e) => setManualLon(e.target.value)}
                    className="w-full border border-[#333333] p-1.5 rounded-sm text-xs bg-white"
                  />
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[#0a0a0a] mb-1">
                Radius Maksimal (Meter)
              </label>
              <input
                type="number"
                min="5"
                max="1000"
                value={radiusMeters}
                onChange={(e) => setRadiusMeters(Number(e.target.value))}
                className="w-full border border-[#333333] p-2 rounded-sm text-xs bg-white"
              />
              <span className="text-[10px] text-[#333333]">Threshold default: 150 meter</span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#0a0a0a] mb-1">
                Max Kandidat / Titik
              </label>
              <input
                type="number"
                min="1"
                max="10"
                value={maxCandidates}
                onChange={(e) => setMaxCandidates(Number(e.target.value))}
                className="w-full border border-[#333333] p-2 rounded-sm text-xs bg-white"
              />
              <span className="text-[10px] text-[#333333]">Urutan rank terdekat</span>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 border border-[#333333] bg-[#0a0a0a] text-white text-xs font-bold rounded-sm shadow-[0_2px_0_#0a0a0a] hover:bg-[#1a1a1a] disabled:opacity-50"
          >
            {loading ? "Menjalankan Pencocokan Spasial..." : "🚀 Jalankan Pencocokan Koordinat"}
          </button>
        </form>
      </div>

      {result && (
        <div className="p-6 border border-[#16a34a] bg-[#dcfce7] rounded-sm shadow-[0_4px_0_#0a0a0a] max-w-xl space-y-3">
          <h2 className="text-base font-bold text-[#16a34a]">Pencocokan Spasial Selesai!</h2>
          <div className="text-xs text-[#0a0a0a] space-y-1">
            <p>ID Proses: <strong>#{result.process_id}</strong></p>
            <p>Total Titik Koordinat: <strong>{result.total_targets}</strong></p>
            <p>Titik Menemukan Kandidat IDPEL: <strong>{result.matched_targets}</strong></p>
            <p>Titik Anomali (Di luar radius): <strong>{result.unmatched_targets}</strong></p>
            <p>Total Pasangan Kandidat yang Terhubung: <strong>{result.total_candidates_found}</strong></p>
          </div>
          <button
            onClick={() => navigate(`/candidates?process_id=${result.process_id}`)}
            className="mt-2 w-full py-2 px-4 border border-[#333333] bg-[#0a0a0a] text-white text-xs font-bold rounded-sm shadow-[0_2px_0_#0a0a0a] hover:bg-[#222]"
          >
            🗺️ Buka Peta & Review Spasial Koordinat →
          </button>
        </div>
      )}
    </div>
  );
}
