'use client';

import { formatRatioValue, type RatioSummary } from '@/lib/performance/financialRatios/model';

const ACTUAL_ABOVE = 'var(--recovery-success)';
const ACTUAL_BELOW = 'var(--recovery-danger)';
const BENCHMARK_COLOR = 'var(--text-muted)';

type BenchmarkChartProps = {
  title: string;
  hint?: string;
  ratios: RatioSummary[];
  emptyMessage?: string;
};

/**
 * One row per ratio: the actual value as a filled bar against a benchmark
 * marker. Each row is scaled to its own maximum because the ratios carry
 * different units (percentages and multiples), so bar lengths are only
 * comparable to the marker on the same row — never across rows.
 */
export function BenchmarkChart({
  title,
  hint,
  ratios,
  emptyMessage = 'No data for this perimeter.',
}: BenchmarkChartProps) {
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
              style={{ backgroundColor: ACTUAL_ABOVE }}
              aria-hidden
            />
            Actual
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-0.5"
              style={{ backgroundColor: BENCHMARK_COLOR }}
              aria-hidden
            />
            Industry benchmark
          </span>
        </div>
      </div>

      {ratios.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <ul className="space-y-3">
          {ratios.map((ratio) => {
            const scale = Math.max(ratio.value, ratio.benchmark, 0) * 1.15 || 1;
            const valuePct = Math.max(0, Math.min(100, (ratio.value / scale) * 100));
            const benchmarkPct = Math.max(
              0,
              Math.min(100, (ratio.benchmark / scale) * 100),
            );
            const color = ratio.status === 'below' ? ACTUAL_BELOW : ACTUAL_ABOVE;

            return (
              <li key={ratio.key}>
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <span
                    className="min-w-0 truncate text-sm font-medium"
                    title={ratio.hint ?? ratio.label}
                  >
                    {ratio.label}
                  </span>
                  <span className="shrink-0 text-sm tabular-nums" style={{ color }}>
                    {formatRatioValue(ratio.value, ratio.unit)}
                  </span>
                </div>
                <div className="progress-bar-bg relative h-3 overflow-hidden rounded-sm">
                  <div
                    className="h-full rounded-sm transition-[width] duration-500"
                    style={{ width: `${valuePct}%`, backgroundColor: color }}
                  />
                  <span
                    className="absolute inset-y-0 w-0.5"
                    style={{ left: `${benchmarkPct}%`, backgroundColor: BENCHMARK_COLOR }}
                    title={`Benchmark: ${formatRatioValue(ratio.benchmark, ratio.unit)}`}
                    aria-hidden
                  />
                </div>
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  Benchmark {formatRatioValue(ratio.benchmark, ratio.unit)} · Target{' '}
                  {formatRatioValue(ratio.target, ratio.unit)}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
