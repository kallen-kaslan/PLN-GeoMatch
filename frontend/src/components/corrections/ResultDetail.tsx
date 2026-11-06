import { X } from "lucide-react";
import { InspectionDrawer } from "@/components/data/InspectionDrawer";
import { DecisionHistory } from "@/components/corrections/DecisionHistory";
import { buttonClass } from "@/lib/button";
import { displayValue, masterFieldLabel, type CorrectionKind } from "@/lib/master";
import { localTime, resultStatus, type SavedResult } from "@/lib/results";

export function ResultDetail({ row, category, processId, generation, radius, onClose }: {
  row: SavedResult;
  category: CorrectionKind;
  processId: number;
  generation?: number;
  radius?: number;
  onClose: () => void;
}) {
  const fields = Array.from(new Set([...Object.keys(row.target_fields), ...Object.keys(row.choice?.candidate.fields ?? {})]))
    .filter((key) => !key.startsWith("_") && key !== "validation_errors");
  const sources = row.choice?.candidate.observations ?? [];
  return <InspectionDrawer label="Panel detail hasil koreksi" onClose={onClose}>
    <section aria-label="Detail hasil koreksi" className="space-y-5">
      <header className="flex items-start justify-between gap-3">
        <div><h2 className="text-base font-semibold">Detail hasil · Baris {row.row_number}</h2><p className="mt-1 text-xs text-ui-muted">Perbandingan target, sumber kandidat, dan riwayat pilihan.</p></div>
        <button type="button" onClick={onClose} aria-label="Tutup detail hasil" className={buttonClass.secondary}><X size={18} /></button>
      </header>
      <div className="space-y-2 rounded-lg border border-ui-border bg-neo-white p-4 text-sm">
        <p className="font-semibold">{resultStatus[row.status]}</p>
        {row.choice ? <><p>{row.choice.actor} · {localTime(row.choice.created_at)}</p><p>Versi pilihan {row.choice.generation} · Revisi {row.choice.revision}</p><p>Alasan: {row.choice.reason || "Pemilihan pertama"}</p></> : <p className="text-ui-muted">Belum ada pilihan kandidat yang disimpan.</p>}
      </div>
      <section aria-label="Perbandingan target dan kandidat">
        <h3 className="mb-3 text-sm font-semibold">Perbandingan target dan kandidat</h3>
        <div className="grid grid-cols-2 gap-3 border-b border-ui-border pb-2 text-xs font-semibold text-ui-muted"><p>Target sebelum koreksi</p><p>Kandidat terpilih</p></div>
        <dl className="divide-y divide-gray-200">{fields.map((key) => <div key={key} className="py-3">
          <dt className="text-xs font-semibold text-ui-muted">{masterFieldLabel(key)}</dt>
          <dd className="mt-1 grid grid-cols-2 gap-3 text-sm"><span className="min-w-0 break-words">{displayValue(row.target_fields[key])}</span><span className="min-w-0 break-words">{displayValue(row.choice?.candidate.fields?.[key])}</span></dd>
        </div>)}</dl>
      </section>
      <section aria-label="Sumber kandidat terpilih"><h3 className="mb-3 text-sm font-semibold">Sumber kandidat terpilih</h3>
        {sources.length ? <ul className="space-y-3">{sources.map((source, index) => <li key={index} className="rounded-lg border border-ui-border p-3 text-xs">
          <p className="break-words font-semibold">{source.filename}</p><p className="mt-1">{source.dataset_type.toUpperCase()} · Baris {source.row_number} · Periode {displayValue(source.fields.tglbaca)}</p>
          {source.source_sheet && <p className="mt-1 break-words">Sheet: {source.source_sheet}</p>}
        </li>)}</ul> : <p className="text-sm text-ui-muted">Belum ada sumber kandidat terpilih.</p>}
      </section>
      <DecisionHistory kind={category} processId={processId} recordId={row.record_id} generation={generation} radius={radius} />
    </section>
  </InspectionDrawer>;
}
