import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { ArrowRight, Layers, Clock, CheckCircle2, AlertCircle, Database } from "lucide-react";

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
    let isMounted = true;
    const loadDashboard = async () => {
      try {
        const res = await api.get("/history/processes");
        if (isMounted) setProcesses(res.data);
      } catch {
        // Fallback jika API belum aktif
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    loadDashboard();
    return () => {
      isMounted = false;
    };
  }, []);

  const totalProcesses = processes.length;
  const activeProcesses = processes.filter((p) => p.review_status !== "finalized").length;
  const totalTargets = processes.reduce((acc, curr) => acc + (curr.total_targets || 0), 0);
  const totalMatched = processes.reduce((acc, curr) => acc + (curr.matched_targets || 0), 0);

  const stats = [
    { label: "Total Sesi Proses", value: String(totalProcesses), delta: "Riwayat Aktif", icon: Layers, color: "text-[#2563eb]" },
    { label: "Proses Perlu Review", value: String(activeProcesses), delta: "Perlu Tindakan Petugas", icon: AlertCircle, color: "text-[#d97706]" },
    { label: "Total Titik Target", value: String(totalTargets), delta: "Dari Lapangan", icon: Database, color: "text-neo-black" },
    { label: "Target Menemukan Pasangan", value: String(totalMatched), delta: "Dalam Radius Spasial", icon: CheckCircle2, color: "text-[#16a34a]" },
  ];

  const actions = [
    { to: "/upload", label: "Upload Data Baru", desc: "Impor XLSX/CSV pelanggan" },
    { to: "/process", label: "Mulai Matching", desc: "Jalankan pencocokan radius" },
    { to: "/candidates", label: "Review Kandidat", desc: "Validasi koordinat pelanggan" },
    { to: "/result", label: "Ekspor Hasil", desc: "Unduh rekonsiliasi CSV" },
  ];

  return (
    <div className="space-y-5 sm:space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-neo-border pb-3">
        <div>
          <h1 className="fluid-h1 font-black tracking-tight text-neo-black">Dashboard</h1>
          <p className="text-xs sm:text-sm text-neo-border mt-0.5">
            Selamat datang di sistem <strong>PLN GeoMatch</strong>. Ringkasan aktivitas verifikasi koordinat lapangan.
          </p>
        </div>
      </div>

      {/* Grid Statistik Realtime (1 col mobile -> 2 col tablet -> 4 col desktop) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <div
              key={s.label}
              className="p-4 border-2 border-neo-border rounded-sm bg-white shadow-[3px_3px_0_#0a0a0a] flex flex-col justify-between"
            >
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-neo-border uppercase tracking-wider">{s.label}</p>
                <Icon size={18} className={s.color} />
              </div>
              <p className="text-2xl sm:text-3xl font-black mt-2 text-neo-black">{s.value}</p>
              <p className="text-[11px] text-[#16a34a] mt-1 font-semibold flex items-center gap-1">
                <span>●</span> {s.delta}
              </p>
            </div>
          );
        })}
      </div>

      {/* Aksi Cepat */}
      <div className="p-4 sm:p-5 border-2 border-neo-border rounded-sm bg-white shadow-[3px_3px_0_#0a0a0a]">
        <h2 className="text-sm sm:text-base font-black mb-3 text-neo-black">Aksi Cepat</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3">
          {actions.map((a) => (
            <Link
              key={a.to}
              to={a.to}
              className="flex flex-col justify-between p-3.5 border-2 border-neo-border rounded-sm text-neo-black hover:bg-[#e5e4e7] shadow-[2px_2px_0_#0a0a0a] transition active:translate-y-0.5 group min-h-[64px]"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-xs sm:text-sm">{a.label}</span>
                <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
              </div>
              <span className="text-[11px] text-neo-border mt-1">{a.desc}</span>
            </Link>
          ))}
        </div>
      </div>

      {/* Pekerjaan Aktif */}
      <div className="p-4 sm:p-5 border-2 border-neo-border rounded-sm bg-white shadow-[3px_3px_0_#0a0a0a]">
        <div className="flex items-center justify-between mb-3.5">
          <h2 className="text-sm sm:text-base font-black text-neo-black">
            Pekerjaan yang Memerlukan Tindakan Petugas
          </h2>
          <span className="text-xs font-semibold text-neo-border hidden sm:inline">
            Menampilkan {Math.min(processes.length, 5)} proses terbaru
          </span>
        </div>

        {loading ? (
          <div className="py-8 text-center text-sm font-semibold text-neo-border animate-pulse">
            Memuat data proses...
          </div>
        ) : processes.length === 0 ? (
          <div className="text-center py-8 border-2 border-dashed border-neo-border rounded-sm bg-neo-white">
            <Clock size={28} className="mx-auto text-neo-border mb-2" />
            <p className="text-sm font-bold text-neo-black">Tidak ada pekerjaan yang menunggu tindakan.</p>
            <p className="text-xs text-neo-border mt-1">Silakan upload data atau jalankan proses matching baru.</p>
          </div>
        ) : (
          <>
            {/* Tampilan Desktop & Tablet: Tabel Terstruktur */}
            <div className="hidden sm:block overflow-x-auto neo-scrollbar">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b-2 border-neo-border bg-neo-white">
                    <th className="p-3 text-neo-border font-bold">Nama Proses</th>
                    <th className="p-3 text-neo-border font-bold">Total Titik</th>
                    <th className="p-3 text-neo-border font-bold">Status Review</th>
                    <th className="p-3 text-neo-border font-bold text-center">Aksi Lanjutan</th>
                  </tr>
                </thead>
                <tbody>
                  {processes.slice(0, 5).map((p) => (
                    <tr key={p.id} className="border-b border-neo-border hover:bg-neo-white/70 transition">
                      <td className="p-3 font-bold text-neo-black">{p.process_name}</td>
                      <td className="p-3 font-mono font-semibold">{p.total_targets} titik</td>
                      <td className="p-3">
                        {p.matching_status === "completed" && p.review_status === "finalized" ? (
                          <span className="neo-highlight px-2 py-1 border border-[#16a34a] bg-[#dcfce7] text-[#16a34a] rounded text-[10px] font-bold">
                            ✓ SELESAI
                          </span>
                        ) : p.matching_status === "completed" ? (
                          <span className="neo-highlight px-2 py-1 border border-[#2563eb] bg-[#dbeafe] text-[#1e40af] rounded text-[10px] font-bold">
                            PERLU REVIEW
                          </span>
                        ) : (
                          <span className="neo-highlight px-2 py-1 border border-[#d97706] bg-[#fef3c7] text-[#92400e] rounded text-[10px] font-bold">
                            {p.matching_status.replace("_", " ").toUpperCase()}
                          </span>
                        )}
                      </td>
                      <td className="p-3 text-center">
                        <Link
                          to={`/candidates?process_id=${p.id}`}
                          className="inline-flex items-center justify-center px-3.5 py-1.5 min-h-[36px] border border-neo-border rounded-sm text-neo-black bg-white hover:bg-[#e5e4e7] text-xs font-bold shadow-[0_1px_0_#0a0a0a] transition active:translate-y-0.5"
                        >
                          Buka Review →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Tampilan Mobile (< 640px): Card List Responsif */}
            <div className="sm:hidden space-y-3">
              {processes.slice(0, 5).map((p) => (
                <div
                  key={p.id}
                  className="p-3.5 border-2 border-neo-border rounded-sm bg-neo-white/50 space-y-2.5 shadow-[2px_2px_0_#0a0a0a]"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-bold text-sm text-neo-black leading-snug">{p.process_name}</p>
                    <span className="font-mono text-xs font-bold text-neo-border bg-white px-2 py-0.5 border border-neo-border rounded-xs shrink-0">
                      #{p.id}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-xs text-neo-border pt-1">
                    <span>
                      Total: <strong className="text-neo-black font-mono">{p.total_targets} titik</strong>
                    </span>
                    <div>
                      {p.matching_status === "completed" && p.review_status === "finalized" ? (
                        <span className="px-2 py-0.5 border border-[#16a34a] bg-[#dcfce7] text-[#16a34a] rounded text-[10px] font-bold">
                          ✓ SELESAI
                        </span>
                      ) : p.matching_status === "completed" ? (
                        <span className="px-2 py-0.5 border border-[#2563eb] bg-[#dbeafe] text-[#1e40af] rounded text-[10px] font-bold">
                          PERLU REVIEW
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 border border-[#d97706] bg-[#fef3c7] text-[#92400e] rounded text-[10px] font-bold">
                          {p.matching_status.replace("_", " ").toUpperCase()}
                        </span>
                      )}
                    </div>
                  </div>

                  <Link
                    to={`/candidates?process_id=${p.id}`}
                    className="w-full touch-min flex items-center justify-center gap-1.5 border-2 border-neo-border bg-neo-black text-white text-xs font-bold rounded-sm shadow-[2px_2px_0_#ff6b35] transition active:translate-y-0.5"
                  >
                    <span>Buka Review Spasial</span>
                    <ArrowRight size={14} />
                  </Link>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

