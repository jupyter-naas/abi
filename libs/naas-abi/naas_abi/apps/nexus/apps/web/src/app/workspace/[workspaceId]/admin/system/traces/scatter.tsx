'use client';

/** Search results as dots: when they started (x) against how long they took (y, log scale). */
import { absoluteTime } from '../data/data-model';
import { formatSpanMs } from './traces-model';
import type { TraceSummary } from './traces-types';

export function Scatter({ traces, onOpen }: { traces: TraceSummary[]; onOpen: (traceId: string) => void }) {
  if (traces.length < 2) return null;
  const times = traces.map((t) => Date.parse(t.start));
  const [t0, t1] = [Math.min(...times), Math.max(...times)];
  const logs = traces.map((t) => Math.log10(Math.max(t.duration_ms, 0.01)));
  const [d0, d1] = [Math.min(...logs), Math.max(...logs)];
  const x = (t: number) => (t1 === t0 ? 50 : 2 + ((t - t0) / (t1 - t0)) * 96);
  const y = (d: number) => (d1 === d0 ? 50 : 92 - ((d - d0) / (d1 - d0)) * 84);
  return (
    <div className="trace-scatter">
      <div className="trace-scatter-axis-y" aria-hidden="true">
        <span>{formatSpanMs(10 ** d1)}</span>
        <span>{formatSpanMs(10 ** d0)}</span>
      </div>
      <div className="trace-scatter-plot" role="group" aria-label="Traces by start time and duration">
        {traces.map((t, i) => (
          <button
            key={t.trace_id}
            type="button"
            // rounded-full keeps the dot round under org branding (square buttons).
            className={t.errors ? 'trace-dot trace-dot-error rounded-full' : 'trace-dot rounded-full'}
            style={{ left: `${x(times[i])}%`, top: `${y(logs[i])}%` }}
            title={`${t.root.service} ${t.root.name} · ${formatSpanMs(t.duration_ms)} · ${absoluteTime(t.start)}`}
            aria-label={`${t.root.name}, ${formatSpanMs(t.duration_ms)}`}
            onClick={() => onOpen(t.trace_id)}
          />
        ))}
      </div>
    </div>
  );
}
