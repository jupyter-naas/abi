'use client';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const CHART_HEIGHT_REM = 18;

/** Anchors (opening/closing totals) are solid; movements are signed. */
const TOTAL_COLOR = 'var(--secondary)';
const INFLOW_COLOR = 'var(--recovery-success)';
const OUTFLOW_COLOR = 'var(--recovery-danger)';

/**
 * One step of a waterfall. `isTotal` steps are absolute anchors drawn from
 * zero; the rest are deltas floating between `start` and `end`. Models compute
 * the running balance so the component stays purely presentational.
 */
export type WaterfallStep = {
  key: string;
  label: string;
  value: number;
  isTotal: boolean;
  start: number;
  end: number;
};

type WaterfallChartProps = {
  title: string;
  hint?: string;
  steps: WaterfallStep[];
  emptyMessage?: string;
  /** Formats the bar labels. Defaults to compact EUR. */
  formatValue?: (value: number) => string;
};

function colorFor(step: WaterfallStep): string {
  if (step.isTotal) {
    return TOTAL_COLOR;
  }
  return step.value >= 0 ? INFLOW_COLOR : OUTFLOW_COLOR;
}

/**
 * Floating-bar waterfall: absolute anchors at each end with signed deltas
 * stacked on the running balance between them. All bars share one scale
 * spanning the full range the running balance covers.
 */
export function WaterfallChart({
  title,
  hint,
  steps,
  emptyMessage = 'No data for this perimeter.',
  formatValue = (value: number) => compactCurrency.format(value),
}: WaterfallChartProps) {
  const bounds = steps.reduce(
    (acc, step) => ({
      min: Math.min(acc.min, step.start, step.end),
      max: Math.max(acc.max, step.start, step.end),
    }),
    { min: 0, max: 0 },
  );
  const span = bounds.max - bounds.min || 1;
  const zeroPct = ((bounds.max - 0) / span) * 100;

  return (
    <div className="glass rounded-lg p-6 h-full">
      <h3 className="type-title-5 mb-4" title={hint}>
        {title}
      </h3>
      {steps.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <div
            className="relative flex items-stretch gap-2 sm:gap-3"
            style={{ height: `${CHART_HEIGHT_REM}rem` }}
          >
            {bounds.min < 0 ? (
              <div
                className="pointer-events-none absolute inset-x-0 border-t border-dashed border-[var(--border)]"
                style={{ top: `${zeroPct}%` }}
                aria-hidden
              />
            ) : null}

            {steps.map((step) => {
              const top = Math.min(step.start, step.end);
              const bottom = Math.max(step.start, step.end);
              // Keep zero-height bars visible as a hairline.
              const heightPct = Math.max(0.6, ((bottom - top) / span) * 100);
              const topPct = ((bounds.max - bottom) / span) * 100;
              const color = colorFor(step);

              return (
                <div
                  key={step.key}
                  className="relative flex min-w-0 flex-1 flex-col"
                  title={`${step.label}: ${formatValue(step.value)}`}
                >
                  <div className="relative min-h-0 flex-1">
                    <div
                      className="absolute inset-x-0 rounded-sm"
                      style={{
                        top: `${topPct}%`,
                        height: `${heightPct}%`,
                        backgroundColor: color,
                        opacity: step.isTotal ? 1 : 0.85,
                      }}
                    />
                    <span
                      className="absolute inset-x-0 -translate-y-full pb-1 text-center text-[11px] font-semibold tabular-nums"
                      style={{ top: `${topPct}%`, color }}
                    >
                      {formatValue(step.value)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-2 flex gap-2 sm:gap-3">
            {steps.map((step) => (
              <span
                key={`label-${step.key}`}
                className="min-w-0 flex-1 truncate text-center text-[11px] text-[var(--text-muted)]"
                title={step.label}
              >
                {step.label}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
