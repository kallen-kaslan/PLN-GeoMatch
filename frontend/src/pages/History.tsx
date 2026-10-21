import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";

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
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [clearingAll, setClearingAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/history/processes");
      setProcesses(res.data);
    } catch (err: any) {
      setError(err.message || "Gagal memuat riwayat proses.");
    } finally {
      setLoading(false);
    }
  };

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
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold mb-1">Riwayat Proses Rekonsiliasi</h1>
          <p className="text-sm text-neo-border">
            Daftar seluruh proses yang pernah dijalankan. Data historis tidak saling menimpa.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {processes.length > 0 && (
            <button
              onClick={handleClearAll}
              disabled={clearingAll || loading}
              className="px-3 py-1.5 border border-[#dc2626] rounded-sm text-xs font-bold text-[#dc2626] bg-white hover:bg-[#fee2e2] shadow-[0_2px_0_#dc2626] disabled:opacity-50"
            >
              {clearingAll ? "Membersihkan..." : "🗑️ Hapus Semua Riwayat"}
            </button>
          )}
          <button
            onClick={fetchHistory}
            disabled={loading}
            className="px-3 py-1.5 border border-neo-border rounded-sm text-xs font-medium bg-white hover:bg-[#e5e4e7] shadow-[0_2px_0_#0a0a0a] disabled:opacity-50"
          >
            Muat Ulang Data ↻
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="p-3 border border-[#16a34a] bg-[#dcfce7] text-[#16a34a] rounded-sm text-xs font-bold shadow-[0_2px_0_#16a34a]">
          ✓ {successMsg}
        </div>
      )}

      {error && (
        <div className="p-4 border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded-sm text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-sm text-neo-border">Memuat riwayat proses...</div>
      ) : processes.length === 0 ? (
        <div className="p-8 border border-dashed border-neo-border rounded-sm text-center text-sm text-neo-border">
          Belum ada proses yang pernah dijalankan. Silakan mulai di menu Proses.
        </div>
      ) : (
        <div className="border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-[#e5e4e7] border-b border-neo-border">
              <tr>
                <th className="p-3 border-r border-neo-border">ID Proses</th>
                <th className="p-3 border-r border-neo-border">Nama Proses</th>
                <th className="p-3 border-r border-neo-border">Tanggal Dibuat</th>
                <th className="p-3 border-r border-neo-border">Radius</th>
                <th className="p-3 border-r border-neo-border">Total Target</th>
                <th className="p-3 border-r border-neo-border">Cocok / Anomali</th>
                <th className="p-3 border-r border-neo-border">Status Review</th>
                <th className="p-3 text-center">Aksi Cepat</th>
              </tr>
            </thead>
            <tbody>
              {processes.map((p) => (
                <tr key={p.id} className="border-b border-neo-border hover:bg-neo-white">
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
                    <span className="px-2 py-1 neo-highlight border border-neo-border rounded text-[10px] uppercase font-bold bg-neo-white">
                      {p.review_status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="p-3 text-center">
                    <div className="flex justify-center items-center gap-1.5">
                      <Link
                        to={`/candidates?process_id=${p.id}`}
                        className="px-2.5 py-1 border border-neo-border rounded text-[11px] font-semibold bg-white hover:bg-[#e5e4e7] shadow-[0_1px_0_#0a0a0a]"
                        title="Buka Peta & Review Kandidat"
                      >
                        Review
                      </Link>
                      <Link
                        to={`/result?process_id=${p.id}`}
                        className="px-2.5 py-1 border border-neo-border rounded text-[11px] font-semibold bg-neo-black text-white shadow-[0_1px_0_#0a0a0a]"
                        title="Lihat Rekapitulasi & Ekspor CSV"
                      >
                        Hasil
                      </Link>
                      <button
                        onClick={() => handleDeleteProcess(p.id, p.process_name)}
                        disabled={deletingId === p.id}
                        className="px-2 py-1 border border-[#dc2626] rounded text-[11px] font-semibold text-[#dc2626] bg-white hover:bg-[#fee2e2] shadow-[0_1px_0_#dc2626] disabled:opacity-50"
                        title="Hapus riwayat proses ini"
                      >
                        {deletingId === p.id ? "..." : "🗑️"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
