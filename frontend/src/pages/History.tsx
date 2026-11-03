import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { DecisionHistory } from "@/components/corrections/DecisionHistory";
import { correctionApi } from "@/lib/corrections";
import { downloadSpreadsheet, resultsApi, type ProcessHistory } from "@/lib/results";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { History, RotateCw, Trash2, ExternalLink, FileSpreadsheet, MapPin } from "lucide-react";


export default function HistoryPage() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const history = useQuery({ queryKey: ["process-history"], queryFn: ({ signal }) => resultsApi.processes(signal), refetchInterval: 5000 });
  const processes = history.data ?? [];
  const loading = history.isPending;
  const selected = processes.find((item) => item.id === Number(params.get("process_id")));
  const generation = Number(params.get("generation")) || selected?.generation;
  const version = useQuery({ queryKey: ["history-radius-version", selected?.id, generation], queryFn: ({ signal }) => correctionApi.check(selected!.category!, selected!.id, signal), enabled: !!selected?.category && !!params.get("generation") });
  const radius = params.get("generation") ? version.data?.runs.find((run) => run.generation === generation)?.radius_meters : selected?.radius_meters;
  const fetchHistory = () => { setError(null); void history.refetch(); };
  const setProcesses = (update: ProcessHistory[] | ((previous: ProcessHistory[]) => ProcessHistory[])) => queryClient.setQueryData<ProcessHistory[]>(["process-history"], (previous = []) => typeof update === "function" ? update(previous) : update);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [clearingAll, setClearingAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const download = useMutation({
    mutationFn: async (process: ProcessHistory) => process.category
      ? resultsApi.download(process.category, process.id, process.generation!, process.radius_meters)
      : { blob: (await api.get<Blob>(`/process/${process.id}/export`, { params: { format: "xlsx" }, responseType: "blob" })).data, filename: `hasil_koreksi_proses_${process.id}.xlsx` },
    onSuccess: (file) => downloadSpreadsheet(file.blob, file.filename),
  });

  const remove = useMutation({ mutationFn: (path: string) => api.delete(path) });

  const handleDeleteProcess = async (processId: number, processName: string) => {
    if (!window.confirm(`Hapus riwayat proses #${processId} ("${processName}") beserta data kandidatnya?`)) {
      return;
    }
    setDeletingId(processId);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await remove.mutateAsync(`/history/processes/${processId}`);
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
      const res = await remove.mutateAsync("/history/processes");
      setSuccessMsg(res.data.message || "Semua riwayat berhasil dihapus.");
      setProcesses([]);
    } catch (err: any) {
      setError(err.message || "Gagal membersihkan riwayat.");
    } finally {
      setClearingAll(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold mb-1 flex items-center gap-2">
            <History className="w-6 h-6 sm:w-7 sm:h-7 text-neo-black" strokeWidth={2.5} />
            Riwayat Proses Rekonsiliasi
          </h1>
          <p className="text-xs sm:text-sm text-ui-muted">
            Daftar seluruh proses yang pernah dijalankan. Data historis tidak saling menimpa.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {processes.length > 0 && (
            <button
              onClick={handleClearAll}
              disabled={clearingAll || loading}
              className="touch-min px-3 py-2 border border-[#dc2626] rounded-lg text-xs font-semibold text-[#dc2626] bg-white hover:bg-[#fee2e2]   disabled:opacity-50 flex items-center gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>{clearingAll ? "Membersihkan..." : "Hapus Semua"}</span>
            </button>
          )}
          <button
            onClick={() => {
              fetchHistory();
            }}
            disabled={history.isFetching}
            className="touch-min px-3.5 py-2 border border-ui-border rounded-lg text-xs font-semibold bg-white hover:bg-slate-100   disabled:opacity-50 flex items-center gap-1.5"
          >
            <RotateCw className={`w-3.5 h-3.5 ${history.isFetching ? "animate-spin" : ""}`} />
            <span>Muat Ulang</span>
          </button>
        </div>
      </div>

      {download.isError && <p role="alert" className="text-sm text-red-700">File XLSX belum dapat diunduh. Silakan coba lagi.</p>}

      {successMsg && (
        <div className="p-3 border border-[#16a34a] bg-[#dcfce7] text-[#16a34a] rounded-lg text-xs font-semibold ">
          ✓ {successMsg}
        </div>
      )}

      {(error || history.isError) && (
        <div className="p-4 border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded-lg text-sm font-semibold">
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-sm font-semibold text-ui-muted border border-dashed border-ui-border rounded-lg bg-white">
          Memuat riwayat proses...
        </div>
      ) : processes.length === 0 ? (
        <div className="p-8 border border-dashed border-ui-border rounded-lg text-center text-sm text-ui-muted bg-white">
          Belum ada proses yang pernah dijalankan. Silakan mulai di menu Proses.
        </div>
      ) : (
        <>
          {/* Mobile Card List (< md) */}
          <div className="block md:hidden space-y-3">
            {processes.map((p) => (
              <div
                key={p.id}
                className="border border-neo-black rounded-lg bg-white p-4  space-y-3"
              >
                <div className="flex items-start justify-between gap-2 border-b border-ui-border pb-2.5">
                  <div>
                    <span className="inline-block px-1.5 py-0.5 bg-ui-primary text-white text-xs font-mono font-semibold rounded mr-1.5">
                      #{p.id}
                    </span>
                    <h3 className="inline text-sm font-semibold text-neo-black">{p.process_name}</h3>
                    {p.category && <p className="mt-1 text-xs">{p.filename} | {p.partial ? "Hasil sebagian" : "Pemeriksaan selesai"} | {p.saved_rows} baris tersimpan | {p.not_processed} belum diproses | {p.chosen_count} pilihan aktif</p>}
                  </div>
                  <span className="shrink-0 px-2 py-0.5 border border-ui-border rounded text-xs uppercase font-semibold bg-[#f1f1f4]">
                    {p.review_status.replace("_", " ")}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-gray-500 block text-xs">Radius:</span>
                    <span className="font-mono font-semibold">{p.radius_meters} meter</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-xs">Dibuat:</span>
                    <span className="text-gray-700 font-medium text-xs">
                      {new Date(p.created_at).toLocaleDateString("id-ID", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-xs">Total Target:</span>
                    <span className="font-semibold">{p.total_targets}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-xs">Hasil Cocok / Anomali:</span>
                    <span>
                      <strong className="text-[#16a34a]">{p.matched_targets}</strong> /{" "}
                      <strong className="text-[#dc2626]">{p.unmatched_targets}</strong>
                    </span>
                  </div>
                </div>

                <div className="pt-2 border-t border-ui-border flex flex-wrap items-center gap-2">
                  <Link
                    to={p.category ? `/peta-koreksi?category=${p.category}&batch_id=${p.batch_id}&process_id=${p.id}` : `/candidates?process_id=${p.id}`}
                    className="touch-min flex-1 flex items-center justify-center gap-1 px-3 py-2 border border-neo-black rounded text-xs font-semibold bg-white hover:bg-slate-100  "
                    title="Buka Peta & Review Kandidat"
                  >
                    <MapPin className="w-3.5 h-3.5" />
                    Review
                  </Link>
                  <Link
                    to={`/result?process_id=${p.id}`}
                    className="touch-min flex-1 flex items-center justify-center gap-1 px-3 py-2 border border-neo-black rounded text-xs font-semibold bg-ui-primary text-white  "
                    title="Lihat Rekapitulasi & Ekspor XLSX"
                  >
                    <FileSpreadsheet className="w-3.5 h-3.5 text-white" />
                    Hasil
                  </Link>
                  <button type="button" aria-label={`Unduh hasil XLSX proses ${p.id}`} disabled={download.isPending || (p.category !== undefined && !p.chosen_count)} onClick={() => download.mutate(p)} className="rounded border border-ui-border bg-white px-2 py-2 text-xs font-semibold disabled:opacity-50">{download.isPending && download.variables?.id === p.id ? "Menyiapkan..." : "XLSX"}</button>
                  {p.category && <button type="button" onClick={() => setParams({ process_id: String(p.id) })} className="text-xs font-semibold underline">Riwayat pilihan</button>}
                  <button
                    onClick={() => handleDeleteProcess(p.id, p.process_name)}
                    disabled={deletingId === p.id}
                    className="touch-min w-11 h-10 flex items-center justify-center border border-[#dc2626] rounded text-[#dc2626] bg-white hover:bg-[#fee2e2]   disabled:opacity-50"
                    title="Hapus riwayat proses ini"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop Table View (>= md) */}
          <div className="hidden md:block border border-ui-border rounded-lg bg-white  overflow-x-auto neo-scrollbar">
            <table className="w-full text-left text-[13px] border-collapse min-w-[760px]">
              <thead className="bg-slate-100 border-b border-ui-border">
                <tr>
                  <th className="p-3 border-r border-ui-border font-semibold">ID</th>
                  <th className="p-3 border-r border-ui-border font-semibold">Nama Proses</th>
                  <th className="p-3 border-r border-ui-border font-semibold">Tanggal Dibuat</th>
                  <th className="p-3 border-r border-ui-border font-semibold">Radius</th>
                  <th className="p-3 border-r border-ui-border font-semibold">Total Target</th>
                  <th className="p-3 border-r border-ui-border font-semibold">Cocok / Anomali</th>
                  <th className="p-3 border-r border-ui-border font-semibold">Status Review</th>
                  <th className="p-3 text-center font-semibold">Aksi Cepat</th>
                </tr>
              </thead>
              <tbody>
                {processes.map((p) => (
                  <tr key={p.id} className="border-b border-ui-border hover:bg-neo-white transition-colors">
                    <td className="p-3 border-r border-ui-border font-semibold">#{p.id}</td>
                    <td className="p-3 border-r border-ui-border font-semibold text-neo-black">
                      {p.process_name}
                      {p.category && <p className="mt-1 text-xs">{p.filename} | {p.partial ? "Hasil sebagian" : "Pemeriksaan selesai"} | {p.saved_rows} baris tersimpan | {p.not_processed} belum diproses | {p.chosen_count} pilihan aktif</p>}
                    </td>
                    <td className="p-3 border-r border-ui-border text-gray-600">
                      {new Date(p.created_at).toLocaleString("id-ID")}
                    </td>
                    <td className="p-3 border-r border-ui-border font-mono">{p.radius_meters} m</td>
                    <td className="p-3 border-r border-ui-border font-semibold">{p.total_targets}</td>
                    <td className="p-3 border-r border-ui-border">
                      <span className="text-[#16a34a] font-semibold">{p.matched_targets}</span> /{" "}
                      <span className="text-[#dc2626] font-semibold">{p.unmatched_targets}</span>
                    </td>
                    <td className="p-3 border-r border-ui-border">
                      <span className="neo-highlight px-2 py-1 border border-ui-border rounded text-xs uppercase font-semibold bg-neo-white">
                        {p.review_status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="p-3 text-center">
                      <div className="flex justify-center items-center gap-1.5">
                        <Link
                          to={p.category ? `/peta-koreksi?category=${p.category}&batch_id=${p.batch_id}&process_id=${p.id}` : `/candidates?process_id=${p.id}`}
                          className="px-2.5 py-1.5 min-h-[34px] flex items-center gap-1 border border-ui-border rounded text-xs font-semibold bg-white hover:bg-slate-100 "
                          title="Buka Peta & Review Kandidat"
                        >
                          <ExternalLink className="w-3 h-3" />
                          Review
                        </Link>
                        <Link
                          to={`/result?process_id=${p.id}`}
                          className="px-2.5 py-1.5 min-h-[34px] flex items-center gap-1 border border-ui-border rounded text-xs font-semibold bg-ui-primary text-white "
                          title="Lihat Rekapitulasi & Ekspor XLSX"
                        >
                          <FileSpreadsheet className="w-3 h-3 text-white" />
                          Hasil
                        </Link>
                        <button type="button" aria-label={`Unduh hasil XLSX proses ${p.id}`} disabled={download.isPending || (p.category !== undefined && !p.chosen_count)} onClick={() => download.mutate(p)} className="rounded border border-ui-border bg-white px-2 py-2 text-xs font-semibold disabled:opacity-50">{download.isPending && download.variables?.id === p.id ? "Menyiapkan..." : "XLSX"}</button>
                  {p.category && <button type="button" onClick={() => setParams({ process_id: String(p.id) })} className="text-xs font-semibold underline">Riwayat pilihan</button>}
                        <button
                          onClick={() => handleDeleteProcess(p.id, p.process_name)}
                          disabled={deletingId === p.id}
                          className="p-1.5 min-h-[34px] min-w-[34px] flex items-center justify-center border border-[#dc2626] rounded text-xs font-semibold text-[#dc2626] bg-white hover:bg-[#fee2e2]  disabled:opacity-50"
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
      {selected?.category && <><p className="text-sm font-semibold">Riwayat pemeriksaan #{selected.id} · Versi {generation} · Radius {radius ?? "…"} m</p><DecisionHistory key={`${selected.id}-${generation}`} kind={selected.category} processId={selected.id} generation={generation} radius={radius} /></>}
    </div>
  );
}
