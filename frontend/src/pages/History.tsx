import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { History, RotateCw, Trash2, ExternalLink, FileSpreadsheet, MapPin } from "lucide-react";

interface ProcessItem {
  id: number;
  process_name: string;
  radius_meters: number;
  matching_status: string;
  review_status: string;
  total_targets: number;
  matched_targets: number;
  unmatched_targets: number;
  created_at: string;
}

export default function HistoryPage() {
  const [processes, setProcesses] = useState<ProcessItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [clearingAll, setClearingAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchHistory = useCallback(() => {
    api.get("/history/processes")
      .then((res) => {
        setProcesses(res.data);
        setError(null);
      })
      .catch((err: any) => {
        setError(err.message || "Gagal memuat riwayat proses.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const handleDeleteProcess = async (processId: number, processName: string) => {
    if (!window.confirm(`Hapus riwayat proses #${processId} ("${processName}") beserta data kandidatnya?`)) {
      return;
    }
    setDeletingId(processId);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await api.delete(`/history/processes/${processId}`);
      setSuccessMsg(res.data.message || `Proses #${processId} berhasil dihapus.`);
      setProcesses((prev) => prev.filter((p) => p.id !== processId));
    } catch (err: any) {
      setError(err.message || `Gagal menghapus proses #${processId}.`);
    } finally {
      setDeletingId(null);
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm("PERINGATAN: Hapus SELURUH riwayat proses rekonsiliasi dan hasil kandidat? Tindakan ini tidak dapat dibatalkan.")) {
      return;
    }
    setClearingAll(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await api.delete("/history/processes");
      setSuccessMsg(res.data.message || "Semua riwayat berhasil dihapus.");
      setProcesses([]);
    } catch (err: any) {
      setError(err.message || "Gagal membersihkan riwayat.");
    } finally {
      setClearingAll(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-black mb-1 flex items-center gap-2">
            <History className="w-6 h-6 sm:w-7 sm:h-7 text-neo-black" strokeWidth={2.5} />
            Riwayat Proses Rekonsiliasi
          </h1>
          <p className="text-xs sm:text-sm text-neo-border">
            Daftar seluruh proses yang pernah dijalankan. Data historis tidak saling menimpa.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {processes.length > 0 && (
            <button
              onClick={handleClearAll}
              disabled={clearingAll || loading}
              className="touch-min px-3 py-2 border-2 border-[#dc2626] rounded-sm text-xs font-bold text-[#dc2626] bg-white hover:bg-[#fee2e2] shadow-[2px_2px_0_#dc2626] active:translate-y-0.5 disabled:opacity-50 flex items-center gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>{clearingAll ? "Membersihkan..." : "Hapus Semua"}</span>
            </button>
          )}
          <button
            onClick={() => {
              setLoading(true);
              fetchHistory();
            }}
            disabled={loading}
            className="touch-min px-3.5 py-2 border-2 border-neo-border rounded-sm text-xs font-bold bg-white hover:bg-[#e5e4e7] shadow-[2px_2px_0_#0a0a0a] active:translate-y-0.5 disabled:opacity-50 flex items-center gap-1.5"
          >
            <RotateCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Muat Ulang</span>
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="p-3 border-2 border-[#16a34a] bg-[#dcfce7] text-[#16a34a] rounded-sm text-xs font-bold shadow-[2px_2px_0_#16a34a]">
          ✓ {successMsg}
        </div>
      )}

      {error && (
        <div className="p-4 border-2 border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded-sm text-sm font-semibold">
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-sm font-semibold text-neo-border border border-dashed border-neo-border rounded-sm bg-white">
          Memuat riwayat proses...
        </div>
      ) : processes.length === 0 ? (
        <div className="p-8 border border-dashed border-neo-border rounded-sm text-center text-sm text-neo-border bg-white">
          Belum ada proses yang pernah dijalankan. Silakan mulai di menu Proses.
        </div>
      ) : (
        <>
          {/* Mobile Card List (< md) */}
          <div className="block md:hidden space-y-3">
            {processes.map((p) => (
              <div
                key={p.id}
                className="border-2 border-neo-black rounded-lg bg-white p-4 shadow-[3px_3px_0_#0a0a0a] space-y-3"
              >
                <div className="flex items-start justify-between gap-2 border-b border-neo-border pb-2.5">
                  <div>
                    <span className="inline-block px-1.5 py-0.5 bg-neo-black text-white text-[10px] font-mono font-bold rounded mr-1.5">
                      #{p.id}
                    </span>
                    <h3 className="inline text-sm font-black text-neo-black">
                      {p.process_name}
                    </h3>
                  </div>
                  <span className="shrink-0 px-2 py-0.5 border border-neo-border rounded text-[10px] uppercase font-bold bg-[#f1f1f4]">
                    {p.review_status.replace("_", " ")}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-gray-500 block text-[11px]">Radius:</span>
                    <span className="font-mono font-bold">{p.radius_meters} meter</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-[11px]">Dibuat:</span>
                    <span className="text-gray-700 font-medium text-[11px]">
                      {new Date(p.created_at).toLocaleDateString("id-ID", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-[11px]">Total Target:</span>
                    <span className="font-bold">{p.total_targets}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-[11px]">Hasil Cocok / Anomali:</span>
                    <span>
                      <strong className="text-[#16a34a]">{p.matched_targets}</strong> /{" "}
                      <strong className="text-[#dc2626]">{p.unmatched_targets}</strong>
                    </span>
                  </div>
                </div>

                <div className="pt-2 border-t border-neo-border flex items-center gap-2">
                  <Link
                    to={`/candidates?process_id=${p.id}`}
                    className="touch-min flex-1 flex items-center justify-center gap-1 px-3 py-2 border-2 border-neo-black rounded text-xs font-bold bg-white hover:bg-[#e5e4e7] shadow-[2px_2px_0_#0a0a0a] active:translate-y-0.5"
                    title="Buka Peta & Review Kandidat"
                  >
                    <MapPin className="w-3.5 h-3.5" />
                    Review
                  </Link>
                  <Link
                    to={`/result?process_id=${p.id}`}
                    className="touch-min flex-1 flex items-center justify-center gap-1 px-3 py-2 border-2 border-neo-black rounded text-xs font-bold bg-neo-black text-white shadow-[2px_2px_0_#ff6b35] active:translate-y-0.5"
                    title="Lihat Rekapitulasi & Ekspor CSV"
                  >
                    <FileSpreadsheet className="w-3.5 h-3.5 text-neo-accent" />
                    Hasil
                  </Link>
                  <button
                    onClick={() => handleDeleteProcess(p.id, p.process_name)}
                    disabled={deletingId === p.id}
                    className="touch-min w-11 h-10 flex items-center justify-center border-2 border-[#dc2626] rounded text-[#dc2626] bg-white hover:bg-[#fee2e2] shadow-[2px_2px_0_#dc2626] active:translate-y-0.5 disabled:opacity-50"
                    title="Hapus riwayat proses ini"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop Table View (>= md) */}
          <div className="hidden md:block border-2 border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] overflow-x-auto neo-scrollbar">
            <table className="w-full text-left text-xs border-collapse min-w-[760px]">
              <thead className="bg-[#e5e4e7] border-b-2 border-neo-border">
                <tr>
                  <th className="p-3 border-r border-neo-border font-black">ID</th>
                  <th className="p-3 border-r border-neo-border font-black">Nama Proses</th>
                  <th className="p-3 border-r border-neo-border font-black">Tanggal Dibuat</th>
                  <th className="p-3 border-r border-neo-border font-black">Radius</th>
                  <th className="p-3 border-r border-neo-border font-black">Total Target</th>
                  <th className="p-3 border-r border-neo-border font-black">Cocok / Anomali</th>
                  <th className="p-3 border-r border-neo-border font-black">Status Review</th>
                  <th className="p-3 text-center font-black">Aksi Cepat</th>
                </tr>
              </thead>
              <tbody>
                {processes.map((p) => (
                  <tr key={p.id} className="border-b border-neo-border hover:bg-neo-white transition-colors">
                    <td className="p-3 border-r border-neo-border font-bold">#{p.id}</td>
                    <td className="p-3 border-r border-neo-border font-semibold text-neo-black">
                      {p.process_name}
                    </td>
                    <td className="p-3 border-r border-neo-border text-gray-600">
                      {new Date(p.created_at).toLocaleString("id-ID")}
                    </td>
                    <td className="p-3 border-r border-neo-border font-mono">{p.radius_meters} m</td>
                    <td className="p-3 border-r border-neo-border font-bold">{p.total_targets}</td>
                    <td className="p-3 border-r border-neo-border">
                      <span className="text-[#16a34a] font-bold">{p.matched_targets}</span> /{" "}
                      <span className="text-[#dc2626] font-bold">{p.unmatched_targets}</span>
                    </td>
                    <td className="p-3 border-r border-neo-border">
                      <span className="neo-highlight px-2 py-1 border border-neo-border rounded text-[10px] uppercase font-bold bg-neo-white">
                        {p.review_status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="p-3 text-center">
                      <div className="flex justify-center items-center gap-1.5">
                        <Link
                          to={`/candidates?process_id=${p.id}`}
                          className="px-2.5 py-1.5 min-h-[34px] flex items-center gap-1 border border-neo-border rounded text-[11px] font-bold bg-white hover:bg-[#e5e4e7] shadow-[0_1px_0_#0a0a0a]"
                          title="Buka Peta & Review Kandidat"
                        >
                          <ExternalLink className="w-3 h-3" />
                          Review
                        </Link>
                        <Link
                          to={`/result?process_id=${p.id}`}
                          className="px-2.5 py-1.5 min-h-[34px] flex items-center gap-1 border border-neo-border rounded text-[11px] font-bold bg-neo-black text-white shadow-[0_1px_0_#0a0a0a]"
                          title="Lihat Rekapitulasi & Ekspor CSV"
                        >
                          <FileSpreadsheet className="w-3 h-3 text-neo-accent" />
                          Hasil
                        </Link>
                        <button
                          onClick={() => handleDeleteProcess(p.id, p.process_name)}
                          disabled={deletingId === p.id}
                          className="p-1.5 min-h-[34px] min-w-[34px] flex items-center justify-center border border-[#dc2626] rounded text-[11px] font-semibold text-[#dc2626] bg-white hover:bg-[#fee2e2] shadow-[0_1px_0_#dc2626] disabled:opacity-50"
                          title="Hapus riwayat proses ini"
                        >
                          {deletingId === p.id ? "..." : <Trash2 className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
