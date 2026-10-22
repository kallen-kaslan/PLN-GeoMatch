import { useState, useEffect, useCallback } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { api, API_BASE_URL } from "@/lib/api";
import { Download, ArrowLeft, CheckCircle2, XCircle, Clock, FileSpreadsheet, RefreshCw, Trash2 } from "lucide-react";

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(() => {
    if (!processId) return;
    api.get(`/process/${processId}/summary`)
      .then((res) => {
        setSummary(res.data);
        setError(null);
        if (res.data?.process_id && String(res.data.process_id) !== processId && !res.data.is_empty) {
          setProcessId(String(res.data.process_id));
        }
      })
      .catch((err: any) => {
        if (err.status === 502) {
          setError("Koneksi ke server backend terputus (502 Bad Gateway). Pastikan backend FastAPI sedang berjalan di port 8000.");
        } else {
          setError(err.message || "Gagal memuat ringkasan hasil proses.");
        }
        setSummary(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [processId]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  const handleDownload = () => {
    window.open(`${API_BASE_URL}/process/${processId}/export`, "_blank");
  };

  const handleReset = async () => {
    if (!confirm("Yakin ingin mereset semua data? Tindakan ini tidak bisa diurungkan.")) return;
    setLoading(true);
    try {
      await api.post("/upload/reset");
      setSummary(null);
      setProcessId("");
      setError(null);
    } catch (err: any) {
      setError(err.message || "Gagal mereset data.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neo-border pb-3">
        <div>
          <h1 className="fluid-h1 font-black tracking-tight text-neo-black">
            Hasil Rekonsiliasi & Ekspor
          </h1>
          <p className="text-xs sm:text-sm text-neo-border mt-0.5">
            Ringkasan akhir status pencocokan koordinat per identitas proses unik.
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-2.5">
          <div className="flex items-center gap-1.5 border-2 border-neo-border px-2.5 py-1.5 rounded-sm bg-white shadow-[2px_2px_0_#0a0a0a]">
            <label className="text-xs font-bold text-neo-black">ID:</label>
            <input
              type="number"
              value={processId}
              onChange={(e) => setProcessId(e.target.value)}
              className="w-14 text-xs font-bold text-neo-black focus:outline-none"
            />
          </div>
          <button
            onClick={fetchSummary}
            className="touch-min px-3 py-1.5 min-h-[38px] border-2 border-neo-border bg-white hover:bg-[#e5e4e7] text-xs font-bold rounded-sm shadow-[2px_2px_0_#0a0a0a] transition active:translate-y-0.5"
            title="Muat ulang"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={handleReset}
            disabled={loading}
            className="touch-min px-3 py-1.5 min-h-[38px] border-2 border-[#dc2626] bg-[#fee2e2] hover:bg-[#fef2f2] text-[#dc2626] text-xs font-bold rounded-sm shadow-[2px_2px_0_#dc2626] transition active:translate-y-0.5 disabled:opacity-50 flex items-center gap-1"
            title="Hapus semua data dan mulai dari awal"
          >
            <Trash2 size={14} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 sm:p-4 border-2 border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded-sm text-xs sm:text-sm font-bold shadow-[2px_2px_0_#dc2626]">
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-sm font-bold text-neo-border animate-pulse">
          Memuat ringkasan proses...
        </div>
      ) : summary && !((summary as any).is_empty) ? (
        <div className="space-y-4 sm:space-y-6">
          {/* Header Info Box */}
          <div className="p-4 sm:p-5 border-2 border-neo-border rounded-sm bg-white shadow-[3px_3px_0_#0a0a0a] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h2 className="text-base sm:text-lg font-black text-neo-black">{summary.process_name}</h2>
              <p className="text-xs text-neo-border mt-0.5">
                Process ID: <strong>#{summary.process_id}</strong> | Radius Matching: <strong>{summary.radius_meters} meter</strong>
              </p>
            </div>
            <span className="self-start sm:self-auto px-2.5 py-1 text-xs font-bold border-2 border-neo-border bg-neo-white rounded-xs">
              Status: {summary.review_status?.toUpperCase() ?? "FINALIZED"}
            </span>
          </div>

          {/* Statistik Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 sm:gap-4">
            <div className="p-3.5 sm:p-4 border-2 border-neo-border rounded-sm bg-white shadow-[3px_3px_0_#0a0a0a]">
              <p className="text-[11px] sm:text-xs font-bold text-neo-border uppercase">TOTAL TARGET</p>
              <p className="text-2xl sm:text-3xl font-black mt-1 text-neo-black">{summary.total_targets}</p>
            </div>
            <div className="p-3.5 sm:p-4 border-2 border-[#16a34a] rounded-sm bg-[#dcfce7] shadow-[3px_3px_0_#16a34a]">
              <div className="flex items-center justify-between">
                <p className="text-[11px] sm:text-xs font-bold text-[#16a34a] uppercase">VALID</p>
                <CheckCircle2 size={16} className="text-[#16a34a]" />
              </div>
              <p className="text-2xl sm:text-3xl font-black mt-1 text-[#16a34a]">{summary.valid_count}</p>
            </div>
            <div className="p-3.5 sm:p-4 border-2 border-[#dc2626] rounded-sm bg-[#fee2e2] shadow-[3px_3px_0_#dc2626]">
              <div className="flex items-center justify-between">
                <p className="text-[11px] sm:text-xs font-bold text-[#dc2626] uppercase">DITOLAK</p>
                <XCircle size={16} className="text-[#dc2626]" />
              </div>
              <p className="text-2xl sm:text-3xl font-black mt-1 text-[#dc2626]">{summary.rejected_count}</p>
            </div>
            <div className="p-3.5 sm:p-4 border-2 border-[#d97706] rounded-sm bg-[#fef3c7] shadow-[3px_3px_0_#d97706]">
              <div className="flex items-center justify-between">
                <p className="text-[11px] sm:text-xs font-bold text-[#d97706] uppercase">PENDING</p>
                <Clock size={16} className="text-[#d97706]" />
              </div>
              <p className="text-2xl sm:text-3xl font-black mt-1 text-[#d97706]">{summary.pending_count}</p>
            </div>
          </div>

          {/* Action Box */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between p-4 sm:p-6 border-2 border-neo-border rounded-sm bg-white shadow-[4px_4px_0_#0a0a0a] gap-4">
            <div>
              <h3 className="font-black text-sm sm:text-base text-neo-black">Unduh Laporan Hasil Rekonsiliasi</h3>
              <p className="text-xs text-neo-border mt-0.5">
                Download file CSV berisi koordinat target, IDPEL kandidat terpilih, dan keputusan petugas.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2.5 shrink-0">
              <Link
                to={`/candidates?process_id=${summary.process_id}`}
                className="touch-min px-4 py-2.5 min-h-[44px] border-2 border-neo-border bg-white text-neo-black text-xs font-bold rounded-sm shadow-[2px_2px_0_#0a0a0a] hover:bg-[#e5e4e7] transition active:translate-y-0.5 flex items-center justify-center gap-1.5"
              >
                <ArrowLeft size={16} />
                <span>Kembali ke Review</span>
              </Link>
              <button
                onClick={handleDownload}
                className="touch-min px-5 py-2.5 min-h-[44px] border-2 border-neo-border bg-neo-black text-white text-xs font-bold rounded-sm shadow-[2px_2px_0_#ff6b35] hover:bg-[#1a1a1a] transition active:translate-y-0.5 flex items-center justify-center gap-2"
              >
                <Download size={16} />
                <span>Unduh File CSV (.CSV)</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-6 sm:p-8 border-2 border-dashed border-neo-border rounded-sm text-center bg-white space-y-3.5 shadow-[3px_3px_0_#0a0a0a]">
          <FileSpreadsheet size={36} className="mx-auto text-neo-border" />
          <div>
            <p className="text-sm sm:text-base font-black text-neo-black">Belum Ada Hasil Rekonsiliasi Tersedia</p>
            <p className="text-xs text-neo-border mt-1 max-w-md mx-auto">
              Silakan jalankan proses matching terlebih dahulu atau gunakan Quick Demo untuk mengisi data secara instan.
            </p>
          </div>
          <div className="pt-2">
            <Link
              to="/upload"
              className="touch-min inline-flex items-center gap-1.5 px-5 py-2.5 min-h-[44px] border-2 border-neo-border bg-neo-accent text-white text-xs sm:text-sm font-bold rounded-sm shadow-[2px_2px_0_#0a0a0a] hover:bg-[#e85a26] transition active:translate-y-0.5"
            >
              <span>⚡ Buka Halaman Upload & Jalankan Quick Demo →</span>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

