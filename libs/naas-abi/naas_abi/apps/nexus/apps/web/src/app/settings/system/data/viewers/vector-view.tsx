'use client';

/** An embedding: its shape at a glance, then metadata and payload. */
import { JsonTree } from './json-tree';

const BARS = 96;

function stats(values: number[]) {
  if (!values.length) return { min: 0, max: 0, mean: 0 };
  let min = Infinity;
  let max = -Infinity;
  let sum = 0;
  for (const v of values) {
    min = Math.min(min, v);
    max = Math.max(max, v);
    sum += v;
  }
  return { min, max, mean: sum / values.length };
}

export function VectorBars({ components }: { components: number[] }) {
  const shown = components.slice(0, BARS);
  const peak = Math.max(1e-9, ...shown.map((v) => Math.abs(v)));
  const width = 100 / Math.max(1, shown.length);
  return (
    <svg className="vector-bars" viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label="Vector components">
      <line x1="0" x2="100" y1="20" y2="20" className="vector-axis" />
      {shown.map((v, i) => {
        const h = (Math.abs(v) / peak) * 19;
        return (
          <rect
            key={i}
            x={i * width + width * 0.12}
            width={width * 0.76}
            y={v >= 0 ? 20 - h : 20}
            height={Math.max(h, 0.4)}
            className={v >= 0 ? 'vector-bar-pos' : 'vector-bar-neg'}
          />
        );
      })}
    </svg>
  );
}

export function VectorView({
  dimension,
  components,
  norm,
  metadata,
  payload,
}: {
  dimension: number;
  components: number[];
  norm?: number | null;
  metadata?: unknown;
  payload?: unknown;
}) {
  const s = stats(components);
  const hasMeta = metadata !== undefined && metadata !== null && Object.keys(metadata as object).length > 0;
  const hasPayload = payload !== undefined && payload !== null && Object.keys(payload as object).length > 0;
  return (
    <div className="vector">
      <div className="vector-card">
        <div className="vector-stats">
          <span>
            <strong>{dimension}</strong> dimensions
          </span>
          {norm !== null && norm !== undefined && (
            <span>
              norm <strong>{norm.toFixed(3)}</strong>
            </span>
          )}
          <span>
            min <strong>{s.min.toFixed(3)}</strong>
          </span>
          <span>
            max <strong>{s.max.toFixed(3)}</strong>
          </span>
        </div>
        <VectorBars components={components} />
        <p className="data-muted">
          {components.length < dimension
            ? `First ${Math.min(components.length, BARS)} of ${dimension} components`
            : `${Math.min(components.length, BARS)} components shown`}
        </p>
      </div>
      {hasPayload && (
        <section className="data-section">
          <h4 className="data-section-title">Payload</h4>
          <JsonTree value={payload} />
        </section>
      )}
      {hasMeta && (
        <section className="data-section">
          <h4 className="data-section-title">Metadata</h4>
          <JsonTree value={metadata} />
        </section>
      )}
    </div>
  );
}
