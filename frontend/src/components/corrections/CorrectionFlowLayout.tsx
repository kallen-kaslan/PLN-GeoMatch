import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export interface FlowDocument { filename?: string; sheet?: string | null; previewRows?: number; totalRows?: number }
const defaultSteps = ["Unggah berkas", "Analisis radius", "Atur radius", "Cari kandidat"];

export function CorrectionFlowLayout({ stage, onStep, availableSteps, children, footer, steps = defaultSteps }: {
  stage: number; onStep?: (stage: number) => void; availableSteps?: number[];
  document?: FlowDocument; radius?: string; children: ReactNode; footer?: ReactNode;
  steps?: string[];
}) {
  return <div className="space-y-5">
    <header className="flex items-center gap-3">
      <Link to="/koreksi/idpel-kosong" aria-label="Kembali ke IDPEL Kosong" title="Kembali ke IDPEL Kosong" className="flex size-11 shrink-0 items-center justify-center rounded-md border border-ui-border bg-white text-ui-primary-text transition-colors hover:border-ui-primary/35 hover:bg-ui-context focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ui-primary"><ArrowLeft aria-hidden="true" size={20} /></Link>
      <h1 className="text-2xl font-bold tracking-tight">IDPEL Kosong</h1>
    </header>
    <ol aria-label="Tahap IDPEL Kosong" className={`grid gap-3 ${steps.length === 2 ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4"}`}>{steps.map((label, index) => <li key={label}><button type="button" onClick={() => onStep?.(index + 1)} disabled={!onStep || (!!availableSteps && !availableSteps.includes(index + 1))} aria-current={stage === index + 1 ? "step" : undefined} className={`flex h-full w-full items-center gap-3 border-b-2 px-1 py-4 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 ${stage === index + 1 ? "border-ui-primary font-semibold text-neo-black" : "border-gray-200 text-gray-500"}`}><span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs ${stage === index + 1 ? "bg-ui-primary text-white" : "bg-gray-100 text-gray-500"}`}>{index + 1}</span>{label}</button></li>)}</ol>
    <div className="min-w-0 space-y-4">{children}</div>
    {footer && <nav aria-label="Navigasi tahap" className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 pt-4">{footer}</nav>}
  </div>;
}
