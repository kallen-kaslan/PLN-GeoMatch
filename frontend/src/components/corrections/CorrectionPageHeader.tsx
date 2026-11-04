import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

export function CorrectionPageHeader({ title }: { title: string }) {
  return <header className="flex min-h-10 items-center gap-3">
    <Link to="/koreksi/idpel-kosong" aria-label="Kembali ke IDPEL Kosong" title="Kembali ke IDPEL Kosong" className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-ui-border bg-white text-ui-primary-text transition-colors hover:bg-ui-context focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ui-primary"><ArrowLeft aria-hidden="true" size={18} /></Link>
    <h1 className="text-lg font-semibold leading-snug tracking-tight sm:text-xl">{title}</h1>
  </header>;
}
