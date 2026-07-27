export function fmt(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString();
}

export function deltaClass(delta: number | null | undefined): string {
  if (delta == null) return "flat";
  const r = Math.round(delta * 10) / 10;
  if (r > 0) return "pos";
  if (r < 0) return "neg";
  return "flat";
}

export function formatDelta(
  delta: number | null | undefined,
  suffix = "",
): string {
  if (delta == null) return "";
  const r = Math.round(delta * 10) / 10;
  if (r === 0) return `±0${suffix}`;
  return `${r > 0 ? "+" : ""}${r.toLocaleString()}${suffix}`;
}

export function pickByQueryScenario<T extends { query_slug: string; scenario_id: string }>(
  list: T[] | undefined,
  slug: string,
  scenarioId: string,
): T | null {
  return (list || []).find((x) => x.query_slug === slug && x.scenario_id === scenarioId) || null;
}
