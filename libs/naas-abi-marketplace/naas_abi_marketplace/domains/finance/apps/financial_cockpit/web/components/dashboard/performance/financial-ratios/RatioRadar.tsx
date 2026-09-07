'use client';

import { formatRatioValue, type RatioSummary } from '@/lib/performance/financialRatios/model';

/** Score axis: 0 at the centre, 1 = benchmark, 2 = twice the benchmark. */
const MAX_SCORE = 2;
const BENCHMARK_SCORE = 1;
const RADIUS = 38;
const CENTRE = 50;

const ACTUAL_COLOR = 'var(--primary)';
const BENCHMARK_COLOR = 'var(--text-muted)';

type RatioRadarProps = {
  title: string;
  hint?: string;
  ratios: RatioSummary[];
  emptyMessage?: string;
};

type Point = { x: number; y: number };

/** Axis `index` of `count`, at `score` along it. First axis points straight up. */
function pointAt(index: number, count: number, score: number): Point {
  const angle = (index / count) * 2 * Math.PI - Math.PI / 2;
  const distance = (Math.min(score, MAX_SCORE) / MAX_SCORE) * RADIUS;
  return {
    x: CENTRE + Math.cos(angle) * distance,
    y: CENTRE + Math.sin(angle) * distance,
  };
}

function polygon(points: Point[]): string {
  return points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(' ');
}

/**
 * Normalized health radar. Every ratio is plotted as `value / benchmark`
 * (inverted for lower-is-better ratios), so the mixed units share one axis and
 * the dashed ring marks "exactly at benchmark". Scores are clamped at twice the
 * benchmark by the model so one outlier cannot flatten the shape.
 */
export function RatioRadar({
  title,
  hint,
  ratios,
  emptyMessage = 'No data for this perimeter.',
}: RatioRadarProps) {
  const count = ratios.length;
  const actual = ratios.map((ratio, index) => pointAt(index, count, ratio.score));
  const benchmark = ratios.map((_, index) => pointAt(index, count, BENCHMARK_SCORE));

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
              style={{ backgroundColor: ACTUAL_COLOR }}
              aria-hidden
            />
            Actual
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-0 w-3 border-t border-dashed"
              style={{ borderColor: BENCHMARK_COLOR }}
              aria-hidden
            />
            Benchmark
          </span>
        </div>
      </div>

      {count < 3 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <div className="flex flex-wrap items-center gap-6">
          <div className="relative h-52 w-52 shrink-0">
            <svg viewBox="0 0 100 100" className="h-full w-full" aria-hidden>
              {/* Concentric grid rings at 0.5 / 1.0 / 1.5 / 2.0 × benchmark. */}
              {[0.5, 1, 1.5, 2].map((score) => (
                <polygon
                  key={score}
                  points={polygon(
                    ratios.map((_, index) => pointAt(index, count, score)),
                  )}
                  fill="none"
                  stroke="var(--border)"
                  strokeWidth={0.5}
                  opacity={0.6}
                />
              ))}
              {/* Spokes. */}
              {ratios.map((ratio, index) => {
                const edge = pointAt(index, count, MAX_SCORE);
                return (
                  <line
                    key={ratio.key}
                    x1={CENTRE}
                    y1={CENTRE}
                    x2={edge.x}
                    y2={edge.y}
                    stroke="var(--border)"
                    strokeWidth={0.5}
                    opacity={0.6}
                  />
                );
              })}
              <polygon
                points={polygon(benchmark)}
                fill="none"
                stroke={BENCHMARK_COLOR}
                strokeWidth={1}
                strokeDasharray="3 2"
              />
              <polygon
                points={polygon(actual)}
                fill={ACTUAL_COLOR}
                fillOpacity={0.18}
                stroke={ACTUAL_COLOR}
                strokeWidth={1.5}
                strokeLinejoin="round"
              />
              {actual.map((point, index) => (
                <circle
                  key={ratios[index].key}
                  cx={point.x}
                  cy={point.y}
                  r={1.6}
                  fill={ACTUAL_COLOR}
                />
              ))}
            </svg>
          </div>

          <ul className="min-w-0 flex-1 space-y-1.5">
            {ratios.map((ratio) => (
              <li key={ratio.key} className="flex items-center gap-2 text-sm">
                <span
                  className="min-w-0 flex-1 truncate"
                  title={ratio.hint ?? ratio.label}
                >
                  {ratio.label}
                </span>
                <span className="shrink-0 text-xs tabular-nums text-[var(--text-muted)]">
                  {formatRatioValue(ratio.value, ratio.unit)}
                </span>
                <span
                  className="w-14 shrink-0 text-right text-xs font-semibold tabular-nums"
                  style={{
                    color:
                      ratio.status === 'below'
                        ? 'var(--recovery-danger)'
                        : 'var(--recovery-success)',
                  }}
                  title="Score against the industry benchmark (1,00 x = at benchmark)"
                >
                  {ratio.score.toFixed(2)} x
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
