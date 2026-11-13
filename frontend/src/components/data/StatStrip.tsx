import type { MetricTone } from "./MetricCard";

export function StatStrip({ items, label }: { label: string; items: { label: string; value: number | string | undefined; tone?: MetricTone }[] }) {
  return <dl aria-label={label} className="geo-stats-strip">{items.map((item) => <div key={item.label} className="geo-stat" data-tone={item.tone ?? "neutral"}><dt>{item.label}</dt><dd>{typeof item.value === "number" ? item.value.toLocaleString("id-ID") : item.value ?? "—"}</dd></div>)}</dl>;
}
