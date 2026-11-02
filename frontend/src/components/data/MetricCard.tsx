import { AlertCircle, CheckCircle2, Clock3, Layers3, ListFilter, History, LoaderCircle, type LucideIcon } from "lucide-react";

export type MetricTone = "primary" | "success" | "warning" | "danger" | "violet" | "neutral";

const icons: Record<MetricTone, LucideIcon> = {
  primary: Layers3,
  success: CheckCircle2,
  warning: Clock3,
  danger: AlertCircle,
  violet: History,
  neutral: ListFilter,
};

export function MetricCard({ label, value, tone = "neutral", icon, compact = false, definition = false, loading = false }: {
  label: string;
  value: string | number | undefined;
  tone?: MetricTone;
  icon?: LucideIcon;
  compact?: boolean;
  definition?: boolean;
  loading?: boolean;
}) {
  const Icon = loading ? LoaderCircle : icon ?? icons[tone];
  const Label = definition ? "dt" : "p";
  const Value = definition ? "dd" : "p";
  const displayed = typeof value === "number" ? value.toLocaleString("id-ID") : value ?? "—";
  return <div className={`geo-metric ${compact ? "geo-metric-compact" : ""}`} data-tone={tone} aria-busy={loading || undefined}>
    <Label className="geo-metric-label">{label}</Label>
    <Value className="geo-metric-value">{displayed}</Value>
    <span aria-hidden="true" className="geo-metric-icon"><Icon size={compact ? 15 : 18} className={loading ? "animate-spin" : undefined} /></span>
    {loading && <span className="sr-only">Jumlah sedang diperbarui</span>}
  </div>;
}
