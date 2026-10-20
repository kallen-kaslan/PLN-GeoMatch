import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { api, API_BASE_URL } from "@/lib/api";

interface ProcessSummary {
  process_id: number;
  process_name: string;
  radius_meters: number;
  total_targets: number;
  total_candidates: number;
  valid_count: number;
  rejected_count: number;
  pending_count: number;
  matching_status: string;
  review_status: string;
}

export default function ResultPage() {
  const [searchParams] = useSearchParams();
  const initialId = searchParams.get("process_id") || "1";

  const [processId, setProcessId] = useState<string>(initialId);
  const [summary, setSummary] = useState<ProcessSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async () => {
    if (!processId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/process/${processId}/summary`);
      setSummary(res.data);
      if (res.data?.process_id && String(res.data.process_id) !== processId && !res.data.is_empty) {
        setProcessId(String(res.data.process_id));
      }
    } catch (err: any) {
      if (err.status === 502) {
        setError("Koneksi ke server backend terputus (502 Bad Gateway). Pastikan backend FastAPI sedang berjalan di port 8000.");
      } else {
        setError(err.message || "Gagal memuat ringkasan hasil proses.");
      }
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [processId]);

  const handleDownload = () => {
    // Direct link download endpoint
    window.open(`${API_BASE_URL}/process/${processId}/export`, "_blank");
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold mb-1">Hasil Rekonsiliasi & Ekspor</h1>
          <p className="text-sm text-[#333333]">
            Ringkasan akhir status pencocokan koordinat per identitas proses unik.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-[#0a0a0a]">Pilih ID Proses:</label>
          <input
            type="number"
            value={processId}
            onChange={(e) => setProcessId(e.target.value)}
            className="w-20 border border-[#333333] p-1.5 rounded-sm text-sm bg-white"
          />
        </div>
      </div>

      {error && (
        <div className="p-4 border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded-sm text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-sm text-[#333333]">Memuat ringkasan proses...</div>
      ) : summary && !((summary as any).is_empty) ? (
        <div className="space-y-6">
          {/* Header Info Box */}
          <div className="p-4 border border-[#333333] rounded-sm bg-white shadow-[0_4px_0_#0a0a0a]">
            <h2 className="text-lg font-bold text-[#0a0a0a]">{summary.process_name}</h2>
            <p className="text-xs text-[#333333] mt-1">
              Process ID: #{summary.process_id} | Radius Matching: {summary.radius_meters} meter
            </p>
          </div>

          {/* Statistik Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 border border-[#333333] rounded-sm bg-white shadow-[0_4px_0_#0a0a0a]">
              <p className="text-xs font-semibold text-[#333333]">TOTAL TARGET</p>
              <p className="text-3xl font-extrabold mt-1 text-[#0a0a0a]">{summary.total_targets}</p>
            </div>
            <div className="p-4 border border-[#16a34a] rounded-sm bg-[#dcfce7] shadow-[0_4px_0_#0a0a0a]">
              <p className="text-xs font-semibold text-[#16a34a]">TERVALIDASI (VALID)</p>
              <p className="text-3xl font-extrabold mt-1 text-[#16a34a]">{summary.valid_count}</p>
            </div>
            <div className="p-4 border border-[#dc2626] rounded-sm bg-[#fee2e2] shadow-[0_4px_0_#0a0a0a]">
              <p className="text-xs font-semibold text-[#dc2626]">DITOLAK</p>
              <p className="text-3xl font-extrabold mt-1 text-[#dc2626]">{summary.rejected_count}</p>
            </div>
            <div className="p-4 border border-[#d97706] rounded-sm bg-[#fef3c7] shadow-[0_4px_0_#0a0a0a]">
              <p className="text-xs font-semibold text-[#d97706]">MENUNGGU REVIEW</p>
              <p className="text-3xl font-extrabold mt-1 text-[#d97706]">{summary.pending_count}</p>
            </div>
          </div>

          {/* Action Box */}
          <div className="flex flex-col sm:flex-row items-center justify-between p-6 border border-[#333333] rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] gap-4">
            <div>
              <h3 className="font-bold text-sm">Unduh Laporan Hasil</h3>
              <p className="text-xs text-[#333333] mt-0.5">
                Download file CSV berisi koordinat target, IDPEL kandidat, dan keputusan petugas.
              </p>
            </div>
            <div className="flex gap-3">
              <Link
                to={`/candidates?process_id=${summary.process_id}`}
                className="px-4 py-2 border border-[#333333] bg-white text-[#0a0a0a] text-xs font-semibold rounded-sm shadow-[0_2px_0_#0a0a0a] hover:bg-[#e5e4e7]"
              >
                Kembali ke Review →
              </Link>
              <button
                onClick={handleDownload}
                className="px-6 py-2 border border-[#333333] bg-[#0a0a0a] text-white text-xs font-semibold rounded-sm shadow-[0_2px_0_#0a0a0a] hover:bg-[#1a1a1a]"
              >
                Unduh Data Rekonsiliasi (.CSV) ⬇
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-8 border border-dashed border-[#333333] rounded-sm text-center bg-white space-y-3 shadow-[0_2px_0_#0a0a0a]">
          <p className="text-sm font-semibold text-[#0a0a0a]">Belum Ada Hasil Rekonsiliasi Tersedia</p>
          <p className="text-xs text-[#333333]">
            Silakan jalankan proses matching terlebih dahulu atau gunakan Quick Demo untuk mengisi data secara instan.
          </p>
          <div className="pt-2">
            <Link
              to="/upload"
              className="inline-block px-4 py-2 border border-[#333333] bg-[#ff6b35] text-white text-xs font-bold rounded-sm shadow-[0_2px_0_#0a0a0a] hover:bg-[#e85a26]"
            >
              ⚡ Buka Halaman Upload & Jalankan Quick Demo →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
