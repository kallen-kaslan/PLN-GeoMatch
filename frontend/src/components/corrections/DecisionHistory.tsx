import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { buttonClass } from "@/lib/button";
import { displayValue, type CorrectionKind } from "@/lib/master";
import { localTime, resultsApi } from "@/lib/results";

export function DecisionHistory({ kind, processId, recordId }: { kind: CorrectionKind; processId: number; recordId?: number }) {
  const [page, setPage] = useState(1);
  const events = useQuery({ queryKey: ["correction-decisions", processId, recordId, page], queryFn: ({ signal }) => resultsApi.history(kind, processId, recordId, (page - 1) * 20, signal), refetchInterval: 5000 });
  const pages = Math.max(1, Math.ceil((events.data?.total ?? 0) / 20));
  return <section aria-label="Riwayat keputusan koreksi" className="space-y-3 rounded-sm border-2 border-neo-border bg-white p-4 sm:p-5">
    <h2 className="text-base font-black">Riwayat pilihan kandidat</h2>
    <p className="text-xs text-neo-border">{events.data?.total ?? 0} perubahan tersimpan pada pemeriksaan #{processId}. Pilihan, penggantian, dan pembatalan dicatat beserta petugas dan alasannya.</p>
    {events.isPending ? <p role="status">Memuat riwayat pilihan...</p> : events.isError ? <p role="alert">Riwayat belum dapat dimuat.</p> : events.data?.items.length ? <ol className="space-y-3">{events.data.items.map((event) => <li key={event.id} className="space-y-1 rounded-sm border border-gray-300 p-3 text-xs">
      <p className="font-bold">Baris {event.row_number} · Revisi {event.revision} · Versi pemeriksaan {event.generation}</p>
      <p>{event.candidate_id ? `Kandidat dipilih: ${displayValue(event.candidate.fields?.idpel)} · ${displayValue(event.candidate.fields?.nama)} · ${event.candidate.distance_meters?.toLocaleString("id-ID", { maximumFractionDigits: 2 })} m` : "Pilihan kandidat dibatalkan"}</p>
      <p>{event.actor} · {localTime(event.created_at)}</p><p>Alasan: {event.reason || "Pemilihan pertama"}</p>
      <details><summary className="cursor-pointer font-bold">Data target dan bukti pilihan</summary><p className="mt-2">Target: {displayValue(event.target_fields.idpel)} · {displayValue(event.target_fields.nama)} · {displayValue(event.target_fields.lat)}, {displayValue(event.target_fields.lon)}</p>
        <ul className="mt-2 space-y-1">{event.candidate.observations?.map((source, index) => <li key={index}>{source.filename} · {source.dataset_type.toUpperCase()} · Baris {source.row_number} · Periode {displayValue(source.fields.tglbaca)}</li>)}</ul>
      </details>
    </li>)}</ol> : <p className="text-sm">Belum ada pilihan kandidat yang disimpan.</p>}
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs"><span>Halaman {page} dari {pages}</span><div className="flex gap-2"><button type="button" className={buttonClass.secondary} disabled={page <= 1 || events.isFetching} onClick={() => setPage(page - 1)}>Riwayat sebelumnya</button><button type="button" className={buttonClass.secondary} disabled={page >= pages || events.isFetching} onClick={() => setPage(page + 1)}>Riwayat berikutnya</button></div></div>
  </section>;
}
