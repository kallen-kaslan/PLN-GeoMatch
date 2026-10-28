export function progressPercent(processed: number, validated: number, total: number, ready: boolean, extraDone = 0, extraTotal = 0) {
  if (ready) return 100;
  if (2 * total + extraTotal <= 0) return 0;
  return Math.min(99.99, 100 * (processed + validated + extraDone) / (2 * total + extraTotal));
}

export function progressLabel(percent: number) {
  return percent > 0 && percent < 0.01 ? "<0,01%" : `${percent.toLocaleString("id-ID", { maximumFractionDigits: 2 })}%`;
}
