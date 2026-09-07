'use client';

import type { StageSummary } from '@/lib/operations/procurement/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 0,
});

const BAND_HEIGHT_REM = 2.6;

type ApprovalFunnelProps = {
  title: string;
  hint?: string;
  stages: StageSummary[];
  emptyMessage?: string;
};

/**
 * How far the orders raised in this window have got. Each band is the count
 * that reached that stage **or went past it**, so the funnel narrows
 * monotonically and the step-to-step drop is what is still in flight at that
 * point in the pipeline.
 *
 * Unlike the pipeline snapshot, an order is counted in every band it has
 * cleared — that is what makes the conversion percentages meaningful.
 */
export function ApprovalFunnel({
  title,
  hint,
  stages,
  emptyMessage = 'No purchase orders for this perimeter.',
}: ApprovalFunnelProps) {
  const entry = stages[0]?.reachedCount ?? 0;

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className={`type-title-5${hint ? ' cursor-help' : ''}`} title={hint}>
          {title}
        </h3>
        <span className="text-xs text-[var(--text-muted)]">
          {entry} raised ·{' '}
          <span className="font-semibold tabular-nums text-[var(--text)]">
            {percentFormatter.format(
              stages[stages.length - 1]?.conversion ?? 0,
            )}
          </span>{' '}
          completed
        </span>
      </div>

      {entry === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <div className="space-y-1.5">
          {stages.map((stage, index) => {
            const widthPct = Math.max(6, stage.conversion * 100);
            const previous = index > 0 ? stages[index - 1] : null;
            const dropped = previous ? previous.reachedCount - stage.reachedCount : 0;
            return (
              <div key={stage.key} className="flex items-center gap-3">
                <span className="w-20 shrink-0 truncate text-xs font-medium">
                  {stage.label}
                </span>
                <div className="min-w-0 flex-1">
                  <div
                    className="relative flex items-center justify-center rounded-sm transition-[width] duration-500"
                    style={{
                      width: `${widthPct}%`,
                      height: `${BAND_HEIGHT_REM}rem`,
                      // Darkens down the funnel, so the surviving orders read
                      // as the concentrated core of what was raised.
                      backgroundColor: `color-mix(in srgb, var(--primary) ${
                        45 + index * 13
                      }%, var(--surface))`,
                    }}
                    title={`${stage.reachedCount} of ${entry} orders reached ${stage.label.toLowerCase()} — ${compactCurrency.format(
                      stage.reachedAmount,
                    )}`}
                  >
                    <span className="truncate px-2 text-[11px] font-semibold tabular-nums text-white">
                      {stage.reachedCount}
                    </span>
                  </div>
                </div>
                <span className="w-24 shrink-0 text-right text-[11px] tabular-nums text-[var(--text-muted)]">
                  {percentFormatter.format(stage.conversion)}
                  {dropped > 0 ? (
                    <span className="ml-1 text-[var(--recovery-orange)]">
                      −{dropped}
                    </span>
                  ) : null}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {entry > 0 ? (
        <p className="mt-3 text-xs text-[var(--text-muted)]">
          Orange marks how many orders have not yet cleared that step — the ones
          still sitting in approval, on order, or awaiting invoice.
        </p>
      ) : null}
    </div>
  );
}
