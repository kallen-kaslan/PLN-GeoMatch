import { MetricCard } from "@/components/data/MetricCard";
import { useState, useEffect, useCallback } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CorrectionResults } from "@/components/corrections/CorrectionResults";
import { resultsApi, reviewStatusLabel } from "@/lib/results";
import { CORRECTION_TYPES } from "@/lib/corrections";
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

function LegacyResultPage({ initialId, onSelect }: { initialId: string; onSelect: (value: string) => void }) {

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
      })
      .catch((err: any) => {
        if (err.status === 502) {
          setError("Layanan belum dapat dihubungi. Muat ulang halaman atau hubungi pengelola.");
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
    window.open(`${API_BASE_URL}/process/${processId}/export?format=xlsx`, "_blank");
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
      <div className="geo-page-heading geo-archive-heading">
        <div>
          <h1 className="fluid-h1 flex items-center gap-3 font-semibold tracking-tight text-neo-black"><FileSpreadsheet aria-hidden="true" />
            Hasil Rekonsiliasi & Ekspor
          </h1>
          <p className="text-xs sm:text-sm text-ui-muted mt-0.5">
            Ringkasan akhir status pencocokan koordinat per identitas proses unik.
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-2.5">
          <div className="flex items-center gap-1.5 border border-ui-border px-2.5 py-1.5 rounded-lg bg-white ">
            <label className="text-xs font-semibold text-neo-black">ID:</label>
            <input
              type="number"
              value={processId}
              onChange={(e) => setProcessId(e.target.value)}
              onBlur={() => { if (Number(processId) > 0) onSelect(processId); }}
              className="w-14 text-xs font-semibold text-neo-black focus:outline-none"
            />
          </div>
          <button
            onClick={fetchSummary}
            className="touch-min px-3 py-1.5 min-h-[38px] border border-ui-border bg-white hover:bg-slate-100 text-xs font-semibold rounded-lg  transition "
            title="Muat ulang"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={handleReset}
            disabled={loading}
            className="touch-min px-3 py-1.5 min-h-[38px] border border-[#dc2626] bg-[#fee2e2] hover:bg-[#fef2f2] text-[#dc2626] text-xs font-semibold rounded-lg  transition  disabled:opacity-50 flex items-center gap-1"
            title="Hapus semua data dan mulai dari awal"
          >
            <Trash2 size={14} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 sm:p-4 border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded-lg text-xs sm:text-sm font-semibold ">
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-sm font-semibold text-ui-muted animate-pulse">
          Memuat ringkasan proses...
        </div>
      ) : summary && !((summary as any).is_empty) ? (
        <div className="space-y-4 sm:space-y-6">
          {/* Header Info Box */}
          <div className="p-4 sm:p-5 border border-ui-border rounded-lg bg-white  flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h2 className="text-base sm:text-lg font-semibold text-neo-black">{summary.process_name}</h2>
              <p className="text-xs text-ui-muted mt-0.5">
                Process ID: <strong>#{summary.process_id}</strong> | Radius Matching: <strong>{summary.radius_meters} meter</strong>
              </p>
            </div>
            <span className="self-start sm:self-auto px-2.5 py-1 text-xs font-semibold border border-ui-border bg-neo-white rounded-md">
              Status: {reviewStatusLabel(summary.review_status)}
            </span>
          </div>

          {/* Statistik Cards */}
          <div className="geo-metrics geo-metrics-4">
            <MetricCard label="Total target" value={summary.total_targets} tone="primary" />
            <MetricCard label="Kandidat dipilih" value={summary.valid_count} tone="success" icon={CheckCircle2} />
            <MetricCard label="Kandidat ditolak" value={summary.rejected_count} tone="danger" icon={XCircle} />
            <MetricCard label="Kandidat belum ditinjau" value={summary.pending_count} tone="warning" icon={Clock} />
          </div>

          {/* Action Box */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between p-4 sm:p-6 border border-ui-border rounded-lg bg-white  gap-4">
            <div>
              <h3 className="font-semibold text-sm sm:text-base text-neo-black">Unduh Laporan Hasil Rekonsiliasi</h3>
              <p className="text-xs text-ui-muted mt-0.5">
                Unduh file XLSX berisi koordinat target, IDPEL kandidat terpilih, dan keputusan petugas.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2.5 shrink-0">
              <Link
                to={`/candidates?process_id=${summary.process_id}`}
                className="touch-min px-4 py-2.5 min-h-[44px] border border-ui-border bg-white text-neo-black text-xs font-semibold rounded-lg  hover:bg-slate-100 transition  flex items-center justify-center gap-1.5"
              >
                <ArrowLeft size={16} />
                <span>Kembali ke Review</span>
              </Link>
              <button
                onClick={handleDownload}
                className="touch-min px-5 py-2.5 min-h-[44px] border border-ui-border bg-ui-primary text-white text-xs font-semibold rounded-lg  hover:bg-ui-primary-hover transition  flex items-center justify-center gap-2"
              >
                <Download size={16} />
                <span>Ekspor XLSX</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-6 sm:p-8 border border-dashed border-ui-border rounded-lg text-center bg-white space-y-3.5 ">
          <FileSpreadsheet size={36} className="mx-auto text-ui-muted" />
          <div>
            <p className="text-sm sm:text-base font-semibold text-neo-black">Belum Ada Hasil Rekonsiliasi Tersedia</p>
            <p className="text-xs text-ui-muted mt-1 max-w-md mx-auto">
              Silakan jalankan proses matching terlebih dahulu atau gunakan Quick Demo untuk mengisi data secara instan.
            </p>
          </div>
          <div className="pt-2">
            <Link
              to="/upload"
              className="touch-min inline-flex items-center gap-1.5 px-5 py-2.5 min-h-[44px] border border-ui-border bg-neo-accent text-white text-xs sm:text-sm font-semibold rounded-lg  hover:bg-ui-primary-hover transition "
            >
              <span>⚡ Buka Halaman Upload & Jalankan Quick Demo →</span>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}


export default function ResultPage() {
  const [params, setParams] = useSearchParams();
  const processes = useQuery({ queryKey: ["process-history"], queryFn: ({ signal }) => resultsApi.processes(signal), refetchInterval: 5000 });
  const requested = Number(params.get("process_id")) || null;
  const category = CORRECTION_TYPES.find((item) => item.key === params.get("category"))?.key;
  const selected = requested ? processes.data?.find((item) => item.id === requested)
    : processes.data?.find((item) => (!category || item.category === category) && (item.chosen_count ?? 0) > 0)
      ?? processes.data?.find((item) => !category || item.category === category);
  const selectedId = selected?.id;
  useEffect(() => {
    if (!requested && selectedId) setParams({ process_id: String(selectedId), ...(category ? { category } : {}) }, { replace: true });
  }, [requested, selectedId, category, setParams]);
  if (processes.isPending) return <p role="status" className="p-6 text-sm">Memuat daftar hasil...</p>;
  if (processes.isError) return <p role="alert" className="p-6 text-sm text-red-700">Daftar hasil belum dapat dimuat. <button type="button" onClick={() => void processes.refetch()} className="font-semibold underline">Coba lagi</button></p>;
  if (selected?.category || (!requested && category)) return <CorrectionResults key={selected?.id ?? category} process={selected} processes={processes.data ?? []} category={selected?.category ?? category!} />;
  if (!selected && !requested) return <div className="space-y-3 border border-ui-border bg-white p-5"><h1 className="text-xl font-semibold">Hasil Koreksi</h1><p>Belum ada hasil pemeriksaan.</p><Link className="font-semibold underline" to="/koreksi">Buka Data Koreksi</Link></div>;
  return <LegacyResultPage key={requested ?? selected?.id} initialId={String(requested ?? selected?.id)} onSelect={(id) => setParams({ process_id: id })} />;
}
