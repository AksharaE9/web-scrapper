export function formatDate(isoStr?: string): string {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    return d.toLocaleString("en-IN", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoStr;
  }
}

export function formatDuration(ms?: number): string {
  if (ms === undefined || ms === null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const secs = ms / 1000;
  if (secs < 60) return `${secs.toFixed(1)}s`;
  const mins = Math.floor(secs / 60);
  const remSecs = Math.round(secs % 60);
  return `${mins}m ${remSecs}s`;
}

export function formatPercent(val?: number): string {
  if (val === undefined || val === null || isNaN(val)) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

/**
 * Wilson score 95% confidence interval for a proportion
 */
export function computeWilsonScoreInterval(
  positive: number,
  total: number,
  z: number = 1.96
): { lower: number; upper: number; point: number } {
  if (total <= 0) return { lower: 0, upper: 0, point: 0 };
  const p = positive / total;
  const z2 = z * z;
  const denom = 1 + z2 / total;
  const center = (p + z2 / (2 * total)) / denom;
  const spread = (z * Math.sqrt((p * (1 - p) + z2 / (4 * total)) / total)) / denom;

  return {
    point: p,
    lower: Math.max(0, center - spread),
    upper: Math.min(1, center + spread),
  };
}
