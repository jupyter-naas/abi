'use client';

/**
 * Generic two-axis heatmap. Shared by the scenario sensitivity matrix (two
 * drivers crossed) and the cost-center variance grid (departments × months).
 *
 * `scale` picks how a cell value maps to colour:
 * - `diverging` centres on zero — negative one hue, positive the other. Use it
 *   for signed quantities like a variance rate.
 * - `sequential` runs low-to-high across the observed range. Use it for
 *   quantities where only the magnitude matters.
 *
 * `goodDirection` decides which end reads as favourable, so a diverging grid
 * can show overspend as red while showing extra EBITDA as green.
 */

const POSITIVE_GOOD = {
  positive: 'var(--recovery-success)',
  negative: 'var(--recovery-danger)',
};
const NEGATIVE_GOOD = {
  positive: 'var(--recovery-danger)',
  negative: 'var(--recovery-success)',
};

type HeatmapGridProps = {
  title: string;
  hint?: string;
  /** Row axis: label shown on the left of each row. */
  rowLabels: string[];
  /** Column axis: label shown in the header. */
  colLabels: string[];
  /** `cells[rowIndex][colIndex]`. */
  cells: number[][];
  formatValue: (value: number) => string;
  scale?: 'diverging' | 'sequential';
  /** Which sign reads as good. Ignored by the sequential scale. */
  goodDirection?: 'positive' | 'negative';
  rowAxisLabel?: string;
  colAxisLabel?: string;
  emptyMessage?: string;
  /** Render values inside the cells. Off for dense grids. */
  showValues?: boolean;
};

export function HeatmapGrid({
  title,
  hint,
  rowLabels,
  colLabels,
  cells,
  formatValue,
  scale = 'diverging',
  goodDirection = 'positive',
  rowAxisLabel,
  colAxisLabel,
  emptyMessage = 'No data for this perimeter.',
  showValues = true,
}: HeatmapGridProps) {
  const flat = cells.flat();
  const isEmpty = rowLabels.length === 0 || colLabels.length === 0 || flat.length === 0;

  const max = isEmpty ? 0 : Math.max(...flat);
  const min = isEmpty ? 0 : Math.min(...flat);
  // A diverging scale is symmetric around zero so equal magnitudes of either
  // sign read equally strong.
  const extent = Math.max(Math.abs(max), Math.abs(min)) || 1;
  const range = max - min || 1;

  const hues = goodDirection === 'positive' ? POSITIVE_GOOD : NEGATIVE_GOOD;

  function backgroundFor(value: number): string {
    if (scale === 'sequential') {
      const intensity = (value - min) / range;
      return `color-mix(in srgb, var(--primary) ${Math.round(
        12 + intensity * 68,
      )}%, transparent)`;
    }
    const intensity = Math.min(1, Math.abs(value) / extent);
    const hue = value >= 0 ? hues.positive : hues.negative;
    return `color-mix(in srgb, ${hue} ${Math.round(intensity * 72)}%, transparent)`;
  }

  return (
    <div className="glass rounded-lg p-6 h-full">
      <h3 className="type-title-5 mb-4" title={hint}>
        {title}
      </h3>

      {isEmpty ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          {colAxisLabel ? (
            <p className="mb-2 text-xs text-[var(--text-muted)]">{colAxisLabel} →</p>
          ) : null}
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-xs">
              <thead>
                <tr>
                  <th className="sticky left-0 z-10 bg-[var(--surface)] px-2 py-1.5 text-left font-medium text-[var(--text-muted)]">
                    {rowAxisLabel ?? ''}
                  </th>
                  {colLabels.map((label) => (
                    <th
                      key={label}
                      className="px-2 py-1.5 text-right font-medium text-[var(--text-muted)] whitespace-nowrap"
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rowLabels.map((rowLabel, rowIndex) => (
                  <tr key={rowLabel}>
                    <td
                      className="sticky left-0 z-10 max-w-[10rem] truncate bg-[var(--surface)] px-2 py-1.5 font-medium"
                      title={rowLabel}
                    >
                      {rowLabel}
                    </td>
                    {colLabels.map((colLabel, colIndex) => {
                      const value = cells[rowIndex]?.[colIndex] ?? 0;
                      return (
                        <td
                          key={`${rowLabel}-${colLabel}`}
                          className="px-2 py-1.5 text-right tabular-nums whitespace-nowrap"
                          style={{ backgroundColor: backgroundFor(value) }}
                          title={`${rowLabel} · ${colLabel}: ${formatValue(value)}`}
                        >
                          {showValues ? formatValue(value) : ''}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rowAxisLabel ? (
            <p className="mt-2 text-xs text-[var(--text-muted)]">↓ {rowAxisLabel}</p>
          ) : null}
        </>
      )}
    </div>
  );
}
