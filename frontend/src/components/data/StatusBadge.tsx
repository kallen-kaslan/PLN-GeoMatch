import type { ReactNode } from "react";

export function StatusBadge({ children, tone = "neutral" }: {
  children: ReactNode; tone?: "neutral" | "success" | "warning" | "danger" | "info";
}) {
  return <span className="geo-state" data-tone={tone}>{children}</span>;
}
