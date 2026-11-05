import type { CorrectionKind } from "@/lib/master";
import { CORRECTION_TYPES } from "@/lib/corrections";
import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

export function CorrectionPageHeader({ title, kind = "idpel_kosong" }: { title: string; kind?: CorrectionKind }) {
  const descriptor = CORRECTION_TYPES.find((item) => item.key === kind)!;
  return <header className="flex min-h-10 items-center gap-3">
    <Link to={`/koreksi/${descriptor.slug}`} aria-label={`Kembali ke ${descriptor.label}`} title={`Kembali ke ${descriptor.label}`} className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-ui-border bg-white text-ui-primary-text transition-colors hover:bg-ui-context focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ui-primary"><ArrowLeft aria-hidden="true" size={18} /></Link>
    <h1 className="text-lg font-semibold leading-snug tracking-tight sm:text-xl">{title}</h1>
  </header>;
}
