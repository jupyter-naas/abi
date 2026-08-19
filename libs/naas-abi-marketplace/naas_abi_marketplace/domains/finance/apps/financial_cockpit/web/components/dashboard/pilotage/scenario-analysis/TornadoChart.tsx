'use client';

import { formatDriverValue, type Driver } from '@/lib/pilotage/scenarioAnalysis/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const FAVOURABLE = 'var(--recovery-success)';
const ADVERSE = 'var(--recovery-danger)';

type TornadoChartProps = {
  title: string;
  hint?: string;
  drivers: Driver[];
  emptyMessage?: string;
};

/**
 * Diverging bars around a zero axis: for each driver, how far EBITDA moves when
 * that driver alone swings to its low and high bound. Ordered by total swing
 * (widest at the top) — the tornado shape that gives the chart its name, and
 * the reason it reads as a ranking of what matters most.
 */
export function TornadoChart({
  title,
  hint,
  drivers,
  emptyMessage = 'No drivers for this perimeter.',
}: TornadoChartProps) {
  const extent = drivers.reduce(
    (acc, driver) => Math.max(acc, Math.abs(driver.lowImpact), Math.abs(driver.highImpact)),
    0,
  );
  const scale = extent * 1.08 || 1;

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
              style={{ backgroundColor: ADVERSE }}
              aria-hidden
            />
            Adverse
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: FAVOURABLE }}
              aria-hidden
            />
            Favourable
          </span>
        </div>
      </div>

      {drivers.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <ul className="space-y-3">
          {drivers.map((driver) => {
            const negative = Math.min(driver.lowImpact, driver.highImpact, 0);
            const positive = Math.max(driver.lowImpact, driver.highImpact, 0);
            // Both halves are measured from the centre line at 50 %.
            const negativePct = (Math.abs(negative) / scale) * 50;
            const positivePct = (positive / scale) * 50;

            return (
              <li key={driver.key}>
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <span
                    className="min-w-0 truncate text-sm font-medium"
                    title={driver.hint ?? driver.label}
                  >
                    {driver.label}
                  </span>
                  <span className="shrink-0 text-xs tabular-nums text-[var(--text-muted)]">
                    {formatDriverValue(driver.lowValue, driver.unit)} …{' '}
                    {formatDriverValue(driver.highValue, driver.unit)}
                  </span>
                </div>

                <div className="relative h-4">
                  <span
                    className="absolute inset-y-0 left-1/2 w-px bg-[var(--border)]"
                    aria-hidden
                  />
                  <span
                    className="absolute inset-y-0 rounded-l-sm"
                    style={{
                      right: '50%',
                      width: `${negativePct}%`,
                      backgroundColor: ADVERSE,
                    }}
                    title={`Adverse: ${compactCurrency.format(negative)}`}
                  />
                  <span
                    className="absolute inset-y-0 rounded-r-sm"
                    style={{
                      left: '50%',
                      width: `${positivePct}%`,
                      backgroundColor: FAVOURABLE,
                    }}
                    title={`Favourable: ${compactCurrency.format(positive)}`}
                  />
                </div>

                <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--text-muted)]">
                  <span>{compactCurrency.format(negative)}</span>
                  <span>{compactCurrency.format(positive)}</span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
