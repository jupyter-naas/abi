'use client';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const CHART_HEIGHT_REM = 16;

const INFLOW_COLOR = 'var(--recovery-success)';
const OUTFLOW_COLOR = 'var(--recovery-danger)';
const NET_COLOR = 'var(--secondary)';

export type FlowBar = {
  key: string;
  label: string;
  inflow: number;
  outflow: number;
  net: number;
};

type InflowsOutflowsChartProps = {
  title: string;
  hint?: string;
  bars: FlowBar[];
  emptyMessage?: string;
};

/**
 * Gross flows around a zero axis: money in above the line, money out below,
 * with the net marked. Showing both gross sides rather than just the net makes
 * the scale of the churn visible — a small net movement can still hide very
 * large collections and payments.
 */
export function InflowsOutflowsChart({
  title,
  hint,
  bars,
  emptyMessage = 'No flows for this perimeter.',
}: InflowsOutflowsChartProps) {
  const extent = bars.reduce(
    (acc, bar) => Math.max(acc, bar.inflow, bar.outflow),
    0,
  );
  const scale = extent * 1.08 || 1;

  const totalIn = bars.reduce((sum, bar) => sum + bar.inflow, 0);
  const totalOut = bars.reduce((sum, bar) => sum + bar.outflow, 0);

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="type-title-5" title={hint}>
          {title}
        </h3>
        <div className="flex flex-wrap gap-4 text-xs text-[var(--text-muted)]">
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: INFLOW_COLOR }}
              aria-hidden
            />
            In
            <span className="font-semibold tabular-nums text-[var(--text)]">
              {compactCurrency.format(totalIn)}
            </span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: OUTFLOW_COLOR }}
              aria-hidden
            />
            Out
            <span className="font-semibold tabular-nums text-[var(--text)]">
              {compactCurrency.format(totalOut)}
            </span>
          </span>
        </div>
      </div>

      {bars.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <div
            className="relative flex items-center gap-1 sm:gap-2"
            style={{ height: `${CHART_HEIGHT_REM}rem` }}
          >
            <span
              className="pointer-events-none absolute inset-x-0 top-1/2 border-t border-[var(--border)]"
              aria-hidden
            />
            {bars.map((bar) => (
              <div
                key={bar.key}
                className="relative flex h-full min-w-0 flex-1 flex-col"
                title={`${bar.label} — in ${compactCurrency.format(
                  bar.inflow,
                )} · out ${compactCurrency.format(bar.outflow)} · net ${compactCurrency.format(bar.net)}`}
              >
                <div className="flex flex-1 items-end justify-center pb-px">
                  <div
                    className="w-2/3 max-w-[2rem] rounded-t-sm"
                    style={{
                      height: `${(bar.inflow / scale) * 100}%`,
                      backgroundColor: INFLOW_COLOR,
                    }}
                  />
                </div>
                <div className="flex flex-1 items-start justify-center pt-px">
                  <div
                    className="w-2/3 max-w-[2rem] rounded-b-sm"
                    style={{
                      height: `${(bar.outflow / scale) * 100}%`,
                      backgroundColor: OUTFLOW_COLOR,
                    }}
                  />
                </div>
                {/* Net marker, placed relative to the zero axis. */}
                <span
                  className="pointer-events-none absolute left-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
                  style={{
                    top: `${50 - (bar.net / scale) * 50}%`,
                    backgroundColor: NET_COLOR,
                  }}
                  aria-hidden
                />
              </div>
            ))}
          </div>

          <div className="mt-2 flex gap-1 sm:gap-2">
            {bars.map((bar, index) => (
              <span
                key={`label-${bar.key}`}
                className="min-w-0 flex-1 truncate text-center text-[10px] text-[var(--text-muted)]"
              >
                {bars.length > 8 && index % 2 === 1 ? '' : bar.label.split(' ')[0]}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
