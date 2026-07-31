'use client';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const CHART_HEIGHT_REM = 22;

/** Group palette — theme tokens only, cycled if there are more groups. */
const GROUP_COLORS = [
  'var(--primary)',
  'var(--secondary)',
  'var(--recovery-success)',
  'var(--recovery-orange)',
  'color-mix(in srgb, var(--primary) 45%, var(--surface))',
];

type Rect = { x: number; y: number; width: number; height: number };

export type TreemapLeaf = {
  key: string;
  label: string;
  value: number;
};

export type TreemapGroup = {
  key: string;
  label: string;
  value: number;
  leaves: TreemapLeaf[];
};

type TreemapProps = {
  title: string;
  hint?: string;
  groups: TreemapGroup[];
  emptyMessage?: string;
  /** Formats tile and legend values. Defaults to compact EUR. */
  formatValue?: (value: number) => string;
};

/**
 * Squarified treemap: groups are laid out first, then each group's leaves are
 * laid out inside its rectangle. Area is proportional to value, so the largest
 * tile is the biggest number — the point of the chart.
 *
 * The layout is the standard squarified algorithm: fill the shorter side of the
 * remaining space with a row of tiles, extending it while doing so improves the
 * worst aspect ratio in that row, then recurse on what is left.
 */
export function squarify<T extends { value: number }>(
  items: T[],
  rect: Rect,
): (Rect & { item: T })[] {
  const out: (Rect & { item: T })[] = [];
  const queue = [...items].sort((a, b) => b.value - a.value).filter((i) => i.value > 0);
  let remaining = { ...rect };
  const total = queue.reduce((sum, item) => sum + item.value, 0);
  if (total <= 0) {
    return out;
  }
  // Convert values into area units of the target rectangle.
  const area = remaining.width * remaining.height;
  const scaled = queue.map((item) => ({ item, area: (item.value / total) * area }));

  function worst(row: { area: number }[], side: number): number {
    if (row.length === 0 || side === 0) {
      return Number.POSITIVE_INFINITY;
    }
    const sum = row.reduce((acc, entry) => acc + entry.area, 0);
    const max = Math.max(...row.map((entry) => entry.area));
    const min = Math.min(...row.map((entry) => entry.area));
    const side2 = side * side;
    const sum2 = sum * sum;
    return Math.max((side2 * max) / sum2, sum2 / (side2 * min));
  }

  let index = 0;
  while (index < scaled.length) {
    const vertical = remaining.width >= remaining.height;
    const side = vertical ? remaining.height : remaining.width;
    const row: typeof scaled = [scaled[index]];
    index += 1;
    while (
      index < scaled.length &&
      worst([...row, scaled[index]], side) <= worst(row, side)
    ) {
      row.push(scaled[index]);
      index += 1;
    }

    const rowArea = row.reduce((sum, entry) => sum + entry.area, 0);
    const thickness = side > 0 ? rowArea / side : 0;
    let offset = 0;
    for (const entry of row) {
      const length = rowArea > 0 ? (entry.area / rowArea) * side : 0;
      out.push({
        item: entry.item,
        x: vertical ? remaining.x : remaining.x + offset,
        y: vertical ? remaining.y + offset : remaining.y,
        width: vertical ? thickness : length,
        height: vertical ? length : thickness,
      });
      offset += length;
    }

    if (vertical) {
      remaining = {
        x: remaining.x + thickness,
        y: remaining.y,
        width: Math.max(0, remaining.width - thickness),
        height: remaining.height,
      };
    } else {
      remaining = {
        x: remaining.x,
        y: remaining.y + thickness,
        width: remaining.width,
        height: Math.max(0, remaining.height - thickness),
      };
    }
  }

  return out;
}

export function Treemap({
  title,
  hint,
  groups,
  emptyMessage = 'No data for this perimeter.',
  formatValue = (value: number) => compactCurrency.format(value),
}: TreemapProps) {
  const total = groups.reduce((sum, group) => sum + group.value, 0);

  const groupTiles = squarify(
    groups.map((group) => ({ value: group.value, group })),
    { x: 0, y: 0, width: 100, height: 100 },
  );

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className={`type-title-5${hint ? ' cursor-help' : ''}`} title={hint}>
          {title}
        </h3>
        <span className="text-xs text-[var(--text-muted)]">
          Total{' '}
          <span className="font-semibold tabular-nums text-[var(--text)]">
            {formatValue(total)}
          </span>
        </span>
      </div>

      {total <= 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <div
            className="relative w-full overflow-hidden rounded-md"
            style={{ height: `${CHART_HEIGHT_REM}rem` }}
          >
            {groupTiles.map((groupTile, groupIndex) => {
              const color = GROUP_COLORS[groupIndex % GROUP_COLORS.length];
              const group = groupTile.item.group;
              const leafTiles = squarify(
                group.leaves.map((leaf) => ({ value: leaf.value, leaf })),
                {
                  x: groupTile.x,
                  y: groupTile.y,
                  width: groupTile.width,
                  height: groupTile.height,
                },
              );

              return leafTiles.map((tile) => {
                const leaf = tile.item.leaf;
                const share = total > 0 ? leaf.value / total : 0;
                // Only label tiles with room for text.
                const showLabel = tile.width > 12 && tile.height > 9;
                return (
                  <div
                    key={`${group.key}-${leaf.key}`}
                    className="absolute overflow-hidden border border-[var(--surface)] p-1.5"
                    style={{
                      left: `${tile.x}%`,
                      top: `${tile.y}%`,
                      width: `${tile.width}%`,
                      height: `${tile.height}%`,
                      backgroundColor: color,
                      opacity: 0.55 + 0.45 * share * (groups.length || 1),
                    }}
                    title={`${group.label} · ${leaf.label}: ${formatValue(
                      leaf.value,
                    )} (${percentFormatter.format(share)})`}
                  >
                    {showLabel ? (
                      <>
                        <p className="truncate text-[11px] font-semibold leading-tight text-white">
                          {leaf.label}
                        </p>
                        <p className="truncate text-[10px] tabular-nums leading-tight text-white/80">
                          {formatValue(leaf.value)}
                        </p>
                      </>
                    ) : null}
                  </div>
                );
              });
            })}
          </div>

          <ul className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5">
            {groups.map((group, index) => (
              <li key={group.key} className="inline-flex items-center gap-1.5 text-xs">
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                  style={{
                    backgroundColor: GROUP_COLORS[index % GROUP_COLORS.length],
                  }}
                  aria-hidden
                />
                <span className="text-[var(--text-muted)]">{group.label}</span>
                <span className="tabular-nums">{formatValue(group.value)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
