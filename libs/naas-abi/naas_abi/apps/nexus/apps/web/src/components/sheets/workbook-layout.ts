/** Sparse pixel dimensions: offsets stay cheap even near Excel's last row. */
export function sheetAxis(count: number, fallback: number, overrides: Record<string, number> = {}) {
  const entries = Object.entries(overrides).map(([key, value]) => [Number(key), value] as const)
    .filter(([key, value]) => Number.isInteger(key) && key >= 0 && key < count && Number.isFinite(value) && value > 0)
    .sort((a, b) => a[0] - b[0]);
  const sizes = new Map(entries);
  const offset = (index: number) => index * fallback + entries.reduce((sum, [key, value]) => sum + (key < index ? value - fallback : 0), 0);
  const at = (pixel: number) => {
    let low = 0; let high = count - 1;
    while (low < high) { const mid = Math.ceil((low + high) / 2); if (offset(mid) <= pixel) low = mid; else high = mid - 1; }
    return low;
  };
  return { offset, at, size: (index: number) => sizes.get(index) ?? fallback };
}
