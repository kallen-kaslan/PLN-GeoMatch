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

export default function DashboardPage() {
  const [processes, setProcesses] = useState<ProcessItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const res = await api.get("/history/processes");
        setProcesses(res.data);
      } catch {
        // Fallback jika API belum aktif
      } finally {
        setLoading(false);
      }
    };
    loadDashboard();
  }, []);

  const totalProcesses = processes.length;
  const activeProcesses = processes.filter((p) => p.review_status !== "finalized").length;
  const totalTargets = processes.reduce((acc, curr) => acc + (curr.total_targets || 0), 0);
  const totalMatched = processes.reduce((acc, curr) => acc + (curr.matched_targets || 0), 0);

  const stats = [
    { label: "Total Sesi Proses", value: String(totalProcesses), delta: "Riwayat Aktif" },
    { label: "Proses Perlu Review", value: String(activeProcesses), delta: "Perlu Tindakan" },
    { label: "Total Titik Target", value: String(totalTargets), delta: "Dari Lapangan" },
    { label: "Target Menemukan Pasangan", value: String(totalMatched), delta: "Dalam Radius" },
  ];

  const actions = [
    { to: "/upload", label: "Upload data baru", desc: "Impor XLSX/CSV pelanggan" },
    { to: "/process", label: "Mulai proses matching", desc: "Jalankan pencocokan radius" },
    { to: "/candidates", label: "Review kandidat", desc: "Validasi koordinat pelanggan" },
    { to: "/result", label: "Lihat & Ekspor Hasil", desc: "Unduh file rekonsiliasi CSV" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold mb-1">Dashboard</h1>
          <p className="text-sm text-neo-border">
            Selamat datang di sistem <strong>PLN GeoMatch</strong>. Ringkasan aktivitas verifikasi koordinat.
          </p>
        </div>
      </div>

      {/* Grid Statistik Realtime */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a]">
            <p className="text-xs text-neo-border">{s.label}</p>
            <p className="text-2xl font-bold mt-1 text-neo-black">{s.value}</p>
            <p className="text-xs text-[#16a34a] mt-1 font-medium">{s.delta}</p>
          </div>
        ))}
      </div>

      {/* Aksi Cepat */}
      <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a]">
        <h2 className="text-sm font-bold mb-3">Aksi Cepat</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {actions.map((a) => (
            <Link
              key={a.to}
              to={a.to}
              className="flex flex-col p-3 border border-neo-border rounded-sm text-neo-black hover:bg-[#e5e4e7] shadow-[0_2px_0_#0a0a0a] transition group"
            >
              <span className="font-semibold">{a.label}</span>
              <span className="text-xs text-neo-border mt-1">{a.desc}</span>
            </Link>
          ))}
        </div>
      </div>

      {/* Pekerjaan Aktif */}
      <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a]">
        <h2 className="text-sm font-bold mb-3">Pekerjaan yang Memerlukan Tindakan Petugas</h2>
        {loading ? (
          <p className="text-sm text-neo-border">Memuat data...</p>
        ) : processes.length === 0 ? (
          <div className="text-center py-8 border-2 border-dashed border-neo-border rounded-sm">
            <p className="text-sm text-neo-border">Tidak ada pekerjaan yang menunggu tindakan.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b-2 border-neo-border">
                  <th className="pb-2 text-neo-border font-semibold">Nama Proses</th>
                  <th className="pb-2 text-neo-border font-semibold">Total Titik</th>
                  <th className="pb-2 text-neo-border font-semibold">Status Review</th>
                  <th className="pb-2 text-neo-border font-semibold text-center">Aksi Lanjutan</th>
                </tr>
              </thead>
              <tbody>
                {processes.slice(0, 5).map((p) => (
                  <tr key={p.id} className="border-b border-neo-border">
                    <td className="py-3 font-medium">{p.process_name}</td>
                    <td className="py-3 font-mono">{p.total_targets} titik</td>
                    <td className="py-3">
                      {p.matching_status === "completed" && p.review_status === "finalized" ? (
                        <span className="neo-highlight px-2 py-1 border border-[#16a34a] bg-[#dcfce7] text-[#16a34a] rounded text-[10px] font-bold">
                          ✓ SELESAI
                        </span>
                      ) : p.matching_status === "completed" ? (
                        <span className="neo-highlight px-2 py-1 border border-[#2563eb] bg-[#dbeafe] text-[#1e40af] rounded text-[10px] font-bold">
                          PERLU REVIEW
                        </span>
                      ) : (
                        <span className="px-2 py-1 neo-highlight border border-[#d97706] bg-[#fef3c7] text-[#92400e] rounded text-[10px] font-bold">
                          {p.matching_status.replace("_", " ").toUpperCase()}
                        </span>
                      )}
                    </td>
                    <td className="py-3 text-center">
                      <Link
                        to={`/candidates?process_id=${p.id}`}
                        className="px-3 py-1 border border-neo-border rounded-sm text-neo-black hover:bg-[#e5e4e7] text-xs font-semibold shadow-[0_1px_0_#0a0a0a]"
                      >
                        Buka Review →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
