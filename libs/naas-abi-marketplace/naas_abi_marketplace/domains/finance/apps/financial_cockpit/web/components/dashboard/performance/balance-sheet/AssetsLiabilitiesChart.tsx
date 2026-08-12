'use client';

import type { BalanceBar } from '@/lib/performance/balanceSheet/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const ASSET_COLORS = ['var(--primary)', 'color-mix(in srgb, var(--primary) 50%, var(--surface))'];
const FINANCING_COLORS = [
  'var(--recovery-success)',
  'var(--recovery-orange)',
  'var(--recovery-warning)',
];

const COLUMN_HEIGHT_REM = 16;

type StackColumn = { heading: string; total: number; bars: BalanceBar[]; colors: string[] };

function Column({ column, maxTotal }: { column: StackColumn; maxTotal: number }) {
  const heightPct = maxTotal > 0 ? (column.total / maxTotal) * 100 : 0;
  return (
    <div className="flex min-w-0 flex-1 flex-col items-center">
      <span className="mb-1 text-sm font-semibold tabular-nums">
        {compactCurrency.format(column.total)}
      </span>
      <div
        className="flex w-full max-w-[7rem] flex-col justify-end"
        style={{ height: `${COLUMN_HEIGHT_REM}rem` }}
      >
        <div
          className="flex w-full flex-col overflow-hidden rounded-md"
          style={{ height: `${heightPct}%` }}
        >
          {column.bars.map((bar, index) => {
            const segmentPct = column.total > 0 ? (bar.value / column.total) * 100 : 0;
            return (
              <div
                key={bar.key}
                className="w-full"
                style={{
                  height: `${segmentPct}%`,
                  backgroundColor: column.colors[index % column.colors.length],
                }}
                title={`${bar.label}: ${compactCurrency.format(bar.value)}`}
              />
            );
          })}
        </div>
      </div>
      <span className="mt-2 text-xs font-medium text-[var(--text-muted)]">
        {column.heading}
      </span>
    </div>
  );
}

type AssetsLiabilitiesChartProps = {
  title: string;
  hint?: string;
  assets: BalanceBar[];
  financing: BalanceBar[];
};

export function AssetsLiabilitiesChart({
  title,
  hint,
  assets,
  financing,
}: AssetsLiabilitiesChartProps) {
  const assetsTotal = assets.reduce((sum, bar) => sum + bar.value, 0);
  const financingTotal = financing.reduce((sum, bar) => sum + bar.value, 0);
  const maxTotal = Math.max(assetsTotal, financingTotal, 1);

  const columns: StackColumn[] = [
    { heading: 'Assets', total: assetsTotal, bars: assets, colors: ASSET_COLORS },
    {
      heading: 'Equity & Liabilities',
      total: financingTotal,
      bars: financing,
      colors: FINANCING_COLORS,
    },
  ];

  const legend = [
    ...assets.map((bar, index) => ({
      key: `a-${bar.key}`,
      label: bar.label,
      color: ASSET_COLORS[index % ASSET_COLORS.length],
    })),
    ...financing.map((bar, index) => ({
      key: `f-${bar.key}`,
      label: bar.label,
      color: FINANCING_COLORS[index % FINANCING_COLORS.length],
    })),
  ];

  return (
    <div className="glass rounded-lg p-6 h-full">
      <h3 className="type-title-5 mb-4" title={hint}>
        {title}
      </h3>
      {assetsTotal <= 0 && financingTotal <= 0 ? (
        <p className="text-sm text-[var(--text-muted)]">No data for this perimeter.</p>
      ) : (
        <>
          <div className="flex items-end justify-center gap-10">
            {columns.map((column) => (
              <Column key={column.heading} column={column} maxTotal={maxTotal} />
            ))}
          </div>
          <ul className="mt-6 grid grid-cols-2 gap-x-4 gap-y-1.5">
            {legend.map((item) => (
              <li key={item.key} className="flex items-center gap-2 text-xs">
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                  style={{ backgroundColor: item.color }}
                  aria-hidden
                />
                <span className="min-w-0 truncate text-[var(--text-muted)]" title={item.label}>
                  {item.label}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
